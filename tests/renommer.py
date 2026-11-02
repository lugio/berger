#!/usr/bin/env python3
"""Renommer un agent (nom AFFICHÉ, agent.conf) — sans modèle, avec un FAUX Herdr qui note ses appels : l'espace Herdr
suit le nouveau nom au passage suivant des titres, une seule fois ; l'identifiant et le dossier ne bougent pas.
Usage : python3 tests/renommer.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"; _produit.copier(SRC, i)
    (m / "coffre.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    appels, etat = t / "appels.txt", t / "libelle.txt"; etat.write_text("🧱 Ancien nom")
    (t / "herdr").write_text(f'#!/bin/sh\necho "$*" >> {appels}\ncase "$1 $2" in\n'
                             f'  "workspace list") printf \'{{"result": {{"workspaces": [{{"workspace_id": "w7", "label": "%s"}}]}}}}\' "$(cat {etat})" ;;\n'
                             f'  "workspace rename") shift 3; echo "$*" > {etat}; echo \'{{"result": {{}}}}\' ;;\n'
                             '  *) echo \'{"result": {}}\' ;;\nesac\n'); os.chmod(t / "herdr", 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": str(t / "herdr")}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=60)
    b("nouveau", "projet-chef", "Ancien nom")
    conf = i / "agents/projet-chef/agent.conf"
    conf.write_text(conf.read_text().replace("nom = Ancien nom", "nom = Lead Dev · P") + "icone = 🧱\n")
    (i / "agents/projet-chef/.herdr.json").write_text(json.dumps({"workspace": "w7", "agents": {"claude": "p1"}}))
    appels.write_text("")
    b("titres")
    dire(etat.read_text().strip() == "🧱 Lead Dev · P", f"l'espace prend le nom affiché ({etat.read_text().strip()!r})")
    b("titres")
    dire(appels.read_text().count("workspace rename") == 1, "renommé une seule fois (le passage suivant ne refait rien)")
    dire((i / "agents/projet-chef").is_dir() and not (i / "agents/lead-dev-p").exists(), "identifiant et dossier inchangés")
    dire("Lead Dev · P" in appels.read_text().split("report-metadata")[-1], "les titres des panes suivent aussi le nouveau nom")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
