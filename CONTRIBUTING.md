# Contributing to Berger

Berger keeps agent methods in plain files and runs agents through the official
Codex and Claude Code CLIs. Changes must preserve that separation.

## Before you start

Follow the [code of conduct](CODE_OF_CONDUCT.md).

Read the [French reference manual](docs/manuel.md) and the
[development process](docs/plans/2026-10-12-processus-dev-generique-spec.md).
Use Linux, Git, Bash and Python 3.11 or later. The test suites also exercise
bubblewrap and GnuPG when available. Engine subscriptions and a personal
configuration are not needed for the model-free suites.

Open an issue describing the concrete problem before a substantial change.
Write a short spec covering expected behavior, refusals, tests and scope.
Do not include agent data, local configuration, credentials or private hosts.

## Language

Issues and pull requests may be written in English or French. Keep code identifiers
consistent with the surrounding code. Update both README files together; the short
installation guide is in English and the reference manual remains in French.

## Development cycle

1. Work on a topic branch in a separate checkout.
2. Write a test that demonstrates the new behavior. For a bug, first reproduce
   the failure and record its root cause.
3. Implement the smallest complete change and update its documentation.
4. Commit complete changes with descriptive messages.
5. Run the gates below, review the diff and submit a pull request.
6. Wait for independent review and the maintainer's merge decision.

```bash
bash tests/syntaxe.sh
bash tests/suites.sh
bash tests/pret.sh
```

These are the `verify`, `tests` and `pret` gates. The last gate compares the
branch with `origin/main`; fetch that branch before running it.
The complete model-free suites create disposable installations and use test
doubles. They do not require your agent engine login or your secret store.

To prove that the committed change works in a fresh checkout with an isolated
home directory, start with a clean working tree and run:

```bash
bash tests/clone-frais.sh
```

This test uses only a local clone and runs `verify` and `tests` there. It is a
separate manual check, not a nested replay inside the local `tests` gate.
The GitHub workflow runs this same fresh-clone check. The local community suite
keeps its lightweight file checks. Do not substitute `tests/tout.sh`: that is the
full admission test for a configured installation, including real engines.

## Code layout

- A **view** is one file in `bin/vues/` (with its `.schema.json`); a **command** family is one file in `bin/commandes/`
  (`FAMILLE`, `VERBES`, `AIDE`, `DROITS`); an **engine** is one file in `bin/moteurs/`; a broker **tool** type is one file
  in `courtier/outils/` (broker code: go rule, see below).
- Views and commands: core API only (`bin/noyau/api.py`) and the standard library. Engines: the API, plus `BASE_NOYAU`,
  what the core lends them and `executable_moteur`, `version_moteur`, `verdict_moteur`, until lot 4. `tests/contrat-noyau.py` proves it; adding a name to the API takes a line there and a test.
  A faulty module is set aside and named (`berger etat`); the others keep running.
- Size: at most 1,500 lines per file under `bin/` (2,000 for a file in `bin/commandes/`). `bin/berger` follows a ratchet
  in `tests/taille-fichiers.py` that can only go down.
- Anything that touches the broker, the wall, credentials or the vault falls under the go rule: write a short spec and wait
  for the owner's go before coding.

## Tests and documentation

Add each new Python suite to `tests/suites.sh`. The `pret` gate checks that no
suite has been forgotten. Changes to runtime code must include both a test and
documentation. A passing syntax check alone does not prove behavior.

Keep claims tied to evidence. Name any check that could not run and explain why.
Never describe a model-free unit test as proof of engine sandbox admission.
See the manual's security section for the boundary and the installation tests.

## Pull requests

Describe the triggering problem, resulting behavior, scope and checks actually
run. A bug fix must state its root cause and include a regression test. Explain
any remaining limitation. Keep unrelated refactoring in a separate change.

A maintainer reviews the code and reruns the gates before merging. Merging does
not authorize a deployment, publishing a release, or changing a user's services.

## Private data and security

Never submit real agent journals, personal configuration, browser profiles,
credentials or secret-store contents, even as a test fixture. Use fictional
values or generate test values at runtime. For a suspected vulnerability, use
the private GitHub reporting channel described in [SECURITY.md](SECURITY.md);
do not open a public issue containing an exploit or sensitive data.
