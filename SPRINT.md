# Sprint — Luka Tennis Player Refactor

**Started:** 2026-05-25  
**Repo:** https://github.com/hmono/Luka-Tennis-Player  
**Goal:** Establish domain model layer, eliminate duplication, add test gate

---

## Tasks

| # | Title | Priority | Status | Notes |
|---|-------|----------|--------|-------|
| S1 | Define TypeScript interfaces for all JSON schemas | High | `done` | `~/luka-sprint/types/index.ts` — ready to copy to repo `types/` |
| S2 | Extract helper/parser functions out of page components | High | `done` | `~/luka-sprint/lib/` — career.ts, benchmarks.ts, tactics.ts |
| S3 | Add unit tests for lib functions | High | `done` | `~/luka-sprint/lib/__tests__/` — career.test.ts (18), benchmarks.test.ts (16), tactics.test.ts (8) |
| S4 | Add test step to CI before deploy | High | `done` | `~/luka-sprint/.github/workflows/deploy.yml` — Test step inserted before Build |
| S5 | Resolve player bio single source of truth | Medium | `done` | `~/luka-sprint/data/player.json` created; patches for page.tsx and tennis-level-comparison/page.tsx |
| S6 | Retire markdown/JSON duplication | Medium | `done` | `data/README.md` + `docs/data-sources/README.md` + `MIGRATE.sh`; md → docs/data-sources/ |
| S7 | Settle on one styling system | Medium | `done` | header.tsx rewritten (0 inline styles); CSS classes added; STYLING_RULE.md documents the contract |
| S8 | Wire pages to typed accessors, not raw JSON imports | Low | `done` | Accessors added to all 3 lib files; patches for career, tactics, tennis-level-comparison pages |

---

| S9 | Create missing automation scripts | High | `done` | `~/luka-sprint/scripts/update_{career,physiology}.py` — copy to repo scripts/ |

---

## Sprint 2 — Post-Audit Hardening

**Started:** 2026-05-25  
**Goal:** Eliminate remaining Fowler smells from audit; wire pages to lib layer; stabilise styling

### Dependency graph

```
A1 ──► A2 ──► A6
         └──► A7
A3 (independent)
A4 (independent)
A5 (independent)
A8 (independent)
```

### Tasks

| ID | Audit # | Title | Priority | Dep | Status |
|----|---------|-------|----------|-----|--------|
| A1 | #8 | Extract `extractOpponent`, `phaseColor`, `phaseWeight` from `career/page.tsx` → `lib/career.ts` | High | — | `todo` |
| A2 | #7 | Make `findRanking` pure (accept events param); add to `lib/career.ts` | Medium | A1 | `todo` |
| A3 | #3+#5+#6 | `app/page.tsx`: read bio from `player.json`; hex → CSS vars; remove stale dates | Medium | — | `todo` |
| A4 | S8 | Wire `app/tactics/page.tsx` to `lib/tactics.ts` (remove raw JSON import) | Medium | — | `todo` |
| A5 | S8 | Wire `app/tennis-level-comparison/page.tsx` to `lib/benchmarks.ts` (remove raw JSON import) | Medium | — | `todo` |
| A6 | #4 | Convert `tableWrapStyle`/`tableHeadStyle` + grid inlines in `career/page.tsx` → CSS classes | Low | A1, A2 | `todo` |
| A7 | #11 | Add component tests (React Testing Library) for lib functions added in A1/A2 | Low | A1, A2 | `todo` |
| A8 | #12 | README with CI badge + dev setup instructions | Low | — | `todo` |

### Open questions (block nothing, resolve async)

- Confirm `PLAYER_ITF_ID = "100610195"` in `scripts/update_career.py`
- Verify `WHOOP_CLIENT_ID`, `WHOOP_CLIENT_SECRET`, `WHOOP_REFRESH_TOKEN` set in GitHub repo Settings → Secrets

---

## Status key
`todo` · `in-progress` · `done` · `blocked`

---

## Log

