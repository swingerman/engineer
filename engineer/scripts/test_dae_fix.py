#!/usr/bin/env python3
"""Unit tests for dae_fix.py"""
import unittest
import tempfile
import os

import dae_fix


class TestParseFix(unittest.TestCase):
    """Tests for parse_fix function"""

    def test_parse_fix_golden_fully_populated(self):
        """Scenario 1: fully-populated artifact parses into all expected fields"""
        text = """---
slug: 2026-05-15-auth-race-condition
title: Authentication race condition on token refresh
source:
  kind: github_issue
  ref: "12345"
severity: critical
blocks_user: true
workaround: refresh the page
status: verified
repro: |
  1. Log in with two tabs
  2. Perform action in tab A
  3. Switch to tab B and verify state
expected: Both tabs should show consistent state
actual: Tab B shows stale data
feature_refs:
  - auth-module
  - session-mgmt
investigation:
  match_mode: substring
  candidates_considered: 5
pin_confirmation:
  feature_refs:
    - feature: auth-module
      spec_path: specs/auth-module.md
      red_run:
        timestamp: "2026-05-15T10:30:00Z"
        result: red
    - feature: session-mgmt
      spec_path: specs/session-mgmt.md
      red_run:
        timestamp: "2026-05-15T10:35:00Z"
        result: red
fix_commits:
  - abc123def456
  - ghi789jkl012
harden_results:
  bug_line_mutation_confirmed: true
  mutation_score: 0.95
  arch_check: passed
gap_analysis:
  - category: architecture_violation
    finding: Race window in token refresh handler
  - category: inadequate_verification
    finding: Specs did not cover multi-tab scenarios
followups:
  - category: architecture_violation
    title: Redesign token refresh
    status: applied
  - category: inadequate_verification
    title: Add multi-tab tests
    status: applied
---
## Body
Some additional content here.
"""
        rec = dae_fix.parse_fix(text)
        self.assertEqual(rec["slug"], "2026-05-15-auth-race-condition")
        self.assertEqual(rec["title"], "Authentication race condition on token refresh")
        self.assertEqual(rec["source"]["kind"], "github_issue")
        self.assertEqual(rec["source"]["ref"], "12345")
        self.assertEqual(rec["severity"], "critical")
        self.assertTrue(rec["blocks_user"])
        self.assertEqual(rec["workaround"], "refresh the page")
        self.assertEqual(rec["status"], "verified")
        self.assertIsNotNone(rec["repro"])
        self.assertIsNotNone(rec["expected"])
        self.assertIsNotNone(rec["actual"])
        self.assertEqual(rec["feature_refs"], ["auth-module", "session-mgmt"])
        self.assertEqual(rec["investigation"]["match_mode"], "substring")
        self.assertEqual(rec["investigation"]["candidates_considered"], 5)
        self.assertIsNotNone(rec["pin_confirmation"])
        self.assertEqual(len(rec["pin_confirmation"]["feature_refs"]), 2)
        self.assertEqual(rec["fix_commits"], ["abc123def456", "ghi789jkl012"])
        self.assertIsNotNone(rec["harden_results"])
        self.assertTrue(rec["harden_results"]["bug_line_mutation_confirmed"])
        self.assertEqual(len(rec["gap_analysis"]), 2)
        self.assertEqual(len(rec["followups"]), 2)

    def test_parse_fix_minimal(self):
        """Scenario 2: only slug + title + status present, other fields default cleanly"""
        text = """---
slug: 2026-05-20-typo-fix
title: Fix typo in login error message
status: fixed
---
## Body
Minor typo fix.
"""
        rec = dae_fix.parse_fix(text)
        self.assertEqual(rec["slug"], "2026-05-20-typo-fix")
        self.assertEqual(rec["title"], "Fix typo in login error message")
        self.assertEqual(rec["status"], "fixed")
        self.assertIsNone(rec["source"])
        self.assertIsNone(rec["severity"])
        self.assertIsNone(rec["blocks_user"])
        self.assertIsNone(rec["workaround"])
        self.assertIsNone(rec["repro"])
        self.assertEqual(rec["feature_refs"], [])
        self.assertEqual(rec["fix_commits"], [])
        self.assertEqual(rec["gap_analysis"], [])
        self.assertEqual(rec["followups"], [])

    def test_parse_fix_tolerates_malformed_frontmatter(self):
        """Scenario 3: malformed frontmatter returns dict with defaults, does not raise"""
        text = """---
this is not valid yaml: [ unclosed bracket
slug: 2026-05-20-test
---
Body
"""
        # Should not raise; should return dict with defaults
        rec = dae_fix.parse_fix(text)
        # Parsing may fail, but defaults should be present
        self.assertIsInstance(rec, dict)
        self.assertIn("slug", rec)
        self.assertIn("feature_refs", rec)

    def test_parse_fix_no_frontmatter(self):
        """Ensure parse_fix handles missing frontmatter gracefully"""
        text = """
Just a markdown file with no frontmatter.
"""
        rec = dae_fix.parse_fix(text)
        self.assertIsNone(rec["slug"])
        self.assertIsNone(rec["title"])
        self.assertEqual(rec["feature_refs"], [])


