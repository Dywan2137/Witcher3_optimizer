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

## 2026-11-22: difficulty switch in the model (Story and Sword for chosen rewards)
- Game check (`r4Game.ws`): the difficulty is read when a quest reward is paid. Death March is 0.8, Blood and Broken Bones 0.9, lower difficulties 1.0. The Hearts of Stone bonus is added to that (0.16 per level of gap, capped at 1.5). The over-level cliff (5%) is the same on every difficulty. Lowering the difficulty below Blood and Broken Bones even once loses the Death March and Blood and Broken Bones achievements (`lowest_difficulty_used`).
- Code:
  - `State.low` holds the steps whose reward is taken on the lower difficulty, and `Taken.low` records it.
  - Rule types `<type>_story` are added to `Reward_rules` in v5 (`base_cliff_story`, `hos_gradual_story`; logged in `Change_log`).
  - `checker.check(ds, order, low)` recomputes the XP independently.
  - `upper_bound(plan, switch)`.
  - The local search has a new move, `difficulty` (one reward, or a run of up to 40), with `--switch` on `local.py` and on `export.py --local`. The second chain starts with every reward on Story and Sword.
  - The export has a `Difficulty` column and a Summary count.
  - New `tests/test_difficulty.py`: on 15 instances, brute force over every order x difficulty choice reaches the optimum 15/15. Full suite: 94 OK.
- Result: v5, 15 restarts, noise 2, local 2 x 4000. Without the switch, same settings:
  - all three parts: 100,585 XP (level 58) → **109,512 XP (level 62)**, with 841 of 1,121 rewards on Story and Sword;
  - base + hos: 70,593 (level 43) → **72,853 (level 44)**, with 637 of 887.
- This beats taking every reward on Story and Sword (the x1 experiment: 108,384 / 71,674). Staying on Death March for some rewards keeps the player under-leveled for what follows.
- Plans: `output/optimal_order_v5_local_{dm,switch}_{all,base_hos}.xlsx`.

## 2026-11-22: experiment: XP without the Death March multiplier
- What-if only, on v5 with blocks, same search as the export defaults. The `Reward_rules` were replaced in memory (scratchpad `norm.py`); plans are in `output/optimal_order_v5_{x1,flat}_*.xlsx`.
  - `x1`: Death March 80% → 100%. The over-level cliff (5% at gap <= -10) stays. Hearts of Stone becomes 1.0 + 0.16 x gap, capped at 150% (from gap +4) and at least 5%, with 100% at gap >= +10.
  - `flat`: every step x1, no penalty or bonus.
- Result, all three parts:
  - Death March 99,951 XP (level 57);
  - x1 108,384 (level 62);
  - flat 119,835 (level 67).
- Result, base + hos:
  - Death March 70,435 (level 43);
  - x1 71,674 (level 43);
  - flat 83,020 (level 49).
- With x1 the player levels faster, so more steps go over the cliff:
  - all three parts: 37 → 106 steps at 5% (7,815 face XP);
  - base + hos: 45 → 57 steps (9,255 face XP).
  - Base + hos therefore gains only +1,239 XP. Part of the Death March 80% "loss" is really what keeps the player under the cliff.

## 2026-11-22: experiment: no sealed blocks at all
- What-if only, no data change. v5 was loaded with every `Block_ID` cleared in memory, so every step can be interrupted for free roam. It was searched with the export defaults (25 restarts x 3 rule settings, noise 2). Script: the session scratchpad `noblocks.py`. Plans: `output/optimal_order_v5_noblocks_*.xlsx`.
- Result:
  - all three parts: 99,951 → 100,048 XP (+97; level 57 → 58, but only 48 XP over the line);
  - base + hos: 70,435 → 71,013 XP (+578, level 43).
  - Steps played at the 5% cliff: 37 → 34 and 45 → 23.
- Conclusion: the blocks cost at most a few hundred XP. Simply moving the flat activities to the end (with blocks) is worth more: 100,616 / 70,797.

