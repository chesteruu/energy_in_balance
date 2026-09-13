"""Async client for the Checkwatt Energy in Balance portal API."""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

from .const import (
    API_AUDIENCE,
    API_BASE,
    API_ORIGIN,
    INSTALL_CHARGE,
    INSTALL_DISCHARGE,
    INSTALL_EXPORT,
    INSTALL_IMPORT,
    INSTALL_SOC,
    INSTALL_SOLAR,
    MEASUREMENT_TYPES,
    REQUEST_TIMEOUT,
    SLOW_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class EnergyInBalanceError(Exception):
    """Base error for the Energy in Balance client."""


class EnergyInBalanceAuthError(EnergyInBalanceError):
    """Raised when login fails or the session is no longer valid."""


class EnergyInBalanceApiError(EnergyInBalanceError):
    """Raised when the Checkwatt API returns an unexpected error."""


@dataclass(slots=True)
class SiteSnapshot:
    """Latest site readings used by Home Assistant sensors."""

    site_id: int
    serial: str
    display_name: str
    timezone: str
    currency: str
    inverter_brand: str | None = None
    inverter_model: str | None = None
    inverter_power_w: float | None = None
    battery_capacity_kwh: float | None = None
    solar_power_w: float | None = None
    battery_power_w: float | None = None
    battery_charge_power_w: float | None = None
    battery_discharge_power_w: float | None = None
    battery_soc: float | None = None
    grid_power_w: float | None = None
    grid_import_power_w: float | None = None
    grid_export_power_w: float | None = None
    house_power_w: float | None = None
    solar_energy_kwh: float | None = None
    battery_charge_energy_kwh: float | None = None
    battery_discharge_energy_kwh: float | None = None
    grid_import_energy_kwh: float | None = None
    grid_export_energy_kwh: float | None = None
    spot_price: float | None = None
    fcr_revenue_today: float | None = None
    fcr_revenue_week: float | None = None
    price_zone: str | None = None
    operation_preference: str | None = None
    fcr_services: list[str] = field(default_factory=list)
    last_seen_inverter: str | None = None
    last_seen_logger: str | None = None
    retailer: str | None = None
    dso: str | None = None
    online: bool | None = None
    updated: datetime | None = None


def latest_series_value(series: dict[str, Any] | None) -> float | None:
    """Return the newest numeric sample from a timestamp-keyed series."""
    if not series:
        return None
    try:
        newest_key = max(series)
    except ValueError:
        return None
    value = series.get(newest_key)
    if value is None:
        return None
    return float(value)


def lifetime_energy_kwh(payload: dict[str, Any] | None) -> float | None:
    """Sum yearly Checkwatt series values (Wh) into lifetime kWh."""
    if not payload:
        return None
    meters = payload.get("Meters") or []
    if not meters:
        return None
    measurements = meters[0].get("Measurements") or []
    total_wh = 0.0
    found = False
    for point in measurements:
        value = point.get("Value")
        if value is None:
            continue
        total_wh += float(value)
        found = True
    if not found:
        return None
    return round(total_wh / 1000.0, 3)


def house_power_w(
    solar_w: float | None,
    battery_w: float | None,
    grid_w: float | None,
) -> float | None:
    """Derive house load from EIB signed energy-flow convention.

    Energy-flow signs observed from the dashboard:
    - solar is production (positive)
    - battery is negative while charging
    - grid is negative while exporting
    so house = solar + battery + grid.
    """
    if solar_w is None and battery_w is None and grid_w is None:
        return None
    return (solar_w or 0.0) + (battery_w or 0.0) + (grid_w or 0.0)


def current_spot_price(
    payload: dict[str, Any] | None, now: datetime | None = None
) -> float | None:
    """Pick the spot-price interval that contains ``now``."""
    if not payload:
        return None
    prices = payload.get("Prices") or []
    if not prices:
        return None
    current = now or datetime.now()
    chosen: tuple[datetime, float] | None = None
    for item in prices:
        raw = item.get("Date")
        value = item.get("Value")
        if raw is None or value is None:
            continue
        stamp = _parse_datetime(raw)
        if stamp is None:
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=current.tzinfo)
        if current.tzinfo and stamp.tzinfo:
            comparable = current
        else:
            comparable = current.replace(tzinfo=None)
            stamp = stamp.replace(tzinfo=None)
        if stamp <= comparable and (chosen is None or stamp > chosen[0]):
            chosen = (stamp, float(value))
    if chosen:
        return chosen[1]
    return float(prices[0]["Value"])


