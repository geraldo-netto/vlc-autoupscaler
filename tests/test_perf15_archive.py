"""BUILD-46: published analysis imports work without the checkout."""
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


class ArchiveTests(unittest.TestCase):
    def test_build46_archive_contains_transitive_imports(self):
        archive = Path(__file__).resolve().parent.parent / 'docs/benchmarks/perf15-ten-pairs/analysis-sources.tar.gz'
        with tempfile.TemporaryDirectory() as root:
            with tarfile.open(archive) as stream:
                stream.extractall(root, filter='data')
            env = {key: value for key, value in os.environ.items() if not key.startswith('PYTHON')}
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            command = [sys.executable, 'build/perf15/analyze_ten_pairs.py', '--help']
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('usage:', result.stdout)


if __name__ == '__main__':
    unittest.main()
