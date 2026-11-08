# Contributing to Berger

Berger keeps agent methods in plain files and runs agents through the official
Codex and Claude Code CLIs. Changes must preserve that separation.

## Before you start

Follow the [code of conduct](CODE_OF_CONDUCT.md). The [French reference manual](docs/manuel.md) is the full
documentation; you do not need it to send a documentation or test change, and this file is self-contained.

Open an issue describing the concrete problem before a substantial change.
Write a short spec covering expected behavior, refusals, tests and scope.
Do not include agent data, local configuration, credentials or private hosts.

**Sensitive changes need a go first.** Anything that touches the broker, the sandbox wall, credentials or the vault, an
authentication or permission rule, writes into a business system, production, the firewall, or adds calls to an outside
service: open an issue titled `[spec] <topic>`, attach the short spec, and wait for the maintainer's explicit "go" in that
issue before writing code. A pull request for such a change without that go will be closed. This is the public form of the
project's go rule. A suspected vulnerability is not discussed in an issue: see [Private data and security](#private-data-and-security).

## Quick start: fork, branch, test, pull request

```bash
git clone https://github.com/<you>/berger.git && cd berger     # your fork of this repository
git remote add upstream https://github.com/lugio/berger.git
git fetch upstream
git switch -c fix-short-topic upstream/main
# ... change, add a test, update the documentation ...
bash tests/syntaxe.sh && bash tests/suites.sh && BERGER_PRET_BASE=upstream/main bash tests/pret.sh
git push -u origin fix-short-topic                              # then open the pull request on GitHub
```

No engine login, model, secret store or network is needed: the suites run on disposable installations with test doubles.

## Test dependencies