class TestValidateFix(unittest.TestCase):
    """Tests for validate_fix function"""

    def test_validate_fix_well_formed_returns_empty(self):
        """Scenario 4: well-formed artifact returns []"""
        rec = {
            "slug": "2026-05-15-auth-race-condition",
            "title": "Authentication race condition",
            "severity": "critical",
            "status": "verified",
            "blocks_user": True,
            "workaround": "refresh the page",
            "gap_analysis": [{"category": "architecture_violation"}],
        }
        errors = dae_fix.validate_fix(rec)
        self.assertEqual(errors, [])

    def test_validate_fix_rejects_bad_slug_no_date(self):
        """Scenario 5a: rejects bad slug (no date prefix)"""
        rec = {
            "slug": "auth-race-condition",
            "title": "Some fix",
            "gap_analysis": [],
        }
        errors = dae_fix.validate_fix(rec)
        self.assertTrue(any("slug must match pattern" in e for e in errors))

    def test_validate_fix_rejects_missing_slug(self):
        """Scenario 5b: rejects missing slug"""
        rec = {
            "title": "Some fix",
            "gap_analysis": [],
        }
        errors = dae_fix.validate_fix(rec)
        self.assertTrue(any("slug is required" in e for e in errors))

    def test_validate_fix_rejects_bad_severity(self):
        """Scenario 5c: rejects bad severity"""
        rec = {
            "slug": "2026-05-15-test",
            "title": "Some fix",
            "severity": "mega-critical",
            "gap_analysis": [],
        }
        errors = dae_fix.validate_fix(rec)
        self.assertTrue(any("severity" in e and "must be one of" in e for e in errors))

    def test_validate_fix_rejects_bad_status(self):
        """Scenario 5d: rejects bad status"""
        rec = {
            "slug": "2026-05-15-test",
            "title": "Some fix",
            "status": "not-a-real-status",
            "gap_analysis": [],
        }
        errors = dae_fix.validate_fix(rec)
        self.assertTrue(any("status" in e and "must be one of" in e for e in errors))

    def test_validate_fix_rejects_bad_gap_category(self):
        """Scenario 5e: rejects bad gap_analysis category"""
        rec = {
            "slug": "2026-05-15-test",
            "title": "Some fix",
            "gap_analysis": [{"category": "invalid_category"}],
        }
        errors = dae_fix.validate_fix(rec)
        self.assertTrue(any("category" in e and "must be one of" in e for e in errors))

    def test_validate_fix_missing_title(self):
        """Rejects missing title"""
        rec = {
            "slug": "2026-05-15-test",
            "title": None,
        }
        errors = dae_fix.validate_fix(rec)
        self.assertTrue(any("title" in e for e in errors))

    def _closed_rec(self):
        """Build a well-formed rec at status: closed (overridable per-test)."""
        return {
            "slug": "2026-05-15-test",
            "title": "test",
            "status": "closed",
            "handoff_path": ".engineer/handoffs/2026-05-15-test-close.md",
            "feature_refs": ["015-thing"],
            "pin_confirmation": {
                "feature_refs": [
                    {"feature": "015-thing", "red_run": {"result": "red"}}
                ]
            },
            "harden_results": {
                "bug_line_mutation_confirmed": True,
                "mutation_score": "80%",
                "arch_check": "ok",
            },
            "gap_analysis": [{"category": "none"}],
            "followups": [],
        }

    def test_validate_fix_closed_happy_path(self):
        rec = self._closed_rec()
        errors = dae_fix.validate_fix(rec)
        self.assertEqual(errors, [])

    def test_validate_fix_closed_rejects_missing_handoff_path(self):
        rec = self._closed_rec()
        rec["handoff_path"] = None
        errors = dae_fix.validate_fix(rec)
        self.assertTrue(any("handoff_path" in e for e in errors))

    def test_validate_fix_closed_rejects_missing_arch_check(self):
        rec = self._closed_rec()
        del rec["harden_results"]["arch_check"]
        errors = dae_fix.validate_fix(rec)
        self.assertTrue(any("arch_check" in e for e in errors))

    def test_validate_fix_closed_rejects_missing_bug_line_mutation(self):
        rec = self._closed_rec()
        rec["harden_results"]["bug_line_mutation_confirmed"] = False
        errors = dae_fix.validate_fix(rec)
        self.assertTrue(any("bug_line_mutation_confirmed" in e for e in errors))

    def test_validate_fix_closed_rejects_empty_gap_analysis(self):
        rec = self._closed_rec()
        rec["gap_analysis"] = []
        errors = dae_fix.validate_fix(rec)
        self.assertTrue(any("gap_analysis" in e for e in errors))

    def test_validate_fix_closed_rejects_pin_not_red(self):
        rec = self._closed_rec()
        rec["pin_confirmation"]["feature_refs"][0]["red_run"]["result"] = "green"
        errors = dae_fix.validate_fix(rec)
        self.assertTrue(any("pin_confirmation" in e for e in errors))

    def test_validate_fix_non_closed_status_skips_close_gate(self):
        """status: hardened doesn't require handoff_path yet."""
        rec = self._closed_rec()
        rec["status"] = "hardened"
        rec["handoff_path"] = None
        errors = dae_fix.validate_fix(rec)
        # No handoff_path error because status != closed
        self.assertFalse(any("handoff_path" in e for e in errors))


