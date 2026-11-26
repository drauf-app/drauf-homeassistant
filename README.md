# drauf for Home Assistant

Brings the [drauf](https://github.com/drauf-app/drauf) **Wochenplan** into Home Assistant — read-only.

- **Calendar** `calendar.drauf_wochenplan`: every plan entry as an all-day event (`Abendessen: Lasagne`), ready for calendar cards and automations.
- **Sensors** `sensor.drauf_today` / `sensor.drauf_tomorrow`: the day's entries as a short summary state, with the structured entries (slot, title, link, image, cook) in attributes — ready for dashboards and TTS announcements.

The integration polls the server every 5 minutes (the plan changes rarely) over a window from 7 days back to 60 days ahead.

## Requirements

- A reachable drauf server with **API token support** ([drauf#97](https://github.com/drauf-app/drauf/issues/97), first release after v0.1.9).
- An **API token with the `plan:read` scope**, created in drauf under *Settings → API tokens*. The integration is read-only by design and needs no other scope.
- Home Assistant 2024.11 or newer.

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → *Custom repositories* → add `https://github.com/drauf-app/drauf-homeassistant` as type *Integration* (skip this step once the repo is in the HACS default store).
2. Install **drauf** and restart Home Assistant.

### Manual

Copy `custom_components/drauf` into your Home Assistant `config/custom_components/` directory and restart.

## Setup

*Settings → Devices & services → Add integration → drauf*, then enter:

- **Instance URL** — e.g. `https://drauf.example.com`
- **API token** — the `plan:read` token (starts with `drauf_`)

Setup validates both: the URL must answer `GET /api/version`, and the token must be able to read the plan. If the token is later revoked, Home Assistant prompts for re-authentication.

## Action: `drauf.get_plan`

For wall displays and scripts that need more than the calendar's summaries: returns every entry in a date range, grouped by date, with slot (name, id, order), link, image, and cook. Either pass an explicit `start_date`/`end_date`, or let it compute the range: `start_day` + `days` + `week_offset` reproduce the web app's week logic — a Friday-to-Friday week is:

```yaml
action: drauf.get_plan
data:
  start_day: fri
  days: 8
  week_offset: 0   # 1 = next week
response_variable: plan
```

Response shape:

```yaml
start: "2026-11-27"
end: "2026-12-04"
days:
  - date: "2026-11-27"
    entries:
      - id: "…"
        title: Pizza
        text: Pizza
        slot: Abendessen
        slot_id: "…"
        slot_order: 10
        cook: { id: "…", display_name: null }
        link: null
        image_url: null
```

Days without entries are included with an empty `entries` list. `cook.display_name` stays `null` until the server exposes names to `plan:read` tokens ([drauf#105](https://github.com/drauf-app/drauf/issues/105)). The range may span at most 92 days (server limit).

## Example: announce today's dinner

```yaml
service: tts.speak
data:
  media_player_entity_id: media_player.kitchen
  message: >
    {% if states('sensor.drauf_today') not in ('unknown', 'unavailable') %}
      Heute gibt es: {{ states('sensor.drauf_today') }}
    {% else %}
      Heute ist nichts geplant.
    {% endif %}
```

The sensor attributes carry the structured entries:

```yaml
date: "2026-11-26"
count: 2
entries:
  - slot: Abendessen
    title: Lasagne
    link: https://example.com/lasagne
    image_url: null
    cook_id: usr_123
```

## Scope

Read-only in v1. Writing to the plan from Home Assistant (e.g. a to-do flow) would need a `plan:write` token and is tracked separately; shopping lists as to-do entities are a later milestone.
