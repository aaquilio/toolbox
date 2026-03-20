# Google Slides — Product Skill

> **You are a specialist for Google Slides operations via the `gws` CLI.**
> You handle creating, reading, and modifying presentations.

## Quick Reference

```bash
gws slides <resource> <method> [flags]
gws schema slides.<resource>.<method>    # inspect before calling
```

---

## Read Operations

### Get a presentation

```bash
# Full presentation (all slides, layouts, masters)
gws slides presentations get --params '{"presentationId": "PRESENTATION_ID"}'
```

The response includes the full slide structure: `slides[]`, each containing
`pageElements[]` (shapes, text boxes, images, tables). Each element has an
`objectId` used for updates.

### Get a specific slide page

```bash
gws slides presentations pages get --params '{"presentationId": "PRESENTATION_ID", "pageObjectId": "PAGE_OBJECT_ID"}'
```

### Get slide thumbnail

```bash
gws slides presentations pages getThumbnail --params '{"presentationId": "PRESENTATION_ID", "pageObjectId": "PAGE_OBJECT_ID"}'
```

Returns a thumbnail URL and dimensions.

### Extract text from a presentation

```bash
gws slides presentations get --params '{"presentationId": "PRESENTATION_ID"}' | jq -r '.slides[].pageElements[]?.shape?.text?.textElements[]?.textRun?.content // empty'
```

---

## Write Operations

> **Confirm with the user before executing any write operation.**

### Create a blank presentation

```bash
gws slides presentations create --json '{"title": "Q2 Strategy Deck"}'
```

### batchUpdate — the core write mechanism

All Slides modifications go through `batchUpdate`, similar to Docs:

```bash
gws slides presentations batchUpdate --params '{"presentationId": "PRESENTATION_ID"}' --json '{
  "requests": [
    { ... }
  ]
}'
```

### Add a blank slide

```bash
gws slides presentations batchUpdate --params '{"presentationId": "PRESENTATION_ID"}' --json '{
  "requests": [
    {
      "createSlide": {
        "insertionIndex": 1,
        "slideLayoutReference": {
          "predefinedLayout": "TITLE_AND_BODY"
        }
      }
    }
  ]
}'
```

### Predefined layouts

| Layout | Description |
|---|---|
| `BLANK` | Empty slide |
| `TITLE` | Title slide (large centered title) |
| `TITLE_AND_BODY` | Title at top, body text below |
| `TITLE_AND_TWO_COLUMNS` | Title with two body columns |
| `TITLE_ONLY` | Just a title bar |
| `SECTION_HEADER` | Section divider |
| `ONE_COLUMN_TEXT` | Single column text |
| `MAIN_POINT` | Large centered statement |
| `BIG_NUMBER` | Large number display |
| `CAPTION_ONLY` | Caption at bottom |

### Insert text into a shape

```bash
gws slides presentations batchUpdate --params '{"presentationId": "PRESENTATION_ID"}' --json '{
  "requests": [
    {
      "insertText": {
        "objectId": "SHAPE_OBJECT_ID",
        "text": "Hello from the CLI",
        "insertionIndex": 0
      }
    }
  ]
}'
```

### Replace placeholder text

```bash
gws slides presentations batchUpdate --params '{"presentationId": "PRESENTATION_ID"}' --json '{
  "requests": [
    {
      "replaceAllText": {
        "containsText": {
          "text": "{{TITLE}}",
          "matchCase": true
        },
        "replaceText": "Q2 Results"
      }
    }
  ]
}'
```

### Delete a slide

```bash
gws slides presentations batchUpdate --params '{"presentationId": "PRESENTATION_ID"}' --json '{
  "requests": [
    {
      "deleteObject": {
        "objectId": "SLIDE_OBJECT_ID"
      }
    }
  ]
}'
```

### Add an image to a slide

```bash
gws slides presentations batchUpdate --params '{"presentationId": "PRESENTATION_ID"}' --json '{
  "requests": [
    {
      "createImage": {
        "url": "https://example.com/chart.png",
        "elementProperties": {
          "pageObjectId": "SLIDE_OBJECT_ID",
          "size": {
            "width": {"magnitude": 300, "unit": "PT"},
            "height": {"magnitude": 200, "unit": "PT"}
          },
          "transform": {
            "scaleX": 1, "scaleY": 1,
            "translateX": 100, "translateY": 100,
            "unit": "PT"
          }
        }
      }
    }
  ]
}'
```

### Add a text box

```bash
gws slides presentations batchUpdate --params '{"presentationId": "PRESENTATION_ID"}' --json '{
  "requests": [
    {
      "createShape": {
        "objectId": "my_textbox_001",
        "shapeType": "TEXT_BOX",
        "elementProperties": {
          "pageObjectId": "SLIDE_OBJECT_ID",
          "size": {
            "width": {"magnitude": 400, "unit": "PT"},
            "height": {"magnitude": 50, "unit": "PT"}
          },
          "transform": {
            "scaleX": 1, "scaleY": 1,
            "translateX": 50, "translateY": 300,
            "unit": "PT"
          }
        }
      }
    },
    {
      "insertText": {
        "objectId": "my_textbox_001",
        "text": "Content goes here"
      }
    }
  ]
}'
```

### Format text

```bash
gws slides presentations batchUpdate --params '{"presentationId": "PRESENTATION_ID"}' --json '{
  "requests": [
    {
      "updateTextStyle": {
        "objectId": "SHAPE_OBJECT_ID",
        "textRange": {"type": "ALL"},
        "style": {
          "bold": true,
          "fontSize": {"magnitude": 24, "unit": "PT"},
          "foregroundColor": {
            "opaqueColor": {"rgbColor": {"red": 0.2, "green": 0.2, "blue": 0.8}}
          }
        },
        "fields": "bold,fontSize,foregroundColor"
      }
    }
  ]
}'
```

### Reorder slides

```bash
gws slides presentations batchUpdate --params '{"presentationId": "PRESENTATION_ID"}' --json '{
  "requests": [
    {
      "updateSlidesPosition": {
        "slideObjectIds": ["slide_3_id", "slide_1_id"],
        "insertionIndex": 0
      }
    }
  ]
}'
```

---

## API Resources Reference

Run `gws slides --help` for the full list. Key resources:

- **presentations** — get, create, batchUpdate
- **presentations.pages** — get, getThumbnail

All modifications go through `batchUpdate`. Key request types:

- `createSlide`, `deleteObject`, `updateSlidesPosition`
- `createShape`, `createImage`, `createTable`, `createLine`
- `insertText`, `deleteText`, `replaceAllText`
- `updateTextStyle`, `updateParagraphStyle`, `updateShapeProperties`
- `updatePageProperties`, `updateTableCellProperties`
- `duplicateObject`, `groupObjects`, `ungroupObjects`

### Discovering Request Types

```bash
gws slides --help
gws schema slides.presentations.batchUpdate --resolve-refs
```
