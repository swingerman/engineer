"""Tests for dae_progress.py."""
import os
import tempfile
import unittest

import dae_progress

# A representative progress.md CURRENT header (with the '>' blockquote marker).
CURRENT = "> ▶ CP3 Spec — 2/4 criteria met | NEXT: write spec.md | BLOCKED: none\n"

# A representative Checkpoints table: CP 0, 1.5, 2 done; CP 3 in progress.
TABLE = (
    "## Checkpoints\n"
    "| CP | Stage | Status |\n"
    "|----|-------|--------|\n"
    "| 0 | Onboard | done |\n"
    "| 1.5 | Ready | done |\n"
    "| 2 | ACs | done |\n"
    "| 3 | Spec | in progress |\n"
)


class ParseCurrentHeaderTests(unittest.TestCase):
    def test_extracts_all_fields(self):
        h = dae_progress.parse_current_header(CURRENT)
        self.assertEqual(h["cp"], 3)
        self.assertEqual(h["stage"], "Spec")
        self.assertEqual(h["met"], 2)
        self.assertEqual(h["total"], 4)
        self.assertEqual(h["next"], "write spec.md")
        self.assertEqual(h["blocked"], "none")

    def test_blocked_reason_is_captured(self):
        line = "> ▶ CP4 Plan — 1/3 criteria met | NEXT: revise | BLOCKED: awaiting ADR-012\n"
        h = dae_progress.parse_current_header(line)
        self.assertEqual(h["blocked"], "awaiting ADR-012")

    def test_half_checkpoint_number(self):
        line = "▶ CP1.5 Ready — 1/1 criteria met | NEXT: discover ACs\n"
        h = dae_progress.parse_current_header(line)
        self.assertEqual(h["cp"], 1.5)
        self.assertIsNone(h["blocked"])

    def test_absent_header_returns_none(self):
        self.assertIsNone(
            dae_progress.parse_current_header("# progress\n\nno header here\n"))


class RenderBreadcrumbTests(unittest.TestCase):
    def test_marks_done_current_and_pending(self):
        out = dae_progress.render_breadcrumb(
            "015-image-formats", {0, 1.5, 2}, 3, "CP3 Spec — 2/4 criteria met")
        self.assertIn("DAE ▸ 015-image-formats", out)
        self.assertIn("✓0 Onboard", out)
        self.assertIn("✓1.5 Ready", out)
        self.assertIn("✓2 ACs", out)
        self.assertIn("▶3 Spec", out)
        self.assertIn("·4 Plan", out)
        self.assertIn("·5 Implement", out)
        self.assertIn("·8 Harden", out)
        self.assertIn("CP3 Spec — 2/4 criteria met", out)

    def test_renders_all_nine_stops(self):
        out = dae_progress.render_breadcrumb("x", set(), None, "")
        for stage in ("Onboard", "Ready", "ACs", "Spec", "Plan",
                      "Implement", "Refine", "Verify", "Harden"):
            self.assertIn(stage, out)

    def test_empty_detail_is_omitted(self):
        out = dae_progress.render_breadcrumb("x", set(), None, "")
        self.assertEqual(len(out.splitlines()), 2)


def _write_feature(parent, name, contents):
    """Create parent/name/ and, if contents is not None, parent/name/progress.md."""
    feat = os.path.join(parent, name)
    os.makedirs(feat)
    if contents is not None:
        with open(os.path.join(feat, "progress.md"), "w", encoding="utf-8") as f:
            f.write(contents)
    return feat


class BreadcrumbTests(unittest.TestCase):
    def test_full_progress_file(self):
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "015-image-formats", CURRENT + "\n" + TABLE)
            out = dae_progress.breadcrumb(feat)
        self.assertIn("DAE ▸ 015-image-formats", out)
        self.assertIn("✓2 ACs", out)
        self.assertIn("▶3 Spec", out)
        self.assertIn("NEXT: write spec.md", out)
        self.assertNotIn("BLOCKED", out)  # blocked: none is omitted

    def test_blocked_reason_shown(self):
        header = "> ▶ CP4 Plan — 1/3 criteria met | NEXT: revise | BLOCKED: awaiting ADR-012\n"
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "042-export", header + "\n" + TABLE)
            out = dae_progress.breadcrumb(feat)
        self.assertIn("BLOCKED: awaiting ADR-012", out)

    def test_missing_progress_degrades(self):
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "099-new", None)
            out = dae_progress.breadcrumb(feat)
        self.assertIn("099-new", out)
        self.assertIn("not yet started", out)
        self.assertIn("·0 Onboard", out)

    def test_no_header_degrades(self):
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "022-x", TABLE)  # table only, no header
            out = dae_progress.breadcrumb(feat)
        self.assertIn("✓2 ACs", out)
        self.assertIn("no CURRENT header", out)


