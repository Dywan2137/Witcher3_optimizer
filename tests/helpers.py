"""Shared test helpers: the real dataset (loaded once) and small synthetic datasets built on its reward rules."""
from dataclasses import replace

import pandas as pd

from witcher3.loader import load

_REAL = None


def real():
    global _REAL
    if _REAL is None:
        _REAL = load()
    return _REAL


def tiny(steps, rels):
    """Synthetic dataset using the real reward rules / level table.
    steps: (uid, quest, extras) with extras keys xp, rec, has, rule, optional, block, tags.
    rels:  (source, type, target) triples."""
    rows = [dict(location='T', row=0, step_uid=uid, quest_id=quest, step_id=uid,
                 reward_xp=x.get('xp', 100), recommended_level=x.get('rec', 1),
                 has_level_recommendation=x.get('has', True), reward_rule_type=x.get('rule', 'base_cliff'),
                 is_optional=x.get('optional', False), block_id=x.get('block'), path_tags=tuple(x.get('tags', ())))
            for uid, quest, x in steps]
    rel = pd.DataFrame([dict(location='T', row=0, relationship_id=i, source=s, type=t, target=g)
                        for i, (s, t, g) in enumerate(rels)],
                       columns=['location', 'row', 'relationship_id', 'source', 'type', 'target'])
    return replace(real(), steps=pd.DataFrame(rows), relationships=rel)
