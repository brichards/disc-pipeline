# disc-pipeline

`BACKLOG.md` holds the ordered plan. Reference item IDs (`DP-04`) in commits.

## Documentation

`README.md` is the style reference. Match it rather than describing it back.

- Tables carry detail: flags, requirements, stages. Prose covers only what a table cannot.
- Each command section is usage block, then flag table, then `Notes:` bullets if needed.
- Declarative present tense. Second person for instructions.
- Cross-reference by anchor, e.g. `[Decoy discs](#decoy-discs)`.
- Plain ``` fences, no language tag. No emoji. No hard wrap.
- State what does not work in `Current Limitations`, not in a footnote.
- Rationale belongs in `Design notes` at the end, and only for facts about external tools.

Any change to a command or feature updates `README.md` in the same branch.

## Comments

Default to none. A comment earns its place by explaining something outside this
codebase that the reader cannot derive: MakeMKV's undocumented attribute IDs,
macOS leaving mount points behind after ejection, Blu-ray never carrying AAC.

Why a threshold is 240 rather than 300, what incident prompted a change, what
was considered and rejected — these go in the commit message.

No comment restates the code or a name.

## Tests

pytest, a development dependency. The runtime stays standard library only, so
tests run from a venv the scripts never touch:

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

A test earns its place by catching a failure that has happened or plausibly
will. Judge each one by whether it would be written first if there were no
tests at all. No coverage targets.

Before trusting a new test, break the code it covers and confirm it fails. A
test that passes against a mutated codebase is testing something else.

## Flags

Two meanings, one name each:

- `--redo` repeats work already marked done.
- `--force` overrides a refusal.

## Git

- One thought per commit, one branch per change.
- Merge with `--no-ff`, then delete the branch.
- Non-verbose subject lines. Body carries the reasoning.

## Verifying a change

`py_compile` does not evaluate default arguments, which has hidden a crash
before. Import every module and run `--help` on every script:

```
python3 -c "import sys; sys.path.insert(0,'.'); import importlib, pathlib; [importlib.import_module('discpipe.'+p.stem) for p in pathlib.Path('discpipe').glob('*.py') if p.stem != '__init__']"
for s in bin/disc-*; do "$s" --help >/dev/null || echo "FAIL $s"; done
```
