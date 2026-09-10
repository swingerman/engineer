#!/usr/bin/env python3
"""dae_infra.py — probe, auto-start, and teardown of declared infrastructure.

Usage:
    dae_infra.py status   [--root DIR] [NAME ...]
    dae_infra.py ensure   [--root DIR] NAME [NAME ...]
    dae_infra.py teardown [--root DIR] [NAME ...]

Exit codes: 0 success; 1 ensure failure; 3 usage error.
"""
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

import dae_resolve

DEFAULT_HTTP_TIMEOUT = 5
DEFAULT_TCP_TIMEOUT = 2
DEFAULT_CMD_TIMEOUT = 5
DEFAULT_READY_TIMEOUT = 60
POLL_INTERVAL = 0.5
MAX_OUTPUT_LINES = 20


def probe_http(url: str, timeout_s: int = DEFAULT_HTTP_TIMEOUT) -> bool:
    """GET url; return True if 2xx or 3xx."""
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def probe_tcp(host: str, port: int, timeout_s: int = DEFAULT_TCP_TIMEOUT) -> bool:
    """Try to open a TCP connection; True if connects."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(timeout_s)
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def probe_process(pattern: str) -> bool:
    """pgrep -f <pattern>; True if any process matches."""
    try:
        return subprocess.run(["pgrep", "-f", pattern],
                              capture_output=True, timeout=5).returncode == 0
    except Exception:
        return False


def probe_command(command: str, timeout_s: int = DEFAULT_CMD_TIMEOUT) -> bool:
    """Run shell command; True if exit 0 within timeout."""
    try:
        return subprocess.run(command, shell=True, capture_output=True,
                              timeout=timeout_s).returncode == 0
    except Exception:
        return False


def make_health_probe(health: dict):
    """Return a zero-arg callable that probes according to the health dict."""
    htype = health.get("type")
    if htype == "http":
        url, t = health["url"], health.get("timeout_s", DEFAULT_HTTP_TIMEOUT)
        return lambda: probe_http(url, t)
    if htype == "tcp":
        host, port = health.get("host", "localhost"), health["port"]
        t = health.get("timeout_s", DEFAULT_TCP_TIMEOUT)
        return lambda: probe_tcp(host, port, t)
    if htype == "process":
        pat = health["pattern"]
        return lambda: probe_process(pat)
    if htype == "command":
        cmd, t = health["command"], health.get("timeout_s", DEFAULT_CMD_TIMEOUT)
        return lambda: probe_command(cmd, t)
    return lambda: False


def _state_dir(root: str) -> str:
    return os.path.join(root, ".engineer", "infra")


def write_state(root: str, name: str, state: dict) -> None:
    d = _state_dir(root)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def read_state(root: str, name: str):
    """Read state; GC stale file if process group is gone; return None if absent/stale."""
    path = os.path.join(_state_dir(root), name + ".json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        return None
    # Prefer PGID liveness (shell=True leaves children in the same group)
    pgid, pid = state.get("pgid"), state.get("pid")
    alive = _pgid_running(pgid) if pgid is not None else (
        _pid_running(pid) if pid is not None else False)
    if not alive:
        try:
            os.remove(path)
        except OSError:
            pass
        return None
    return state


def remove_state(root: str, name: str) -> None:
    try:
        os.remove(os.path.join(_state_dir(root), name + ".json"))
    except OSError:
        pass


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _pgid_running(pgid: int) -> bool:
    """True if any process in the group is running.

    Asks the kernel, not an external pgrep: the busybox applet that ships as
    pgrep in alpine images rejects -g with exit 1 -- the very code procps uses
    for "no matches" -- so a nonzero exit cannot be read as an answer.
    """
    try:
        pgid = int(pgid)
    except (TypeError, ValueError):
        return False
    if pgid <= 0:
        # killpg(0) would signal our own group and always report "alive".
        return False
    try:
        os.killpg(pgid, 0)
        return True
    except PermissionError:
        return True  # group exists, we are just not allowed to signal it
    except OSError:
        return False


def load_entries(root: str) -> dict:
    """Return {name: {health, start, teardown}} with defaults applied."""
    manifest_path = os.path.join(root, ".engineer", "manifest.yml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        text = f.read()
    manifest = dae_resolve.read_manifest(text)
    infra = manifest.get("infra") or {}
    default_td = infra.get("default_teardown", "leave-running")
    entries = {}
    for name, entry in infra.items():
        if name == "default_teardown" or not isinstance(entry, dict):
            continue
        health = dict(entry.get("health") or {})
        if health.get("type") == "http":
            health.setdefault("timeout_s", DEFAULT_HTTP_TIMEOUT)
        elif health.get("type") == "tcp":
            health.setdefault("host", "localhost")
            health.setdefault("timeout_s", DEFAULT_TCP_TIMEOUT)
        elif health.get("type") == "command":
            health.setdefault("timeout_s", DEFAULT_CMD_TIMEOUT)
        start = dict(entry.get("start") or {})
        start.setdefault("background", True)
        start.setdefault("ready_timeout_s", DEFAULT_READY_TIMEOUT)
        entries[name] = {
            "health": health,
            "start": start,
            "teardown": entry.get("teardown") or default_td,
        }
    return entries


class StartFailure(Exception):
    def __init__(self, diagnosis, detail, last_output, elapsed_s, suggested_fix=""):
        self.diagnosis = diagnosis
        self.detail = detail
        self.last_output = last_output
        self.elapsed_s = elapsed_s
        self.suggested_fix = suggested_fix
        super().__init__(detail)


_FIX = {
    "command-not-found": "Install '{0}' or ensure it is on PATH",
    "port-in-use": "Stop the existing process using this port before starting",
    "ready-timeout": "Check start command and health probe; increase ready_timeout_s if needed",
    "start-exit-nonzero": "Check the start command for errors; review last_output for details",
}


def _suggested_fix(diag: str, cmd: str) -> str:
    tmpl = _FIX.get(diag, "Check logs for details")
    return tmpl.format(cmd.split()[0] if cmd.strip() else cmd)


def _diagnose_start(command: str, health: dict) -> str:
    """Pre-start diagnosis: command-not-found or port-in-use."""
    first = command.split()[0] if command.strip() else ""
    if first and shutil.which(first) is None:
        return "command-not-found"
    htype = health.get("type")
    if htype in ("tcp", "http"):
        port = health.get("port")
        if not port and htype == "http":
            m = re.search(r":(\d+)", (health.get("url", "")).split("//")[-1])
            if m:
                port = int(m.group(1))
        host = health.get("host", "localhost")
        if port and probe_tcp(host, int(port), timeout_s=1):
            return "port-in-use"
    return ""


def start_background(command: str, ready_signal, ready_timeout_s: int,
                     health_probe, methodology_root: str) -> dict:
    """Spawn command; poll for ready; return {pid, pgid, started_at, last_output}."""
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.monotonic()
    output_lines = []
    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=True,
                            cwd=methodology_root)
    try:
        os.set_blocking(proc.stdout.fileno(), False)
    except (AttributeError, OSError):
        pass
    ready_re = re.compile(ready_signal) if ready_signal else None
    found_ready = False
    while True:
        elapsed = time.monotonic() - t0
        try:
            chunk = proc.stdout.read(4096)
            if chunk:
                for line in chunk.decode("utf-8", errors="replace").splitlines():
                    output_lines.append(line)
                    if len(output_lines) > MAX_OUTPUT_LINES * 2:
                        output_lines = output_lines[-MAX_OUTPUT_LINES:]
                    if ready_re and ready_re.search(line):
                        found_ready = True
        except (BlockingIOError, OSError):
            pass
        if found_ready:
            break
        ret = proc.poll()
        if ret is not None and ret != 0:
            raise StartFailure("start-exit-nonzero",
                               "Process exited with code %d after %.1fs" % (ret, elapsed),
                               output_lines[-MAX_OUTPUT_LINES:], elapsed,
                               _suggested_fix("start-exit-nonzero", command))
        if not ready_re:
            try:
                if health_probe():
                    found_ready = True
                    break
            except Exception:
                pass
        if elapsed >= ready_timeout_s:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except OSError:
                try:
                    proc.kill()
                except OSError:
                    pass
            raise StartFailure("ready-timeout",
                               "Not ready after %.1fs (timeout=%ds)" % (elapsed, ready_timeout_s),
                               output_lines[-MAX_OUTPUT_LINES:], elapsed,
                               _suggested_fix("ready-timeout", command))
        time.sleep(POLL_INTERVAL)
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = proc.pid
    return {"pid": proc.pid, "pgid": pgid, "started_at": started_at,
            "last_output": output_lines[-MAX_OUTPUT_LINES:]}


def _find_root(root_arg=None) -> str:
    if root_arg:
        return os.path.abspath(root_arg)
    root, _ = dae_resolve.find_methodology_root(os.getcwd())
    if root is None:
        sys.stderr.write("error: no .engineer/manifest.yml found walking up from cwd\n")
        sys.exit(3)
    return root


def _parse_common(argv):
    """Return (root_arg, names, quiet) from [--root DIR] [--quiet] [NAME ...]."""
    args = list(argv)
    root_arg, quiet = None, False
    if "--quiet" in args:
        quiet = True
        args.remove("--quiet")
    if "--root" in args:
        idx = args.index("--root")
        if idx + 1 >= len(args):
            sys.stderr.write("error: --root requires a directory argument\n")
            sys.exit(3)
        root_arg = args[idx + 1]
        del args[idx:idx + 2]
    return root_arg, args, quiet


def _probe_entry(root: str, name: str, health: dict) -> dict:
    state = read_state(root, name)
    try:
        up = make_health_probe(health)()
    except Exception:
        up = False
    return {
        "status": "up" if up else "down",
        "pid": state.get("pid") if state else None,
        "started_at": state.get("started_at") if state else None,
    }


def cmd_status(argv):
    root_arg, names, _ = _parse_common(argv)
    root = _find_root(root_arg)
    entries = load_entries(root)
    selected = {n: entries[n] for n in names if n in entries} if names else entries
    result = {name: _probe_entry(root, name, e["health"]) for name, e in selected.items()}
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_ensure(argv):
    root_arg, names, _ = _parse_common(argv)
    root = _find_root(root_arg)
    entries = load_entries(root)
    report, all_up = [], True
    for name in names:
        if name not in entries:
            report.append({"name": name, "status": "start-failed", "diagnosis": "unknown",
                           "detail": "No infra entry named %r in manifest" % name,
                           "last_output": [], "elapsed_s": 0.0,
                           "suggested_fix": "Add an infra.%s entry to the manifest" % name})
            all_up = False
            break
        entry = entries[name]
        health, start_cfg = entry["health"], entry["start"]
        probe = make_health_probe(health)
        already_up = False
        try:
            already_up = probe()
        except Exception:
            pass
        if already_up:
            state = read_state(root, name)
            report.append({"name": name, "status": "up",
                           "pid": state.get("pid") if state else None,
                           "started_at": state.get("started_at") if state else None})
            continue
        command = start_cfg["command"]
        pre = _diagnose_start(command, health)
        if pre in ("command-not-found", "port-in-use"):
            report.append({"name": name, "status": "start-failed", "diagnosis": pre,
                           "detail": "Pre-start check failed: %s" % pre,
                           "last_output": [], "elapsed_s": 0.0,
                           "suggested_fix": _suggested_fix(pre, command)})
            all_up = False
            break
        try:
            sd = start_background(command, start_cfg.get("ready_signal"),
                                  start_cfg.get("ready_timeout_s", DEFAULT_READY_TIMEOUT),
                                  probe, root)
        except StartFailure as sf:
            report.append({"name": name, "status": "start-failed", "diagnosis": sf.diagnosis,
                           "detail": sf.detail, "last_output": sf.last_output,
                           "elapsed_s": sf.elapsed_s, "suggested_fix": sf.suggested_fix})
            all_up = False
            break
        write_state(root, name, {"name": name, "pid": sd["pid"], "pgid": sd["pgid"],
                                 "command": command, "started_at": sd["started_at"],
                                 "health": health})
        report.append({"name": name, "status": "up", "pid": sd["pid"],
                       "started_at": sd["started_at"]})
    json.dump({"entries": report, "all_up": all_up}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if all_up else 1


def cmd_teardown(argv):
    root_arg, names, _ = _parse_common(argv)
    root = _find_root(root_arg)
    entries = load_entries(root)
    if not names:
        names = [n for n, e in entries.items() if e.get("teardown") in ("session-end", "always")]
    report = []
    for name in names:
        state = read_state(root, name)
        if state is None:
            report.append({"name": name, "status": "not-running", "error": None})
            continue
        error = None
        try:
            pgid, pid = state.get("pgid"), state.get("pid")
            if pgid:
                os.killpg(pgid, signal.SIGTERM)
            elif pid:
                os.kill(pid, signal.SIGTERM)
        except OSError as e:
            error = str(e)
        remove_state(root, name)
        report.append({"name": name, "status": "stopped", "error": error})
    json.dump({"entries": report}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


USAGE = ("usage:\n"
         "  dae_infra.py status   [--root DIR] [NAME ...]\n"
         "  dae_infra.py ensure   [--root DIR] NAME [NAME ...]\n"
         "  dae_infra.py teardown [--root DIR] [NAME ...]\n")
COMMANDS = {"status": cmd_status, "ensure": cmd_ensure, "teardown": cmd_teardown}


def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        sys.stdout.write(USAGE)
        return 0
    sub = args[0]
    if sub not in COMMANDS:
        sys.stderr.write("error: unknown sub-command %r\n%s" % (sub, USAGE))
        return 3
    return COMMANDS[sub](args[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
