#!/usr/bin/env python3
"""Contrôle (6) du contrat d'admission, hors moteur (codex-trous, 18/10/2026, docs/plans/2026-10-18-codex-trous-spec.md) :
le socket témoin écoute et compte les connexions ; la sonde dit si elle le VOIT et si connect() aboutit ; verdict vert
seulement si l'agent le voit ET est refusé ; socket retiré à la fin, et par la reprise d'un contrat coupé (MARQUE dans son
nom), jamais un socket sans marque. Le refus réel dans un bac à sable est prouvé par tests/contrat-moteur.sh.
Sans socket AF_UNIX possible ici (dans un bac à sable qui les refuse) : NON JOUÉ, jamais ok.
Usage : python3 tests/contrat-socket.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util, os, socket, subprocess, sys, tempfile
from pathlib import Path

T = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("contrat", T / "contrat-moteur.py"); C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def sonde(d, f):
    r = subprocess.run([sys.executable, str(T / "sonde-mcp.py"), "mur", str(d), "--unix", str(f)], capture_output=True, text=True, timeout=60)
    return C.ligne_mur([r.stdout]) or {}


try: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM).close()
except OSError:
    print("NON JOUÉ socket AF_UNIX impossible dans cet environnement (bac à sable) : contrôle (6) hors moteur non prouvé"); sys.exit(0)

with tempfile.TemporaryDirectory(prefix="cs-", dir="/tmp" if os.access("/tmp", os.W_OK) else None) as t:
    d = Path(t); journal = d / "pose.json"
    f = C.chemin_socket([None, d / "absent", d])
    dire(f is not None and f.parent == d and C.MARQUE in f.name, "chemin du socket témoin : premier dossier existant, nom marqué")
    dire(C.chemin_socket([d / ("x" * 120)]) is None, "chemin trop long pour AF_UNIX : aucun (le contrôle sera rouge, jamais deviné)")
    p = C.Pose(journal); s = p.poser_socket(f)
    dire(journal.is_file() and str(f) in journal.read_text(), "socket témoin journalisé avant d'écouter (reprise possible)")
    dire(f.is_socket() and C.connecte(f) and s.attendre(1), "témoin hors bac à sable : connexion acceptée et comptée")
    m = sonde(d, f); s.attendre(2)
    dire(m.get("vu") == "oui" and m.get("connect") == "connecte" and m.get("af_unix") == "permis", f"sonde sans bac à sable : vu, connectée ({m})")
    bon, texte = C.verdict_af_unix(m, s)
    dire(not bon and "CONNECTÉ" in texte, f"agent connecté → (6) rouge : {texte}")
    bon, texte = C.verdict_af_unix({"vu": "oui", "connect": "refuse", "af_unix": "permis"}, type("S", (), {"n": 1})())
    dire(bon and "création du socket : permis" in texte, f"vu et refusé, rien d'autre accepté → (6) vert, création en information : {texte}")
    bon, texte = C.verdict_af_unix({"vu": "oui", "connect": "refuse", "af_unix": "permis"}, type("S", (), {"n": 2})())
    dire(not bon, "sonde « refusée » mais le serveur a accepté une connexion de plus → rouge")
    m2 = sonde(d, d / "absent.sock"); bon, texte = C.verdict_af_unix(m2, type("S", (), {"n": 1})())
    dire(m2.get("vu") == "non" and not bon and "invisible" in texte, f"socket témoin invisible pour l'agent → non prouvé, rouge : {texte}")
    s.fermer(); p.retirer()
    dire(not f.exists() and not journal.exists(), "fin du contrat : socket témoin retiré, journal effacé")
    # contrat coupé net (SIGKILL) : la reprise retire le socket marqué, jamais un socket sans marque
    autre = d / "autre.sock"; a = socket.socket(socket.AF_UNIX); a.bind(str(autre))
    p = C.Pose(journal); s = p.poser_socket(f); s.fermer()
    p2 = C.Pose(journal); p2.faits = p.faits + [{"f": str(autre), "cote": None, "nouveaux": []}]; p2._ecrire()
    n = C.Pose(journal).reprendre()
    dire(n == 2 and not f.exists() and autre.is_socket(), "reprise d'un contrat coupé : socket marqué retiré, socket sans marque laissé")
    a.close()

sys.exit(1 if ko else 0)
