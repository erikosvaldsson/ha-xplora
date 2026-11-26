"""Config + options flow for myXplora."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import XploraApi, XploraAuthError
from .const import (
    CONF_COUNTRY_CODE,
    CONF_LANGUAGE,
    CONF_PHONE,
    CONF_SCAN_MINUTES,
    CONF_TIMEZONE,
    DEFAULT_LANGUAGE,
    DEFAULT_SCAN_MINUTES,
    DEFAULT_TIMEZONE,
    DOMAIN,
    MIN_SCAN_MINUTES,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COUNTRY_CODE, default="+46"): str,
        vol.Optional(CONF_EMAIL, default=""): str,
        vol.Optional(CONF_PHONE, default=""): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): str,
        vol.Optional(CONF_TIMEZONE, default=DEFAULT_TIMEZONE): str,
    }
)


class XploraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_EMAIL) and not user_input.get(CONF_PHONE):
                errors["base"] = "need_email_or_phone"
            else:
                api = XploraApi(
                    country_code=user_input[CONF_COUNTRY_CODE],
                    phone=user_input.get(CONF_PHONE, ""),
                    email=user_input.get(CONF_EMAIL, ""),
                    password=user_input[CONF_PASSWORD],
                    language=user_input.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
                    timezone=user_input.get(CONF_TIMEZONE, DEFAULT_TIMEZONE),
                    session=async_get_clientsession(self.hass),
                )
                try:
                    await api.async_login()
                except XploraAuthError:
                    errors["base"] = "invalid_auth"
                except Exception:  # noqa: BLE001
                    errors["base"] = "cannot_connect"
                else:
                    unique = user_input.get(CONF_EMAIL) or (
                        user_input[CONF_COUNTRY_CODE] + user_input.get(CONF_PHONE, "")
                    )
                    await self.async_set_unique_id(unique.lower())
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="Xplora", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> XploraOptionsFlow:
        return XploraOptionsFlow()


class XploraOptionsFlow(OptionsFlow):
    """Adjust the (deliberately slow) scan interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(CONF_SCAN_MINUTES, DEFAULT_SCAN_MINUTES)
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_MINUTES, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_MINUTES, max=1440)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
