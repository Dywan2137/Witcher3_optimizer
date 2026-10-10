"""Load and validate the quest data. Usage: python main.py [--file PATH] [--csv issues.csv] [--all] [--units]"""
import argparse
import sys

import pandas as pd

from witcher3.loader import DATA_FILE, load, summarize, validate
from witcher3.simulator import Model
from witcher3.units import Plan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', default=DATA_FILE, help='workbook to load')
    ap.add_argument('--csv', help='also write all issues to this CSV')
    ap.add_argument('--all', action='store_true', help='print every issue, not 5 per check')
    ap.add_argument('--units', action='store_true', help='also print the decision-unit summary and its diagnostics')
    args = ap.parse_args()

    ds = load(args.file)
    issues = validate(ds)
    pd.set_option('display.width', 200, 'display.max_columns', 30, 'display.max_colwidth', 90)

    print(f'{len(ds.steps)} steps, {len(ds.relationships)} relationships\n')
    print(summarize(ds), '\n')
    if issues.empty:
        print('No issues.')
    else:
        print(issues.groupby(['severity', 'check']).size().rename('count').to_string(), '\n')
        for (sev, check), g in issues.groupby(['severity', 'check']):
            print(f'[{sev}] {check} ({len(g)})')
            print(g.head(None if args.all else 5)[['location', 'ref', 'message']].to_string(index=False), '\n')
    if args.units:
        plan = Plan(Model(ds))
        print('decision units:', plan.stats())
        notes = plan.diagnostics()
        print(f'{len(notes)} unit diagnostics' + (':' if notes else '.'))
        for note in notes:
            print(' ', note)
    if args.csv:
        issues.to_csv(args.csv, index=False, encoding='utf-8-sig')
    return int((issues['severity'] == 'error').any()) if not issues.empty else 0


if __name__ == '__main__':
    sys.exit(main())
