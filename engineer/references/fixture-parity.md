# Fixture parity — seed data must match the schema before tests run

A seed/init fixture that has drifted from the canonical schema + migrations is
one of the most expensive failure modes in an ATDD project, because it fails in
**two opposite directions**:

- **False RED cliffs.** The fixture is missing a column/table the code needs, so
  acceptance tests go RED. Each time it's re-diagnosed as "fixture, not code" and
  hand-patched — a recurring diagnosis tax (wipist: `init-db.sql` missing
  `simulation_id` across 4 tables → a 24/30 cliff, re-diagnosed every run).
- **Masked real defects.** The fixture has *phantom* columns the real schema
  lacks, so broken code passes against the test DB and ships (wipist: phantom
  test-DB columns masked real money-path defects on the 3DS path).

Both come from the same root: the test DB is booted from a **hand-maintained
fixture** instead of from the canonical schema + migrations.

## The gate

If a project declares a parity check in its manifest:

```yaml
acceptance:
  fixture_parity:
    check: <command that exits non-zero when fixtures drift from schema/migrations>
    # e.g. "make db-parity", "scripts/check_fixture_parity.sh"
```

then any skill about to run acceptance or regression tests **runs that command
first, as a hard gate**:

- Exit 0 → proceed to the tests.
- Non-zero → **STOP**. Report "fixture drift — seed data is out of sync with the
  schema/migrations" and surface the command's output. Do **not** run the tests,
  and do **not** attribute the (inevitable) RED to code.

The discipline rule, even when no `check` is configured: **a RED must not be
diagnosed as fixture drift without evidence.** If you suspect the fixture, prove
it (diff the fixture against the schema) before patching the fixture — otherwise
you may be patching over a real defect.

## The real fix (out of this repo)

The gate is the *discipline layer*. The lasting fix is to stop hand-maintaining
the fixture at all — generate the test DB by applying the **canonical schema +
migrations**, so parity holds by construction. That lives in the atdd
`pipeline-builder` (which emits the harness), not the engineer plugin. Until a
project adopts generate-from-schema, the `fixture_parity.check` gate keeps the
drift from costing diagnosis time and from masking defects.

## Who runs it

- `engineer:atdd` — when generating the pipeline, if `acceptance.fixture_parity`
  is set, require the generated harness to run the check as a pre-run gate.
- `engineer:fix` — Steps 3/4/7 run the regression spec / acceptance / mutation;
  the fixture-parity contract fires before them.

## References

- `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` — validates `acceptance.fixture_parity.check`
- `${CLAUDE_PLUGIN_ROOT}/skills/atdd/SKILL.md` — pipeline generation (the bridge to atdd)
