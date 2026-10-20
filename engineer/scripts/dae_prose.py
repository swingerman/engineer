#!/usr/bin/env python3
"""dae_prose.py — flag mechanical AI tells in pipeline prose.

The mechanical half of `references/plain-prose.md`: banned words and phrases,
chatbot phrases, em-dash chains. Judgment rules stay with /engineer.refine.

  dae_prose.py <file.md>...          check files
  dae_prose.py --changed <feature-dir>   .md files under the dir changed vs. base
  dae_prose.py -                      check stdin (a PR body)

Exit 0 = clean, 1 = tells found, 2 = bad usage.

Skipped: YAML frontmatter, fenced code, inline code, blockquotes, quoted text
("..." and curly quotes), and any line holding `<!-- prose-ok -->`.
"""
import os
import re
import subprocess
import sys

# ponytail: flat word lists; tune here when a real artifact trips a false positive.
BANNED = [
    "leverage", "leverages", "leveraging", "robust", "seamless", "seamlessly",
    "delve", "delves", "utilize", "utilizes", "utilizing", "utilization",
    "serves as", "acts as a testament", "testament to", "tapestry",
    "game-changer", "game changer", "cutting-edge", "state-of-the-art",
    "holistic", "synergy", "paradigm", "empower", "empowers", "streamline",
    "streamlines", "elevate", "unlock", "unlocks", "landscape",
    "realm", "pivotal", "crucial", "vital", "myriad", "plethora",
    "navigate the", "in order to", "it is important to note",
    "it's important to note", "it is worth noting", "it's worth noting",
    "needless to say", "at the end of the day", "in today's",
    "arguably", "essentially", "basically", "very unique",
]
CHATBOT = [
    "i hope this helps", "hope this helps", "great question", "certainly!",
    "absolutely!", "i'd be happy to", "happy to help", "feel free to",
    "let me know if", "as an ai", "as a language model", "in conclusion",
    "in summary,", "i apologize", "you're absolutely right", "let's dive",
    "dive into", "dive deep",
]
EM_DASH_MAX = 2  # per line; three or more is a chain

_WORDS = [(w, re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(w), re.I))
          for w in BANNED]
_CHAT = [(w, re.compile(r"(?<!\w)%s" % re.escape(w), re.I)) for w in CHATBOT]
_INLINE = re.compile(r"`[^`]*`|\"[^\"\n]*\"|“[^”\n]*”|<!--.*?-->")
_FENCE = re.compile(r"^\s*(```|~~~)")


def prose_lines(text):
    """(lineno, line) for lines that are prose, with code and quotes removed."""
    lines = text.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":  # frontmatter
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                i = j + 1
                break
    fence = None
    for n in range(i, len(lines)):
        line = lines[n]
        m = _FENCE.match(line)
        if fence:
            if m and m.group(1) == fence:
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        if line.lstrip().startswith(">") or "<!-- prose-ok -->" in line:
            continue
        if line.startswith("    ") and not line.lstrip().startswith(("-", "*", "+")) \
                and not re.match(r"\s*\d+\.", line) and n and not lines[n - 1].strip():
            continue  # ponytail: indented code block only after a blank line
        yield n + 1, _INLINE.sub("", line)


def check_text(text):
    """Pure: list of (lineno, rule, hit)."""
    hits = []
    for n, line in prose_lines(text):
        for w, rx in _WORDS:
            if rx.search(line):
                hits.append((n, "banned", w))
        for w, rx in _CHAT:
            if rx.search(line):
                hits.append((n, "chatbot", w))
        if line.count("—") > EM_DASH_MAX:
            hits.append((n, "em-dash chain", "%d em-dashes" % line.count("—")))
    return hits


def changed_md(feature_dir):
    """.md files under feature_dir changed vs. the base branch's merge-base.
    git unavailable or no diff → every .md under the dir (fail-closed)."""
    d = os.path.abspath(feature_dir)
    def git(*a):
        p = subprocess.run(["git", "-C", d, *a], capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else ""
    top = git("rev-parse", "--show-toplevel")
    base = git("rev-parse", "--abbrev-ref", "origin/HEAD") or "origin/main"
    names = git("diff", "--name-only", "--merge-base", base, "--", d).splitlines() if top else []
    paths = [os.path.join(top, n) for n in names if n.endswith(".md")]
    if not names:
        paths = [os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f.endswith(".md")]
    return sorted(p for p in paths if os.path.isfile(p))


def check_files(paths):
    out = []
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as fh:
            out += [(p, n, r, h) for n, r, h in check_text(fh.read())]
    return out


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    if argv[0] == "-":
        hits = [("<stdin>", n, r, h) for n, r, h in check_text(sys.stdin.read())]
    elif argv[0] == "--changed":
        if len(argv) < 2 or not os.path.isdir(argv[1]):
            sys.stderr.write("--changed needs a feature dir\n")
            return 2
        hits = check_files(changed_md(argv[1]))
    else:
        hits = check_files(argv)
    for p, n, r, h in hits:
        sys.stdout.write("%s:%d: %s: %s\n" % (p, n, r, h))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