class StateTests(unittest.TestCase):
    def test_json_state_for_the_mods(self):
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "015-image-formats", CURRENT + "\n" + TABLE)
            _write_fm(feat, "autonomy_level: medium")
            os.makedirs(os.path.join(feat, "handoffs"))
            with open(os.path.join(feat, "handoffs", "cp2.md"), "w", encoding="utf-8") as f:
                f.write("---\ncheckpoint: 2\nhuman_action_needed: yes\n---\n")
            with open(os.path.join(feat, "run-graph.yml"), "w", encoding="utf-8") as f:
                f.write("segments:\n  - name: front\n    checkpoints: [2, 3, 4]\n")
            out = dae_progress.state(feat)
        self.assertEqual((out["cp"], out["met"], out["total"]), (3, 2, 4))
        self.assertEqual(out["segment"], "front")
        self.assertEqual(out["autonomy_level"], "medium")
        self.assertTrue(out["last_handoff"].endswith("handoffs/cp2.md"))
        self.assertTrue(out["human_action_needed"])
        self.assertIn("DAE ▸ 015-image-formats", out["breadcrumb"])

    def test_bare_feature_degrades(self):
        with tempfile.TemporaryDirectory() as d:
            out = dae_progress.state(_write_feature(d, "099-new", None))
        self.assertIsNone(out["cp"])
        self.assertIsNone(out["last_handoff"])
        self.assertFalse(out["human_action_needed"])


def _write_fm(feature_dir, body):
    """Write a feature.md with the given frontmatter body."""
    with open(os.path.join(feature_dir, "feature.md"), "w",
              encoding="utf-8") as f:
        f.write("---\n" + body + "\n---\n\n# Feature\n")


class RoadmapLineTests(unittest.TestCase):
    def test_absent_feature_md_yields_empty(self):
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "010-x", TABLE)
            self.assertEqual(dae_progress.roadmap_line(feat), "")

    def test_linked_item_shows_ref_and_status(self):
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "010-x", TABLE)
            _write_fm(feat, "slug: 010-x\nroadmap_ref: bulk-export\nstatus: ready")
            line = dae_progress.roadmap_line(feat)
        self.assertIn("ROADMAP ▸ bulk-export", line)
        self.assertIn("(ready)", line)

    def test_unlinked_feature_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "010-x", TABLE)
            _write_fm(feat, "slug: 010-x\nstatus: in-progress")
            line = dae_progress.roadmap_line(feat)
        self.assertIn("not linked", line)
        self.assertIn("in-progress", line)

    def test_parent_and_children_are_surfaced(self):
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "008-x", TABLE)
            _write_fm(feat, "slug: 008-x\nroadmap_ref: design-foundations\n"
                            "status: ready\nparent_feature: 007-nav\n"
                            "child_features:\n  - 009-a\n  - 010-b")
            line = dae_progress.roadmap_line(feat)
        self.assertIn("child of 007-nav", line)
        self.assertIn("parent of 2", line)

    def test_breadcrumb_appends_roadmap_line(self):
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "010-x", CURRENT + "\n" + TABLE)
            _write_fm(feat, "slug: 010-x\nroadmap_ref: bulk-export\nstatus: ready")
            out = dae_progress.breadcrumb(feat)
        self.assertIn("ROADMAP ▸ bulk-export", out)
        # still renders the checkpoint stops and detail
        self.assertIn("▶3 Spec", out)
        self.assertIn("NEXT: write spec.md", out)

    def test_breadcrumb_omits_roadmap_line_when_no_feature_md(self):
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "010-x", CURRENT + "\n" + TABLE)
            out = dae_progress.breadcrumb(feat)
        self.assertNotIn("ROADMAP", out)


class MainTests(unittest.TestCase):
    def test_help_returns_zero(self):
        self.assertEqual(dae_progress.main(["--help"]), 0)

    def test_no_args_returns_zero(self):
        self.assertEqual(dae_progress.main([]), 0)

    def test_run_on_feature_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            feat = _write_feature(d, "015-x", CURRENT + "\n" + TABLE)
            self.assertEqual(dae_progress.main([feat]), 0)


if __name__ == "__main__":
    unittest.main()
