#!/usr/bin/env python3
"""dae_release.py — automate the DAE plugin release + cache-sync dance.

Editing the marketplace clone does NOT reach the running plugin: Claude Code
loads the *cache* copy at ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/,
pointed to by installed_plugins.json. Shipping an edit means: bump the source
plugin.json, build a cache dir for the new version, repoint installed_plugins.json
(installPath AND version), and verify. Done by hand this is ~5 error-prone steps
across two files — this script does it atomically.

Usage:
  dae_release.py <plugin> [--bump patch|minor|major] [--set-version X.Y.Z] [--apply]

Default is a dry-run (prints the plan). --apply performs it:
  1. back up installed_plugins.json
  2. write the new version into the source plugin.json (targeted, minimal diff)
  2b. sync the plugin's entry in the marketplace's marketplace.json
  3. copy source -> a fresh cache dir for the new version (skips .git/.build/pycache)
  4. repoint installed_plugins.json entry (installPath + version + lastUpdated)
  5. verify cache plugin.json, marketplace entry, and install pointer all agree

Output: JSON plan/result. Exit 0 ok; 2 plugin/source not found; 3 usage error;
4 refused (cache dir already exists — use --force).
"""
import json
import os
import re
import shutil
import sys
from datetime import date

HOME = os.path.expanduser("~")
MARKETPLACES = os.path.join(HOME, ".claude", "plugins", "marketplaces")
CACHE = os.path.join(HOME, ".claude", "plugins", "cache")
INSTALLED = os.path.join(HOME, ".claude", "plugins", "installed_plugins.json")

_VERSION_RE = re.compile(r'("version"\s*:\s*)"[^"]*"')
_COPY_IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".build")


class ReleaseError(Exception):
    pass


def bump_version(cur, level):
    """Semver bump. cur='0.20.0', level in {patch,minor,major} -> new string."""
    try:
        major, minor, patch = (int(x) for x in cur.split("."))
    except ValueError:
        raise ReleaseError("version %r is not X.Y.Z" % cur)
    if level == "major":
        return "%d.0.0" % (major + 1)
    if level == "minor":
        return "%d.%d.0" % (major, minor + 1)
    if level == "patch":
        return "%d.%d.%d" % (major, minor, patch + 1)
    raise ReleaseError("bad bump level: %r" % level)


def find_source(plugin, marketplaces=MARKETPLACES):
    """Locate the plugin's source dir by matching .claude-plugin/plugin.json name.
    Returns (source_dir, marketplace_name, plugin_json_path, current_version)."""
    if not os.path.isdir(marketplaces):
        raise ReleaseError("no marketplaces dir: %s" % marketplaces)
    for mk in sorted(os.listdir(marketplaces)):
        # <mk>/<plugin>/ is the common layout; <mk>/ itself is a plugin whose
        # marketplace entry has source "./" (atdd).
        for cand in (os.path.join(marketplaces, mk, plugin, ".claude-plugin", "plugin.json"),
                     os.path.join(marketplaces, mk, ".claude-plugin", "plugin.json")):
            if not os.path.isfile(cand):
                continue
            with open(cand, encoding="utf-8") as f:
                meta = json.load(f)
            if meta.get("name") == plugin:
                return (os.path.dirname(os.path.dirname(cand)), mk, cand,
                        meta.get("version"))
    raise ReleaseError("plugin %r not found under %s" % (plugin, marketplaces))


def _set_plugin_version(text, new_version):
    """Rewrite only the "version": "..." value; minimal diff, key order kept."""
    new, n = _VERSION_RE.subn(r'\1"%s"' % new_version, text, count=1)
    if n != 1:
        raise ReleaseError("could not find a version field to bump")
    return new


def _set_marketplace_version(text, plugin, new_version):
    """Rewrite the named plugin's "version" inside marketplace.json.

    marketplace.json carries several version fields — one under `metadata` for
    the marketplace itself, plus one per plugin entry. This targets the first
    `"version"` *following* that plugin's `"name"`, which is unambiguous because
    the metadata block precedes the plugins array. The marketplace's own
    `metadata.version` is deliberately left alone: bumping it is a release
    decision about the marketplace, not a side effect of shipping one plugin.

    Returns (new_text, changed). A plugin absent from the manifest is not an
    error — some plugins are installed but unlisted.
    """
    m = re.search(r'"name"\s*:\s*"%s"' % re.escape(plugin), text)
    if not m:
        return text, False
    head, tail = text[:m.end()], text[m.end():]
    new_tail, n = _VERSION_RE.subn(r'\1"%s"' % new_version, tail, count=1)
    if n != 1:
        return text, False
    return head + new_tail, True


