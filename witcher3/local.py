"""Step 6: local search (simulated annealing) on top of the greedy.

Encoding: a solution is a priority key per action (`units.Action`). The decoder plays the game and at every decision
takes the legal action with the lowest key, so every key vector decodes to a legal playthrough and no repair is
needed. Path choices are just keys too: whichever variant of a block (or first step of a path) comes first is taken.
Actions without a key go last, in workbook order. After decoding, the keys of a solution are its positions
(0, 1, 2, ...), so a move such as "key of X = 10.5" reads as "play X right after the 11th action".

Moves, picked at a position weighted by the XP lost there (gain vs the step's best multiplier: late steps at the
5% cliff, Hearts of Stone steps played outside +5..+9):
  shift   move one action earlier or later (up to `window` positions)
  swap    exchange two nearby actions
  segment move a run of 2-8 consecutive actions together
  choice  try another variant of a block, or the other path of a free-step choice group, at the same position
  insert  play a never-played action (e.g. one a cutoff killed) at a position where it was available

Acceptance: simulated annealing on total XP (worse solutions accepted with probability exp(delta / T), T cooled
geometrically from t0 to t1); `t0 = 0` is plain hill climbing. t0 and t1 are fractions of the mean XP of a paying
step, so the same setting works on datasets of any scale (0.2 x 155 XP = 31 XP at the start on base + hos). The search starts from the best greedy run, so it
can only improve on it.

Speed: the decoder keeps every decision point (state, candidates, which ones were found illegal). A move only
changes the playthrough from the first decision where a candidate not known to be illegal now outranks the old
choice, so only the tail from there is replayed.

Usage: python -m witcher3.local [--scope base,hos] [--iters N] [--chains K] [--seed S] [--restarts N] [--history h.csv]
       [--steps] [--csv plan.csv]
"""
from __future__ import annotations

import argparse
import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ''):  # run as a plain script (python witcher3/local.py, an IDE Run button)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from witcher3.baselines import Run, first_index, play, summarize_run, upper_bound
from witcher3.checker import check
from witcher3.cli import add_data_args, load_plan
from witcher3.greedy import CONFIGS, best_of, greedy, steps_table
from witcher3.simulator import State, start_state
from witcher3.units import Action, Plan

UNKEYED = 10 ** 6          # actions without a key go after every keyed one, in workbook order


@dataclass
class Point:
    """One decision of a decoded playthrough."""
    state: State           # state before the decision
    cands: list            # candidate actions in the order they were generated
    illegal: frozenset     # indices into cands found illegal from this state
    chosen: int | None     # index into cands; None at the final point (nothing legal)
    taken: list            # [Taken] of the chosen action
    after: State           # state after it


class Decoder:
    def __init__(self, plan: Plan):
        self.plan = plan
        self._first = {}

    def key(self, keys: dict, a: Action) -> float:
        k = keys.get(a)
        if k is not None:
            return k
        if a not in self._first:
            self._first[a] = UNKEYED + first_index(self.plan, a)
        return self._first[a]

    def decide(self, keys: dict, state: State) -> Point:
        cands = self.plan.candidates(state)
        illegal = set()
        for n in sorted(range(len(cands)), key=lambda n: (self.key(keys, cands[n]), n)):
            a = cands[n]
            out = self.plan.apply(state, a) if a.kind == 'step' else self.plan.try_play(state, a.ref, a.variant, a.optionals)
            if out is not None:
                return Point(state, cands, frozenset(illegal), n, out[1], out[0])
            illegal.add(n)
        return Point(state, cands, frozenset(illegal), None, [], state)

    def decode(self, keys: dict, prefix: list = ()) -> list:
        """Play from the end of `prefix` (decision points kept from an earlier decode) to the end of the game."""
        points = list(prefix)
        s = points[-1].after if points else start_state(self.plan.model)
        while True:
            pt = self.decide(keys, s)
            points.append(pt)
            if pt.chosen is None:
                return points
            s = pt.after

    def divergence(self, points: list, keys: dict) -> int | None:
        """First decision whose outcome may change under `keys`, or None if the playthrough stays the same."""
        for p, pt in enumerate(points):
            if pt.chosen is None:
                rank = (math.inf, math.inf)
            else:
                rank = (self.key(keys, pt.cands[pt.chosen]), pt.chosen)
            for n, a in enumerate(pt.cands):
                if n != pt.chosen and n not in pt.illegal and (self.key(keys, a), n) < rank:
                    return p
        return None


