"""Difficulty switch: rewards taken on the lower difficulty use the `<type>_story` rules (simulator.State.low)."""
import random
import unittest
from dataclasses import replace

import pandas as pd

from tests.helpers import plan_for, real
from witcher3.baselines import play
from witcher3.checker import check
from witcher3.greedy import greedy
from witcher3.loader import restrict
from witcher3.local import Search, optimize
from witcher3.simulator import Model, simulate, start_state
from witcher3.units import Plan

# Story and Sword rates, as in the workbook: 100% instead of Death March 80%, same cliff, Hearts of Stone 1.0 + 0.16 x gap
STORY = [('base_cliff_story', -999, -10, 0.05), ('base_cliff_story', -9, 999, 1.0),
         ('hos_gradual_story', -999, -7, 0.05), ('hos_gradual_story', -6, -6, 0.04)] + \
        [('hos_gradual_story', g, g, round(1.0 + 0.16 * g, 2)) for g in range(-5, 4)] + \
        [('hos_gradual_story', 4, 9, 1.5), ('hos_gradual_story', 10, 999, 1.0)]


def with_story(ds):
    rows = pd.DataFrame(STORY, columns=['reward_rule_type', 'level_gap_min', 'level_gap_max', 'multiplier'])
    return replace(ds, reward_rules=pd.concat([ds.reward_rules, rows], ignore_index=True))


def story_plan(steps, rels):
    ds, _ = plan_for(steps, rels)
    ds = with_story(ds)
    return ds, Plan(Model(ds))


def exhaustive(plan, state=None) -> float:
    """Best final XP over every order of the free steps and every difficulty choice for each reward."""
    m = plan.model
    state = state or start_state(m)
    actions = plan.legal_actions(state)
    if not actions:
        return state.xp
    best = 0.0
    for a in actions:
        for low in ([False, True] if m.low_rule[a.ref] is not None else [False]):
            s = state.copy()
            s.low = s.low | {a.ref} if low else s.low - {a.ref}
            best = max(best, exhaustive(plan, plan.apply(s, a)[0]))
    return best


def instance(seed: int):
    rng = random.Random(seed)
    steps, rels = [], []
    for k in range(5):
        rule = rng.choice(['base_cliff', 'hos_gradual'])
        steps.append((f'S{k}', f'Q{k}', dict(xp=rng.choice([1000, 2000, 4000, 6000]), rec=rng.randint(1, 12), rule=rule)))
        if k and rng.random() < 0.3:
            rels.append((f'S{rng.randrange(k)}', 'requires', f'S{k}'))
    return steps, rels


class Rates(unittest.TestCase):
    def test_story_rule_pays_full_rate(self):
        _, plan = story_plan([('A', 'Q', dict(xp=1000, rec=1))], [])
        m = plan.model
        self.assertEqual(simulate(m, ['A']).xp, 800)
        r = simulate(m, ['A'], low=['A'])
        self.assertEqual(r.xp, 1000)
        self.assertTrue(r.trace[0].low)

    def test_exempt_step_is_not_switchable(self):
        _, plan = story_plan([('A', 'Q', dict(xp=100, has=False, rule='exempt_full'))], [])
        self.assertEqual(plan.model.switchable, [])
        self.assertEqual(simulate(plan.model, ['A'], low=['A']).xp, 100)

    def test_without_story_rules_nothing_switches(self):
        _, plan = plan_for([('A', 'Q', dict(xp=1000, rec=1))], [])
        self.assertEqual(plan.model.switchable, [])
        self.assertEqual(simulate(plan.model, ['A'], low=['A']).xp, 800)


class RealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = with_story(restrict(real(), ['base']))
        cls.plan = Plan(Model(cls.ds))
        cls.greedy_run = play(cls.plan, greedy(cls.plan))

    def test_checker_agrees_on_random_difficulty_choices(self):
        rng = random.Random(0)
        for _ in range(3):
            low = [u for u in self.greedy_run.order if rng.random() < 0.5]
            sim = simulate(self.plan.model, self.greedy_run.order, low=low)
            problems, xp, level = check(self.ds, self.greedy_run.order, low)
            self.assertEqual(problems, [])
            self.assertAlmostEqual(sim.xp, xp, places=6)
            self.assertEqual(sim.level, level)

    def test_prefix_replay_equals_full_decode_with_flips(self):
        s = Search(self.plan, random.Random(2), switch=True)
        sol = s.solution({a: float(n) for n, a in enumerate(self.greedy_run.actions)})
        for _ in range(8):
            out = s.flip(sol, s.pick(sol))
            if out is None or out[0] == sol.low:       # nothing to switch there, or already at that difficulty
                continue
            fast = s.solution(sol.keys(), sol, out[0])
            full = s.solution(sol.keys(), low=out[0])
            self.assertAlmostEqual(fast.xp, full.xp, places=6)
            self.assertEqual(fast.run(self.plan).low, full.run(self.plan).low)
            sol = fast


class BruteForce(unittest.TestCase):
    def test_local_search_with_switch_reaches_the_optimum(self):
        rows = []
        for seed in range(15):
            with self.subTest(seed=seed):
                steps, rels = instance(seed)
                ds, plan = story_plan(steps, rels)
                opt = exhaustive(plan)
                no_switch = optimize(plan, iters=400, seed=seed, chains=2)[0]
                best = optimize(plan, iters=800, seed=seed, chains=3, switch=True)[0]
                self.assertEqual(check(ds, best.order, best.low)[0], [])
                self.assertAlmostEqual(check(ds, best.order, best.low)[1], best.xp, places=6)
                self.assertLessEqual(best.xp, opt + 1e-6)
                self.assertGreaterEqual(best.xp + 1e-6, no_switch.xp)
                rows.append((opt, best.xp, no_switch.xp))
        exact = sum(abs(b - o) < 1e-6 for o, b, _ in rows)
        print(f'\nswitch optimum reached {exact}/{len(rows)}; '
              f'gain over Death March only: {[round(b - n) for _, b, n in rows]}')
        self.assertGreaterEqual(exact, 0.9 * len(rows))
        self.assertTrue(any(b > n + 1e-6 for _, b, n in rows))


if __name__ == '__main__':
    unittest.main()
