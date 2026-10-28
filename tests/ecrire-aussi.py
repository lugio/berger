#!/usr/bin/env python3
"""Tests de `ecrire_aussi` (agent.conf) — sans modèle, sans Herdr, installation JETABLE.
Un FICHIER de `ecrire_aussi` (ex. la checklist d'un projet) reste inscriptible par le bac à sable (allowWrite) mais n'est
PAS mis dans permissions.additionalDirectories, qui n'accepte que des dossiers (07/10/2026 : Artisan démarrait avec
« checklists/projet-moncab.md is not a directory ») ; un DOSSIER y reste. Usage : python3 tests/ecrire-aussi.py (0 = tout passe)"""
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
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    fichier = i / "checklists/projet-essai.md"; fichier.parent.mkdir(parents=True); fichier.write_text("- [ ] étape\n")
    dossier = m / "partage"; dossier.mkdir()
    d = i / "agents/coord"; (d / "memory").mkdir(parents=True)
    (d / "agent.conf").write_text(f"nom = Coord\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\n"
                                  f"ecrire_aussi = {fichier}, {dossier}\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0, "regenerer réussit avec un fichier et un dossier dans ecrire_aussi"
         + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr).strip()[-200:]}"))
    s = json.loads((d / ".claude/settings.json").read_text())
    aw, ad = s["sandbox"]["filesystem"].get("allowWrite", []), s["permissions"].get("additionalDirectories", [])
    dire(str(fichier) in aw and str(dossier) in aw, "bac à sable : le fichier ET le dossier restent inscriptibles (allowWrite)")
    dire(str(fichier) not in ad, "additionalDirectories : le FICHIER n'y est pas (sinon « is not a directory » au lancement)")
    dire(str(dossier) in ad, "additionalDirectories : le DOSSIER y est toujours")
    dire(all(not Path(x).is_file() for x in ad), "additionalDirectories : aucun fichier")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
