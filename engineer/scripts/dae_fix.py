#!/usr/bin/env python3
"""dae_fix.py — parse + validate bug-fix artifacts.

Parses `.engineer/fixes/<YYYY-MM-DD-slug>.md` artifacts and provides validation,
gate-check functions, and a scanner for open fixes. Reuses dae_resolve for YAML
frontmatter parsing to avoid duplicate walkers.

Usage:
    dae_fix.py <fix-dir>               scan and list open fixes
    dae_fix.py --validate <fix-file>   check a single fix for errors
"""
import os
import re
import glob
import sys

import dae_resolve

# Closed-set vocabularies
STATUS_LIFECYCLE = {
    "investigating", "pinned-pending", "pinned", "fixed", "refined",
    "verified", "hardened", "gap-analyzed", "closed"
}
GAP_ANALYSIS_CATEGORIES = {
    "missing_ac", "unspecced_ac", "incomplete_spec", "inadequate_verification",
    "architecture_violation", "external_dependency", "no_feature", "none"
}
SEVERITY_VALUES = {"low", "medium", "high", "critical"}

# Slug pattern: YYYY-MM-DD-<slug>
SLUG_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}-[\w-]+$')


def parse_fix(text):
    """Parse a fix .md into a dict mirroring the artifact schema.

    Returns {"slug", "title", "source": {"kind", "ref"}, "severity",
             "blocks_user", "workaround", "status", "repro", "expected", "actual",
             "feature_refs": [str], "investigation": {"match_mode", "candidates_considered"},
             "pin_confirmation": {"feature_refs": [{"feature", "spec_path", "red_run": {...}}]},
             "fix_commits": [str], "harden_results": {...}, "gap_analysis": [...], "followups": [...]}.

    Unknown/missing fields default to None or [] as appropriate.
    Tolerant of malformed frontmatter (returns dict with defaults rather than raising).
    """
    rec = {
        "slug": None,
        "title": None,
        "source": None,
        "severity": None,
        "blocks_user": None,
        "workaround": None,
        "status": None,
        "repro": None,
        "expected": None,
        "actual": None,
        "feature_refs": [],
        "investigation": None,
        "pin_confirmation": None,
        "fix_commits": [],
        "harden_results": None,
        "gap_analysis": [],
        "followups": [],
        "handoff_path": None,
        "attempts": [],
    }

    fm = dae_resolve.extract_frontmatter(text)
    if not fm:
        return rec

    try:
        data = dae_resolve.read_manifest(fm)
    except dae_resolve.ManifestError:
        return rec

    if not isinstance(data, dict):
        return rec

    # slug: must be present in the frontmatter
    slug = data.get("slug")
    if isinstance(slug, str):
        rec["slug"] = slug

    # title
    title = data.get("title")
    if isinstance(title, str):
        rec["title"] = title

    # source: {kind, ref}
    source_block = data.get("source")
    if isinstance(source_block, dict):
        kind = source_block.get("kind")
        ref = source_block.get("ref")
        if kind or ref:
            rec["source"] = {
                "kind": kind if isinstance(kind, str) else None,
                "ref": ref if isinstance(ref, str) else None,
            }

    # severity
    severity = data.get("severity")
    if isinstance(severity, str):
        rec["severity"] = severity

    # blocks_user: boolean
    blocks_user = data.get("blocks_user")
    if isinstance(blocks_user, bool):
        rec["blocks_user"] = blocks_user
    elif blocks_user is not None and str(blocks_user).lower() in ("true", "false", "yes", "no"):
        rec["blocks_user"] = str(blocks_user).lower() in ("true", "yes")

    # workaround: string
    workaround = data.get("workaround")
    if isinstance(workaround, str):
        rec["workaround"] = workaround

    # status
    status = data.get("status")
    if isinstance(status, str):
        rec["status"] = status

    # repro, expected, actual: strings (often block scalars)
    for field in ("repro", "expected", "actual"):
        value = data.get(field)
        if isinstance(value, str):
            rec[field] = value

    # feature_refs: list of strings
    feature_refs = data.get("feature_refs")
    if isinstance(feature_refs, list):
        rec["feature_refs"] = [f for f in feature_refs if isinstance(f, str)]

    # investigation: {match_mode, candidates_considered}
    investigation = data.get("investigation")
    if isinstance(investigation, dict):
        match_mode = investigation.get("match_mode")
        candidates = investigation.get("candidates_considered")
        if match_mode or candidates:
            rec["investigation"] = {
                "match_mode": match_mode if isinstance(match_mode, str) else None,
                "candidates_considered": candidates if isinstance(candidates, (int, str)) else None,
            }

    # pin_confirmation: {feature_refs: [{feature, spec_path, red_run: {...}}]}
    pin_conf = data.get("pin_confirmation")
    if isinstance(pin_conf, dict):
        pin_feature_refs = pin_conf.get("feature_refs")
        if isinstance(pin_feature_refs, list):
            parsed_pin_refs = []
            for item in pin_feature_refs:
                if isinstance(item, dict):
                    pin_item = {
                        "feature": item.get("feature"),
                        "spec_path": item.get("spec_path"),
                        "red_run": item.get("red_run"),  # dict or None
                    }
                    parsed_pin_refs.append(pin_item)
            if parsed_pin_refs:
                rec["pin_confirmation"] = {"feature_refs": parsed_pin_refs}

    # fix_commits: list of strings
    fix_commits = data.get("fix_commits")
    if isinstance(fix_commits, list):
        rec["fix_commits"] = [c for c in fix_commits if isinstance(c, str)]

    # harden_results: dict (passed through as-is)
    harden_results = data.get("harden_results")
    if isinstance(harden_results, dict):
        rec["harden_results"] = harden_results

    # gap_analysis: list of dicts
    gap_analysis = data.get("gap_analysis")
    if isinstance(gap_analysis, list):
        rec["gap_analysis"] = [item for item in gap_analysis if isinstance(item, dict)]

    # followups: list of dicts
    followups = data.get("followups")
    if isinstance(followups, list):
        rec["followups"] = [item for item in followups if isinstance(item, dict)]

    # handoff_path: string pointing at the close-step handoff for this fix
    handoff_path = data.get("handoff_path")
    if isinstance(handoff_path, str):
        rec["handoff_path"] = handoff_path

    # attempts: ordered log of fix attempts, [{gate, result, premise?}]
    attempts = data.get("attempts")
    if isinstance(attempts, list):
        rec["attempts"] = attempts

    return rec


