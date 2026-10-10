"""Independent solution checker (does not use simulator.py).

check(ds, order) looks at a finished ordering of step ids and returns (problems, xp, level):
every rule is tested against the positions of the steps in the list, and XP is recomputed from the raw tables.
It exists to catch bugs in simulator.py, so keep the two implementations separate.
"""
from __future__ import annotations

from collections import defaultdict

from .loader import Dataset


def _multiplier(rules, rule_type, gap, has_level):
    if not has_level:
        return 1.0
    for r in rules[rule_type]:
        if r[0] <= gap <= r[1]:
            return r[2]
    raise ValueError(f'no {rule_type} rule for gap {gap}')


def check(ds: Dataset, order: list[str]):
    st = {r.step_uid: r for r in ds.steps.itertuples()}
    pos, problems = {}, []
    for p, u in enumerate(order):
        if u not in st:
            problems.append(f'{p}: unknown step {u}')
        elif u in pos:
            problems.append(f'{p}: {u} taken twice')
        else:
            pos[u] = p

    kills, excl, pexcl = [], [], defaultdict(set)
    unlock_src = defaultdict(list)
    for e in ds.relationships.itertuples():
        a, b, t = e.source, e.target, e.type
        if t == 'requires' and b in pos and not (a in pos and pos[a] < pos[b]):
            problems.append(f'{pos[b]}: {b} requires {a} first')
        elif t == 'unlocks':
            unlock_src[b].append(a)
        elif t == 'blocks':
            kills.append((a, b))
            if a in pos and b in pos and pos[b] > pos[a]:
                problems.append(f'{pos[b]}: {b} taken after {a} blocked it')
        elif t == 'excludes':
            excl.append((a, b))
            if a in pos and b in pos:
                problems.append(f'{max(pos[a], pos[b])}: {a} and {b} exclude each other')
        elif t == 'excludes_path':
            pexcl[a].add(b)
            pexcl[b].add(a)
        elif t == 'during':
            problems.append('relationship type "during" is not supported')
    for b, srcs in unlock_src.items():
        if b in pos and not any(a in pos and pos[a] < pos[b] for a in srcs):
            problems.append(f'{pos[b]}: {b} needs one of {srcs}')

    def tags_chosen_before(p):
        return {st[u].path_tags[0] for u, q in pos.items() if q < p and len(st[u].path_tags) == 1}

    for u, p in pos.items():                   # path exclusivity
        tags = st[u].path_tags
        if not tags:
            continue
        ex = set().union(*(pexcl[c] for c in tags_chosen_before(p)), set())
        if all(t in ex for t in tags):
            problems.append(f'{p}: {u} is on an excluded path')

    # sealed blocks
    members = defaultdict(list)
    for u, r in st.items():
        if isinstance(r.block_id, str):
            members[r.block_id].append(u)
    for tag, mem in members.items():
        taken = sorted(pos[u] for u in mem if u in pos)
        if not taken:
            continue
        quests = {st[u].quest_id for u in mem}

        def unavailable(u, p):                 # state after the step at position p has been taken
            if any(a in pos and pos[a] <= p for a, b in kills if b == u):
                return True
            if any((x == u and y in pos and pos[y] <= p) or (y == u and x in pos and pos[x] <= p) for x, y in excl):
                return True
            r = st[u]
            if r.path_tags:
                ex = set().union(*(pexcl[c] for c in tags_chosen_before(p + 1)), set())
                return all(t in ex for t in r.path_tags)
            return False

        end = len(order)
        for p in range(taken[0], len(order)):
            if all((u in pos and pos[u] <= p) or st[u].is_optional or unavailable(u, p) for u in mem):
                end = p
                break
        for p in range(taken[0] + 1, min(end, len(order) - 1) + 1):
            r = st.get(order[p])
            bid = r.block_id if r is not None and isinstance(r.block_id, str) else None
            if r is not None and (r.quest_id not in quests or bid not in (None, tag)):
                problems.append(f'{p}: {order[p]} taken while block {tag} is open')

    # XP, recomputed from the raw tables
    rules = defaultdict(list)
    for r in ds.reward_rules.itertuples():
        rules[r.reward_rule_type].append((r.level_gap_min, r.level_gap_max, r.multiplier))
    cum = list(ds.level_table['cumulative_xp_to_reach_level'])
    xp = 0.0
    level = 1
    for u in order:
        if u not in st:
            continue
        r = st[u]
        gap = (r.recommended_level - level) if r.has_level_recommendation else 0
        xp += r.reward_xp * _multiplier(rules, r.reward_rule_type, gap, r.has_level_recommendation)
        level = 1 + sum(1 for c in cum[1:] if c <= xp)
    return problems, xp, level
