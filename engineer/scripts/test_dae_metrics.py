#!/usr/bin/env python3
"""Tests for dae_metrics.py — median, fix parsing, governance, compute shape."""
import os
import tempfile
import time
import unittest

import dae_metrics as mm


class TestHelpers(unittest.TestCase):
    def test_median(self):
        self.assertIsNone(mm._med([]))
        self.assertEqual(mm._med([1, 3, 5]), 3.0)
        self.assertEqual(mm._med([2, 4]), 3.0)

    def test_fix_stats(self):
        with tempfile.TemporaryDirectory() as root:
            fdir = os.path.join(root, ".engineer", "fixes")
            os.makedirs(fdir)
            for name in ("2026-01-01-old.md", "2026-06-01-recent.md", "notes.txt"):
                open(os.path.join(fdir, name), "w").close()
            since = time.mktime((2026, 3, 1, 0, 0, 0, 0, 0, -1))
            in_window, mttr = mm._fix_stats(root, since)
            self.assertEqual(in_window, 1)          # only the June fix is after March
            self.assertEqual(len(mttr), 2)          # both dated fixes contribute MTTR

    def test_governance_counts_handoffs(self):
        with tempfile.TemporaryDirectory() as root:
            hdir = os.path.join(root, "features", "010-x", "handoffs")
            os.makedirs(hdir)
            for n in ("a.md", "b.md", "c.md"):
                open(os.path.join(hdir, n), "w").close()
            rows = mm._governance(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["feature"], "010-x")
            self.assertEqual(rows[0]["artifact_versions"], 3)


class TestCompute(unittest.TestCase):
    def test_shape_is_failsafe(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".engineer"))
            with open(os.path.join(root, ".engineer", "manifest.yml"), "w") as fh:
                fh.write("methodology_version: 0.27.0\n")
            d = mm.compute(root, window_days=90)
            self.assertIn("dora", d)
            for k in ("deploy_frequency", "lead_time_days", "change_failure_rate", "mttr_days"):
                self.assertIn(k, d["dora"])
            # no data -> graceful nulls, not crashes
            self.assertIsNone(d["dora"]["lead_time_days"]["median"])
            self.assertEqual(d["governance"], [])


if __name__ == "__main__":
    unittest.main()
