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


ANCIENS_ONGLETS = {n: (n, f"{i} {n}") for n, i in (   # titres EXACTS créés par Berger (avec et sans icône), onglets d'avant le regroupement 11 → 5 (31/10/2026)
    ("Documents", "🗂"), ("Checklists", "✅"), ("Livrables", "📐"), ("Synthèse", "🚦"), ("Sources", "🔎"), ("Courtier", "🔐"),
    ("Échanges", "💬"), ("Catalogue", "📚"), ("Tokens", "🪙"))}


def panneaux_sans_doublon_accueil(ws, noms, retires=(), gardes=1):
    """Les panneaux de l'espace `ws` après avoir fermé les anciens onglets `retires` (Documents, Livrables, Courtier… : seulement leur titre EXACT, jamais un
    onglet de l'utilisateur comme « Notes Documents ») et les panneaux en trop dans l'onglet Accueil (`gardes` panneaux : les premiers restent).
    `noms` : {tab_id: nom d'onglet sans icône}."""
    titres = {t for n in retires for t in ANCIENS_ONGLETS.get(n, ())}
    for t in herdr("tab", "list", "--workspace", ws).get("tabs", []):
        if t.get("label") in titres: herdr("tab", "close", t["tab_id"])
    panneaux = herdr("pane", "list", "--workspace", ws)["panes"]
    for x in [x for x in panneaux if noms.get(x["tab_id"]) == "Accueil"][gardes:]: herdr("pane", "close", x["pane_id"])
    return herdr("pane", "list", "--workspace", ws)["panes"]


def panneaux_en_plus(panes, combien):
    """Crée `combien` panneaux de plus dans l'onglet de `panes` (déjà là, dans l'ordre) : côte à côte, puis en grille (1 | 2 / 3 | 4) ; rend leurs ids."""
    sens = [(0, "right"), (1, "down"), (0, "down")]                             # (panneau qu'on coupe, direction) pour les 2e, 3e, 4e
    nouveaux = []
    for de, direction in sens[len(panes) - 1:len(panes) - 1 + combien]:
        nouveaux.append(herdr("pane", "split", "--pane", (panes + nouveaux)[de], "--direction", direction, "--cwd", str(BERGER), "--no-focus")["pane"]["pane_id"])
    return nouveaux


def panneaux_des_vues(vues):
    """{onglet: vues de ses panneaux} : l'onglet d'une vue de l'espace Berger est son GROUPE (sinon son TITRE) ; ses panneaux, par ORDRE, 4 au plus.
    HERDR = False : vue de la page web, sans panneau Herdr."""
    out = {}
    for t, m in sorted(vues.items(), key=lambda x: x[1].ORDRE):
        if m.ONGLET == "berger" and getattr(m, "HERDR", True): out.setdefault(getattr(m, "GROUPE", None) or m.TITRE, []).append(t)
    return {l: tuple(ts[:4]) for l, ts in out.items()}


def commandes_par_rang(noms, panes, commande):
    """[(panneau, commande)] des panneaux connus des onglets (`noms` : tab_id → nom) : le rang du panneau dans son onglet donne sa vue ; + {tab_id: nombre de panneaux}."""
    rang = {}; sortie = []
    for x in panes:
        c = commande(noms.get(x["tab_id"]), rang.setdefault(x["tab_id"], 0)); rang[x["tab_id"]] += 1
        if c: sortie.append((x, c))
    return sortie, rang


def lancer_panneaux(p0, label, voulus, commande):
    """Les panneaux d'un onglet neuf dont `p0` est le premier : coupe `voulus[label]` (jusqu'à 4) puis lance la commande de chacun."""
    for k, p in enumerate([p0] + panneaux_en_plus([p0], len(voulus.get(label, ())) - 1)): herdr("pane", "run", p, f"clear; {commande(label, k)}")


def panneaux_manquants(noms, panes, rang, voulus, commande):
    """Ajoute à chaque onglet gardé les panneaux qui lui manquent (`voulus` : nom → vues) et les lance ; rend les noms d'onglets complétés."""
    faits = []
    for tid, nom in noms.items():
        manque = len(voulus.get(nom, ())) - rang.get(tid, 0)
        ids = [x["pane_id"] for x in panes if x["tab_id"] == tid]
        if manque <= 0 or not ids: continue                              # rien à compléter, ou onglet sans panneau lisible : intact
        for k, p in enumerate(panneaux_en_plus(ids, manque), len(ids)): herdr("pane", "run", p, f"clear; {commande(nom, k)}"); faits.append(nom)
    return faits


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


__all__ = ('ANCIENS_ONGLETS', 'panneaux_en_plus', 'panneaux_manquants', 'lancer_panneaux', 'panneaux_des_vues', 'commandes_par_rang', 'herdr', 'herdr_api', 'herdr_ids', 'panneaux_sans_doublon_accueil', 'socket_herdr', 'statut_herdr',)
