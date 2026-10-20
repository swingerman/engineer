#!/usr/bin/env python3
"""Tests for dae_handoff — handoff completeness audit.

Run: python3 -m unittest test_dae_handoff -v
"""
import os
import shutil
import tempfile
import unittest

import dae_handoff as dh

HANDOFF_COMPLETE = """---
skill: discover-acs
agent_id: subagent-1
checkpoint: 2
artifacts:
  - features/001-x/acs.md
exit_criteria:
  - criterion: "acs.md exists"
    met: true
    evidence: "written"
  - criterion: "human approved"
    met: true
    evidence: "approved in review"
status: complete
---

# discover-acs — handoff summary
"""

HANDOFF_UNMET = HANDOFF_COMPLETE.replace(
    'met: true\n    evidence: "approved in review"',
    'met: false\n    evidence: "awaiting review"')

HANDOFF_INTERRUPTED = HANDOFF_COMPLETE.replace(
    "status: complete", "status: interrupted")

HANDOFF_NULL_CP = HANDOFF_COMPLETE.replace("checkpoint: 2", "checkpoint: null")


class TestParseHandoff(unittest.TestCase):
    def test_scalar_fields(self):
        rec = dh.parse_handoff(HANDOFF_COMPLETE)
        self.assertEqual(rec["checkpoint"], 2)
        self.assertEqual(rec["status"], "complete")

    def test_null_checkpoint(self):
        rec = dh.parse_handoff(HANDOFF_NULL_CP)
        self.assertIsNone(rec["checkpoint"])

    def test_exit_criteria_all_met(self):
        rec = dh.parse_handoff(HANDOFF_COMPLETE)
        self.assertEqual(len(rec["exit_criteria"]), 2)
        self.assertTrue(all(c["met"] for c in rec["exit_criteria"]))

    def test_exit_criteria_one_unmet(self):
        rec = dh.parse_handoff(HANDOFF_UNMET)
        self.assertFalse(all(c["met"] for c in rec["exit_criteria"]))


PROGRESS = """# Feature 001: x — Progress

> ▶ CP2 ACs — 2/2 criteria met | NEXT: spec | BLOCKED: none

## Checkpoints
| # | Stage | Status | Artifact |
|---|-------|--------|----------|
| 1.5 | Ready | ✅ done | feature.md |
| 2 | ACs | ✅ done | acs.md |
| 3 | Spec | 🟡 in progress | — |
| 4 | Plan | ⏳ pending | — |
"""


class TestReadProgress(unittest.TestCase):
    def test_done_and_pending(self):
        cps = dh.read_progress(PROGRESS)
        self.assertTrue(cps[1.5])
        self.assertTrue(cps[2])
        self.assertFalse(cps[3])
        self.assertFalse(cps[4])

    def test_header_and_separator_skipped(self):
        cps = dh.read_progress(PROGRESS)
        self.assertEqual(set(cps), {1.5, 2, 3, 4})


class TestRecComplete(unittest.TestCase):
    def test_complete(self):
        self.assertTrue(dh._rec_complete(dh.parse_handoff(HANDOFF_COMPLETE)))

    def test_unmet_criterion_blocks(self):
        self.assertFalse(dh._rec_complete(dh.parse_handoff(HANDOFF_UNMET)))

    def test_interrupted_blocks(self):
        self.assertFalse(dh._rec_complete(dh.parse_handoff(HANDOFF_INTERRUPTED)))

    def test_no_criteria_complete_on_status(self):
        legacy = """---
skill: x
checkpoint: 4
status: complete
---
"""
        self.assertTrue(dh._rec_complete(dh.parse_handoff(legacy)))


def _make_feature(handoffs, progress):
    """Create a temp feature dir; return its path. Caller cleans up."""
    d = tempfile.mkdtemp()
    hd = os.path.join(d, "handoffs")
    os.makedirs(hd)
    for i, text in enumerate(handoffs):
        with open(os.path.join(hd, "h%d.md" % i), "w", encoding="utf-8") as f:
            f.write(text)
    with open(os.path.join(d, "progress.md"), "w", encoding="utf-8") as f:
        f.write(progress)
    return d


