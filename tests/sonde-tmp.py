#!/usr/bin/env python3
"""Sonde du dossier temporaire PAR agent (tmp-par-agent, 14/10/2026) : lancée DANS le bac à sable de l'agent, elle dit
si son TMPDIR est le sien, s'il y écrit, et s'il lit ou écrit le temporaire commun de Claude ou celui d'un autre agent.
N'affiche jamais de contenu. Les témoins à NE PAS lire (.lisible-essai-tmp) sont posés par tests/tout.sh hors bac à
sable ; ceux qu'elle tente d'écrire (.temoin-tmp-<moi>) sont cherchés par tout.sh sur le VRAI disque (sous Claude, une
écriture interdite peut « réussir » sans toucher le disque). Relais réseau du bac à sable : la sonde joint le mandataire
de son environnement (Claude) — le dossier temporaire ne doit pas l'avoir coupé.
Usage : python3 sonde-tmp.py <agent> <autre-agent|-> <claude|codex>"""
import hashlib, os, socket, sys
from pathlib import Path
from urllib.parse import urlsplit

moi, autre, moteur = sys.argv[1], (sys.argv[2] if sys.argv[2] != "-" else None), sys.argv[3]
R = Path(os.environ.get("BERGER_TMP_AGENTS") or "/tmp/bt")
tmp = lambda a: R / hashlib.sha256(a.encode()).hexdigest()[:12]
COMMUN = Path(f"/tmp/claude-{os.getuid()}")
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def lu(d):
    """LU si le témoin posé par tout.sh se lit, ou si le dossier se liste avec au moins une entrée."""
    try: open(d / ".lisible-essai-tmp", "rb").read(1); return True
    except OSError: pass
    try: return bool(os.listdir(d))
    except OSError: return False


def ecrire(d):
    try: (d / f".temoin-tmp-{moi}").write_text("x\n")
    except OSError: pass


t = Path(os.environ.get("TMPDIR") or "/tmp")
dire(t == tmp(moi) or t.is_relative_to(tmp(moi)), f"TMPDIR est son dossier ({'sous ' + str(tmp(moi)) if t.is_relative_to(tmp(moi)) else 'AILLEURS : ' + str(t)})")
try:
    f = t / f".essai-{moi}"; f.write_text("ok\n"); bon = f.read_text() == "ok\n"; f.unlink()
except OSError: bon = False
dire(bon, "écrit et relit dans son dossier temporaire")
dire(not lu(COMMUN), f"temporaire commun de Claude ({COMMUN}) : illisible"); ecrire(COMMUN)
if autre:
    dire(not lu(tmp(autre)), f"temporaire de {autre} : illisible"); ecrire(tmp(autre))
if moteur == "claude":
    p = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
    if not p: print("INFO  aucun mandataire réseau dans l'environnement : relais non testé")
    else:
        u = urlsplit(p)
        try: socket.create_connection((u.hostname, u.port or 80), timeout=5).close(); ok = True
        except OSError: ok = False
        dire(ok, "relais réseau du bac à sable joignable (mandataire de l'environnement)")
print(f"---- {ko} échec(s)")