| Date | Entry |
|------|-------|
| 2026-05-25 | Sprint created from code review findings |
| 2026-05-25 | S1 done — `~/luka-sprint/types/index.ts` (6 domains, inferred from JSON summaries; validate field names against raw JSON before committing) |
| 2026-05-25 | S2 done — `~/luka-sprint/lib/{career,benchmarks,tactics}.ts`; types patched: `CareerEvent`, `BenchmarkEntry` added, `GamePattern` corrected to actual JSON shape |
| 2026-05-25 | S3 done — 42 tests across 3 files; vitest.config.ts included; @ alias points to repo root |
| 2026-05-25 | S4 done — deploy.yml updated: Test → Build → Deploy; failing tests now block deploy |
| 2026-05-25 | S5 done — data/player.json canonical source; PlayerProfile type updated; patches for both affected pages |
| 2026-05-25 | S6 done — JSON = app layer, md = human reference; MIGRATE.sh moves 4 files to docs/data-sources/ in one commit |
| 2026-05-25 | S7 done — header.tsx: 13 inline style objects → 5 class names; spacing/text utilities added to components.css; STYLING_RULE.md committed |
| 2026-05-25 | S8 done — typed accessors in lib/{career,benchmarks,tactics}.ts; 3 type fixes (CoachingFramework, SurfaceTactics, TacticalBenchmark); page patches produced |
| 2026-05-25 | S9 done — update_physiology.py (WHOOP API, upsert by date) + update_career.py (ITF scraper, dedup by date+title); PLAYER_ITF_ID needs confirmation |

---

## Sprint 3 — Code Quality (from audit 2026-05-25)

**Goal:** Eliminate all audit findings: dead CSS, STYLING_RULE violations, hardcoded strings, type smells, redundant logic.

### Dependency graph

```
C1 (independent — phaseColor/phaseWeight simplify)
C2 (independent — as unknown as → single cast)
C3 (independent — TacticalData key alignment)
C4 (independent — seasons derived from data)
C5 (independent — hardcoded bio strings → player.json)
C6 ──► C7       (dead CSS removal → split components.css)
C8 (independent — static inlines → CSS classes)
```

### Tasks

| ID | Audit ref | Title | Priority | Dep | Status |
|----|-----------|-------|----------|-----|--------|
| C1 | P4 | Simplify `phaseColor`/`phaseWeight` to 2-branch ternaries in `lib/career.ts` | Low | — | `todo` |
| C2 | P3 | Replace `as unknown as T` double-cast with `as T` single cast in all 4 lib files | Low | — | `todo` |
| C3 | P3 | Align `TacticalData` exported interface keys with actual JSON (`game_patterns`, `surface_tactics`, `target_benchmarks`) | Medium | — | `todo` |
| C4 | P2 | Derive `seasons` array from data instead of hardcoded `["2021"…"2026"]` in `career/page.tsx` | Medium | — | `todo` |
| C5 | P2 | Remove hardcoded bio strings from `career/page.tsx` (birthDate, hero-sub range, luka-box-tag date) → read from `player.json` | Medium | — | `todo` |
| C6 | P0 | Delete 22 dead CSS classes from `components.css` (`.shell`, `.section-block`, `.page-layout`, `.hero-panel`, `.surface-card`, `.level-legend`, `.level-item`, `.level-dot`, `.level-note`, `.level-label`, `.stat-strip`, `.stat-item`, `.stat-value`, `.stat-label` and 8 more) | High | — | `todo` |
| C7 | P0 | Split `components.css` (1 339 lines, 227 selectors) into `layout.css`, `hero.css`, `cards.css`, `table.css` | Medium | C6 | `todo` |
| C8 | P1 | Move static inline styles → CSS classes in `physical/page.tsx` (6 violations) and `tactics/page.tsx` (3 violations + remove dead `display:none` link) | High | — | `todo` |

### Log

| Date | Entry |
|------|-------|
| 2026-05-25 | Sprint 3 created from audit; 8 tasks, 2 blocking (C6→C7) |
