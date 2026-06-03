# Quarantined role_notes — 20260422T140322

These files were moved out of their campaign folders because they contained
analysis for a DIFFERENT campaign than the folder they were saved in. The
agent correctly recognized the mismatch when generating the analysis but then
wrote it to the conversation's stored campaign folder instead of the analyzed
campaign's folder.

## Files

- `23722199501/role_notes/ppc_strategist.md` — Greece V2 folder contained:
  - Lines 1-117, 165-292: legitimate Greece V2 daily reviews (re-extract if needed)
  - Lines 118-164: a MENA campaign daily review (campaign 23688200557)
  - Lines 293-373: a UK proposed campaign plan (belongs to 23777965360)
- `23777965360/role_notes/ppc_strategist.md` — UK folder contained:
  - 100% Portugal USA analysis (campaign 23636342079)

## What replaces them

Each campaign folder now has a clean stub with the date of the cleanup. New
agent runs will write fresh, correctly-scoped analysis.
