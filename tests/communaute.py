#!/usr/bin/env python3
"""Contrôles légers des fichiers communautaires et du lanceur de CI."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
from pathlib import Path
import subprocess
import sys

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, message):
    global ko
    ko += not ok
    print(('ok    ' if ok else 'ÉCHEC ') + message)


fichiers = ('LICENSE', 'SECURITY.md', 'CODE_OF_CONDUCT.md', 'CHANGELOG.md', 'CONTRIBUTING.md', '.github/pull_request_template.md',
            '.github/ISSUE_TEMPLATE/bug_report.yml', '.github/ISSUE_TEMPLATE/feature_request.yml',
            '.github/workflows/ci.yml', 'tests/clone-frais.sh')
for fichier in fichiers:
    dire((SRC / fichier).is_file(), f'fichier communautaire présent : {fichier}')
if any(not (SRC / f).is_file() for f in fichiers):
    sys.exit(1)
licence = (SRC / 'LICENSE').read_text()
dire(licence.startswith('MIT License\n') and 'Copyright (c) 2026 ' in licence
     and licence.splitlines()[2] == 'Copyright (c) 2026 The Berger contributors'
     and 'Permission is hereby granted, free of charge' in licence
     and 'THE SOFTWARE IS PROVIDED "AS IS"' in licence,
     'licence MIT complète, année et titulaire présents')
for nom in ('SECURITY.md', 'CODE_OF_CONDUCT.md'):
    texte = (SRC / nom).read_text()
    dire('Private vulnerability reporting' in texte and 'Security' in texte and '@' not in texte,
         f'{nom} : signalement privé GitHub, aucune adresse email')
journal = (SRC / 'CHANGELOG.md').read_text()
dire('## [0.1.0] - 2026-10-21' in journal and '1.1.0' in journal,
     'journal initial 0.1.0 au format Keep a Changelog 1.1.0')
ci = (SRC / '.github/workflows/ci.yml').read_text()
dire('permissions:\n  contents: read' in ci and 'write' not in ci,
     'CI limitée à la lecture du dépôt')
dire('secrets.' not in ci and 'pull_request_target' not in ci,
     'CI sans secret ni contexte privilégié de pull request')
dire('bash tests/clone-frais.sh' in ci, 'CI joue la preuve réelle du clone frais')
clone = (SRC / 'tests/clone-frais.sh').read_text()
dire('env -i' in clone and 'GIT_CONFIG_NOSYSTEM=1' in clone and 'GIT_CONFIG_GLOBAL=/dev/null' in clone,
     'clone frais : environnement et configuration Git personnels écartés')
dire('tests/syntaxe.sh' in clone and 'tests/suites.sh' in clone and 'set -euo pipefail' in clone,
     'clone frais : verify puis tests, échec propagé')
dire('BERGER_HERDR=' in clone and 'BERGER_NOTIFY_SEND=' in clone,
     'clone frais : sentinelles Herdr et notifications explicites')
contribution = (SRC / 'CONTRIBUTING.md').read_text()
dire(all(texte in contribution for texte in ('spec', 'tests/syntaxe.sh', 'tests/suites.sh', 'tests/pret.sh', 'root cause')),
     'contribution : spec, tests, trois portes et cause racine des correctifs')
for fichier in fichiers:
    if fichier != 'tests/clone-frais.sh':
        r = subprocess.run(['git', '-C', str(SRC), 'check-ignore', fichier], capture_output=True)
        dire(r.returncode == 1, f'liste blanche accepte {fichier}')
print(f'==== {ko} échec(s)')
sys.exit(1 if ko else 0)
