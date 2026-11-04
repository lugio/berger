#!/usr/bin/env python3
"""Sonde du mur système d'un agent Berger : tente d'OUVRIR chaque emplacement interdit, dit LU ou REFUSE.
N'affiche jamais de contenu. Les emplacements viennent de config.toml (masques) + le dossier d'un autre agent.
Usage (dans le bac à sable de l'agent) : python3 sonde-mur.py <agent> <autre-agent>"""
import json, os, sys, tomllib
from pathlib import Path
H = Path.home(); B = Path(__file__).resolve().parent.parent; moi = sys.argv[1]; autre = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None   # seul agent de la machine : pas de voisin à tester
C = tomllib.loads((B / "config.toml").read_text())
rel = lambda p: str(Path(p).relative_to(H))
oui = lambda cle: any(l.split("=", 1)[0].strip() == cle and l.split("=", 1)[1].split("#")[0].strip().lower() in ("oui", "yes", "true", "1")
                      for l in (B / "agents" / moi / "agent.conf").read_text().splitlines() if "=" in l and not l.lstrip().startswith("#"))
# `superviseur = oui` (09/10/2026) : LIT les autres agents, leur bibliothèque, les projets et les archives (bin/berger masques()) ;
# ces emplacements passent d'interdits à permis. Le coffre, les sources des outils et toutes les écritures restent interdits.
sup = oui("superviseur")
INTERDITS = [m for m in C.get("masques", []) + C.get("masques_si_presents", []) if (H / m).exists()] \
            + [C.get("masque_fichier", ".claude/.credentials.json")] + ([rel(B / "agents" / autre)] if autre and not sup else []) \
            + ([rel(B / ".codex")] if C.get("codex_identifiants") == "fichier" else [])
PERMIS = [rel(B / "agents" / moi / "SOUL.md"), rel(B / "commun/REGLES.md")] \
         + ([rel(B / "agents" / autre / "SOUL.md")] if autre and sup and (B / "agents" / autre / "SOUL.md").exists() else [])
# Bibliothèque (08/10/2026) : le dossier d'un autre agent y est interdit ; le commun se lit (tests/tout.sh y pose un fichier
# lisible avant la sonde) ; chemins absolus si la racine n'est pas sous ~ (H / "/abs" = "/abs").
BIB = Path(os.path.expanduser((C.get("bibliotheque") or {}).get("racine") or str(B / "bibliotheque")))
ab = lambda p: str(p.relative_to(H)) if p.is_relative_to(H) else str(p)
inscrit = oui("bibliotheque")
VOISINS_BIB = [BIB / "agents" / x for x in (os.listdir(BIB / "agents") if (BIB / "agents").is_dir() else []) if x != moi]
if sup: PERMIS += [ab(v / "travail/.lisible-essai") for v in VOISINS_BIB if (v / "travail/.lisible-essai").exists()]
else: INTERDITS += [ab(v) for v in VOISINS_BIB]
if (BIB / "commun/.lisible-essai").exists(): PERMIS.append(ab(BIB / "commun/.lisible-essai"))
# Projets d'équipe (lot 4) : le registre (hors bibliothèque, lisible) dit de quels projets je suis membre — les miens se lisent
# et s'écrivent, ceux des autres et les archives sont interdits (tests/tout.sh pose un .lisible-essai dans chaque projet).
MES_PROJETS, AUTRES_PROJETS = [], []
for reg in (B / "equipes").glob("*/projets.json"):
    try: projets = json.loads(reg.read_text())
    except (OSError, ValueError): continue
    for p, v in projets.items():
        (MES_PROJETS if moi in v.get("membres", []) else AUTRES_PROJETS).append(BIB / "equipes" / reg.parent.name / "projets" / p)
if sup: PERMIS += [ab(p / ".lisible-essai") for p in AUTRES_PROJETS if (p / ".lisible-essai").exists()]
else: INTERDITS += [ab(p) for p in AUTRES_PROJETS if p.is_dir()] + [ab(a) for a in (BIB / "equipes").glob("*/archives") if a.is_dir()]
PERMIS += [ab(p / ".lisible-essai") for p in MES_PROJETS if (p / ".lisible-essai").exists()]


def essai(r):
    p = H / r
    try:
        if not p.is_dir():
            open(p, "rb").read(1); return "LU"
        vus = 0
        for racine, _, fichiers in os.walk(p):
            for f in fichiers:
                vus += 1
                try: open(os.path.join(racine, f), "rb").read(1); return "LU"
                except OSError: pass
                if vus >= 40: break
        return "REFUSE"
    except FileNotFoundError: return "ABSENT"
    except OSError: return "REFUSE"


