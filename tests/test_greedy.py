"""Tests for witcher3.greedy (step 5). Run with: python -m unittest -v"""
import random
import unittest

from tests.helpers import real, tiny
from witcher3.baselines import play, story_order
from witcher3.checker import check
from witcher3.greedy import best_of, greedy, steps_table
from witcher3.loader import restrict
from witcher3.simulator import Model
from witcher3.units import Plan

REAL = real()


def run(steps, rels, **kw):
    ds = tiny(steps, rels)
    plan = Plan(Model(ds))
    return ds, play(plan, greedy(plan, **kw))


class Rules(unittest.TestCase):
    def test_earliest_deadline_first(self):
        steps = [('LATE', 'Q', {'rec': 20}), ('SOON', 'R', {'rec': 1})]      # LATE is listed first
        ds, r = run(steps, [])
        self.assertEqual(r.order, ['SOON', 'LATE'])
        self.assertEqual(check(ds, r.order)[0], [])

    def test_no_level_steps_go_last(self):
        steps = [('FREE', 'Q', {'has': False, 'xp': 500}), ('SOON', 'R', {'rec': 30})]
        _, r = run(steps, [])
        self.assertEqual(r.order, ['SOON', 'FREE'])

    def test_gates_inherit_the_deadline_of_what_they_unlock(self):
        # GATE pays nothing and is nominally due late, but CHILD (due soon) needs it: GATE must go before OTHER
        steps = [('OTHER', 'Q', {'rec': 5}), ('GATE', 'R', {'rec': 30, 'xp': 0}), ('CHILD', 'S', {'rec': 1, 'xp': 500})]
        rels = [('GATE', 'requires', 'CHILD')]
        self.assertEqual(run(steps, rels)[1].order, ['GATE', 'CHILD', 'OTHER'])
        self.assertEqual(run(steps, rels, propagate=False)[1].order, ['OTHER', 'GATE', 'CHILD'])

    def test_cutoff_guard_plays_what_would_be_destroyed_first(self):
        steps = [('KILLER', 'Q', {'rec': 1}), ('VICTIM', 'R', {'rec': 20, 'xp': 300})]
        rels = [('KILLER', 'blocks', 'VICTIM')]
        self.assertEqual(run(steps, rels)[1].order, ['VICTIM', 'KILLER'])
        self.assertEqual(run(steps, rels, cutoff_guard=False)[1].order, ['KILLER'])      # victim is cut off

    def test_hearts_of_stone_waits_until_under_leveled_by_five(self):
        steps = [('HOS', 'Q', {'rec': 20, 'rule': 'hos_gradual'}), ('BASE', 'R', {'rec': 40})]
        self.assertEqual(run(steps, [])[1].order, ['BASE', 'HOS'])                       # level 1 is 19 below: wait
        self.assertEqual(run(steps, [], hos_wait=False)[1].order, ['HOS', 'BASE'])

    def test_picks_the_better_paying_variant_of_a_block(self):
        steps = [('S', 'Q', {'block': 'T'}), ('A', 'Q', {'block': 'T', 'tags': ('X',), 'xp': 100}),
                 ('B', 'Q', {'block': 'T', 'tags': ('Y',), 'xp': 400})]
        rels = [('S', 'requires', 'A'), ('S', 'requires', 'B'), ('X', 'excludes_path', 'Y')]
        self.assertEqual(run(steps, rels)[1].order, ['S', 'B'])


class RealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = restrict(REAL, ('base', 'hos'))
        cls.plan = Plan(Model(cls.ds))

    def test_greedy_is_valid_and_beats_story_order(self):
        g = play(self.plan, greedy(self.plan))
        problems, xp, level = check(self.ds, g.order)
        self.assertEqual(problems, [])
        self.assertAlmostEqual(xp, g.xp)
        self.assertEqual(g.unresolved, [])
        self.assertGreater(g.xp, play(self.plan, story_order).xp)

    def test_restarts_never_do_worse_and_stay_valid(self):
        base = play(self.plan, greedy(self.plan))
        best = best_of(self.plan, 3, noise=4.0, seed=1)
        self.assertGreaterEqual(best.xp, base.xp)
        self.assertEqual(check(self.ds, best.order)[0], [])


class Output(unittest.TestCase):
    def test_steps_table_lists_the_run_in_order(self):
        ds = restrict(REAL, ('base', 'hos'))
        plan = Plan(Model(ds))
        r = play(plan, greedy(plan))
        table = steps_table(ds, r)
        self.assertEqual(list(table['step']), r.order)
        self.assertEqual(list(table['n']), list(range(1, len(r.order) + 1)))
        self.assertEqual(table['level_after'].iloc[-1], r.level)
        self.assertAlmostEqual(table['xp_gain'].sum(), r.xp, delta=len(table) * 0.05)       # gains are rounded to 0.1
        self.assertTrue((table['level_after'].diff().dropna() >= 0).all())                  # level never goes down


class Scope(unittest.TestCase):
    def test_base_and_hos_keep_only_their_steps(self):
        ds = restrict(REAL, ('base', 'hos'))
        self.assertEqual(set(ds.steps['dlc']), {'podstawa', 'Serce z kamienia'})
        uids = set(ds.steps['step_uid'])
        steps_edges = ds.relationships[~ds.relationships['type'].isin(['in_block', 'excludes_path'])]
        self.assertTrue(steps_edges['source'].isin(uids).all() and steps_edges['target'].isin(uids).all())


if __name__ == '__main__':
    unittest.main()
