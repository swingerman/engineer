#!/usr/bin/env python3
"""dae_handoff.py — audit handoff completeness against progress.md.

A checkpoint is "complete" only when its handoff exists, has status: complete,
and (if it carries an exit_criteria block) every criterion is met. This is the
enforcement helper for handoff-as-gate (DAE Foundation Design, Sections 5 + 8).

Usage:
  dae_handoff.py <feature-dir>               report; exit 0 if consistent
  dae_handoff.py <feature-dir> --through N   exit non-zero unless checkpoint N
                                             is complete and there are no gaps
  dae_handoff.py --status [START_DIR]        JSON: every feature's status,
                                             latest-complete checkpoint, gaps,
                                             and last handoff (project-wide)
"""
import json
import os
import re
import sys

import dae_resolve

# Checkpoints 0 (Onboard) and 1.5 (Ready) are human/feature-init gated — they
# carry no skill handoff, so they never count as a gate failure.
NON_SKILL_CHECKPOINTS = (0, 1.5)


def _num(val):
    """Parse a checkpoint number ('2' -> 2, '1.5' -> 1.5); None if not numeric."""
    try:
        return float(val) if "." in val else int(val)
    except (ValueError, TypeError):
        return None


def parse_handoff(text):
    """Parse a handoff .md into {checkpoint, status, exit_criteria, skill, agent_id}.

    `met` is normalized to {True, False, "partial", None}. distbute saw a verify
    handoff with met: partial slip through because the parser silently dropped
    'partial' to None — the gate logic then treated it as "not true → fail",
    but feature.md still claimed status: done. Keeping 'partial' as a distinct
    value lets callers report it explicitly instead of confusing it with absent.
    """
    rec = {"checkpoint": None, "status": None, "exit_criteria": [],
           "skill": None, "agent_id": None}
    fm = dae_resolve.extract_frontmatter(text)
    if not fm:
        return rec
    try:
        data = dae_resolve.read_manifest(fm)
    except dae_resolve.ManifestError:
        return rec
    if not isinstance(data, dict):
        return rec
    cp = data.get("checkpoint")
    if cp is not None and cp not in ("", "null", "~"):
        rec["checkpoint"] = cp if isinstance(cp, (int, float)) else _num(str(cp))
    status = data.get("status")
    rec["status"] = status if isinstance(status, str) else None
    skill = data.get("skill")
    rec["skill"] = skill if isinstance(skill, str) else None
    agent_id = data.get("agent_id")
    rec["agent_id"] = agent_id if isinstance(agent_id, str) else None
    raw_criteria = data.get("exit_criteria")
    if isinstance(raw_criteria, list):
        for entry in raw_criteria:
            if isinstance(entry, dict):
                met_raw = entry.get("met")
                if met_raw is True:
                    met = True
                elif met_raw is False:
                    met = False
                elif isinstance(met_raw, str) and met_raw.lower() == "partial":
                    met = "partial"
                else:
                    met = None
                rec["exit_criteria"].append({"met": met})
    return rec


def read_progress(text):
    """Parse the progress.md Checkpoints table -> {checkpoint: done_bool}."""
    result = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        cp = _num(cells[0])
        if cp is None:
            continue  # header or separator row
        result[cp] = "done" in cells[2].lower()
    return result


def _rec_complete(rec):
    """True if a handoff record means its checkpoint is genuinely done."""
    if rec["status"] != "complete":
        return False
    return all(c["met"] is True for c in rec["exit_criteria"])


def _all_records(feature_dir):
    """Return [(filename, rec), ...] for all parsed handoffs in feature_dir/handoffs."""
    records = []
    hdir = os.path.join(feature_dir, "handoffs")
    if os.path.isdir(hdir):
        for name in sorted(os.listdir(hdir)):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(hdir, name), encoding="utf-8") as f:
                records.append((name, parse_handoff(f.read())))
    return records


# Principle 7: who must not verify whose work. CP5 implements, CP6 refines
# (also authorship), CP7/CP8 verify. A checkpoint's handoff agent_id must
# differ from every author checkpoint listed against it.
_INDEPENDENT_OF = {6: (5,), 7: (5, 6), 8: (5, 6)}


def independence_violations(feature_dir):
    """Return [(handoff_filename, shared_agent_id, violator_cp, author_cp), ...]
    for every handoff whose agent_id matches an author checkpoint it must be
    independent of (_INDEPENDENT_OF): the refiner is not the implementer, the
    verifier is neither the implementer nor the refiner.

    A missing agent_id on either side is ignored (no comparison possible).
    """
    records = _all_records(feature_dir)
    authors = {}
    for _, rec in records:
        if rec["checkpoint"] in (5, 6) and rec["agent_id"]:
            authors.setdefault(rec["checkpoint"], rec["agent_id"])
    violations = []
    for fname, rec in records:
        for author_cp in _INDEPENDENT_OF.get(rec["checkpoint"], ()):
            if rec["agent_id"] and rec["agent_id"] == authors.get(author_cp):
                violations.append((fname, rec["agent_id"], rec["checkpoint"], author_cp))
    return violations


