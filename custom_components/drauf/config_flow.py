"""Config flow for the drauf integration: instance URL + API token."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DraufApiClient, DraufAuthError, DraufConnectionError, DraufError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_API_TOKEN): str,
    }
)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): str})


def normalize_url(raw: str) -> str:
    """Normalize the instance URL: default to https, drop trailing slashes."""
    value = raw.strip().rstrip("/")
    if not urlparse(value).scheme:
        value = f"https://{value}"
    return value


async def validate_input(hass: HomeAssistant, url: str, token: str) -> None:
    """Check the URL is a drauf server and the token can read the plan.

    GET /api/version is public and proves the URL; GET /api/plan/slots needs
    a token with the plan:read scope and proves the credentials.
    """
    client = DraufApiClient(async_get_clientsession(hass), url, token)
    await client.async_get_version()
    await client.async_get_slots()


class DraufConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the drauf config flow, including reauth on rejected tokens."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initial step: ask for instance URL and API token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            token = user_input[CONF_API_TOKEN].strip()
            errors = await self._async_validate(url, token)
            if not errors:
                await self.async_set_unique_id(url.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=urlparse(url).netloc or url,
                    data={CONF_URL: url, CONF_API_TOKEN: token},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth after the server rejected the stored token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a fresh token for the existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            token = user_input[CONF_API_TOKEN].strip()
            errors = await self._async_validate(entry.data[CONF_URL], token)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_TOKEN: token}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={CONF_URL: entry.data[CONF_URL]},
            errors=errors,
        )

    async def _async_validate(self, url: str, token: str) -> dict[str, str]:
        """Validate credentials, mapping failures to form error keys."""
        try:
            await validate_input(self.hass, url, token)
        except DraufAuthError:
            return {"base": "invalid_auth"}
        except DraufConnectionError:
            return {"base": "cannot_connect"}
        except DraufError:
            _LOGGER.exception("Unexpected error validating drauf credentials")
            return {"base": "unknown"}
        return {}
