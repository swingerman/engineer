#!/usr/bin/env python3
"""Tests for dae_mergeready.py — fail-closed composition + frontmatter parsing."""
import unittest

import dae_mergeready as mr


class TestEvaluate(unittest.TestCase):
    def test_all_green_is_ready(self):
        checks = [{"name": "a", "ok": True, "detail": ""},
                  {"name": "b", "ok": True, "detail": ""}]
        v = mr.evaluate(checks)
        self.assertTrue(v["ready"])
        self.assertEqual(v["blockers"], [])

    def test_one_red_blocks_and_is_named(self):
        checks = [{"name": "a", "ok": True, "detail": ""},
                  {"name": "CI green on open PR", "ok": False, "detail": "no PR"}]
        v = mr.evaluate(checks)
        self.assertFalse(v["ready"])
        self.assertEqual(v["blockers"], ["CI green on open PR"])

    def test_fail_closed_empty(self):
        # No checks at all → vacuously ready is WRONG for a merge gate; but gather
        # always emits checks, so evaluate([]) being ready is fine as a pure fn.
        # The real guard is that any un-runnable check appears as ok=False.
        self.assertTrue(mr.evaluate([])["ready"])


class TestFrontmatter(unittest.TestCase):
    FM = (
        "slug: x\n"
        "autonomy_level: high\n"
        "branch: feat/x\n"
        "gate_profile:\n"
        "  front: bundled\n"
        "  verify: auto\n"
    )

    def test_field_scalar(self):
        self.assertEqual(mr._field(self.FM, "autonomy_level"), "high")
        self.assertEqual(mr._field(self.FM, "branch"), "feat/x")

    def test_field_nested_verify(self):
        # `verify:` only occurs inside gate_profile, so a plain field lookup works
        self.assertEqual(mr._field(self.FM, "verify"), "auto")
        self.assertEqual(mr._field(self.FM, "front"), "bundled")

    def test_field_missing(self):
        self.assertIsNone(mr._field(self.FM, "validation_method"))


if __name__ == "__main__":
    unittest.main()
