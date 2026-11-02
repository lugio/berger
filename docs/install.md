# Install Berger

This guide covers a new installation on Linux in `~/berger`.
Do not overwrite an existing installation or command link.

## Prerequisites

Install Git, Bash, Python **3.11+**, [Herdr](https://herdr.dev) **0.9+**,
bubblewrap, GnuPG and working systemd user services. Install and authenticate
Codex and/or Claude Code with your subscription, in a covered version (see [Engine versions](#engine-versions)). The first agent below
uses Codex; for Claude Code, change `moteur` and `panneaux` in its `agent.conf`
to `claude` before opening its workspace.

Verify that the sandbox starts:

```bash
bwrap --ro-bind / / --dev /dev --unshare-net true
```

On Ubuntu 24.04 and later, AppArmor may deny user namespaces. An administrator
must install an AppArmor profile allowing bubblewrap itself; the exact profile
is in the [French installation reference](manuel.md#installation-résumé).
A strict agent refuses to start without a working sandbox.

## Configure the checkout

Run this from a terminal as the user who will own the agents:

```bash
git clone https://github.com/lugio/berger.git ~/berger
cd ~/berger
cp config.exemple.toml config.toml
cp commun/modeles/USER.md commun/USER.md
mkdir -p ~/.local/bin ~/.config/systemd/user
ln -s "$PWD/bin/berger" ~/.local/bin/berger
ln -s "$PWD/courtier/berger-outil" ~/.local/bin/berger-outil
export PATH="$HOME/.local/bin:$PATH"
```

Keep `~/.local/bin` in your shell's PATH for later sessions. The supplied units
expect the checkout at `~/berger` and Herdr at `~/.local/bin/herdr`.
Check that path before enabling the services.

Manual configuration is required: edit `config.toml`, setting `proprietaire`
to your name and reviewing `coffre`, `masques`, `masques_si_presents` and
`masque_fichier` against your machine. Keep the credential store and sensitive
profiles protected. The copied example is sufficient for an initial agent with
no external tools; all tool declarations are commented out and no custom guard
is supplied. Do not insert credentials into this file or into agent files.
Complete `commun/USER.md` to describe whom the agents work for.

## Minimal sensitive configuration

These are the keys of `config.toml` that protect your machine. The copied example already holds sensible defaults; adapt them.

```toml
proprietaire = "Your Name"                    # who the agents work for

# Secret store: a JSON file, mode 600, read only by the broker. Keep its folder in `masques`.
coffre = "~/.config/berger/coffre.json"

# Folders (relative to your home) that every agent is forbidden to read.
masques = [".config/berger", ".ssh", ".gnupg"]

# Same, but only masked when the path exists. A missing path in `masques` stops Codex from starting;
# one in this list is simply skipped. List here everything that may not exist on your machine.
masques_si_presents = [".aws", ".kube", ".config/gh", ".local/share/keyrings"]

# One isolated file Codex must not read (Codex can mask a single file).
masque_fichier = ".claude/.credentials.json"

# Machine WITHOUT a system keyring (a server, a container): keep Codex's login in a file under
# ~/berger/.codex instead. That folder is then masked from every agent. Omit this line when you have a keyring.
codex_identifiants = "fichier"
```

- **No keyring**: set `codex_identifiants = "fichier"` as above, then run `CODEX_HOME="$HOME/berger/.codex" codex login`.
- **Masks that do not exist**: move the path from `masques` to `masques_si_presents`, then run `berger regenerer`.
- After any change, run `berger regenerer` and open a new conversation in the agents.

## Which Python Berger uses

Python 3.11 in a virtual environment is not enough by itself. `berger`, `berger-outil` and the broker start with
`#!/usr/bin/env python3`, so they use the first `python3` of the `PATH` they were started with (the supplied systemd units set
`PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin`). Once running, Berger **reorders** that `PATH`
(`PATH_MISE` in `bin/noyau/config.py`): `~/.local/share/mise/shims`, `~/.local/bin`, `/usr/local/bin`, `/usr/bin`, `/bin`, then
the rest. Its helper processes and the agents' tools find `python3` in that order. An activated virtual environment is not in
that list, so the interpreter used there may be an older system Python without `tomllib`.

Check what each context really uses; every line must print 3.11 or later:

```bash
python3 --version                                                                     # your shell
env PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin" python3 --version            # the systemd services
env PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin" \
  python3 -c 'import sys; print(sys.executable, sys.version.split()[0])'               # Berger's helpers and sub-processes
```

If the second or third line is older, install Python 3.11+ system-wide, or link it first in that order, for example
`ln -sf /path/to/python3.11 ~/.local/bin/python3`, then restart the services and the agents (`berger relancer <agent>`).

## Create and open the first agent

```bash
berger nouveau assistant "Assistant"
```

Expected result: `agent créé :` followed by the path of `agents/assistant`.
Edit its `SOUL.md` to describe its role, capabilities and limits. In
`agents/assistant/agent.conf`, set `heures = aucune` for a first agent that runs
only on request. Keep its default strict boundary. Then regenerate the settings
and authenticate Codex's dedicated profile interactively:

```bash
berger regenerer
CODEX_HOME="$HOME/berger/.codex" codex login
```

On a headless machine without a credential keyring, first read the
[Codex credential settings](manuel.md#sécurité-identique-pour-chaque-agent-et-chaque-moteur).
For Claude Code, authenticate its CLI instead. Review any engine hook approval
prompt; an unapproved hook does not establish a working guard.

```bash
cp systemd/* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now berger.timer berger-courtier.service berger-herdr.service
berger espace assistant
berger espace ensemble
berger etat
```

Expected result: an Assistant workspace with its engine conversation and a Berger
workspace showing the agent's state. Ask it to introduce its role: its answer
should reflect the `SOUL.md` you wrote. The first launch of a new engine version
runs a real-engine admission contract and may take up to 20 minutes; a rejected
engine can fall back to another admitted engine, otherwise startup is refused.
Do not interpret file generation or model-free tests as engine admission.

To keep user services running after logout, enable lingering if your system
policy allows it: `loginctl enable-linger "$USER"`. The optional test and web
units are described in the [French operations reference](manuel.md#exploitation).
Configuration, login, hook approval and admission are required steps; the guide
does not replace them with a dependency installer.

## Engine versions

Covered versions: Claude Code **2.1.312** and **2.1.314**, Codex **0.160.0** and **0.165.0**.
Each has a closed tool list in `tests/outils-connus/<engine>-<version>.json`.

- **List available** means that file exists. It is **not** an admission.
- **Admission** is the result of the engine contract on your machine, with your own login, for that exact
  version: `bash tests/contrat-moteur.sh <engine> <strict-agent>`. Without a passing contract, a strict agent does not start.
- Any other version is refused until its list is added through a reviewed pull request (manual, section
  « À la mise à jour d'un moteur »), then the contract tests are rerun.

Install a covered version with the engine's own installer pinned to it, for example
`npm install -g @anthropic-ai/claude-code@2.1.314` or `npm install -g @openai/codex@0.165.0`, and turn off its automatic
updates so the version does not move under a validated contract. Check with `claude --version` or `codex --version`.
