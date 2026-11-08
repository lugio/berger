#!/usr/bin/env python3
"""La CI joue pret sur le diff de la PR (base explicite) ; les états générés à l'exécution sont ignorés, aucun fichier suivi ne l'est."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
from pathlib import Path
import subprocess

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok
    print(('ok    ' if ok else 'ÉCHEC ') + texte)


ci = (SRC / '.github/workflows/ci.yml').read_text()
dire("if: github.event_name == 'pull_request'" in ci and 'BERGER_PRET_BASE="origin/${BASE_REF}" bash tests/pret.sh' in ci,
     'CI : pret joué sur les pull requests, base = origin/<branche cible>')
dire('BASE_REF: ${{ github.base_ref }}' in ci and ci.count('github.base_ref') == 1,
     'CI : la branche cible passe par une variable d\'environnement, jamais interpolée dans le script')
dire('fetch-depth: 0' in ci and 'fetch --no-tags origin "+refs/heads/${BASE_REF}:refs/remotes/origin/${BASE_REF}"' in ci,
     'CI : historique complet et branche cible récupérée avant pret')
dire(ci.index('tests/pret.sh') < ci.index('bash tests/clone-frais.sh'), 'CI : pret (rapide) avant la preuve du clone frais')
dire('permissions:\n  contents: read' in ci and 'secrets.' not in ci and 'pull_request_target' not in ci, 'CI : lecture seule, sans secret ni contexte privilégié')
# Le courtier lance tout avec /usr/bin/python3 (courtier/python-systeme/python3, aucun repli sur le PATH, choix gardé sur une vraie installation) :
# sur le runner Ubuntu 22.04 c'est le 3.10 du système (sans tomllib ni cryptography) ; la CI en fait donc le Python 3.11 testé (run 42369602601).
# ffprobe est lu par bin/commandes/conversation.py avec PATH=/usr/bin:/bin : le paquet ffmpeg doit le poser dans /usr/bin.
apt_ligne = next((l for l in ci.splitlines() if 'apt-get install' in l), '')
dire(' ffmpeg' in apt_ligne, 'CI : ffmpeg installé par apt (ffprobe dans /usr/bin, seul dossier que voit la vérification des pièces audio)')
lien = 'ln -sf "$(python3 -c \'import os, sys; print(os.path.realpath(sys.executable))\')" /usr/bin/python3'
dire('sudo ' + lien in ci or lien in ci, 'CI : /usr/bin/python3 (le Python du courtier) devient le Python 3.11 testé')
dire(0 <= ci.find('apt-get install') < ci.find('/usr/bin/python3') < ci.find('bash tests/clone-frais.sh'),
     'CI : /usr/bin/python3 remplacé APRÈS les installations apt, AVANT la preuve du clone frais')
dire('/usr/bin/python3 -c' in ci and 'import tomllib, cryptography' in ci and '/usr/bin/ffprobe' in ci,
     'CI : une étape contrôle /usr/bin/python3 (version, tomllib, cryptography) et /usr/bin/ffprobe')
# États locaux et fichiers générés à l'exécution par le courtier et le relais web : tous ignorés.
generes = ('courtier/web/agent.json', 'courtier/mcp/agent.sock', 'courtier/mcp/agent-web/proxy.sock', 'courtier/besoins/1.json',
           'courtier/besoin-debit.json', 'courtier/fermeture', 'courtier/file-tenue.json', 'courtier/appels.log', 'courtier/echanges.jsonl',
           'courtier/notifications.log', 'courtier/installations.log', 'courtier/ecrire-debit.json', 'courtier/boucles.json',
           'courtier/validations/1.json', 'courtier/validations/web-remises/a', 'courtier/sollicitations/1.json', 'courtier/panneaux/a.json',
           'courtier/consignes/x.json', 'courtier/dernier-audit.txt', 'courtier/derniere-sauvegarde.txt', 'courtier/essai-ecritures.txt',
           'commun/USER.md', 'tests/.tout.verrou')
for fichier in generes:
    r = subprocess.run(['git', '-C', str(SRC), 'check-ignore', '-q', fichier])
    dire(r.returncode == 0, f'état local généré ignoré : {fichier}')
suivis = subprocess.run(['git', '-C', str(SRC), 'ls-files', '-ci', '--exclude-standard'], capture_output=True, text=True).stdout.split()
dire(not suivis, f'aucun fichier suivi n\'est ignoré {suivis[:5] or ""}')
print(f'==== {ko} échec(s)')
raise SystemExit(1 if ko else 0)
