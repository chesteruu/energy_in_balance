"""Energy in Balance Home Assistant integration."""

from __future__ import annotations

from typing import Any

from .const import DOMAIN

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Set up Energy in Balance from a config entry."""
    from .coordinator import EnergyInBalanceCoordinator

    coordinator = EnergyInBalanceCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: Any, entry: Any) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


__all__ = ["DOMAIN", "async_setup_entry", "async_unload_entry"]
