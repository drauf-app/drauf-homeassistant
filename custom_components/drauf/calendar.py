"""Calendar entity exposing plan entries as all-day events."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import DraufConfigEntry, DraufCoordinator, PlanEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DraufConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the plan calendar."""
    async_add_entities([DraufCalendar(entry.runtime_data, entry)])


def _event_for(entry: PlanEntry) -> CalendarEvent:
    """Map a plan entry to an all-day calendar event."""
    summary = entry.title
    if entry.slot_name:
        summary = f"{entry.slot_name}: {summary}" if summary else entry.slot_name
    description_parts = [part for part in (entry.link, entry.cook_id and f"Cook: {entry.cook_id}") if part]
    return CalendarEvent(
        summary=summary,
        start=entry.date,
        end=entry.date + timedelta(days=1),
        description="\n".join(description_parts) or None,
        uid=entry.id,
    )


class DraufCalendar(CoordinatorEntity[DraufCoordinator], CalendarEntity):
    """Read-only calendar over the household's Wochenplan."""

    _attr_has_entity_name = True
    _attr_translation_key = "plan"

    def __init__(self, coordinator: DraufCoordinator, entry: DraufConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_plan"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def event(self) -> CalendarEvent | None:
        """The next (or ongoing) event: today's first entry, else the next day's."""
        today = dt_util.now().date()
        for entry in self.coordinator.data.entries:
            if entry.date >= today:
                return _event_for(entry)
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Events in the requested range, served from the polled window."""
        start = dt_util.as_local(start_date).date()
        end = dt_util.as_local(end_date).date()
        return [
            _event_for(entry)
            for entry in self.coordinator.data.entries
            if start <= entry.date <= end
        ]
