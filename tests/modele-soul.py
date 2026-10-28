#!/usr/bin/env python3
"""Modèle de SOUL à la création : `berger nouveau master` utilise commun/modeles/SOUL-master.md ({nom}, {proprietaire}
remplacés) ; tout autre agent garde le SOUL générique ; un nom piégé ne lit jamais hors de commun/modeles/.
Usage : python3 tests/modele-soul.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import os, subprocess, sys, tempfile
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
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=60)
    modele = (i / "commun/modeles/SOUL-master.md").read_text()
    b("nouveau", "master", "Gardien")
    soul = (i / "agents/master/SOUL.md").read_text()
    dire(soul == modele.replace("{nom}", "Gardien").replace("{proprietaire}", "Proprio"), "master : SOUL.md = le modèle, {nom} remplacé")
    dire("Tu es **Gardien**, le gardien de Berger" in soul and "{" not in soul and "}" not in soul, "master : plus aucune accolade de gabarit")
    dire("À compléter par" not in soul, "master : ce n'est pas le SOUL générique")
    b("nouveau", "autre", "Autre")
    dire((i / "agents/autre/SOUL.md").read_text() == "# Qui tu es\n\nTu es **Autre**. À compléter par Proprio.\n\n"
         "## Ce que tu sais faire\n\n- …\n\n## Tes limites\n\n- …\n", "autre agent : SOUL générique inchangé")
    # nom piégé : un SOUL-<…>.md hors de modeles/ ne doit jamais servir
    (i / "commun/SOUL-piege.md").write_text("PIEGE {nom}")
    r = b("nouveau", "../SOUL-piege", "X")
    dire(not any("PIEGE" in p.read_text() for p in i.rglob("SOUL.md")), "nom piégé : aucun modèle lu hors de commun/modeles/")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
