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
| 4 | Baselines and upper bound | todo |
| 5 | Greedy search, then randomized restarts / beam search / local search | todo |
| 6 | Validation against brute force on a subset, result report | todo |

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
tests/                   unittest suite
main.py                  command line: load, validate, summarize
CLAUDE.md                detailed project and data conventions
```

## Usage

```
pip install -r requirements.txt
python main.py                  # summary + data validation (exit code 1 on errors)
python main.py --units --all    # also decision-unit stats and diagnostics, every issue listed
python -m witcher3.build_relationships   # after editing Before/After/Block_ID/Path_ID in the workbook
python -m unittest              # tests (about 10 s)
```

Close the workbook in Excel before running anything that writes to it.
