# Google Meet — Product Skill

> **You are a specialist for Google Meet operations via the `gws` CLI.**
> You handle creating meeting spaces, checking participants, and managing conferences.

## Quick Reference

```bash
gws meet <resource> <method> [flags]
gws schema meet.<resource>.<method>    # inspect before calling
```

---

## Read Operations

### Get a meeting space

```bash
gws meet spaces get --params '{"name": "spaces/SPACE_ID"}'
```

Returns the meeting space configuration including the meeting URI and join info.

### List conference records

Conference records represent completed or active meetings.

```bash
# List recent conference records
gws meet conferenceRecords list

# Filter by space
gws meet conferenceRecords list --params '{"filter": "space.name = spaces/SPACE_ID"}'
```

### Get a specific conference record

```bash
gws meet conferenceRecords get --params '{"name": "conferenceRecords/CONFERENCE_ID"}'
```

### List participants in a conference

```bash
gws meet conferenceRecords participants list --params '{"parent": "conferenceRecords/CONFERENCE_ID"}'
```

Returns each participant with their display name, join time, and duration.

### Get details about a specific participant

```bash
gws meet conferenceRecords participants get --params '{"name": "conferenceRecords/CONFERENCE_ID/participants/PARTICIPANT_ID"}'
```

### List participant sessions (join/leave times)

A single participant can have multiple sessions (if they dropped and rejoined):

```bash
gws meet conferenceRecords participants participantSessions list --params '{"parent": "conferenceRecords/CONFERENCE_ID/participants/PARTICIPANT_ID"}'
```

### List recordings

```bash
gws meet conferenceRecords recordings list --params '{"parent": "conferenceRecords/CONFERENCE_ID"}'
```

### List transcripts

```bash
gws meet conferenceRecords transcripts list --params '{"parent": "conferenceRecords/CONFERENCE_ID"}'
```

### Get transcript entries

```bash
gws meet conferenceRecords transcripts entries list --params '{"parent": "conferenceRecords/CONFERENCE_ID/transcripts/TRANSCRIPT_ID"}'
```

---

## Write Operations

> **Confirm with the user before executing any write operation.**

### Create a meeting space

```bash
# Create a new meeting space
gws meet spaces create --json '{}'
```

The response includes `meetingUri` (the join link) and `meetingCode`.

### Create a meeting space with specific config

```bash
gws meet spaces create --json '{
  "config": {
    "accessType": "OPEN",
    "entryPointAccess": "ALL"
  }
}'
```

Access types:
- `OPEN` — anyone with the link can join
- `TRUSTED` — only people in the organization and invited guests
- `RESTRICTED` — only explicitly invited attendees

### Update a meeting space config

```bash
gws meet spaces patch --params '{"name": "spaces/SPACE_ID", "updateMask": "config.accessType"}' --json '{
  "config": {
    "accessType": "TRUSTED"
  }
}'
```

### End an active conference

```bash
gws meet spaces endActiveConference --params '{"name": "spaces/SPACE_ID"}'
```

---

## Common Workflows

### Create a meeting and share the link

```bash
# 1. Create the space
gws meet spaces create --json '{}'
# Response includes meetingUri — share this with attendees

# 2. Optionally, create a Calendar event with the Meet link
# (delegate to Calendar skill with the meetingUri in conferenceData)
```

### Review meeting attendance

```bash
# 1. Find the conference record
gws meet conferenceRecords list --params '{"filter": "space.name = spaces/SPACE_ID"}'

# 2. List participants
gws meet conferenceRecords participants list --params '{"parent": "conferenceRecords/CONFERENCE_ID"}'
```

### Check meeting recordings

```bash
gws meet conferenceRecords recordings list --params '{"parent": "conferenceRecords/CONFERENCE_ID"}'
```

The response includes the recording's Drive file ID, so you can use the Drive
skill to share or download it.

---

## API Resources Reference

Run `gws meet --help` for the full list. Key resources:

- **spaces** — get, create, patch, endActiveConference
- **conferenceRecords** — get, list
- **conferenceRecords.participants** — get, list
- **conferenceRecords.participants.participantSessions** — get, list
- **conferenceRecords.recordings** — get, list
- **conferenceRecords.transcripts** — get, list
- **conferenceRecords.transcripts.entries** — get, list

### Discovering New Methods

```bash
gws meet --help
gws schema meet.spaces.create
gws schema meet.conferenceRecords.participants.list
```
