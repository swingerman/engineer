#!/usr/bin/env python3
"""Tests for dae_arch — the charter architecture fitness checker.

Run: python3 -m unittest test_dae_arch -v
"""
import os
import shutil
import tempfile
import unittest

import dae_arch as da


class TestGlob(unittest.TestCase):
    def test_star_within_segment(self):
        rx = da._glob_to_regex("src/*.py")
        self.assertTrue(rx.match("src/a.py"))
        self.assertFalse(rx.match("src/sub/a.py"))

    def test_double_star_spans_segments(self):
        rx = da._glob_to_regex("src/**/*.py")
        self.assertTrue(rx.match("src/a.py"))
        self.assertTrue(rx.match("src/x/y/a.py"))
        self.assertFalse(rx.match("lib/a.py"))

    def test_match_any(self):
        globs = da._compile_globs(["src/**", "lib/**"])
        self.assertTrue(da._match_any("src/x/y.py", globs))
        self.assertTrue(da._match_any("lib/z.py", globs))
        self.assertFalse(da._match_any("test/z.py", globs))


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class TestGenericChecks(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

    def test_forbidden_pattern_hit(self):
        _write(self.root, "src/a.py", "x = 1\nconsole.log(x)\n")
        rules = [{"pattern": r"console\.log", "paths": ["src/**"],
                  "reason": "use the logger"}]
        v = da.check_forbidden(self.root, ["src/a.py"], rules)
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0][0], "src/a.py")
        self.assertEqual(v[0][1], 2)
        self.assertEqual(v[0][2], "forbidden_patterns")

    def test_forbidden_pattern_out_of_scope(self):
        _write(self.root, "lib/a.py", "console.log(1)\n")
        rules = [{"pattern": r"console\.log", "paths": ["src/**"]}]
        self.assertEqual(da.check_forbidden(self.root, ["lib/a.py"], rules), [])

    def test_naming_violation(self):
        rules = [{"paths": ["src/**"], "filename_must_match": r"^[a-z0-9_]+\.py$",
                  "reason": "snake_case"}]
        v = da.check_naming(["src/BadName.py"], rules)
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0][2], "naming")

    def test_naming_ok(self):
        rules = [{"paths": ["src/**"], "filename_must_match": r"^[a-z0-9_]+\.py$"}]
        self.assertEqual(da.check_naming(["src/good_name.py"], rules), [])

    def test_file_size_over_cap(self):
        _write(self.root, "src/big.py", "\n".join("x" for _ in range(50)) + "\n")
        cfg = {"max_lines": 10}
        v = da.check_file_size(self.root, ["src/big.py"], cfg)
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0][2], "file_size")

    def test_file_size_override(self):
        _write(self.root, "src/generated/g.py", "\n".join("x" for _ in range(50)) + "\n")
        cfg = {"max_lines": 10,
               "overrides": [{"paths": ["**/generated/**"], "max_lines": 1000}]}
        self.assertEqual(da.check_file_size(self.root, ["src/generated/g.py"], cfg), [])


class TestImports(unittest.TestCase):
    def test_python_imports(self):
        text = "import os\nfrom pkg.mod import thing\nfrom .relmod import other\n"
        specs = da.extract_imports("a/b.py", text)
        self.assertIn("os", specs)
        self.assertIn("pkg.mod", specs)
        self.assertIn(".relmod", specs)

    def test_js_imports(self):
        text = ('import x from "./local";\n'
                'const y = require("../up/dep");\n'
                'import "react";\n')
        specs = da.extract_imports("a/b.ts", text)
        self.assertIn("./local", specs)
        self.assertIn("../up/dep", specs)
        self.assertIn("react", specs)