PREMISE_FIELDS = ("belief", "observation", "command", "output")


def attempt_errors(rec):
    """Once two attempts on a gate have failed, every later attempt on that gate
    must carry a premise: block — the root-cause belief being acted on, an
    observation that would come out differently if it were false, and the
    command + output that ran it — with falsified: false. A falsified premise
    blocks the attempt until the agent re-diagnoses and records a new one.
    """
    errors = []
    failed = {}
    for i, a in enumerate(rec.get("attempts") or []):
        if not isinstance(a, dict) or not a.get("gate"):
            errors.append("attempts[%d] must be a mapping with a gate" % i)
            continue
        gate = str(a["gate"])
        if failed.get(gate, 0) >= 2:
            where = "attempts[%d] (gate %r, after %d failed attempts)" % (i, gate, failed[gate])
            premise = a.get("premise")
            if not isinstance(premise, dict):
                errors.append("%s requires a premise: block %s — re-check the root-cause belief "
                              "before another patch" % (where, list(PREMISE_FIELDS) + ["falsified"]))
            else:
                missing = [f for f in PREMISE_FIELDS if not premise.get(f)]
                if missing:
                    errors.append("%s premise missing %s" % (where, missing))
                if premise.get("falsified") is True:
                    errors.append("%s premise was falsified by its observation — re-diagnose and "
                                  "record a new premise before writing code" % where)
                elif premise.get("falsified") is not False:
                    errors.append("%s premise.falsified must be true or false" % where)
        if a.get("result") == "fail":
            failed[gate] = failed.get(gate, 0) + 1
    return errors


