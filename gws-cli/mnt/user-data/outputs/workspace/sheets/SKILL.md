# Google Sheets — Product Skill

> **You are a specialist for Google Sheets operations via the `gws` CLI.**
> You handle reading, writing, appending, and managing spreadsheets.

## Quick Reference

```bash
gws sheets <resource> <method> [flags]
gws schema sheets.<resource>.<method>    # inspect before calling
```

**Shell escaping:** Sheets ranges use `!` which bash interprets as history expansion.
Always wrap `--params` values in **single quotes**.

---

## Read Operations

### Read cell values (helper)

```bash
# Read a range
gws sheets +read --spreadsheet SPREADSHEET_ID --range 'Sheet1!A1:D10'

# Read an entire sheet
gws sheets +read --spreadsheet SPREADSHEET_ID --range Sheet1
```

### Read values via API

```bash
gws sheets spreadsheets values get --params '{"spreadsheetId": "SPREADSHEET_ID", "range": "Sheet1!A1:C10"}'
```

### Read multiple ranges at once

```bash
gws sheets spreadsheets values batchGet --params '{"spreadsheetId": "SPREADSHEET_ID", "ranges": ["Sheet1!A1:B5", "Sheet2!A1:C3"]}'
```

### Get spreadsheet metadata

```bash
# Full spreadsheet metadata (sheets, properties, named ranges)
gws sheets spreadsheets get --params '{"spreadsheetId": "SPREADSHEET_ID"}'

# Only metadata, no cell data (faster)
gws sheets spreadsheets get --params '{"spreadsheetId": "SPREADSHEET_ID", "includeGridData": false}'
```

### List all sheet tabs in a spreadsheet

```bash
gws sheets spreadsheets get --params '{"spreadsheetId": "SPREADSHEET_ID", "fields": "sheets.properties"}'
```

---

## Write Operations

> **Confirm with the user before executing any write operation.**

### Append a row (helper)

```bash
# Append a single row
gws sheets +append --spreadsheet SPREADSHEET_ID --values "Alice,95,A"

# Append multiple rows (JSON)
gws sheets +append --spreadsheet SPREADSHEET_ID --json-values '[["Bob", 87, "B+"], ["Carol", 92, "A-"]]'
```

### Append via API

```bash
gws sheets spreadsheets values append \
  --params '{"spreadsheetId": "SPREADSHEET_ID", "range": "Sheet1!A1", "valueInputOption": "USER_ENTERED"}' \
  --json '{"values": [["Name", "Score"], ["Alice", 95]]}'
```

### Write / update cells

```bash
# Overwrite a specific range
gws sheets spreadsheets values update \
  --params '{"spreadsheetId": "SPREADSHEET_ID", "range": "Sheet1!A1:B2", "valueInputOption": "USER_ENTERED"}' \
  --json '{"values": [["Name", "Score"], ["Alice", 95]]}'
```

### Batch update multiple ranges

```bash
gws sheets spreadsheets values batchUpdate \
  --params '{"spreadsheetId": "SPREADSHEET_ID"}' \
  --json '{
    "valueInputOption": "USER_ENTERED",
    "data": [
      {"range": "Sheet1!A1", "values": [["Updated"]]},
      {"range": "Sheet1!B1", "values": [["Also Updated"]]}
    ]
  }'
```

### Clear a range

```bash
gws sheets spreadsheets values clear \
  --params '{"spreadsheetId": "SPREADSHEET_ID", "range": "Sheet1!A2:D100"}'
```

### Create a new spreadsheet

```bash
gws sheets spreadsheets create --json '{"properties": {"title": "Q1 Budget"}}'

# With initial sheets
gws sheets spreadsheets create --json '{
  "properties": {"title": "Expense Tracker"},
  "sheets": [
    {"properties": {"title": "January"}},
    {"properties": {"title": "February"}},
    {"properties": {"title": "Summary"}}
  ]
}'
```

### Add a new sheet tab

```bash
gws sheets spreadsheets batchUpdate --params '{"spreadsheetId": "SPREADSHEET_ID"}' --json '{
  "requests": [
    {
      "addSheet": {
        "properties": {"title": "March"}
      }
    }
  ]
}'
```

### Duplicate a sheet tab

```bash
gws sheets spreadsheets batchUpdate --params '{"spreadsheetId": "SPREADSHEET_ID"}' --json '{
  "requests": [
    {
      "duplicateSheet": {
        "sourceSheetId": SHEET_ID_NUMBER,
        "newSheetName": "April (Copy)"
      }
    }
  ]
}'
```

### Delete a sheet tab

```bash
gws sheets spreadsheets batchUpdate --params '{"spreadsheetId": "SPREADSHEET_ID"}' --json '{
  "requests": [
    {
      "deleteSheet": {
        "sheetId": SHEET_ID_NUMBER
      }
    }
  ]
}'
```

### Formatting via batchUpdate

```bash
# Bold the header row
gws sheets spreadsheets batchUpdate --params '{"spreadsheetId": "SPREADSHEET_ID"}' --json '{
  "requests": [
    {
      "repeatCell": {
        "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
        "cell": {
          "userEnteredFormat": {
            "textFormat": {"bold": true}
          }
        },
        "fields": "userEnteredFormat.textFormat.bold"
      }
    }
  ]
}'
```

---

## valueInputOption Reference

| Value | Meaning |
|---|---|
| `RAW` | Values are stored as-is (no parsing) |
| `USER_ENTERED` | Values are parsed as if typed in the UI (formulas evaluated, dates parsed) |

Always prefer `USER_ENTERED` unless you specifically want raw string storage.

---

## Range Notation

| Notation | Meaning |
|---|---|
| `Sheet1!A1:C10` | Specific range on Sheet1 |
| `Sheet1!A:C` | Entire columns A through C |
| `Sheet1!1:5` | Entire rows 1 through 5 |
| `Sheet1` | All data on Sheet1 |
| `A1:C10` | Range on the first sheet |
| `'Sheet With Spaces'!A1:B2` | Sheet name with spaces (single-quoted) |

---

## API Resources Reference

Run `gws sheets --help` for the full list. Key resources:

- **spreadsheets** — get, create, batchUpdate, getByDataFilter
- **spreadsheets.values** — get, update, append, clear, batchGet, batchUpdate, batchClear, batchGetByDataFilter, batchUpdateByDataFilter
- **spreadsheets.sheets** — copyTo
- **spreadsheets.developerMetadata** — get, search

### Discovering New Methods

```bash
gws sheets --help
gws schema sheets.spreadsheets.values.get
gws schema sheets.spreadsheets.batchUpdate
```
