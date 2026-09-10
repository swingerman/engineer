#!/usr/bin/env python3
"""dae-resolve — resolve the DAE methodology root and parse/validate the manifest.

The first step of every DAE skill. Walks up from a start directory to find
`.engineer/manifest.yml`, parses it, validates it against the Foundation
Design Section 2 schema, and prints JSON.

Parsing is stdlib-only: a *scoped reader* for the locked manifest schema —
NOT a general YAML parser. It handles exactly what the manifest uses:
`key: value`, nested maps by indentation, `-` lists of scalars or maps,
inline `[...]` lists, `#` comments, and quoted/typed scalars.

Usage:
    dae_resolve.py [--validate-only] [START_DIR]

Output (JSON on stdout):
    {
      "methodology_root": "/abs/path",                  # dir containing .engineer/
      "manifest_path": "/abs/path/.engineer/manifest.yml",
      "manifest": { ... },                              # parsed manifest
      "valid": true,
      "errors": [],                                     # hard — block
      "warnings": []                                    # soft — review
    }

Exit codes:
    0  manifest found and valid
    1  manifest found but invalid (errors present)
    2  no manifest found walking up from START_DIR
    3  usage error
"""

import json
import os
import re
import sys

KNOWN_METHODOLOGY_VERSIONS = {"0.1", "0.2"}
TRACKER_TYPES = {"notion", "github-projects", "linear", "jira", "local"}
# The roadmap is the strategic feature-list altitude (see references/roadmap.md).
# Its host is chosen independently of the tracker, so its enum is its own —
# broader, and including the explicit opt-out `none` and the free-text `other`.
ROADMAP_TYPES = {"local", "notion", "confluence", "gdoc",
                 "github-projects", "other", "none"}
# A roadmap can only be onboarded if DAE can reach its host programmatically.
# The `other` host must declare which channel DAE drives it through.
ROADMAP_OTHER_ACCESS = {"mcp", "cli", "api"}
AUTONOMY_LEVELS = {"low", "medium", "high"}
MUTATION_SCOPES = {"changed_files", "changed_module", "full"}
MUTATION_CADENCES = {"per_pr", "per_merge", "per_release", "on_demand"}
MUTATION_DEFAULTS = {"required", "opt_in"}
AGENTIC_SUMMARY_FORMATS = {"markdown"}
IMPACT_ANALYSIS_VALUES = {"on", "off"}
GIT_MANUAL_VALUES = {True, False}
DUPLICATION_TOOLS = {"jscpd", "pmd-cpd", "flay", "dupl"}
DUPLICATION_SKIP_VALUES = {True, False}
FEATURE_FLAG_TOOLS = {"launchdarkly", "unleash", "flagsmith", "growthbook", "other"}
INFRA_HEALTH_TYPES = {"http", "tcp", "process", "command"}
INFRA_TEARDOWN_MODES = {"leave-running", "session-end", "always"}
INFRA_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")

# A block-scalar header may carry a chomping indicator (`-` strip, `+` keep)
# and/or an explicit indentation indicator, in either order: `>-`, `|+`, `>2`,
# `|2-`. They are accepted and discarded — group 2 stays just the style. The
# assembler below always strips trailing newlines and re-derives the indent
# from the first non-blank line, so neither indicator has anything left to
# change; `+` (keep) is the one lossy case, and this parser has no way to
# represent trailing blank lines anyway.
_BLOCK_HEADER_RE = re.compile(
    r'^([\w.-]+):\s*([|>])(?:[0-9]+[-+]?|[-+][0-9]*)?\s*$')


class ManifestError(Exception):
    """Raised when the manifest text cannot be parsed at all."""


# --------------------------------------------------------------------------
# Scoped manifest reader
# --------------------------------------------------------------------------

def _strip_comment(line):
    """Remove a trailing/whole-line `#` comment, ignoring `#` inside quotes."""
    out = []
    in_quote = None
    for i, c in enumerate(line):
        if in_quote:
            out.append(c)
            if c == in_quote:
                in_quote = None
        elif c in ('"', "'"):
            in_quote = c
            out.append(c)
        elif c == '#' and (i == 0 or line[i - 1] in ' \t'):
            break
        else:
            out.append(c)
    return ''.join(out)