def audit(feature_dir):
    """Audit one feature folder. Returns a dict with complete/claimed/gaps."""
    complete = set()
    for _, rec in _all_records(feature_dir):
        if rec["checkpoint"] is not None and _rec_complete(rec):
            complete.add(rec["checkpoint"])
    claimed_done = set()
    progress_path = os.path.join(feature_dir, "progress.md")
    if os.path.isfile(progress_path):
        with open(progress_path, encoding="utf-8") as f:
            for cp, done in read_progress(f.read()).items():
                if done:
                    claimed_done.add(cp)
    return {
        "complete": complete,
        "claimed_done": claimed_done,
        "gaps": sorted(claimed_done - complete),
        "latest_complete": max(complete) if complete else None,
        "independence_violations": independence_violations(feature_dir),
    }


def gate(feature_dir, through=None):
    """Return (ok, message). ok is False if a checkpoint <= `through` is not
    backed by a complete handoff, or any claimed-done checkpoint has no handoff,
    or any verification handoff shares agent_id with an author (CP5/CP6) handoff.
    NON_SKILL_CHECKPOINTS never count as gaps — they carry no skill handoff.
    """
    a = audit(feature_dir)
    real_gaps = [g for g in a["gaps"] if g not in NON_SKILL_CHECKPOINTS]
    if real_gaps:
        return False, "checkpoints marked done with no complete handoff: %s" % real_gaps
    if a["independence_violations"]:
        v = a["independence_violations"][0]
        return False, ("verifier-independence violated: CP%s handoff %s "
                       "shares agent_id %s with the CP%s handoff "
                       "(Principle 7)") % (v[2], v[0], v[1], v[3])
    if through is not None and through not in NON_SKILL_CHECKPOINTS \
            and through not in a["complete"]:
        return False, "checkpoint %s is not complete -- cannot advance past it" % through
    return True, "ok -- latest complete checkpoint: %s" % a["latest_complete"]


_STATUS_RE = re.compile(r"^status:[ \t]*(\S+)", re.MULTILINE)


def _feature_status_field(feature_dir):
    """feature.md frontmatter `status:`, or None."""
    fm_path = os.path.join(feature_dir, "feature.md")
    if not os.path.isfile(fm_path):
        return None
    with open(fm_path, encoding="utf-8") as f:
        fm = dae_resolve.extract_frontmatter(f.read())
    if not fm:
        return None
    m = _STATUS_RE.search(fm)
    return m.group(1) if m else None


def _last_handoff(feature_dir):
    """Newest handoff filename by mtime, or None."""
    hdir = os.path.join(feature_dir, "handoffs")
    if not os.path.isdir(hdir):
        return None
    files = [n for n in os.listdir(hdir) if n.endswith(".md")]
    if not files:
        return None
    files.sort(key=lambda n: os.path.getmtime(os.path.join(hdir, n)))
    return files[-1]


def project_status(start_dir="."):
    """Enumerate every feature under the resolved features_root. One dict per
    feature: status, latest-complete checkpoint, gaps, independence-violation
    count, last handoff. Replaces the fragile inline grep/ls pipeline agents
    hand-roll to survey pipeline state."""
    root, manifest_path = dae_resolve.find_methodology_root(start_dir)
    if not root:
        return []
    manifest = {}
    if manifest_path and os.path.isfile(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            try:
                manifest = dae_resolve.read_manifest(f.read())
            except dae_resolve.ManifestError:
                manifest = {}
    features_root = manifest.get("features_root") or "features/"
    features_dir = os.path.join(root, features_root)
    if not os.path.isdir(features_dir):
        return []
    out = []
    for name in sorted(os.listdir(features_dir)):
        fdir = os.path.join(features_dir, name)
        if not os.path.isfile(os.path.join(fdir, "feature.md")):
            continue
        a = audit(fdir)
        out.append({
            "feature": name,
            "status": _feature_status_field(fdir),
            "latest_complete_cp": a["latest_complete"],
            "gaps": a["gaps"],
            "independence_violations": len(a["independence_violations"]),
            "last_handoff": _last_handoff(fdir),
        })
    return out


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if "--status" in argv:
        rest = [a for a in argv if a != "--status"]
        print(json.dumps(project_status(rest[0] if rest else "."), indent=1))
        return 0
    feature_dir = argv[0]
    through = None
    if "--through" in argv:
        through = _num(argv[argv.index("--through") + 1])
    ok, msg = gate(feature_dir, through)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
