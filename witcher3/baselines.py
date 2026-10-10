"""Step 4: reference numbers every search result is compared against.

story order   always play the first legal action in workbook order (regions in game order, rows top to bottom).
random        random legal playthroughs; shows how much the ordering matters.
upper bound   every step at its best multiplier, the best alternative of every choice group, cutoffs ignored.
              No ordering can beat it, so (upper bound - result) is the room left.

Usage: python -m witcher3.baselines [--random N] [--seed S] [--scope base,hos,bw] [--file PATH]
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ''):  # run as a plain script (python witcher3/baselines.py, an IDE Run button)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from witcher3.loader import DATA_FILE, Dataset, load, restrict
from witcher3.simulator import Model, State, is_dead, start_state
from witcher3.units import Action, Plan


@dataclass
class Run:
    order: list                     # step ids in the order they were played
    state: State
    trace: list = field(default_factory=list)       # [Taken]
    actions: int = 0
    unresolved: list = field(default_factory=list)  # choice groups that still owed a choice at the end

    @property
    def xp(self) -> float:
        return self.state.xp

    @property
    def level(self) -> int:
        return self.state.level

    @property
    def cliff_steps(self) -> int:
        """Steps played at the minimum (over-leveled) multiplier of 5%."""
        return sum(1 for t in self.trace if t.multiplier <= 0.05)


def first_index(plan: Plan, action: Action) -> int:
    """Workbook position of an action: the step itself, or the earliest member of a block."""
    return action.ref if action.kind == 'step' else min(plan.blocks[action.ref].members)


def story_order(plan: Plan, state: State, actions: list) -> Action:
    return min(actions, key=lambda a: first_index(plan, a))     # min is stable: ties keep the listed variant


def random_policy(rng: random.Random):
    return lambda plan, state, actions: rng.choice(actions)


def play(plan: Plan, policy, start_xp: float = 0.0) -> Run:
    """Play until nothing is legal. `policy(plan, state, legal_actions) -> Action`."""
    m = plan.model
    s, run = start_state(m, start_xp), None
    order, trace, n = [], [], 0
    while True:
        actions = plan.legal_actions(s)
        if not actions:
            break
        s, taken = plan.apply(s, policy(plan, s, actions))
        order += [t.uid for t in taken]
        trace += taken
        n += 1
    return Run(order, s, trace, n, plan.unresolved_choices(s))


def upper_bound(plan: Plan) -> dict:
    """Valid upper bound on total XP: best multiplier per step, best alternative per choice group, cutoffs ignored."""
    m = plan.model

    def best(i):
        top = 1.0 if not m.has_level[i] else max(m.rules[m.rule[i]][2])
        return m.xp[i] * top

    grouped = {i for g in plan.groups.values() for t in g.tags for i in g.steps[t]}
    total = sum(best(i) for i in range(len(m.uids)) if i not in grouped)
    for g in plan.groups.values():
        total += max(sum(best(i) for i in g.steps[t]) for t in g.tags)
    return dict(xp=total, level=m.level_of(total))


def lost_steps(m: Model, s: State, done: set) -> set:
    """Steps that can never be played any more: killed by a cutoff / path choice, or needing a lost step."""
    lost = {i for i in range(len(m.uids)) if i not in done and is_dead(m, s, i)}
    changed = True
    while changed:
        changed = False
        for i in range(len(m.uids)):
            if i in done or i in lost:
                continue
            if any(j in lost for j in m.req[i]) or (m.unl[i] and all(j in lost for j in m.unl[i])):
                lost.add(i)
                changed = True
    return lost


def summarize_run(plan: Plan, run: Run) -> dict:
    """`lost` steps were made unavailable by a path choice or cutoff, or need a lost step (expected); `stuck` steps are
    still alive but can never be reached, which points at missing entry gates or circular prerequisites in the data."""
    m = plan.model
    taken = {m.idx[u] for u in run.order}
    lost_set = lost_steps(m, run.state, taken)
    lost = sorted(lost_set)
    stuck = [i for i in range(len(m.uids)) if i not in taken and i not in lost_set]
    return dict(xp=round(run.xp), level=run.level, steps=len(taken), lost=len(lost), stuck=len(stuck),
                stuck_xp=round(sum(m.xp[i] for i in stuck)), cliff_steps=run.cliff_steps,
                unresolved_choices=len(run.unresolved))


def stuck_quests(plan: Plan, run: Run, top: int = 8) -> list:
    m = plan.model
    taken = {m.idx[u] for u in run.order}
    lost = lost_steps(m, run.state, taken)
    counts = {}
    for i in range(len(m.uids)):
        if i not in taken and i not in lost:
            counts[m.quest[i]] = counts.get(m.quest[i], 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])[:top]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--file', default=DATA_FILE)
    ap.add_argument('--random', type=int, default=10, help='number of random playthroughs (0 to skip)')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--scope', default='base,hos,bw', help='comma separated: base, hos, bw')
    args = ap.parse_args()

    plan = Plan(Model(restrict(load(args.file), args.scope.split(','))))
    ub = upper_bound(plan)
    print(f'upper bound        : xp {ub["xp"]:>9,.0f}  level {ub["level"]}')
    run = play(plan, story_order)
    print('story order        :', summarize_run(plan, run))
    if stuck := stuck_quests(plan, run):
        print('  stuck steps by quest:', ', '.join(f'{q} {n}' for q, n in stuck))
        print(f'  {len(plan.circular_blocks())} circular blocks in the data (python main.py --units lists them)')
    if args.random:
        rng = random.Random(args.seed)
        runs = [play(plan, random_policy(rng)) for _ in range(args.random)]
        lv = [r.level for r in runs]
        xp = [r.xp for r in runs]
        print(f'random x{args.random:<3}       : level min {min(lv)} / mean {statistics.mean(lv):.1f} / max {max(lv)}, '
              f'xp min {min(xp):,.0f} / mean {statistics.mean(xp):,.0f} / max {max(xp):,.0f}, '
              f'cliff steps mean {statistics.mean(r.cliff_steps for r in runs):.0f}')


if __name__ == '__main__':
    main()