class TestIsPinConfirmed(unittest.TestCase):
    """Tests for is_pin_confirmed function"""

    def test_pin_confirmed_all_features_have_red(self):
        """Scenario 6: True when all feature_refs have RED-confirmed pin entries"""
        rec = {
            "feature_refs": ["auth-module", "session-mgmt"],
            "pin_confirmation": {
                "feature_refs": [
                    {"feature": "auth-module", "red_run": {"result": "red"}},
                    {"feature": "session-mgmt", "red_run": {"result": "red"}},
                ]
            },
        }
        self.assertTrue(dae_fix.is_pin_confirmed(rec))

    def test_pin_confirmed_missing_pin_entry(self):
        """Scenario 7: False when one feature_ref is missing its pin entry"""
        rec = {
            "feature_refs": ["auth-module", "session-mgmt"],
            "pin_confirmation": {
                "feature_refs": [
                    {"feature": "auth-module", "red_run": {"result": "red"}},
                ]
            },
        }
        self.assertFalse(dae_fix.is_pin_confirmed(rec))

    def test_pin_confirmed_green_result(self):
        """Scenario 8: False when a pin entry's result is 'green' (spec didn't pin the bug)"""
        rec = {
            "feature_refs": ["auth-module"],
            "pin_confirmation": {
                "feature_refs": [
                    {"feature": "auth-module", "red_run": {"result": "green"}},
                ]
            },
        }
        self.assertFalse(dae_fix.is_pin_confirmed(rec))

    def test_pin_confirmed_empty_feature_refs(self):
        """When feature_refs is empty, return True (v1: loose-fix not validated)"""
        rec = {
            "feature_refs": [],
            "pin_confirmation": None,
        }
        self.assertTrue(dae_fix.is_pin_confirmed(rec))


