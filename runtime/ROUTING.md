# Operation routing

## Read the current stage

Run `python scripts/route_registry.py read OPERATION --stage STAGE --condition CONDITION --format compact`; `index --operation OPERATION` shows purpose and family choices; `--query TEXT` or `--family FAMILY` finds exact conditions. Deployed trees use `.agents/scripts/route_registry.py --layout installed`; flat packs provide the selected bodies. Follow `next_offset` under the same `content_sha256` and seen arguments; restart changed text. Supply `--seen BODY_SHA256` only for a complete returned body still present in this intact context. The compact `bodies` map identifies those complete bodies and `reused` names every omission. After compaction, handoff, a model change or missing context, restore the original bodies without seen arguments. The default JSON interface remains available for existing callers.

Stages are `entry` (classify), `contract` (adopt question/method and inputs), `compose` (execute or write), `review` (interpret and repair), and `finalize` (save and deliver).

Expand an incomplete pack from canonical source. On Skill-scoped hosts, read each specialist's `instructions.md` in its own package and common bodies through `project-work/references/shared/`; acquire the matching runtime bundle once for code inspection or execution.
