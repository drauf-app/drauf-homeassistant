"""The drauf.get_plan action: full plan entries for a date range (#5).

Built for wall displays and other consumers that need more than the
calendar's summaries: every entry with slot name and order, link, image,
and cook. Cook display names need server support (drauf-app/drauf#105);
until then `cook.display_name` is null.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .api import DraufError
from .const import DOMAIN
from .coordinator import DraufConfigEntry, PlanEntry, parse_entries

SERVICE_GET_PLAN = "get_plan"

# The server refuses ranges longer than this (whole days between from and to).
MAX_RANGE_DAYS = 92

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"
ATTR_START_DAY = "start_day"
ATTR_WEEK_OFFSET = "week_offset"
ATTR_DAYS = "days"

GET_PLAN_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_START_DATE): cv.date,
        vol.Optional(ATTR_END_DATE): cv.date,
        vol.Optional(ATTR_START_DAY): vol.In(cv.WEEKDAYS),
        vol.Optional(ATTR_WEEK_OFFSET, default=0): vol.Coerce(int),
        vol.Optional(ATTR_DAYS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_RANGE_DAYS + 1)
        ),
    }
)


def _entry_payload(entry: PlanEntry) -> dict[str, Any]:
    """One plan entry in the response shape of #5."""
    return {
        "id": entry.id,
        "title": entry.title,
        "text": entry.text,
        "slot": entry.slot_name,
        "slot_id": entry.slot_id,
        "slot_order": entry.slot_order if entry.slot_id else None,
        "cook": {"id": entry.cook_id, "display_name": None} if entry.cook_id else None,
        "link": entry.link,
        "image_url": entry.image_url,
    }


def resolve_range(call_data: dict[str, Any], today: date) -> tuple[date, date]:
    """The [start, end] range a call asks for.

    An explicit start_date wins; otherwise the range starts at the most
    recent start_day (default: today), shifted by week_offset whole weeks —
    the web app's week logic ("Friday to Friday" = start_day fri, days 8).
    The end is end_date, or start + days - 1 (default 7 days).
    """
    start: date | None = call_data.get(ATTR_START_DATE)
    if start is None:
        start_day: str | None = call_data.get(ATTR_START_DAY)
        start = today
        if start_day is not None:
            start -= timedelta(days=(today.weekday() - cv.WEEKDAYS.index(start_day)) % 7)
        start += timedelta(weeks=call_data[ATTR_WEEK_OFFSET])
    end: date | None = call_data.get(ATTR_END_DATE)
    if end is None:
        end = start + timedelta(days=call_data.get(ATTR_DAYS, 7) - 1)
    if end < start:
        raise ServiceValidationError(f"end_date {end} is before start_date {start}")
    if (end - start).days > MAX_RANGE_DAYS:
        raise ServiceValidationError(
            f"Range {start}..{end} spans more than {MAX_RANGE_DAYS} days"
        )
    return start, end


def _target_entry(hass: HomeAssistant, call: ServiceCall) -> DraufConfigEntry:
    """The config entry a call targets: explicit id, or the only loaded one."""
    entry_id: str | None = call.data.get(ATTR_CONFIG_ENTRY_ID)
    loaded: list[DraufConfigEntry] = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if entry_id is not None:
        for entry in loaded:
            if entry.entry_id == entry_id:
                return entry
        raise ServiceValidationError(f"No loaded drauf config entry {entry_id}")
    if len(loaded) == 1:
        return loaded[0]
    if not loaded:
        raise ServiceValidationError("No drauf instance is set up")
    raise ServiceValidationError(
        "Several drauf instances are set up; pass config_entry_id"
    )


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the drauf actions."""

    async def get_plan(call: ServiceCall) -> ServiceResponse:
        coordinator = _target_entry(hass, call).runtime_data
        start, end = resolve_range(call.data, dt_util.now().date())
        try:
            raw_entries = await coordinator.client.async_get_entries(start, end)
        except DraufError as err:
            raise HomeAssistantError(f"Error talking to drauf: {err}") from err
        entries = parse_entries(raw_entries, coordinator.data.slots)
        days = []
        day = start
        while day <= end:
            days.append(
                {
                    "date": day.isoformat(),
                    "entries": [
                        _entry_payload(entry) for entry in entries if entry.date == day
                    ],
                }
            )
            day += timedelta(days=1)
        return {"start": start.isoformat(), "end": end.isoformat(), "days": days}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PLAN,
        get_plan,
        schema=GET_PLAN_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
