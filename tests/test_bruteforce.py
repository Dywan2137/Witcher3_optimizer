"""Step 7: on small random instances, compare greedy and local search with the exhaustive optimum.

Every legal playthrough (unit by unit, as in baselines.play) is enumerated, so the optimum is exact. The instances
mix the cliff and Hearts of Stone rules, prerequisites, a cutoff, a sealed block and a path choice.
Run with: python -m unittest tests.test_bruteforce -v
"""
import random
import unittest

from tests.helpers import plan_for
from witcher3.baselines import play
from witcher3.checker import check
from witcher3.greedy import greedy
from witcher3.local import optimize
from witcher3.simulator import start_state


def exhaustive(plan, state=None) -> float:
    """Best final XP over every legal playthrough from `state`."""
    state = state or start_state(plan.model)
    actions = plan.legal_actions(state)
    if not actions:
        return state.xp
    return max(exhaustive(plan, plan.apply(state, a)[0]) for a in actions)


def instance(seed: int):
    rng = random.Random(seed)
    steps, rels = [], []
    for k in range(6):
        rule = rng.choice(['base_cliff', 'base_cliff', 'hos_gradual'])
        steps.append((f'S{k}', f'Q{k}', dict(xp=rng.choice([500, 1000, 2000, 3000]), rec=rng.randint(1, 10), rule=rule)))
        if k and rng.random() < 0.3:
            rels.append((f'S{rng.randrange(k)}', 'requires', f'S{k}'))
    # a sealed two-step block whose second step is a path choice
    steps += [('B1', 'QB', dict(xp=1000, rec=rng.randint(1, 8), block='QB_BLOCK')),
              ('B2a', 'QB', dict(xp=2000, rec=rng.randint(1, 8), block='QB_BLOCK', tags=('QB_PATH_A',))),
              ('B2b', 'QB', dict(xp=1500, rec=rng.randint(1, 8), block='QB_BLOCK', tags=('QB_PATH_B',)))]
    rels += [('B1', 'unlocks', 'B2a'), ('B1', 'unlocks', 'B2b'), ('QB_PATH_A', 'excludes_path', 'QB_PATH_B')]
    rels.append((f'S{rng.randrange(6)}', 'blocks', f'S{rng.randrange(6)}'))
    return [(u, q, x) for u, q, x in steps], [r for r in rels if r[0] != r[2]]


class BruteForce(unittest.TestCase):
    def test_local_search_reaches_the_optimum(self):
        """Annealing is stochastic: every instance must end within 2% of the optimum and at least 90% exactly on it."""
        rows = []
        for seed in range(25):
            with self.subTest(seed=seed):
                steps, rels = instance(seed)
                ds, plan = plan_for(steps, rels)
                opt = exhaustive(plan)
                g = play(plan, greedy(plan)).xp
                best = optimize(plan, iters=800, seed=seed, chains=3)[0]
                self.assertEqual(check(ds, best.order)[0], [])
                self.assertLessEqual(best.xp, opt + 1e-6)
                self.assertGreaterEqual(best.xp, g)
                self.assertGreaterEqual(best.xp, 0.98 * opt)
                rows.append((opt, g, best.xp))
        exact = sum(abs(b - o) < 1e-6 for o, _, b in rows)
        greedy_exact = sum(abs(g - o) < 1e-6 for o, g, _ in rows)
        print(f'\noptimum reached: local search {exact}/{len(rows)}, greedy {greedy_exact}/{len(rows)}; '
              f'gaps (greedy, local): {[(round(o - g), round(o - b)) for o, g, b in rows if o - b > 1e-6 or o - g > 1e-6]}')
        self.assertGreaterEqual(exact, 0.9 * len(rows))


if __name__ == '__main__':
    unittest.main()
