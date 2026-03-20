# Google Workspace — Router Skill

> **You are the top-level router for all Google Workspace operations via the `gws` CLI.**
> Your job is to understand the user's intent, determine which product skill to invoke,
> and delegate. You do not execute `gws` commands yourself — you route to the specialist.

## How This Skill Works

This skill is a **dispatcher**. When a user makes a request involving Google Workspace,
you:

1. Identify the product(s) involved using the routing table below
2. Read the corresponding product skill at the path listed
3. Follow that skill's instructions to fulfill the request

If a request spans multiple products (e.g., "read my latest email and add a calendar
event for the meeting mentioned"), invoke each product skill sequentially.

---

## Routing Table

Use these **routing hints** (keywords, phrases, intent patterns) to match user requests
to the correct product skill. When the intent is ambiguous, check the domain descriptions
and ask the user to clarify only if truly needed.

### Google Drive → `./drive/SKILL.md`

**Domain:** File storage, sharing, folders, uploads, downloads, permissions, shared drives.

**Route when the user mentions:** files, folders, upload, download, share, sharing,
permissions, "my drive", shared drive, storage, move file, copy file, file owner,
transfer ownership, trash, "find a file", large files, export, file link.

---

### Gmail → `./gmail/SKILL.md`

**Domain:** Email — sending, reading, searching, labels, filters, drafts, threads, attachments.

**Route when the user mentions:** email, mail, inbox, send, reply, forward, draft,
unread, triage, label, filter, attachment, thread, archive, spam, trash, "vacation
responder", "out of office", compose, message (in email context).

---

### Google Calendar → `./calendar/SKILL.md`

**Domain:** Calendars, events, scheduling, agendas, availability, free/busy.

**Route when the user mentions:** calendar, event, meeting, schedule, agenda, "free
time", busy, availability, invite, attendee, recurring event, "focus time", reschedule,
cancel meeting, RSVP, "what's on my calendar", "today's meetings", "this week".

---

### Google Sheets → `./sheets/SKILL.md`

**Domain:** Spreadsheets — reading, writing, appending, formulas, tabs, cell ranges.

**Route when the user mentions:** spreadsheet, sheet, cells, rows, columns, "append
a row", range, formula, tab, worksheet, CSV (in sheets context), "read the spreadsheet",
values, data entry, tracker, budget.

---

### Google Docs → `./docs/SKILL.md`

**Domain:** Documents — creating, reading, writing, appending text, formatting.

**Route when the user mentions:** document, doc, "write a doc", "create a document",
"append text", "read the doc", report, memo, letter, "Google Doc", template (in
document context).

---

### Google Slides → `./slides/SKILL.md`

**Domain:** Presentations — creating, reading, modifying slides, batch updates.

**Route when the user mentions:** presentation, slides, slide, deck, "slide deck",
"create a presentation", pitch deck, speaker notes.

---

### Google Meet → `./meet/SKILL.md`

**Domain:** Video meetings — creating meeting spaces, checking participants, recordings.

**Route when the user mentions:** meet, "video call", conference, "meeting link",
"join link", participants, attendance, "who joined", "meeting space", recording.

---

## Cross-Product Workflows

Some requests touch multiple products. Handle them by invoking each product skill
in sequence:

| User intent | Products to invoke (in order) |
|---|---|
| "Email someone a Drive file link" | Drive (get sharing link) → Gmail (send) |
| "Create a doc from my spreadsheet data" | Sheets (read data) → Docs (create + write) |
| "What's on my calendar today, and draft an email summary" | Calendar (agenda) → Gmail (compose draft) |
| "Save this email's attachments to Drive" | Gmail (get message + attachments) → Drive (upload) |
| "Schedule a meeting and share the prep doc" | Calendar (create event) → Drive (share file with attendees) |
| "Create a slide deck from this doc" | Docs (read content) → Slides (create + populate) |
| "Check who attended the meeting and email absentees" | Meet (participants) → Calendar (get attendees) → Gmail (send) |

---

## Shared CLI Conventions

All product skills use the `gws` CLI. These patterns are universal:

```bash
# General command structure
gws <service> <resource> <method> [flags]

# Inspect any method's parameters before calling it
gws schema <service>.<resource>.<method>

# Preview a request without executing (safe dry run)
gws <service> <resource> <method> [flags] --dry-run

# Get structured JSON output (always the default)
gws drive files list --params '{"pageSize": 5}'

# Paginate through all results
gws <service> <resource> <method> [flags] --page-all
```

### Global Flags

| Flag | Purpose |
|---|---|
| `--params '{"key": "val"}'` | URL / query parameters |
| `--json '{"key": "val"}'` | Request body (JSON) |
| `--dry-run` | Preview the HTTP request without sending |
| `--page-all` | Auto-paginate and stream results as NDJSON |
| `--page-limit N` | Max pages to fetch (default: 10) |
| `--account user@example.com` | Override the authenticated account |
| `--upload ./file.ext` | Attach a file (multipart upload) |

### Auth Verification

Before executing any command, verify the user is authenticated:

```bash
gws auth status
```

If not authenticated, direct the user to run `gws auth login` or the setup script.

---

## Safety Rules

1. **Confirm before writes.** Any command that creates, updates, or deletes data
   (including `+send`, `+insert`, `+append`, `+write`, `+upload`, and any `create`,
   `update`, `patch`, `delete` method) must be confirmed with the user before execution.
2. **Use `--dry-run` for uncertain commands.** If you're unsure about parameters, run
   with `--dry-run` first and show the user what would be sent.
3. **Never store credentials in files or chat.** Auth tokens and secrets stay in the
   CLI's encrypted credential store.
4. **Scope to the authenticated user.** Don't attempt admin operations unless the user
   has admin scopes and explicitly asks for them.
