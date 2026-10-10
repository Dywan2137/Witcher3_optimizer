# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Witcher 3 quest-order optimizer. Find the order of doing quests (base game + Hearts of Stone + Blood and Wine) that maximises Geralt's level at the end of a single playthrough (no New Game+). The game is deterministic, so this is a sequencing/combinatorial optimisation problem, not a Monte Carlo one; randomness is only used to explore the space of orderings.

Steps 1-3 of the plan (load + validate, simulator, decision units) are done; the search is not written yet. There is no build or lint tooling; tests use `unittest`. Do not code the search until the data model is agreed; prefer explicit, data-driven rules over hardcoded logic.

## Commands

- Layout: code in the `witcher3/` package (`loader.py`, `simulator.py`, `checker.py`, `units.py`, `build_relationships.py`), tests in `tests/` (`helpers.py` has the shared `real()` dataset and the `tiny()` synthetic-dataset builder), `main.py` is the CLI, `Data/` holds the workbook. Dependencies are in `requirements.txt` (Python 3.10+).
- `python main.py` loads `Data/Witcher_3_quests copy.xlsx`, prints a per-location summary and runs the validation checks (`--all` prints every issue, `--csv issues.csv` saves them, `--file PATH` loads another workbook, `--units` adds the decision-unit stats and diagnostics). It exits 1 if any check reports an error.
- `witcher3/loader.py` has the pieces: `load()` returns a `Dataset` (`steps`, `relationships`, `reward_rules`, `level_table`, `rel_types`), `validate(ds)` returns the issues DataFrame, `summarize(ds)` the per-location counts. It reads formulas (not cached values), evaluating the `=CONCAT(D<row>,"suffix")` Block_ID/Path_ID formulas itself, and computes `step_uid` from `Quest_ID` + `_S` + `Step_ID`. Reward_rules is read from columns A:E only (the sheet has stray data further right).
- `python -m unittest` (about 10 s) runs everything in `tests/`; a single test: `python -m unittest tests.test_simulator.Rules.test_requires`.
- `witcher3/simulator.py`: `Model(ds)` (static, built once), `start_state(model)`, `available(model, state)` (indices of steps that can be taken now), `why_not(...)`, `take(...)` and `simulate(model, ordered_step_ids, on_violation='raise'|'skip'|'stop')`, which returns XP, level, a per-step trace (`trace_frame()`) and violations. Its rule semantics are documented in the module docstring. Notable choices: a sealed block, once one member is done, allows only steps of the quests that have a member in it (steps of the same quest between members stay allowed) and closes when every member is done, unavailable or optional; a Path_ID cell with several tags is a shared anchor and picks no path; the reward uses the level before the step; XP is not rounded; the `during` edge type is not supported (the simulator raises if it appears).
- `witcher3/checker.py` re-checks a finished order independently (positions + raw tables, no `simulator.py` code), and the tests assert both agree on random valid and mutated orderings. Keep them independent.
- `witcher3/units.py`: `Plan(model)` splits the model into what the search chooses between. `plan.legal_actions(state)` returns `Action`s: free steps (steps with no Block_ID, one at a time) and block units (a whole sealed block played through in place with the simulator's own `take`, one action per path variant and per optional-members mode; its XP therefore depends on the entry state). `plan.apply(state, action)` returns `(new_state, [Taken])` and raises on an illegal action. Units are only started between units (`state.open_block is None`). `plan.unresolved_choices(state)` lists reachable choice groups (connected `excludes_path` tags) with no path chosen yet, and the search must make sure each ends up with exactly one. `plan.diagnostics()` reports blocks that cannot be played through or that force a path choice (currently WOF4_BLOCK/WOF6_BLOCK and the per-path WOZP5 blocks, by data design). Optional free steps are simply left out of an ordering to switch them off.
- Validation covers duplicate step ids, bad XP/level/rule type, reward-rule gaps and `Level_table` consistency, unknown/dangling/self relationships, `requires`/`unlocks` cycles, steps that can never become available, a blocker that is also a prerequisite of its target, After/Before cells that produced no edge, and Block_ID vs `in_block` sync.

## Core mechanic

- Level only goes up; XP needed per level comes from an XP-to-level table.
- Each quest step pays `Reward XP x multiplier`, where the multiplier depends on `level_gap = recommended_level - player_level` at the moment the step is completed (negative = over-leveled). Doing quests too late gives almost nothing, so order matters.
- Quests with `Has_level_recommendation = False` always pay 100%, ignoring Death March.

### Reward rules (Death March difficulty)

Stored as data in the `Reward_rules` sheet (`Reward_rule_type`, `Level_gap_min`, `Level_gap_max`, `Multiplier`); never hardcode them in simulation logic.

- `base_cliff` (base game, Blood and Wine): 80% normally, 5% if over-leveled by 10 or more. The exact boundary (-10 inclusive vs -11) must still be verified in-game, as must the under-leveled side (no extra penalty known). The sheet currently has -999..-11 → 0.05 and -10..999 → 0.8.
- `hos_gradual` (Hearts of Stone), by gap: <= -6: 5%, -5: 10%, -4: 16%, -3: 32% (the sheet has 36%, verify), -2: 48%, -1: 64%, 0: 80%, +1: 96%, +2: 112%, +3: 128%, +4: 144%, +5: 150%, >= +6: 80%.
- `exempt_full`: always 100%.

## Data: `Data/Witcher_3_quests.xlsx` / `Data/Witcher_3_quests copy.xlsx`

`Data/Witcher_3_quests copy.xlsx` is the working file; `Data/Witcher_3_quests.xlsx` is the original. The `Level_table` sheet (levels 1-100: `xp_to_next_level`, `cumulative_xp_to_reach_level`) converts total XP to a level. Quest text (Quest_Name, Describtion) is in Polish; column names are English. Edit the workbook with openpyxl (the package has no charts or external links); `scripts/recalc.py` from the xlsx skill does not run on this Windows setup, so formula values only refresh when the file is opened in Excel.

One sheet per region, in game order: White Orchard, Visima (sic, Vizima), Velen, Novigrad, Skellige, Kear Morhen, Toussaint (Blood and Wine). Each `<Region> Relationships` sheet (`relationship_id`, `source_step_id`, `relationship_type`, `target_step_uid`) is generated from that region's Before/After/Block_ID/Path_ID columns, keyed by the sheet of the target step: `After` → `requires` (single prerequisite) or `unlocks` (one row per alternative in a branch group or `|` list); `Before` → `blocks`; `Path_ID` → `excludes_path` between the path tags of a quest (source/target are tags, not step IDs); `Block_ID` → `in_block` (source is the block tag, target a member step; this type is an addition, documented on `Relationships`). Name-based cells are resolved to the quest's last mandatory step. `Relationship_issues` lists cells that could not be resolved. A `Path_ID` cell may list several tags (`WOF4_PATH_A / WOF5_PATH_B / WOF6_PATH_C`): they are alternatives to each other and get `excludes_path` edges too. Regenerate with `python -m witcher3.build_relationships` after editing the source columns; it overwrites these sheets and `Relationship_issues`, so edit the source columns, not the sheets (`python main.py` warns when `in_block` edges drift out of sync). `Relationships` documents the edge types (below). `Reward_rules` also has a stray block of Novigrad rows pasted at columns T onward.

Each row is one quest step. Column layouts differ per sheet (White Orchard has `Manditory`; Skellige has an extra `During`; Visima lacks `Manditory`), so look columns up by header name, not position. Header spellings vary too (`Before ` has a trailing space in Velen; `Describtion` vs `Description`).

- Step key: `ID` = `Quest_ID` + `_S` + `Step_ID`, a formula (`=_xlfn.CONCAT(D2,"_S",E2)`). `Step_ID` is an int or a string: `2a`/`2b` are alternative branches, an `o` suffix (`3o`, `3bo`) marks an optional step.
- `Quest_ID` prefixes encode region and category, e.g. `VF` Velen main, `VZB` Velen side, `NZB` Novigrad side, `SZP` Skellige side, `SZK*` Hearts of Stone, `KIW*` Blood and Wine. `Category` is Polish (`Fabularny` main story, `Zadanie poboczne`/`Zadanie Poboczne` side quest, `Zlecenie wiedźmińskie` contract, `Poszukiwania` treasure hunt), and its capitalisation is inconsistent.

### Before / After / Block_ID / Path_ID convention

These four columns are temporary, for human readability. The final data moves into the `relationships` table (below).

- `After`: the step that must be completed before this one is available (a `requires`). Within a quest it is the previous step. Branch groups are written `QID_S2a/b/c`. Optional (`o`) steps do not gate later steps. The first step of a quest points at a prerequisite in another quest. `|` separates alternative cross-quest prerequisites (`VF9_S4|VF3_S11|NF9_S2|SF7NA_S2`).
- `Before`: only for true cutoffs, the step whose completion makes this step permanently unavailable (a `blocks`), e.g. `WOF1_S5` for the White Orchard side quests. `-` means none. Do not store ordinary forward sequencing in both columns (desync risk), and do not use it for `2a`/`2b` exclusivity.
- `Path_ID`: `<Quest_ID>_PATH_<LETTER>` for steps with a branch letter (`2a` → `..._PATH_A`); once a path is started, steps of the other paths of that quest are unavailable. Unlettered steps are `-`. Written as plain strings; White Orchard/Visima use equivalent `CONCAT` formulas.
- `Block_ID`: steps that are sealed together, where the game never returns free roam between them. Every step in the block carries the same value (order inside comes from `After`). The block is named after its last quest (`WOF3_BLOCK`, `KMF7_BLOCK`); `-` means no block. A step after the first free-roam moment is not in the block even if mandatory: mandatory is not the same as sealed.
  - Two heuristic block kinds were added by request and are not true free-roam locks: every quest with exactly two unbranched steps and a 0 XP "Zacznij zadanie" start gets its own `<Quest_ID>_BLOCK`, and longer unblocked quests get `<Quest_ID>_BLOCK` on just the start step and the next step (all branch rows of either step). The purpose is to stop the search from opening many zero-reward quests at once.
- `-` is the "none" marker in all four columns. Never overwrite a non-empty hand-entered value.
- Path_ID and After were generated by parsing `Step_ID` letters. That is fine for filling the sheet, but the simulation itself must never parse `Step_ID` or the ID string; use the explicit columns and relationships.
- Gating gap that matters for the search: at game start the simulator can take 52 of 1043 steps, 50 of them in Toussaint (plus one each in White Orchard and Novigrad), because those quests have `After = -` and no region gate. Until entry gates are filled in (Blood and Wine needs KIWF1's prerequisite, etc.), a search will happily do Blood and Wine quests at level 1.
- Known gaps: some Skellige and Toussaint cells hold Polish quest names instead of step IDs; first steps of side quests and of each region's first main quest are mostly `-` until filled by hand with game knowledge; the `Block_ID` chains for the Ciri flashbacks, Isle of Mists → Kaer Morhen, On Thin Ice → finale and Capture the Castle → end of Blood and Wine were assigned from a lock-in guide plus memory and need checking.

## Planned data model

1. `quest_steps`: one row per XP-earning step. Key columns: step_uid (unique), quest_id, step_id, quest_name, description, location, dlc, category, recommended_level, has_level_recommendation, reward_xp, mandatory, reward_rule_type, block_id, path_id.
2. `relationships`: edges (source, relationship_type, target):
   - `requires`: source before target, both still happen
   - `during`: target must sit inside source's open window (only for OPTIONAL inserts into a quest that keeps progressing; if the inner content is mandatory and blocking, use `requires`)
   - `excludes`: two single steps are mutually exclusive
   - `excludes_path`: two whole `path_id` groups are mutually exclusive
   - `unlocks`: taking source makes target available
   - `blocks`: taking source makes target permanently unavailable (cutoff / point of no return)
3. `reward_rules`: multiplier lookup (above).
4. `mandatory_block_lookup`: precomputed entry_xp → exit_xp for sealed blocks (sampled at low and high entry XP to check whether the total is level-sensitive).
5. `relationship_types`: documentation only. Optional `choice_groups` metadata.

## Modeling decisions

- Step_ID letters are cosmetic labels (a/b/c = mutually exclusive alternatives, `o` = optional, additive).
- Optional, consequence-free bonus (e.g. Axii use, ~25-40 XP): one row with `mandatory = False`, no dummy "didn't do it" row. It is a free variable (include/exclude toggle). It gets a `during` edge inside its mandatory neighbours, never a `requires` edge forward (the mandatory chain must be valid with all optionals removed).
- Real mutually exclusive branches: `path_id` + `excludes_path` (or choice groups for single steps). When a path group is reachable, exactly ONE member must be selected (not zero, not two); enforce this in the solution generator, not only in data.
- "Either ending unlocks the next quest": both endings get an `unlocks` edge to the same target, or use a zero-XP milestone node.
- Zero-XP synthetic "start quest" anchor rows (suffix `_START` / "zacznij zadanie") exist for when something external must point at a quest or the first real steps are optional/branching. They are structural, not real rewards.
- `path_id` and `block_id` can apply to the same steps (path decides which survives, block then collapses). Leave tags blank when there is no partner group.
- Sealed blocks can be collapsed to a single node only via an entry_xp → exit_xp lookup, not a flat sum, because XP per step depends on player level at entry. A flat constant is acceptable only if verified insensitive to entry level.
- Kaer Morhen battle (KMF6) and Isle of Mists (SF9) are treated as one sealed block; KMF7 and its level 20 value need confirmation.
- Side quests with deadlines (e.g. White Orchard side quests lost after leaving): `unlocks` for the lower bound plus a `blocks` edge from the cutoff step.

## Known cutoffs (from wiki/checklists)

- Imperial Audience (leaving White Orchard): fails On Death's Bed, Missing in Action, Twisted Firestarter (Frying Pan), Precious Cargo, etc. Only Faithful Friend survives later.
- Ugly Baby (taking Uma to Kaer Morhen): fails Following the Thread, The Last Wish.
- The Isle of Mists (19 quests fail): A Towerful of Mice, A Favor for a Friend, For the Advancement of Learning, Magic Lamp, An Invitation from Keira Metz, Ciri's Room, The Fall of the House of Reardon, Ghosts of the Past, Return to Crookback Bog, A Matter of Life and Death, Now or Never, A Deadly Plot, An Eye for an Eye, Redania's Most Wanted, A Dangerous Game, Cabaret, Carnal Sins, Fencing Lessons, Berengar's Blade. One source claims 25; check the Witcher Wiki "Cutoff Point" section.
- Battle Preparations (Skellige succession): The Lord of Undvik, Possession, King's Gambit, Coronation.
- On Thin Ice: Reason of State, Contract: Devil by the Well.

## Known data issues (from earlier review, not re-verified)

- Duplicate step_uid / Step_ID `END` in WOF3 (start and end rows); use unique ids.
- WOF1/WOF2 are not linear: The Beast of White Orchard (WOF2) runs after WOF1 step 3 and must finish before WOF1 ends. Model as a `requires` chain (WOF1 step 3 → WOF2 start, WOF2 end → WOF1 end), not `during`.
- WOF6 tragic ending takes place in Crookback Bog (Velen): fix location.
- XP values to double-check: Axii at the inn (25 vs 40), WOF2 endings (300/400 vs 350/500 in the sheet), Mislav wild dogs (350).
- WOF2 step 2 row is missing/duplicated pointers; several White Orchard `After` values reference non-existent ids (WOF1_S3 vs WOF1_S2/S4 renumbering, WOF2_S3a/b; WOZP5 steps 3a/3b/3c point at `WOZP5_S1a/b/c`, probably `S2a/b/c`).
- A row with Quest_ID `VF4` for a `VF3` step (Sprawy Rodzinne 6b) is likely a typo.

## Search / optimisation plan

- A solution = (ordering of selected steps, choice vector). Moves: swap/reorder, choice-flip (re-resolve availability and repair order), include/exclude toggle for optional steps.
- Evaluate: resolve availability (unlocks/blocks/excludes) → collapse sealed blocks via lookup → topologically valid order → simulate level/XP step by step → score = final level.
- Method: greedy constructive heuristic (do the quests about to become worthless first) as the starting point, then simulated annealing. Exact bitmask DP is infeasible for 100+ quests.
- Validate: compare to the greedy baseline, multiple seeds/restarts, brute force on a 10-15 quest subset, plot best-score vs iterations, verify the cliff boundary and the prerequisite graph.
