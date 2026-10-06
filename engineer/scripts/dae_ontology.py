#!/usr/bin/env python3
"""dae_ontology.py — deterministic constraint checks over DAE's artifact graph.

DAE already has an ontology: entities (Feature, AC, SpecScenario, Handoff,
Checkpoint, RoadmapItem), relations between them (`covers`, `parent_feature`,
`verifies`), and constraints on both. Until now it lived as an English rule
table in the `consistency-check` skill and was evaluated by an LLM reading
prose — which meant it ran when someone remembered to ask.

This script is the ledger position: the mechanical rows of that table, executed
against the artifacts on disk, cheaply enough to run at every checkpoint exit.
The judgment rows ("are these ACs in domain language?", "do they cover the
outcome?") stay with the skill — they are not mechanical and this script does
not pretend otherwise.

Constraint vocabulary is borrowed from OWL because naming a check precisely is
most of the value — it makes the *missing* checks obvious:

  enumeration  a property's value must come from a fixed set
  functional   at most one holder of a value ("exactly one father")
  inverse      two properties must agree in both directions
  transitive   a relation that chains, and therefore must not cycle
  disjoint     two roles that must not be filled by the same individual
  closure      every X must be reachable from some Y (coverage)

Read-only. Never mutates an artifact.

Usage:
  dae_ontology.py <feature-dir>         check one feature
  dae_ontology.py --project [START_DIR] check project-wide invariants
  dae_ontology.py ... --json            machine-readable findings

Exit codes:
  0  no error-severity findings (warnings may be present)
  1  at least one error-severity finding
  2  bad usage / target not found
"""
import json
import os
import re
import sys

import dae_handoff
import dae_resolve

# --- the vocabulary -------------------------------------------------------

# enumeration: a Feature's lifecycle states. `merged-unverified` is written by
# dae_reconcile when work shipped without its ACs verified.
FEATURE_STATUSES = {"parked", "ready", "in-progress", "done",
                    "merged-unverified"}
# enumeration: assignee — who executes the next checkpoint.
ASSIGNEES = {"human", "local", "cloud"}
# enumeration: the canonical pipeline stops (mirrors dae_progress.CHECKPOINTS).
CHECKPOINTS = {0, 1.5, 2, 3, 4, 5, 6, 7, 8}
# enumeration: roadmap horizons (mirrors references/roadmap.md).
HORIZONS = {"now", "next", "later"}

_AC_HEADING_RE = re.compile(r"^##\s+AC-(\d+)\b", re.MULTILINE)
_AC_TAG_RE = re.compile(r"@AC-(\d+)\b")
_FEATURE_DIR_RE = re.compile(r"^(\d+)-[a-z0-9][a-z0-9-]*$")
_NUM_PREFIX_RE = re.compile(r"^\d+-")

# Trunk branches are shared by construction — a multi-repo umbrella runs every
# feature off `master` (wipist), so branch uniqueness cannot apply to them.
TRUNK_BRANCHES = {"master", "main", "develop", "trunk"}


def bare_slug(name):
    """A feature identifier with its numeric prefix removed.

    Both `012-washer-tracking` and `washer-tracking` are used in the wild for
    the same feature — `slug:` and `parent_feature:` fields frequently carry the
    bare form while the folder carries the numbered one. Identity comparisons
    normalize through this rather than demanding one convention.
    """
    return _NUM_PREFIX_RE.sub("", name or "")


def finding(severity, constraint, entity, message):
    return {"severity": severity, "constraint": constraint,
            "entity": entity, "message": message}


def _abbrev(items, limit=8):
    """Join a list for a one-line message, eliding a long tail."""
    if len(items) <= limit:
        return ", ".join(items)
    return "%s … (+%d more)" % (", ".join(items[:limit]), len(items) - limit)


# --- loading --------------------------------------------------------------

