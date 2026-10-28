# Changelog

All notable changes to Berger are documented in this file.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-28

Berger goes public and its codebase is reorganised. This version brings the public repository (onboarding guide, README
captures on fictitious data, logo, a green continuous integration), the reunion of the development line and the
installation line into one history, the post-production alignment declared by a project, the modular core (lots 1 to 3 bis:
shared base with an explicit API, one file per engine, one file per family of verbs), neutral wording throughout and a witness
line check for Claude's personal instructions. Source tree only: it does not assert that a release has been published or a Git
tag has been created.

### Added

- Public onboarding: a documented setup path and the exact public clone command, `docs/` decisions kept for the public, and a
  repository check (`verifier-depot`) that admits the one exact URL of the public repository and rejects former third-party
  product references and business-software names.
- README showcase: Home and broker views on fictitious data, logo and icon.
- Post-production alignment (`docs/alignement.md`): a project declares what must follow a release (changelog, wiki, memory,
  skills, versions); a faulty declaration stops the broker at load, and without it nothing changes.
- Per-agent layout: `agents/<agent>/espace.toml` takes precedence over the shared workspace layout.
- Witness-line check for Claude's personal instructions, in `tests/tout.sh`: instead of the model's own YES/NO, it picks a line of
  `~/.claude/CLAUDE.md` absent from the corpus it looks in (the agent folder, `.claude/skills`, `skills-agent`, `commun/`, `@`-imported
  files) and asks Claude to copy it after a marker line; only the word ABSENT passes, an engine error is "not measurable".
  `tests/consignes-canari.py` tests only its choice and comparison functions, without a model.
- Test suites count the unittest tests they play; a suite without any check is reported as NOT MEASURED.
- `docs/ROADMAP.md`: the planned, not yet started, gradual move from Python to Rust, after lot 4 of the modular work.

### Changed

- Modular core, lot 1: the shared base (configuration, private transport, display, agent files, Herdr door, read-only readers)
  moves to `bin/noyau/` with an explicit, named API (`bin/noyau/api.py`); views receive that API instead of a copy of every
  core global. Pure move, no behaviour change. New checks: `tests/contrat-noyau.py`, `tests/taille-fichiers.py`.

- Modular core, lot 2: each engine moves to its own file in `bin/moteurs/` (`claude.py`, `codex.py`; admission, choice and launch
  arguments in `bin/moteurs/__init__.py`), engines are loaded from that folder instead of a fixed list, and the consumption readers
  follow their engine. An engine that fails to load is set aside and named (`berger etat`), never silently replaced by the other.
  Walls, masks and MCP generation stay in the core until lot 4. Pure move, no behaviour change.

- Modular core, lot 3: the commands move to `bin/commandes/`, one family of verbs per file, loaded from that folder like the views and the
  engines. `main()` no longer knows any verb: it looks it up in one registry (`FAMILLE`, `VERBES`, `AIDE`, `DROITS` per family), and the verbs
  that need a private JSON entry are declared there instead of being written in `main()`. A family uses the noyau API only: the core lends it
  nothing and no private noyau name is visible to it, so a verb that calls a core function, the broker, the wall, the sandbox, the engine
  settings or the credentials stays in the core until lot 4 (58 of the 60 verbs; only `livrable` and `veille` move) and is registered in the
  same registry by a transition family. A family that fails to load, that declares a verb another family declares, or whose verb fails when
  called is set aside and named (`berger etat`), with two exceptions: the transition family calls the core without interception, and
  `SystemExit` and `KeyboardInterrupt` always pass. Two names join the noyau API: `LECTURES` and `EXTENSIONS`.
  New check: `tests/commandes-couverture.py`.

- Modular core, lot 3 bis: eight more verbs move to `bin/commandes/` (`etat`, `validations`, `vues`, `titres`, `statusline`, `notifier`, `noter`,
  `lire`; 50 of the 60 verbs stay in the core until lot 4). Their functions move to the noyau (`registre.py`, `ecrans.py`, `bandeaux.py`) and ten
  names join its API, each with its test: `journal`, `Refus`, `liste_vues`, `etat`, `validations`, `lire_document`, `lire_interactif`,
  `notifier`, `mettre_a_jour_titres`, `statusline`. None goes through the broker, the wall, the sandbox, the engine settings, the credentials,
  the vault, rights, missions, messages, teams, installation, backup or audit. The registers of set-aside views, engines and command families
  live in the noyau so `berger etat` reads them without importing the core. A family may declare, per verb, the exceptions it lets through unchanged (`PASSE`: `Refus`, the usage refusal of the API, or `IndexError` for `statusline`); any other defect, an internal `ValueError` included, still sets the family aside, except that the transition family calls the core without interception and `SystemExit` and `KeyboardInterrupt` always pass. `vue` stays in the core: `vue fiche --json` reaches the wall (`masques`). `bin/berger` shrinks from 4 439 to about 4 200 lines (ratchet lowered).

- Describe Berger directly in comments and the manual, and reject former
  third-party product references with a configuration-independent repository check.

- Keep the fresh-clone proof in CI and as a manual command, while the local
  community suite checks its files without replaying the complete test suite.

- Continuous integration (already present in 0.1.0): the runner now installs what the checks need (`bubblewrap`, `gnupg`, `socat`,
  `cryptography`) and exposes the system Python 3.11 as `python3`; the CI is green for the first time.

### Fixed

- Test suites no longer reach the real Herdr server (they had created about 80 workspaces in the real session). Isolation is now
  positive: `tests/suites.sh` imposes a stand-in Herdr on every suite, and each suite imports `tests/_herdr_isole.py` first, so it is
  isolated when run alone too; inherited `HERDR_*`, `XDG_CONFIG_HOME` and `BERGER_HERDR_SOCKET` are removed. The guard
  `tests/herdr-fuite.py` has a positive control (without isolation the real path is reached). The real acceptance runs
  (`tests/tout.sh`, `tests/sonde-herdr*.py`) stay connected to the real Herdr on purpose.
- Views keep their results and refusals under heavy activity, and long titles are bounded.
- Reunion of the development line and the installation line: eight fixes that had only landed on one side now live in the
  shared history, with five tests adapted; texts that came from the installation line follow the neutrality rule.
- Test helpers launch `bin/berger` with the interpreter of the test, and `regle-go` puts it first in `PATH`.

## [0.1.0] - 2026-10-21

### Added

- Initial documented baseline: agents described by plain files, with memory,
  checklists, scheduled work and a choice of Codex or Claude Code.
- Herdr workspaces, a broker for controlled tool access, engine admission tests
  and model-free regression suites.
- French reference manual and a short repository entry point.
- Contribution guidelines, private reporting policies, issue and pull request
  templates, and a workflow for model-free checks in a fresh local clone.
- MIT license.

This entry records the initial version in the source tree. It does not assert
that a release has been published or a Git tag has been created.
