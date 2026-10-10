"""Tests for witcher3.baselines (step 4) and the circular-block diagnostic. Run with: python -m unittest -v"""
import random
import unittest

from tests.helpers import real, tiny
from witcher3.baselines import play, random_policy, story_order, summarize_run, upper_bound
from witcher3.checker import check
from witcher3.simulator import Model
from witcher3.units import Plan

REAL = real()


def plan_for(steps, rels):
    ds = tiny(steps, rels)
    return ds, Plan(Model(ds))


class UpperBound(unittest.TestCase):
    def test_best_multiplier_per_rule_and_best_alternative_per_group(self):
        steps = [('A', 'Q', {'xp': 100}),                                   # base_cliff: 100 x 0.8
                 ('H', 'Q', {'xp': 100, 'rule': 'hos_gradual'}),            # 100 x 1.5
                 ('N', 'Q', {'xp': 100, 'has': False}),                     # no level: 100 x 1.0
                 ('X1', 'Q', {'xp': 100, 'tags': ('X',)}), ('X2', 'Q', {'xp': 100, 'tags': ('X',)}),   # path X: 160
                 ('Y1', 'Q', {'xp': 300, 'tags': ('Y',)})]                  # path Y: 240 -> Y wins
        _, plan = plan_for(steps, [('X', 'excludes_path', 'Y')])
        self.assertAlmostEqual(upper_bound(plan)['xp'], 80 + 150 + 100 + 240)

    def test_ignores_cutoffs(self):
        steps = [('A', 'Q', {'xp': 100}), ('B', 'R', {'xp': 100})]
        _, plan = plan_for(steps, [('A', 'blocks', 'B')])
        self.assertAlmostEqual(upper_bound(plan)['xp'], 160)


class Policies(unittest.TestCase):
    def test_story_order_follows_the_workbook_order(self):
        steps = [('A', 'Q', {}), ('B', 'Q', {}), ('C', 'R', {}), ('D', 'R', {})]
        ds, plan = plan_for(steps, [('A', 'requires', 'D')])
        run = play(plan, story_order)
        self.assertEqual(run.order, ['A', 'B', 'C', 'D'])
        self.assertEqual(check(ds, run.order)[0], [])

    def test_story_order_respects_prerequisites_and_blocks(self):
        steps = [('D', 'Q', {}), ('A1', 'R', {'block': 'T'}), ('A2', 'R', {'block': 'T'}), ('C', 'S', {})]
        ds, plan = plan_for(steps, [('D', 'requires', 'C'), ('A1', 'requires', 'A2')])   # (source, type, target): source comes first
        run = play(plan, story_order)
        self.assertEqual(run.order, ['D', 'A1', 'A2', 'C'])                 # the block runs as one unit
        self.assertEqual(run.unresolved, [])
        self.assertEqual(check(ds, run.order)[0], [])

    def test_play_reports_lost_and_stuck_steps(self):
        steps = [('A', 'Q', {}), ('B', 'Q', {}), ('G', 'R', {})]
        _, plan = plan_for(steps, [('B', 'requires', 'G'), ('A', 'blocks', 'B')])
        s = summarize_run(plan, play(plan, story_order))
        self.assertEqual((s['lost'], s['stuck']), (2, 0))                  # A cuts B off, so G (which needs B) is lost too

    def test_a_circular_block_leaves_stuck_steps(self):
        steps = [('B1', 'Q', {'block': 'T'}), ('X', 'R', {}), ('B3', 'Q', {'block': 'T'})]
        _, plan = plan_for(steps, [('B1', 'requires', 'X'), ('X', 'requires', 'B3')])
        s = summarize_run(plan, play(plan, story_order))
        self.assertEqual((s['lost'], s['stuck'], s['steps']), (0, 3, 0))   # alive but unreachable: a data problem

    def test_random_runs_are_valid_orders(self):
        plan = Plan(Model(REAL))
        run = play(plan, random_policy(random.Random(1)))
        problems, xp, level = check(REAL, run.order)
        self.assertEqual(problems, [])
        self.assertAlmostEqual(xp, run.xp)
        self.assertEqual(level, run.level)


class RealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = Plan(Model(REAL))

    def test_story_order_is_valid_and_below_the_bound(self):
        run = play(self.plan, story_order)
        problems, xp, level = check(REAL, run.order)
        self.assertEqual(problems, [])
        self.assertAlmostEqual(xp, run.xp)
        ub = upper_bound(self.plan)
        self.assertLessEqual(run.xp, ub['xp'])
        self.assertLessEqual(run.level, ub['level'])
        self.assertEqual(run.unresolved, [])

    def test_play_is_deterministic(self):
        self.assertEqual(play(self.plan, story_order).order, play(self.plan, story_order).order)


class CircularBlocks(unittest.TestCase):
    def test_detects_a_block_that_needs_a_step_depending_on_itself(self):
        # block T = {B1, B3}; B3 needs X (outside), X needs B1 (inside): cannot be played contiguously
        steps = [('B1', 'Q', {'block': 'T'}), ('X', 'R', {}), ('B3', 'Q', {'block': 'T'})]
        _, plan = plan_for(steps, [('B1', 'requires', 'X'), ('X', 'requires', 'B3')])
        notes = plan.circular_blocks()
        self.assertEqual(len(notes), 1)
        self.assertIn('B3 needs X', notes[0])

    def test_clean_block_is_not_reported(self):
        steps = [('E', 'R', {}), ('B1', 'Q', {'block': 'T'}), ('B2', 'Q', {'block': 'T'})]
        _, plan = plan_for(steps, [('E', 'requires', 'B1'), ('B1', 'requires', 'B2')])
        self.assertEqual(plan.circular_blocks(), [])


if __name__ == '__main__':
    unittest.main()