class TestLayers(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

    def test_layering_violation_python(self):
        _write(self.root, "src/domain/order.py", "from src.infra.db import save\n")
        _write(self.root, "src/infra/db.py", "def save(): pass\n")
        layers = [
            {"name": "domain", "paths": ["src/domain/**"],
             "may_not_import": ["infra"]},
            {"name": "infra", "paths": ["src/infra/**"]},
        ]
        files = ["src/domain/order.py", "src/infra/db.py"]
        v = da.check_layers(self.root, files, layers, files)
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0][2], "layers")
        self.assertIn("domain", v[0][3])
        self.assertIn("infra", v[0][3])

    def test_layering_clean(self):
        _write(self.root, "src/domain/order.py", "from src.domain.money import M\n")
        _write(self.root, "src/domain/money.py", "M = 1\n")
        layers = [{"name": "domain", "paths": ["src/domain/**"],
                   "may_not_import": ["infra"]},
                  {"name": "infra", "paths": ["src/infra/**"]}]
        files = ["src/domain/order.py", "src/domain/money.py"]
        self.assertEqual(da.check_layers(self.root, files, layers, files), [])

    def test_layering_violation_js(self):
        _write(self.root, "src/web/page.ts", 'import {db} from "../infra/db";\n')
        _write(self.root, "src/infra/db.ts", "export const db = 1;\n")
        layers = [{"name": "web", "paths": ["src/web/**"],
                   "may_not_import": ["infra"]},
                  {"name": "infra", "paths": ["src/infra/**"]}]
        files = ["src/web/page.ts", "src/infra/db.ts"]
        v = da.check_layers(self.root, files, layers, files)
        self.assertEqual(len(v), 1)


