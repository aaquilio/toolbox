# Gmail — Product Skill

> **You are a specialist for Gmail operations via the `gws` CLI.**
> You handle sending, reading, searching, labeling, filtering, drafts, and threads.

## Quick Reference

```bash
gws gmail <resource> <method> [flags]
gws schema gmail.<resource>.<method>    # inspect before calling
```

---

## Read Operations

### Triage — unread inbox summary (helper)

```bash
# Show unread messages (default)
gws gmail +triage

# Show more messages
gws gmail +triage --max 20

# Filter with a Gmail search query
gws gmail +triage --query "from:boss@company.com"
```

### List messages

```bash
# List inbox messages
gws gmail users messages list --params '{"userId": "me", "maxResults": 10}'

# Search messages with Gmail query syntax
gws gmail users messages list --params '{"userId": "me", "q": "from:alice@example.com subject:budget", "maxResults": 10}'

# List unread messages
gws gmail users messages list --params '{"userId": "me", "q": "is:unread", "maxResults": 10}'

# List messages with a specific label
gws gmail users messages list --params '{"userId": "me", "labelIds": ["INBOX"], "maxResults": 10}'
```

### Read a specific message

```bash
# Get full message (metadata + body)
gws gmail users messages get --params '{"userId": "me", "id": "MESSAGE_ID"}'

# Get metadata only (faster)
gws gmail users messages get --params '{"userId": "me", "id": "MESSAGE_ID", "format": "metadata"}'

# Get specific headers
gws gmail users messages get --params '{"userId": "me", "id": "MESSAGE_ID", "format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]}'
```

### Get attachments

```bash
gws gmail users messages attachments get --params '{"userId": "me", "messageId": "MESSAGE_ID", "id": "ATTACHMENT_ID"}'
```

### List threads

```bash
gws gmail users threads list --params '{"userId": "me", "maxResults": 10}'

# Get a full thread
gws gmail users threads get --params '{"userId": "me", "id": "THREAD_ID"}'
```

### List labels

```bash
gws gmail users labels list --params '{"userId": "me"}'
```

### Get profile

```bash
gws gmail users getProfile --params '{"userId": "me"}'
```

### Search query syntax

| Query | Meaning |
|---|---|
| `from:alice@example.com` | From a specific sender |
| `to:bob@example.com` | Sent to a specific recipient |
| `subject:quarterly report` | Subject contains phrase |
| `has:attachment` | Messages with attachments |
| `filename:pdf` | Attachments of a specific type |
| `is:unread` | Unread messages |
| `is:starred` | Starred messages |
| `after:2025/01/01 before:2025/06/01` | Date range |
| `in:sent` | Sent messages |
| `label:important` | Messages with a label |
| `larger:5M` | Messages larger than 5 MB |

Combine with spaces (implicit AND) or `OR`: `from:alice OR from:bob`

---

## Write Operations

> **Confirm with the user before executing any write operation.**

### Send an email (helper)

```bash
# Simple send
gws gmail +send --to alice@example.com --subject "Hello" --body "Hi there"

# Multiple recipients
gws gmail +send --to alice@example.com,bob@example.com --subject "Update" --body "See attached"

# With CC/BCC
gws gmail +send --to alice@example.com --cc manager@example.com --bcc archive@example.com --subject "FYI" --body "Details below"
```

### Reply to a message (helpers)

```bash
# Reply (to sender only)
gws gmail +reply --message-id MESSAGE_ID --body "Thanks, got it!"

# Reply all
gws gmail +reply-all --message-id MESSAGE_ID --body "Sounds good to everyone"

# Forward
gws gmail +forward --message-id MESSAGE_ID --to newrecipient@example.com --body "FYI — see below"
```

### Create a draft

```bash
gws gmail users drafts create --params '{"userId": "me"}' --json '{
  "message": {
    "raw": "BASE64_ENCODED_RFC2822_MESSAGE"
  }
}'
```

Note: The raw field requires a base64url-encoded RFC 2822 message. For simple
drafts, it's often easier to use `+send` with `--dry-run` to preview, then
compose via the Gmail UI.

### Apply / remove labels

```bash
# Add a label
gws gmail users messages modify --params '{"userId": "me", "id": "MESSAGE_ID"}' --json '{"addLabelIds": ["LABEL_ID"]}'

# Remove a label
gws gmail users messages modify --params '{"userId": "me", "id": "MESSAGE_ID"}' --json '{"removeLabelIds": ["LABEL_ID"]}'

# Mark as read (remove UNREAD label)
gws gmail users messages modify --params '{"userId": "me", "id": "MESSAGE_ID"}' --json '{"removeLabelIds": ["UNREAD"]}'

# Archive (remove INBOX label)
gws gmail users messages modify --params '{"userId": "me", "id": "MESSAGE_ID"}' --json '{"removeLabelIds": ["INBOX"]}'
```

### Create a label

```bash
gws gmail users labels create --params '{"userId": "me"}' --json '{"name": "Projects/Q1", "labelListVisibility": "labelShow", "messageListVisibility": "show"}'
```

### Create a filter

```bash
gws gmail users settings filters create --params '{"userId": "me"}' --json '{
  "criteria": {
    "from": "notifications@service.com"
  },
  "action": {
    "addLabelIds": ["LABEL_ID"],
    "removeLabelIds": ["INBOX"]
  }
}'
```

### Set vacation responder

```bash
gws gmail users settings updateVacation --params '{"userId": "me"}' --json '{
  "enableAutoReply": true,
  "responseSubject": "Out of Office",
  "responseBodyHtml": "<p>I am out of the office until Jan 6. For urgent matters, contact team@example.com.</p>",
  "startTime": 1735689600000,
  "endTime": 1736121600000
}'
```

### Trash / delete

```bash
# Move to trash
gws gmail users messages trash --params '{"userId": "me", "id": "MESSAGE_ID"}'

# Permanently delete (cannot be undone)
gws gmail users messages delete --params '{"userId": "me", "id": "MESSAGE_ID"}'
```

### Watch for new emails (helper)

```bash
# Stream new messages as NDJSON (requires Pub/Sub topic)
gws gmail +watch --project PROJECT_ID --subscription SUBSCRIPTION_NAME --topic TOPIC_NAME
```

---

## API Resources Reference

Run `gws gmail --help` for the full list. Key resources:

- **users** — getProfile, stop, watch
- **users.messages** — list, get, send, modify, trash, untrash, delete, batchModify, batchDelete
- **users.messages.attachments** — get
- **users.threads** — list, get, modify, trash, untrash, delete
- **users.labels** — list, get, create, update, patch, delete
- **users.drafts** — list, get, create, update, send, delete
- **users.settings** — getAutoForwarding, getImap, getPop, getLanguage, getVacation, updateAutoForwarding, updateImap, updatePop, updateLanguage, updateVacation
- **users.settings.filters** — list, get, create, delete
- **users.settings.forwardingAddresses** — list, get, create, delete
- **users.settings.sendAs** — list, get, create, update, patch, delete, verify
- **users.history** — list

### Discovering New Methods

```bash
gws gmail --help
gws schema gmail.users.messages.list
gws schema gmail.users.settings.filters.create
```