class TestAudit(unittest.TestCase):
    def test_clean(self):
        # progress claims 2 done; handoff covers 2 (1.5 is human/feature-init)
        prog = PROGRESS.replace("| 1.5 | Ready | ✅ done", "| 1.5 | Ready | ⏳ pending")
        d = _make_feature([HANDOFF_COMPLETE], prog)
        self.addCleanup(shutil.rmtree, d)
        res = dh.audit(d)
        self.assertEqual(res["gaps"], [])
        self.assertEqual(res["latest_complete"], 2)

    def test_gap_detected(self):
        # progress claims 2 done but the only handoff has an unmet criterion
        d = _make_feature([HANDOFF_UNMET], PROGRESS)
        self.addCleanup(shutil.rmtree, d)
        res = dh.audit(d)
        self.assertIn(2, res["gaps"])


class TestGate(unittest.TestCase):
    def test_through_passes(self):
        prog = PROGRESS.replace("| 1.5 | Ready | ✅ done", "| 1.5 | Ready | ⏳ pending")
        d = _make_feature([HANDOFF_COMPLETE], prog)
        self.addCleanup(shutil.rmtree, d)
        ok, _ = dh.gate(d, through=2)
        self.assertTrue(ok)

    def test_through_fails_when_incomplete(self):
        prog = PROGRESS.replace("| 1.5 | Ready | ✅ done", "| 1.5 | Ready | ⏳ pending")
        d = _make_feature([HANDOFF_COMPLETE], prog)
        self.addCleanup(shutil.rmtree, d)
        ok, msg = dh.gate(d, through=3)
        self.assertFalse(ok)
        self.assertIn("3", msg)


class BlockScalarEvidenceTests(unittest.TestCase):
    def test_six_criteria_with_bullet_evidence_blocks_all_count(self):
        # Reproducer for the image-titler CP8 handoff bug: each criterion's
        # `evidence: |` block contains `- ` bullets. The parser must count
        # exactly six criteria, all met: true.
        text = """---
skill: atdd-mutate
checkpoint: 8
status: complete
exit_criteria:
  - criterion: "Mutation testing tooling installed"
    verified_by: tool
    met: true
    evidence: |
      - jscpd 4.x installed via npm
      - configured against src/
  - criterion: "Two test streams green before mutating"
    verified_by: tool
    met: true
    evidence: |
      - acceptance: 14/14 passing
      - unit: 47/47 passing
  - criterion: "Mutation score >= 70%"
    verified_by: tool
    met: true
    evidence: |
      - score: 88%
      - killed: 132 / survived: 18
  - criterion: "Surviving mutants triaged"
    verified_by: human
    met: true
    evidence: |
      - 12 equivalent (no behavior change)
      - 6 documented in handoff
  - criterion: "Mutation report written"
    verified_by: tool
    met: true
    evidence: |
      - features/015/handoffs/2026-05-22-mutate.md
  - criterion: "agent_id differs from implementer"
    verified_by: tool
    met: true
    evidence: |
      - implementer: aXX; this run: bYY
---

body text
"""
        rec = dh.parse_handoff(text)
        self.assertEqual(rec["checkpoint"], 8)
        self.assertEqual(rec["status"], "complete")
        self.assertEqual(len(rec["exit_criteria"]), 6,
                         "expected exactly 6 criteria; got %r" % (rec["exit_criteria"],))
        self.assertTrue(all(c["met"] is True for c in rec["exit_criteria"]))
        self.assertTrue(dh._rec_complete(rec))

    def test_list_valued_evidence_does_not_create_phantom_criteria(self):
        # Variant: evidence as a real nested list (no | block scalar). Should
        # also parse as a single criterion with a list-valued evidence.
        text = """---
checkpoint: 7
status: complete
exit_criteria:
  - criterion: "first"
    met: true
    evidence:
      - bullet a
      - bullet b
---
body
"""
        rec = dh.parse_handoff(text)
        self.assertEqual(len(rec["exit_criteria"]), 1)
        self.assertTrue(rec["exit_criteria"][0]["met"])


