#!/usr/bin/env python3
"""BUILD-40: run actual shell-test recipes under a parent Make jobserver."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class JobserverTests(unittest.TestCase):
    def check_recipe(self, name):
        root = Path(__file__).resolve().parent.parent
        recipe = next(line for line in (root / "Makefile").read_text().splitlines()
                      if line.startswith("\t") and "sh tests/" + name in line)
        env = {key: value for key, value in os.environ.items()
               if key not in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL")}
        with tempfile.TemporaryDirectory(prefix="autoupscale-jobserver-") as directory:
            makefile = Path(directory) / "Makefile"
            makefile.write_text("all:\n" + recipe + "\n")
            result = subprocess.run(["make", "--no-print-directory", "-j2", "-f", str(makefile)],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("jobserver unavailable", result.stderr)

    def test_install_recipe(self):
        self.check_recipe("test_plugin_install.sh")

    def test_benchmark_recipe(self):
        self.check_recipe("test_bench_recipes.sh")


if __name__ == "__main__":
    unittest.main()
