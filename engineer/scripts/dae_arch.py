#!/usr/bin/env python3
"""dae_arch.py — charter architecture fitness checker.

Reads the `architecture:` section of .engineer/manifest.yml and checks the
project against it: dependency layering, cycles, forbidden patterns, file naming,
and file size. Reports violations and exits non-zero if any are found — it is a
gate, like a test.

Usage:
  dae_arch.py [START_DIR]            check changed files vs. the base branch
  dae_arch.py --full [START_DIR]     check every tracked file
  dae_arch.py --format json [...]    machine-readable output

Exit codes:
    0  no violations
    1  violations found
    2  no manifest / no architecture section
    3  usage error
"""
import json
import os
import re
import subprocess
import sys

import dae_resolve

SOURCE_EXTENSIONS = (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")


def _glob_to_regex(pattern):
    """Compile a gitignore-style path glob to an anchored regex.

    `**` spans path segments (including zero); `*` and `?` stay within one.
    """
    out = []
    i = 0
    while i < len(pattern):
        if pattern[i:i + 2] == "**":
            out.append(".*")
            i += 2
            if i < len(pattern) and pattern[i] == "/":
                i += 1  # `**/` also matches zero directories
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def _compile_globs(patterns):
    """A list of glob strings -> a list of compiled regexes."""
    return [_glob_to_regex(p) for p in patterns]


def _match_any(path, compiled_globs):
    """True if `path` matches any compiled glob (empty list -> matches all)."""
    if not compiled_globs:
        return True
    return any(g.match(path) for g in compiled_globs)


def _git(root, *args):
    """Run a git command in `root`; return stdout text ('' on failure)."""
    try:
        out = subprocess.run(["git", "-C", root, *args],
                             capture_output=True, text=True, check=True)
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def files_in_scope(root, full):
    """Repo-relative source file paths to check.

    full=False -> files changed vs. the base branch's merge-base; full=True ->
    every tracked file. Only SOURCE_EXTENSIONS are returned.
    """
    if full:
        names = _git(root, "ls-files").splitlines()
    else:
        base = (_git(root, "rev-parse", "--abbrev-ref",
                     "origin/HEAD").strip() or "origin/main")
        names = _git(root, "diff", "--name-only", "--merge-base",
                     base).splitlines()
        if not names:
            names = _git(root, "ls-files").splitlines()  # no diff -> full
    return [n for n in names if n.endswith(SOURCE_EXTENSIONS)]


def _read_lines(root, rel):
    """Lines of a repo-relative file ([] if unreadable)."""
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except OSError:
        return []


def check_forbidden(root, files, rules):
    """Flag lines matching a forbidden pattern within the rule's path scope."""
    violations = []
    for rule in rules:
        pat = re.compile(rule["pattern"])
        globs = _compile_globs(rule.get("paths", []))
        reason = rule.get("reason", "matches forbidden pattern %r" % rule["pattern"])
        for f in files:
            if not _match_any(f, globs):
                continue
            for n, line in enumerate(_read_lines(root, f), 1):
                if pat.search(line):
                    violations.append((f, n, "forbidden_patterns", reason))
    return violations


def check_naming(files, rules):
    """Flag files whose basename fails the rule's filename regex."""
    violations = []
    for rule in rules:
        globs = _compile_globs(rule.get("paths", []))
        name_re = re.compile(rule["filename_must_match"])
        reason = rule.get("reason",
                          "filename must match %r" % rule["filename_must_match"])
        for f in files:
            if not _match_any(f, globs):
                continue
            if not name_re.search(os.path.basename(f)):
                violations.append((f, 0, "naming", reason))
    return violations


def check_file_size(root, files, cfg):
    """Flag files whose line count exceeds the nearest matching max_lines cap."""
    default = cfg.get("max_lines")
    overrides = [(_compile_globs(ov["paths"]), ov["max_lines"])
                 for ov in cfg.get("overrides", [])]
    violations = []
    for f in files:
        cap = default
        for globs, limit in overrides:
            if _match_any(f, globs):
                cap = limit
        if cap is None:
            continue
        n = len(_read_lines(root, f))
        if n > cap:
            violations.append((f, n, "file_size", "%d lines > max %d" % (n, cap)))
    return violations


_PY_IMPORT = re.compile(r"^\s*(?:from\s+(\.[\w.]*|[\w.]+)\s+import|"
                        r"import\s+([\w.]+))", re.MULTILINE)
_JS_IMPORT = re.compile(r"""(?:from|require\(|import)\s*['"]([^'"]+)['"]""")


def extract_imports(rel_path, text):
    """The import specifiers in a source file (language by extension)."""
    if rel_path.endswith(".py"):
        return [a or b for a, b in _PY_IMPORT.findall(text)]
    return _JS_IMPORT.findall(text)


def _resolve_python(spec, importer, known):
    """Resolve a Python import specifier to a repo-relative file, or None.

    Handles project-rooted dotted modules (`pkg.mod` -> `pkg/mod.py`) and
    relative imports (`.relmod` -> a sibling of the importing file).
    """
    if spec.startswith("."):
        depth = len(spec) - len(spec.lstrip("."))
        base = importer
        for _ in range(depth):
            base = os.path.dirname(base)
        tail = spec.lstrip(".").replace(".", "/")
        stem = os.path.join(base, tail) if tail else base
    else:
        stem = spec.replace(".", "/")
    for cand in (stem + ".py", os.path.join(stem, "__init__.py")):
        norm = os.path.normpath(cand)
        if norm in known:
            return norm
    return None


def _resolve_js(spec, importer, known):
    """Resolve a JS/TS *relative* import to a repo-relative file, or None.

    Bare specifiers (packages) return None — they are not project layers.
    """
    if not spec.startswith("."):
        return None
    stem = os.path.normpath(os.path.join(os.path.dirname(importer), spec))
    exts = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
    cands = [stem + e for e in exts]
    cands += [os.path.join(stem, "index" + e) for e in exts]
    for cand in cands:
        norm = os.path.normpath(cand)
        if norm in known:
            return norm
    return None


def _layer_of(path, layer_globs):
    """The layer name whose globs match `path`, or None."""
    for name, globs in layer_globs:
        if _match_any(path, globs):
            return name
    return None


def _build_import_graph(root, all_files):
    """Build a directed graph of all project file imports.

    Returns {file: [target_file, ...]} where file and target_file are
    repo-relative paths to project source files.
    """
    graph = {}
    known = {os.path.normpath(f) for f in all_files}
    for f in all_files:
        text = "\n".join(_read_lines(root, f))
        graph[f] = []
        for spec in extract_imports(f, text):
            if f.endswith(".py"):
                target = _resolve_python(spec, f, known)
            else:
                target = _resolve_js(spec, f, known)
            if target is not None:
                graph[f].append(target)
    return graph


def check_cycles_in_imports(root, all_files):
    """Flag dependency cycles in the import graph.

    Returns violations as (file, 0, "cycles", message) tuples.
    """
    graph = _build_import_graph(root, all_files)
    cycles = check_cycles(graph)
    violations = []
    for cycle in cycles:
        cycle_str = " -> ".join(cycle) + " -> " + cycle[0]
        message = "circular dependency: %s" % cycle_str
        # Report the cycle on the first file in it
        if cycle:
            violations.append((cycle[0], 0, "cycles", message))
    return violations


def check_layers(root, files, layer_rules, all_files):
    """Flag imports that cross a `may_not_import` layer boundary."""
    layer_globs = [(r["name"], _compile_globs(r["paths"])) for r in layer_rules]
    forbidden = {r["name"]: set(r.get("may_not_import", [])) for r in layer_rules}
    known = {os.path.normpath(f) for f in all_files}
    violations = []
    for f in files:
        src_layer = _layer_of(f, layer_globs)
        if src_layer is None or not forbidden.get(src_layer):
            continue
        text = "\n".join(_read_lines(root, f))
        for spec in extract_imports(f, text):
            if f.endswith(".py"):
                target = _resolve_python(spec, f, known)
            else:
                target = _resolve_js(spec, f, known)
            if target is None:
                continue  # external / unresolvable — not a project layer
            tgt_layer = _layer_of(target, layer_globs)
            if tgt_layer in forbidden[src_layer]:
                violations.append((f, 0, "layers",
                                   "%s must not import %s (%s)"
                                   % (src_layer, tgt_layer, target)))
    return violations


def audit_rules(root, files, rules):
    """Run every configured check over `files`; return all violations."""
    violations = []
    if rules.get("forbidden_patterns"):
        violations += check_forbidden(root, files, rules["forbidden_patterns"])
    if rules.get("naming"):
        violations += check_naming(files, rules["naming"])
    if rules.get("file_size"):
        violations += check_file_size(root, files, rules["file_size"])
    # Both check_layers and check_cycles_in_imports need the full file list.
    # Hoist the (subprocess-backed) call so it runs at most once.
    all_files = files_in_scope(root, full=True)
    if rules.get("layers"):
        violations += check_layers(root, files, rules["layers"], all_files)
    # Always check for cycles in the import graph
    violations += check_cycles_in_imports(root, all_files)
    return violations


def audit(start_dir, full):
    """Resolve the project, run the checks. Returns (root, rules, violations)
    or (None, None, None) if there is no manifest / no architecture section.
    """
    result = dae_resolve.resolve(start_dir)
    if result is None:
        return None, None, None
    rules = (result["manifest"] or {}).get("architecture")
    if not rules:
        return result["methodology_root"], None, None
    root = result["methodology_root"]
    files = files_in_scope(root, full)
    return root, rules, audit_rules(root, files, rules)


def graph(start_dir):
    """Component graph: layer nodes + aggregated layer->layer import edges.

    Reuses the file-level import graph the fitness checks already build (and
    otherwise discard). Nodes are the manifest's architecture layers; edges are
    real file->file imports rolled up to layer->layer (kind "actual"), plus each
    layer's declared `may_not_import` rules (kind "forbidden"; count>0 means the
    rule is actually violated). Returns {arch_supported, layers, edges}; graceful
    empty when there is no `architecture.layers` section.
    """
    result = dae_resolve.resolve(start_dir)
    if result is None:
        return {"arch_supported": False, "layers": [], "edges": []}
    rules = (result["manifest"] or {}).get("architecture")
    root = result["methodology_root"]
    if not rules or not rules.get("layers"):
        return {"arch_supported": False, "layers": [], "edges": []}
    layer_rules = rules["layers"]
    layer_globs = [(r["name"], _compile_globs(r.get("paths", []))) for r in layer_rules]
    forbidden = {r["name"]: set(r.get("may_not_import", [])) for r in layer_rules}

    all_files = files_in_scope(root, True)
    igraph = _build_import_graph(root, all_files)  # {file: [target, ...]}
    cyclic = set()
    for cycle in check_cycles(igraph):
        cyclic.update(cycle)

    file_count = {r["name"]: 0 for r in layer_rules}
    in_cycle = {r["name"]: False for r in layer_rules}
    edge_counts = {}  # (src_layer, dst_layer) -> import count
    for f in all_files:
        src = _layer_of(f, layer_globs)
        if src is None:
            continue
        file_count[src] += 1
        if f in cyclic:
            in_cycle[src] = True
        for tgt in igraph.get(f, []):
            dst = _layer_of(tgt, layer_globs)
            if dst is None or dst == src:
                continue
            edge_counts[(src, dst)] = edge_counts.get((src, dst), 0) + 1

    layers = [{
        "name": r["name"],
        "paths": r.get("paths", []),
        "may_not_import": r.get("may_not_import", []),
        "file_count": file_count[r["name"]],
        "in_cycle": in_cycle[r["name"]],
    } for r in layer_rules]

    edges, seen = [], set()
    for (src, dst), n in sorted(edge_counts.items()):
        edges.append({"src": src, "dst": dst,
                      "kind": "forbidden" if dst in forbidden.get(src, set()) else "actual",
                      "count": n})
        seen.add((src, dst))
    # declared forbidden edges that are NOT violated (count 0) — show the rule
    for r in layer_rules:
        for dst in r.get("may_not_import", []):
            if (r["name"], dst) not in seen:
                edges.append({"src": r["name"], "dst": dst, "kind": "forbidden", "count": 0})

    return {"arch_supported": True, "layers": layers, "edges": edges}


def main(argv):
    args = list(argv)
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if "--graph" in args:
        args.remove("--graph")
        start_dir = args[0] if args else os.getcwd()
        json.dump(graph(start_dir), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    fmt = "text"
    if "--format" in args:
        i = args.index("--format")
        fmt = args[i + 1] if i + 1 < len(args) else "text"
        del args[i:i + 2]
    full = False
    if "--full" in args:
        full = True
        args.remove("--full")
    if len(args) > 1:
        sys.stderr.write("usage: dae_arch.py [--full] [--format json] [START_DIR]\n")
        return 3
    start_dir = args[0] if args else os.getcwd()

    root, rules, violations = audit(start_dir, full)
    if root is None:
        sys.stderr.write("no .engineer/manifest.yml found — run /engineer.onboard\n")
        return 2
    if rules is None:
        sys.stderr.write("no `architecture:` section in the manifest — nothing to check\n")
        return 2

    if fmt == "json":
        json.dump([{"file": f, "line": n, "kind": k, "message": m}
                   for f, n, k, m in violations], sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for kind in ("layers", "cycles", "forbidden_patterns", "naming", "file_size"):
            hits = [v for v in violations if v[2] == kind]
            if hits:
                sys.stdout.write("\n%s (%d):\n" % (kind, len(hits)))
                for f, n, _, m in hits:
                    loc = "%s:%d" % (f, n) if n else f
                    sys.stdout.write("  %s — %s\n" % (loc, m))
        sys.stdout.write("\n%d violation(s)\n" % len(violations))
    return 1 if violations else 0


def check_cycles(graph):
    """Find dependency cycles via Tarjan's strongly-connected-components.

    graph - {node: [neighbor, ...]}.
    Returns a sorted list of cycles; each cycle is a sorted list of nodes.
    An SCC of size > 1, or a size-1 SCC with a self-loop, counts as a cycle.
    """
    index_counter = [0]
    stack = []
    on_stack = {}
    index = {}
    lowlink = {}
    cycles = []

    def strongconnect(v):
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True
        for w in graph.get(v, []):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w):
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            component = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                component.append(w)
                if w == v:
                    break
            if len(component) > 1 or (len(component) == 1 and v in graph.get(v, [])):
                cycles.append(sorted(component))

    for node in list(graph):
        if node not in index:
            strongconnect(node)
    return sorted(cycles)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