@dataclass
class Solution:
    points: list

    @property
    def actions(self) -> list:
        return [pt.cands[pt.chosen] for pt in self.points if pt.chosen is not None]

    @property
    def state(self) -> State:
        return self.points[-1].state

    @property
    def xp(self) -> float:
        return self.state.xp

    def keys(self) -> dict:
        return {a: float(n) for n, a in enumerate(self.actions)}

    def run(self, plan: Plan) -> Run:
        trace = [t for pt in self.points for t in pt.taken]
        return Run([t.uid for t in trace], self.state, trace, plan.unresolved_choices(self.state), self.actions)


class Search:
    def __init__(self, plan: Plan, rng: random.Random, window: int = 40):
        self.plan, self.rng, self.window = plan, rng, window
        self.dec = Decoder(plan)
        m = plan.model
        self.best_gain = [m.xp[i] * (1.0 if not m.has_level[i] else max(m.rules[m.rule[i]][2])) for i in range(len(m.uids))]

    def solution(self, keys: dict, base: Solution | None = None) -> Solution | None:
        """Decode `keys`, reusing the unchanged prefix of `base`. None if nothing changes."""
        if base is None:
            return Solution(self.dec.decode(keys))
        p = self.dec.divergence(base.points, keys)
        if p is None:
            return None
        return Solution(self.dec.decode(keys, base.points[:p]))

    # ---- moves ----
    def pick(self, sol: Solution) -> int:
        m = self.plan.model
        loss = [sum(self.best_gain[m.idx[t.uid]] - t.gain for t in pt.taken) for pt in sol.points if pt.chosen is not None]
        floor = sum(loss) / len(loss) * 0.2 + 1.0
        return self.rng.choices(range(len(loss)), weights=[x + floor for x in loss])[0]

    def move(self, sol: Solution) -> tuple[dict, str]:
        acts, keys = sol.actions, sol.keys()
        n, rng, w = len(acts), self.rng, self.window
        i = self.pick(sol)
        a = acts[i]
        kind = rng.choices(['shift', 'swap', 'segment', 'choice', 'insert'], weights=[4, 2, 2, 1, 2])[0]
        if kind == 'insert':
            unplayed = self.unplayed(sol)
            if unplayed:
                b, where = rng.choice(list(unplayed.items()))
                j = rng.choice(where)
                keys[b] = j - 0.5
                return keys, f'insert {b.label(self.plan.model)} ->{j}'
            kind = 'shift'
        if kind == 'choice':
            alts = self.alternatives(a, keys)
            if alts:
                keys.update(rng.choice(alts))
                return keys, f'choice {a.label(self.plan.model)}'
            kind = 'shift'
        j = min(n - 1, max(0, i + rng.randint(-w, w)))
        if kind == 'swap':
            keys[a], keys[acts[j]] = keys[acts[j]], keys[a]
        elif kind == 'segment':
            length = rng.randint(2, 8)
            seg = acts[i:i + length]
            if i <= j < i + length:
                j = max(0, i - rng.randint(1, w)) if rng.random() < 0.5 else min(n, i + length + rng.randint(0, w))
            at = j - 0.5
            for k, b in enumerate(seg):
                keys[b] = at + (k + 1) / (len(seg) + 2)
        else:
            keys[a] = j - 0.5 if j < i else j + 0.5
        return keys, f'{kind} {a.label(self.plan.model)} {i}->{j}'

    @staticmethod
    def unplayed(sol: Solution) -> dict:
        """Actions never played (lost to a cutoff or a choice, or left for later): action -> positions where it
        could have been started. Without this move a step killed by a cutoff could never come back."""
        played = set(sol.actions)
        out = {}
        for p, pt in enumerate(sol.points):
            for n, a in enumerate(pt.cands):
                if a not in played and n not in pt.illegal and n != pt.chosen:
                    out.setdefault(a, []).append(p)
        return out

    def alternatives(self, a: Action, keys: dict) -> list:
        """Key updates that try another way of playing the choice behind `a`, at its current position."""
        plan, m = self.plan, self.plan.model
        if a.kind == 'block':
            return [{b: keys[a] - 0.5} for v in plan.variants(a.ref) for o in plan.optional_modes(a.ref)
                    if (b := Action('block', a.ref, v, o)) != a]
        tags = m.tags[a.ref]
        if len(tags) != 1 or tags[0] not in plan.tag_group:
            return []
        g = plan.groups[plan.tag_group[tags[0]]]
        mine = sorted(keys[x] for i in g.steps[tags[0]] if (x := Action('step', i)) in keys)
        out = []
        for t in g.tags:
            free = [i for i in g.steps[t] if m.block[i] is None]
            if t == tags[0] or not free or not mine:
                continue
            slots = mine + [mine[-1] + 0.01 * (k + 1) for k in range(len(free))]
            out.append({Action('step', i): k - 0.5 for i, k in zip(free, slots)})
        return out

    # ---- annealing ----
    def anneal(self, start: Solution, iters: int, t0: float = 0.2, t1: float = 0.005, log=None):
        """-> (best Solution, history [(iteration, current xp, best xp)])."""
        paying = [x for x in self.plan.model.xp if x > 0]
        scale = sum(paying) / len(paying) if paying else 1.0
        t0, t1 = t0 * scale, max(t1 * scale, 1e-9)
        cur = best = start
        history = [(0, cur.xp, best.xp)]
        for it in range(1, iters + 1):
            temp = t0 * (t1 / t0) ** (it / iters) if t0 > 0 else 0.0
            keys, desc = self.move(cur)
            new = self.solution(keys, cur)
            if new is None:
                continue
            delta = new.xp - cur.xp
            if delta >= 0 or (temp > 0 and self.rng.random() < math.exp(delta / temp)):
                cur = new
                if cur.xp > best.xp:
                    best = cur
                    if log:
                        log(f'  iter {it:>5}: {best.xp:,.0f} XP, level {best.state.level}  ({desc})')
            history.append((it, cur.xp, best.xp))
        return best, history