def _handoff(skill, agent_id, checkpoint, met=True):
    """Build a minimal handoff text with given skill/agent_id/checkpoint."""
    met_str = "true" if met is True else "false" if met is False else "partial"
    return ("---\n"
            "skill: %s\n"
            "agent_id: %s\n"
            "checkpoint: %s\n"
            "exit_criteria:\n"
            "  - criterion: \"work done\"\n"
            "    met: %s\n"
            "    evidence: \"yes\"\n"
            "status: complete\n"
            "---\n") % (skill, agent_id, checkpoint, met_str)


class MetPartialTests(unittest.TestCase):
    def test_partial_parsed_distinct_from_true(self):
        text = _handoff("verify", "subagent-7", 7, met="partial")
        rec = dh.parse_handoff(text)
        self.assertEqual(rec["exit_criteria"][0]["met"], "partial")

    def test_partial_blocks_completeness(self):
        text = _handoff("verify", "subagent-7", 7, met="partial")
        self.assertFalse(dh._rec_complete(dh.parse_handoff(text)))


class IndependenceViolationTests(unittest.TestCase):
    def test_no_violation_when_agents_differ(self):
        d = _make_feature([
            _handoff("atdd", "subagent-A", 5),
            _handoff("verify", "subagent-B", 7),
        ], PROGRESS)
        self.addCleanup(shutil.rmtree, d)
        self.assertEqual(dh.independence_violations(d), [])

    def test_violation_when_verifier_is_implementer(self):
        d = _make_feature([
            _handoff("atdd", "subagent-A", 5),
            _handoff("verify", "subagent-A", 7),
        ], PROGRESS)
        self.addCleanup(shutil.rmtree, d)
        v = dh.independence_violations(d)
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0][1], "subagent-A")
        self.assertEqual(v[0][2], 7)

    def test_violation_blocks_gate(self):
        # Use an empty progress.md so the only failure mode is independence.
        d = _make_feature([
            _handoff("atdd", "main", 5),
            _handoff("verify", "main", 7),
        ], "# stub\n")
        self.addCleanup(shutil.rmtree, d)
        ok, msg = dh.gate(d, through=7)
        self.assertFalse(ok)
        self.assertIn("Principle 7", msg)

    def test_violation_when_verifier_is_refiner(self):
        d = _make_feature([
            _handoff("atdd", "subagent-A", 5),
            _handoff("refine", "subagent-B", 6),
            _handoff("verify", "subagent-B", 7),
        ], PROGRESS)
        self.addCleanup(shutil.rmtree, d)
        self.assertEqual([v[2:] for v in dh.independence_violations(d)], [(7, 6)])

    def test_no_cp5_no_violation(self):
        # If there's no implement handoff at CP5, independence is vacuous.
        d = _make_feature([
            _handoff("verify", "subagent-X", 7),
        ], PROGRESS)
        self.addCleanup(shutil.rmtree, d)
        self.assertEqual(dh.independence_violations(d), [])

    def test_missing_agent_id_skips_comparison(self):
        # If CP5 agent_id is missing, no comparison can be made.
        no_agent_cp5 = ("---\n"
                        "skill: atdd\n"
                        "checkpoint: 5\n"
                        "exit_criteria:\n"
                        "  - criterion: \"x\"\n"
                        "    met: true\n"
                        "status: complete\n"
                        "---\n")
        d = _make_feature([
            no_agent_cp5,
            _handoff("verify", "main", 7),
        ], PROGRESS)
        self.addCleanup(shutil.rmtree, d)
        self.assertEqual(dh.independence_violations(d), [])


