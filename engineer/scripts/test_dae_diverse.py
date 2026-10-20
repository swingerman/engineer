#!/usr/bin/env python3
"""Tests for dae_diverse — the second-family review gate.

Run: python3 test_dae_diverse.py
"""

import unittest

from dae_diverse import evaluate


class TestEvaluate(unittest.TestCase):
    def test_large_sizes_get_diverse(self):
        for size in ("L", "XL", "l"):
            self.assertTrue(evaluate({"size": size})[0], size)

    def test_small_sizes_never_even_when_flagged(self):
        for size in ("XS", "S"):
            self.assertFalse(evaluate({"size": size, "charter_flagged": True})[0], size)

    def test_express_lane_never(self):
        fm = {"size": "L", "charter_flagged": True, "gate_profile": {"lane": "express"}}
        self.assertFalse(evaluate(fm)[0])

    def test_flagged_medium_or_unsized_gets_diverse(self):
        self.assertTrue(evaluate({"size": "M", "charter_flagged": True})[0])
        self.assertTrue(evaluate({"charter_flagged": "true"})[0])

    def test_plain_medium_and_unsized_skip(self):
        self.assertFalse(evaluate({"size": "M"})[0])
        self.assertFalse(evaluate({})[0])


if __name__ == "__main__":
    unittest.main()