ko = 0
for r in INTERDITS:
    x = essai(r); ok = x != "LU"; ko += not ok; print("ok   " if ok else "ÉCHEC", "interdit", r, "→", x)
for r in PERMIS:
    x = essai(r); ok = x == "LU"; ko += not ok; print("ok   " if ok else "ÉCHEC", "permis  ", r, "→", x)


def ecrire(p):
    try: open(p, "w").write("x"); os.remove(p); return True
    except OSError: return False


# Chez l'autre agent : un TÉMOIN laissé exprès. Sous Claude, le dossier interdit est remplacé par un dossier vide
# jetable : l'écriture « réussit » sans toucher le disque. tests/tout.sh vérifie, HORS bac à sable, qu'il n'existe pas.
if autre:
    try: open(B / "agents" / autre / f".temoin-{moi}", "w").write("x")
    except OSError: pass
    print("info  témoin écrit chez", autre, "→ à vérifier hors bac à sable")
# Bibliothèque : témoins vérifiés HORS bac à sable par tests/tout.sh — chez un voisin et dans le commun ils ne doivent PAS
# exister sur le disque ; dans SON dossier de travail (inscrit) il DOIT exister (une écriture « réussie » dans un dossier
# remplacé par le bac à sable ne prouverait rien).
for v in VOISINS_BIB:
    try: (v / "travail").is_dir() and open(v / "travail" / f".temoin-{moi}", "w").write("x")
    except OSError: pass
if (BIB / "commun").is_dir():
    try: open(BIB / "commun" / f".temoin-{moi}", "w").write("x")
    except OSError: pass
if inscrit:
    try: open(BIB / "agents" / moi / "travail" / f".temoin-ecrit-{moi}", "w").write("x")
    except OSError: pass
for p in AUTRES_PROJETS:                      # projet d'autrui : le témoin ne doit PAS exister sur le disque
    try: p.is_dir() and open(p / f".temoin-{moi}", "w").write("x")
    except OSError: pass
for p in MES_PROJETS:                         # mon projet : le témoin DOIT exister
    try: open(p / f".temoin-ecrit-{moi}", "w").write("x")
    except OSError: pass
if VOISINS_BIB or (BIB / "commun").is_dir() or inscrit or MES_PROJETS or AUTRES_PROJETS:
    print("info  témoins de la bibliothèque écrits → à vérifier hors bac à sable")
for p, attendu in ((B / "agents" / moi / ".essai", True), (B / "commun/.essai", False), (H / ".essai-hors", False)):
    x = ecrire(p); ok = x == attendu; ko += not ok
    print("ok   " if ok else "ÉCHEC", "écriture", rel(p), "→", "permise" if x else "refusée")
# Son agent.conf (ses droits) : lisible, PAS inscriptible. Ouverture en ajout sans rien écrire : rien n'est modifié même
# si le mur laissait passer (une écriture « x » aurait écrasé ses droits).
def inscriptible(p):
    try: os.close(os.open(p, os.O_WRONLY | os.O_APPEND)); return True
    except OSError: return False
c = B / "agents" / moi / "agent.conf"
x = inscriptible(c); ko += x
print("ÉCHEC" if x else "ok   ", "écriture", rel(c), "→", "permise" if x else "refusée")
# `proteges` (09/10/2026) : lus, jamais réécrits. Fichier : ouverture en ajout, comme agent.conf. Dossier : un TÉMOIN, vérifié
# HORS bac à sable par tests/tout.sh (sous Claude une écriture refusée peut sembler réussir dans un dossier remplacé).
PROTEGES = [x.strip() for l in c.read_text().splitlines() if "=" in l and not l.lstrip().startswith("#")
            and l.split("=", 1)[0].strip() == "proteges" for x in l.split("=", 1)[1].split("#")[0].split(",") if x.strip()]
for x in PROTEGES:
    p = B / "agents" / moi / x
    if p.is_file():
        e = inscriptible(p); ko += e; print("ÉCHEC" if e else "ok   ", "protégé ", rel(p), "→", "inscriptible" if e else "refusé")
    elif p.is_dir():
        try: open(p / f".temoin-protege-{moi}", "w").write("x"); print("info  témoin écrit dans", rel(p), "→ à vérifier hors bac à sable")
        except OSError: print("ok    protégé ", rel(p), "→ écriture refusée")
print("----", ko, "échec(s)")
