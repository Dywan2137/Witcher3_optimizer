"""Tests for witcher3.local (step 6). Run with: python -m unittest -v"""
import random
import unittest

from tests.helpers import plan_for, real
from witcher3.baselines import play
from witcher3.checker import check
from witcher3.greedy import greedy
from witcher3.loader import restrict
from witcher3.local import Search, optimize
from witcher3.simulator import Model
from witcher3.units import Action, Plan

REAL = real()


def keys_of(run):
    return {a: float(n) for n, a in enumerate(run.actions)}


class Decoder(unittest.TestCase):
    def test_lowest_key_first_and_unkeyed_last(self):
        _, plan = plan_for([('A', 'Q', {}), ('B', 'R', {}), ('C', 'S', {})], [])
        m = plan.model
        sol = Search(plan, random.Random(0)).solution({Action('step', m.idx['C']): 0.0, Action('step', m.idx['B']): 1.0})
        self.assertEqual(sol.run(plan).order, ['C', 'B', 'A'])

    def test_illegal_low_key_is_skipped_not_fatal(self):
        _, plan = plan_for([('A', 'Q', {}), ('B', 'Q', {})], [('A', 'requires', 'B')])
        m = plan.model
        sol = Search(plan, random.Random(0)).solution({Action('step', m.idx['B']): 0.0, Action('step', m.idx['A']): 1.0})
        self.assertEqual(sol.run(plan).order, ['A', 'B'])

    def test_choice_is_the_variant_with_the_lower_key(self):
        steps = [('S', 'Q', {'block': 'T'}), ('A', 'Q', {'block': 'T', 'tags': ('X',)}),
                 ('B', 'Q', {'block': 'T', 'tags': ('Y',)})]
        rels = [('S', 'requires', 'A'), ('S', 'requires', 'B'), ('X', 'excludes_path', 'Y')]
        _, plan = plan_for(steps, rels)
        for v in plan.variants('T'):
            sol = Search(plan, random.Random(0)).solution({Action('block', 'T', v): 0.0})
            self.assertEqual(sol.actions, [Action('block', 'T', v)])

    def test_unchanged_keys_need_no_replay(self):
        _, plan = plan_for([('A', 'Q', {}), ('B', 'R', {'rec': 5})], [])
        s = Search(plan, random.Random(0))
        sol = s.solution({})
        self.assertIsNone(s.solution(sol.keys(), sol))

    def test_prefix_replay_equals_full_decode(self):
        plan = Plan(Model(restrict(REAL, ['base'])))
        s = Search(plan, random.Random(1))
        sol = s.solution(keys_of(play(plan, greedy(plan))))
        for _ in range(5):
            keys, _ = s.move(sol)
            fast = s.solution(keys, sol) or sol
            self.assertEqual(fast.run(plan).order, s.solution(keys).run(plan).order)


class RealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = restrict(REAL, ['base', 'hos'])
        cls.plan = Plan(Model(cls.ds))

    def test_seed_reproduces_greedy(self):
        g = play(self.plan, greedy(self.plan))
        sol = Search(self.plan, random.Random(0)).solution(keys_of(g))
        self.assertEqual(sol.run(self.plan).order, g.order)

    def test_search_never_ends_below_its_start_and_is_valid(self):
        best, start, history = optimize(self.plan, iters=40, seed=3)
        self.assertGreaterEqual(best.xp, start.xp)
        self.assertEqual([b for _, _, b in history], sorted(b for _, _, b in history))     # best is monotone
        self.assertEqual(check(self.ds, best.order)[0], [])
        self.assertEqual(best.unresolved, [])

    def test_same_seed_same_result(self):
        a = optimize(self.plan, iters=15, seed=7)[0]
        b = optimize(self.plan, iters=15, seed=7)[0]
        self.assertEqual(a.order, b.order)


if __name__ == '__main__':
    unittest.main()
