#!/usr/bin/env python3
"""Tests de la documentation « Installer le Master, pas à pas » (15/10/2026) — sans modèle, sans Herdr, sans installation.
La doc doit dire vrai :
1. la commande d'extraction citée par la section, jouée sur config.exemple.toml, donne du TOML qui se lit ;
2. ce TOML porte les clés citées ([equipes.berger] : chef_projet, coordinateur, fusion_par, installer_outil, verify, tests, pret ;
   [outils.berger-admin] : verbes de lecture et actions cités par la section) ;
3. chaque « berger <commande> » cité existe dans bin/berger (mode d'emploi) ET dans le registre des commandes (bin/commandes/) ;
4. les réglages d'agent.conf cités sont des clés connues de bin/berger.
Usage : python3 tests/installer-master.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import re, subprocess, sys, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


readme = (SRC / "docs/manuel.md").read_text()
debut = readme.index("### Installer le Master, pas à pas")
section = readme[debut:readme.index("\n## ", debut)]
berger = (SRC / "bin/berger").read_text()

# 1. extraction → TOML
cmd = next((l for l in section.splitlines() if l.startswith("sed -n ") and "config.exemple.toml" in l), None)
dire(cmd is not None, "la section cite la commande qui affiche les blocs de config.exemple.toml décommentés")
cfg = {}
if cmd:
    r = subprocess.run(["bash", "-c", cmd], cwd=SRC, capture_output=True, text=True)
    try: cfg = tomllib.loads(r.stdout); ok = True
    except tomllib.TOMLDecodeError as e: ok = False; print(e)
    dire(r.returncode == 0 and ok, "ces blocs, décommentés, se lisent en TOML")

# 2. clés citées
eq = cfg.get("equipes", {}).get("berger", {})
dire(bool(eq), "[equipes.berger] est présent")
for k in ("chef_projet", "coordinateur", "fusion_par", "installer_outil", "verify", "tests", "pret"):
    dire(k in eq and re.search(rf"`{k}[`= ]", section), f"[equipes.berger] porte « {k} » et la section le cite")
dire(eq.get("fusion_par") == "proprietaire", "fusion_par = proprietaire (un agent ne change pas ses propres murs)")
dire(eq.get("chef_projet") == "master" and eq.get("coordinateur") == "master", "chef_projet et coordinateur = master")
adm = cfg.get("outils", {}).get("berger-admin", {})
lect, acts = adm.get("lecture", {}), adm.get("actions", {})
dire(adm.get("type") == "commandes" and bool(lect) and bool(acts), "[outils.berger-admin] déclare des verbes de lecture ET des actions")
verbe_installer = eq.get("installer_outil", "").split(" ")[-1]
dire(verbe_installer in acts, f"installer_outil désigne une action déclarée de berger-admin ({verbe_installer})")
cites = set(re.findall(r"berger-outil berger-admin (\w[\w-]*)", section))
dire("etat" in cites, "la section cite le verbe de vérification etat")
for v in sorted(cites - {"aide"}):
    dire(v in lect or v in acts, f"verbe cité « berger-admin {v} » déclaré")
for v in ("etat", "services", "journal-courtier", "validations", "relancer"):
    dire(v in lect, f"lecture « {v} » déclarée")
for v in ("regenerer", "espace", "installer", "publier", "synchroniser", "exporter"):
    dire(v in acts, f"action « {v} » déclarée")

# 3. commandes « berger <x> » citées
usage = {m for l in re.findall(r"^  berger ([\w|-]+)", berger.split('"""', 2)[1], re.M) for m in l.split("|")}   # « valider|refuser »
aiguillage = _produit.verbes_declares(SRC)    # le registre des commandes (bin/commandes/, lot 3) a remplacé l'aiguillage `cmd == …` de main()
mots = set()
for bloc in re.findall(r"```\n(.*?)```", section, re.S):
    for l in bloc.splitlines():
        m = re.match(r"(?:\w+=\S+ )*berger (\w[\w-]*)", l)
        if m: mots.add(m.group(1))
mots |= set(re.findall(r"`berger (\w[\w-]*)", section)) | set(re.findall(r"(?<![\w-])berger (nouveau|regenerer|espace|valider|refuser|validations)\b", section))
dire({"nouveau", "regenerer", "espace", "validations", "valider", "refuser"} <= mots, f"commandes citées : {', '.join(sorted(mots))}")
for m in sorted(mots):
    dire(m in usage and m in aiguillage, f"« berger {m} » existe dans bin/berger (mode d'emploi et registre des commandes)")

# 4. agent.conf
bloc = next((b for b in re.findall(r"```\n(.*?)```", section, re.S) if "superviseur = oui" in b), "")
reglages = dict(re.findall(r"^(\w+) = (\S+)$", bloc, re.M))
dire(reglages == {"moteur": "claude", "panneaux": "claude", "superviseur": "oui", "skills": "berger", "outils": "berger-admin"},
     f"agent.conf de Master : {reglages}")
dire("mur = ouvert" not in bloc and "`mur = ouvert`" in section, "le mur reste strict (défaut) et la section interdit mur = ouvert")
for k in ("moteur", "panneaux", "superviseur", "skills", "outils"):
    dire(f'"{k}"' in berger or f"{k} =" in berger or f"`{k}" in berger, f"réglage « {k} » connu de bin/berger")

# SOUL-master : le modèle existe dans le produit et la section le cite
dire((SRC / "commun/modeles/SOUL-master.md").is_file() and "commun/modeles/SOUL-master.md" in section,
     "la section cite commun/modeles/SOUL-master.md, qui existe")
print(f"==== {ko} échec(s)"); sys.exit(1 if ko else 0)
