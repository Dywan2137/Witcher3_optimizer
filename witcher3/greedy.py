"""Step 5: the greedy policy.

It plugs into baselines.play(plan, policy) like the story-order and random policies. At every decision it ranks the
legal actions (free steps and block units) with these rules, best first:

  1. Delay cutoffs: an action that kills still-valuable steps that could be saved first (a `blocks` edge, e.g. leaving
     White Orchard, Isle of Mists) is only taken when nothing safer is left, so everything it would destroy is played
     first. Not applied once the action itself is past its deadline (`urgent`): delaying it would cost more.
  2. Hearts of Stone pays most when the player is under-leveled (peak 150% at +5..+9), so while the player is more
     than 9 levels below a Hearts of Stone step's recommended level the action waits.
  3. Earliest deadline first: the deadline of a step is the last level at which it still pays its full rate
     (base game / Blood and Wine: recommended level + 9, the last level before the Death March cliff; Hearts of
     Stone: its recommended level). Steps without a recommended level never lose value and go last.
  Both levels in 2 and 3 are read from the Reward_rules sheet (rule_offsets), not hardcoded.
  4. Larger XP first; the highest-paying variant of a block when everything else ties.

greedy(plan) returns the policy. `noise` > 0 perturbs the deadlines (used by the randomized restarts).

Usage: python -m witcher3.greedy [--scope base,hos] [--restarts N] [--steps] [--csv plan.csv] [--file PATH]
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import pandas as pd

if __package__ in (None, ''):  # run as a plain script (python witcher3/greedy.py, an IDE Run button)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from witcher3.baselines import play, random_policy, story_order, summarize_run, upper_bound
from witcher3.cli import add_data_args, load_plan
from witcher3.simulator import Model, State, is_dead
from witcher3.units import Action, Plan

FOREVER = 10 ** 6


def rule_offsets(m: Model, rule_type: str) -> tuple:
    """Read from the Reward_rules sheet, as offsets from the recommended level (level = rec + offset):
    deadline: last level that still pays at least the at-level (gap 0) rate (base_cliff: gap -9 -> rec + 9);
    earliest: first level of the peak multiplier (hos_gradual: 150% from gap 9 down to gap 5, so rec - 9). Waiting
    only until rec - 5 (the end of the window) was tried: about 1.2k XP worse on base + hos and on all scopes."""
    gaps = range(-60, 61)
    mult = {g: m.multiplier(rule_type, g) for g in gaps}
    deadline = -min(g for g in gaps if g <= 0 and mult[g] >= mult[0])
    peak = max(mult.values())
    earliest = -max((g for g in gaps if g >= 0 and mult[g] == peak), default=0) if peak > mult[0] else -FOREVER
    return deadline, earliest


def step_tables(m: Model):
    """deadline[i]: last level at which step i pays its full rate; earliest[i]: level before which it should wait."""
    offsets = {r: rule_offsets(m, r) for r in m.rules}
    deadline, earliest = [], []
    for i in range(len(m.uids)):
        if not m.has_level[i] or len(set(m.rules[m.rule[i]][2])) == 1:      # one multiplier at every gap: never decays
            deadline.append(FOREVER)
            earliest.append(-FOREVER)
        else:
            d, e = offsets[m.rule[i]]
            deadline.append(m.rec[i] + d)
            earliest.append(m.rec[i] + e if e != -FOREVER else -FOREVER)
    return deadline, earliest


def descendants(m: Model) -> list:
    """desc[i]: bitmask of the steps that need step i, directly or through a chain of prerequisites."""
    desc = [0] * len(m.uids)
    for i in reversed(m.topo):                              # children before parents
        for c in m.children[i]:
            desc[i] |= (1 << c) | desc[c]
    return desc


def effective_deadlines(m: Model, deadline: list) -> list:
    """A step is due when the earliest thing that needs it is due: zero-XP gates (e.g. Brothers in Arms) inherit the
    deadline of the high-value chain behind them. Only steps that pay XP carry a deadline of their own."""
    eff = [deadline[i] if m.xp[i] > 0 else FOREVER for i in range(len(m.uids))]
    for i in reversed(m.topo):
        for c in m.children[i]:
            eff[i] = min(eff[i], eff[c])
    return eff


def greedy(plan: Plan, noise: float = 0.0, rng: random.Random | None = None,
           cutoff_guard: bool = True, hos_wait: bool = True, urgent: float = 3.0, savable_only: bool = True,
           propagate: bool = True):
    m = plan.model
    deadline, earliest = step_tables(m)
    if propagate:
        deadline = effective_deadlines(m, deadline)
    rng = rng or random.Random(0)
    desc = descendants(m) if savable_only else None
    jitter = [rng.uniform(-noise, noise) if noise else 0.0 for _ in range(len(m.uids))]

    def steps_of(a: Action):
        return [a.ref] if a.kind == 'step' else list(plan.blocks[a.ref].members)

    def cutoff_risk(state: State, steps) -> float:
        inside = set(steps)
        hit = {t for i in steps for t in m.kills[i] if t not in inside}
        if savable_only:                               # a victim that needs this very action can never be saved first
            needs_it = 0
            for i in steps:
                needs_it |= desc[i]
            hit = {t for t in hit if not (needs_it >> t) & 1}
        return sum(m.xp[t] for t in hit if t not in state.done and not is_dead(m, state, t))

    def rank(state: State, a: Action):
        steps = steps_of(a)
        paying = [i for i in steps if m.xp[i] > 0]
        slack = min((deadline[i] + jitter[i] for i in steps), default=FOREVER) - state.level
        too_early = hos_wait and any(earliest[i] > state.level for i in paying)
        risky = cutoff_guard and slack > urgent and cutoff_risk(state, steps) > 0     # an action past its deadline is not delayed
        tier = (1 if risky else 0) + (2 if too_early else 0)
        return (tier, slack, -sum(m.xp[i] for i in steps))

    def policy(plan_: Plan, state: State, actions: list) -> Action:
        ranked = sorted(((rank(state, a), a) for a in actions), key=lambda ra: ra[0])
        best = ranked[0][0]
        tied = [a for r, a in ranked if r == best]
        if len(tied) == 1:
            return tied[0]

        def value(a: Action) -> float:            # variants of one block tie on the rank: take the one that pays most
            if a.kind == 'step':
                return m.xp[a.ref]
            _, taken = plan.apply(state, a)
            return sum(t.gain for t in taken)
        return max(tied, key=value)

    return policy


CONFIGS = [dict(), dict(cutoff_guard=False), dict(urgent=6.0)]      # rule settings tried by the portfolio


def best_of(plan: Plan, restarts: int, noise: float, seed: int = 0, configs=None):
    """Randomized greedy: for every rule setting, the plain greedy plus `restarts` runs with perturbed deadlines.
    Returns the best Run (most XP)."""
    rng = random.Random(seed)
    best = None
    for cfg in configs or [dict()]:
        for k in range(restarts + 1):
            run = play(plan, greedy(plan, noise=noise if k else 0.0, rng=rng, **cfg))
            if best is None or run.xp > best.xp:
                best = run
    return best


def steps_table(ds, run) -> pd.DataFrame:
    """The playthrough as a table: one row per step in the order to play it."""
    info = ds.steps.set_index('step_uid')
    rows = []
    for n, t in enumerate(run.trace, 1):
        s = info.loc[t.uid]
        rows.append(dict(n=n, step=t.uid, quest=s['quest_name'], description=s['description'], region=s['location'],
                         recommended_level=s['recommended_level'], level_before=t.level_before, multiplier=t.multiplier,
                         xp_gain=round(t.gain, 1), total_xp=round(t.xp), level_after=t.level,
                         level_up='LEVEL UP' if t.level > t.level_before else ''))
    return pd.DataFrame(rows)


def report(plan: Plan, label: str, run) -> None:
    print(f'{label:<18}: {summarize_run(plan, run)}')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    add_data_args(ap, 'base,hos')
    ap.add_argument('--random', type=int, default=5)
    ap.add_argument('--restarts', type=int, default=0, help='randomized greedy restarts (0 = skip)')
    ap.add_argument('--noise', type=float, default=4.0, help='deadline perturbation, in levels, for the restarts')
    ap.add_argument('--steps', action='store_true', help='print the best run as an ordered list of steps')
    ap.add_argument('--csv', help='save the best run as an ordered list of steps to this CSV file')
    ap.add_argument('--ablate', action='store_true', help='also run the greedy with each rule switched off')
    args = ap.parse_args()

    _, ds, plan = load_plan(args)
    ub = upper_bound(plan)
    print(f'scope {args.scope}: {len(plan.model.uids)} steps')
    print(f'upper bound       : xp {ub["xp"]:>9,.0f}  level {ub["level"]}   (loose: best multiplier everywhere, no cutoffs)')
    report(plan, 'story order', play(plan, story_order))
    if args.random:
        rng = random.Random(0)
        runs = [play(plan, random_policy(rng)) for _ in range(args.random)]
        print(f'random x{args.random:<3}       : level {min(r.level for r in runs)}-{max(r.level for r in runs)}, '
              f'xp {min(r.xp for r in runs):,.0f}-{max(r.xp for r in runs):,.0f}')
    plain = play(plan, greedy(plan))
    report(plan, 'greedy', plain)
    if args.ablate:
        report(plan, ' - no cutoff guard', play(plan, greedy(plan, cutoff_guard=False)))
        report(plan, ' - no HoS wait', play(plan, greedy(plan, hos_wait=False)))
        report(plan, ' - neither', play(plan, greedy(plan, cutoff_guard=False, hos_wait=False)))
    best = plain
    if args.restarts:
        best = best_of(plan, args.restarts, args.noise, configs=CONFIGS)
        report(plan, f'best of {args.restarts}x{len(CONFIGS)} runs', best)
    if args.steps or args.csv:
        table = steps_table(ds, best)
        if args.csv:
            table.to_csv(args.csv, index=False, encoding='utf-8-sig')     # utf-8-sig so Excel shows the Polish text
            print(f'wrote {len(table)} steps to {args.csv}')
        if args.steps:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            view = table.drop(columns=['level_up', 'recommended_level']).assign(
                quest=table['quest'].str.slice(0, 30), description=table['description'].str.slice(0, 50))
            print(view.to_string(index=False))


if __name__ == '__main__':
    main()
