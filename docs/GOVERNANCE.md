# Repository governance

## Canonical branch

`main` is the canonical source of integration truth for 0liviA.

Branch new work from `main`. Pull requests that change product code, tests, workflows,
deployment material or architecture documentation target `main`.

## Compatibility mirror

`arch/gpt-synthesis-v1` is a compatibility mirror retained for historical links and
older automation. Do not base new work on `arch/gpt-synthesis-v1`.

The mirror must not become a second product line. If it diverges, reconcile it to the
exact canonical `main` tree and preserve both histories with an ordinary merge commit.

## Required merge gate

Before merging product changes:

1. inspect the live `main` HEAD;
2. run the repository CI on the exact candidate SHA;
3. require Python 3.11 and 3.12 jobs to pass;
4. preserve secret-tree/history scans, syntax gates and test coverage;
5. avoid direct production deployment unless the task explicitly authorizes it.

## Platform enforcement

GitHub branch protection or repository rulesets should require pull requests and the
core CI checks on `main` when repository administration permissions are available.
Repository documentation/tests are defense in depth and do not replace server-side
branch protection.
