"""Step 3: decision units.

The search should not reason about 1000+ single steps. It works with `Action`s:

  free step      any step outside a sealed block, taken one at a time (optional free steps are simply never taken
                 if the search leaves them out: that is the include/exclude toggle).
  block unit     a sealed block (Block_ID tag) played through in place, as one action. The interior is played with
                 the simulator's own `take`, so every rule is enforced exactly as for single steps, and the XP
                 depends on the state it is entered in (no flat sum). A unit is parameterised by
                   variant    which path tag to follow for each choice group that has members in the block;
                   optionals  which optional members to include.
  choice group   mutually exclusive path tags (connected by excludes_path). Exactly one alternative has to end up
                 chosen once the group is reachable: `unresolved_choices` reports the groups that still owe a choice.

Unit boundaries never leave a block open, so between actions `state.open_block is None`.
"""
from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass

from .simulator import Model, State, Taken, available, is_dead, take, why_not


@dataclass(frozen=True)
class Action:
    kind: str                       # 'step' | 'block'
    ref: object                     # step index (kind 'step') or block tag (kind 'block')
    variant: tuple = ()             # ((group id, path tag), ...)
    optionals: tuple = ()           # optional member indices included in the play

    def label(self, model: Model) -> str:
        if self.kind == 'step':
            return model.uids[self.ref]
        extra = ''.join(f' {t}' for _, t in self.variant) + (f' +{len(self.optionals)} optional' if self.optionals else '')
        return f'{self.ref}{extra}'


@dataclass(frozen=True)
class ChoiceGroup:
    gid: str                        # smallest tag of the group
    tags: tuple
    steps: dict                     # tag -> step indices carrying exactly that tag
    entry: tuple                    # prerequisites outside the group: it is reachable once one of them is done


@dataclass(frozen=True)
class BlockUnit:
    tag: str
    members: tuple
    quests: frozenset
    groups: tuple                   # ids of choice groups with a (single-tag) member in the block
    optional_members: tuple


