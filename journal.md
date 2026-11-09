# Journal

A record of every important change to the project: code, data, rules and results. Newest entries first. Each entry has a date, what changed, and why (plus the result, when a change moves the numbers).

Format:

```
## YYYY-MM-DD: short title
- What changed.
- Why.
- Result (XP / level before -> after), if any.
```

---

## 2026-10-23: Game-file XP applied to a copy of the workbook
- New file `Data/Witcher_3_quests_game_xp.xlsx`: a copy of the working workbook with the differences against `Data/quest_xp_rewards_named.csv` (rewards extracted from the game files) applied and colour-coded (yellow = level, light green = reward, dark green row = new step, red row = removed step kept in place, orange ID = quest with no game match). Sheets `Change_log` (every change with its game reward code) and `Game_unmapped` (game rewards not matched to any quest) were added. The working file is unchanged.
- Main fixes: Battle of Kaer Morhen +1,750 (three new steps), Blood on the Battlefield (KMF7) 1,000 -> 0, Through Time and Space (NF13) duplicate 1,000 step removed, Bald Mountain +500, missing contract investigation rewards, Pyres of Novigrad / Novigrad Dreaming levels swapped back (7 / 10), fist fights and the two free-DLC contracts made level-free (game level 0).
- Why: the wiki-based values had a few missing and duplicated rewards; the game file is the reference.
- Result (greedy, no restarts): base + hos 63,124 -> 64,000 XP (level 40 both); all scopes 91,616 -> 92,540 XP (level 54 both). The loader still reads the red (removed) NF13_S4 row, so these numbers still include its 1,000 XP.

## 2026-10-23: Journal started
- Added `journal.md`. Earlier entries below were reconstructed from git history and `CLAUDE.md`.

## 2026-10-20: Reward rules updated
- `Reward_rules` sheet changed: the base-game cliff moved from gap -11 to -10, the Hearts of Stone 150% peak widened from +5 to +5..+9, and gap -5 dropped to 5%.
- Results with the new rules: greedy 63,124 XP (level 40) on base + hos, 91,616 XP (level 54) with all three scopes; story order level 34 / 48. Results recorded before this date used the old rules.
- Brute-force test: greedy now matches the optimum on 14/25 instances; local search needed 800 iterations x 3 chains (300 left one instance at 87%).

## 2026-10-16: Local search (simulated annealing)
- Added `witcher3/local.py`: priority-key annealing on top of the best greedy run, with shift, swap, segment, choice and insert moves; added `tests/test_local.py` and `tests/test_bruteforce.py` (exact optimum on 25 random 9-step instances).
- All three scopes: 92,491 XP (level 54, +502 over greedy, 509 XP short of level 55); base + hos: 63,998 XP (level 40, +331). Recovers some cutoff victims (lost steps 116 -> 91).
- Added `witcher3/cli.py` (shared `--file`/`--scope` arguments) and `tests/test_validate.py`.

## 2026-10-10: Baselines, greedy search and Excel export
- Added `baselines.py` (story order, random, upper bound), `greedy.py` (cutoff guard, HoS window, effective deadlines), `export.py` (`output/optimal_order.xlsx`) and `build_relationships.py`.
- Effective deadlines (a step inherits the earliest deadline of anything that needs it) took the full game from level 51 to 54.
- Quest data fixes: blocks merged so sealed chains can complete (`VF2/VF3/VF8/NF6/SZKF2_BLOCK_1`), quest-level choices in Blood and Wine, entry gates per region.

## 2026-10-10: Loader, simulator, checker and decision units
- Added the `witcher3/` package: `loader.py` (load + validate the workbook), `simulator.py`, an independent `checker.py`, and `units.py` (free steps and sealed-block units the search chooses between). Repo restructured, tests in `tests/`.

## 2026-07-23: Project started
- Initial commit and the Witcher 3 quest workbook (`Data/Witcher_3_quests.xlsx`).
