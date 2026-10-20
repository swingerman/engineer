# Plain prose

Rules for every prose artifact the pipeline writes: ACs, specs, plans, handoffs,
session logs, fix reports, PR bodies, docs. A reader should get the concrete
claim on the first read. Vague wording in an AC means behavior nobody can test.

## Rules

1. Use the plain word. Write "use", not `utilize` or `leverage`. Write "strong" or
   name the property, not `robust`.
2. Say what the code does, not how it feels. "Retries 3 times, then returns 503"
   beats `seamlessly handles failures`.
3. Use active voice and name the actor. "The verifier writes the CP7 handoff",
   not "the handoff is written".
4. Cut filler and hedging. Drop `it is worth noting`, `in order to`, `basically`,
   `arguably`. If a claim is uncertain, state the condition under which it holds.
5. One idea per sentence. Split sentences joined by em-dashes or semicolons.
6. No decorative bold, emoji or headings. Bold marks a term the reader must not
   miss. A heading earns its place when the section is long enough to navigate.
7. No chatbot phrases: `hope this helps`, `great question`, `feel free to`,
   `let me know if`, `in conclusion`.
8. Name the thing. Replace vague nouns (`surface`, `landscape`, `realm`) with the
   file, function, field or screen.

The judgment test for each sentence: can it be restated as a fact, a number or
an instruction? If yes, restate it that way. If no, delete it.

## Enforcement

- Mechanical rules live in `${CLAUDE_PLUGIN_ROOT}/scripts/dae_prose.py`: the
  banned word list, chatbot phrases, and lines with three or more em-dashes. It
  skips frontmatter, code (fenced and inline), blockquotes and quoted text. Mark
  a line that must keep a flagged word with `<!-- prose-ok -->`.
  - `dae_prose.py --changed <feature-dir>` checks the feature's changed `.md` files.
  - `gh pr view --json body -q .body | dae_prose.py -` checks a PR body.
- `dae_mergeready.py` fails on any hit in changed artifacts or the PR body.
- `/engineer.refine` at CP6 applies the judgment test to the feature's prose.
  The XS/express lane runs only the script.
