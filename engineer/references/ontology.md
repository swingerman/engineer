# The DAE ontology — constraints at the ledger, not in prose

DAE has always had an ontology. Entities: `Feature`, `AC`, `SpecScenario`,
`Plan`, `Handoff`, `Checkpoint`, `ADR`, `TrackedFeature`, `RoadmapItem`, `Fix`.
Relations between them: `covers` (AC → scenario), `parent_feature`, `verifies`
(handoff → checkpoint), `roadmap_ref`. Constraints on both.

Until now it lived as an English rule table inside the `consistency-check`
skill, evaluated by an LLM reading prose. Across 121 skill invocations in a
three-week sample, `consistency-check` ran **once**. A constraint that only
holds when someone remembers to ask for it is not a constraint.

`scripts/dae_ontology.py` is that table made executable and moved to the
**ledger position** — it runs at every checkpoint exit, before the handoff is
written. Read-only, stdlib-only, milliseconds.

## The split: mechanical vs judgment

| Stays in the script | Stays in `consistency-check` |
|---|---|
| Is `status` a legal value? | Are these ACs written in domain language? |
| Does `ac_count` match the ACs present? | Do the ACs cover the feature's outcome? |
| Does every AC have a scenario? | Is *this* scenario a good test of *that* AC? |
| Do parent and child agree? | Is this parent/child decomposition sensible? |
| Is the verifier ≠ the implementer? | Was the verification actually rigorous? |

The left column is a join over structured data. The right column is judgment.
Do not migrate the right column into the script — a check that returns a
confident wrong answer is worse than one that was never written.

## Constraint vocabulary

Borrowed from OWL, because naming a check precisely is most of its value: it
makes the *missing* checks obvious. Add a constraint by naming its kind first.

| Kind | Meaning | Where it bites |
|---|---|---|
| **enumeration** | value comes from a fixed set | `status: probably-shipped` — the talk's own example. Also `assignee`, `autonomy_level`, handoff `checkpoint` |
| **functional** | at most one holder ("exactly one father") | one feature branch per feature; one feature per roadmap item; `ac_count` == ACs present; `slug` == its folder |
| **inverse** | two properties must agree both ways | `parent_feature` ↔ `child_features` |
| **transitive** | the relation chains, so it must not cycle | `parent_feature` loops |
| **disjoint** | two roles, never the same individual | Principle 7: the refiner is not the implementer; the verifier is neither |
| **closure** | every X reachable from some Y | every AC has a `@AC-N` scenario; every tagged AC exists |

## The coverage join — the part prose cannot do

`closure` is the reason this is a script rather than a longer checklist. Given
the `@AC-N` Gherkin tags in `spec.md` and the `## AC-N` headings in `acs.md`,
"which acceptance criteria have no scenario?" is a set difference. An LLM asked
to eyeball two documents for the same answer will usually be right and
occasionally be confidently wrong, and you cannot tell which from the output.

This is the same gap analysis `fix` performs *after* a bug ships ("was the AC
missing, or the spec, or the test?"). Running it before implementation is the
whole point.

**Non-adoption is not a defect.** A `spec.md` with *zero* `@AC-N` tags gets one
warning saying coverage cannot be checked — not one error per AC. Partial
adoption is a real gap; never adopting the convention is a project's choice.

## Modelling rules learned the hard way

The first version produced 71 errors on one repo, nearly all false. Three
lessons, each a case of the model not matching the domain:

1. **One individual, several names.** `012-washer-tracking` and
   `washer-tracking` are the same feature — `slug` and `parent_feature` carry
   the bare form in the wild while folders carry the numbered one. Identity
   comparisons normalize through `bare_slug()`. Demanding one convention would
   have been the model dictating to the domain.
2. **Trunk is shared by construction.** A multi-repo umbrella runs every feature
   off `master`. Branch uniqueness is a real constraint over *feature* branches
   and meaningless over trunk.
3. **Severity is part of the model.** A half-linked parent/child pair is untidy
   and breaks nothing downstream — warning. A reference to a feature that does
   not exist breaks traversal — error. Getting this wrong makes the gate noise,
   and a noisy gate gets disabled.

## Usage

```
dae_ontology.py <feature-dir>            # one feature
dae_ontology.py --project [START_DIR]    # cross-feature relations
dae_ontology.py ... --json               # machine-readable findings
```

Exit `0` = no errors (warnings may be present), `1` = at least one error,
`2` = bad usage. Feature scope is what runs at a checkpoint exit; `--project`
belongs in `consistency-check --project` and CI.

## Deliberately not built

RDF/Turtle serialization, a triple store, SPARQL, an external reasoner,
schema.org or Dublin Core alignment. Ten entity types in one repository do not
need a graph database — the relational pain that motivates one starts at a
different order of magnitude, and every one of those would be a dependency
where a set difference suffices.

Revisit when the entity count passes ~30, or when a second tool needs to
*query* the graph rather than validate it.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md` — the checkpoint-exit gate rule
- `${CLAUDE_PLUGIN_ROOT}/references/spec-ir.md` — why coverage reads `spec.md`, not the IR
- `${CLAUDE_PLUGIN_ROOT}/references/host-capabilities.md` — `--json` output feeds an optional rendered report; cross-feature violations are inherently tabular
- `${CLAUDE_PLUGIN_ROOT}/skills/consistency-check/SKILL.md` — the judgment half
