#!/usr/bin/env python3
"""Tests for dae_infra.py — probe, state, ensure, teardown, status."""
import http.server
import json
import os
import signal
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import dae_infra

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DAE_INFRA = os.path.join(SCRIPTS_DIR, "dae_infra.py")


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_root(tmp: str, infra_yml: str = "") -> str:
    d = os.path.join(tmp, ".engineer")
    os.makedirs(d, exist_ok=True)
    body = ('methodology_version: "0.2"\nroadmap:\n  type: local\n'
            'tracker:\n  type: local\n')
    if infra_yml:
        body += "\ninfra:\n" + infra_yml
    with open(os.path.join(d, "manifest.yml"), "w") as f:
        f.write(body)
    return tmp


def _tcp_infra_yml(port: int, name: str = "svc", rto: int = 10) -> str:
    """YAML snippet: TCP health check + minimal TCP echo server as start command."""
    py = ("import socket,threading,time;s=socket.socket();"
          "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
          "s.bind(('127.0.0.1',{p}));s.listen(10);"
          "threading.Thread(target=lambda:[s.accept()[0].close() or None"
          " for _ in iter(int,1)],daemon=True).start();time.sleep(3600)").format(p=port)
    return ("  {n}:\n    health:\n      type: tcp\n      port: {p}\n"
            "      host: 127.0.0.1\n      timeout_s: 2\n"
            "    start:\n      command: python3 -c \"{py}\"\n"
            "      background: true\n      ready_timeout_s: {rto}\n"
            "    teardown: session-end\n").format(n=name, p=port, py=py, rto=rto)


def _run_cli(*args, root=None):
    cmd = ([sys.executable, DAE_INFRA, args[0], "--root", root] + list(args[1:])
           if root else [sys.executable, DAE_INFRA] + list(args))
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _rmtree(path): import shutil; shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# 1. Probe: HTTP
# ---------------------------------------------------------------------------

class TestProbeHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.server = socketserver.TCPServer(("127.0.0.1", cls.port),
                                            http.server.SimpleHTTPRequestHandler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_up(self):
        self.assertTrue(dae_infra.probe_http("http://127.0.0.1:%d" % self.port, timeout_s=3))

    def test_down(self):
        self.assertFalse(dae_infra.probe_http("http://127.0.0.1:%d" % _free_port(), timeout_s=1))


# ---------------------------------------------------------------------------
# 2. Probe: TCP
# ---------------------------------------------------------------------------

class TestProbeTCP(unittest.TestCase):
    def setUp(self):
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.port = self.srv.getsockname()[1]
        self.srv.listen(1)

    def tearDown(self):
        self.srv.close()

    def test_up(self):
        self.assertTrue(dae_infra.probe_tcp("127.0.0.1", self.port, timeout_s=2))

    def test_down(self):
        self.srv.close()
        self.assertFalse(dae_infra.probe_tcp("127.0.0.1", _free_port(), timeout_s=1))


# ---------------------------------------------------------------------------
# 3. Probe: command and process
# ---------------------------------------------------------------------------

class TestProbeCommand(unittest.TestCase):
    def test_true(self):
        self.assertTrue(dae_infra.probe_command("true", timeout_s=3))

    def test_false(self):
        self.assertFalse(dae_infra.probe_command("false", timeout_s=3))

    def test_nonexistent(self):
        self.assertFalse(dae_infra.probe_command("__no_such_cmd_xyz__", timeout_s=2))


class TestProbeProcess(unittest.TestCase):
    MARKER = "__dae_infra_probe_test_marker_xyz__"

    def setUp(self):
        self.proc = subprocess.Popen(
            [sys.executable, "-c",
             "import time; time.sleep(30)  # %s" % self.MARKER],
            start_new_session=True)
        time.sleep(0.2)

    def tearDown(self):
        try:
            self.proc.kill(); self.proc.wait()
        except Exception:
            pass

    def test_matching_pattern(self):
        self.assertTrue(dae_infra.probe_process(self.MARKER))

    def test_no_match(self):
        self.assertFalse(dae_infra.probe_process("__no_such_process_xyz_abc_123__"))


# ---------------------------------------------------------------------------
# 4. make_health_probe factory
# ---------------------------------------------------------------------------

class TestMakeHealthProbe(unittest.TestCase):
    def test_http_down(self):
        self.assertFalse(dae_infra.make_health_probe(
            {"type": "http", "url": "http://127.0.0.1:19999", "timeout_s": 1})())

    def test_tcp_down(self):
        self.assertFalse(dae_infra.make_health_probe(
            {"type": "tcp", "host": "127.0.0.1", "port": 19998, "timeout_s": 1})())

    def test_command_true(self):
        self.assertTrue(dae_infra.make_health_probe(
            {"type": "command", "command": "true", "timeout_s": 3})())

    def test_command_false(self):
        self.assertFalse(dae_infra.make_health_probe(
            {"type": "command", "command": "false", "timeout_s": 3})())

    def test_process_match(self):
        MARKER = "__dae_make_health_probe_marker_abc__"
        proc = subprocess.Popen([sys.executable, "-c",
                                 "import time; time.sleep(30)  # %s" % MARKER],
                                start_new_session=True)
        time.sleep(0.2)
        try:
            self.assertTrue(dae_infra.make_health_probe({"type": "process", "pattern": MARKER})())
        finally:
            proc.kill(); proc.wait()

    def test_unknown_type_false(self):
        self.assertFalse(dae_infra.make_health_probe({"type": "unknown_xyz"})())


# ---------------------------------------------------------------------------
# 5. Schema loading via dae_resolve
# ---------------------------------------------------------------------------

class TestLoadEntries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        _rmtree(self.tmp)

    def _root(self, yml):
        return _make_root(self.tmp, yml)

    def test_basic_entry_loaded(self):
        self._root("  auth:\n    health:\n      type: tcp\n      port: 9099\n"
                   "    start:\n      command: echo hi\n")
        entries = dae_infra.load_entries(self.tmp)
        self.assertIn("auth", entries)

    def test_http_timeout_default(self):
        self._root("  svc:\n    health:\n      type: http\n"
                   "      url: http://localhost:8080\n    start:\n      command: echo x\n")
        self.assertEqual(dae_infra.load_entries(self.tmp)["svc"]["health"]["timeout_s"],
                         dae_infra.DEFAULT_HTTP_TIMEOUT)

    def test_start_defaults(self):
        self._root("  svc:\n    health:\n      type: process\n      pattern: foo\n"
                   "    start:\n      command: echo x\n")
        s = dae_infra.load_entries(self.tmp)["svc"]["start"]
        self.assertTrue(s["background"])
        self.assertEqual(s["ready_timeout_s"], dae_infra.DEFAULT_READY_TIMEOUT)

    def test_default_teardown_from_block(self):
        self._root("  default_teardown: session-end\n"
                   "  svc:\n    health:\n      type: process\n      pattern: foo\n"
                   "    start:\n      command: echo x\n")
        self.assertEqual(dae_infra.load_entries(self.tmp)["svc"]["teardown"], "session-end")

    def test_entry_teardown_overrides_default(self):
        self._root("  default_teardown: session-end\n"
                   "  svc:\n    health:\n      type: process\n      pattern: foo\n"
                   "    start:\n      command: echo x\n    teardown: leave-running\n")
        self.assertEqual(dae_infra.load_entries(self.tmp)["svc"]["teardown"], "leave-running")

    def test_tcp_host_default(self):
        self._root("  svc:\n    health:\n      type: tcp\n      port: 9099\n"
                   "    start:\n      command: echo x\n")
        self.assertEqual(dae_infra.load_entries(self.tmp)["svc"]["health"]["host"], "localhost")


# ---------------------------------------------------------------------------
# 6. State files
# ---------------------------------------------------------------------------

class TestStateFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _make_root(self.tmp)

    def tearDown(self):
        _rmtree(self.tmp)

    def test_write_and_read(self):
        state = {"name": "foo", "pid": os.getpid(), "started_at": "2026-01-01T00:00:00Z"}
        dae_infra.write_state(self.tmp, "foo", state)
        got = dae_infra.read_state(self.tmp, "foo")
        self.assertIsNotNone(got)
        self.assertEqual(got["name"], "foo")

    def test_read_missing_returns_none(self):
        self.assertIsNone(dae_infra.read_state(self.tmp, "nonexistent"))

    def test_stale_pid_gc(self):
        dae_infra.write_state(self.tmp, "bar", {"name": "bar", "pid": 999999})
        path = os.path.join(self.tmp, ".engineer", "infra", "bar.json")
        self.assertTrue(os.path.isfile(path))
        self.assertIsNone(dae_infra.read_state(self.tmp, "bar"))
        self.assertFalse(os.path.isfile(path))

    def test_remove_state(self):
        dae_infra.write_state(self.tmp, "baz", {"name": "baz", "pid": os.getpid()})
        dae_infra.remove_state(self.tmp, "baz")
        self.assertIsNone(dae_infra.read_state(self.tmp, "baz"))

    def test_state_dir_created_on_write(self):
        dae_infra.write_state(self.tmp, "new", {"pid": os.getpid()})
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, ".engineer", "infra")))


