"""Tests for witcher3.units (step 3). Run with: python -m unittest -v"""
import random
import unittest

from tests.helpers import real, tiny
from witcher3.checker import check
from witcher3.simulator import Model, simulate, start_state
from witcher3.units import Action, Plan

REAL = real()


def plan_for(steps, rels):
    ds = tiny(steps, rels)
    m = Model(ds)
    return ds, m, Plan(m)


def uids(m, taken):
    return [t.uid for t in taken]


class Blocks(unittest.TestCase):
    STEPS = [('A1', 'Q', {'block': 'T'}), ('MID', 'Q', {}), ('A2', 'Q', {'block': 'T'}), ('OUT', 'R', {})]
    RELS = [('A1', 'requires', 'MID'), ('MID', 'requires', 'A2')]

    def test_block_is_one_action_and_plays_in_place(self):
        ds, m, plan = plan_for(self.STEPS, self.RELS)
        s = start_state(m)
        acts = plan.legal_actions(s)
        self.assertCountEqual([(a.kind, a.ref) for a in acts], [('step', m.idx['OUT']), ('block', 'T')])
        s2, taken = plan.apply(s, Action('block', 'T'))
        self.assertEqual(uids(m, taken), ['A1', 'MID', 'A2'])       # the non-member step of the same quest is played too
        self.assertIsNone(s2.open_block)
        self.assertAlmostEqual(s2.xp, simulate(m, ['A1', 'MID', 'A2']).xp)
        self.assertEqual(check(ds, ['A1', 'MID', 'A2'])[0], [])

    def test_free_step_actions_exclude_block_steps(self):
        _, m, plan = plan_for(self.STEPS, self.RELS)
        self.assertEqual(plan.free_steps, [m.idx['MID'], m.idx['OUT']])

    def test_block_needs_its_outside_prerequisites_first(self):
        steps = [('EXT', 'R', {}), ('A1', 'Q', {'block': 'T'}), ('A2', 'Q', {'block': 'T'})]
        rels = [('EXT', 'requires', 'A1'), ('A1', 'requires', 'A2')]
        _, m, plan = plan_for(steps, rels)
        s = start_state(m)
        self.assertNotIn('block', [a.kind for a in plan.legal_actions(s)])
        s, _ = plan.apply(s, Action('step', m.idx['EXT']))
        self.assertIn(('block', 'T'), [(a.kind, a.ref) for a in plan.legal_actions(s)])

    def test_block_that_cannot_finish_is_not_offered(self):
        steps = [('A1', 'Q', {'block': 'T'}), ('A2', 'Q', {'block': 'T'}), ('EXT', 'R', {})]
        rels = [('A1', 'requires', 'A2'), ('EXT', 'requires', 'A2')]     # A2 also needs a step outside the quest
        _, m, plan = plan_for(steps, rels)
        s = start_state(m)
        self.assertNotIn('block', [a.kind for a in plan.legal_actions(s)])      # A2 needs EXT, outside the block's quest
        s, _ = plan.apply(s, Action('step', m.idx['EXT']))
        self.assertIn(('block', 'T'), [(a.kind, a.ref) for a in plan.legal_actions(s)])
        self.assertEqual(plan.diagnostics(), [])                                 # fine once the outside step is done

    def test_cannot_start_units_inside_a_block(self):
        _, m, plan = plan_for(self.STEPS, self.RELS)
        s = start_state(m)
        from witcher3.simulator import take
        take(m, s, m.idx['A1'])
        with self.assertRaisesRegex(ValueError, 'is open'):
            plan.legal_actions(s)

    def test_illegal_action_raises(self):
        _, m, plan = plan_for(self.STEPS, self.RELS)
        with self.assertRaises(ValueError):
            plan.apply(start_state(m), Action('step', m.idx['MID']))          # needs A1 first
        with self.assertRaises(ValueError):
            plan.apply(start_state(m), Action('step', m.idx['A1']))           # belongs to a block unit

    def test_xp_depends_on_the_entry_state(self):
        steps = [('A1', 'Q', {'block': 'T', 'xp': 1000, 'rec': 1}), ('A2', 'Q', {'block': 'T', 'xp': 1000, 'rec': 1})]
        _, m, plan = plan_for(steps, [('A1', 'requires', 'A2')])
        low, _ = plan.apply(start_state(m), Action('block', 'T'))
        high, _ = plan.apply(start_state(m, xp=REAL.level_table.loc[20, 'cumulative_xp_to_reach_level']), Action('block', 'T'))
        self.assertAlmostEqual(low.xp, 1600)                                  # 80% each
        self.assertAlmostEqual(high.xp - REAL.level_table.loc[20, 'cumulative_xp_to_reach_level'], 100)   # 5% each