def validate_fix(rec):
    """Schema validation. Returns list of human-readable error strings; empty list = valid.

    Checks: slug present and matches <YYYY-MM-DD>-<slug> pattern, title non-empty, severity
    in {low, medium, high, critical}, status in the known lifecycle set, blocks_user is bool,
    workaround is str (use "none" for no workaround), gap_analysis entries have category from
    the closed vocabulary.
    """
    errors = []

    # slug: must be present and match YYYY-MM-DD-<slug>
    if not rec.get("slug"):
        errors.append("slug is required")
    elif not SLUG_PATTERN.match(rec["slug"]):
        errors.append(
            "slug must match pattern YYYY-MM-DD-<slug>, got: %r" % rec["slug"]
        )

    # title: must be non-empty string
    if not rec.get("title"):
        errors.append("title is required and must be non-empty")

    # severity: must be in vocabulary (if present)
    if rec.get("severity") and rec["severity"] not in SEVERITY_VALUES:
        errors.append("severity %r must be one of %s" % (rec["severity"], sorted(SEVERITY_VALUES)))

    # status: must be in lifecycle (if present)
    if rec.get("status") and rec["status"] not in STATUS_LIFECYCLE:
        errors.append("status %r must be one of %s" % (rec["status"], sorted(STATUS_LIFECYCLE)))

    # blocks_user: must be bool (if present)
    if rec.get("blocks_user") is not None and not isinstance(rec["blocks_user"], bool):
        errors.append("blocks_user must be a boolean, got: %r" % rec["blocks_user"])

    # workaround: must be a string (if present)
    if rec.get("workaround") is not None and not isinstance(rec["workaround"], str):
        errors.append("workaround must be a string, got: %r" % rec["workaround"])

    # gap_analysis: each entry must have a category in the vocabulary
    for i, entry in enumerate(rec.get("gap_analysis") or []):
        if not isinstance(entry, dict):
            errors.append("gap_analysis[%d] must be a dict" % i)
            continue
        category = entry.get("category")
        if category is None:
            errors.append("gap_analysis[%d] missing required field 'category'" % i)
        elif category not in GAP_ANALYSIS_CATEGORIES:
            errors.append(
                "gap_analysis[%d].category %r must be one of %s"
                % (i, category, sorted(GAP_ANALYSIS_CATEGORIES))
            )

    errors.extend(attempt_errors(rec))

    # When status == 'closed', enforce close-step preconditions at schema time.
    # The mmc audit showed 5 fixes with status: closed but only 2 handoffs —
    # the close step was silently skipped under deploy pressure. Make it hard.
    if rec.get("status") == "closed":
        if not rec.get("handoff_path"):
            errors.append("status: closed requires handoff_path (path to the close-step handoff)")
        if not is_pin_confirmed(rec):
            errors.append("status: closed requires pin_confirmation with red_run.result == 'red' for every feature_ref")
        if not is_hardened(rec):
            errors.append(
                "status: closed requires harden_results with bug_line_mutation_confirmed: true, "
                "mutation_score recorded, and arch_check recorded"
            )
        if not (rec.get("gap_analysis") or []):
            errors.append("status: closed requires non-empty gap_analysis (the 'why didn't we catch it?' loop)")
        if has_unresolved_blockers(rec):
            errors.append("status: closed requires all blocker followups resolved (architecture_violation or blocks_user+workaround:none)")

    return errors


def is_pin_confirmed(rec):
    """True iff every feature_refs[*] has a matching pin_confirmation.feature_refs entry
    whose red_run.result == 'red'. Also True if feature_refs is empty AND the artifact
    explicitly logs a loose-fix RED run (TBD: for v1, return True if feature_refs is empty
    — loose-fix pin lives in a separate path, not validated here).
    """
    feature_refs = rec.get("feature_refs") or []

    # If no feature refs, treat as confirmed (v1: loose-fix not validated here).
    if not feature_refs:
        return True

    pin_conf = rec.get("pin_confirmation")
    if not pin_conf or not isinstance(pin_conf, dict):
        return False

    pin_feature_refs = pin_conf.get("feature_refs") or []
    if not isinstance(pin_feature_refs, list):
        return False

    # Build a map of feature -> red_run for quick lookup
    pin_map = {}
    for pin_entry in pin_feature_refs:
        if not isinstance(pin_entry, dict):
            continue
        feature = pin_entry.get("feature")
        red_run = pin_entry.get("red_run")
        if feature:
            pin_map[feature] = red_run

    # Check: every feature_ref must have a pin entry with red_run.result == 'red'
    for feature in feature_refs:
        if feature not in pin_map:
            return False
        red_run = pin_map[feature]
        if not isinstance(red_run, dict):
            return False
        if red_run.get("result") != "red":
            return False

    return True


def is_hardened(rec):
    """True iff harden_results.bug_line_mutation_confirmed == True AND
    mutation_score is recorded AND arch_check is recorded.
    """
    harden_results = rec.get("harden_results")
    if not isinstance(harden_results, dict):
        return False

    bug_line = harden_results.get("bug_line_mutation_confirmed")
    if bug_line is not True:
        return False

    mutation_score = harden_results.get("mutation_score")
    if mutation_score is None:
        return False

    arch_check = harden_results.get("arch_check")
    if arch_check is None:
        return False

    return True


