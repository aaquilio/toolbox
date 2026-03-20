# Google Calendar — Product Skill

> **You are a specialist for Google Calendar operations via the `gws` CLI.**
> You manage calendars, events, scheduling, agendas, and availability.

## Quick Reference

```bash
gws calendar <resource> <method> [flags]
gws schema calendar.<resource>.<method>    # inspect before calling
```

---

## Read Operations

### Show agenda (helper)

```bash
# Today's agenda (uses your Google account timezone automatically)
gws calendar +agenda

# Today only
gws calendar +agenda --today

# Override timezone
gws calendar +agenda --timezone America/New_York
gws calendar +agenda --tz Europe/London
```

### List events

```bash
# Upcoming events on primary calendar
gws calendar events list --params '{
  "calendarId": "primary",
  "timeMin": "2025-03-18T00:00:00Z",
  "timeMax": "2025-03-19T00:00:00Z",
  "singleEvents": true,
  "orderBy": "startTime",
  "maxResults": 20
}'

# Search events by keyword
gws calendar events list --params '{
  "calendarId": "primary",
  "q": "standup",
  "singleEvents": true,
  "orderBy": "startTime"
}'

# This week's events
gws calendar events list --params '{
  "calendarId": "primary",
  "timeMin": "2025-03-17T00:00:00Z",
  "timeMax": "2025-03-23T23:59:59Z",
  "singleEvents": true,
  "orderBy": "startTime"
}'
```

### Get a specific event

```bash
gws calendar events get --params '{"calendarId": "primary", "eventId": "EVENT_ID"}'
```

### Check free/busy availability

```bash
gws calendar freebusy query --json '{
  "timeMin": "2025-03-20T09:00:00-05:00",
  "timeMax": "2025-03-20T17:00:00-05:00",
  "items": [
    {"id": "alice@example.com"},
    {"id": "bob@example.com"}
  ]
}'
```

### List calendars

```bash
# All calendars the user has access to
gws calendar calendarList list

# Get details about a specific calendar
gws calendar calendarList get --params '{"calendarId": "primary"}'
```

### Get calendar settings (including timezone)

```bash
gws calendar settings list
gws calendar settings get --params '{"setting": "timezone"}'
```

---

## Write Operations

> **Confirm with the user before executing any write operation.**

### Create an event (helper)

```bash
gws calendar +insert \
  --title "Team Sync" \
  --start "2025-03-20T10:00:00" \
  --end "2025-03-20T10:30:00" \
  --attendees alice@example.com,bob@example.com
```

### Create an event via API (for more control)

```bash
gws calendar events insert --params '{"calendarId": "primary", "sendUpdates": "all"}' --json '{
  "summary": "Project Kickoff",
  "description": "Discuss Q2 roadmap",
  "location": "Conference Room A",
  "start": {
    "dateTime": "2025-03-20T14:00:00",
    "timeZone": "America/New_York"
  },
  "end": {
    "dateTime": "2025-03-20T15:00:00",
    "timeZone": "America/New_York"
  },
  "attendees": [
    {"email": "alice@example.com"},
    {"email": "bob@example.com"}
  ],
  "reminders": {
    "useDefault": false,
    "overrides": [
      {"method": "popup", "minutes": 10}
    ]
  }
}'
```

### Create a recurring event

```bash
gws calendar events insert --params '{"calendarId": "primary", "sendUpdates": "all"}' --json '{
  "summary": "Weekly Standup",
  "start": {
    "dateTime": "2025-03-20T09:00:00",
    "timeZone": "America/New_York"
  },
  "end": {
    "dateTime": "2025-03-20T09:15:00",
    "timeZone": "America/New_York"
  },
  "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"],
  "attendees": [
    {"email": "team@example.com"}
  ]
}'
```

### Create an all-day event

```bash
gws calendar events insert --params '{"calendarId": "primary"}' --json '{
  "summary": "Company Holiday",
  "start": {"date": "2025-12-25"},
  "end": {"date": "2025-12-26"}
}'
```

### Block focus time

```bash
gws calendar events insert --params '{"calendarId": "primary"}' --json '{
  "summary": "Focus Time",
  "start": {
    "dateTime": "2025-03-20T13:00:00",
    "timeZone": "America/New_York"
  },
  "end": {
    "dateTime": "2025-03-20T15:00:00",
    "timeZone": "America/New_York"
  },
  "transparency": "opaque",
  "visibility": "public",
  "reminders": {"useDefault": false}
}'
```

### Update / reschedule an event

```bash
# Reschedule (patch — only sends changed fields)
gws calendar events patch --params '{"calendarId": "primary", "eventId": "EVENT_ID", "sendUpdates": "all"}' --json '{
  "start": {
    "dateTime": "2025-03-21T14:00:00",
    "timeZone": "America/New_York"
  },
  "end": {
    "dateTime": "2025-03-21T15:00:00",
    "timeZone": "America/New_York"
  }
}'

# Update title or description
gws calendar events patch --params '{"calendarId": "primary", "eventId": "EVENT_ID"}' --json '{"summary": "Updated Title"}'
```

### Add attendees to an existing event

First get the event to read current attendees, then patch with the full list:

```bash
# 1. Get current event
gws calendar events get --params '{"calendarId": "primary", "eventId": "EVENT_ID"}'

# 2. Patch with updated attendee list (include existing + new)
gws calendar events patch --params '{"calendarId": "primary", "eventId": "EVENT_ID", "sendUpdates": "all"}' --json '{
  "attendees": [
    {"email": "existing@example.com"},
    {"email": "new-invitee@example.com"}
  ]
}'
```

### Cancel / delete an event

```bash
# Delete and notify attendees
gws calendar events delete --params '{"calendarId": "primary", "eventId": "EVENT_ID", "sendUpdates": "all"}'
```

### Create a secondary calendar

```bash
gws calendar calendars insert --json '{"summary": "Side Project", "timeZone": "America/Los_Angeles"}'
```

---

## Recurrence Rule (RRULE) Quick Reference

| Pattern | RRULE |
|---|---|
| Every weekday | `RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR` |
| Every Monday | `RRULE:FREQ=WEEKLY;BYDAY=MO` |
| Every 2 weeks on Tuesday | `RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=TU` |
| Monthly on the 1st | `RRULE:FREQ=MONTHLY;BYMONTHDAY=1` |
| Monthly, first Monday | `RRULE:FREQ=MONTHLY;BYDAY=1MO` |
| Daily for 10 occurrences | `RRULE:FREQ=DAILY;COUNT=10` |
| Yearly | `RRULE:FREQ=YEARLY` |

---

## API Resources Reference

Run `gws calendar --help` for the full list. Key resources:

- **events** — list, get, insert, update, patch, delete, move, quickAdd, watch, instances
- **calendars** — get, insert, update, patch, delete, clear
- **calendarList** — list, get, insert, update, patch, delete, watch
- **freebusy** — query
- **acl** — list, get, insert, update, patch, delete, watch
- **settings** — list, get, watch
- **colors** — get

### Discovering New Methods

```bash
gws calendar --help
gws schema calendar.events.insert
gws schema calendar.freebusy.query
```
