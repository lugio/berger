# Install Berger

This guide covers a new installation on Linux in `~/berger`.
Do not overwrite an existing installation or command link.

## Prerequisites

Install Git, Bash, Python **3.11+**, [Herdr](https://herdr.dev) **0.9+**,
bubblewrap, GnuPG and working systemd user services. Install and authenticate
Codex **0.160+** and/or Claude Code with your subscription. The first agent below
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
