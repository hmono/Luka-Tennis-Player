# docs/data-sources/

Human-readable reference documents. These are the original authoring artifacts from which the `data/*.json` files were derived.

**They are not imported by the app.** Edit them for human comprehension; propagate structural changes to the corresponding JSON file.

| Document | Corresponding JSON | Language |
|----------|--------------------|----------|
| `tactical_insights.md` | `data/tactical.json` | English |
| `physical_training.md` | `data/physical.json` | English |
| `physiology_log.md` | `data/physiology.json` | Portuguese |
| `nutrition.md` | `data/nutrition.json` | English |
| `supplementation.md` | — (sem JSON correspondente) | Portuguese |

## Keeping them in sync

These files diverge from their JSON counterparts over time — that is acceptable. They serve different purposes:

- **JSON** — machine-readable, strictly typed, consumed by the app
- **Markdown** — narrative context, citations, coaching rationale, change history

When adding a new data field to a JSON file, add a corresponding note here so the rationale is preserved.