class Choices(unittest.TestCase):
    def test_variants_play_only_the_chosen_path(self):
        steps = [('S', 'Q', {'block': 'T'}), ('A', 'Q', {'block': 'T', 'tags': ('X',)}),
                 ('B', 'Q', {'block': 'T', 'tags': ('Y',)})]
        rels = [('S', 'requires', 'A'), ('S', 'requires', 'B'), ('X', 'excludes_path', 'Y')]
        ds, m, plan = plan_for(steps, rels)
        self.assertEqual(plan.variants('T'), [(('X', 'X'),), (('X', 'Y'),)])
        acts = [a for a in plan.legal_actions(start_state(m)) if a.kind == 'block']
        self.assertEqual(len(acts), 2)
        for variant, path, other in [((('X', 'X'),), 'A', 'B'), ((('X', 'Y'),), 'B', 'A')]:
            s, taken = plan.apply(start_state(m), Action('block', 'T', variant))
            self.assertEqual(uids(m, taken), ['S', path])
            self.assertIn(m.idx[other], s.dead | {i for i in range(len(m.uids)) if m.tags[i] and set(m.tags[i]) <= s.excluded})

    def test_unresolved_choices(self):
        steps = [('P', 'Q', {}), ('A', 'Q', {'tags': ('X',)}), ('B', 'Q', {'tags': ('Y',)})]
        rels = [('P', 'requires', 'A'), ('P', 'requires', 'B'), ('X', 'excludes_path', 'Y')]
        _, m, plan = plan_for(steps, rels)
        s = start_state(m)
        self.assertEqual(plan.unresolved_choices(s), [])                  # branch point not reached yet
        s, _ = plan.apply(s, Action('step', m.idx['P']))
        self.assertEqual(plan.unresolved_choices(s), ['X'])               # reachable and nothing chosen
        s, _ = plan.apply(s, Action('step', m.idx['B']))
        self.assertEqual(plan.unresolved_choices(s), [])
        self.assertNotIn(Action('step', m.idx['A']), plan.legal_actions(s))

    def test_shared_anchor_listing_all_tags(self):
        steps = [('ANC', 'Q', {'tags': ('X', 'Y', 'Z')}), ('A', 'Q', {'tags': ('X',)}), ('B', 'Q', {'tags': ('Y',)}),
                 ('C', 'R', {'tags': ('Z',)})]
        rels = [('ANC', 'requires', 'A'), ('X', 'excludes_path', 'Y'), ('X', 'excludes_path', 'Z'), ('Y', 'excludes_path', 'Z')]
        _, m, plan = plan_for(steps, rels)
        self.assertEqual(list(plan.groups), ['X'])
        self.assertEqual(plan.groups['X'].tags, ('X', 'Y', 'Z'))

    def test_block_that_forces_a_path_is_reported(self):
        steps = [('S', 'Q', {'block': 'T'}), ('A', 'Q', {'block': 'T', 'tags': ('X',)}), ('B', 'R', {'tags': ('Y',)})]
        rels = [('S', 'requires', 'A'), ('X', 'excludes_path', 'Y')]
        _, _, plan = plan_for(steps, rels)
        self.assertTrue(any('forces X' in n for n in plan.diagnostics()), plan.diagnostics())


class Optionals(unittest.TestCase):
    def test_optional_members_are_a_toggle(self):
        steps = [('M', 'Q', {'block': 'T'}), ('OPT', 'Q', {'block': 'T', 'optional': True}), ('N', 'Q', {'block': 'T'})]
        rels = [('M', 'requires', 'OPT'), ('M', 'requires', 'N')]
        _, m, plan = plan_for(steps, rels)
        self.assertEqual(plan.optional_modes('T'), [(), (m.idx['OPT'],)])
        _, without = plan.apply(start_state(m), Action('block', 'T'))
        _, with_opt = plan.apply(start_state(m), Action('block', 'T', (), (m.idx['OPT'],)))
        self.assertEqual(uids(m, without), ['M', 'N'])
        self.assertEqual(uids(m, with_opt), ['M', 'OPT', 'N'])
        self.assertEqual(len([a for a in plan.legal_actions(start_state(m)) if a.kind == 'block']), 2)


class RealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = Model(REAL)
        cls.plan = Plan(cls.model)

    def test_plan_stats(self):
        st = self.plan.stats()
        self.assertEqual(st['free_steps'] + st['block_members'], st['steps'])
        self.assertGreater(st['blocks'], 100)
        self.assertGreater(st['choice_groups'], 10)

    def test_every_playable_block_variant_is_consistent(self):
        # from an "everything outside is done" state, each block that is playable must also validate independently
        m = self.model
        from witcher3.simulator import State
        for tag, b in list(self.plan.blocks.items())[:80]:
            ideal = State(done={i for i in range(len(m.uids)) if m.quest[i] not in b.quests})
            for v in self.plan.variants(tag):
                out = self.plan.try_play(ideal, tag, v)
                if out is not None:
                    self.assertIsNone(out[0].open_block)

    def test_unit_level_walks_obey_every_rule(self):
        m, plan = self.model, self.plan
        rng = random.Random(11)
        for _ in range(4):
            s, order = start_state(m), []
            for _ in range(40):
                acts = plan.legal_actions(s)
                if not acts:
                    break
                s, taken = plan.apply(s, rng.choice(acts))
                order += uids(m, taken)
                self.assertIsNone(s.open_block)
            problems, xp, level = check(REAL, order)
            self.assertEqual(problems, [])
            res = simulate(m, order)
            self.assertAlmostEqual(res.xp, s.xp)
            self.assertAlmostEqual(xp, s.xp)
            self.assertEqual(level, s.level)

    def test_diagnostics_run(self):
        self.assertIsInstance(self.plan.diagnostics(), list)


if __name__ == '__main__':
    unittest.main()