class TestIsHardened(unittest.TestCase):
    """Tests for is_hardened function"""

    def test_hardened_true_case(self):
        """Scenario 9a: True case"""
        rec = {
            "harden_results": {
                "bug_line_mutation_confirmed": True,
                "mutation_score": 0.95,
                "arch_check": "passed",
            }
        }
        self.assertTrue(dae_fix.is_hardened(rec))

    def test_hardened_false_case_missing_confirmation(self):
        """Scenario 9b: False when bug_line_mutation_confirmed is missing"""
        rec = {
            "harden_results": {
                "mutation_score": 0.95,
                "arch_check": "passed",
            }
        }
        self.assertFalse(dae_fix.is_hardened(rec))

    def test_hardened_false_case_missing_score(self):
        """False when mutation_score is missing"""
        rec = {
            "harden_results": {
                "bug_line_mutation_confirmed": True,
                "arch_check": "passed",
            }
        }
        self.assertFalse(dae_fix.is_hardened(rec))

    def test_hardened_false_case_missing_arch_check(self):
        """False when arch_check is missing"""
        rec = {
            "harden_results": {
                "bug_line_mutation_confirmed": True,
                "mutation_score": 0.95,
            }
        }
        self.assertFalse(dae_fix.is_hardened(rec))


class TestBlockerCategories(unittest.TestCase):
    """Tests for blocker_categories function"""

    def test_blocker_categories_architecture_violation_always_blocker(self):
        """Scenario 10: architecture_violation is ALWAYS a blocker"""
        rec = {
            "blocks_user": False,
            "workaround": None,
            "gap_analysis": [
                {"category": "architecture_violation"},
                {"category": "missing_ac"},
            ],
        }
        blockers = dae_fix.blocker_categories(rec)
        self.assertIn("architecture_violation", blockers)
        # missing_ac should NOT be a blocker in this case
        self.assertNotIn("missing_ac", blockers)

    def test_blocker_categories_all_when_fully_blocked(self):
        """Scenario 11: when blocks_user=true AND workaround='none', all categories are blockers"""
        rec = {
            "blocks_user": True,
            "workaround": "none",
            "gap_analysis": [
                {"category": "architecture_violation"},
                {"category": "missing_ac"},
                {"category": "unspecced_ac"},
            ],
        }
        blockers = dae_fix.blocker_categories(rec)
        self.assertEqual(
            set(blockers),
            {"architecture_violation", "missing_ac", "unspecced_ac"}
        )

    def test_blocker_categories_with_workaround(self):
        """Scenario 12: when blocks_user=true BUT has workaround, only arch_violation is blocker"""
        rec = {
            "blocks_user": True,
            "workaround": "restart the app",
            "gap_analysis": [
                {"category": "architecture_violation"},
                {"category": "missing_ac"},
                {"category": "inadequate_verification"},
            ],
        }
        blockers = dae_fix.blocker_categories(rec)
        self.assertEqual(blockers, ["architecture_violation"])


class TestHasUnresolvedBlockers(unittest.TestCase):
    """Tests for has_unresolved_blockers function"""

    def test_has_unresolved_blockers_true_case(self):
        """Scenario 13: True if any blocker-category followup has status != 'applied'"""
        rec = {
            "blocks_user": True,
            "workaround": "none",
            "gap_analysis": [
                {"category": "architecture_violation"},
                {"category": "missing_ac"},
            ],
            "followups": [
                {"category": "architecture_violation", "status": "open"},
                {"category": "missing_ac", "status": "applied"},
            ],
        }
        self.assertTrue(dae_fix.has_unresolved_blockers(rec))

    def test_has_unresolved_blockers_false_case(self):
        """Scenario 14: False if all blocker followups have status='applied'"""
        rec = {
            "blocks_user": True,
            "workaround": "none",
            "gap_analysis": [
                {"category": "architecture_violation"},
                {"category": "missing_ac"},
            ],
            "followups": [
                {"category": "architecture_violation", "status": "applied"},
                {"category": "missing_ac", "status": "applied"},
            ],
        }
        self.assertFalse(dae_fix.has_unresolved_blockers(rec))

    def test_has_unresolved_blockers_missing_followup(self):
        """If blocker category has no followup at all, it's unresolved"""
        rec = {
            "blocks_user": True,
            "workaround": "none",
            "gap_analysis": [
                {"category": "architecture_violation"},
                {"category": "missing_ac"},
            ],
            "followups": [
                {"category": "missing_ac", "status": "applied"},
            ],
        }
        self.assertTrue(dae_fix.has_unresolved_blockers(rec))


