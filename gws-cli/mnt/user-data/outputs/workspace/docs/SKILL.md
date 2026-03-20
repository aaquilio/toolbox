# Google Docs — Product Skill

> **You are a specialist for Google Docs operations via the `gws` CLI.**
> You handle creating, reading, writing, and formatting documents.

## Quick Reference

```bash
gws docs <resource> <method> [flags]
gws schema docs.<resource>.<method>    # inspect before calling
```

---

## Read Operations

### Get a document

```bash
# Full document (content + metadata)
gws docs documents get --params '{"documentId": "DOCUMENT_ID"}'
```

The response includes the full document body as a structured JSON tree of
`content` elements (paragraphs, tables, lists, etc.). Each element has a
`startIndex` and `endIndex` — you'll need these for write operations.

### Get document metadata only

To check title, revision, or document ID without pulling the full body:

```bash
gws docs documents get --params '{"documentId": "DOCUMENT_ID"}' | jq '{documentId, title, revisionId}'
```

### Read text content

The document body is in `.body.content[]`. Each paragraph's text is in
`.elements[].textRun.content`. To extract plain text:

```bash
gws docs documents get --params '{"documentId": "DOCUMENT_ID"}' | jq -r '.body.content[].paragraph?.elements[]?.textRun?.content // empty'
```

---

## Write Operations

> **Confirm with the user before executing any write operation.**

### Append text (helper)

```bash
gws docs +write --document DOCUMENT_ID --text "New paragraph added at the end."
```

### Create a blank document

```bash
gws docs documents create --json '{"title": "Meeting Notes — Q2 Kickoff"}'
```

### batchUpdate — the core write mechanism

All Docs modifications (inserting text, deleting text, formatting, adding tables,
etc.) go through `batchUpdate`. Each request specifies an operation and a location
using character indices.

```bash
gws docs documents batchUpdate --params '{"documentId": "DOCUMENT_ID"}' --json '{
  "requests": [
    { ... }
  ]
}'
```

### Insert text at a position

```bash
gws docs documents batchUpdate --params '{"documentId": "DOCUMENT_ID"}' --json '{
  "requests": [
    {
      "insertText": {
        "location": {"index": 1},
        "text": "Hello, this is inserted at the beginning.\n"
      }
    }
  ]
}'
```

Index 1 is the start of the document body (index 0 is reserved).

### Append text at the end

To append, you need the document's end index. Workflow:

```bash
# 1. Get the document to find the end index
gws docs documents get --params '{"documentId": "DOCUMENT_ID"}' | jq '.body.content[-1].endIndex'

# 2. Insert at that index minus 1
gws docs documents batchUpdate --params '{"documentId": "DOCUMENT_ID"}' --json '{
  "requests": [
    {
      "insertText": {
        "location": {"index": END_INDEX_MINUS_1},
        "text": "\nAppended paragraph.\n"
      }
    }
  ]
}'
```

Or just use the helper: `gws docs +write --document DOCUMENT_ID --text "..."`

### Delete text

```bash
gws docs documents batchUpdate --params '{"documentId": "DOCUMENT_ID"}' --json '{
  "requests": [
    {
      "deleteContentRange": {
        "range": {
          "startIndex": 10,
          "endIndex": 50
        }
      }
    }
  ]
}'
```

### Replace text (find and replace)

```bash
gws docs documents batchUpdate --params '{"documentId": "DOCUMENT_ID"}' --json '{
  "requests": [
    {
      "replaceAllText": {
        "containsText": {
          "text": "{{PLACEHOLDER}}",
          "matchCase": true
        },
        "replaceText": "Actual Value"
      }
    }
  ]
}'
```

This is especially useful for template workflows — create a doc from a template
(via Drive copy) then replace all placeholders.

### Format text (bold, italic, etc.)

```bash
gws docs documents batchUpdate --params '{"documentId": "DOCUMENT_ID"}' --json '{
  "requests": [
    {
      "updateTextStyle": {
        "range": {
          "startIndex": 1,
          "endIndex": 20
        },
        "textStyle": {
          "bold": true,
          "fontSize": {"magnitude": 14, "unit": "PT"}
        },
        "fields": "bold,fontSize"
      }
    }
  ]
}'
```

### Apply a paragraph style (heading)

```bash
gws docs documents batchUpdate --params '{"documentId": "DOCUMENT_ID"}' --json '{
  "requests": [
    {
      "updateParagraphStyle": {
        "range": {
          "startIndex": 1,
          "endIndex": 25
        },
        "paragraphStyle": {
          "namedStyleType": "HEADING_1"
        },
        "fields": "namedStyleType"
      }
    }
  ]
}'
```

Named style types: `NORMAL_TEXT`, `HEADING_1` through `HEADING_6`, `TITLE`, `SUBTITLE`.

### Insert a table

```bash
gws docs documents batchUpdate --params '{"documentId": "DOCUMENT_ID"}' --json '{
  "requests": [
    {
      "insertTable": {
        "rows": 3,
        "columns": 2,
        "location": {"index": 1}
      }
    }
  ]
}'
```

---

## Important Notes on Indices

- Indices are **character positions** in the document body, starting at 1.
- After any insert or delete, **all subsequent indices shift**. Process requests
  in reverse order (highest index first) or let batchUpdate handle ordering.
- Always fetch the document fresh before making index-based edits.

---

## API Resources Reference

Run `gws docs --help` for the full list. Key resources:

- **documents** — get, create, batchUpdate

That's the entire API surface. All document manipulation flows through `batchUpdate`
with different request types:

- `insertText`, `deleteContentRange`, `replaceAllText`
- `updateTextStyle`, `updateParagraphStyle`
- `insertTable`, `insertTableRow`, `insertTableColumn`, `deleteTableRow`, `deleteTableColumn`
- `insertInlineImage`
- `createNamedRange`, `deleteNamedRange`
- `insertSectionBreak`, `insertPageBreak`

### Discovering Request Types

```bash
gws schema docs.documents.batchUpdate --resolve-refs
```
