#!/usr/bin/env python3
"""Tests for dae_dashboard.py — checkpoint parsing, pct, violation→layer map."""
import os
import subprocess
import tempfile
import unittest

import dae_dashboard as dd


class TestFeatures(unittest.TestCase):
    def _feature(self, root, slug, fm, progress=None):
        d = os.path.join(root, "features", slug)
        os.makedirs(d)
        with open(os.path.join(d, "feature.md"), "w") as fh:
            fh.write(fm)
        if progress is not None:
            with open(os.path.join(d, "progress.md"), "w") as fh:
                fh.write(progress)

    def test_frontmatter_scalars(self):
        fm = dd._frontmatter('---\nslug: x\ntitle: "Hi"\ntags: [a, b]\n---\nbody')
        self.assertEqual(fm["slug"], "x")
        self.assertEqual(fm["title"], "Hi")

    def test_prose_status_fallback(self):
        self.assertEqual(dd._prose_status("**Status**: Shipped. blah"), "done")
        self.assertEqual(dd._prose_status("Status: parked"), "parked")
        self.assertIsNone(dd._prose_status("no status line"))

    def test_reached_index(self):
        self.assertEqual(dd._reached_index("did CP2 then CP5"), dd._CP_INDEX["5"])
        self.assertEqual(dd._reached_index("Checkpoint 3 reached"), dd._CP_INDEX["3"])
        self.assertEqual(dd._reached_index("nothing here"), -1)

    def test_collect_and_pct(self):
        with tempfile.TemporaryDirectory() as root:
            # in-progress at CP5 → partial bar
            self._feature(root, "010-thing",
                          "---\nslug: thing\ntitle: Thing\nstatus: in-progress\nsize: M\n---\n",
                          "reached CP5 now")
            # done → full regardless of checkpoint text
            self._feature(root, "011-done",
                          "---\nslug: done\ntitle: Done\nstatus: done\n---\n",
                          "at CP7")
            feats = {f["slug"]: f for f in dd.collect_features(root)}
            self.assertEqual(feats["010-thing"]["checkpoint"], "5")
            self.assertAlmostEqual(feats["010-thing"]["pct"],
                                   dd._CP_INDEX["5"] / (len(dd.CP_STAGES) - 1), places=2)
            self.assertEqual(feats["011-done"]["pct"], 1.0)


class TestComponents(unittest.TestCase):
    def test_violation_maps_to_layer(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".engineer"))
            with open(os.path.join(root, ".engineer", "manifest.yml"), "w") as fh:
                fh.write(
                    "methodology_version: 0.22.0\n"
                    "architecture:\n"
                    "  layers:\n"
                    "    - name: domain\n"
                    "      paths: [\"src/domain/**\"]\n"
                    "      may_not_import: [http]\n"
                    "    - name: http\n"
                    "      paths: [\"src/http/**\"]\n"
                )
            # domain importing http is a forbidden edge → one layers violation
            os.makedirs(os.path.join(root, "src", "domain"))
            os.makedirs(os.path.join(root, "src", "http"))
            with open(os.path.join(root, "src", "http", "api.py"), "w") as fh:
                fh.write("x = 1\n")
            with open(os.path.join(root, "src", "domain", "core.py"), "w") as fh:
                fh.write("from src.http.api import thing\n")  # dotted to the file, resolvable
            # files_in_scope(full=True) lists git-tracked files, so init a repo
            q = {"cwd": root, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            subprocess.run(["git", "init"], **q)
            subprocess.run(["git", "add", "-A"], **q)
            comp = dd.collect_components(root)
            if not comp["arch_supported"]:
                self.skipTest("resolve/audit unavailable in this env")
            by = {l["name"]: l for l in comp["layers"]}
            self.assertEqual(by["domain"]["violations"], 1)
            self.assertEqual(by["http"]["violations"], 0)


if __name__ == "__main__":
    unittest.main()