# ---------------------------------------------------------------------------
# 7. status CLI
# ---------------------------------------------------------------------------

class TestStatusCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.server = socketserver.TCPServer(("127.0.0.1", cls.port),
                                            http.server.BaseHTTPRequestHandler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.tmp = tempfile.mkdtemp()
        _make_root(cls.tmp, _tcp_infra_yml(cls.port, name="web"))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        _rmtree(cls.tmp)

    def test_status_up(self):
        rc, out, _ = _run_cli("status", root=self.tmp)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["web"]["status"], "up")

    def test_status_specific_name(self):
        rc, out, _ = _run_cli("status", "web", root=self.tmp)
        self.assertEqual(rc, 0)
        self.assertIn("web", json.loads(out))

    def test_status_down(self):
        tmp = tempfile.mkdtemp()
        try:
            _make_root(tmp, _tcp_infra_yml(_free_port(), name="dead"))
            rc, out, _ = _run_cli("status", root=tmp)
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out)["dead"]["status"], "down")
        finally:
            _rmtree(tmp)

    def test_status_stale_pid_gc(self):
        tmp = tempfile.mkdtemp()
        try:
            _make_root(tmp, _tcp_infra_yml(_free_port(), name="stale"))
            dae_infra.write_state(tmp, "stale", {"name": "stale", "pid": 999999})
            rc, out, _ = _run_cli("status", root=tmp)
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out)["stale"]["status"], "down")
            self.assertFalse(os.path.isfile(
                os.path.join(tmp, ".engineer", "infra", "stale.json")))
        finally:
            _rmtree(tmp)


# ---------------------------------------------------------------------------
# 8. ensure + teardown CLI
# ---------------------------------------------------------------------------

