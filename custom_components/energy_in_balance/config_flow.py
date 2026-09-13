"""Config flow for Energy in Balance."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EnergyInBalanceApi, EnergyInBalanceApiError, EnergyInBalanceAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class EnergyInBalanceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Energy in Balance."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api = EnergyInBalanceApi(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                await api.async_login()
                await api.async_bootstrap()
                snapshot = await api.async_update(force_slow=True)
            except EnergyInBalanceAuthError:
                errors["base"] = "invalid_auth"
            except EnergyInBalanceApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(snapshot.site_id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=snapshot.display_name, data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        _ = entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if reauth_entry is None:
            return self.async_abort(reason="unknown")
        if user_input is not None:
            username = user_input.get(CONF_USERNAME, reauth_entry.data[CONF_USERNAME])
            api = EnergyInBalanceApi(
                username,
                user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                await api.async_login()
                await api.async_bootstrap()
            except EnergyInBalanceAuthError:
                errors["base"] = "invalid_auth"
            except EnergyInBalanceApiError:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EnergyInBalanceOptionsFlow(config_entry)


class EnergyInBalanceOptionsFlow(OptionsFlow):
    """Tune polling interval."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options.get(
            CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds())
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=30, max=600)
                    )
                }
            ),
        )
