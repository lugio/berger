#!/usr/bin/env python3
"""Sonde des sites permis (12/10/2026), lancée DANS le bac à sable d'un agent : chaque site permis de son projet doit RÉPONDRE,
un site hors liste doit être REFUSÉ ; projet sans liste, ou moteur Codex : tout refusé. N'affiche jamais de contenu, seulement
le code HTTP ou la raison du refus. Les attentes sont recalculées ICI (config.toml, agent.conf, equipes/<projet>/domaines),
sans le code de Berger : la sonde ne croit pas ce qu'elle vérifie.
Usage (dans le bac à sable de l'agent) : python3 sonde-domaines.py <agent> <claude|codex>"""
import re, sys, tomllib, urllib.error, urllib.request
from pathlib import Path
B = Path(__file__).resolve().parent.parent; moi, moteur = sys.argv[1], sys.argv[2]
C = tomllib.loads((B / "config.toml").read_text())
conf = {l.split("=", 1)[0].strip(): l.split("=", 1)[1].split("#")[0].strip()
        for l in (B / "agents" / moi / "agent.conf").read_text().splitlines() if "=" in l and not l.lstrip().startswith("#")}
EXACT = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
projets = [p for p, e in C.get("equipes", {}).items() if e.get("coordinateur") == moi or (conf.get("projet") == p and conf.get("sujet"))]
def lire_liste(p):
    try: return (B / "equipes" / p / "domaines").read_text().splitlines()
    except OSError: return []
liste = sorted({x.split("#")[0].strip() for p in projets for x in lire_liste(p) if EXACT.fullmatch(x.split("#")[0].strip())})
temoin = next(x for x in ("example.com", "example.org", "example.net") if x not in liste)   # jamais listé : doit être refusé


def essai(nom):
    try:
        with urllib.request.urlopen(f"https://{nom}/", timeout=8) as r: return f"RÉPOND ({r.status})"
    except urllib.error.HTTPError as e: return f"RÉPOND ({e.code})"           # une réponse HTTP, même une erreur : le site est joint
    except Exception as e: return f"REFUSÉ ({type(e).__name__}: {str(e)[:60]})"


ko = 0
permis = liste[:3] if moteur == "claude" else []
print(f"info  {moi} ({moteur}) : sites permis {', '.join(liste) or 'aucun'}" + (" — Codex : aucun réseau attendu" if liste and moteur != "claude" else ""))
for nom in liste[:3]:
    x = essai(nom); attendu = nom in permis; ok = x.startswith("RÉPOND") == attendu; ko += not ok
    print("ok   " if ok else "ÉCHEC", "permis  " if attendu else "interdit", nom, "→", x)
x = essai(temoin); ok = x.startswith("REFUSÉ"); ko += not ok
print("ok   " if ok else "ÉCHEC", "interdit", temoin, "(hors liste) →", x)
print("----", ko, "échec(s)")
