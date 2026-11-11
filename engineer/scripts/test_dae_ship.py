#!/usr/bin/env python3
"""Tests for dae_ship. Run: python3 test_dae_ship.py"""
import os
import tempfile
import unittest

import dae_reconcile as dr
import dae_ship as ds

FEATURE = "---\nslug: 042-x\nbranch: 042-x\nstatus: in-progress\n---\nbody\n"
PROGRESS = "> ▶ CP8 Harden — 2/3 criteria met | NEXT: x | BLOCKED: none\n\n| 7 | Verify | done |\n| 8 | Harden | in-progress |\n"


def _mk(tmp, progress=PROGRESS):
    d = os.path.join(tmp, "042-x")
    os.makedirs(d)
    open(os.path.join(d, "feature.md"), "w").write(FEATURE)
    open(os.path.join(d, "progress.md"), "w").write(progress)
    return d


class TestShip(unittest.TestCase):
    def test_full_lane_refuses_without_handoffs(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _mk(tmp)
            with self.assertRaises(ds.ShipRefused):
                ds.ship(d)
            self.assertEqual(dr.feature_status(d), "in-progress")  # nothing written

    def test_express_writes_done_and_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _mk(tmp)
            ds.ship(d, lane="express")
            self.assertEqual(dr.feature_status(d), "done")
            text = open(os.path.join(d, "progress.md")).read()
            self.assertIn("awaiting merge", text)
            self.assertNotIn("merged_at", text)

    def test_set_progress_marks_cp8_row(self):
        out = ds.set_progress(PROGRESS)
        self.assertIn("| 8 | Harden | done |", out)
        self.assertEqual(out.count("▶"), 1)


if __name__ == "__main__":
    unittest.main()