def _tokenize(text):
    """Text -> [(indent, content, block_value), ...] with comments and blank lines
    removed. block_value is None for normal lines; a string for block-scalar
    (| or >) value lines."""
    raw_lines = text.splitlines()
    out = []
    i = 0
    while i < len(raw_lines):
        raw = raw_lines[i]
        if not raw.strip() or raw.lstrip().startswith('#'):
            i += 1
            continue
        line_indent = len(raw) - len(raw.lstrip())
        content = _strip_comment(raw.rstrip())
        if not content:
            i += 1
            continue
        content_stripped = content.strip()
        m = _BLOCK_HEADER_RE.match(content_stripped)
        if m:
            key, marker = m.group(1), m.group(2)
            scalar_raw = []
            j = i + 1
            while j < len(raw_lines):
                nxt = raw_lines[j]
                if not nxt.strip():
                    scalar_raw.append('')
                    j += 1
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip())
                if nxt_indent <= line_indent:
                    break
                scalar_raw.append(nxt)
                j += 1
            base = None
            for sl in scalar_raw:
                if sl.strip():
                    base = len(sl) - len(sl.lstrip())
                    break
            if base is None:
                base = line_indent + 2
            stripped = []
            for sl in scalar_raw:
                if sl.strip():
                    stripped.append(sl[base:] if len(sl) >= base else sl.lstrip())
                else:
                    stripped.append('')
            scalar = '\n'.join(stripped).strip('\n')
            if marker == '>':
                scalar = ' '.join(line for line in scalar.split('\n')).strip()
            out.append((line_indent, key + ":", scalar))
            i = j
            continue
        out.append((line_indent, content_stripped, None))
        i += 1
    return out


def _parse_scalar(s):
    """A scalar token -> Python value (str/int/float/bool/None/list)."""
    s = s.strip()
    if s.startswith('[') and s.endswith(']'):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(x) for x in inner.split(',')]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    low = s.lower()
    if low in ('true', 'yes'):
        return True
    if low in ('false', 'no'):
        return False
    if low in ('null', '~', ''):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _parse_block(lines, i, indent):
    if lines[i][1].startswith('- '):
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines, i, indent):
    result = {}
    while i < len(lines):
        line_indent, content, block_value = lines[i]
        if line_indent != indent or content.startswith('- '):
            break
        if block_value is not None:
            key = content.rstrip(":").strip()
            result[key] = block_value
            i += 1
            continue
        key, sep, val = content.partition(':')
        if not sep:
            raise ManifestError("expected 'key: value', got: %r" % content)
        key, val = key.strip(), val.strip()
        if val:
            result[key] = _parse_scalar(val)
            i += 1
        else:
            i += 1
            if i < len(lines) and lines[i][0] > indent:
                child, i = _parse_block(lines, i, lines[i][0])
                result[key] = child
            else:
                result[key] = None
    return result, i


def _parse_list(lines, i, indent):
    result = []
    while i < len(lines):
        line_indent, content, _ = lines[i]
        if line_indent != indent or not content.startswith('- '):
            break
        item = content[2:].strip()
        # A quoted or bracketed item is a scalar even if it contains ':'
        # (e.g. framework_constraints: - "Flutter web has no hot-reload: rebuild").
        if item[:1] in ('"', "'", '['):
            result.append(_parse_scalar(item))
            i += 1
            continue
        key, sep, val = item.partition(':')
        if sep:  # list item is a map; first key sits on the `-` line
            item_indent = indent + 2
            entry = {key.strip(): _parse_scalar(val.strip()) if val.strip() else None}
            i += 1
            if i < len(lines) and lines[i][0] == item_indent \
                    and not lines[i][1].startswith('- '):
                cont, i = _parse_map(lines, i, item_indent)
                entry.update(cont)
            result.append(entry)
        else:  # scalar list item
            result.append(_parse_scalar(item))
            i += 1
    return result, i


def read_manifest(text):
    """Parse manifest YAML-subset text into a dict."""
    lines = _tokenize(text)
    if not lines:
        return {}
    if lines[0][0] != 0:
        raise ManifestError("manifest must start at indent 0")
    value, consumed = _parse_block(lines, 0, 0)
    if consumed != len(lines):
        raise ManifestError("unparsed content at line %d: %r"
                            % (consumed, lines[consumed][1]))
    if not isinstance(value, dict):
        raise ManifestError("manifest top level must be a map")
    return value