## 2026-11-22: `Data/Witcher_3_quests_v5.xlsx`: abandoned sites and monster nests added
- v4 plus 81 new one-step rows (category `Aktywność`, `exempt_full`, no level, no block or path, no cutoff), from the game files. Each row is logged in `Change_log`; relationships were regenerated and validation passes.
  - 29 abandoned sites, 3,830 XP:
    - 24 `lw_rescuetown_*` rewards, paid by region code: plg 90, nml 120, nov 150, skl 170;
    - 5 Blood and Wine `poi_*_reward`, 120 each.
    - Yesterday's count (23) missed the Scoia'tael camp near Oxenfurt, which pays `lw_rescuetown_nov` from a scene script (`GiveRewardToPlayer`), not a quest reward block.
    - The region code is the game's, not the map's: `lw_gr12_ferry_station_2` (Velen) pays plg 90 and `sk10_woodcutters_lodge` (Skellige) pays nml 120.
  - 52 nests, 1,965 XP: 20 each plus the boss bonus (925 in total). The `mp4_warzone_island` bonus is left out (its boss tag does not match the nest).
- Placement: White Orchard rows on the White Orchard sheet; Velen, Novigrad-map and Hearts of Stone (`ep1_*`) rows on the Velen sheet; the Oxenfurt camp on the Novigrad sheet; Skellige and Toussaint rows on their own sheets.
  - Quest IDs: `<prefix>OM<n>` for sites and `<prefix>GN<n>` for nests (`WO`, `V`, `N`, `S`, `SZK`, `KIW`).
  - Gates: `WOF1_S1`, `VZF1_S2`, `SF1_S3` (arrival in Skellige), `SZKF1_S1`, `KIWF1_S2`.
- Result (default export):
  - all three parts: level 57, 99,951 XP (94,156 quest + 5,795 activities);
  - base + hos: level 43, 70,435 XP (65,540 + 4,895).
- The search is now worse on quest XP than in v4 (−665 / −362). It plays some activities before late quests, which raises the level too early. Flat XP is best done last.
  - The v4 order with every activity appended at the end gives 100,616 XP (level 58) and 70,797 XP (level 43).
  - So the search needs a fix (no-level flat steps should go after everything else), or the activities should be appended at the end.

## 2026-11-21: XP saturation by level (where the thresholds bind)

Analysis only. The tables are in `output/xp_saturation_all.csv` and `output/xp_saturation_base_hos.csv`.

- Method: for each deadline level D, add up the full-value XP of the plan's steps:
  - base and Blood and Wine steps: deadline = recommended level + 9, at 80%;
  - Hearts of Stone steps: deadline = recommended level − 5 (the end of the 150% window), at 150%.
- Then compare that running total with the XP at which you reach D+1 (`overload`). A positive overload means not everything can be paid at full rate, whatever the order.
- Result: overload is positive only for D = 30–39 (up to about +4,000 XP at D 33/35), and negative everywhere else.
  - In that stretch the base-game endgame (Bitwa w Kear Morhen, Wyspa Mgieł, Łysa Góra, Tedd Deireadh) meets the Hearts of Stone peak window (Hulaj dusza!, Sezamie, otwórz się!, Żyli długo i szczęśliwie).
  - The plan loses 3,554 XP against the Hearts of Stone 150% value and 488 XP to the base-game cliff, almost all of it there.
  - Above level 40 there is spare room (−2,000 to −9,000), and the plan already does most no-level XP there (2,513 of 4,173 after level 45).
- Plan for 2026-11-22 (agreed with the user to continue tomorrow):
  - Look at the saturated stretch (deadlines 30–39) and whether anything in the data can ease it. In particular, check where the Hearts of Stone quests sit against their 150% window (Żyli długo i szczęśliwie −1,482, Sezamie, otwórz się! −903).
  - Possibly add the out-of-quest XP to the data so the optimizer places it after level 40 itself: abandoned sites 3,080, Blood and Wine map rewards 600, nests 1,040, nest bosses 925, all flat 100% (see the nests entry below).
  - Still open: whether to seal SF2_S4 and SZP22_S3/S4 (fast travel locked in the game, no block in our data), and committing v4 so it replaces v3 on GitHub.

