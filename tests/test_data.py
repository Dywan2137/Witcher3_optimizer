"""Data-health tests on the real workbook: they fail when the data gets a known kind of problem again.
Run with: python -m unittest tests.test_data -v"""
import unittest

from tests.helpers import real
from witcher3.baselines import play, story_order, summarize_run
from witcher3.loader import edges_leaving_scope, restrict, validate
from witcher3.simulator import Model, start_state, available
from witcher3.units import Plan

REAL = real()


class DataHealth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = Model(REAL)
        cls.plan = Plan(cls.model)

    def test_validation_has_no_issues(self):
        issues = validate(REAL)
        self.assertTrue(issues.empty, '\n' + issues.head(15).to_string())

    def test_only_the_first_step_of_the_game_is_available_at_start(self):
        # every other quest needs an entry gate (e.g. VZF1_S2 for Velen/Novigrad, KIWF1_S2 for Toussaint)
        start = [self.model.uids[i] for i in available(self.model, start_state(self.model))]
        self.assertEqual(start, ['WOF1_S1'])

    def test_base_and_hos_do_not_depend_on_blood_and_wine(self):
        self.assertTrue(edges_leaving_scope(REAL, ('base', 'hos')).empty)
        scoped = restrict(REAL, ('base', 'hos'))
        self.assertTrue(validate(scoped).empty)

    def test_no_sealed_block_depends_on_itself(self):
        self.assertEqual(self.plan.circular_blocks(), [])

    def test_no_block_is_unplayable(self):
        unplayable = [n for n in self.plan.diagnostics() if 'cannot be played' in n]
        self.assertEqual(unplayable, [])

    def test_story_order_leaves_no_step_stuck(self):
        s = summarize_run(self.plan, play(self.plan, story_order))
        self.assertEqual(s['stuck'], 0, s)
        self.assertEqual(s['unresolved_choices'], 0, s)


if __name__ == '__main__':
    unittest.main()
