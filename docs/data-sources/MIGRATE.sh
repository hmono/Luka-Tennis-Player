#!/usr/bin/env bash
# Run from repo root.
# Moves .md files out of data/ into docs/data-sources/ and commits.

set -e

mkdir -p docs/data-sources

git mv data/tactical_insights.md  docs/data-sources/tactical_insights.md
git mv data/physical_training.md  docs/data-sources/physical_training.md
git mv data/physiology_log.md     docs/data-sources/physiology_log.md
git mv data/nutrition.md          docs/data-sources/nutrition.md

cp ~/luka-sprint/data/README.md           data/README.md
cp ~/luka-sprint/docs/data-sources/README.md  docs/data-sources/README.md

git add data/README.md docs/data-sources/README.md

git commit -m "S6: move data-source .md files to docs/data-sources/

JSON files in data/ are the authoritative app data layer.
Markdown documents are human reference — now separated to
eliminate ambiguity about source of truth.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