## 2026-11-21: Block_ID checked against the game's free-roam locks

The results are in `output/block_check_game.csv`. The user reviewed the split candidates: only Panie Lasu can be split. VF9_S3 Block_ID `VF9_BLOCK` → `-` in v4; S1+S2 stay as the usual start block. The change is logged in `Change_log`, relationships were regenerated and validation passes. The other candidates stay sealed. Re-export with the same settings: base + hos 65,866 → 65,902 XP (level 40, 831 steps); all three parts 94,740 → 94,821 XP (level 55, 1,045 steps).

- The game has no "block" concept. A sequence is sealed when one of these happens:
  - fast travel or meditation is locked (`BlockGameplayFunctionality` with `lock=1` and the `fastTravel` flag set; `BlockGlobalFastTravelQuest`);
  - scenes chain straight into the next reward;
  - the world changes, a denied area is set, or the player plays as Ciri.
- Method:
  - Ran a must and may data-flow of the fast-travel lock over the context-sensitive quest graph.
  - For each pair of linked steps inside a block, checked whether the game flow between the two rewards waits for a free-roam action: a trigger area, an interaction, a dialogue with an NPC, clues, a container, an item count or a book.
- Confirmed sealed (fast travel locked on every path):
  - KMF6 battle steps S5–S11;
  - VF15 S2–S3;
  - SZKF2 S3–S11;
  - the second step of KMF4, SZKZP3, SZP13, KIWF3 and WOF4;
  - KIWF8 S2–S3.
- Locked in the game but in no block: SF2_S4 (after the fist fight) and SZP22_S3/S4.
- Free roam between members, with no lock (candidates to split):
  - VF8 (Po omacku);
  - VF3_BLOCK_2 (Sprawy Rodzinne S6–S8);
  - VF9;
  - NF7 / NF7_BLOCK_1;
  - NF1_BLOCK_1;
  - SZKF3 and SZKF3_BLOCK_1;
  - most of SZKF7;
  - SZP19;
  - VZB18_S3→S4;
  - KIWF8 after S3 (S3→S4→S5, KIWF9_S2→S3, KIWF10_S3→S4);
  - SZKF2_S12/S13 and SZKZP7;
  - VF15_S3→S4;
  - SF5_S2→SF4_S2, which was kept in one block at the user's request.
- 73 pairs are not linked in the graph (contracts with separate reward-giver phases, and fact links) and 394 have no reward on one side (0 XP start steps). These cannot be judged this way.

## 2026-11-21: XP outside quests (nests, abandoned sites), from the game files

Not in the data yet; estimate only. The list is in `output/nest_bosses.csv`.

- Abandoned sites: 23 `lw_rescuetown_*` reward blocks. They pay White Orchard 90, Velen 120, Novigrad/Hearts of Stone 150, Skellige 170, at level 0, so always 100%. Total 3,080 XP. Blood and Wine has 5 `poi_*_reward` worth 600 XP.
- Nests (`CMonsterNestEntity`): 52 playable, not counting the 2 in `prolog_village_winter`. That is 37 in base + Hearts of Stone and 15 in Blood and Wine, each paying 20 XP when destroyed.
- Nest bosses: 14 nests have a `CSpawnTreeMonsterNestMonitorInitializer` boss, worth 925 XP in total. The bonus is 50/75/100 depending on the template. Blood and Wine nests have none. `mp4_warzone_island` has a boss monitor tagged `lw_mp4_nekker_nest`, but the nest there is `lw_mp4_rotfiend_nest`, so that bonus likely never fires.
- Places of power give a skill point, not XP.
- Effect: base + Hearts of Stone goes from 65,866 to about 70,600 (level 40 → 43). All three parts go from 94,740 to about 100,400 (level 55 → 58). Kill XP is extra.

