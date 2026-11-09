"""Command-line pieces shared by the runnable modules (baselines, greedy, export)."""
from __future__ import annotations

from witcher3.loader import DATA_FILE, load, restrict
from witcher3.simulator import Model
from witcher3.units import Plan


def add_data_args(ap, scope: str) -> None:
    ap.add_argument('--file', default=DATA_FILE, help='workbook to load')
    ap.add_argument('--scope', default=scope, help='comma separated: base, hos, bw')


def load_plan(args):
    """-> (full dataset, dataset restricted to --scope, Plan over the restricted dataset)."""
    full = load(args.file)
    ds = restrict(full, args.scope.split(','))
    return full, ds, Plan(Model(ds))
