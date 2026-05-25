# Luka Ono Analytics

[![Deploy to GitHub Pages](https://github.com/hmono/Luka-Tennis-Player/actions/workflows/deploy.yml/badge.svg)](https://github.com/hmono/Luka-Tennis-Player/actions/workflows/deploy.yml)

Data-driven performance intelligence platform for Luka Bojičić Ono — professional tennis player (Campinas, Brazil · ATP ~1.951).

Six analytics modules covering career trajectory, tactical patterns, physical training, physiology monitoring, nutrition protocols, and level benchmarks across ITF, Challenger, and ATP.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 15 (App Router, static export) |
| Language | TypeScript 5 (strict) |
| Styling | Tailwind CSS 4 + CSS custom properties |
| Tests | Vitest + React Testing Library |
| Deploy | GitHub Actions → GitHub Pages |

---

## Dev setup

```bash
# 1. Clone
git clone git@github.com:hmono/Luka-Tennis-Player.git
cd Luka-Tennis-Player

# 2. Install
npm install

# 3. Dev server (Turbopack)
npm run dev        # http://localhost:3000

# 4. Tests
npm test           # vitest run (all 4 test files)

# 5. Production build
npm run build      # static export → out/
```

---

## Project structure

```
app/                        # Next.js App Router pages
  page.tsx                  # Homepage (Module overview)
  career/                   # Career & ranking
  tactics/                  # Tactics & game patterns
  tennis-level-comparison/  # Level benchmarks
  physical/                 # Physical training
  physiology/               # HRV & monitoring
  nutrition/                # Nutrition protocols

lib/                        # Pure domain helpers (tested)
  career.ts                 # Career event helpers + accessors
  benchmarks.ts             # Benchmark helpers + player profile
  tactics.ts                # Tactics helpers + accessors

types/
  index.ts                  # Canonical TypeScript interfaces

data/                       # JSON data layer (app source of truth)
  career.json               # Tournament results, ranking events
  benchmarks.json           # Level benchmarks (ATP/Challenger/ITF)
  tactical.json             # Coaching frameworks, game patterns
  player.json               # Player bio (single source of truth)
  physiology.json           # WHOOP log entries
  physical.json             # Training protocols
  nutrition.json            # Nutrition protocols

scripts/
  update_career.py          # ITF scraper (cron: daily)
  update_physiology.py      # WHOOP API sync (cron: daily)

components/
  ui/header.tsx             # Site navigation header

src/styles/
  tokens.css                # Design tokens (--luka-blue, --luka-itf, …)
  components.css            # Component CSS classes
```

---

## Data layer

All application data lives in `data/*.json`. Markdown files in `docs/data-sources/` are human reference only and are never imported by the app.

Pages import data exclusively via typed accessors in `lib/` — never directly from JSON.

---

## Automation

| Script | Trigger | Purpose |
|--------|---------|---------|
| `scripts/update_career.py` | GitHub Actions cron | Scrapes ITF tournament results |
| `scripts/update_physiology.py` | GitHub Actions cron | Syncs WHOOP recovery data |

Secrets required in GitHub repo Settings → Secrets:
- `WHOOP_CLIENT_ID`
- `WHOOP_CLIENT_SECRET`
- `WHOOP_REFRESH_TOKEN`

---

## Styling contract

Static CSS values must be in `src/styles/` class definitions.  
Inline `style={{}}` props are permitted only for **dynamic values** computed from data (widths, colors from data records, conditional expressions).  
See `docs/STYLING_RULE.md` for full contract.

---

## CI

Tests run before every build. A failing test blocks the deploy.

```
push → Test (vitest run) → Build (next build) → Deploy (GitHub Pages)
```
