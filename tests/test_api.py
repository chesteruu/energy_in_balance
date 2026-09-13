"""Unit tests for the Energy in Balance API helpers and client."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.energy_in_balance.api import (
    EnergyInBalanceApi,
    EnergyInBalanceAuthError,
    current_spot_price,
    house_power_w,
    latest_series_value,
    lifetime_energy_kwh,
    revenue_totals,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_latest_series_value() -> None:
    measurements = load_fixture("measurements.json")
    assert latest_series_value(measurements["Data"]["Soc"]) == 54.8
    assert latest_series_value(measurements["Data"]["SolarProductionPower"]) == 2400
    assert latest_series_value({}) is None
    assert latest_series_value(None) is None


def test_house_power_matches_har_energy_flow() -> None:
    flow = load_fixture("energyflow.json")
    # 2400 solar, -360 charging, -120 exporting => 1920 W house load
    assert house_power_w(flow["SolarNow"], flow["BatteryNow"], flow["GridNow"]) == 1920


def test_lifetime_energy_kwh_sums_yearly_wh() -> None:
    payload = {
        "Meters": [
            {
                "Measurements": [
                    {"Value": 1000000.0, "Date": "2024"},
                    {"Value": 500000.0, "Date": "2025"},
                ]
            }
        ]
    }
    assert lifetime_energy_kwh(payload) == 1500.0
    assert lifetime_energy_kwh({"Meters": []}) is None


def test_current_spot_price_picks_current_interval() -> None:
    payload = {
        "Currency": "SEK",
        "Prices": [
            {"Value": 0.10, "Date": "2026-09-13T10:00:00.000"},
            {"Value": 0.75, "Date": "2026-09-13T12:00:00.000"},
            {"Value": 1.20, "Date": "2026-09-13T13:00:00.000"},
        ],
    }
    now = datetime.fromisoformat("2026-09-13T12:30:00")
    assert current_spot_price(payload, now) == 0.75


def test_revenue_totals() -> None:
    payload = {
        "Revenue": [
            {"ServiceName": "FCR-D", "Date": "2026-09-12", "NetRevenue": 2.0},
            {"ServiceName": "FCR-D", "Date": "2026-09-13", "NetRevenue": 2.49},
        ]
    }
    today, week = revenue_totals(payload, datetime(2026, 9, 13))
    assert today == pytest.approx(2.49)
    assert week == pytest.approx(4.49)


def test_build_snapshot_from_har_payloads() -> None:
    api = EnergyInBalanceApi("user@example.com", "secret")
    api._site_id = 25210
    api._serial = "abc123serial"
    api._display_name = "Test House"
    api._timezone = "Europe/Stockholm"
    api._battery_capacity_kwh = 10.0
    api._site = load_fixture("site.json")
    api._slow_cache = {
        "energy": {"solar": 22.81, "charge": 1.0, "discharge": 2.0, "import": 3.0, "export": 4.0},
        "spot": {
            "Currency": "SEK",
            "Prices": [{"Value": 0.75, "Date": "2026-09-13T00:00:00.000"}],
        },
        "revenue": {
            "Revenue": [
                {"ServiceName": "FCR-D", "Date": "2026-09-13", "NetRevenue": 2.49}
            ]
        },
        "price_zone": "SE3",
        "preference": {"PreferenceId": "co"},
    }

    snapshot = api._build_snapshot(
        load_fixture("energyflow.json"),
        [
            {
                "SiteId": 25210,
                "DisplayName": "Test House",
                "Service": ["fcrdup", "fcrddown"],
                "OperationPreference": "co",
                "LastSeenInverter": "2026-09-13T10:42:23Z",
                "LastSeenCm10": "2026-09-13T10:42:23Z",
                "Retailer": {"DisplayName": "Test Retailer"},
            }
        ],
        load_fixture("measurements.json"),
    )

    assert snapshot.solar_power_w == 2400
    assert snapshot.battery_power_w == -360
    assert snapshot.battery_charge_power_w == 360
    assert snapshot.battery_discharge_power_w == 0
    assert snapshot.battery_soc == 54.8
    assert snapshot.grid_power_w == -120
    assert snapshot.grid_import_power_w == 0
    assert snapshot.grid_export_power_w == 120
    assert snapshot.house_power_w == 1920
    assert snapshot.inverter_brand == "SAJ"
    assert snapshot.inverter_model == "H2-10K-T2"
    assert snapshot.battery_capacity_kwh == 10.0
    assert snapshot.price_zone == "SE3"
    assert snapshot.operation_preference == "co"
    assert snapshot.fcr_services == ["fcrdup", "fcrddown"]
    assert snapshot.solar_energy_kwh == 22.81


@pytest.mark.asyncio
async def test_login_uses_basic_auth_and_stores_jwt() -> None:
    response = MagicMock()
    response.status = 200
    response.text = AsyncMock(
        return_value='{"LoggedIn": true, "JwtToken": "jwt-token", "RefreshToken": "refresh"}'
    )

    session = MagicMock()
    session.closed = False
    session.post.return_value.__aenter__ = AsyncMock(return_value=response)
    session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    api = EnergyInBalanceApi("user@example.com", "secret", session=session)
    await api.async_login()

    assert api._jwt == "jwt-token"
    headers = session.post.call_args.kwargs["headers"]
    assert headers["authorization"].startswith("Basic ")
    assert session.post.call_args.kwargs["json"] == {"OneTimePassword": ""}
    assert session.post.call_args.kwargs["params"] == {"audience": "eib"}


@pytest.mark.asyncio
async def test_safe_json_accepts_plain_price_zone() -> None:
    from custom_components.energy_in_balance.api import _safe_json

    response = MagicMock()
    response.text = AsyncMock(return_value="SE3")
    assert await _safe_json(response) == "SE3"


@pytest.mark.asyncio
async def test_login_rejects_bad_credentials() -> None:
    response = MagicMock()
    response.status = 401
    response.text = AsyncMock(return_value='{"LoggedIn": false}')

    session = MagicMock()
    session.closed = False
    session.post.return_value.__aenter__ = AsyncMock(return_value=response)
    session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    api = EnergyInBalanceApi("user@example.com", "wrong", session=session)
    with pytest.raises(EnergyInBalanceAuthError):
        await api.async_login()
