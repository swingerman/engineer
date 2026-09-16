"""Tests for dae_feature_number.py."""
import os
import subprocess
import tempfile
import unittest

import dae_feature_number


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   cwd=cwd, check=True, capture_output=True)


def _commit_feature(repo, name):
    os.makedirs(os.path.join(repo, "features", name))
    open(os.path.join(repo, "features", name, "feature.md"), "w").close()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", name)


class NextNumberTests(unittest.TestCase):
    def test_no_repo_uses_local_dir(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "features", "004-x"))
            self.assertEqual(dae_feature_number.next_number(os.path.join(d, "features")), "005")

    def test_missing_dir_starts_at_001(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(dae_feature_number.next_number(os.path.join(d, "features")), "001")

    def test_sees_other_branches_and_worktrees(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, "repo")
            os.makedirs(repo)
            _git(repo, "init", "-b", "main")
            _commit_feature(repo, "001-base")
            # committed on a branch with no worktree
            _git(repo, "checkout", "-b", "other")
            _commit_feature(repo, "005-other")
            _git(repo, "checkout", "main")
            # uncommitted folder in another worktree
            wt = os.path.join(d, "wt")
            _git(repo, "worktree", "add", "-b", "wip", wt)
            os.makedirs(os.path.join(wt, "features", "007-wip"))
            self.assertEqual(dae_feature_number.next_number(os.path.join(repo, "features")), "008")


if __name__ == "__main__":
    unittest.main()