class TestCloseReady(unittest.TestCase):
    """Tests for close_ready function"""

    def test_close_ready_happy_path(self):
        """Scenario 15: happy path — all gates green → True"""
        rec = {
            "status": "gap-analyzed",
            "feature_refs": ["auth-module"],
            "pin_confirmation": {
                "feature_refs": [
                    {"feature": "auth-module", "red_run": {"result": "red"}},
                ]
            },
            "harden_results": {
                "bug_line_mutation_confirmed": True,
                "mutation_score": 0.95,
                "arch_check": "passed",
            },
            "gap_analysis": [
                {"category": "none", "finding": "clean fix"},
            ],
            "blocks_user": False,
            "workaround": None,
            "followups": [],
        }
        self.assertTrue(dae_fix.close_ready(rec))

    def test_close_ready_rejects_early_status(self):
        """Scenario 16a: rejects status too early"""
        rec = {
            "status": "pinned",  # too early
            "feature_refs": ["auth-module"],
            "pin_confirmation": {
                "feature_refs": [
                    {"feature": "auth-module", "red_run": {"result": "red"}},
                ]
            },
            "harden_results": {
                "bug_line_mutation_confirmed": True,
                "mutation_score": 0.95,
                "arch_check": "passed",
            },
            "gap_analysis": [{"category": "none"}],
            "followups": [],
        }
        self.assertFalse(dae_fix.close_ready(rec))

    def test_close_ready_rejects_pin_missing(self):
        """Scenario 16b: rejects pin missing"""
        rec = {
            "status": "gap-analyzed",
            "feature_refs": ["auth-module"],
            "pin_confirmation": None,
            "harden_results": {
                "bug_line_mutation_confirmed": True,
                "mutation_score": 0.95,
                "arch_check": "passed",
            },
            "gap_analysis": [{"category": "none"}],
            "followups": [],
        }
        self.assertFalse(dae_fix.close_ready(rec))

    def test_close_ready_rejects_not_hardened(self):
        """Scenario 16c: rejects not hardened"""
        rec = {
            "status": "gap-analyzed",
            "feature_refs": ["auth-module"],
            "pin_confirmation": {
                "feature_refs": [
                    {"feature": "auth-module", "red_run": {"result": "red"}},
                ]
            },
            "harden_results": {
                "bug_line_mutation_confirmed": False,
            },
            "gap_analysis": [{"category": "none"}],
            "followups": [],
        }
        self.assertFalse(dae_fix.close_ready(rec))

    def test_close_ready_rejects_empty_gap_analysis(self):
        """Scenario 16d: rejects gap_analysis empty"""
        rec = {
            "status": "gap-analyzed",
            "feature_refs": ["auth-module"],
            "pin_confirmation": {
                "feature_refs": [
                    {"feature": "auth-module", "red_run": {"result": "red"}},
                ]
            },
            "harden_results": {
                "bug_line_mutation_confirmed": True,
                "mutation_score": 0.95,
                "arch_check": "passed",
            },
            "gap_analysis": [],  # empty!
            "followups": [],
        }
        self.assertFalse(dae_fix.close_ready(rec))

    def test_close_ready_rejects_unresolved_blocker(self):
        """Scenario 16e: rejects unresolved blocker"""
        rec = {
            "status": "gap-analyzed",
            "feature_refs": ["auth-module"],
            "pin_confirmation": {
                "feature_refs": [
                    {"feature": "auth-module", "red_run": {"result": "red"}},
                ]
            },
            "harden_results": {
                "bug_line_mutation_confirmed": True,
                "mutation_score": 0.95,
                "arch_check": "passed",
            },
            "gap_analysis": [
                {"category": "architecture_violation"},
            ],
            "blocks_user": False,
            "workaround": None,
            "followups": [
                {"category": "architecture_violation", "status": "open"},
            ],
        }
        self.assertFalse(dae_fix.close_ready(rec))

    def test_close_ready_trivial_fix(self):
        """Scenario 17: accepts trivial fix with gap_analysis: [{category: 'none', ...}]"""
        rec = {
            "status": "gap-analyzed",
            "feature_refs": [],
            "pin_confirmation": None,
            "harden_results": {
                "bug_line_mutation_confirmed": True,
                "mutation_score": 0.95,
                "arch_check": "passed",
            },
            "gap_analysis": [
                {"category": "none", "finding": "trivial typo"}
            ],
            "blocks_user": False,
            "workaround": None,
            "followups": [],
        }
        self.assertTrue(dae_fix.close_ready(rec))