def extract_frontmatter(text):
    """Return the YAML frontmatter block of a markdown file — the text between
    the first pair of `---` fences — or None if there is none or it is
    unterminated. Companion to read_manifest, which parses the returned block.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return None


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

def find_methodology_root(start_dir):
    """Walk up from start_dir for a directory containing .engineer/manifest.yml.

    Returns (methodology_root, manifest_path) or (None, None).
    """
    d = os.path.abspath(start_dir)
    while True:
        candidate = os.path.join(d, '.engineer', 'manifest.yml')
        if os.path.isfile(candidate):
            return d, candidate
        parent = os.path.dirname(d)
        if parent == d:
            return None, None
        d = parent


# --------------------------------------------------------------------------
# Validation (Foundation Design, Section 2)
# --------------------------------------------------------------------------

def _check_range(errors, manifest, section, key, lo, hi):
    block = manifest.get(section)
    if not isinstance(block, dict) or key not in block:
        return
    v = block[key]
    if not isinstance(v, (int, float)) or not (lo <= v <= hi):
        errors.append("%s.%s must be a number in [%d, %d]" % (section, key, lo, hi))


def _check_enum(errors, manifest, section, key, allowed):
    block = manifest.get(section)
    if not isinstance(block, dict) or key not in block or block[key] is None:
        return
    if block[key] not in allowed:
        errors.append("%s.%s = %r — must be one of %s"
                      % (section, key, block[key], sorted(allowed)))


def _validate_architecture(errors, manifest):
    """Light structural validation of the optional `architecture:` section."""
    arch = manifest.get("architecture")
    if not isinstance(arch, dict):
        return
    for i, layer in enumerate(arch.get("layers") or []):
        if not isinstance(layer, dict) or not layer.get("name") \
                or not layer.get("paths"):
            errors.append("architecture.layers[%d] must have 'name' and 'paths'" % i)
    fs = arch.get("file_size")
    if isinstance(fs, dict) and "max_lines" in fs:
        ml = fs["max_lines"]
        if not isinstance(ml, int) or ml <= 0:
            errors.append("architecture.file_size.max_lines must be a positive int")


def validate_manifest(manifest):
    """Validate against the locked schema. Returns (errors, warnings)."""
    errors, warnings = [], []

    # Required fields
    if not manifest.get("methodology_version"):
        errors.append("missing required field: methodology_version")
    elif str(manifest["methodology_version"]) not in KNOWN_METHODOLOGY_VERSIONS:
        warnings.append("methodology_version %r is not a known version %s"
                        % (manifest["methodology_version"],
                           sorted(KNOWN_METHODOLOGY_VERSIONS)))

    for section in ("roadmap", "tracker"):
        block = manifest.get(section)
        if not isinstance(block, dict) or not block.get("type"):
            errors.append("missing required field: %s.type" % section)

    # Enums
    _check_enum(errors, manifest, "roadmap", "type", ROADMAP_TYPES)
    _check_enum(errors, manifest, "tracker", "type", TRACKER_TYPES)
    _check_enum(errors, manifest, "mutation", "scope", MUTATION_SCOPES)
    _check_enum(errors, manifest, "mutation", "cadence", MUTATION_CADENCES)
    _check_enum(errors, manifest, "mutation", "default_per_feature", MUTATION_DEFAULTS)
    _check_enum(errors, manifest, "autonomy", "default_level", AUTONOMY_LEVELS)
    _check_enum(errors, manifest, "agentic_summary", "format", AGENTIC_SUMMARY_FORMATS)
    _check_enum(errors, manifest, "acceptance", "impact_analysis",
                IMPACT_ANALYSIS_VALUES)
    _check_enum(errors, manifest, "git", "manual", GIT_MANUAL_VALUES)
    _check_enum(errors, manifest, "duplication", "tool", DUPLICATION_TOOLS)
    _check_enum(errors, manifest, "duplication", "skip", DUPLICATION_SKIP_VALUES)
    _check_enum(errors, manifest, "introversion", "skip", DUPLICATION_SKIP_VALUES)

    # acceptance.fixture_parity — optional project-supplied pre-test drift gate.
    acc = manifest.get("acceptance")
    if isinstance(acc, dict) and acc.get("fixture_parity") is not None:
        fp = acc.get("fixture_parity")
        check = fp.get("check") if isinstance(fp, dict) else None
        if not isinstance(check, str) or not check.strip():
            errors.append("acceptance.fixture_parity.check must be a "
                          "non-empty command string")

    val = manifest.get("validation")
    if isinstance(val, dict):
        ff = val.get("feature_flags")
        if isinstance(ff, dict):
            tool = ff.get("tool")
            if tool is not None and tool not in FEATURE_FLAG_TOOLS:
                errors.append(
                    "validation.feature_flags.tool = %r -- must be one of %s"
                    % (tool, sorted(FEATURE_FLAG_TOOLS)))
        clis = val.get("clis")
        if isinstance(clis, dict):
            for field in ("available", "suggested"):
                v = clis.get(field)
                if v is None:
                    continue
                if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                    errors.append(
                        "validation.clis.%s = %r -- must be a list of strings"
                        % (field, v))

    autonomy = manifest.get("autonomy")
    if isinstance(autonomy, dict):
        allowed = autonomy.get("allowed_levels")
        if allowed is not None:
            if not isinstance(allowed, list) or any(x not in AUTONOMY_LEVELS for x in allowed):
                errors.append("autonomy.allowed_levels must be a subset of %s"
                              % sorted(AUTONOMY_LEVELS))
        for ov in autonomy.get("path_overrides") or []:
            if isinstance(ov, dict) and ov.get("max_level") not in AUTONOMY_LEVELS:
                errors.append("autonomy.path_overrides[].max_level = %r — must be one of %s"
                              % (ov.get("max_level"), sorted(AUTONOMY_LEVELS)))
        stuck = autonomy.get("stuck_loop_threshold")
        if stuck is not None and not (isinstance(stuck, int) and stuck >= 2):
            errors.append("autonomy.stuck_loop_threshold = %r -- must be int >= 2"
                          % stuck)

    # Quality thresholds in range
    for key in ("crap_max", "coverage_min", "mutation_score_min"):
        _check_range(errors, manifest, "quality_thresholds", key, 0, 100)

    # Verification independence implies the verifier role
    verification = manifest.get("verification")
    if isinstance(verification, dict) and verification.get("enforce_independence"):
        team = manifest.get("team")
        roles = team.get("default_roles") if isinstance(team, dict) else None
        if not isinstance(roles, list) or "verifier" not in roles:
            errors.append("verification.enforce_independence is true — "
                          "team.default_roles must include 'verifier'")

    _validate_architecture(errors, manifest)
    _validate_roadmap(errors, manifest)
    _validate_infra(errors, manifest)
    _validate_infra_quirks(errors, manifest)

    return errors, warnings


def _validate_roadmap(errors, manifest):
    """Validate the `roadmap:` section beyond its `type` enum.

    A roadmap can only be onboarded if DAE can reach its host
    programmatically (a connected MCP, an installed CLI, or a usable API) —
    see references/roadmap.md. The manifest can't probe reachability, but it
    enforces that the catch-all `other` host declares HOW DAE reaches it, so
    `next`/`onboard` never have to guess (a manual-only host is `none`).
    """
    block = manifest.get("roadmap")
    if not isinstance(block, dict):
        return
    if block.get("type") != "other":
        return
    if not block.get("platform"):
        errors.append("roadmap.type is 'other' — roadmap.platform "
                      "(the hosting platform's name) is required")
    if not (block.get("url") or block.get("ref")):
        errors.append("roadmap.type is 'other' — roadmap.url (or "
                      "roadmap.ref) pointing at the roadmap is required")
    access = block.get("access")
    if access is None:
        errors.append("roadmap.type is 'other' — roadmap.access "
                      "(mcp|cli|api) is required; a manual-only host "
                      "cannot be onboarded")
    elif access not in ROADMAP_OTHER_ACCESS:
        errors.append("roadmap.access = %r — must be one of %s"
                      % (access, sorted(ROADMAP_OTHER_ACCESS)))


def _validate_infra_quirks(errors, manifest):
    """Validate the optional `infra_quirks:` section.

    Schema:
        infra_quirks:
          runtime_pins:                  # optional, map of str -> str
            java: "21"
            node: "20.x"
          port_map_file: ~/.x-ports.md   # optional, str path or null
          framework_constraints:         # optional, list of str
            - "Flutter web has no hot-reload"
          recovery_commands:             # optional, map of str -> str
            coresimulator_wedged: "killall -9 com.apple.CoreSimulator.CoreSimulatorService"
          worktree_preview: >            # optional, str: how to preview a
            set THEME_PATH to the worktree and `docker compose restart web`
    """
    quirks = manifest.get("infra_quirks")
    if quirks is None:
        return
    if not isinstance(quirks, dict):
        errors.append("infra_quirks must be a mapping")
        return
    pins = quirks.get("runtime_pins")
    if pins is not None:
        if not isinstance(pins, dict) or not all(
                isinstance(k, str) and isinstance(v, (str, int, float)) for k, v in pins.items()):
            errors.append("infra_quirks.runtime_pins must be a map of str -> str/number")
    pmf = quirks.get("port_map_file")
    if pmf is not None and not isinstance(pmf, str):
        errors.append("infra_quirks.port_map_file must be a string path or omitted")
    fc = quirks.get("framework_constraints")
    if fc is not None:
        if not isinstance(fc, list) or not all(isinstance(x, str) for x in fc):
            errors.append("infra_quirks.framework_constraints must be a list of strings")
    rc = quirks.get("recovery_commands")
    if rc is not None:
        if not isinstance(rc, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in rc.items()):
            errors.append("infra_quirks.recovery_commands must be a map of str -> str")
    wp = quirks.get("worktree_preview")
    if wp is not None and not isinstance(wp, str):
        errors.append("infra_quirks.worktree_preview must be a string or omitted")


def _validate_infra(errors, manifest):
    """Validate the optional `infra:` section.

    Schema (per entry):
        infra:
          <name>:                       # kebab-case, [a-z0-9][a-z0-9-]{0,49}
            health:                     # required
              type: http|tcp|process|command
              # http:    url (str), timeout_s (int, default 5)
              # tcp:     port (int), host (str, default localhost), timeout_s (int, default 2)
              # process: pattern (str, pgrep -f regex)
              # command: command (str), timeout_s (int, default 5)
            start:                      # required
              command: str
              background: bool          # default true
              ready_signal: str         # optional regex; otherwise health probe is used
              ready_timeout_s: int      # default 60
            teardown: leave-running|session-end|always   # default leave-running

    Optional charter-level default:
        infra:
          default_teardown: leave-running|session-end|always
    """
    block = manifest.get("infra")
    if block is None:
        return
    if not isinstance(block, dict):
        errors.append("infra must be a mapping")
        return

    default_teardown = block.get("default_teardown")
    if default_teardown is not None and default_teardown not in INFRA_TEARDOWN_MODES:
        errors.append("infra.default_teardown = %r — must be one of %s"
                      % (default_teardown, sorted(INFRA_TEARDOWN_MODES)))

    for name, entry in block.items():
        if name == "default_teardown":
            continue
        if not isinstance(name, str) or not INFRA_NAME_RE.match(name):
            errors.append(
                "infra entry name %r must be kebab-case alphanumeric, ≤50 chars" % name)
            continue
        if not isinstance(entry, dict):
            errors.append("infra.%s must be a mapping" % name)
            continue

        health = entry.get("health")
        if not isinstance(health, dict):
            errors.append("infra.%s.health is required (mapping)" % name)
        else:
            htype = health.get("type")
            if htype not in INFRA_HEALTH_TYPES:
                errors.append("infra.%s.health.type = %r — must be one of %s"
                              % (name, htype, sorted(INFRA_HEALTH_TYPES)))
            else:
                required_keys = {
                    "http": ["url"],
                    "tcp": ["port"],
                    "process": ["pattern"],
                    "command": ["command"],
                }[htype]
                for rk in required_keys:
                    if not health.get(rk):
                        errors.append(
                            "infra.%s.health.%s is required for type %s"
                            % (name, rk, htype))

        start = entry.get("start")
        if not isinstance(start, dict):
            errors.append("infra.%s.start is required (mapping)" % name)
        elif not start.get("command"):
            errors.append("infra.%s.start.command is required" % name)

        teardown = entry.get("teardown")
        if teardown is not None and teardown not in INFRA_TEARDOWN_MODES:
            errors.append(
                "infra.%s.teardown = %r — must be one of %s"
                % (name, teardown, sorted(INFRA_TEARDOWN_MODES)))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def resolve(start_dir):
    """Full resolve: returns a result dict (see module docstring)."""
    root, manifest_path = find_methodology_root(start_dir)
    if root is None:
        return None
    with open(manifest_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        manifest = read_manifest(text)
        parse_error = None
    except ManifestError as exc:
        manifest, parse_error = {}, str(exc)
    if parse_error:
        errors, warnings = ["manifest parse error: " + parse_error], []
    else:
        errors, warnings = validate_manifest(manifest)
    return {
        "methodology_root": root,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def main(argv):
    args = [a for a in argv[1:]]
    validate_only = False
    if "--validate-only" in args:
        validate_only = True
        args.remove("--validate-only")
    if len(args) > 1:
        sys.stderr.write("usage: dae_resolve.py [--validate-only] [START_DIR]\n")
        return 3
    start_dir = args[0] if args else os.getcwd()

    result = resolve(start_dir)
    if result is None:
        sys.stderr.write(
            "no .engineer/manifest.yml found walking up from %s — "
            "run /engineer.onboard first\n" % os.path.abspath(start_dir))
        return 2

    if validate_only:
        for e in result["errors"]:
            sys.stderr.write("ERROR: " + e + "\n")
        for w in result["warnings"]:
            sys.stderr.write("WARNING: " + w + "\n")
        if result["valid"]:
            sys.stderr.write("manifest valid: %s\n" % result["manifest_path"])
    else:
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
