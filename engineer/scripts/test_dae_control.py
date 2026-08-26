#!/usr/bin/env python3
"""Tests for dae_control.py + dae_arch.graph — component graph + served API."""
import http.server
import json
import os
import subprocess
import tempfile
import threading
import unittest
import urllib.request

import dae_arch
import dae_control


def _mk_layered_repo(root):
    """A tiny 2-layer project where domain imports http (a forbidden edge)."""
    os.makedirs(os.path.join(root, ".engineer"))
    with open(os.path.join(root, ".engineer", "manifest.yml"), "w") as fh:
        fh.write(
            "methodology_version: 0.25.0\n"
            "architecture:\n"
            "  layers:\n"
            "    - name: domain\n"
            "      paths: [\"src/domain/**\"]\n"
            "      may_not_import: [http]\n"
            "    - name: http\n"
            "      paths: [\"src/http/**\"]\n"
        )
    os.makedirs(os.path.join(root, "src", "domain"))
    os.makedirs(os.path.join(root, "src", "http"))
    with open(os.path.join(root, "src", "http", "api.py"), "w") as fh:
        fh.write("thing = 1\n")
    with open(os.path.join(root, "src", "domain", "core.py"), "w") as fh:
        fh.write("from src.http.api import thing\n")  # forbidden import
    q = {"cwd": root, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    subprocess.run(["git", "init"], **q)  # files_in_scope lists git-tracked files
    subprocess.run(["git", "add", "-A"], **q)


class TestGraph(unittest.TestCase):
    def test_forbidden_edge_and_nodes(self):
        with tempfile.TemporaryDirectory() as root:
            _mk_layered_repo(root)
            g = dae_arch.graph(root)
            if not g["arch_supported"]:
                self.skipTest("resolve/audit unavailable in this env")
            names = {l["name"] for l in g["layers"]}
            self.assertEqual(names, {"domain", "http"})
            forbidden = [e for e in g["edges"]
                         if e["src"] == "domain" and e["dst"] == "http"]
            self.assertEqual(len(forbidden), 1)
            self.assertEqual(forbidden[0]["kind"], "forbidden")
            self.assertGreaterEqual(forbidden[0]["count"], 1)  # actually violated

    def test_no_architecture_is_graceful(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".engineer"))
            with open(os.path.join(root, ".engineer", "manifest.yml"), "w") as fh:
                fh.write("methodology_version: 0.25.0\n")
            g = dae_arch.graph(root)
            self.assertFalse(g["arch_supported"])
            self.assertEqual(g["layers"], [])


class TestServer(unittest.TestCase):
    def test_api_and_page(self):
        with tempfile.TemporaryDirectory() as root:
            _mk_layered_repo(root)
            handler = dae_control._make_handler(root)
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                base = "http://127.0.0.1:%d" % httpd.server_address[1]
                state = json.loads(urllib.request.urlopen(base + "/api/state", timeout=5).read())
                self.assertIn("features", state)
                self.assertIn("components", state)
                self.assertIn("layers", state["components"])
                self.assertIn("edges", state["components"])
                page = urllib.request.urlopen(base + "/", timeout=5).read().decode()
                self.assertIn("<!doctype html>", page.lower())
                self.assertIn("/api/state", page)  # the page fetches the API
                self.assertEqual(urllib.request.urlopen(base + "/", timeout=5).status, 200)
            finally:
                httpd.shutdown()


if __name__ == "__main__":
    unittest.main()