class TestEnsureTeardown(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.port = _free_port()
        _make_root(self.tmp, _tcp_infra_yml(self.port, name="svc"))

    def tearDown(self):
        _run_cli("teardown", root=self.tmp)
        _rmtree(self.tmp)

    def test_ensure_brings_up(self):
        rc, out, err = _run_cli("ensure", "svc", root=self.tmp)
        self.assertEqual(rc, 0, err)
        self.assertTrue(json.loads(out)["all_up"])
        rc2, out2, _ = _run_cli("status", root=self.tmp)
        self.assertEqual(json.loads(out2)["svc"]["status"], "up")

    def test_ensure_idempotent(self):
        rc, _, _ = _run_cli("ensure", "svc", root=self.tmp)
        self.assertEqual(rc, 0)
        rc2, out2, _ = _run_cli("ensure", "svc", root=self.tmp)
        self.assertEqual(rc2, 0)
        self.assertTrue(json.loads(out2)["all_up"])

    def test_teardown_kills(self):
        _run_cli("ensure", "svc", root=self.tmp)
        rc, out, _ = _run_cli("teardown", root=self.tmp)
        self.assertEqual(rc, 0)
        statuses = {e["name"]: e["status"] for e in json.loads(out)["entries"]}
        self.assertEqual(statuses["svc"], "stopped")

    def test_teardown_not_running(self):
        rc, out, _ = _run_cli("teardown", root=self.tmp)
        self.assertEqual(rc, 0)
        statuses = {e["name"]: e["status"] for e in json.loads(out)["entries"]}
        self.assertEqual(statuses["svc"], "not-running")


# ---------------------------------------------------------------------------
# 9. ensure failure diagnostics
# ---------------------------------------------------------------------------

class TestEnsureFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        _rmtree(self.tmp)

    def test_command_not_found(self):
        _make_root(self.tmp,
                   "  svc:\n    health:\n      type: process\n      pattern: __no_match__\n"
                   "    start:\n      command: __no_such_binary_xyz__ --start\n"
                   "      ready_timeout_s: 3\n")
        rc, out, _ = _run_cli("ensure", "svc", root=self.tmp)
        self.assertNotEqual(rc, 0)
        entry = json.loads(out)["entries"][0]
        self.assertEqual(entry["diagnosis"], "command-not-found")

    def test_ready_timeout(self):
        _make_root(self.tmp,
                   "  svc:\n    health:\n      type: tcp\n      port: %d\n"
                   "      host: 127.0.0.1\n"
                   "    start:\n      command: python3 -c \"import time; time.sleep(60)\"\n"
                   "      ready_timeout_s: 2\n" % _free_port())
        rc, out, _ = _run_cli("ensure", "svc", root=self.tmp)
        self.assertNotEqual(rc, 0)
        self.assertEqual(json.loads(out)["entries"][0]["diagnosis"], "ready-timeout")

    def test_unknown_name(self):
        _make_root(self.tmp)
        rc, out, _ = _run_cli("ensure", "nonexistent", root=self.tmp)
        self.assertNotEqual(rc, 0)
        self.assertFalse(json.loads(out)["all_up"])

    def test_start_exit_nonzero(self):
        _make_root(self.tmp,
                   "  svc:\n    health:\n      type: process\n      pattern: __no_match__\n"
                   "    start:\n      command: python3 -c \"import sys; sys.exit(1)\"\n"
                   "      ready_timeout_s: 5\n")
        rc, out, _ = _run_cli("ensure", "svc", root=self.tmp)
        self.assertNotEqual(rc, 0)
        self.assertIn(json.loads(out)["entries"][0]["diagnosis"],
                      ("start-exit-nonzero", "ready-timeout"))


# ---------------------------------------------------------------------------
# 10. ready_signal detection
# ---------------------------------------------------------------------------

class TestReadySignal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _make_root(self.tmp)

    def tearDown(self):
        _run_cli("teardown", root=self.tmp)
        _rmtree(self.tmp)

    def test_ready_signal_detected(self):
        _make_root(self.tmp,
                   "  svc:\n    health:\n      type: command\n      command: true\n"
                   "    start:\n      command: python3 -c \""
                   "import sys,time; sys.stdout.write('READY\\n'); "
                   "sys.stdout.flush(); time.sleep(30)\"\n"
                   "      ready_signal: READY\n      ready_timeout_s: 5\n")
        rc, out, err = _run_cli("ensure", "svc", root=self.tmp)
        self.assertEqual(rc, 0, err)
        self.assertTrue(json.loads(out)["all_up"])


# ---------------------------------------------------------------------------
# 11. CLI shape
# ---------------------------------------------------------------------------

class TestCLIShape(unittest.TestCase):
    def test_help_exit_zero(self):
        rc, out, _ = _run_cli("--help")
        self.assertEqual(rc, 0)
        for word in ("status", "ensure", "teardown"):
            self.assertIn(word, out)

    def test_unknown_subcommand(self):
        rc, _, _ = _run_cli("foobar")
        self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# 12. _pid_running and _pgid_running helpers
# ---------------------------------------------------------------------------

class TestPidHelpers(unittest.TestCase):
    def test_own_pid_running(self):
        self.assertTrue(dae_infra._pid_running(os.getpid()))

    def test_dead_pid_not_running(self):
        self.assertFalse(dae_infra._pid_running(999999))

    def test_pgid_running_for_new_session(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                start_new_session=True)
        pgid = os.getpgid(proc.pid)
        time.sleep(0.1)
        try:
            self.assertTrue(dae_infra._pgid_running(pgid))
        finally:
            proc.kill(); proc.wait()

    def test_pgid_zero_not_running(self):
        # 0 means "the caller's own group" to killpg -- never a stored pgid.
        self.assertFalse(dae_infra._pgid_running(0))

    def test_pgid_negative_not_running(self):
        self.assertFalse(dae_infra._pgid_running(-1))

    def test_pgid_unparsable_not_running(self):
        # A hand-edited or corrupt state file must not crash read_state.
        self.assertFalse(dae_infra._pgid_running("not-a-pgid"))
        self.assertFalse(dae_infra._pgid_running(None))

    def test_dead_pgid_not_running(self):
        self.assertFalse(dae_infra._pgid_running(999999))

    def test_group_alive_after_its_leader_is_reaped(self):
        # start_background runs with shell=True, and the shell may fork and
        # exit while its children keep running in the same group. That is the
        # reason liveness is tracked per group and not per leader pid.
        proc = subprocess.Popen(
            "%s -c 'import time; time.sleep(30)' & exit 0" % sys.executable,
            shell=True, start_new_session=True)
        pgid = os.getpgid(proc.pid)
        proc.wait()  # leader reaped -- only the backgrounded child is left
        time.sleep(0.1)
        try:
            self.assertFalse(dae_infra._pid_running(pgid))
            self.assertTrue(dae_infra._pgid_running(pgid))
        finally:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                pass

    def test_pgid_running_when_signalling_is_denied(self):
        # EPERM means the group is there and we are merely not allowed to
        # signal it -- that is a live group, not a missing one.
        with mock.patch.object(dae_infra.os, "killpg",
                               side_effect=PermissionError(1, "Operation not permitted")):
            self.assertTrue(dae_infra._pgid_running(4242))


# ---------------------------------------------------------------------------
# 12a. Regression: _pgid_running must not depend on the installed pgrep
# ---------------------------------------------------------------------------

def _busybox_pgrep_dir() -> str:
    """Dir with a `pgrep` that refuses -g the way the busybox applet does:
    usage on stderr, exit 1 -- the same code procps uses for "no matches"."""
    d = tempfile.mkdtemp()
    shim = os.path.join(d, "pgrep")
    with open(shim, "w") as f:
        f.write("#!/bin/sh\n"
                "case \"$1\" in\n"
                "  -g) echo 'pgrep: unrecognized option: g' >&2\n"
                "      echo 'Usage: pgrep [-flanovx] [-s SID|-P PPID|PATTERN]' >&2\n"
                "      exit 1 ;;\n"
                "esac\n"
                "exit 1\n")
    os.chmod(shim, 0o755)
    return d


class TestPgidRunningWithoutProcpsPgrep(unittest.TestCase):
    """Liveness of a process group must not depend on which pgrep is installed.

    The pgrep on PATH here rejects -g, as the busybox applet does in every
    alpine image: it prints usage and exits 1 -- the same code procps uses
    for "no matches".
    """

    def setUp(self):
        shim_dir = _busybox_pgrep_dir()
        self.addCleanup(_rmtree, shim_dir)
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = shim_dir + os.pathsep + old_path
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)

    def _spawn_group(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                start_new_session=True)
        pgid = os.getpgid(proc.pid)
        time.sleep(0.1)
        return proc, pgid

    def _reap(self, proc):
        try:
            proc.kill()
        except OSError:
            pass
        proc.wait()

    def test_live_group_reported_running(self):
        proc, pgid = self._spawn_group()
        self.addCleanup(self._reap, proc)
        self.assertTrue(dae_infra._pgid_running(pgid))

    def test_dead_group_reported_not_running(self):
        proc, pgid = self._spawn_group()
        self._reap(proc)
        self.assertFalse(dae_infra._pgid_running(pgid))

    def test_live_service_state_survives_read(self):
        proc, pgid = self._spawn_group()
        self.addCleanup(self._reap, proc)
        tmp = tempfile.mkdtemp()
        self.addCleanup(_rmtree, tmp)
        dae_infra.write_state(tmp, "svc", {"name": "svc", "pid": proc.pid,
                                           "pgid": pgid, "started_at": "now"})
        self.assertIsNotNone(dae_infra.read_state(tmp, "svc"))
        self.assertTrue(os.path.isfile(
            os.path.join(tmp, ".engineer", "infra", "svc.json")))


