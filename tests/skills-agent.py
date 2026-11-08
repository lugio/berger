#!/usr/bin/env python3
"""Correctif (extensions, lot 1) : une méthode PROPRE d'un agent (skills-agent/) passe le même contrôle que le catalogue — sans modèle, installation JETABLE.
Cause racine : lier_skills appliquait motif_refus_skill aux seules méthodes du catalogue ; la boucle de skills-agent/ liait tout, sans bruit.
Usage : python3 tests/skills-agent.py (0 = tout passe)"""
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
    # Correctif (extensions lot 1) : une méthode propre (skills-agent/) passait sans aucun contrôle, alors que la même au catalogue était refusée.
    # Cause racine : lier_skills appliquait motif_refus_skill aux méthodes du catalogue seulement ; la boucle de skills-agent/ liait tout.
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n\n[skills]\ninterdits = ["MOT_INTERDIT_[0-9]+"]\n')
    d = i / "agents/delta"; (d / "memory").mkdir(parents=True)
    (d / "agent.conf").write_text("nom = Delta\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\n")
    for n, txt in (("propre", "rien à signaler"), ("fuite-coffre", "les identifiants sont dans coffre-essai.json"), ("fuite-motif", "voir MOT_INTERDIT_42")):
        (d / "skills-agent" / n).mkdir(parents=True); (d / "skills-agent" / n / "SKILL.md").write_text(f"---\nname: {n}\n---\n{txt}\n")
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env={**{k: v for k, v in os.environ.items() if k != "BERGER_AGENT"}, "HOME": str(m), "BERGER_DIR": str(i)}, capture_output=True, text=True, timeout=300)
    liens = sorted(p.name for p in (d / ".claude/skills").iterdir() if p.is_symlink()) if (d / ".claude/skills").is_dir() else []
    dire(r.returncode == 0 and liens == ["propre"], f"skills-agent/ : une méthode propre qui cite le coffre ou un motif interdit n'est pas donnée ({liens})")
    dire("méthode propre « fuite-coffre » (skills-agent/) refusée" in r.stdout and "fuite-motif" in r.stdout, "skills-agent/ : le refus est nommé, avec son motif")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