def blocker_categories(rec):
    """Return the list of gap-analysis categories that are blockers for THIS fix.

    Blocker rule:
      - 'architecture_violation' is ALWAYS a blocker.
      - If rec.blocks_user is True AND rec.workaround == 'none', then ALL gap-analysis
        categories present on this fix are promoted to blockers.

    Returns deduplicated list of category strings.
    """
    blockers = set()

    # Collect all categories present in gap_analysis
    gap_analysis = rec.get("gap_analysis") or []
    all_categories = set()
    for entry in gap_analysis:
        if isinstance(entry, dict):
            category = entry.get("category")
            if category:
                all_categories.add(category)

    # architecture_violation is always a blocker
    if "architecture_violation" in all_categories:
        blockers.add("architecture_violation")

    # If blocks_user=True and workaround='none', all present categories are blockers
    if rec.get("blocks_user") is True and rec.get("workaround") == "none":
        blockers.update(all_categories)

    return sorted(blockers)


def has_unresolved_blockers(rec):
    """True iff any gap_analysis entry whose category is in blocker_categories(rec)
    has a followup.status != 'applied'. (Followup entries should have a 'status' field;
    treat missing status as 'open' = unresolved.)
    """
    blockers = set(blocker_categories(rec))
    if not blockers:
        return False

    gap_analysis = rec.get("gap_analysis") or []
    followups = rec.get("followups") or []

    # Build a map from category -> list of followups for that category
    category_followups = {}
    for followup in followups:
        if not isinstance(followup, dict):
            continue
        category = followup.get("category")
        if category:
            if category not in category_followups:
                category_followups[category] = []
            category_followups[category].append(followup)

    # For each blocker category in gap_analysis, check if there's an unresolved followup
    for gap_entry in gap_analysis:
        if not isinstance(gap_entry, dict):
            continue
        category = gap_entry.get("category")
        if category not in blockers:
            continue

        # Check if there's a followup for this category with status != 'applied'
        followups_for_cat = category_followups.get(category) or []
        if not followups_for_cat:
            # No followup entry at all = unresolved
            return True

        # Check each followup; if ANY has status != 'applied', it's unresolved
        for fu in followups_for_cat:
            status = fu.get("status")
            if status != "applied":
                return True

    return False


def close_ready(rec):
    """Combines all close-gate preconditions:
      - status is at least 'gap-analyzed' (i.e., reached gap analysis)
      - is_pin_confirmed(rec)
      - is_hardened(rec)
      - rec.gap_analysis is non-empty (even a single {category: none, ...} counts)
      - not has_unresolved_blockers(rec)
    """
    # status must be at least 'gap-analyzed'
    status = rec.get("status")
    status_order = [
        "investigating", "pinned-pending", "pinned", "fixed", "refined",
        "verified", "hardened", "gap-analyzed", "closed"
    ]
    try:
        status_idx = status_order.index(status) if status else -1
    except ValueError:
        status_idx = -1

    if status_idx < status_order.index("gap-analyzed"):
        return False

    # pin confirmed
    if not is_pin_confirmed(rec):
        return False

    # hardened
    if not is_hardened(rec):
        return False

    # gap_analysis non-empty
    gap_analysis = rec.get("gap_analysis") or []
    if not gap_analysis:
        return False

    # no unresolved blockers
    if has_unresolved_blockers(rec):
        return False

    return True


