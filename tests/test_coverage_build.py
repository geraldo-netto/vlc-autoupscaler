#!/usr/bin/env python3
"""Coverage regressions remain wired into the instrumented suite."""
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parent.parent


class CoverageBuildTests(unittest.TestCase):
    def coverage_tests(self, *settings):
        result = subprocess.run(
            ["make", "--no-print-directory", *settings,
             "--eval=print-coverage:;@printf '%s\\n' $(COV_TESTS)", "print-coverage"],
            cwd=ROOT, capture_output=True, text=True, check=True)
        return {Path(line).name for line in result.stdout.splitlines()}

    def test_rev3_retirement_regressions_instrumented(self):
        names = self.coverage_tests("HAVE_PROFILE_SDKS=1")
        self.assertIn("test_frame_retirement_usm", names)
        self.assertIn("test_frame_retirement_zimg", names)
        names = self.coverage_tests("HAVE_PROFILE_SDKS=")
        self.assertIn("test_frame_retirement_usm", names)
        self.assertNotIn("test_frame_retirement_zimg", names)

    def test_rev2_metrics_instrumented_and_gated(self):
        self.assertIn('test_pipeline_metrics', self.coverage_tests())
        scope = (ROOT / 'scripts/coverage_scope.txt').read_text().splitlines()
        self.assertIn('src/pipeline_metrics.h', scope)


if __name__ == "__main__":
    unittest.main()