class Plan:
    """Static decomposition of a Model into units. Built once."""

    def __init__(self, model: Model):
        self.model = m = model
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, others in m.tag_excl.items():
            for b in others:
                parent[find(a)] = find(b)
        by_root = defaultdict(set)
        for t in list(parent):
            by_root[find(t)].add(t)

        self.tag_group = {}
        self.groups = {}
        for tags in by_root.values():
            gid = min(tags)
            steps = {t: tuple(i for i in range(len(m.uids)) if m.tags[i] == (t,)) for t in sorted(tags)}
            inside = {i for i in range(len(m.uids)) if m.tags[i] and set(m.tags[i]) <= tags}
            entry = sorted({j for i in inside for j in m.req[i] + m.unl[i] if j not in inside})
            self.groups[gid] = ChoiceGroup(gid, tuple(sorted(tags)), steps, tuple(entry))
            for t in tags:
                self.tag_group[t] = gid

        self.free_steps = [i for i in range(len(m.uids)) if m.block[i] is None]
        self.blocks = {}
        for tag, members in m.members.items():
            gids = sorted({self.tag_group[m.tags[i][0]] for i in members if len(m.tags[i]) == 1 and m.tags[i][0] in self.tag_group})
            self.blocks[tag] = BlockUnit(tag, tuple(members), frozenset(m.block_quests[tag]), tuple(gids),
                                         tuple(i for i in members if m.optional[i]))

    # ---- parameter space of a block unit ----
    def variants(self, tag: str) -> list:
        """One variant per way of choosing a path tag in every choice group that has members in the block."""
        b, m = self.blocks[tag], self.model
        per_group = []
        for gid in b.groups:
            tags = sorted({m.tags[i][0] for i in b.members if len(m.tags[i]) == 1 and self.tag_group.get(m.tags[i][0]) == gid})
            per_group.append([(gid, t) for t in tags])
        return [tuple(c) for c in itertools.product(*per_group)]

    def optional_modes(self, tag: str) -> list:
        opt = self.blocks[tag].optional_members
        return [(), opt] if opt else [()]

    # ---- playing ----
    def try_play(self, state: State, tag: str, variant: tuple = (), optionals: tuple = ()):
        """Play block `tag` to its closure from `state`. Returns (new_state, [Taken]) or None if it cannot be done."""
        m, b = self.model, self.blocks[tag]
        chosen, extra = dict(variant), set(optionals)
        s, taken = state.copy(), []

        def skipped(i):                                # a step of a path the variant does not follow
            return len(m.tags[i]) == 1 and m.tags[i][0] in self.tag_group and \
                chosen.get(self.tag_group[m.tags[i][0]], m.tags[i][0]) != m.tags[i][0]

        def usable(i):
            return m.quest[i] in b.quests and m.block[i] in (None, tag) and not skipped(i)

        def next_step(i, seen):
            if i in seen or not usable(i):
                return None
            seen.add(i)
            reason = why_not(m, s, i)
            if reason is None:
                return i
            if i in s.done or is_dead(m, s, i):
                return None
            for j in m.req[i]:                         # all required: the first missing one must be reachable
                if j not in s.done:
                    return next_step(j, seen)
            if m.unl[i] and not any(j in s.done for j in m.unl[i]):
                for j in m.unl[i]:                     # alternatives: first one that works
                    found = next_step(j, seen)
                    if found is not None:
                        return found
            return None                                # blocked by the open-block rule, or unreachable

        for _ in range(len(m.uids) + 1):               # n steps + one pass to see nothing is pending
            pending = [i for i in b.members if i not in s.done and not is_dead(m, s, i) and not skipped(i)
                       and (not m.optional[i] or i in extra)]
            if not pending:
                break
            nxt = next((f for f in (next_step(i, set()) for i in pending) if f is not None), None)
            if nxt is None:
                return None
            taken.append(take(m, s, nxt))
        else:
            return None
        return (s, taken) if s.open_block is None and taken else None

    @staticmethod
    def _between_units(state: State) -> None:
        if state.open_block is not None:
            raise ValueError(f'block {state.open_block} is open: units are only started between units')

    def legal_actions(self, state: State) -> list:
        """Everything the search may start now: available free steps, and every block unit (with each variant
        and optional mode) that can be entered and played to its end from this state."""
        m = self.model
        self._between_units(state)
        av = set(available(m, state))
        acts = [Action('step', i) for i in self.free_steps if i in av]
        for tag, b in self.blocks.items():
            if not any(i in av for i in b.members):    # cheap filter before the dry runs
                continue
            for variant in self.variants(tag) or [()]:
                for opts in self.optional_modes(tag):
                    if self.try_play(state, tag, variant, opts) is not None:
                        acts.append(Action('block', tag, variant, opts))
        return acts

    def apply(self, state: State, action: Action):
        """-> (new_state, [Taken]). Raises ValueError if the action is not legal in `state`."""
        m = self.model
        self._between_units(state)
        if action.kind == 'step':
            reason = why_not(m, state, action.ref)
            if reason or m.block[action.ref] is not None:
                raise ValueError(f'{action.label(m)}: {reason or "step belongs to a block unit"}')
            s = state.copy()
            return s, [take(m, s, action.ref)]
        out = self.try_play(state, action.ref, action.variant, action.optionals)
        if out is None:
            raise ValueError(f'block {action.ref} cannot be played from this state')
        return out

    # ---- choices ----
    def unresolved_choices(self, state: State) -> list:
        """Choice groups that are reachable (an entry step is done, or the group has none), still have a live
        alternative, and have no tag chosen yet. Exactly one alternative must be taken for each of them."""
        m, out = self.model, []
        for g in self.groups.values():
            if g.entry and not any(j in state.done for j in g.entry):
                continue
            if any(i in state.done for t in g.tags for i in g.steps[t]):
                continue
            if any(g.steps[t] and not all(is_dead(m, state, i) for i in g.steps[t]) for t in g.tags):
                out.append(g.gid)
        return out

    # ---- reporting ----
    def diagnostics(self) -> list:
        """Data problems visible to the units: blocks that cannot be completed or that force a path choice."""
        m, notes = self.model, []
        for tag, b in self.blocks.items():
            # everything except this block's members and the unblocked steps of its quests (played inside the block)
            # counts as done, including earlier blocks of the same quest
            ideal = State(done={i for i in range(len(m.uids))
                                if m.block[i] != tag and not (m.quest[i] in b.quests and m.block[i] is None)})
            plays = [self.try_play(ideal, tag, v, o) for v in self.variants(tag) or [()] for o in self.optional_modes(tag)]
            if not any(plays):
                notes.append(f'block {tag}: cannot be played through even when every outside step is done')
            for gid in b.groups:
                g = self.groups[gid]
                inside = {m.tags[i][0] for i in b.members if len(m.tags[i]) == 1}
                outside = [t for t in g.tags if t not in inside]
                if outside and len(inside & set(g.tags)) == 1:
                    notes.append(f'block {tag}: entering it forces {sorted(inside & set(g.tags))[0]}; '
                                 f'{", ".join(outside)} sit outside the block')
        return notes + self.circular_blocks()

    def circular_blocks(self) -> list:
        """Blocks that can never be completed in place: a step they need from outside depends on one of their own
        members (e.g. a sealed Baron questline that needs a Ciri flashback, which itself starts after a block step)."""
        import graphlib
        m = self.model
        ts = graphlib.TopologicalSorter()
        for i in range(len(m.uids)):
            ts.add(i, *(m.req[i] + m.unl[i]))
        try:
            order = list(ts.static_order())
        except graphlib.CycleError:
            return ['precedence graph has a cycle (see python main.py validation)']
        anc = {}
        for i in order:                                          # ancestors via requires/unlocks, parents first
            anc[i] = set().union(*((anc[p] | {p}) for p in m.req[i] + m.unl[i]))
        notes = []
        for tag, b in self.blocks.items():
            members = set(b.members)
            inside = {i for i in range(len(m.uids)) if m.quest[i] in b.quests and m.block[i] is None}
            need = set().union(*(anc[i] for i in members)) if members else set()
            closure = members | (inside & need)

            def depends_on_block(p):
                return sorted(members & (anc[p] | {p}))

            for i in sorted(closure):
                outside = [p for p in m.req[i] if p not in closure]
                alts = [p for p in m.unl[i] if p not in closure]
                if m.unl[i] and not any(p in closure for p in m.unl[i]) and alts and all(depends_on_block(p) for p in alts):
                    outside.append(alts[0])
                for p in outside:
                    via = depends_on_block(p)
                    if via:
                        notes.append(f'block {tag}: {m.uids[i]} needs {m.uids[p]}, which itself needs {m.uids[via[0]]} '
                                     f'inside the block, so the block can never be completed')
        return notes

    def stats(self) -> dict:
        var = [len(self.variants(t)) or 1 for t in self.blocks]
        return dict(steps=len(self.model.uids), free_steps=len(self.free_steps), blocks=len(self.blocks),
                    block_members=sum(len(b.members) for b in self.blocks.values()),
                    blocks_with_choices=sum(1 for b in self.blocks.values() if b.groups),
                    max_variants=max(var), choice_groups=len(self.groups),
                    optional_free=sum(1 for i in self.free_steps if self.model.optional[i]),
                    optional_in_blocks=sum(len(b.optional_members) for b in self.blocks.values()))
