"""Today/tomorrow convenience sensors over the plan.

State is a short human-readable summary ("Frühstück: Pancakes · Abendessen:
Curry"); the structured entries live in attributes, ready for dashboards and
TTS announcements.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import DraufConfigEntry, DraufCoordinator, PlanEntry

# HA caps sensor states at 255 characters.
MAX_STATE_LENGTH = 255


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DraufConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the today and tomorrow sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            DraufDaySensor(coordinator, entry, "today", 0),
            DraufDaySensor(coordinator, entry, "tomorrow", 1),
        ]
    )


def _label(entry: PlanEntry) -> str:
    """One entry as "Slot: Title" (or just the title)."""
    if entry.slot_name:
        return f"{entry.slot_name}: {entry.title}" if entry.title else entry.slot_name
    return entry.title


class DraufDaySensor(CoordinatorEntity[DraufCoordinator], SensorEntity):
    """Summarizes one day's plan entries."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DraufCoordinator,
        entry: DraufConfigEntry,
        key: str,
        day_offset: int,
    ) -> None:
        super().__init__(coordinator)
        self._day_offset = day_offset
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    def _entries(self) -> list[PlanEntry]:
        day = dt_util.now().date() + timedelta(days=self._day_offset)
        return self.coordinator.data.entries_on(day)

    @property
    def native_value(self) -> str | None:
        """All of the day's entries joined, or None when nothing is planned."""
        entries = self._entries()
        if not entries:
            return None
        state = " · ".join(_label(entry) for entry in entries)
        if len(state) > MAX_STATE_LENGTH:
            state = f"{state[: MAX_STATE_LENGTH - 1]}…"
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Structured entries for templates, dashboards, and TTS."""
        day = dt_util.now().date() + timedelta(days=self._day_offset)
        return {
            "date": day.isoformat(),
            "count": len(self._entries()),
            "entries": [
                {
                    "slot": entry.slot_name,
                    "title": entry.title,
                    "text": entry.text,
                    "link": entry.link,
                    "image_url": entry.image_url,
                    "cook_id": entry.cook_id,
                }
                for entry in self._entries()
            ],
        }