def list_open_fixes(root):
    """Scan <root>/.engineer/fixes/*.md, parse each, return list of {slug, title,
    severity, blocks_user, workaround, status, feature_refs}. Used by `next` to
    populate the OPEN FIXES bucket. Skips files whose frontmatter fails to parse
    (logs a warning to stderr but continues). Excludes status == 'closed' from
    the output.
    """
    fixes_dir = os.path.join(root, ".engineer", "fixes")
    result = []

    if not os.path.isdir(fixes_dir):
        return result

    for fix_file in sorted(glob.glob(os.path.join(fixes_dir, "*.md"))):
        try:
            with open(fix_file, "r", encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write("warning: failed to read %s: %s\n" % (fix_file, e))
            continue

        rec = parse_fix(text)

        # Skip if parsing failed (slug or title missing)
        if not rec.get("slug") or not rec.get("title"):
            sys.stderr.write("warning: %s: failed to parse frontmatter\n" % fix_file)
            continue

        # Exclude closed fixes
        if rec.get("status") == "closed":
            continue

        # Return the summary dict
        result.append({
            "slug": rec["slug"],
            "title": rec["title"],
            "severity": rec["severity"],
            "blocks_user": rec["blocks_user"],
            "workaround": rec["workaround"],
            "status": rec["status"],
            "feature_refs": rec["feature_refs"],
        })

    return result


def render_fix_closure_entry(rec, followups_summary=None):
    """Render the markdown block to append to a feature's progress.md when a fix closes.

    Args:
        rec: a parsed fix artifact dict (from parse_fix)
        followups_summary: optional {"advisory": int, "blocker_applied": int} counts
                           for the closure report. If None, omits that line.

    Returns:
        A markdown string ending in a blank line. Shape:

        ## Fix applied — 2026-05-25-stale-cache-on-401
        - Severity: high; user-blocking: yes; workaround: none
        - Followups: 2 advisory, 1 blocker applied inline
        - See `.engineer/fixes/2026-05-25-stale-cache-on-401.md`

        Fields adjust to what's in rec — if blocks_user is False, the bullet
        reads "user-blocking: no" with no workaround mention. If followups_summary
        is None, omit the followups bullet.
    """
    slug = rec.get("slug") or "unknown"
    severity = rec.get("severity") or "unknown"
    blocks_user = rec.get("blocks_user")

    # Build the severity/blocking line
    if blocks_user:
        workaround = rec.get("workaround") or "none"
        blocking_part = "user-blocking: yes; workaround: %s" % workaround
    else:
        blocking_part = "user-blocking: no"

    lines = [
        "## Fix applied — %s" % slug,
        "- Severity: %s; %s" % (severity, blocking_part),
    ]

    # Optional followups line
    if followups_summary is not None:
        advisory = followups_summary.get("advisory", 0)
        blocker_applied = followups_summary.get("blocker_applied", 0)
        lines.append(
            "- Followups: %d advisory, %d blocker applied inline"
            % (advisory, blocker_applied)
        )

    lines.append("- See `.engineer/fixes/%s.md`" % slug)
    lines.append("")  # trailing blank line

    return "\n".join(lines)


def render_consolidation_entries(rec: dict) -> list:
    """Render markdown entries to append to .engineer/consolidation.md for the
    advisory (non-blocker) followups in this fix's gap_analysis.

    Args:
        rec: a parsed fix artifact dict (from parse_fix)

    Returns:
        A list of markdown entries (one per advisory followup). Each entry is
        self-contained and ready to append. Blocker followups are NOT included
        (those must be applied inline before close; they don't land in the
        backlog).

    Each entry shape:

        - [ ] [<category>] <action> — `<target>` (from fix `<slug>`)

    Example:
        - [ ] [inadequate_verification] Add scenario "cache invalidation on 401 from upstream" — `features/058-cache-layer/specs/cache.spec.md` (from fix `2026-05-25-stale-cache-on-401`)

    Empty list if rec has no advisory followups, or no gap_analysis at all.
    `category: none` entries are also excluded — "none" means "explicitly
    nothing to learn here" and shouldn't land in the backlog.

    Uses the existing blocker_categories(rec) helper to determine which
    findings are advisory vs blocker.
    """
    gap_analysis = rec.get("gap_analysis") or []
    if not gap_analysis:
        return []

    slug = rec.get("slug") or "unknown"
    blockers = set(blocker_categories(rec))

    entries = []
    for item in gap_analysis:
        if not isinstance(item, dict):
            continue
        category = item.get("category") or "unknown"
        if category in blockers:
            continue
        if category == "none":
            continue
        followup = item.get("followup") or {}
        action = followup.get("action") or "Review finding"
        target = followup.get("target") or "unknown"
        entries.append(
            "- [ ] [%s] %s — `%s` (from fix `%s`)" % (category, action, target, slug)
        )

    return entries


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    if argv[0] == "--validate":
        if len(argv) < 2:
            sys.stderr.write("usage: dae_fix.py --validate <fix-file>\n")
            return 1
        fix_file = argv[1]
        try:
            with open(fix_file, "r", encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write("error: failed to read %s: %s\n" % (fix_file, e))
            return 1

        rec = parse_fix(text)
        errors = validate_fix(rec)
        if errors:
            for err in errors:
                sys.stderr.write("ERROR: " + err + "\n")
            return 1
        sys.stdout.write("OK: %s\n" % fix_file)
        return 0

    # Default: scan fixes directory
    root = argv[0]
    fixes = list_open_fixes(root)
    for fix in fixes:
        print("%-40s %s [%s] blocks_user=%s" % (
            fix["slug"], fix["title"][:30], fix["status"] or "?", fix["blocks_user"]
        ))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
