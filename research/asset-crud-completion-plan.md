# Asset CRUD Completion Plan (approved 2026-07-21 — "update assets + deletion, all CRUD if possible")

Goal: complete the asset tool surface from create-only to full CRUD, so the app's agents
(and the MCP) can edit and remove sitelinks/callouts/snippets/call/image assets in place —
same class of gap as the final-URL saga; same proven fix pattern (mutate + update_mask).

## 1. `asset_update_asset` — edit an existing asset in place
`update_asset(customer_id, asset_id | asset_resource_name, ...typed fields)` via
`AssetService.mutate_assets` + `AssetOperation.update` + explicit FieldMask (mirror the
sibling idiom: field_mask_pb2 paths, as in update_ad_status / update_ad_final_urls /
primary_for_goal). Per-type mutable fields (ENCODE Google's immutability rules):
- SITELINK: link_text (≤25), description1/2 (≤35 each), final_urls (http/https)
- CALLOUT: callout_text (≤25)
- STRUCTURED_SNIPPET: header (valid enum-ish string), values[] (each ≤25, ≥3 recommended)
- CALL: phone_number, country_code
- IMAGE: name ONLY (media bytes are immutable — reject any attempt to change image data
  with a clear message "create a new image asset instead")
Validation BEFORE mutation (char limits + the ads symbol ban on text fields: no ~ | + etc.).
Only fields explicitly provided enter the mask; None = untouched.

## 2. `asset_remove_asset` — delete an asset
`AssetOperation.remove` by resource name. Guard: warn-and-proceed semantics are NOT enough —
first do a cheap GAQL count of live linkages (campaign_asset + ad_group_asset + customer_asset
WHERE asset = X AND status != REMOVED); if >0, return the linkage list and require
`force=true` to remove anyway (removing an asset detaches it everywhere — the operator must
see the blast radius). This mirrors how we protect against silent live-campaign damage.

## 3. Linkage CRUD completeness (audit + fill)
Inventory what exists vs missing across levels; fill ONLY the gaps:
- ad_group_asset: link / link-multiple / list / remove / status — EXISTS (verified) ✓
- campaign_asset: verify link/list/remove tools are all registered (the service file exists;
  function inventory was inconclusive — if remove/list missing, add them; the campaign-level
  sitelink unlink I ran 2026-07-15 used raw SDK, which suggests a tool gap)
- customer_asset (account-level): OUT OF SCOPE unless trivially symmetrical (note in report)

## 4. Wire-through (all three, or the tools are decorative)
- Register in the MCP surface exactly like siblings (asset namespace, groups incl. the
  restricted default set if that's where create_* lives)
- Add the new write names to `tool_registry.execution_catalog()` WRITE list so chat
  Directors can grant them by exact name (the Jul-21 execution-grant contract)
- Dry-run harness entries in validate_all_tools.py (validate_only, fail-closed) for
  update + remove (+ any new linkage tools)

## Gates
Suite green (319 baseline) + new tests: per-type mask correctness, image-immutability
rejection, symbol/char validation, remove-with-linkages requires force, registry/catalog
presence, harness discovery. No live mutations in tests. No prod restart (flag). Feature-log.
