"""Data update coordinator for Energy in Balance."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EnergyInBalanceApi,
    EnergyInBalanceApiError,
    EnergyInBalanceAuthError,
    SiteSnapshot,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EnergyInBalanceCoordinator(DataUpdateCoordinator[SiteSnapshot]):
    """Poll Checkwatt and cache the latest site snapshot."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = entry.options.get(
            CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds())
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.config_entry = entry
        self.api = EnergyInBalanceApi(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            session=async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> SiteSnapshot:
        try:
            return await self.api.async_update()
        except EnergyInBalanceAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EnergyInBalanceApiError as err:
            raise UpdateFailed(str(err)) from err