def optimize(plan: Plan, iters: int, seed: int = 0, restarts: int = 0, noise: float = 4.0,
             t0: float = 0.2, t1: float = 0.005, chains: int = 1, log=None):
    """Greedy (best of `restarts` randomized runs), then `chains` independent annealing runs of `iters` iterations
    from it (seeds seed, seed + 1, ...). -> (best Run, greedy start Run, history of the best chain)."""
    start = best_of(plan, restarts, noise, configs=CONFIGS) if restarts else play(plan, greedy(plan))
    keys = {a: float(n) for n, a in enumerate(start.actions)}
    best = history = None
    for c in range(chains):
        search = Search(plan, random.Random(seed + c))
        sol, hist = search.anneal(search.solution(keys), iters, t0, t1, log)
        if log and chains > 1:
            log(f'chain {c + 1}/{chains}: {sol.xp:,.0f} XP, level {sol.state.level}')
        if best is None or sol.xp > best.xp:
            best, history = sol, hist
    return best.run(plan), start, history


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    add_data_args(ap, 'base,hos')
    ap.add_argument('--iters', type=int, default=2000)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--chains', type=int, default=1, help='independent annealing runs (seeds seed, seed + 1, ...)')
    ap.add_argument('--restarts', type=int, default=0, help='randomized greedy restarts for the start (0 = plain greedy)')
    ap.add_argument('--noise', type=float, default=4.0, help='deadline perturbation, in levels, for the restarts')
    ap.add_argument('--t0', type=float, default=0.2, help='start temperature, x mean step XP (0 = hill climbing)')
    ap.add_argument('--t1', type=float, default=0.005, help='final temperature, x mean step XP')
    ap.add_argument('--history', help='save (iteration, current xp, best xp) to this CSV file')
    ap.add_argument('--steps', action='store_true', help='print the best run as an ordered list of steps')
    ap.add_argument('--csv', help='save the best run as an ordered list of steps to this CSV file')
    args = ap.parse_args()

    _, ds, plan = load_plan(args)
    ub = upper_bound(plan)
    print(f'scope {args.scope}: {len(plan.model.uids)} steps, upper bound {ub["xp"]:,.0f} XP (level {ub["level"]})')
    t = time.time()
    best, start, history = optimize(plan, args.iters, args.seed, args.restarts, args.noise, args.t0, args.t1,
                                     args.chains, log=print)
    print(f'greedy start      : {summarize_run(plan, start)}')
    print(f'local search      : {summarize_run(plan, best)}')
    print(f'{args.chains} x {args.iters} iterations in {time.time() - t:.0f} s, gain {best.xp - start.xp:+,.0f} XP')
    problems = check(ds, best.order)[0]
    print('checker: ok' if not problems else f'checker: {len(problems)} problems, first: {problems[0]}')
    if args.history:
        with open(args.history, 'w') as f:
            f.write('iteration,current_xp,best_xp\n')
            f.writelines(f'{i},{c:.1f},{b:.1f}\n' for i, c, b in history)
        print(f'wrote {len(history)} rows to {args.history}')
    if args.steps or args.csv:
        table = steps_table(ds, best)
        if args.csv:
            table.to_csv(args.csv, index=False, encoding='utf-8-sig')
            print(f'wrote {len(table)} steps to {args.csv}')
        if args.steps:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            print(table.to_string(index=False))


if __name__ == '__main__':
    main()