class TestAudit(unittest.TestCase):
    def test_audit_collects_all_kinds(self):
        rules = {
            "forbidden_patterns": [{"pattern": "TODO", "paths": ["**"]}],
            "file_size": {"max_lines": 1},
        }
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        _write(root, "src/a.py", "TODO\nx\n")
        v = da.audit_rules(root, ["src/a.py"], rules)
        kinds = sorted(set(x[2] for x in v))
        self.assertEqual(kinds, ["file_size", "forbidden_patterns"])

    def test_audit_empty_rules(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        self.assertEqual(da.audit_rules(root, [], {}), [])


class CheckCyclesTests(unittest.TestCase):
    def test_no_cycle_in_empty_graph(self):
        self.assertEqual(da.check_cycles({}), [])

    def test_no_cycle_in_linear_chain(self):
        # a -> b -> c, no cycle
        graph = {"a": ["b"], "b": ["c"], "c": []}
        self.assertEqual(da.check_cycles(graph), [])

    def test_self_loop_is_a_cycle(self):
        graph = {"a": ["a"]}
        self.assertEqual(da.check_cycles(graph), [["a"]])

    def test_two_node_cycle(self):
        graph = {"a": ["b"], "b": ["a"]}
        self.assertEqual(da.check_cycles(graph), [["a", "b"]])

    def test_three_node_cycle(self):
        graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
        self.assertEqual(da.check_cycles(graph), [["a", "b", "c"]])

    def test_disjoint_cycles_are_both_reported(self):
        # Two independent 2-cycles.
        graph = {"a": ["b"], "b": ["a"], "x": ["y"], "y": ["x"]}
        cycles = da.check_cycles(graph)
        self.assertEqual(len(cycles), 2)
        self.assertIn(["a", "b"], cycles)
        self.assertIn(["x", "y"], cycles)

    def test_acyclic_portions_are_excluded(self):
        # a -> b -> c -> b (cycle b<->c); d -> a (acyclic).
        graph = {"a": ["b"], "b": ["c"], "c": ["b"], "d": ["a"]}
        cycles = da.check_cycles(graph)
        self.assertEqual(cycles, [["b", "c"]])


class AuditIncludesCyclesTests(unittest.TestCase):
    def test_audit_reports_cycles_when_present(self):
        import subprocess
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        # Initialize git repo so files_in_scope works
        subprocess.run(["git", "init"], cwd=root, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True)
        os.makedirs(os.path.join(root, "src"))
        with open(os.path.join(root, "src", "a.py"), "w") as f:
            f.write("from .b import x\n")
        with open(os.path.join(root, "src", "b.py"), "w") as f:
            f.write("from .a import y\n")
        # Add files to git
        subprocess.run(["git", "add", "src/a.py", "src/b.py"], cwd=root, capture_output=True)

        manifest = {"architecture": {"layers": []}}
        result = da.audit_rules(root, ["src/a.py", "src/b.py"], manifest["architecture"])
        cycle_violations = [v for v in result if v[2] == "cycles"]
        self.assertEqual(len(cycle_violations), 1,
                         "expected exactly one cycle violation; got %r" % (result,))
        v = cycle_violations[0]
        self.assertIn(v[0], (os.path.join("src", "a.py"),
                             os.path.join("src", "b.py"),
                             "src/a.py", "src/b.py"))
        self.assertEqual(v[2], "cycles")
        # Message should reference both files in the cycle.
        self.assertIn("a.py", v[3])
        self.assertIn("b.py", v[3])


def _git(cwd, *args):
    import subprocess
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


def _repo(path):
    os.makedirs(path, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@t.t")
    _git(path, "config", "user.name", "T")


class NestedRepoTests(unittest.TestCase):
    """A manifest `repos:` entry that is its own git repo (e.g. `android/`, gitignored by the
    methodology repo) is audited too, with paths reported relative to the methodology root."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        _repo(self.root)
        _write(self.root, ".gitignore", "/android/\n")
        _write(self.root, ".engineer/manifest.yml",
               "project: p\n"
               "repos:\n"
               "  - name: android\n"
               "    path: android\n"
               "    default_branch: main\n"
               "architecture:\n"
               "  file_size:\n"
               "    max_lines: 2\n"
               "  forbidden_patterns:\n"
               "    - pattern: \"^import android \"\n"
               "      paths: [\"android/**/pure/**\"]\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "init")
        self.android = os.path.join(self.root, "android")
        _repo(self.android)
        _write(self.android, "app/Ok.kt", "class Ok\n")
        _git(self.android, "add", "-A")
        _git(self.android, "commit", "-qm", "base")
        _git(self.android, "checkout", "-qb", "feature")

    def test_jvm_sources_are_in_scope(self):
        for ext in (".java", ".kt", ".swift"):
            self.assertTrue(("X" + ext).endswith(da.SOURCE_EXTENSIONS), ext)

    def test_full_audit_reports_nested_repo_files_with_their_prefix(self):
        _write(self.android, "app/Big.kt", "a\nb\nc\n")
        _git(self.android, "add", "-A")
        _git(self.android, "commit", "-qm", "big")
        _, _, v = da.audit(self.root, full=True)
        self.assertIn(("android/app/Big.kt", 3, "file_size", "3 lines > max 2"), v)

    def test_diff_audit_scopes_nested_repo_to_its_branch_changes(self):
        _write(self.android, "app/pure/P.kt", "import android view\n")
        _git(self.android, "add", "-A")
        _git(self.android, "commit", "-qm", "pure")
        _, _, v = da.audit(self.root, full=False)
        files = sorted({x[0] for x in v})
        self.assertEqual(files, ["android/app/pure/P.kt"])   # Ok.kt is unchanged vs main
        self.assertEqual(v[0][2], "forbidden_patterns")

    def test_option_like_default_branch_is_not_passed_as_an_option(self):
        names = da.files_in_scope(self.android, full=False, base="--output=/tmp/pwned")
        self.assertFalse(os.path.exists("/tmp/pwned"))
        self.assertEqual(names, ["app/Ok.kt"])   # unresolvable base -> full listing, no option parsed

    def test_repo_entry_that_is_not_its_own_git_repo_is_ignored(self):
        shutil.rmtree(os.path.join(self.android, ".git"))
        _, _, v = da.audit(self.root, full=True)
        self.assertFalse([x for x in v if x[0].startswith("android/")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