class TestProjectStatus(unittest.TestCase):
    def _root(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        os.makedirs(os.path.join(root, ".engineer"))
        with open(os.path.join(root, ".engineer", "manifest.yml"), "w") as f:
            f.write('methodology_version: "0.2"\nfeatures_root: features/\n')
        return root

    def test_enumerates_features(self):
        root = self._root()
        fa = os.path.join(root, "features", "001-alpha", "handoffs")
        os.makedirs(fa)
        with open(os.path.join(root, "features", "001-alpha", "feature.md"), "w") as f:
            f.write("---\nslug: 001-alpha\nstatus: in-progress\n---\n# a\n")
        with open(os.path.join(fa, "h.md"), "w") as f:
            f.write(HANDOFF_COMPLETE)
        with open(os.path.join(root, "features", "001-alpha", "progress.md"), "w") as f:
            f.write(PROGRESS)
        fb = os.path.join(root, "features", "002-beta")
        os.makedirs(fb)
        with open(os.path.join(fb, "feature.md"), "w") as f:
            f.write("---\nslug: 002-beta\nstatus: done\n---\n# b\n")
        os.makedirs(os.path.join(root, "features", ".build"))  # skipped (no feature.md)

        rows = dh.project_status(root)
        self.assertEqual([r["feature"] for r in rows], ["001-alpha", "002-beta"])
        self.assertEqual(rows[0]["status"], "in-progress")
        self.assertEqual(rows[0]["latest_complete_cp"], 2)
        self.assertEqual(rows[0]["last_handoff"], "h.md")
        self.assertEqual(rows[1]["status"], "done")
        self.assertIsNone(rows[1]["last_handoff"])

    def test_no_manifest_returns_empty(self):
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty)
        self.assertEqual(dh.project_status(empty), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class RealRunGateTests(unittest.TestCase):
    """CP7 on an onboarded project needs evidence from the real app."""

    def _project(self, verify_app="verify-web", evidence=b"HTTP 200",
                 created=dh.REAL_RUN_CUTOFF):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        os.makedirs(os.path.join(root, ".engineer"))
        with open(os.path.join(root, ".engineer", "manifest.yml"), "w") as f:
            f.write("verify_app: %s\n" % verify_app)
        os.makedirs(os.path.join(root, ".claude", "skills", "verify-web"))
        open(os.path.join(root, ".claude", "skills", "verify-web", "SKILL.md"), "w").close()
        fdir = os.path.join(root, "features", "001-a")
        os.makedirs(os.path.join(fdir, "handoffs"))
        with open(os.path.join(fdir, "feature.md"), "w") as f:
            f.write("---\nslug: 001-a\ncreated: %s\n---\n" % created)
        if evidence is not None:
            os.makedirs(os.path.join(fdir, "evidence"))
            with open(os.path.join(fdir, "evidence", "run.txt"), "wb") as f:
                f.write(evidence)
        return fdir

    def _write(self, fdir, real_run):
        with open(os.path.join(fdir, "handoffs", "h7.md"), "w") as f:
            f.write(_handoff("arch-check", "v", 7).replace(
                "status: complete\n", real_run + "status: complete\n"))

    RR = ("real_run:\n  skill: verify-web\n  evidence:\n"
          "    - features/001-a/evidence/run.txt\n")

    def test_passes_with_evidence(self):
        fdir = self._project()
        self._write(fdir, self.RR)
        self.assertTrue(dh.gate(fdir, 7)[0])

    def test_tests_only_handoff_blocked(self):
        fdir = self._project()
        self._write(fdir, "")
        ok, msg = dh.gate(fdir, 7)
        self.assertFalse(ok)
        self.assertIn("real_run", msg)

    def test_missing_or_empty_evidence_blocked(self):
        for ev in (None, b""):
            fdir = self._project(evidence=ev)
            self._write(fdir, self.RR)
            self.assertFalse(dh.gate(fdir, 7)[0])

    def test_explicit_opt_out(self):
        fdir = self._project(verify_app="none")
        self._write(fdir, "")
        self.assertTrue(dh.gate(fdir, 7)[0])

    def test_in_flight_feature_warns_but_passes(self):
        fdir = self._project(created="2026-10-19")
        self._write(fdir, "")
        ok, msg = dh.gate(fdir, 7)
        self.assertTrue(ok)
        self.assertIn("WARNING", msg)