def revenue_totals(
    payload: dict[str, Any] | None, today: datetime | None = None
) -> tuple[float | None, float | None]:
    """Return today's and the payload window's FCR net revenue."""
    if not payload:
        return None, None
    rows = payload.get("Revenue") or []
    if not rows:
        return None, None
    day = (today or datetime.now()).date()
    today_total = 0.0
    week_total = 0.0
    saw_today = False
    for row in rows:
        value = row.get("NetRevenue")
        if value is None:
            continue
        amount = float(value)
        week_total += amount
        raw = row.get("Date")
        stamp = _parse_datetime(raw) if raw else None
        if stamp and stamp.date() == day:
            today_total += amount
            saw_today = True
    return (today_total if saw_today else None, week_total)


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class EnergyInBalanceApi:
    """Talk to api.checkwatt.se the same way energyinbalance.se does."""

    def __init__(
        self,
        username: str,
        password: str,
        session: ClientSession | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._owns_session = session is None
        self._jwt: str | None = None
        self._refresh_token: str | None = None
        self._site_id: int | None = None
        self._serial: str | None = None
        self._display_name: str | None = None
        self._timezone = "Europe/Stockholm"
        self._currency = "SEK"
        self._meter_ids: dict[str, int] = {}
        self._battery_capacity_kwh: float | None = None
        self._site: dict[str, Any] = {}
        self._status: dict[str, Any] = {}
        self._slow_cache: dict[str, Any] = {}
        self._slow_fetched_at: datetime | None = None

    async def async_close(self) -> None:
        """Close the session if this client created it."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def async_login(self) -> None:
        """Authenticate with HTTP Basic + empty one-time password."""
        session = await self._session_or_create()
        credentials = base64.b64encode(
            f"{self._username}:{self._password}".encode()
        ).decode()
        headers = {
            **self._base_headers(),
            "authorization": f"Basic {credentials}",
        }
        try:
            async with session.post(
                f"{API_BASE}/user/Login",
                params={"audience": API_AUDIENCE},
                headers=headers,
                json={"OneTimePassword": ""},
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                payload = await _safe_json(response)
                if response.status == 401:
                    raise EnergyInBalanceAuthError("Invalid Energy in Balance credentials")
                if response.status >= 400:
                    raise EnergyInBalanceApiError(
                        f"Login failed with HTTP {response.status}"
                    )
        except (ClientError, TimeoutError) as err:
            raise EnergyInBalanceApiError(f"Login request failed: {err}") from err

        if not payload.get("LoggedIn") or not payload.get("JwtToken"):
            raise EnergyInBalanceAuthError("Energy in Balance login was rejected")
        self._jwt = payload["JwtToken"]
        self._refresh_token = payload.get("RefreshToken")

    async def async_bootstrap(self) -> None:
        """Resolve site id, serial, and meter map after login."""
        customer = await self._request("GET", "/controlpanel/CustomerDetail")
        meters = customer.get("Meter") or []
        soc = _first_meter(meters, INSTALL_SOC) or (meters[0] if meters else None)
        if not soc:
            raise EnergyInBalanceApiError("No meters were returned for this account")

        serial = soc.get("RpiSerial")
        if not serial:
            raise EnergyInBalanceApiError("The account has no logger serial number")

        self._serial = serial
        self._display_name = soc.get("DisplayName") or "Energy in Balance"
        self._battery_capacity_kwh = _as_float(soc.get("BatteryCapacityKwh"))
        self._meter_ids = {
            key: meter["Id"]
            for key, install in (
                (INSTALL_SOC, INSTALL_SOC),
                (INSTALL_SOLAR, INSTALL_SOLAR),
                (INSTALL_CHARGE, INSTALL_CHARGE),
                (INSTALL_DISCHARGE, INSTALL_DISCHARGE),
                (INSTALL_IMPORT, INSTALL_IMPORT),
                (INSTALL_EXPORT, INSTALL_EXPORT),
            )
            if (meter := _first_meter(meters, install))
        }

        site_lookup = await self._request(
            "GET", "/Site/SiteIdBySerial", params={"serial": serial}
        )
        site_id = site_lookup.get("SiteId")
        if not site_id:
            raise EnergyInBalanceApiError("Could not resolve Checkwatt site id")
        self._site_id = int(site_id)

        self._site = await self._request("GET", f"/site/{self._site_id}")
        self._timezone = self._site.get("TimeZone") or self._timezone
        self._currency = self._site.get("Currency") or self._currency

    async def async_update(self, *, force_slow: bool = False) -> SiteSnapshot:
        """Fetch live power data and, periodically, energy/price totals."""
        if self._site_id is None or self._serial is None:
            await self.async_login()
            await self.async_bootstrap()

        assert self._site_id is not None
        assert self._serial is not None

        flow, statuses, measurements = await self._gather_live()
        if force_slow or self._should_refresh_slow():
            await self._refresh_slow()

        snapshot = self._build_snapshot(flow, statuses, measurements)
        snapshot.updated = datetime.now(timezone.utc)
        return snapshot

    async def _gather_live(
        self,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        flow, statuses, measurements = await asyncio.gather(
            self._request("GET", "/ems/energyflow"),
            self._request("GET", "/site/Statuses", params={"serial": self._serial}),
            self._request_measurements(),
        )
        return flow, statuses if isinstance(statuses, list) else [], measurements

    async def _request_measurements(self) -> dict[str, Any]:
        tz_name = self._timezone
        try:
            zone = ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001 - fall back if tzdata is incomplete
            zone = timezone.utc
            tz_name = "UTC"
        now = datetime.now(zone).replace(second=0, microsecond=0)
        start = now - timedelta(minutes=10)
        params = [
            ("resolution", "Minute"),
            ("from", start.strftime("%Y-%m-%dT%H:%M:%S")),
            ("to", now.strftime("%Y-%m-%dT%H:%M:%S")),
            ("timeZone", tz_name),
        ]
        for data_type in MEASUREMENT_TYPES:
            params.append(("dataType", data_type))
        return await self._request(
            "GET", f"/SiteMeasurements/{self._site_id}/Data", params=params
        )

    def _should_refresh_slow(self) -> bool:
        if self._slow_fetched_at is None:
            return True
        return datetime.now(timezone.utc) - self._slow_fetched_at >= SLOW_SCAN_INTERVAL

    async def _refresh_slow(self) -> None:
        year = datetime.now().year
        price_zone = await self._request("GET", "/ems/pricezone")
        if isinstance(price_zone, str):
            zone = price_zone
        else:
            zone = (price_zone or {}).get("Zone") or "SE3"

        async def _series(install: str) -> float | None:
            meter_id = self._meter_ids.get(install)
            if not meter_id:
                return None
            payload = await self._request(
                "GET",
                "/datagrouping/series",
                params={
                    "grouping": 3,
                    "fromdate": 2000,
                    "todate": year,
                    "meterId": meter_id,
                },
            )
            return lifetime_energy_kwh(payload)

        solar_e, charge_e, discharge_e, import_e, export_e = await asyncio.gather(
            _series(INSTALL_SOLAR),
            _series(INSTALL_CHARGE),
            _series(INSTALL_DISCHARGE),
            _series(INSTALL_IMPORT),
            _series(INSTALL_EXPORT),
        )
        energy = {
            "solar": solar_e,
            "charge": charge_e,
            "discharge": discharge_e,
            "import": import_e,
            "export": export_e,
        }

        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        week_ago = today - timedelta(days=6)
        spot = await self._request(
            "GET",
            "/ems/spotprice",
            params={
                "zone": zone,
                "fromDate": today.isoformat(),
                "toDate": tomorrow.isoformat(),
                "siteId": 0,
            },
        )
        revenue = await self._request(
            "GET",
            f"/revenue/{self._site_id}",
            params={
                "from": week_ago.isoformat(),
                "to": today.isoformat(),
                "resolution": "day",
            },
        )
        try:
            preference = await self._request(
                "GET", f"/site/{self._site_id}/operation-preference"
            )
        except EnergyInBalanceApiError:
            preference = {}

        self._slow_cache = {
            "energy": energy,
            "spot": spot if isinstance(spot, dict) else {},
            "revenue": revenue if isinstance(revenue, dict) else {},
            "price_zone": zone,
            "preference": preference if isinstance(preference, dict) else {},
        }
        self._slow_fetched_at = datetime.now(timezone.utc)

    def _build_snapshot(
        self,
        flow: dict[str, Any],
        statuses: list[dict[str, Any]],
        measurements: dict[str, Any],
    ) -> SiteSnapshot:
        series = (measurements or {}).get("Data") or {}
        solar = _coalesce(
            latest_series_value(series.get("SolarProductionPower")),
            _as_float(flow.get("SolarNow")),
        )
        charge = latest_series_value(series.get("BatteryChargePower"))
        discharge = latest_series_value(series.get("BatteryDischargePower"))
        bought = latest_series_value(series.get("BoughtPower"))
        sold = latest_series_value(series.get("SoldPower"))
        soc = _coalesce(
            latest_series_value(series.get("Soc")),
            _as_float(flow.get("BatterySoC")),
        )

        battery = _as_float(flow.get("BatteryNow"))
        if battery is None and (charge is not None or discharge is not None):
            battery = (discharge or 0.0) - (charge or 0.0)
        if charge is None and battery is not None:
            charge = max(-battery, 0.0)
        if discharge is None and battery is not None:
            discharge = max(battery, 0.0)

        grid = _as_float(flow.get("GridNow"))
        if grid is None and (bought is not None or sold is not None):
            grid = (bought or 0.0) - (sold or 0.0)
        if bought is None and grid is not None:
            bought = max(grid, 0.0)
        if sold is None and grid is not None:
            sold = max(-grid, 0.0)

        status = next((item for item in statuses if item.get("SiteId") == self._site_id), None)
        if status is None and statuses:
            status = statuses[0]
        self._status = status or {}

        inverter = (self._site or {}).get("InverterModel") or {}
        energy = self._slow_cache.get("energy") or {}
        spot_payload = self._slow_cache.get("spot") or {}
        try:
            zoneinfo = ZoneInfo(self._timezone)
        except Exception:  # noqa: BLE001
            zoneinfo = timezone.utc
        last_seen = self._status.get("LastSeenInverter")
        online = None
        if last_seen:
            stamp = _parse_datetime(last_seen)
            if stamp:
                online = datetime.now(timezone.utc) - stamp <= timedelta(minutes=15)

        fcr_today, fcr_week = revenue_totals(
            self._slow_cache.get("revenue"), datetime.now(zoneinfo)
        )

        return SiteSnapshot(
            site_id=self._site_id or 0,
            serial=self._serial or "",
            display_name=self._display_name
            or self._status.get("DisplayName")
            or "Energy in Balance",
            timezone=self._timezone,
            currency=self._site.get("Currency") or spot_payload.get("Currency") or "SEK",
            inverter_brand=inverter.get("Brand"),
            inverter_model=inverter.get("Model"),
            inverter_power_w=_as_float(inverter.get("PowerWatt")),
            battery_capacity_kwh=self._battery_capacity_kwh,
            solar_power_w=solar,
            battery_power_w=battery,
            battery_charge_power_w=charge,
            battery_discharge_power_w=discharge,
            battery_soc=soc,
            grid_power_w=grid,
            grid_import_power_w=bought,
            grid_export_power_w=sold,
            house_power_w=house_power_w(solar, battery, grid),
            solar_energy_kwh=energy.get("solar"),
            battery_charge_energy_kwh=energy.get("charge"),
            battery_discharge_energy_kwh=energy.get("discharge"),
            grid_import_energy_kwh=energy.get("import"),
            grid_export_energy_kwh=energy.get("export"),
            spot_price=current_spot_price(spot_payload, datetime.now(zoneinfo)),
            fcr_revenue_today=fcr_today,
            fcr_revenue_week=fcr_week,
            price_zone=self._slow_cache.get("price_zone"),
            operation_preference=(self._slow_cache.get("preference") or {}).get(
                "PreferenceId"
            )
            or self._status.get("OperationPreference"),
            fcr_services=list(self._status.get("Service") or []),
            last_seen_inverter=self._status.get("LastSeenInverter"),
            last_seen_logger=self._status.get("LastSeenCm10"),
            retailer=((self._status.get("Retailer") or {}).get("DisplayName")),
            dso=((self._site.get("Dso") or {}).get("DisplayName")),
            online=online,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Any | None = None,
        json_data: Any | None = None,
        retry: bool = True,
    ) -> Any:
        if not self._jwt:
            await self.async_login()
        session = await self._session_or_create()
        headers = {
            **self._base_headers(),
            "authorization": f"Bearer {self._jwt}",
        }
        try:
            async with session.request(
                method,
                f"{API_BASE}{path}",
                params=params,
                json=json_data,
                headers=headers,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                if response.status == 401 and retry:
                    _LOGGER.debug("JWT rejected, logging in again")
                    await self.async_login()
                    return await self._request(
                        method,
                        path,
                        params=params,
                        json_data=json_data,
                        retry=False,
                    )
                if response.status == 401:
                    raise EnergyInBalanceAuthError("Energy in Balance session expired")
                if response.status >= 400:
                    raise EnergyInBalanceApiError(
                        f"{method} {path} failed with HTTP {response.status}"
                    )
                if response.status == 204:
                    return {}
                return await _safe_json(response)
        except (ClientResponseError, ClientError, TimeoutError) as err:
            raise EnergyInBalanceApiError(f"{method} {path} failed: {err}") from err

    async def _session_or_create(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession()
            self._owns_session = True
        return self._session

    @staticmethod
    def _base_headers() -> dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": API_ORIGIN,
            "referer": f"{API_ORIGIN}/",
            "wslog-platform": "EIB",
        }


def _first_meter(meters: list[dict[str, Any]], install_type: str) -> dict[str, Any] | None:
    return next(
        (meter for meter in meters if meter.get("InstallationType") == install_type),
        None,
    )


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coalesce(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


async def _safe_json(response: Any) -> Any:
    """Parse JSON, or return raw text for endpoints like /ems/pricezone (SE3)."""
    import json

    text = await response.text()
    if not text:
        return {}
    try:
        return json.loads(text)
    except ValueError:
        return text.strip()