# ---------------------------------------------------------------------------
# 13. _diagnose_start
# ---------------------------------------------------------------------------

class TestDiagnoseStart(unittest.TestCase):
    def test_command_not_found(self):
        self.assertEqual(
            dae_infra._diagnose_start("__no_such_binary_xyz__", {"type": "process", "pattern": "foo"}),
            "command-not-found")

    def test_valid_command_no_diag(self):
        self.assertEqual(
            dae_infra._diagnose_start("python3 --version", {"type": "process", "pattern": "foo"}),
            "")

    def test_port_in_use(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)
        try:
            self.assertEqual(
                dae_infra._diagnose_start("python3 --version",
                                          {"type": "tcp", "host": "127.0.0.1", "port": port}),
                "port-in-use")
        finally:
            srv.close()


# ---------------------------------------------------------------------------
# 14. Multi-entry teardown by name
# ---------------------------------------------------------------------------

class TestMultiEntry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.port1, self.port2 = _free_port(), _free_port()
        _make_root(self.tmp,
                   _tcp_infra_yml(self.port1, name="svc1") +
                   _tcp_infra_yml(self.port2, name="svc2"))

    def tearDown(self):
        _run_cli("teardown", root=self.tmp)
        _rmtree(self.tmp)

    def test_teardown_specific_name(self):
        _run_cli("ensure", "svc1", root=self.tmp)
        rc, out, _ = _run_cli("teardown", "svc1", root=self.tmp)
        self.assertEqual(rc, 0)
        names = {e["name"] for e in json.loads(out)["entries"]}
        self.assertIn("svc1", names)
        self.assertNotIn("svc2", names)

    def test_status_multiple(self):
        rc, out, _ = _run_cli("status", root=self.tmp)
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("svc1", data)
        self.assertIn("svc2", data)


if __name__ == "__main__":
    unittest.main()
