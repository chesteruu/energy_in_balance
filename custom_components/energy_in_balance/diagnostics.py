"""Diagnostics for Energy in Balance. Never include tokens or account PII."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostic data without credentials or customer PII."""
    _ = hass
    data = entry.runtime_data.data
    return {
        "site_id": data.site_id,
        "inverter_brand": data.inverter_brand,
        "inverter_model": data.inverter_model,
        "timezone": data.timezone,
        "currency": data.currency,
        "price_zone": data.price_zone,
        "operation_preference": data.operation_preference,
        "fcr_services": data.fcr_services,
        "online": data.online,
        "sensors": {
            "solar_power_w": data.solar_power_w,
            "battery_power_w": data.battery_power_w,
            "battery_soc": data.battery_soc,
            "grid_power_w": data.grid_power_w,
            "house_power_w": data.house_power_w,
            "spot_price": data.spot_price,
        },
    }
