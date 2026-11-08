#!/usr/bin/env python3
"""Sonde Herdr d'un agent Berger : depuis SON bac à sable, peut-il parler au serveur Herdr (et donc lire le pane d'un autre
espace, ou y taper du texte) ? Tente la connexion au socket de l'API et `herdr pane list`. N'affiche jamais de contenu.
Usage (dans le bac à sable de l'agent) : python3 sonde-herdr.py
RECETTE RÉELLE : connectée au VRAI Herdr EXPRÈS (n'importe pas tests/_herdr_isole.py). Les suites de tests/suites.sh, elles, sont isolées."""
import os, socket, subprocess
from pathlib import Path

H = Path.home()
chemin = os.environ.get("HERDR_SOCKET_PATH") or str(Path(os.environ.get("XDG_CONFIG_HOME") or H / ".config") / "herdr/herdr.sock")


def socket_api():
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(3); s.connect(chemin); s.close(); return "OUVERT"
    except FileNotFoundError: return "ABSENT"
    except OSError: return "REFUSE"


def liste_panes():
    for b in ("herdr", str(H / ".local/bin/herdr")):
        try: r = subprocess.run([b, "pane", "list"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired): continue
        return "LU" if r.returncode == 0 and '"pane_id"' in r.stdout else "REFUSE"
    return "ABSENT"


ko = 0
for quoi, x in (("socket de l'API Herdr", socket_api()), ("herdr pane list", liste_panes())):
    ok = x not in ("OUVERT", "LU"); ko += not ok
    print("ok   " if ok else "ÉCHEC", "herdr", quoi, "→", x)
print("----", ko, "échec(s)")
