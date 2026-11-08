# Changelog

All notable changes to Berger are documented in this file.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

<!-- Entries go in changelog.d/<topic>.md (see CONTRIBUTING.md): this section stays empty. -->

## [0.4.0] - 2026-11-08

### Added

- Web interface v2, part 1 (read only; spec `docs/plans/2026-11-03-interface-web-v2-spec.md`, the owner's mock-up is the reference): a short Home (what waits for the owner first, then alerts and working agents, the rest folded), Board, To read, Backstage and one page per agent; detail windows for a write, a document, a deliverable, an agent or an alert; a collapsible side menu remembered in this browser only; no horizontal overflow at 1440, 820 and 390 px.
- One shared source of icons and tab labels for Herdr and the web page, `bin/page/icones.json`: the page draws each icon as a line SVG, Herdr shows a plain one-character text symbol in front of the tab label. Agents now carry a `role` (chef, developpeur, agent) that picks their icon.
- Engine contract: a new engine version **without its own closed tool list is admitted by equivalence** when its only failing check is (12) « no closed list », (13) passes under Codex, and its tools match the most recent reviewed list in the repository (no new tool, no web tool, complete positive control). No list is written: the verdict (`tests/contrats/`, outside the repository) names the reference list and its sha256, and is « to rerun » if that list changes or disappears. A YELLOW alert asks for the exact list until it is added. A new tool, a web tool, a (13) escape or an incomplete control are still refused, with a red alert.
- Summary: YELLOW alert « installed version without a verdict: contract to run », computed locally. The manual and `docs/install.md` now say to pin engine versions (mise or npm) and to run the contract before launching a strict agent.
- The test queue is held by Berger (part A): before gates that run the suites, the broker takes a numbered ticket, waits for its turn in arrival order and for the suites lock (the same `flock` as `tests/suites.sh`), and keeps it until the last gate; the gate delay starts only then. A dead ticket is removed; waiting is capped at 2 h (« file des tests : attente dépassée », no verdict). `equipe liste` and `demandes` show « en file (2e, derrière <topic>) » or « en cours », Home turns YELLOW past 30 min, and the client does not time out while its request waits. A manual `tests/suites.sh` run takes a ticket in the same queue (from a sandbox that cannot write the queue, it takes no ticket but waits until the queue is empty, or is refused, named); the gates recorded by `demander-fusion` run in a frozen copy of the requested commit, out of the agent's reach; a zombie process counts as dead; the client ignores a stale queue marker and never waits beyond an absolute cap; tickets carry the agent's project, and `demandes` also lists a request still waiting for its turn. Agents no longer ask for a turn.
- Extensions, lot 1 (spec `docs/plans/2026-11-07-extensions-spec.md`, go n° 181): `berger extension verifier|ajouter|retirer|revenir|liste` installs a skill from a local folder or a full commit of a local git repository without touching the product or `config.toml`. A package carries an `extension.toml` manifest (name, genre, SemVer version, description, requested rights) and gets a sha256 fingerprint. Files go to `extensions/<genre>/<name>/<version>/` (frozen read-only copy, `actuelle` points to the active version), settings to a generated `extensions.toml`; both are git-ignored and refused by `berger verifier-depot`. Every refusal is named and writes nothing (agent caller, invalid manifest, taken name, older version, symbolic link, size, vault value or vault file name, forbidden pattern or private mark in any file, unknown agent, abbreviated or missing git commit); a vault value is never shown, only the file, the line and the key name. Each change is preceded by verified `.avant-` backups of `extensions.toml` and the `agent.conf` files it touches, followed by `regenerer`, and rolled back automatically if that fails; `retirer` restores the agent's line byte for byte and moves the files to `extensions/.retirees/`. The fingerprint is recomputed on the copy actually placed in `extensions/` (a mismatch refuses and installs nothing), and the source is read through directory file descriptors, so a parent folder swapped for a link is never followed. Vault values and private marks are also looked for in file names and in the decoded manifest texts (a TOML `\uXXXX` escape hides nothing); a refusal never echoes an unknown key, right or genre, and every refusal message goes through a last filter. `retirer` restores `agent.conf` byte for byte with or without a final newline, and removing the last extension removes `extensions.toml`, as before the first one. One line per change in `courtier/extensions.log`. The command is a new family (`bin/commandes/extensions.py`) served by the action service `gerer_extension`; vault values and `regenerer` are handed to `bin/noyau/extensions.py` by the core and never reach the read API. The `mcp`, `vue` and `outil` genres are refused until their own lot.
- Extensions, lot 2 (spec `docs/plans/2026-11-07-extensions-spec.md` § 6, go n° 181): a read-only "Extensions" tab in the web page (and `berger vue extensions`), one card per installed extension with genre, name, version, short fingerprint, agents, granted rights (network highlighted), install date, last use ("non mesuré" for a skill) and state (active, or set aside with the reason). Data comes from the read API (`extensions_donnees`) as an allow-list: unknown keys of `extensions.toml` are never shown, invalid values are reported as invalid, key-shaped values and private marks are masked, the home folder becomes `~`, and the vault is never read. `GET /api/vue/extensions` only (405 with `Allow: GET` otherwise); the server applies the same last filter as Réglages before sending. No field, no button.
- Extensions, lot 3 (spec `docs/plans/2026-11-07-extensions-spec.md`, go n° 181; decisions in `docs/plans/2026-11-07-extensions-decisions.md`): `berger extension` installs an MCP server. The manifest gives `[mcp] commande` (an absolute path to an already installed executable, outside agent folders and `extensions/`, never a downloading launcher), and `[droits] reseau`, `ecriture` (relative sub-folders) and `env` (variable names only, given empty values). Network needs both the manifest request and `--reseau`; `web` with network, an unknown `[mcp]` key, a team developer or a name already declared in `config.toml` are refused before anything is written. The server joins the declared MCP servers (`config.toml` wins) and `serveur_mcp`, unchanged, is replayed for each agent after writing: a refusal rolls everything back. The agent only gets the relay, as for a hand-declared server. The Extensions page shows an MCP's last use from the broker log.
- Every MCP server with network access that an agent has (extension or `config.toml`) is reported by a `⚠ réseau ouvert` line of `berger regenerer` and `berger etat`, and by the new `mcp_reseau` field of `berger etat --json`; no notification.
- `tests/interface-finition.py`: without a browser, refuses any colour outside the token blocks of `app.css` and any left border; with Playwright (optional, otherwise « NON JOUÉ »), `tests/_page_mesures.js` measures contrast on every visible text node (worst case quoted), text sizes, touch targets, horizontal overflow, mid-word title breaks, keyboard (Escape, Tab trap, focus return), the 2-click decision path, refusal without a reason, refresh with an open window, layout shift, the two-pane To read page and the folded Detail — at 1920, 1440, 820 and 390 px, in both themes.
- The web interface shows the official logo (`docs/assets/berger.png`, unchanged, spec `docs/plans/archive/2026-10-24-logo-spec.md`): served as is at `/logo.png` (read only, same strict content policy as the page), in place of the « B » in the side bar, in the header on phones (where the side bar brand is hidden) and as the page favicon. The static preview embeds it.
- Web interface v2, « Réglages » page (spec `docs/plans/2026-11-05-interface-reglages-spec.md`, go n° 169), read only: a new tab after Documents (web only, no Herdr tab) shows `config.toml` by section in file order, one card per entry of a family (`[outils.<name>]`) or of a repeated section (`[[gardes]]`), and for each setting its key, its value and one plain sentence (a catalogue next to the reader; « réglage non décrit » otherwise). The page opens with « Ces réglages se changent dans ~/berger/config.toml » and is read again each time the tab is opened. Masking is decided by the server, before serialisation (`bin/noyau/reglages.py`, standard library only): a closed list of keys, any key with a sensitive WHOLE word in its name (`ip_secours`, `cle_api`, `url_webhook` are masked; `description`, `principale`, `equipe`, `cycle` are not), any value with a key shape (`MOTIFS_CLES`), an address or a declared private mark, a whole list when one item is sensitive, nested tables key by key — a masked value is sent as « [masqué] » and never reaches the HTTP response, the log or the page. The vault is never read. Missing pieces are flagged with their consequence (no local transcriber: microphone greyed out; no `[interface] actions`: decisions read only; a tool without its file in `courtier/outils/`; a team without a readable repository; an invalid `config.toml`, told without its content). Route `GET /api/vue/reglages`, served in process by the server so that an invalid file is still reported; any other method answers 405 (`Allow: GET`). Same data from `berger vue reglages [--json]`.
- « Réglages » page, review n° 177: every value of an `env` table (an `[mcp.<name>]` server's environment) is masked, only variable names show; acronyms in camelCase names are words (`APIToken` → api, token); any PEM block is masked under any key name; every masked value is remembered and replaced by « [masqué] » wherever else it appears in the response (a host reused in a command, the vault path), and the same filter runs over the WHOLE response — card titles, keys, flags — not only values. A last pass refuses to answer (500, no detail) if a masked value or a key shape is still in the response; it never compares with the vault, which is never read.
- « Réglages » page, review of n° 178: a masked value or private mark shorter than 3 characters is now searched as a whole word (a two-letter host reused in « ssh <host> uptime »); masked values are matched regardless of case (a host name capitalised in a section title); a root `[env]` table shows only its variable names; only texts that come from the code (catalogue, known titles, header) are exempt from the filter, by origin, so a `config.toml` value equal to a catalogue text is filtered like any other.
- Web interface v2, part 2 (owner actions, off by default): with `[interface] actions = true`, the page can Validate, Refuse (reason required), Answer an agent's question and Mark as read — through `berger action`, which runs the same path as the command line (`berger valider` / `berger refuser`, `parler`, `lire`). Only from the local machine or the VPN; session, `Origin`, an anti-replay token derived from the session and a single-use preview token bound to the request's fingerprint (a request changed after the preview is refused); every attempt, refusals included, logged without the text of a reason or answer; 30 per hour.
- Web interface v2, part 3 (spec `docs/plans/2026-11-05-interface-web-v2-lot3-spec.md`, go n° 166), step 1 — the « Conversation » page of an agent, opened for the agents listed in `[conversation] agents` of `config.toml` (one line per agent, no code): the agent's real engine conversation, read only and never copied (Claude: the transcript noted in `.conversation-claude`; Codex: its current session file), as a message thread — the owner on the right, the agent on the left. Tool calls between two messages fold into one « N actions » line showing each tool and its short target, never a tool output; every block goes through `MOTIFS_CLES` and becomes « [masqué : secret possible] » when it matches; the agent's validation requests appear at their time as cards with the part 2 « Valider » gesture; « Copier » on each answer and code block; 50 turns and 200 KiB at most. New command `berger conversation liste --json` (owner only) and read-only route `GET /api/conversations`.
- Part 3, steps 2 to 4 — writing from the « Conversation » page, from the machine itself only (peer `127.0.0.1`/`::1`, local `Host`, `[interface] actions = true`): a text message (Enter sends, Shift+Enter breaks the line; 20 000 characters, no control character, no key-shaped text) takes the same path as `berger parler <agent> --stdin` (`agent.prompt` of Herdr, the Exchanges line marked « via l'interface web »), to a live agent only (« au repos : relance-le depuis Herdr »). A long paste (over 4 000 characters or 80 lines) becomes a `.txt` attachment, a pasted or dropped image an attachment; types are checked by extension AND first bytes (PNG, JPEG, WebP 10 MiB; WebM, Ogg, WAV 25 MiB and 10 minutes; UTF-8 text 2 MiB), stored only in the recipient agent's folder under `entrees/AAAA-MM-JJ/HHMMSS-<n>.<ext>` (0700 folders, 0600 files written with O_EXCL|O_NOFOLLOW, name made by Berger), 500 MiB quota per agent. The microphone works only with a declared local transcriber (`[interface] transcription = "<absolute binary>"`, run under `bwrap --unshare-net --clearenv`, vault and masked folders hidden, 120 s at most); otherwise it is greyed out with its reason and refused by the server. Guards: single-use send token, fingerprint of what is shown (agent, text, each attachment's type, size and sha256), « admis » journal line before acting and a result line after (no text, no content), 60 messages, 20 attachments and 100 MiB per hour, counted again after a restart, 40 MiB per request read as a stream. New routes `GET /api/message/jeton`, `POST /api/message`, `POST /api/transcrire`; commands `berger conversation envoyer|transcrire` (owner only).

### Changed

- Changelog in fragments (spec `docs/plans/2026-11-04-changelog-fragments-spec.md`): a branch writes its entry in `changelog.d/<topic>.md` instead of `CHANGELOG.md`, so two merge requests no longer share a file and the automatic update applies. `tests/changelog.py verifier` (in `tests/suites.sh` and the short documentation gate) refuses a malformed fragment; `tests/changelog.py regrouper <x.y.z> <date>` writes the version entry and deletes the fragments; `etiqueter` refuses a version while a fragment is left (« fragments non regroupés »). A `changelog.d/<name>.md` fragment counts as documentation for the short gate. Lines already under `[Unreleased]` stay allowed until the first grouping, which takes them over.
- The Decisions tab is removed from the web page and from Herdr: Home already shows what waits for the owner. `berger vue decisions` still works on the command line, and `berger refaire-espace berger` closes the old tab by its exact title and renames tabs that still carry the old emoji.
- No emoji, no coloured left border and no « null » anywhere in the web page; Git hashes are shortened to 7 characters and long sentences are cut at a word (the full text is in the detail window); a closed agent reads « closed » instead of « ? ».
- A merge request is no longer made stale by another merge (spec `docs/plans/2026-11-04-acceleration-fusions-spec.md`, part B): `demander-fusion` accepts a branch behind `main` when it has no conflict and no file in common with what `main` gained since the branch base (« main a avancé : mise à jour automatique à la fusion », recorded as `retard`). The validated merge still makes the automatic update, replays the gates chosen from the diff (short gate possible) and pushes nothing if a gate is red; the frozen SHA is unchanged. A conflict or a common file is still refused, now naming the files.
- The manual's fingerprint is now kept per section (part D, option (b)): `tests/attendus/manuel/<section>.sha256`, recomputed with `python3 -I tests/manuel-empreintes.py recalculer <section>`. A section changed without recomputing stays red and is named; an added or removed section is detected; `tests/vitrine.py` holds no fingerprint any more, so two branches on different sections no longer share it.
- Web interface v2, finishing pass (spec `docs/plans/2026-11-05-interface-finition-ui-spec.md`, presentation only, nothing changed on the server): every colour, spacing step (4 px scale), text size, radius, shadow and transition length of `bin/page/app.css` is now a token on `:root`, in a light and a dark theme (system preference, or the choice kept in this browser through a header button); no hard-coded colour and no coloured left border remain, and a test refuses them. Body text is 15 px, documents 16 px, nothing under 12 px; titles break between words only.
- Shared components (one definition each, ready for part 3): Card, Window (title and a one-line « author · date · read » header, body, footer of actions stuck to the bottom; 820 px on desktop, full screen on phones; Escape closes it, Tab stays inside, focus returns to what opened it), Button (primary, secondary, danger, link; 40 px high, 44 on phones), state Badge, key/value List (replaces the one-value boxes of agent pages and Backstage), Table, Markdown (real lists, readable inline code in both themes, tables that scroll inside their frame), Empty state, Loading (shown after 300 ms). Human labels only (« À décider », « Type », « Objet »).
- A decision takes 2 clicks: « Valider » on the card opens the decision window (number, exact preview, fingerprint), « Valider » in its footer confirms; « Refuser » opens the reason field and is confirmed only with a reason. Same `/api/action/apercu` and `/api/action` calls as part 2; afterwards a short confirmation (« n° 160 validée ») shows, the card disappears and the scroll position stays.
- To read (« À lire »): above 1280 px, two panes — the list (360 px) on the left, the open document on the right; below, a full-width list and the Window. Unread documents are bold with a dot, read ones keep a normal weight at AA contrast. A document opening with « **En bref** : … » then « **Pour toi** : … » shows them first in a soft box, and its `## Détail` section is folded until clicked.
- Board cards show the expected action first (badge), the rest in muted text, 3 lines at most before « Voir ». Refreshing never closes an open window, never clears a reason being typed, and keeps unfolded blocks with their content (layout shift measured ≤ 0.1); transitions last 150 ms at most, none under `prefers-reduced-motion`.
- Modular core, lot 4d, broker part (same owner go): `valider`, `refuser`, `courtier redemarrer`, `lancer`, `moteur` and `args` move to the `courtier`
  command family (`bin/commandes/courtier.py`). Acting goes through five services (`decider_validation`, `redemarrer_courtier`, `lancer_agent`,
  `ouvrir_moteur`, `parametres_moteur`) whose action stays in `bin/berger` with all its guards (atomic decision file, web access duration, held queue;
  closing mark, wait, checked restart and rollback; sandbox required, temporary folder, engine admission and fallback, strict arguments). The wall
  calculation, secrets, vault and repository stay in the core. `transport` (running a program) leaves the read API: only engines receive it, from their
  loader (`BASE_NOYAU`); no read API name reaches the vault or a secret (contract). Outputs, refusals, written files and rights are unchanged
  (`tests/equivalence-courtier.py`, 48 scenarios measured on `main`); `berger aide` lists 1 more family line (`refuser`). `bin/berger`: 6 lines fewer.
- Modular core, lot 4d, wall part (same owner go): `regenerer`, `nouveau` and `agent apercu|appliquer` move to the `agents` command family
  (`bin/commandes/agents.py`), acting through four services (`regenerer_agents`, `creer_agent`, `apercu_agent`, `appliquer_agent`). The wall calculation
  (masks, partitions, Claude and Codex settings, network, MCP, skills, temporary folders) and the check of a proposal (allowed and forbidden keys, strict
  wall only, tools, vault, fingerprint) stay in `bin/berger`. Outputs, refusals, written files and links are unchanged (`tests/equivalence-mur.py`,
  28 scenarios measured on `main`, through the command line and the broker); `berger aide` is unchanged. `bin/berger`: 6 lines fewer.
- Modular core, lot 4d, secrets part (same owner go): `secrets audit` and `coffre sauvegarder|purger` move to the `secrets` command family
  (`bin/commandes/secrets.py`), acting through two services (`auditer_secrets`, `sauvegarder_coffre`). The vault is read only in `bin/berger`
  (`valeurs_coffre`, `coffre_sauvegarder`); the family reads neither the vault nor the configuration, and prints only key names. Outputs, refusals and
  written files are unchanged (`tests/equivalence-secrets.py`, 18 scenarios measured on `main`, plus a guard: no vault value in any output or file written
  by berger); `berger aide` is unchanged. `bin/berger`: 8 lines fewer.
- Modular core, lot 4d, repository part (same owner go): `verifier-depot`, `installer`, `publier`, `sauvegarder`, `restaurer` and `verifier-sauvegarde`
  move to the `depot` command family (`bin/commandes/depot.py`), acting through six services (`verifier_neutralite`, `installer_forge`, `publier_en_ligne`,
  `sauvegarder_donnees`, `restaurer_archive`, `verifier_sauvegarde_distante`). Git, the automatic rollback, the checked restart, the keyring passphrase and the
  WebDAV credentials (read from the vault) stay in `bin/berger`; `bin/noyau/publication.py` stays outside every API. Outputs, refusals, written files and
  commits are unchanged (`tests/equivalence-depot.py`, 24 scenarios measured on `main` on a throwaway installation, forge and online repository, plus a
  guard: neither the passphrase nor the WebDAV password in any output); `berger aide` lists 3 more family lines (`publier`, `verifier-depot`, `verifier-sauvegarde`).
  `bin/berger`: 9 lines fewer (4 034 → 4 005 after merging `main`). Still in the core after lot 4d: `mcp-enveloppe`, `web`, `interface` and the space, wake-up and display verbs (see the
  modular decisions, « Écarts du 4d »).

### Fixed

- The web page no longer requests the same view twice within a few seconds, and reads schemas only when a generic view needs them, so the first load is lighter.
- Claude Code no longer updates itself under Berger. It had updated on its own despite `"autoUpdates": false`, because agents run with `--setting-sources project,local`, which does not read the user setting. Berger now sets `DISABLE_AUTOUPDATER=1` in the process environment of every Claude it launches (agents, strict or open, delegation, missions, team developers, `berger args` and the engine contract). One definition, Codex unchanged; the engine changes only by an owner's gesture, followed by the engine contract.
- Collected text sources, including GitHub CI status, now keep their original lines without extra JSON quotes in the Home summary and Sources. Structured responses retain their JSON formatting and secret filtering still applies.
- Test queue follow-up (part A, review 7/10): a manual run that cannot write the queue now takes the suites lock first and reads the queue while holding it, so no ticket can slip in between; each ticket is held by its owner's `flock`, so an orphan ticket (dead owner, even with a reused or invisible pid) is removed or ignored without blocking the queue; frozen gate copies are held by a usage lock and the broker removes orphaned ones (left by a hard stop) at startup, together with orphan tickets.
- The GitHub CI is green again: the broker runs everything with `/usr/bin/python3` (unchanged, no fallback to the `PATH`), which on the Ubuntu 22.04 runner was the system Python 3.10 (no `tomllib`, no `cryptography`). The workflow now makes the Python 3.11 under test that `/usr/bin/python3`, installs `ffmpeg` (so `ffprobe` is in `/usr/bin`, the only place the audio-attachment check looks) and checks both in a dedicated step.
- The GitHub CI, three remaining failures (run 42423542338): the sandbox keeps `courtier/python-systeme` visible when the installation lives under `/tmp` (the CI's fresh clone; the sandbox mounts a `tmpfs` there, so the broker's `python3` was lost and the `PATH` fell back to `/usr/local/bin/python3`), read-only and before the masks, with `/usr/bin/python3` and the "no fallback to the `PATH`" refusal unchanged; `berger secrets audit` lists the files it found sorted by path (the order came from the file system); `tests/suites.sh` no longer prints "No such file or directory" when no Herdr witness socket was reached; `tests/equivalence-depot.py` measures `git` in the C locale (its messages are translated).
- A skill in an agent's own `skills-agent/` folder is now checked like a catalogue skill (vault file name, `[skills] interdits` patterns) and refused, named, by `regenerer`; it used to be linked silently.
- The first install of a genre created `extensions/<genre>/`, which a rollback left behind; it is now removed with the rest.
- An extension MCP server can no longer run something an agent can rewrite (review no. 187): no interpreter as `commande[0]`, and every path in the command (each argument, an `--option=` value, the `#!` line of `commande[0]`, symlinks resolved) is refused in an agent folder, `extensions/` or any folder an agent writes to (work folder, memory, `ecrire_aussi`, library, agent temporaries); relative paths are refused. A downloading launcher is detected by its sub-command anywhere in the arguments (`npm --yes exec …`), for `config.toml` servers too.
- `berger extension revenir` gives back to an MCP version the network grant recorded for that very version (`reseau_versions`), never a new one, and refuses a version that asks for network without a recorded grant.
- Backstage › Latest calls: a call whose arguments span several lines (the broker writes them as they are) was read as several broken calls (« — — — — — non — », « — accepté | 1 résultat(s) | — — non — »). Lines that do not start with a date now continue the previous call; today's counts count it once. Owner QA of 05/11.
- Side bar: a developer is named by its topic (« interface-lot3 », with the team key icon) instead of a cut-off « Berger · interface-l… »; the full name stays on hover and for screen readers. Owner QA of 05/11.
- Wide screens (1920 px): every page is centred within a 1440 px maximum instead of stopping at 1240 px with an empty right side; on « À lire », the document frame now follows its reading column (75 characters at 16 px) and the two panes are centred together, instead of a frame running to the right edge with ~1 200 px of empty space. Measured in the browser at 1920 px (`tests/_page_mesures.js`: empty right side bounded, content centred, frame ≤ 40 px around the text). Owner QA of 05/11.
- Web owner actions (security review of part 2): the request's identity now goes all the way to the write — `berger valider|refuser <n> --empreinte` re-checks the request file's sha256 under the decisions lock shared with the command line, and Mark as read picks the document by its key (path and modification time), re-checked under the reading lock, never by its rank in a moving list; the answer quotes the question it answers. The hourly limit re-reads the whole last hour of the log after a restart, source and Host refusals on action paths are logged, an action is not done when its log line cannot be written, and the session cookie is `Secure` whenever TLS is on.
- Web page (review of part 1): every folded block keeps its open state when the view refreshes; a late answer never fills a detail window opened in the meantime; a long question or go request opens in full in a window; inline Markdown keeps the spaces around bold and code; a view still being read is reused instead of being requested again after 4 s. The mock-up's script works again (quoted keys).
- Web owner actions (second security review of part 2): a decision is never overwritten — `berger valider|refuser <n>` refuses (« déjà décidée ») under the decisions lock when `<n>.decision`, `<n>.execution` or `<n>.fait.json` already exists, so refusing then validating the same request before the broker runs it no longer replaces the first decision; when the final « fait » log line cannot be written the page gets an error (500) instead of 200; the « admis » line now counts the attempt, so it stays counted after a restart. Tested with two truly concurrent confirmations (same preview token, and validate/refuse on the same request) and refuse-then-validate.
- Part 3, review n° 172: the local transcriber's sandbox no longer sees any path socket — `/run` (user D-Bus bus, user systemd), `/var/run` and `/tmp` are covered by a tmpfs before the dictation folder is bound, as is Herdr's socket folder; the attachment quota is counted and written under one lock per agent (`entrees/.verrou`), so two simultaneous uploads can no longer both pass it; a dictation request takes a single-use token and carries the audio's sha256, so a replayed request is refused, and it counts in the rate limit; a WebM or Ogg file with a video track is refused; C1 control characters (U+0080–U+009F, including U+009B CSI) are refused in typed, pasted and transcribed text.
- Part 3, review of n° 175: the local transcriber's sandbox also hides the optional masks of `config.toml` (`masques_si_presents`: `.aws`, `.kube`, `.config/gh`, browsers…), as the broker does; its standard output and error are read 64 KiB at most each while it runs, and it is killed beyond that (« sortie trop longue »), so a runaway transcriber can no longer fill the server's memory.
- Modular core contract (Codex review of lot 4d, faults older than the lot): an ALIAS of `getattr` (`g = getattr`, an argument, a default value, a tuple,
  `operator.attrgetter`, `methodcaller`) was not recognised, so a view could reach the namespace behind a read API function (vault path, transport) and the
  action service registry. Every alias of `getattr`, `setattr`, `delattr` and `hasattr`, any import of a closed name under another name, and any special
  attribute name in a string are now refused in views, engines and command families. The service registry (`noyau.actions._SERVICES`) is frozen when
  `bin/berger` plugs it in, once per process (read-only, nothing outside `ACTIONS`), and `_geste` refuses a name outside `ACTIONS` before any lookup.
- Publication: `berger publier` and the automatic publication after an installation pushed without replaying `verifier-depot`. The repository check now
  runs right before the first push, on the exact commit being pushed (read from the forge's git objects, never the installed tree); when it fails, nothing is pushed, the faulty files are named, the refusal is logged and notified, and the exit code is 1.
- Project gates and every command the broker runs now use the system Python (`/usr/bin/python3`) instead of the mise `python3` shim (other tools keep their mise shims), so a mise shim that cannot write in the sandbox no longer kills the `verify` gate before it starts; a missing `/usr/bin/python3` is refused by name instead of falling back to another `python3`.

### Security

- `berger secrets audit` now reads the agents' Claude transcripts whatever the installation path: it looked for them under the path with only `/` replaced, while Claude replaces every non-alphanumeric character (`_` and `.` included), so an installation whose path contains them had its transcripts left out of the audit. One rule (`dossier_transcriptions` in `bin/noyau/lectures.py`) now serves the audit, the readers and Décisions; the folders examined before are still examined.
- A validated agent proposal can no longer give `ecrire_aussi` towards `extensions/`, `extensions.toml` or its `.avant-*` backups (directly, through a parent, a link or `..`): the agent would have written into the frozen copies without any install check.

## [0.3.1] - 2026-11-04

### Added

- Read-only GitHub `ci` verb for the latest Actions run on an allowed repository and branch, with one request and no token in process arguments. A commented source example displays CI failures and running workflows in the Home summary; missing or unreadable runs fail collection explicitly.

### Fixed

- Claude agents no longer stop on the « Bypass Permissions mode » warning after a Claude Code update. Berger launches every
  Claude agent with `--dangerously-skip-permissions`, but only declared `defaultMode = "bypassPermissions"` in the project
  `.claude/settings.json`, where Claude Code ignores the acceptance key (measured on 2.1.316 with a throwaway `HOME`).
  Berger now writes `"skipDangerousModePermissionPrompt": true` in `.claude/settings.local.json` (agent in its own folder)
  or in the file already passed by `--settings` (agent in an existing folder). Permissions, deny rules and sandbox are unchanged.
- `berger regenerer` no longer fails on an existing read-only `.claude/settings.local.json` (installed agents carry an empty
  0444 file, set by Berger against MCP declarations; the owner may have added the key by hand). An empty file counts as `{}`;
  when the key is already true nothing is written; otherwise the key is merged, other keys kept, through a temporary file in
  the same folder with the original mode, then `os.replace`. A file that is not a JSON object is left untouched with a named warning.
- The team equivalence test (`tests/equivalence-equipes.py`) no longer fails on GitHub Actions. Regenerated Claude settings
  name Claude's shared temporary folder `/tmp/claude-<uid>`; the expected results were recorded under uid 1000, the GitHub
  runner account is uid 1001, so the 8 scenarios that regenerate settings differed there. The account's own uid is now
  normalised to `<UID>` (any other uid still counts as a difference), the expected results carry no raw uid, and a failing
  scenario now prints each differing field around its first differing character instead of the first 400 characters.
- Decode message and team-hook stdin as strict UTF-8, independently of the interpreter's stdin error handler;
  invalid bytes are rejected before JSON fields or exchange logs are processed.
- Compare JSON recursion failures by their exception and decoding operation across Python 3.11 and 3.14,
  preserving exit codes and side-effect checks rather than freezing CPython's stack-limit wording.
- Keep the contention test's lock inode visible inside the private `/tmp` sandbox even when the CI clone lives
  under `/tmp`; the regression now always puts the lock there and binds only that file read-only.
- Engine contract (12): closed tool list for Claude Code 2.1.316 (`tests/outils-connus/claude-2.1.316.json`), an exact copy of the 2.1.314 list; the owner's contract on 2.1.316 named no new tool. Without it Claude was NOT ADMITTED after an automatic engine update.

### Security

- **Codex 0.166.0 is refused.** Its contract fails check (13): a sub-agent read another agent's folder. No list is added for it; keep Codex pinned to 0.165.0 (see `docs/install.md`, Engine versions).

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
