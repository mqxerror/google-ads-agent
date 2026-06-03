# Feature Log — google-ads-agent (BMAD drift reconcile, Tier 1)

Lightweight delta capture so the BMAD planning artifacts don't silently drift from the code.

- **Tier 1 (this file):** every session that ships a feature appends ONE row to the Active table below — *before ending the session*. Cheap (~10s), captures the *why* while it's fresh. Same reflex as the chronicle line in this folder's product-dev memory.
- **Tier 2 (reconcile):** when this log exceeds ~10 unreconciled rows **OR** a month has passed **OR** before a version milestone, run `/bmad-document-project` to fold these deltas back into `_bmad-output/planning-artifacts/`. Then move the folded rows under **Reconciled** with the date.

Convention: **Story** = the epic/story id it maps to, or `NEW — unplanned` if it had no story. Keep each row to one line.

## Active (unreconciled)

| Date | Feature / change | Story | Files touched |
|---|---|---|---|
| | | | |

## Reconciled

_Rows folded into the planning artifacts. Format: `YYYY-MM-DD — reconciled via /bmad-document-project (covers <date range>)` followed by the moved rows._
