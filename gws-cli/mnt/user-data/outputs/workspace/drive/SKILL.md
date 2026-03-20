# Google Drive — Product Skill

> **You are a specialist for Google Drive operations via the `gws` CLI.**
> You manage files, folders, permissions, shared drives, uploads, and downloads.

## Quick Reference

```bash
gws drive <resource> <method> [flags]
gws schema drive.<resource>.<method>    # inspect before calling
```

---

## Read Operations

### List files

```bash
# List recent files (default: 10)
gws drive files list --params '{"pageSize": 10}'

# Search by name
gws drive files list --params '{"q": "name contains '\''budget'\''", "pageSize": 10}'

# Search by MIME type (e.g., spreadsheets only)
gws drive files list --params '{"q": "mimeType = '\''application/vnd.google-apps.spreadsheet'\''", "pageSize": 10}'

# List files in a specific folder
gws drive files list --params '{"q": "'\''FOLDER_ID'\'' in parents", "pageSize": 20}'

# Include specific fields in the response
gws drive files list --params '{"pageSize": 10, "fields": "files(id,name,mimeType,modifiedTime,size)"}'

# Paginate through all results
gws drive files list --params '{"pageSize": 100}' --page-all
```

### Get file metadata

```bash
gws drive files get --params '{"fileId": "FILE_ID"}'

# With specific fields
gws drive files get --params '{"fileId": "FILE_ID", "fields": "id,name,mimeType,webViewLink,owners,permissions"}'
```

### Download / export a file

```bash
# Download a binary file (PDF, image, etc.)
gws drive files get --params '{"fileId": "FILE_ID", "alt": "media"}' > output.pdf

# Export a Google Doc as PDF
gws drive files export --params '{"fileId": "FILE_ID", "mimeType": "application/pdf"}' > document.pdf

# Export a Google Sheet as CSV
gws drive files export --params '{"fileId": "FILE_ID", "mimeType": "text/csv"}' > data.csv
```

### List permissions on a file

```bash
gws drive permissions list --params '{"fileId": "FILE_ID"}'
```

### Find large files consuming storage

```bash
gws drive files list --params '{"q": "trashed = false", "orderBy": "quotaBytesUsed desc", "pageSize": 10, "fields": "files(id,name,size,quotaBytesUsed)"}'
```

### Shared drives

```bash
# List all shared drives
gws drive drives list --params '{"pageSize": 20}'

# Get shared drive details
gws drive drives get --params '{"driveId": "DRIVE_ID"}'

# List files in a shared drive
gws drive files list --params '{"driveId": "DRIVE_ID", "corpora": "drive", "includeItemsFromAllDrives": true, "supportsAllDrives": true, "pageSize": 20}'
```

---

## Write Operations

> **Confirm with the user before executing any write operation.**

### Upload a file (helper)

```bash
# Simple upload
gws drive +upload ./report.pdf

# Upload with a custom name
gws drive +upload ./report.pdf --name "Q1 Report"

# Upload into a specific folder
gws drive +upload ./report.pdf --name "Q1 Report" --parent FOLDER_ID
```

### Upload via API (for more control)

```bash
gws drive files create --json '{"name": "report.pdf", "parents": ["FOLDER_ID"]}' --upload ./report.pdf
```

### Create a folder

```bash
gws drive files create --json '{"name": "Project Files", "mimeType": "application/vnd.google-apps.folder"}'

# Create a subfolder
gws drive files create --json '{"name": "Subproject", "mimeType": "application/vnd.google-apps.folder", "parents": ["PARENT_FOLDER_ID"]}'
```

### Move a file to a different folder

```bash
gws drive files update --params '{"fileId": "FILE_ID", "addParents": "NEW_FOLDER_ID", "removeParents": "OLD_FOLDER_ID"}'
```

### Rename a file

```bash
gws drive files update --params '{"fileId": "FILE_ID"}' --json '{"name": "New Name.pdf"}'
```

### Copy a file

```bash
gws drive files copy --params '{"fileId": "FILE_ID"}' --json '{"name": "Copy of Document"}'
```

### Share a file (add permission)

```bash
# Share with a specific user (writer)
gws drive permissions create --params '{"fileId": "FILE_ID"}' --json '{"role": "writer", "type": "user", "emailAddress": "alice@example.com"}'

# Share with a specific user (reader)
gws drive permissions create --params '{"fileId": "FILE_ID"}' --json '{"role": "reader", "type": "user", "emailAddress": "bob@example.com"}'

# Share with anyone who has the link
gws drive permissions create --params '{"fileId": "FILE_ID"}' --json '{"role": "reader", "type": "anyone"}'
```

### Remove a permission

```bash
gws drive permissions delete --params '{"fileId": "FILE_ID", "permissionId": "PERMISSION_ID"}'
```

### Transfer ownership

```bash
gws drive permissions create --params '{"fileId": "FILE_ID", "transferOwnership": true}' --json '{"role": "owner", "type": "user", "emailAddress": "newowner@example.com"}'
```

### Trash / delete

```bash
# Move to trash
gws drive files update --params '{"fileId": "FILE_ID"}' --json '{"trashed": true}'

# Permanently delete (cannot be undone)
gws drive files delete --params '{"fileId": "FILE_ID"}'

# Empty trash
gws drive files emptyTrash
```

### Create a shared drive

```bash
gws drive drives create --params '{"requestId": "unique-id-123"}' --json '{"name": "Team Drive"}'
```

---

## Drive Search Query Syntax

The `q` parameter supports these operators:

| Query | Meaning |
|---|---|
| `name contains 'budget'` | File name contains "budget" |
| `mimeType = 'application/vnd.google-apps.folder'` | Folders only |
| `mimeType = 'application/vnd.google-apps.spreadsheet'` | Sheets only |
| `mimeType = 'application/vnd.google-apps.document'` | Docs only |
| `'FOLDER_ID' in parents` | Files in a specific folder |
| `trashed = false` | Exclude trashed files |
| `modifiedTime > '2025-01-01T00:00:00'` | Modified after a date |
| `sharedWithMe` | Files shared with the user |

Combine with `and`: `"name contains 'report' and mimeType = 'application/pdf'"`

---

## Common MIME Types

| Google type | MIME type |
|---|---|
| Folder | `application/vnd.google-apps.folder` |
| Document | `application/vnd.google-apps.document` |
| Spreadsheet | `application/vnd.google-apps.spreadsheet` |
| Presentation | `application/vnd.google-apps.presentation` |
| Form | `application/vnd.google-apps.form` |

---

## API Resources Reference

Run `gws drive --help` for the full list. Key resources:

- **files** — list, get, create, update, copy, delete, export, emptyTrash
- **permissions** — list, get, create, update, delete
- **drives** — list, get, create, update, delete (shared drives)
- **changes** — list, getStartPageToken, watch
- **revisions** — list, get, update, delete
- **comments** — list, get, create, update, delete
- **replies** — list, get, create, update, delete

### Discovering New Methods

```bash
gws drive --help
gws schema drive.files.list
gws schema drive.permissions.create
```
