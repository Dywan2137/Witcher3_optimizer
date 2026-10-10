# Witcher3_optimizer

Finds the order of doing Witcher 3 quests (base game, Hearts of Stone, Blood and Wine) that gives the highest
character level at the end of a single playthrough, without New Game+. Level-dependent quest rewards (Death March)
make the order matter: quests done too late pay almost nothing.

## Status

| Step | What | State |
|---|---|---|
| 1 | Load and validate the quest data | done |
| 2 | Simulator and independent solution checker | done |
| 3 | Decision units (free steps, sealed blocks, path choices, optional toggles) | done |
| 4 | Baselines (story order, random) and upper bound | done |
| 5 | Greedy policy and randomized restarts | done |
| 6 | Local search / beam search, brute-force check on a subset, result report | todo |

The data is still being completed by hand; run `python main.py --units` for the current issues.

## Layout

```
Data/                    quest workbook (one sheet per region + Relationships, Reward_rules, Level_table)
witcher3/
  loader.py              workbook -> pandas tables, data validation
  build_relationships.py regenerates the '<Region> Relationships' sheets from Before/After/Block_ID/Path_ID
  simulator.py           step-by-step game rules: availability, rewards, levels, sealed blocks
  checker.py             independent re-check of a finished ordering (does not share code with the simulator)
  units.py               decision units the search works with
  baselines.py           reference results: story order, random playthroughs, upper bound
  greedy.py              greedy policy (propagated deadlines, cutoff guard, Hearts of Stone wait) and randomized restarts
  export.py              writes the best playthrough to an Excel file for the player (Plan / Skipped / Summary)
tests/                   unittest suite
main.py                  command line: load, validate, summarize
CLAUDE.md                detailed project and data conventions
```

## Usage

```
pip install -r requirements.txt
python main.py                  # summary + data validation (exit code 1 on errors)
python main.py --units --all    # also decision-unit stats and diagnostics, every issue listed
python -m witcher3.baselines --random 20  # reference numbers (story order, random, upper bound)
python -m witcher3.greedy --restarts 40   # greedy on base game + Hearts of Stone (--scope base,hos,bw to change)
python -m witcher3.greedy --random 0 --steps --csv plan.csv   # the playthrough as an ordered step list (screen / CSV)
python -m witcher3.export                 # output/optimal_order.xlsx: the order to play, ~2 min (--restarts 0 for a quick one)
python -m witcher3.build_relationships   # after editing Before/After/Block_ID/Path_ID in the workbook
python -m unittest              # tests (about 40 s)
```

Every runnable file (`main.py` and the modules above) also starts
as a plain script from any folder, e.g. with an IDE Run button; `tests/test_entrypoints.py` checks that.

Close the workbook in Excel before running anything that writes to it.
