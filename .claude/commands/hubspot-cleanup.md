---
description: Analyse HubSpot exports for post-migration cleanup (read-only)
argument-hint: <folder containing properties.json, fill_rates.json, contacts.json, workflows.json>
---
Using the exports in `$ARGUMENTS`, run the tools in `05-hubspot-ops`:
- `python -m hubspot_ops.cli properties --props ... --fill ...`
- `python -m hubspot_ops.cli workflows --workflows ...`
- `python -m hubspot_ops.cli marketing --contacts ... --tier-size <n> --cost-per-tier <n>` (ask me for tier size and price; do not guess them)

Produce a prioritised cleanup plan: highest risk and highest savings first, each with the exact items. These tools only recommend. State clearly that nothing has been changed in HubSpot and that a person must review before applying.
