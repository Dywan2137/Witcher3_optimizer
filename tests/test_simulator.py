"""Run with: python -m unittest -v"""
import random
import unittest

from tests.helpers import real, tiny
from witcher3.checker import check
from witcher3.simulator import Model, simulate, start_state, available, take, why_not

REAL = real()


def ok(ds, order):
    simulate(Model(ds), order)
    assert check(ds, order)[0] == [], check(ds, order)[0]


def bad(test, ds, order, text=''):
    with test.assertRaisesRegex(ValueError, text):
        simulate(Model(ds), order)
    test.assertTrue(check(ds, order)[0], 'checker accepted an order the simulator rejected')


class Tables(unittest.TestCase):
    def test_level_of(self):
        m = Model(REAL)
        for xp, lvl in [(0, 1), (999, 1), (999.9, 1), (1000, 2), (182999, 99), (183000, 100), (10 ** 9, 100)]:
            self.assertEqual(m.level_of(xp), lvl, xp)

    def test_cliff_boundary(self):
        m = Model(REAL)
        self.assertEqual(m.multiplier('base_cliff', -10), 0.8)
        self.assertEqual(m.multiplier('base_cliff', -11), 0.05)
        self.assertEqual(m.multiplier('base_cliff', -999), 0.05)
        self.assertEqual(m.multiplier('base_cliff', 50), 0.8)

    def test_hos_table_matches_sheet(self):
        m = Model(REAL)
        for r in REAL.reward_rules.itertuples():
            for gap in range(r.level_gap_min, r.level_gap_max + 1) if r.level_gap_max - r.level_gap_min < 50 else [r.level_gap_min, r.level_gap_max]:
                self.assertEqual(m.multiplier(r.reward_rule_type, gap), r.multiplier, (r.reward_rule_type, gap))
        self.assertEqual(m.multiplier('hos_gradual', 5), 1.5)
        self.assertEqual(m.multiplier('hos_gradual', 6), 0.8)
        self.assertEqual(m.multiplier('hos_gradual', -6), 0.05)

    def test_no_level_pays_full(self):
        self.assertEqual(Model(REAL).multiplier('base_cliff', -50, has_level=False), 1.0)


class Rules(unittest.TestCase):
    def test_requires(self):
        ds = tiny([('A', 'Q', {}), ('B', 'Q', {})], [('A', 'requires', 'B')])
        bad(self, ds, ['B'], 'requires A')
        ok(ds, ['A', 'B'])

    def test_unlocks_is_any_of(self):
        ds = tiny([('A', 'Q', {}), ('B', 'Q', {}), ('C', 'Q', {})], [('A', 'unlocks', 'C'), ('B', 'unlocks', 'C')])
        bad(self, ds, ['C'], 'needs one of')
        ok(ds, ['B', 'C'])

    def test_blocks(self):
        ds = tiny([('A', 'Q', {}), ('B', 'R', {})], [('A', 'blocks', 'B')])
        bad(self, ds, ['A', 'B'], 'unavailable')
        ok(ds, ['B', 'A'])

    def test_excludes(self):
        ds = tiny([('A', 'Q', {}), ('B', 'R', {})], [('A', 'excludes', 'B')])
        bad(self, ds, ['A', 'B'], 'unavailable')
        ok(ds, ['A'])

    def test_path_exclusion_and_anchor(self):
        ds = tiny([('S', 'Q', {'tags': ('X', 'Y')}), ('A', 'Q', {'tags': ('X',)}), ('B', 'Q', {'tags': ('Y',)})],
                  [('X', 'excludes_path', 'Y')])
        ok(ds, ['S', 'A'])
        ok(ds, ['S', 'B'])
        bad(self, ds, ['S', 'A', 'B'], 'excluded path')
        bad(self, ds, ['A', 'S', 'B'], 'excluded path')       # anchor after the choice, then the other path

    def test_sealed_block(self):
        ds = tiny([('A1', 'Q', {'block': 'T'}), ('MID', 'Q', {}), ('A2', 'Q', {'block': 'T'}), ('OUT', 'R', {}),
                   ('OPT', 'Q', {'block': 'T', 'optional': True})],
                  [('A1', 'requires', 'MID'), ('MID', 'requires', 'A2')])
        # A1 opens the block; MID (same quest, no block tag) is allowed; OUT (another quest) is not
        bad(self, ds, ['A1', 'OUT'], 'block T is open')
        ok(ds, ['A1', 'MID', 'A2', 'OUT'])             # the optional member does not keep the block open
        ok(ds, ['OUT', 'A1', 'MID', 'A2'])

    def test_other_block_cannot_start_inside_a_block(self):
        ds = tiny([('A', 'Q', {'block': 'T'}), ('A2', 'Q', {'block': 'T'}), ('B', 'Q', {'block': 'U'})], [])
        bad(self, ds, ['A', 'B'], 'block T is open')

    def test_block_closes_when_members_become_unavailable(self):
        ds = tiny([('A', 'Q', {'block': 'T'}), ('B', 'Q', {'block': 'T'}), ('OUT', 'R', {})], [('A', 'blocks', 'B')])
        ok(ds, ['A', 'OUT'])

    def test_rewards_depend_on_level(self):
        ds = tiny([(u, 'Q', {'xp': 1000, 'rec': 1}) for u in 'ABC'], [])
        r = simulate(Model(ds), ['A', 'B', 'C'])
        self.assertEqual([t.gain for t in r.trace], [800, 800, 800])
        self.assertEqual([t.level_before for t in r.trace], [1, 1, 2])      # 800 and 1600 XP -> levels 1 and 2
        self.assertEqual([t.gap for t in r.trace], [0, 0, -1])
        self.assertEqual((r.xp, r.level), (2400, 3))

    def test_cliff_applies_at_minus_11(self):
        m = Model(tiny([('A', 'Q', {'xp': 1000, 'rec': 1})], []))
        s = start_state(m, xp=REAL.level_table.loc[11, 'cumulative_xp_to_reach_level'])   # level 12
        self.assertEqual(s.level, 12)
        self.assertAlmostEqual(take(m, s, 0).gain, 50)                                   # gap 1 - 12 = -11 -> 5%
        s = start_state(m, xp=REAL.level_table.loc[10, 'cumulative_xp_to_reach_level'])  # level 11, gap -10
        self.assertAlmostEqual(take(m, s, 0).gain, 800)

    def test_skip_mode_records_violations(self):
        ds = tiny([('A', 'Q', {}), ('B', 'Q', {})], [('A', 'requires', 'B')])
        r = simulate(Model(ds), ['B', 'A', 'B'], on_violation='skip')
        self.assertEqual([v[1] for v in r.violations], ['B'])
        self.assertEqual(len(r.trace), 2)


