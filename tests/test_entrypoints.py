"""Every runnable file must start no matter how it is launched (plain script from any folder, or python -m)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ['greedy', 'baselines', 'build_relationships', 'export']


def run(args, cwd):
    return subprocess.run([sys.executable, *args, '--help'], cwd=cwd, capture_output=True, text=True, timeout=120)


class EntryPoints(unittest.TestCase):
    def test_as_a_plain_script_from_the_package_folder(self):
        for name in MODULES:
            r = run([f'{name}.py'], ROOT / 'witcher3')               # e.g. an IDE "run file" button
            self.assertEqual(r.returncode, 0, f'{name}.py: {r.stderr[-300:]}')
            self.assertIn('usage', r.stdout.lower())

    def test_as_a_plain_script_from_an_unrelated_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in MODULES:
                r = run([str(ROOT / 'witcher3' / f'{name}.py')], tmp)
                self.assertEqual(r.returncode, 0, f'{name}.py: {r.stderr[-300:]}')

    def test_with_dash_m_from_the_project_root(self):
        for name in MODULES:
            r = run(['-m', f'witcher3.{name}'], ROOT)
            self.assertEqual(r.returncode, 0, f'{name}: {r.stderr[-300:]}')

    def test_main_py(self):
        r = run(['main.py'], ROOT)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])


if __name__ == '__main__':
    unittest.main()
