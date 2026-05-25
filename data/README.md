# data/

**This directory is the app data layer. All files here are consumed by Next.js page components.**

| File | Type | Consumer |
|------|------|----------|
| `player.json` | Canonical player bio | `app/page.tsx`, `app/tennis-level-comparison/page.tsx` |
| `benchmarks.json` | Level benchmarks | `app/tennis-level-comparison/page.tsx` |
| `career.json` | Match history, rankings | `app/career/page.tsx` |
| `tactical.json` | Frameworks, patterns, surfaces | `app/tactics/page.tsx` |
| `physiology.json` | Zones, HRV matrix, log | `app/physiology/page.tsx` |
| `physical.json` | Periodization, targets | `app/physical/page.tsx` |
| `nutrition.json` | Macros, protocols | `app/nutrition/page.tsx` |

**Do not add `.md` files here.** Human-readable source documents live in `docs/data-sources/`.

## Update workflows

- `career.json` — updated by `.github/workflows/update_career.yml` (weekly)
- `physiology.json` — updated by `.github/workflows/update_physiology.yml` (daily, WHOOP API)
- All others — updated manually or via future workflows
