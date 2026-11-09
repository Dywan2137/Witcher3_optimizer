"""validate() on small synthetic datasets: every check must fire when its problem is present, and stay quiet otherwise."""
import unittest

from tests.helpers import tiny
from witcher3.loader import validate


def checks(steps, rels):
    return set(validate(tiny(steps, rels))['check'])


def S(uid, quest='Q', **x):
    return (uid, quest, x)


class Validate(unittest.TestCase):
    def test_a_clean_dataset_has_no_issues(self):
        steps = [S('A1', block='T'), S('A2', block='T')]
        rels = [('A1', 'requires', 'A2'), ('T', 'in_block', 'A1'), ('T', 'in_block', 'A2')]
        self.assertEqual(checks(steps, rels), set())

    def test_step_checks(self):
        self.assertIn('duplicate_step_uid', checks([S('A'), S('A')], []))
        self.assertIn('bad_reward_xp', checks([S('A', xp=-5)], []))
        self.assertIn('unknown_reward_rule', checks([S('A', rule='nope')], []))
        self.assertIn('missing_recommended_level', checks([S('A', rec=float('nan'))], []))

    def test_relationship_checks(self):
        steps = [S('A'), S('B')]
        self.assertIn('unknown_relationship_type', checks(steps, [('A', 'teleports', 'B')]))
        self.assertIn('self_edge', checks(steps, [('A', 'requires', 'A')]))
        self.assertIn('dangling_endpoint', checks(steps, [('A', 'requires', 'NOPE')]))
        self.assertIn('duplicate_relationship', checks(steps, [('A', 'requires', 'B')] * 2))

    def test_graph_checks(self):
        steps = [S('A'), S('B')]
        cyc = checks(steps, [('A', 'requires', 'B'), ('B', 'requires', 'A')])
        self.assertIn('precedence_cycle', cyc)
        self.assertIn('unreachable_step', cyc)
        self.assertIn('blocker_is_prerequisite', checks(steps, [('A', 'requires', 'B'), ('A', 'blocks', 'B')]))

    def test_block_sync(self):
        self.assertIn('relationships_out_of_sync', checks([S('A', block='T')], []))                 # tag without an in_block edge
        self.assertIn('relationships_out_of_sync', checks([S('A')], [('T', 'in_block', 'A')]))      # edge without a tag

    def test_path_tag_checks(self):
        pair = [('X', 'excludes_path', 'Y')]
        self.assertIn('branch_letter_without_path_tag', checks([S('2a'), S('2b')], []))
        self.assertIn('path_tag_on_unlettered_step', checks([S('A', tags=('X',)), S('B', tags=('Y',))], pair))
        self.assertIn('path_without_partner', checks([S('2a', tags=('X',))], []))
        # one tag on two separate chains = two decisions sharing a tag
        self.assertIn('path_tag_reused', checks([S('2a', tags=('X',)), S('5a', tags=('X',)), S('2b', tags=('Y',))], pair))

    def test_alternatives_declared_by_an_anchor_are_not_flagged(self):
        steps = [S('ANCHOR', tags=('X', 'Y')), S('A', tags=('X',)), S('B', tags=('Y',))]
        rels = [('X', 'excludes_path', 'Y')]
        self.assertNotIn('path_tag_on_unlettered_step', checks(steps, rels))


if __name__ == '__main__':
    unittest.main()
