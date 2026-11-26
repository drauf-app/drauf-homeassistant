"""Update coordinator polling the drauf plan."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DraufApiClient, DraufAuthError, DraufError
from .const import DOMAIN, FUTURE_DAYS, PAST_DAYS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Entries without a slot sort after all labeled ones.
_NO_SLOT_ORDER = 10_000_000


@dataclass(frozen=True)
class PlanEntry:
    """One plan entry, with its slot resolved to a name."""

    id: str
    date: date
    slot_id: str | None
    slot_name: str | None
    slot_order: int
    text: str | None
    link: str | None
    image_url: str | None
    cook_id: str | None

    @property
    def title(self) -> str:
        """Human-readable title: the text, falling back to the bare link."""
        return self.text or self.link or ""


@dataclass
class DraufData:
    """Snapshot of the plan window around today."""

    entries: list[PlanEntry] = field(default_factory=list)
    slot_names: dict[str, str] = field(default_factory=dict)

    def entries_on(self, day: date) -> list[PlanEntry]:
        """The day's entries, in slot order."""
        return [entry for entry in self.entries if entry.date == day]


type DraufConfigEntry = ConfigEntry[DraufCoordinator]


class DraufCoordinator(DataUpdateCoordinator[DraufData]):
    """Polls slots and entries for a window around today."""

    config_entry: DraufConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: DraufConfigEntry, client: DraufApiClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> DraufData:
        today = dt_util.now().date()
        start = today - timedelta(days=PAST_DAYS)
        end = today + timedelta(days=FUTURE_DAYS)
        try:
            slots = await self.client.async_get_slots()
            raw_entries = await self.client.async_get_entries(start, end)
        except DraufAuthError as err:
            raise ConfigEntryAuthFailed("API token was rejected") from err
        except DraufError as err:
            raise UpdateFailed(f"Error talking to drauf: {err}") from err

        slot_names: dict[str, str] = {}
        slot_orders: dict[str, int] = {}
        for slot in slots:
            slot_names[slot["id"]] = slot["name"]
            slot_orders[slot["id"]] = slot.get("sortOrder", 0)

        entries: list[PlanEntry] = []
        for raw in raw_entries:
            slot_id = raw.get("slotId")
            try:
                entry_date = date.fromisoformat(raw["date"])
            except (KeyError, ValueError):
                continue
            entries.append(
                PlanEntry(
                    id=raw["id"],
                    date=entry_date,
                    slot_id=slot_id,
                    slot_name=slot_names.get(slot_id) if slot_id else None,
                    slot_order=slot_orders.get(slot_id, _NO_SLOT_ORDER)
                    if slot_id
                    else _NO_SLOT_ORDER,
                    text=raw.get("text"),
                    link=raw.get("link"),
                    image_url=raw.get("imageUrl"),
                    cook_id=raw.get("cookId"),
                )
            )
        entries.sort(key=lambda entry: (entry.date, entry.slot_order, entry.id))
        return DraufData(entries=entries, slot_names=slot_names)
