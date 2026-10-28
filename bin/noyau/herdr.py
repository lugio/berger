"""La porte vers Herdr : commande, API par socket, statuts.

Code déplacé de bin/berger (modulaire, lot 1) : aucun comportement changé."""
import datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, tomllib, unicodedata
import importlib.util
import shutil as _sh, textwrap
from pathlib import Path
from noyau.config import *
from noyau.transport import *
from noyau.affichage import *
from noyau.agents import *


def herdr_ids(a):
    try: return json.loads(lire(dossier(a) / ".herdr.json", "{}"))
    except ValueError: return {}


def herdr(*args):
    r = subprocess.run([HERDR, *args], capture_output=True, text=True, timeout=20)
    try: return json.loads(r.stdout).get("result", {})
    except ValueError: return {}


def socket_herdr():
    """Socket de l'API Herdr (doc socket-api : HERDR_SOCKET_PATH, sinon <XDG_CONFIG_HOME ou ~/.config>/herdr/herdr.sock).
    Un Herdr de remplacement (BERGER_HERDR, tests) ne parle qu'à BERGER_HERDR_SOCKET : jamais au vrai serveur."""
    if HERDR != "herdr": return os.environ.get("BERGER_HERDR_SOCKET")
    return os.environ.get("HERDR_SOCKET_PATH") or str(Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config") / "herdr/herdr.sock")


def herdr_api(methode, params, strict=False):
    """Méthode brute de l'API Herdr, pour ce que sa ligne de commande n'expose pas (tab.move en 0.9.3) : une requête
    JSON par ligne, une réponse par ligne. {} si le serveur ne répond pas."""
    import socket
    chemin = socket_herdr()
    if not chemin:
        if strict: raise ValueError("API Herdr indisponible")
        return {}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as so:
            so.settimeout(10); so.connect(chemin)
            so.sendall((json.dumps({"id": "berger", "method": methode, "params": params}) + "\n").encode())
            tampon = b""
            while not tampon.endswith(b"\n"):
                bout = so.recv(65536)
                if not bout: break
                tampon += bout
        reponse = json.loads(tampon or b"{}")
        if strict and (not isinstance(reponse, dict) or reponse.get("id") != "berger"
                       or "error" in reponse or not isinstance(reponse.get("result"), dict)):
            raise ValueError("réponse Herdr invalide")
        return reponse.get("result", {})
    except (OSError, ValueError):
        if strict: raise ValueError("remise Herdr impossible (API indisponible ou message refusé)") from None
        return {}


def statut_herdr(pane, ttl=15):
    """Statut détecté par Herdr, gardé 15 s : chaque appel coûte une requête au serveur Herdr
    (17 panneaux × toutes les 5 s = 18 % de processeur pour Herdr, mesuré le 04/10)."""
    if not pane: return "?"
    t, v = _STATUTS.get(pane, (0, None))
    if time.time() - t > ttl:
        v = (herdr("pane", "get", pane).get("pane") or {}).get("agent_status", "?"); _STATUTS[pane] = (time.time(), v)
    return v


__all__ = ('herdr', 'herdr_api', 'herdr_ids', 'socket_herdr', 'statut_herdr',)
