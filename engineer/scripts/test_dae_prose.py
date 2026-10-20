#!/usr/bin/env python3
"""Tests for dae_prose.py — what counts as prose, and what is a tell."""
import os
import unittest

import dae_prose as p

HERE = os.path.dirname(os.path.abspath(__file__))


def rules(text):
    return [(r, h) for _, r, h in p.check_text(text)]


class TestTells(unittest.TestCase):
    def test_banned_word_and_chatbot_phrase(self):
        self.assertEqual(rules("We leverage the cache.\nHope this helps!"),
                         [("banned", "leverage"), ("chatbot", "hope this helps")])

    def test_word_boundaries(self):
        self.assertEqual(rules("Robustness and pre-leverage are other words."), [])

    def test_em_dash_chain(self):
        self.assertEqual(rules("a — b — c"), [])
        self.assertEqual(rules("a — b — c — d")[0][0], "em-dash chain")


class TestSkips(unittest.TestCase):
    def test_code_quotes_and_frontmatter_are_ignored(self):
        text = ("---\ntitle: robust\n---\n"
                "```\nleverage\n```\n"
                "Use `robust` here.\n"
                'The banned word "leverage" is quoted.\n'
                "> a robust quote\n"
                "robust on purpose <!-- prose-ok -->\n")
        self.assertEqual(rules(text), [])

    def test_line_numbers_survive_skips(self):
        self.assertEqual(p.check_text("```\nx\n```\nrobust")[0][0], 4)


class TestRepoBaseline(unittest.TestCase):
    def test_engineer_references_are_clean(self):
        ref = os.path.join(HERE, "..", "references")
        paths = [os.path.join(r, f) for r, _, fs in os.walk(ref) for f in fs if f.endswith(".md")]
        self.assertEqual(p.check_files(paths), [])


if __name__ == "__main__":
    unittest.main()