class TestListOpenFixes(unittest.TestCase):
    """Tests for list_open_fixes function"""

    def test_list_open_fixes_scans_and_excludes_closed(self):
        """Scenario 18: scans temp dir, returns open fixes; excludes closed ones"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fixes_dir = os.path.join(tmpdir, ".engineer", "fixes")
            os.makedirs(fixes_dir, exist_ok=True)

            # Open fix
            open_fix = """---
slug: 2026-05-15-open-bug
title: Open bug fix
severity: high
blocks_user: true
workaround: none
status: investigating
feature_refs:
  - feature-a
---
Body
"""
            with open(os.path.join(fixes_dir, "2026-05-15-open-bug.md"), "w") as f:
                f.write(open_fix)

            # Closed fix (should be excluded)
            closed_fix = """---
slug: 2026-05-10-closed-bug
title: Closed bug fix
status: closed
---
Body
"""
            with open(os.path.join(fixes_dir, "2026-05-10-closed-bug.md"), "w") as f:
                f.write(closed_fix)

            fixes = dae_fix.list_open_fixes(tmpdir)
            self.assertEqual(len(fixes), 1)
            self.assertEqual(fixes[0]["slug"], "2026-05-15-open-bug")
            self.assertEqual(fixes[0]["status"], "investigating")

    def test_list_open_fixes_skips_malformed_with_warning(self):
        """Scenario 18: skips malformed file with warning (to stderr)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fixes_dir = os.path.join(tmpdir, ".engineer", "fixes")
            os.makedirs(fixes_dir, exist_ok=True)

            # Malformed fix (no slug)
            malformed = """---
title: No slug here
status: investigating
---
Body
"""
            with open(os.path.join(fixes_dir, "malformed.md"), "w") as f:
                f.write(malformed)

            # Good fix
            good_fix = """---
slug: 2026-05-15-good
title: Good fix
status: investigating
---
Body
"""
            with open(os.path.join(fixes_dir, "2026-05-15-good.md"), "w") as f:
                f.write(good_fix)

            fixes = dae_fix.list_open_fixes(tmpdir)
            # Should return only the good fix
            self.assertEqual(len(fixes), 1)
            self.assertEqual(fixes[0]["slug"], "2026-05-15-good")

    def test_list_open_fixes_empty_dir(self):
        """When fixes dir doesn't exist, return empty list"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fixes = dae_fix.list_open_fixes(tmpdir)
            self.assertEqual(fixes, [])


class TestRenderFixClosureEntry(unittest.TestCase):
    """Tests for render_fix_closure_entry function"""

    def test_render_fix_closure_entry_full_happy_path(self):
        """Scenario 19a: full happy path — all fields present"""
        rec = {
            "slug": "2026-05-25-stale-cache-on-401",
            "severity": "high",
            "blocks_user": True,
            "workaround": "none",
        }
        followups_summary = {"advisory": 2, "blocker_applied": 1}
        result = dae_fix.render_fix_closure_entry(rec, followups_summary)

        self.assertIn("## Fix applied — 2026-05-25-stale-cache-on-401", result)
        self.assertIn("Severity: high", result)
        self.assertIn("user-blocking: yes", result)
        self.assertIn("workaround: none", result)
        self.assertIn("2 advisory, 1 blocker applied inline", result)
        self.assertIn("`.engineer/fixes/2026-05-25-stale-cache-on-401.md`", result)
        self.assertTrue(result.endswith("\n"))

    def test_render_fix_closure_entry_blocks_user_false(self):
        """Scenario 19b: blocks_user False — reads 'user-blocking: no', no workaround"""
        rec = {
            "slug": "2026-05-20-minor-glitch",
            "severity": "low",
            "blocks_user": False,
            "workaround": "restart the app",
        }
        result = dae_fix.render_fix_closure_entry(rec, {"advisory": 0, "blocker_applied": 0})

        self.assertIn("user-blocking: no", result)
        self.assertNotIn("workaround", result)

    def test_render_fix_closure_entry_no_followups_summary(self):
        """Scenario 19c: followups_summary None — followups bullet absent"""
        rec = {
            "slug": "2026-05-22-null-ptr",
            "severity": "medium",
            "blocks_user": False,
        }
        result = dae_fix.render_fix_closure_entry(rec, None)

        self.assertNotIn("Followups", result)
        self.assertIn("## Fix applied — 2026-05-22-null-ptr", result)
        self.assertIn("`.engineer/fixes/2026-05-22-null-ptr.md`", result)

    def test_render_fix_closure_entry_minimal_artifact(self):
        """Scenario 19d: minimal artifact (only slug + severity) — renders without crashing"""
        rec = {
            "slug": "2026-01-01-minimal",
            "severity": "critical",
            "blocks_user": None,
            "workaround": None,
        }
        result = dae_fix.render_fix_closure_entry(rec)

        self.assertIn("## Fix applied — 2026-01-01-minimal", result)
        self.assertIn("Severity: critical", result)
        self.assertIn("`.engineer/fixes/2026-01-01-minimal.md`", result)
        self.assertTrue(result.endswith("\n"))


class TestRenderConsolidationEntries(unittest.TestCase):
    """Tests for render_consolidation_entries function"""

    def test_happy_path_two_advisory_one_blocker(self):
        """Scenario: 2 advisory + 1 blocker → 2 entries (blocker excluded)"""
        rec = {
            "slug": "2026-05-25-stale-cache-on-401",
            "blocks_user": False,
            "workaround": None,
            "gap_analysis": [
                {
                    "category": "missing_ac",
                    "finding": "AC missing for stale cache scenario",
                    "followup": {
                        "kind": "amend_ac",
                        "target": "features/042-auth-session/acceptance-criteria.md",
                        "action": "Add AC #4b for stale cache",
                    },
                },
                {
                    "category": "inadequate_verification",
                    "finding": "Test skipped in CI",
                    "followup": {
                        "kind": "add_verification",
                        "target": "features/058-cache-layer/specs/cache.spec.md",
                        "action": "Add scenario cache invalidation on 401",
                    },
                },
                {
                    "category": "architecture_violation",
                    "finding": "Cache layer reaches into auth client directly",
                    "followup": {
                        "kind": "tighten_arch_check",
                        "target": "charter.md",
                        "action": "Forbid cross-layer reach",
                    },
                },
            ],
        }
        entries = dae_fix.render_consolidation_entries(rec)
        self.assertEqual(len(entries), 2)
        # blocker (architecture_violation) must NOT appear
        self.assertFalse(any("architecture_violation" in e for e in entries))
        # advisory categories must appear
        self.assertTrue(any("missing_ac" in e for e in entries))
        self.assertTrue(any("inadequate_verification" in e for e in entries))
        # slug must appear in each entry
        for entry in entries:
            self.assertIn("2026-05-25-stale-cache-on-401", entry)
        # entry format: starts with "- [ ] "
        for entry in entries:
            self.assertTrue(entry.startswith("- [ ] "))

    def test_all_blockers_returns_empty(self):
        """Scenario: all findings are blockers → empty list"""
        rec = {
            "slug": "2026-05-25-all-blockers",
            "blocks_user": True,
            "workaround": "none",
            "gap_analysis": [
                {
                    "category": "missing_ac",
                    "followup": {"target": "features/foo/acs.md", "action": "Add AC"},
                },
                {
                    "category": "architecture_violation",
                    "followup": {"target": "charter.md", "action": "Tighten arch"},
                },
            ],
        }
        # blocks_user=True + workaround=none promotes all to blockers
        entries = dae_fix.render_consolidation_entries(rec)
        self.assertEqual(entries, [])

    def test_no_gap_analysis_returns_empty(self):
        """Scenario: no gap_analysis → empty list"""
        rec = {
            "slug": "2026-05-25-no-gap",
            "blocks_user": False,
            "workaround": None,
            "gap_analysis": [],
        }
        entries = dae_fix.render_consolidation_entries(rec)
        self.assertEqual(entries, [])

    def test_missing_followup_details_uses_placeholders(self):
        """Scenario: missing followup sub-fields → placeholders used gracefully"""
        rec = {
            "slug": "2026-05-25-sparse-followup",
            "blocks_user": False,
            "workaround": None,
            "gap_analysis": [
                {
                    "category": "missing_ac",
                    # no followup key at all
                },
            ],
        }
        entries = dae_fix.render_consolidation_entries(rec)
        self.assertEqual(len(entries), 1)
        self.assertIn("missing_ac", entries[0])
        self.assertIn("2026-05-25-sparse-followup", entries[0])
        # Should not raise; should use placeholder strings
        self.assertIn("Review finding", entries[0])
        self.assertIn("unknown", entries[0])

    def test_user_blocking_no_workaround_promotes_all_to_blockers(self):
        """Scenario: blocks_user=True + workaround=none → even advisory categories become blockers → empty list"""
        rec = {
            "slug": "2026-05-25-blocking-no-workaround",
            "blocks_user": True,
            "workaround": "none",
            "gap_analysis": [
                {
                    "category": "missing_ac",
                    "followup": {
                        "target": "features/042-auth/acs.md",
                        "action": "Add missing AC",
                    },
                },
                {
                    "category": "inadequate_verification",
                    "followup": {
                        "target": "features/042-auth/specs/auth.spec.md",
                        "action": "Add verification scenario",
                    },
                },
            ],
        }
        entries = dae_fix.render_consolidation_entries(rec)
        self.assertEqual(entries, [])

    def test_category_none_excluded(self):
        """category: 'none' = 'explicitly nothing to learn' → no consolidation entry"""
        rec = {
            "slug": "2026-05-25-trivial-typo",
            "blocks_user": False,
            "workaround": "",
            "gap_analysis": [
                {"category": "none", "finding": "trivial typo, no methodology gap"},
            ],
        }
        entries = dae_fix.render_consolidation_entries(rec)
        self.assertEqual(entries, [])


class TestAttemptPremiseGate(unittest.TestCase):
    """A 3rd attempt on a gate after 2 failures needs a tested, unfalsified premise."""

    HEAD = "---\nslug: 2026-05-25-x\ntitle: X\nattempts:\n"
    FAIL = "  - gate: spec\n    result: fail\n"
    PREMISE = ("    premise:\n      belief: b\n      observation: o\n"
               "      command: c\n      output: out\n      falsified: %s\n")

    def errors(self, body):
        return dae_fix.attempt_errors(dae_fix.parse_fix(self.HEAD + body + "---\n"))

    def test_gate(self):
        third = "  - gate: spec\n    result: pending\n"
        self.assertEqual(self.errors(self.FAIL * 2), [])
        self.assertEqual(self.errors(self.FAIL * 2 + "  - gate: other\n    result: pending\n"), [])
        self.assertIn("requires a premise", self.errors(self.FAIL * 2 + third)[0])
        self.assertEqual(self.errors(self.FAIL * 2 + third + self.PREMISE % "false"), [])
        self.assertIn("falsified", self.errors(self.FAIL * 2 + third + self.PREMISE % "true")[0])
        # 4th attempt needs its own premise, not the 3rd's
        self.assertTrue(self.errors(self.FAIL * 2 + third + self.PREMISE % "false" + third))
        # validate_fix surfaces it
        rec = dae_fix.parse_fix(self.HEAD + self.FAIL * 3 + "---\n")
        self.assertTrue(any("premise" in e for e in dae_fix.validate_fix(rec)))


if __name__ == "__main__":
    unittest.main()
