"""Step 2: the quest simulator.

Model   - static data built once from a loader.Dataset (indexed steps, edges, reward rules, level table).
State   - what has happened so far (XP, level, completed / dead steps, excluded path tags, open sealed block).
simulate(model, order) replays an ordered list of step ids and returns the XP / level trace plus any rule violations.

Rule semantics (edge types from the Relationships sheets):
  requires       every source must be completed before the target.
  unlocks        if a step has incoming unlocks, at least one source must be completed (alternatives).
  blocks         completing the source makes the target permanently unavailable (unless already done).
  excludes       two single steps are mutually exclusive.
  excludes_path  completing a step that has ONE path tag excludes the partner tags; a step is unavailable once all
                 of its tags are excluded (a step listing several tags is a shared anchor and chooses nothing).
  in_block       sealed block: once one member is completed, only steps of the quests that have a member in the block
                 may be taken, and no step of a different block, until every member is settled
                 (completed, unavailable, or optional). Steps of the same quest between members stay allowed.
Rewards: reward_xp x multiplier(rule type, recommended_level - level before the step); no recommended level pays 100%.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field

import pandas as pd

from .loader import Dataset

UNSUPPORTED = {'during'}


class Model:
    def __init__(self, ds: Dataset):
        st, rel = ds.steps.reset_index(drop=True), ds.relationships
        self.uids = st['step_uid'].tolist()
        self.idx = {u: i for i, u in enumerate(self.uids)}
        n = len(self.uids)
        self.xp = st['reward_xp'].tolist()
        self.rec = st['recommended_level'].fillna(0).tolist()
        self.has_level = st['has_level_recommendation'].tolist()
        self.rule = st['reward_rule_type'].tolist()
        self.optional = st['is_optional'].tolist()
        self.quest = st['quest_id'].tolist()
        self.block = [b if isinstance(b, str) else None for b in st['block_id']]
        self.tags = [tuple(t) for t in st['path_tags']]

        self.req, self.unl, self.kills, self.excl = ([[] for _ in range(n)] for _ in range(4))
        self.tag_excl = defaultdict(set)
        for e in rel.itertuples():
            if e.type in UNSUPPORTED:
                raise NotImplementedError(f'relationship type {e.type!r} is not supported by the simulator')
            if e.type == 'excludes_path':
                self.tag_excl[e.source].add(e.target)
                self.tag_excl[e.target].add(e.source)
            elif e.type in ('requires', 'unlocks', 'blocks', 'excludes'):
                s, t = self.idx[e.source], self.idx[e.target]
                if e.type == 'requires':
                    self.req[t].append(s)
                elif e.type == 'unlocks':
                    self.unl[t].append(s)
                elif e.type == 'blocks':
                    self.kills[s].append(t)
                else:
                    self.excl[s].append(t)
                    self.excl[t].append(s)
            # in_block edges are redundant with the Block_ID column, which is what the simulator reads

        self.members = defaultdict(list)
        for i, b in enumerate(self.block):
            if b:
                self.members[b].append(i)
        self.block_quests = {b: {self.quest[i] for i in m} for b, m in self.members.items()}

        rules = ds.reward_rules.sort_values(['reward_rule_type', 'level_gap_min'])
        self.rules = {t: (g['level_gap_min'].tolist(), g['level_gap_max'].tolist(), g['multiplier'].tolist())
                      for t, g in rules.groupby('reward_rule_type')}
        self.cum = ds.level_table['cumulative_xp_to_reach_level'].tolist()

    def level_of(self, xp: float) -> int:
        return bisect_right(self.cum, xp)           # cum[0] == 0, so the minimum is level 1; capped by the table

    def multiplier(self, rule_type: str, gap: float, has_level: bool = True) -> float:
        if not has_level:
            return 1.0
        mins, maxs, mults = self.rules[rule_type]
        k = bisect_right(mins, gap) - 1
        if k < 0 or gap > maxs[k]:
            raise ValueError(f'reward rule {rule_type!r} does not cover level gap {gap}')
        return mults[k]


@dataclass
class State:
    xp: float = 0.0
    level: int = 1
    done: set = field(default_factory=set)
    dead: set = field(default_factory=set)           # made unavailable by `blocks` / `excludes`
    excluded: set = field(default_factory=set)       # path tags that can no longer be chosen
    open_block: str | None = None

    def copy(self) -> 'State':
        return State(self.xp, self.level, set(self.done), set(self.dead), set(self.excluded), self.open_block)


@dataclass
class Taken:
    uid: str
    level_before: int
    gap: float
    multiplier: float
    gain: float
    xp: float
    level: int


@dataclass
class Result:
    xp: float
    level: int
    trace: list
    violations: list            # (position, uid, reason)
    state: State


def start_state(model: Model, xp: float = 0.0) -> State:
    return State(xp=xp, level=model.level_of(xp))


def is_dead(m: Model, s: State, i: int) -> bool:
    return i in s.dead or (bool(m.tags[i]) and all(t in s.excluded for t in m.tags[i]))


def why_not(m: Model, s: State, i: int) -> str | None:
    """None if step i can be taken now, otherwise the reason it cannot."""
    if i in s.done:
        return 'already done'
    if is_dead(m, s, i):
        return 'unavailable (blocked, excluded, or on an excluded path)'
    miss = [m.uids[j] for j in m.req[i] if j not in s.done]
    if miss:
        return f'requires {", ".join(miss)}'
    if m.unl[i] and not any(j in s.done for j in m.unl[i]):
        return f'needs one of {", ".join(m.uids[j] for j in m.unl[i])}'
    if s.open_block and m.block[i] not in (None, s.open_block):
        return f'block {s.open_block} is open (step is in {m.block[i]})'
    if s.open_block and m.quest[i] not in m.block_quests[s.open_block]:
        return f'block {s.open_block} is open'
    return None


def available(m: Model, s: State) -> list[int]:
    return [i for i in range(len(m.uids)) if why_not(m, s, i) is None]


def take(m: Model, s: State, i: int) -> Taken:
    """Complete step i (caller has checked why_not)."""
    gap = (m.rec[i] - s.level) if m.has_level[i] else 0
    mult = m.multiplier(m.rule[i], gap, m.has_level[i])
    before, gain = s.level, m.xp[i] * mult
    s.xp += gain
    s.level = m.level_of(s.xp)
    s.done.add(i)
    for t in m.kills[i] + m.excl[i]:
        if t not in s.done:
            s.dead.add(t)
    if len(m.tags[i]) == 1:
        s.excluded |= m.tag_excl[m.tags[i][0]]
    if s.open_block is None and m.block[i]:
        s.open_block = m.block[i]
    if s.open_block and all(j in s.done or m.optional[j] or is_dead(m, s, j) for j in m.members[s.open_block]):
        s.open_block = None
    return Taken(m.uids[i], before, gap, mult, gain, s.xp, s.level)


def simulate(model: Model, order: list[str], start_xp: float = 0.0, on_violation: str = 'raise') -> Result:
    """Replay `order`. on_violation: 'raise' (ValueError), 'skip' (record it, leave the step out) or 'stop'."""
    s, trace, bad = start_state(model, start_xp), [], []
    for pos, uid in enumerate(order):
        i = model.idx.get(uid)
        reason = 'unknown step' if i is None else why_not(model, s, i)
        if reason:
            if on_violation == 'raise':
                raise ValueError(f'position {pos}: {uid}: {reason}')
            bad.append((pos, uid, reason))
            if on_violation == 'stop':
                break
            continue
        trace.append(take(model, s, i))
    return Result(s.xp, s.level, trace, bad, s)


def trace_frame(result: Result) -> pd.DataFrame:
    return pd.DataFrame([t.__dict__ for t in result.trace])