def plan_release(plugin, level="patch", set_version=None,
                 marketplaces=MARKETPLACES, cache=CACHE):
    src_dir, mk, pj_path, cur = find_source(plugin, marketplaces)
    new_version = set_version or bump_version(cur, level)
    cache_dir = os.path.join(cache, mk, plugin, new_version)
    mkt_json = os.path.join(marketplaces, mk, ".claude-plugin",
                            "marketplace.json")
    return {
        "plugin": plugin, "marketplace": mk,
        "source_dir": src_dir, "plugin_json": pj_path,
        "marketplace_json": mkt_json if os.path.isfile(mkt_json) else None,
        "current_version": cur, "new_version": new_version,
        "cache_dir": cache_dir,
        "installed_key": "%s@%s" % (plugin, mk),
        "cache_exists": os.path.isdir(cache_dir),
    }


def apply_release(pl, installed_path=INSTALLED, force=False):
    """Execute a plan dict from plan_release(). Returns a result dict."""
    if pl["cache_exists"] and not force:
        raise ReleaseError(
            "cache dir already exists: %s (use --force to overwrite)"
            % pl["cache_dir"])

    # 1. back up the install manifest
    backup = None
    if os.path.isfile(installed_path):
        backup = installed_path + ".bak"
        shutil.copy2(installed_path, backup)

    # 2. bump the source plugin.json (targeted)
    with open(pl["plugin_json"], encoding="utf-8") as f:
        text = f.read()
    with open(pl["plugin_json"], "w", encoding="utf-8") as f:
        f.write(_set_plugin_version(text, pl["new_version"]))

    # 2b. keep the marketplace manifest in step. This is what the marketplace
    # advertises to anyone installing; letting it drift from plugin.json means
    # shipping a version nobody can install. (engineer once advertised 0.18.0
    # while 0.21.0 was live, because this step did not exist.)
    marketplace_synced = False
    if pl.get("marketplace_json"):
        with open(pl["marketplace_json"], encoding="utf-8") as f:
            mtext = f.read()
        mnew, marketplace_synced = _set_marketplace_version(
            mtext, pl["plugin"], pl["new_version"])
        if marketplace_synced:
            with open(pl["marketplace_json"], "w", encoding="utf-8") as f:
                f.write(mnew)

    # 3. build the cache dir
    if pl["cache_exists"] and force:
        shutil.rmtree(pl["cache_dir"])
    shutil.copytree(pl["source_dir"], pl["cache_dir"], ignore=_COPY_IGNORE)

    # 4. repoint the install manifest
    repointed = False
    if os.path.isfile(installed_path):
        with open(installed_path, encoding="utf-8") as f:
            manifest = json.load(f)
        entries = manifest.get("plugins", {}).get(pl["installed_key"])
        if entries:
            entries[0]["installPath"] = pl["cache_dir"]
            entries[0]["version"] = pl["new_version"]
            entries[0]["lastUpdated"] = date.today().isoformat()
            with open(installed_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=1)
                f.write("\n")
            repointed = True

    # 5. verify
    cache_pj = os.path.join(pl["cache_dir"], ".claude-plugin", "plugin.json")
    cache_ver = None
    if os.path.isfile(cache_pj):
        with open(cache_pj, encoding="utf-8") as f:
            cache_ver = json.load(f).get("version")
    # The marketplace entry is part of "shipped": a correct cache and install
    # pointer still leave the plugin uninstallable-at-the-right-version if the
    # manifest advertises something else.
    mkt_ok = marketplace_synced or not pl.get("marketplace_json")
    ok = ((cache_ver == pl["new_version"])
          and (repointed or not os.path.isfile(installed_path))
          and mkt_ok)

    return {**pl, "applied": True, "backup": backup, "repointed": repointed,
            "marketplace_synced": marketplace_synced,
            "cache_version": cache_ver, "verified": ok}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    plugin = argv[0]
    rest = argv[1:]
    level = "patch"
    set_version = None
    apply = "--apply" in rest
    force = "--force" in rest
    if "--bump" in rest:
        level = rest[rest.index("--bump") + 1]
    if "--set-version" in rest:
        set_version = rest[rest.index("--set-version") + 1]

    try:
        pl = plan_release(plugin, level=level, set_version=set_version)
        result = apply_release(pl, force=force) if apply else pl
    except ReleaseError as exc:
        sys.stderr.write("%s\n" % exc)
        return 4 if "already exists" in str(exc) else 2
    except (IndexError, KeyError):
        sys.stderr.write("usage: dae_release.py <plugin> "
                         "[--bump patch|minor|major] [--set-version X.Y.Z] [--apply]\n")
        return 3
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
