#!/usr/bin/env bash
# Contrat d'admission d'un moteur pour les agents strict (mcp-trous, 17/10/2026) — le même pour chaque moteur.
# Détail, contrôles et verdict : tests/contrat-moteur.py. Usage : bash tests/contrat-moteur.sh <claude|codex> [agent strict]
exec python3 "$(cd "$(dirname "$0")" && pwd)/contrat-moteur.py" "$@"
