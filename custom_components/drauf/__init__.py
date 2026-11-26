"""The drauf integration: the Wochenplan in Home Assistant, read-only."""

from __future__ import annotations

from homeassistant.const import CONF_API_TOKEN, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .api import DraufApiClient, DraufAuthError, DraufConnectionError, DraufError
from .const import DOMAIN
from .coordinator import DraufConfigEntry, DraufCoordinator
from .services import async_setup_services

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the drauf actions."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DraufConfigEntry) -> bool:
    """Set up a drauf instance from a config entry."""
    client = DraufApiClient(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_API_TOKEN]
    )

    try:
        version = await client.async_get_version()
    except DraufAuthError as err:
        raise ConfigEntryAuthFailed from err
    except (DraufConnectionError, DraufError) as err:
        raise ConfigEntryNotReady(f"Cannot reach drauf at {client.base_url}") from err

    coordinator = DraufCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="drauf",
        manufacturer="drauf",
        sw_version=version.get("version"),
        configuration_url=client.base_url,
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DraufConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