| Needed by | Install on Debian / Ubuntu | Check |
| --- | --- | --- |
| everything | `sudo apt-get install -y git bash python3` (Python **3.11 or later**, for `tomllib`) | `python3 --version` |
| sandbox tests | `sudo apt-get install -y bubblewrap gnupg` | `bwrap --ro-bind / / --dev /dev --unshare-net true` |
| web access proxy tests (`tests/web-https.py`, `tests/web-effacement.py`, …) | `cryptography` for the Python that Berger uses, see [Installing `cryptography`](#installing-cryptography) below | `python3 -c 'import cryptography'` |
| web access sandbox relay (`tests/mcp.py`) | `sudo apt-get install -y socat`. Without it Berger refuses to build the web relay (`bin/berger` raises « web = true : socat introuvable (paquet socat) »), so the web checks of `tests/mcp.py` **fail**; they are not skipped | `socat -V` |
| real-browser checks (optional) | Chromium, only if you want the browser-based checks to run; they are skipped when it is absent | |

The interpreter matters. Berger puts `~/.local/share/mise/shims`, `~/.local/bin`, `/usr/local/bin`, `/usr/bin` and `/bin` first
in `PATH` and starts its helpers with the first `python3` it finds there. If that one is older than 3.11 (Ubuntu 22.04 ships
3.10), dozens of checks fail far from the cause. `tests/clone-frais.sh` checks it. See [docs/install.md](docs/install.md#which-python-berger-uses).
Use a distribution with Python 3.11 or later, or make a 3.11 interpreter the first `python3` in that order (the CI links it
as `/usr/local/bin/python3`). Commands the broker runs always use `/usr/bin/python3` (no fallback to the `PATH`), so on a machine whose system Python is older the CI also links the 3.11 under test there, and checks it (version, `tomllib`, `cryptography`) before the tests.

### Installing `cryptography`

Recent Debian and Ubuntu protect the system Python (PEP 668): `python3 -m pip install cryptography` is refused, and pip may not be
installed at all. Use one of these, and make sure the result is visible to the `python3` Berger runs (see above).

1. **System package (preferred)**: `sudo apt-get install -y python3-cryptography`. It lands in `/usr/bin/python3`, which Berger
   finds as long as that interpreter is 3.11 or later and no `python3` earlier in the order shadows it.
2. **Virtual environment**, when the system package does not fit (for example the 3.11 interpreter is not the system one). A venv
   alone is not enough, because Berger reorders `PATH` and would not use it; make a small launcher the first `python3` of
   `/usr/local/bin`, where the CI and `tests/clone-frais.sh` look:

   ```bash
   python3 -m venv ~/.venvs/berger-tests            # run it with the 3.11+ interpreter you want to use
   ~/.venvs/berger-tests/bin/python3 -m pip install 'cryptography==43.0.3'
   if [ -e /usr/local/bin/python3 ] || [ -L /usr/local/bin/python3 ]; then   # -L: also a broken symlink
     echo "/usr/local/bin/python3 already exists: do NOT overwrite it, see below" >&2
   else
     printf '#!/bin/sh\nexec "%s/.venvs/berger-tests/bin/python3" "$@"\n' "$HOME" | sudo tee /usr/local/bin/python3 >/dev/null &&
       sudo chmod +x /usr/local/bin/python3
   fi
   PATH=/usr/local/bin:/usr/bin:/bin python3 -c 'import cryptography, sys; print(sys.version.split()[0])'
   ```

   The last line must print a version 3.11 or later without an error. If `/usr/local/bin/python3` already exists, never overwrite it: use the system package (option 1), or put the launcher in
   `~/.local/bin/python3` instead (Berger looks there first, but the CI and `tests/clone-frais.sh` do not).

## Which tests to run

Three levels, not to be confused:

1. **While you work**: `python3 tests/<topic>.py` for the part you change (seconds, no model). Useful, but not enough to open a PR.
2. **Before every pull request**: the three complete model-free gates, all green.

```bash
bash tests/syntaxe.sh      # verify: syntax of every Python and shell file
bash tests/suites.sh       # tests: every suite, one at a time by default
BERGER_PRET_BASE=upstream/main bash tests/pret.sh   # pret: finishing checks on your diff against the target branch
```

`pret` compares your branch with the target branch you name in `BERGER_PRET_BASE`: fetch it first (`git fetch upstream main`) and make sure your branch is based on it.
Add each new Python suite to `tests/suites.sh`; `pret` fails if a suite was forgotten.
`BERGER_SUITES_PARALLELE=<n>` (1 to 4) plays several suites at once; the default is one at a time because the suites are memory hungry.
Run only one `suites.sh` at a time on a machine.
3. **Engine admission** (maintainers and users, not a PR requirement): `bash tests/contrat-moteur.sh <claude|codex> <strict-agent>`
   needs a configured installation, a real engine and its login. `tests/tout.sh` is the full admission test of an installation.
   A passing model-free suite is never proof that an engine enforces its sandbox.

## What CI runs

The GitHub workflow (`.github/workflows/ci.yml`; the file is the reference) runs on every push and pull request, on a runner
with Python 3.11, `bubblewrap`, `gnupg`, `socat` (apt) and `cryptography==43.0.3` (pip) installed, and that Python linked as
`/usr/local/bin/python3`. It never starts a real engine, Herdr or a desktop notification. It plays, in this order:

1. **`pret`** on every pull request only: `BERGER_PRET_BASE=origin/<target branch> bash tests/pret.sh`, on a checkout with
   `fetch-depth: 0`. The base is the pull request's explicit target branch; without a base, or with a doubtful one, the
   job fails with a named message and never falls back to `origin/main`. It does not run on a push, which has no target branch.
2. **`bash tests/clone-frais.sh`**: a fresh, isolated clone of the committed state (its own `HOME` and `TMPDIR`, its own suites
   lock `BERGER_SUITES_VERROU`, no real engine, no real Herdr), where `tests/syntaxe.sh` then `tests/suites.sh` run.

To reproduce it locally, from a clean working tree:

```bash
bash tests/syntaxe.sh
bash tests/suites.sh
BERGER_PRET_BASE=upstream/main bash tests/pret.sh    # the target branch of your PR, fetched first (origin/main if you work in a clone of this repository)
bash tests/clone-frais.sh                            # the isolated clone, as in the CI
```

If CI is red and your local gates are green, suspect an undeclared dependency, a file you did not commit, or the wrong `python3`
first in `PATH`.

## Supporting a new engine version

A strict agent starts only on an engine version that has a closed list of known non-web tools in `tests/outils-connus/`. A new
Claude Code or Codex release has none until it is added, through a pull request, like any other change:

1. Copy `tests/outils-connus/<engine>-<old>.json` to `<engine>-<new>.json` and correct `version`.
2. Rerun the engine contract tests on your own machine, `bash tests/contrat-moteur.sh <engine> <strict-agent>`; it names the tools that
   are not in the list.
3. For each new tool, check from the engine's documentation and the contract's witness that it is **not** a web tool and
   cannot send data out, then add it to `outils`. A web tool goes in `web`, never in `outils`.
4. Open the pull request with the contract's output (no secret, no private path) and the engine's release notes link.
   A maintainer reruns the contract tests before merging. A list is not an admission: each user still reruns the contract tests.

The reference is the manual's section « À la mise à jour d'un moteur » (in French).

## Language

Issues and pull requests may be written in English or French. Keep code identifiers
consistent with the surrounding code. Update both README files together; the short
installation guide is in English and the reference manual remains in French.

## Development cycle

1. Work on a topic branch in your fork.
2. Write a test that demonstrates the new behavior. For a bug, first reproduce the failure and record its root cause.
3. Implement the smallest complete change and update its documentation.
4. Commit complete changes with descriptive messages.
5. Run the three gates above, review the diff and open a pull request.
6. Wait for independent review and the maintainer's merge decision.

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

Each `##` section of `docs/manuel.md` has its own sha256 in `tests/attendus/manuel/<section>.sha256`. After editing a section,
run `python3 -I tests/manuel-empreintes.py recalculer <section>` (no name: all sections); `tests/vitrine.py` names any section
whose fingerprint is stale, added or removed. Two pull requests on different sections then share no fingerprint file.

Keep claims tied to evidence. Name any check that could not run and explain why.
Never describe a model-free unit test as proof of engine sandbox admission.

## Changelog entries

Do not edit `CHANGELOG.md` in a topic branch. Write your entry in `changelog.d/<topic>.md`, where `<topic>` is your branch
name (lower case letters, digits and dashes). Use only Keep a Changelog sections, in English, followed by bullets:

```markdown
### Fixed

- What changed, for the user, in one sentence.
```

No `#` or `##` heading, no sub-folder, no link or executable file. `python3 -I tests/changelog.py verifier` checks it (it runs
in `tests/suites.sh`). Two pull requests then never touch the same changelog file. At release time the maintainer runs
`python3 -I tests/changelog.py regrouper <x.y.z> <YYYY-MM-DD>`, which writes the version entry and deletes the fragments; a
version tag is refused while a fragment is left.

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
