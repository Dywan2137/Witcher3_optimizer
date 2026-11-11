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

## 2026-11-11: `Data/Witcher_3_quests_v2.xlsx`: Dorwać Juniora x Gangi Novigradu
- New file `Data/Witcher_3_quests_v2.xlsx` = `Witcher_3_quests_game_xp.xlsx` (left unchanged as the previous version) + the Junior/Tasak model, regenerated Relationships, and a `Model_notes` sheet with the special rules and open questions.
- Model (author's rules): the arena and the casino are separate choices, each Axii / bribe / Tasak's men (`NF4_S3a/b/c`, `NF4_S5a/b/c`, one closes the others; Tasak's options need `NZB26_S1`). Each site is investigated afterwards: `NF4_S4` arena 150 and `NF4_S6` casino 150 (game `q302_02_investigated_ring/_casino`; this was the wiki's 300 on the old S5). Later NF4 steps renumbered (Junior is now `NF4_S9`). Tasak's reward: `NZB26_S2a` both sites stormed (full), `S2b` arena only / `S2c` casino only (half; 50 XP per the game file, the wiki said 25), `S2d` neither (quest fails, 0 XP). The NZB26 block was removed because its rewards come after NF4 progress. All nine combinations were played through `Plan` and leave exactly the expected reward open.
- Assumption to test in game: after Axii or a bribe at a site, Tasak's men can no longer storm it. Game rewards `q302_02_cleaver_reward_nogold` (200 XP) and `_beggarking` (100 XP) are not modelled yet.
- Code: `build_relationships` reads `A & B` in After as "needs both" (one requires per part). The `blocker_is_prerequisite` check now ignores a blocker that sits on only one of several alternative routes (it flagged Axii at the arena blocking "arena only" although the casino is also reachable through the bribe or Tasak); new test in `tests/test_validate.py`. Full test suite passes.
- Result (greedy, v2 vs game_xp): base + hos 64,018 -> 63,978 XP (level 40); all scopes 92,670 -> 92,630 XP (level 54). Greedy uses Axii at both sites (80 XP, against 50 from Tasak).

## 2026-11-11: Split steps kept in their block; visual file of the new steps
- Author's rule: when a step inside a block is split, every piece stays in that block. 49 rows in `Data/Witcher_3_quests_game_xp.xlsx` got their quest's block back (contract finals, gear-hunt diagrams, VZB18, VZB37, SZP44, SZW6 4a, KIWZP37 3b; logged in `Change_log` as "block restored"). This replaces the start-block-only handling in the entry below. Relationships regenerated, validation clean.
- New `Data/Witcher_3_new_steps.xlsx` (visual only, values not formulas): every quest with a new step, one sheet per region in the workbook's own columns and colours, with a "Zmiana" column (new step + game code, renumbered Step_ID, changed XP/After/Block_ID). Sheet `Tylko_wiki` lists the quests that pay XP but are missing from the game reward table (Honor złodzieja, Awantura o wino: Konsorcjum, Więcej niż mistrz, plus the Axii/choice-only ones). The author remembers getting XP for them, so they stay in the data and need watching.
- Result (greedy, game_xp workbook): base + hos 64,018 -> 64,018 XP (level 40); all scopes 92,630 -> 92,670 XP (level 54).

## 2026-11-11: Missing game rewards added; last CSV rows named
- `Data/Witcher_3_quests_game_xp.xlsx`: three rewards the wiki left out were added as new steps (author's descriptions): Śmierć w ogniu `VZB37_S3` 10 XP on completion (S2 is the 25 XP for saving the elf), Smutna historia braci Grossbart `SZP44_S2` 50 XP for finding the hideout (the 25 XP end is now S3), Po nitce do kłębka `NZB31_S5` 50 XP from Crach after killing Hammond (only if you talked to Crach first; the Tauler choice is now `NZB31_S6a/b`, still after S4). The tournament card step `KIWZP20_S4` now reads "po zakończeniu zadania". Relationships regenerated, validation clean.
- `Data/quest_xp_rewards_named_polish.csv`: step names filled for cg700_tournament_card, sq106_3_hammond_killed_crach, mq1046_burning_down_the_house_reward, mq2013_1_location_reward and mq3023_3_we_are_awesome (= "Ośmiesz kapłana", the choice that leads to the witch-hunter fight, already `NZB14NA_S2`); sq313_1_ruse_complete = Niespokojna okolica; the four boat races (br201/br202/br301/br302) are cut content and marked `-`.
- Honor złodzieja (NZB27, 100 + 150 XP) is not in the game reward table, but the quest exists and pays XP; kept from the wiki, like the two Toussaint quests below.
- Result (greedy, game_xp workbook): base + hos 64,000 -> 64,018 XP (level 40); all scopes 92,612 -> 92,630 XP (level 54).

## 2026-11-11: Summed wiki steps split in `Data/Witcher_3_quests_game_xp.xlsx`
- Where one wiki step was the sum of several game rewards, it is now one row per reward (63 new dark-green rows, the original row kept as the last piece with its XP reduced, light green; 290 entries in `Change_log`, each new row tagged `(gra: <reward code>)`). Covered: every contract with an investigation reward (WOZW1, VZW3-9, VZW12, NZW1-8, SZW1-4, SZW6, SZW7, SZW9), the five grandmaster gear hunts (one step per stash), Żyli długo i szczęśliwie (8 memories), W księżycową jasną noc, Duchy przeszłości, Przyjacielska przysługa, Zagłada domu Reardonów, Gonitwa Erazma Vegelbuda, O wysoką stawkę (four card wins), Obcy w obcym kraju, Królewski Gambit (900 = one path 500 as new `SZP34_PATH_A/B` steps + Crach's 400) and Równowaga w przyrodzie (spare path 200 + count's thanks 50). Later steps were renumbered and every Before/After pointing at them redirected; Relationships regenerated, validation clean.
- Contracts follow the start-block convention: the start step and the first new piece share the block, the final reward is now outside it.
- Not split: Dorwać Juniora S5 (Roche and Radovid already have their own steps), Niech żyje sztuka (alternatives, not a sum), Zlecenie: Potwór z lasu (both 25 XP rewards fire together). Zdravko's 150 XP for the gear diagrams is not in the workbook.
- Why: the game pays these rewards at different moments (and so at different levels).
- Result (greedy, game_xp workbook): base + hos 64,000 -> 64,000 XP (level 40); all scopes 92,652 -> 92,612 XP (level 54). The working file is unchanged.

## 2026-11-11: Polish names filled in `Data/quest_xp_rewards_named_polish.csv`
- Blank or `?` quest names were matched to the workbook's Polish names through the game folder names (from the public file-path dump at gist.github.com/Berny23/6f45582df8dcd63c17565568eae87195); English quest names were replaced by the workbook's Polish ones; blank step names were filled from the workbook steps (same quest and XP) or as a short Polish description of the reward code. `id` was filled on every row touched. Only the `id`, `quest_name` and `step_name` columns changed (198 rows).
- Confirmed by the author: ff205 = Wściekłe pięści: Mistrz nad Mistrzami, mq3015 = Najprawdziwszy z bazyliszków, mq7020 = W służbie muzy, q402_1_full_crew_achiv = Towarzysze broni (Full Crew bonus), mq003_02_found_sister = duplicate of mq0003_02_found_sister.
- Why: to know which quest each game reward belongs to. No XP/level effect (the simulator does not read this file).
- Follow-up by the author: Więzy krwi = mq1051 (the game sets it at level 7, the wiki at 12; same XP and description), W księżycową jasną noc = q602_romance_gift + q602_romance_end (the wiki summed them into one 300 XP step), Sąsiedzka sprzeczka = mq4003 (was "Monster Slayer").
- Not in the game reward table, but the quests exist and pay XP (kept from the wiki): Awantura o wino: Konsorcjum (KIWZP22, 200 XP) and Więcej niż mistrz (KIWZP28, 150 XP). Axii/bribe steps are also absent from the table (the game stores that XP elsewhere) and stay as the wiki has them.

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