## 2026-11-21: `Data/Witcher_3_quests_v4.xlsx`: step order checked against the game's quest graphs
- Source: the game's `.w2quest` / `.w2phase` files (1,041, read only from the bundles), parsed into the quest flow graph (one copy of each phase per place it is used; phase input/output sockets matched by name; fact set -> fact wait links as weaker evidence). The 1,010 `CQuestRewardBlock`s carry the reward codes, so the order of rewards in the game was compared with the order of our steps. 606 of 749 paying steps matched a reward node (the rest are paid inside dialogue scenes, not parsed). All findings: `output/game_order_check.csv` (86 rows).
- Fixed in v4 (v3 kept; every change in `Change_log`):
  - Władca Undvik: `SZP31_S5o` (Vigi) is now cut off by `SZP31_S6` (the game's saved_vigi leads to killed_giant); `S3o`/`S4o` by `SZP31_S8` (quest end; their rewards are paid in scenes, so the exact deadline is not in the graph). The Isle of Mists cutoff `SF9_S1` stays. The v3 plans did these rescues after the giant / after the quest.
  - Novigrad finale: `NF12_S2` (q310_9_lodge_gathered, 1000) now comes after `NF18_S3` (the game pays it after Wielka ucieczka, Wyrównanie rachunków, Najciemniej pod latarnią and Ostatnia przysługa); NF12_BLOCK removed; `NF13_S1` after `NF12_S1`; `NF17_S1` (q310_10_lessons_learned) after `NF12_S2`; `NF18_S1` after `NF16_S2`.
  - Sprawy Rodzinne: `VF3_S10` now also needs `VF3_S8` (the game's q103_05 leads to q103_07); before, the quest end did not depend on the middle of the quest.
- Reordered to the game's reward order (second pass, same day):
  - Żyli długo i szczęśliwie: study `S10` -> summer world `S13` -> cellar `S11` -> sad dinner `S12` -> `S14`.
  - Spis cudzołożnic: `S3` (300) is q304_07_visited_all_girls, now after the last visit (`S9`, before `S10`) and renamed.
  - Niech żyje sztuka: play `S4` -> Blanka `S7` -> Abelard `S6` -> actress `S8` -> Maskonury bonus `S9` -> all lines right `S5` -> Axii `S10`.
  - Niebezpieczny ładunek: free the owner `S3` -> burn the cart `S2` -> `S4`.
  - Ktokolwiek widział + Bezimienny (author): one sealed block `SF4_BLOCK`, order `SF4_S1` -> `SF5_S1` -> `SF5_S2` (Skjall found) -> `SF4_S2`; `SF6_S1` now after `SF4_S2`.
  - Po omacku / Magiczny kaganek: `VF8_S7` (completion) -> `VZB19` (lamp), still inside `VF8_BLOCK` (author: the lamp must be taken before leaving the ruins); `VZB24_S1` (Keira) now needs `VZB19_S2`.
  - Not changed, author checks in game: Zagłada domu Reardonów (game pays the 25 XP end before the Humbert rewards, which need the body found).
  - Result: unchanged (greedy base + hos 65,445 XP level 40, all scopes 94,107 XP level 55); the moves are a few positions and cross no level-up.
- Regression found (author): `Witcher_3_quests_game_xp.xlsx` set to 0 every step whose XP was not in `rewards.xml`, but dialogue payments and Axii are paid by the scene script (`choiceActions.ws`: payment = money / 10 rounded up, Axii = 20 + 5 x Axii level, both flat through `AddPoints`), so they never appear in `rewards.xml`. The game's XP sources are only: `rewards.xml` (quest graphs and scenes), these dialogue choices, and world XP (kills, nests, places of power). The 153 Axii / payment choices were extracted from the 6,380 scene files and every XP reduction in the game_xp `Change_log` was checked against them. Restored in v4 (`exempt_full`, no level):
  - `SF1_S2` paying Wolverstone 1000 -> 100 XP (the q201_07_afterparty 100 on `SF2_S6` is a separate reward, kept); `NZB54_S2` entry fee 1000 -> 100 XP; `KIWZP32_S5` paying for the portrait 1000 -> 100 XP.
  - `SZKZP2_S2b` (150 in the wiki) = paying Vimme 1000 crowns (100 XP, flat) + mq6003_completed 50: split into `S2b` (payment) and a new `S3b` (completion, 50 hos_gradual; row appended at the end of the Velen sheet).
  - The other reductions have no Axii / payment option in their quest's scenes and stand. Still open: `NZB19NA_S1` (a 100-crown payment at the Novigrad race start = 10 XP?) and `WOZP5_S2b` (the Axii XP on top of the 25 quest reward).
  - Result (greedy, 15 restarts x 3): all scopes 94,107 -> 94,154 XP (level 55); base + hos 65,445 -> 65,392 XP (level 40; greedy noise, 300 XP more is available).
- Axii / payment corrections (author's call; Axii still assumes full Delusion = 40 XP where the option needs it, except at the very start):
  - `WOF1_S3a` Axii at the inn 40 -> 25 (level 1, no Delusion points possible yet).
  - `WOZP5`: new step `WOZP5_S2bx` = the Axii XP (25, exempt_full) on top of the 25 quest reward of `S2b`, in `WOZP5_BLOCK_B` / `WOZP5_PATH_B`, `S3b` now after it (row appended at the end of the White Orchard sheet). 25 assumes no Delusion yet in White Orchard.
  - `SZP22_S2b` "don't use Axii" 40 -> 0 (no game reward; sq209 pays only the tavern 50 and Lugos 80; the Axii XP stays on `S2a`).
  - Payments made flat / rounded as the game does: `SZP15_S2b` (500 crowns, 50) base_cliff -> exempt_full; `VF2_S2b` 1 -> 2 and exempt_full; `NZB13NA_S2a` 5 -> 3; `VZB11NA_S2` 52 -> 53.
  - Not changed (author): the 100-crown payment at the Novigrad race start (`NZB19NA`); the game file does not flag it as no-XP, so if XP shows up in game it is 10.
  - Result (greedy): base + hos 65,394 XP (level 40), all scopes 94,156 XP (level 55).
- Export (15 restarts, 2 x 4000 annealing iterations, final v4): all scopes level 55, 94,740 XP, 1044 steps (v3: 94,536, level 56 needs 96,000) -> `output/optimal_order_v4_all.xlsx`; base + hos level 40, 65,866 XP, 823 steps (v3: 65,541; level 41 needs 66,000) -> `output/optimal_order_v4_base_hos.xlsx`. Checked in the plans: the Undvik rescues come before the giant, NF12_S2 after the Novigrad side of the finale, VF3_S10 after VF3_S8.
- Checked and not changed: Pogłos (KIWF4). `q702_04_wight_brew_obtained` (1000) is paid on both paths, so the totals (path A 2000, path B 1650) match the game.
- Result (greedy, 15 restarts x 3 settings): base + hos 64,928 -> 65,445 XP (level 40); all scopes 93,590 -> 94,107 XP (level 54 -> 55). No annealing run yet.

## 2026-11-11: `Data/Witcher_3_quests_v3.xlsx`: checked against the game files
- Source: the game's own files (read only): `rewards.xml` of the base game, ep1, bob, dlc3/12/15 (898 rewards: base 73,280 XP, HoS 11,400, BaW 41,100, free DLCs 1,150), `geralt_levelups.xml`, `exp_mods.csv` (kills and quests x1), and the scripts `r4Game.ws` (OnGiveReward) / `gameParams.ws` (LEVEL_DIFF_HIGH 10, LEVEL_DIFF_XP_MOD 0.16, MAX_XP_MOD 1.5).
- Confirmed correct: `Reward_rules` (level 0 = 100%; gap <= -10 = 5%; Death March 80%; HoS 0.80 + 0.16 x gap capped 150%, floored to 5%, back to 80% at +10). The HoS scale applies to reward codes containing `q60`, which are exactly our `hos_gradual` steps. `Data/quest_xp_rewards_named.csv` is identical to the game rewards (names, levels, XP). The game rounds each reward to an integer (we do not; a few XP at most). The game halves base/BaW quest XP when the fact `witcher3_game_finished` is above 1 (looks like New Game+ only).
- Fixed in v3 (v2 kept as the previous version; every change in `Change_log`):
  - `Level_table` = the game table: +500 XP from level 11, +1,000 from level 21 (level 55 needs 94,000), 2,000 per level after 50.
  - Quest levels: Szepczące Wzgórze 5 -> 6, Więzy krwi 12 -> 7, Przysługa dla Radowida 9 -> 12, Miecz rodowy 15 -> 12, Ścieżki Przeznaczenia 43 -> 46, SZKF6_S3 35 -> 34; Niespokojna okolica and Szlak bohaterów have game level 0 (100%, `exempt_full`).
  - XP: NF13_S4 (duplicate 1,000) removed; Na łasce obcych start step 25 -> 0 (the 25 was counted twice); Biada mi! 30 -> 15; Bardzo cenny róg 20 -> 25; Pijany motłoch's 25 XP completion split out of both choices (5 / 40 + 25).
  - Added: Bez i agrest `WOF1_S5` Yennefer's raven skull 50 XP (level 0; the quest end is now `WOF1_S6`, the White Orchard cutoff follows it), Cena przejścia first guard encounter 10, Kurtyzana w opałach first encounter 25.
  - Niech żyje sztuka (author: maximise every choice): completion 500 + bonuses as separate steps: all lines right 150, Abelard 110, Blanka found 50, actress 25, jugglers 25, plus the wiki's Axii at the Maskonury 40.
- Hidden XP logic scan (scripts + every quest/scene file in the bundles, read only): no quest reward ignores the player level except level-0 rewards (107, already `exempt_full`). `BoostPlayerLevel` (HoS/BaW start boosts) only raises a low level; `SetGeraltLevel` is a debug helper; `SetRewardModifierScene` (contract haggling) scales only gold/items. Flat XP outside the reward table: Axii in dialogue 20 + 5 x (1 + Delusion level) = 25-40, dialogue payments money / 10, monster nests 20 + boss bonus, places of power.
- So 34 Axii / payment steps were switched to `exempt_full` (always 100%; yellow cells, `Change_log`). Not switched (Axii XP mixed with a quest reward): VZB14NA_S3b 90, VZW12_S3b 215, NZB18NA_S2b 65.
- Kill XP (npc.ws, not modelled yet): enemy stats / 99, capped at 1 + 2 x level (humans) or 5 + 4 x level (monsters), + 1; / 4 below player level 30, / 2 from 30; enemy 10+ levels below = 2 XP; from player level 35 a further level-gap cut and / 2 (min 2).
- Result (export: 15 restarts, 2 x 4000 annealing iterations; game level table; no kill XP): all scopes 94,152 -> 94,536 XP after the Axii fix (level 55; level 56 needs 96,000); base + hos 65,508 -> 65,541 XP (level 40; level 41 needs 66,000). Plans in `output/optimal_order_v3_*.xlsx`.
- Not changed: Kasiarz (Casimir or the safecracker, 150 either way) and Jak kot z wilkiem (kill or spare, 200 either way) were alternatives, not missing rewards. Still open: Leże Bestii `q702_08b_bootblack_fight_lost` 400, Tasak `nogold` 200 / `beggarking` 100, and about 15 wiki steps with no game reward.

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
