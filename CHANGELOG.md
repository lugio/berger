# Changelog

All notable changes to Berger are documented in this file.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-11-01

**Security release: users of 0.2.0 should update.** A strict agent could use the engines' built-in web tools (WebFetch and
WebSearch on Claude, `web_search` on Codex), which do not go through the broker, so it could read any site and send data out in a
URL or a query with nothing logged. This version closes them for every strict agent and checks it with a closed list of known
non-web tools per engine and version in the engine contract. Codex is admitted again as a first-class engine, next to Claude Code.

**Upgrade:** `git pull`, `berger regenerer`, then restart each strict agent with `berger relancer <agent>` (one agent at a time; there is no
command for all of them, and an agent at work is refused until it rests), for example
`for d in ~/berger/agents/*/; do grep -qE '^mur *= *ouvert' "$d/agent.conf" || berger relancer "$(basename "$d")"; done`, then rerun the contract tests, `bash tests/contrat-moteur.sh claude <strict-agent>` and
`bash tests/contrat-moteur.sh codex <strict-agent>` outside the sandbox (otherwise the first strict launch waits for the contract,
several minutes), then `berger refaire-espace berger`.

### Added

- **Supported versions** (closed lists in `tests/outils-connus/`): Claude Code 2.1.312 and 2.1.314, Codex 0.160.0 and 0.165.0.
  A list is not an admission: a strict agent starts only after the contract passed for that exact version on the user's machine.
  For another version, check (12) fails and names the new tools against the most recent list; the list is completed through a
  reviewed change (manual, « À la mise à jour d'un moteur »), then the contract tests are rerun. An older ADMIS verdict written without
  (12) no longer admits; the contract tests are rerun before the next strict launch, never admitted without (12), never blocked without an attempt.
- New root option `codex_modele_strict` forces a model with `-m` on strict Codex agents.

### Changed

- **Berger space: 11 → 5 tabs** (view only; no change to the broker, the wall, the secrets or the validations): **Home** (red and
  yellow alerts on top with "since when", consumption on the side; **every red alert is listed**, only yellow ones beyond two fold into "… and N more"),
  **Decisions**, **Board**, **To read** and **Behind the scenes** (Broker, Exchanges, Sources and Catalogue). Home and Decisions show as "waiting for you" only what needs the
  owner's gesture; reads are never decisions. `berger refaire-espace berger` removes the old tabs by their exact title (never a tab you
  added) and puts the new ones in order. Tests: `tests/refonte-espace.py`.
- **Agent web access** (lots 1 and 1 bis): any strict agent gets the `web` MCP server from its own `agent.conf`. A `--post` access
  is accepted only within a closed list of formats (named headers, one `Content-Type` among form, JSON, text or `multipart/form-data`,
  strict UTF-8, no file), every decoded form of a URL, header or body goes through the broker's secret detector, and a path containing
  `delete` passes only for a POST the owner validated as such. Tests: `tests/web-effacement.py`, `tests/mcp.py`.
- **Lighter merge gates**: a `doc` gate replaces `tests` when the diff touches only documentation (`docs/plans/2026-10-28-portes-allegees-spec.md`);
  `verify` and `pret` still run. A merge validation carries the full commit SHA shown at preview; a remote gate is green only if it
  reports that SHA.
- **Models by level and type of work** (`[modeles.<engine>]`, `[modeles.types]`, `Type : <type>` line of a mission).
- **Test suites**: played one at a time by default, in parallel with `BERGER_SUITES_PARALLELE=<n>` (1 to 4), one `suites.sh` at a time on
  the machine, Herdr proved out of reach of every suite.
- **Publication**: after a successful installation, `berger courtier redemarrer --publier <forge>` pushes the installed commit
  (fast-forward only, never forced) and the `v*` tags that are its ancestors; new verb `berger publier <forge>`. Off unless the owner sets `publication`.
- **Modular core, lots 4a to 4c** (missions, messages and needs, teams): command families in `bin/commandes/`, read and action APIs
  in `bin/noyau/`; outputs, refusals and rights unchanged (`tests/equivalence-*.py`). `bin/berger`: 4 237 → 4 050 lines.
- Public repository: self-contained English `CONTRIBUTING.md` (fork, branch, test dependencies, which tests, what CI runs, adding an engine version's closed list); `docs/install.md` gains engine versions, a minimal commented sensitive configuration and « Which Python Berger uses »; `config.exemple.toml` comments in English; `docs/ROADMAP.md` updated; the code of conduct has its own reporting path (GitHub « Report content », or a short public issue without detail asking for a private contact; no e-mail address), distinct from the vulnerability channel; `docs/plans/` keeps the decisions in force and moves the 40 finished plans to `docs/plans/archive/`, with an index (`docs/plans/README.md`) giving each one's status.

### Security

- **Built-in web tools closed** for every strict agent. Claude: `WebFetch` and `WebSearch`, plus the tools that leave the machine or
  run outside the scheduler (`RemoteTrigger`, `PushNotification`, `DesignSync`, `SendMessage`, `ListAgents`, `Workflow`, `CronCreate`,
  `CronDelete`, `CronList`, `ScheduleWakeup`), are denied in the generated settings. Codex: `web_search="disabled"`, `features.sleep_tool=false`
  and `features.multi_agent=false`. Open agents are unchanged.
- **Contract check (12), closed list**: every tool of the strict agent must be a known non-web tool of this engine and version. Claude
  tools are compared by name; Codex tools are read from both `tools` and `additional_tools`, validated for structure, and compared as
  (type, name) pairs. MCP tools relayed by `berger-mcp` are known only for the servers in the agent's own `mcp =`. A positive witness
  must show every web tool when Berger's refusal is lifted (Codex: on the named witness model, `modele_temoin`). Any unknown tool or
  incomplete trace is a failure.
- **Codex sub-agents proven sandboxed, condition (13)** (owner's decision, `docs/plans/2026-10-31-codex-sous-agents-spec.md`): the contract plays the model
  itself with a scripted fake provider on the local loopback, makes Codex launch one sub-agent that runs a probe, and reads only the
  requests Codex sends (never a file or a model's text). Green only if the sub-agent runs in the parent's sandbox and four escapes
  fail (reading the vault or another agent's folder, writing an MCP file, the witness socket, the network). Only then is the
  `collaboration` namespace accepted by (12); web tools and `clock` stay refused. Tests: `tests/contrat-sous-agents.py`.

### Fixed

- Public CI: the fresh-clone check now works on a real GitHub checkout. Root cause: the suites lock was found by walking the clone's origins up to a bare repository, but on GitHub the clone's origin is a non-bare checkout whose own origin is an https URL, so the walk stopped and the suites were NOT RUN; `tests/clone-frais.sh` now gives the clone its own explicit lock (proved by a network-free simulation, `tests/clone-frais-checkout.py`). The CI also plays `tests/pret.sh` on every pull request against its target branch (`BERGER_PRET_BASE`, explicit base), and `.gitignore` now excludes the runtime state of the broker and the web relay (`courtier/web/`, `courtier/mcp/`, `courtier/besoins/` and three state files).
- `mettre-a-jour` (`berger-dev`) failed on a real merge for lack of a git identity; the broker signs the merge.
- The core contract (`tests/contrat-noyau.py`) resolves names by Python's real scopes.
- An engine with invalid metadata is set aside and named; the other engines load.
- `berger demander` and `berger parler` with an invalid private input end with `ValueError` again.

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