class RealData(unittest.TestCase):
    def test_white_orchard_hand_worked(self):
        # WOF1 S2 250xp, S3a 40, S4 350 at level 1 (rec 1, x0.8) = 512; WOF2 S2 350 (x0.8) + S3 500 (x0.8) = 680
        order = ['WOF1_S1', 'WOF1_S2', 'WOF1_S3a', 'WOF1_S4', 'WOF2_S1', 'WOF2_S2', 'WOF2_S3']
        r = simulate(Model(REAL), order)
        self.assertEqual([round(t.gain) for t in r.trace], [0, 200, 32, 280, 0, 280, 400])
        self.assertAlmostEqual(r.xp, 1192)
        self.assertEqual(r.level, 2)
        self.assertEqual(check(REAL, order)[1:], (r.xp, r.level))

    def test_wof1_block_blocks_other_quests_but_not_its_own_steps(self):
        m = Model(REAL)
        s = start_state(m)
        take(m, s, m.idx['WOF1_S1'])
        self.assertEqual(s.open_block, 'WOF1_BLOCK')
        self.assertIsNone(why_not(m, s, m.idx['WOF1_S2']))
        self.assertTrue(all(m.quest[i] == 'WOF1' for i in available(m, s)))

    def test_simulator_agrees_with_checker(self):
        m = Model(REAL)
        rng = random.Random(7)
        checked = rejected = 0
        for _ in range(6):
            s, walk = start_state(m), []
            for _ in range(250):
                opts = available(m, s)
                if not opts:
                    break
                i = rng.choice(opts)
                take(m, s, i)
                walk.append(m.uids[i])
            problems, xp, level = check(REAL, walk)
            self.assertEqual(problems, [])
            r = simulate(m, walk)
            self.assertAlmostEqual(r.xp, xp)
            self.assertEqual(r.level, level)
            for _ in range(60):                                         # mutated orderings must be judged alike
                w = list(walk)
                kind = rng.choice(['swap', 'drop', 'dup'])
                a, b = rng.randrange(len(w)), rng.randrange(len(w))
                if kind == 'swap':
                    w[a], w[b] = w[b], w[a]
                elif kind == 'drop':
                    del w[a]
                else:
                    w.insert(b, w[a])
                try:
                    simulate(m, w)
                    sim_ok = True
                except ValueError:
                    sim_ok = False
                chk_ok = check(REAL, w)[0] == []
                self.assertEqual(sim_ok, chk_ok, f'{kind} {a},{b}: sim {sim_ok} checker {chk_ok}: {check(REAL, w)[0][:2]}')
                checked += 1
                rejected += not sim_ok
        self.assertGreater(rejected, 10)       # the mutations really do exercise the rejection paths


if __name__ == '__main__':
    unittest.main()