def _read(path):
    """File text, or None if absent/unreadable."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def load_feature(feature_dir):
    """Frontmatter dict for a feature, {} if unparseable, None if no feature.md."""
    text = _read(os.path.join(feature_dir, "feature.md"))
    if text is None:
        return None
    block = dae_resolve.extract_frontmatter(text)
    if block is None:
        return {}
    try:
        data = dae_resolve.read_manifest(block)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def ac_ids(feature_dir):
    """AC numbers declared in acs.md, as a sorted list. [] if no acs.md."""
    text = _read(os.path.join(feature_dir, "acs.md"))
    if text is None:
        return []
    return sorted({int(n) for n in _AC_HEADING_RE.findall(text)})


def spec_ac_refs(feature_dir):
    """AC numbers referenced by `@AC-N` Gherkin tags in spec.md.

    Reads spec.md rather than .build/spec.json deliberately: the IR shape
    (references/spec-ir.md) carries no tags, and widening it would change a
    contract several consumers read plus churn the dae_gherkin fingerprint.
    ponytail: regex over tag lines; if scenario-level tag semantics ever matter
    beyond coverage, add tags to the IR and read them from there instead.
    """
    text = _read(os.path.join(feature_dir, "spec.md"))
    if text is None:
        return None  # distinct from "spec.md exists but tags nothing"
    return sorted({int(n) for n in _AC_TAG_RE.findall(text)})


# --- feature-scope checks -------------------------------------------------

def check_feature(feature_dir):
    """Constraint findings for one feature folder."""
    out = []
    name = os.path.basename(os.path.normpath(feature_dir))
    fm = load_feature(feature_dir)
    if fm is None:
        return [finding("error", "existence", name, "no feature.md")]

    # enumeration — status, assignee, autonomy_level
    status = fm.get("status")
    if status is not None and status not in FEATURE_STATUSES:
        out.append(finding(
            "error", "enumeration", name,
            "status: %r not in %s" % (status, sorted(FEATURE_STATUSES))))
    assignee = fm.get("assignee")
    if assignee is not None and assignee not in ASSIGNEES:
        out.append(finding(
            "error", "enumeration", name,
            "assignee: %r not in %s" % (assignee, sorted(ASSIGNEES))))
    level = fm.get("autonomy_level")
    if level is not None and level not in dae_resolve.AUTONOMY_LEVELS:
        out.append(finding(
            "error", "enumeration", name,
            "autonomy_level: %r not in %s"
            % (level, sorted(dae_resolve.AUTONOMY_LEVELS))))

    # functional — a non-parked feature has exactly one autonomy_level
    if status and status != "parked" and not level:
        out.append(finding(
            "error", "functional", name,
            "status: %s requires an autonomy_level" % status))

    # functional — slug agrees with the folder it lives in, in either the
    # numbered or the bare form
    slug = fm.get("slug")
    if slug and slug != name and bare_slug(slug) != bare_slug(name):
        out.append(finding(
            "error", "functional", name,
            "slug: %r does not match folder %r" % (slug, name)))

    # closure — every AC is covered by at least one spec scenario, and every
    # tagged AC exists. This is the check prose cannot do: it is a join.
    acs = ac_ids(feature_dir)
    refs = spec_ac_refs(feature_dir)
    declared = fm.get("ac_count")
    if acs and isinstance(declared, int) and declared != len(acs):
        out.append(finding(
            "error", "functional", name,
            "ac_count: %d but acs.md declares %d ACs" % (declared, len(acs))))
    if acs and refs is not None:
        if not refs:
            # spec.md exists but tags nothing — this project isn't using the
            # @AC-N convention, so per-AC errors would be pure noise. Say it
            # once, as a warning: adopting the convention is what unlocks the
            # coverage join, but not adopting it is a choice, not a defect.
            out.append(finding(
                "warning", "closure", name,
                "spec.md carries no @AC-N tags — AC↔scenario coverage cannot "
                "be checked for this feature"))
        else:
            uncovered = [n for n in acs if n not in refs]
            if uncovered:
                out.append(finding(
                    "error", "closure", name,
                    "ACs with no @AC-N scenario in spec.md: %s"
                    % _abbrev(["AC-%d" % n for n in uncovered])))
            dangling = [n for n in refs if n not in acs]
            if dangling:
                out.append(finding(
                    "error", "closure", name,
                    "spec.md tags ACs that acs.md does not define: %s"
                    % _abbrev(["AC-%d" % n for n in dangling])))

    # enumeration — handoff checkpoints are real pipeline stops.
    # _all_records yields (filename, record) pairs.
    for fname, rec in dae_handoff._all_records(feature_dir):
        cp = rec.get("checkpoint")
        if cp is not None and cp not in CHECKPOINTS:
            out.append(finding(
                "error", "enumeration", name,
                "%s: checkpoint %r is not a pipeline stop" % (fname, cp)))

    # disjoint — verifier must not be the implementer or refiner (Principle 7).
    # dae_handoff owns this rule; reuse it rather than restating it.
    for fname, agent, cp, author_cp in dae_handoff.independence_violations(feature_dir):
        out.append(finding(
            "error", "disjoint", name,
            "%s: CP%s run by %r, the same agent that authored CP%s"
            % (fname, cp, agent, author_cp)))

    return out


# --- project-scope checks -------------------------------------------------

def _feature_dirs(features_root):
    if not os.path.isdir(features_root):
        return []
    return sorted(
        os.path.join(features_root, d) for d in os.listdir(features_root)
        if os.path.isdir(os.path.join(features_root, d))
        and not d.startswith("."))


def check_project(start_dir="."):
    """Cross-feature constraint findings: the relations no single feature sees."""
    root, _ = dae_resolve.find_methodology_root(start_dir)
    if root is None:
        return [finding("error", "existence", start_dir,
                        "no .engineer/manifest.yml found walking up")]
    dirs = _feature_dirs(os.path.join(root, "features"))
    features = {}
    out = []
    for d in dirs:
        name = os.path.basename(d)
        fm = load_feature(d)
        if fm is None:
            continue
        features[name] = fm
        out.extend(check_feature(d))

    # Resolve references (parent_feature / child_features) through the bare
    # slug, so `012-washer-tracking` and `washer-tracking` name one individual.
    by_bare = {}
    for name in features:
        by_bare.setdefault(bare_slug(name), []).append(name)

    def resolve(ref):
        """The folder name a reference points at, or None if unresolvable."""
        if ref in features:
            return ref
        hits = by_bare.get(bare_slug(ref), [])
        return hits[0] if len(hits) == 1 else None

    # functional — a feature branch belongs to at most one feature. Trunk
    # branches are excluded: a multi-repo umbrella legitimately runs every
    # feature off master. Sharing a non-trunk branch is a smell (two features
    # cannot be merged or reverted independently) but sometimes deliberate, so
    # it is a warning rather than an error.
    by_branch = {}
    for name, fm in features.items():
        br = fm.get("branch")
        if br and br not in TRUNK_BRANCHES:
            by_branch.setdefault(br, []).append(name)
    for br, owners in sorted(by_branch.items()):
        if len(owners) > 1:
            out.append(finding(
                "warning", "functional", ", ".join(sorted(owners)),
                "branch %r is claimed by %d features — they cannot ship or "
                "revert independently" % (br, len(owners))))

    # functional — a roadmap item promotes into at most one feature
    by_ref = {}
    for name, fm in features.items():
        ref = fm.get("roadmap_ref")
        if ref:
            by_ref.setdefault(ref, []).append(name)
    for ref, owners in sorted(by_ref.items()):
        if len(owners) > 1:
            out.append(finding(
                "error", "functional", ", ".join(sorted(owners)),
                "roadmap item %r is claimed by %d features" % (ref, len(owners))))

    # inverse — parent_feature and child_features must agree both ways
    for name, fm in sorted(features.items()):
        parent = resolve(fm.get("parent_feature")) if fm.get("parent_feature") else None
        if not fm.get("parent_feature"):
            continue
        if parent is None:
            out.append(finding(
                "error", "inverse", name,
                "parent_feature %r does not resolve to a feature"
                % fm.get("parent_feature")))
            continue
        kids = features[parent].get("child_features")
        kids = kids if isinstance(kids, list) else []
        if not any(resolve(k) == name for k in kids):
            out.append(finding(
                "warning", "inverse", name,
                "declares parent %r, which does not list it in child_features"
                % parent))
    for name, fm in sorted(features.items()):
        kids = fm.get("child_features")
        if not isinstance(kids, list):
            continue
        for kid in kids:
            target = resolve(kid)
            if target is None:
                out.append(finding(
                    "error", "inverse", name,
                    "child_features names %r, which does not resolve to a "
                    "feature" % kid))
            elif resolve(features[target].get("parent_feature") or "") != name:
                out.append(finding(
                    "warning", "inverse", name,
                    "lists child %r, which does not name it as parent" % kid))

    # transitive — parent_feature chains must not cycle
    for name in sorted(features):
        seen, cur = [], name
        while cur:
            if cur in seen:
                out.append(finding(
                    "error", "transitive", name,
                    "parent_feature cycle: %s" % " → ".join(seen + [cur])))
                break
            seen.append(cur)
            nxt = features[cur].get("parent_feature")
            cur = resolve(nxt) if nxt else None

    # functional — feature numbers are unique
    by_num = {}
    for name in features:
        m = _FEATURE_DIR_RE.match(name)
        if m:
            by_num.setdefault(m.group(1), []).append(name)
    for num, owners in sorted(by_num.items()):
        if len(owners) > 1:
            out.append(finding(
                "warning", "functional", ", ".join(sorted(owners)),
                "feature number %s is reused" % num))

    return out


# --- reporting ------------------------------------------------------------

def render(findings):
    if not findings:
        return "ontology: clean — no constraint violations."
    errs = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] != "error"]
    lines = []
    for label, group in (("ERROR", errs), ("warning", warns)):
        for f in group:
            lines.append("%-7s [%s] %s: %s"
                         % (label, f["constraint"], f["entity"], f["message"]))
    lines.append("")
    lines.append("ontology: %d error(s), %d warning(s)." % (len(errs), len(warns)))
    return "\n".join(lines)


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if argv and argv[0] == "--project":
        findings = check_project(argv[1] if len(argv) > 1 else ".")
    elif argv:
        target = argv[0]
        if not os.path.isdir(target):
            sys.stderr.write("not a directory: %s\n" % target)
            return 2
        findings = check_feature(target)
    else:
        print(__doc__)
        return 0
    print(json.dumps(findings, indent=2) if as_json else render(findings))
    return 1 if any(f["severity"] == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
