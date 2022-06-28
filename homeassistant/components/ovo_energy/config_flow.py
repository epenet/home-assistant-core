"""Config flow to configure the OVO Energy integration."""
from collections.abc import Mapping
from typing import Any

import aiohttp
from ovoenergy.ovoenergy import OVOEnergy
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})
USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class OVOEnergyFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a OVO Energy config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the flow."""
        self.username = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            client = OVOEnergy()
            try:
                authenticated = await client.authenticate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            else:
                if authenticated:
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=client.username,
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )

                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        errors = {}

        if entry_data and entry_data.get(CONF_USERNAME):
            self.username = entry_data[CONF_USERNAME]

        self.context["title_placeholders"] = {CONF_USERNAME: self.username}

        if entry_data is not None and entry_data.get(CONF_PASSWORD) is not None:
            client = OVOEnergy()
            try:
                authenticated = await client.authenticate(
                    self.username, entry_data[CONF_PASSWORD]
                )
            except aiohttp.ClientError:
                errors["base"] = "connection_error"
            else:
                if authenticated:
                    entry = await self.async_set_unique_id(self.username)
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            CONF_USERNAME: self.username,
                            CONF_PASSWORD: entry_data[CONF_PASSWORD],
                        },
                    )
                    return self.async_abort(reason="reauth_successful")

                errors["base"] = "authorization_error"

        return self.async_show_form(
            step_id="reauth", data_schema=REAUTH_SCHEMA, errors=errors
        )
