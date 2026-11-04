#!/usr/bin/env python3
"""Tests du panneau Catalogue — sans modèle, sans Herdr : une installation JETABLE (outils, agents, journal du courtier,
méthodes, garde-fous) dont on lit la vue. Vérifie : qui a droit à quoi, outil attribué à personne, verbes de lecture et
d'écriture, dernier usage (accepté seulement), méthodes, garde-fous, et AUCUNE valeur du coffre affichée.
Usage : python3 tests/catalogue.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0
VALEUR_COFFRE = "valeur-secrete-du-catalogue-7f3"


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text(json.dumps({"erp": {"cle": VALEUR_COFFRE}}))
    (i / "config.toml").write_text(
        f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n\n'
        '[[gardes]]\nmoment = "avant"\noutils = "Bash|Read"\ncommande = "python3 ~/gardes/secrets-avant.py"\n\n'
        '[outils.veille]\ntype = "commandes"\ndossier = "/tmp"\n[outils.veille.lecture]\nbulletins = "echo b"\n\n'
        '[outils.serveur]\ntype = "commandes"\ndossier = "/tmp"\n[outils.serveur.lecture]\netat = "echo e"\n'
        '[outils.serveur.actions]\nredemarrer = "echo r {arg}"\n\n'
        '[outils.oublie]\ntype = "commandes"\ndossier = "/tmp"\n[outils.oublie.lecture]\nrien = "true"\n')
    for a, nom, outils in (("vigie", "Vigie", "veille, serveur"), ("autre", "Autre", "veille, deleguer:vigie")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {nom}\nicone = ●\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils = {outils}\n")
    (i / "agents/vigie/skills-agent/pivot").mkdir(parents=True); (i / "agents/vigie/skills-agent/pivot/SKILL.md").write_text("# pivot\n")
    (m / ".claude/skills/partagee").mkdir(parents=True); (m / ".claude/skills/partagee/SKILL.md").write_text("# p\n")
    maintenant = datetime.datetime.now(); vieux = maintenant - datetime.timedelta(days=40)
    (i / "courtier/appels.log").write_text(
        f"{maintenant:%Y-%m-%d %H:%M:%S}\tvigie\tveille\tbulletins\t\taccepté\tok\n"
        f"{vieux:%Y-%m-%d %H:%M:%S}\tvigie\tserveur\tetat\t\taccepté\tok\n"
        f"{maintenant:%Y-%m-%d %H:%M:%S}\tautre\tveille\tbulletins\t\tREFUSÉ\tpas le droit\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    code = f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');print('\\n'.join(g['VUES']['catalogue'].vue_catalogue(140, 200)))"
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    vue = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", r.stdout)
    lignes = vue.splitlines()
    dire(r.returncode == 0 and "CATALOGUE" in vue, "la vue se construit" + ("" if r.returncode == 0 else f" — {r.stderr.strip()[-200:]}"))

    def bloc(o):        # lignes de l'outil o jusqu'au suivant
        k = next((n for n, l in enumerate(lignes) if l.strip().startswith(o + " ")), None)
        if k is None: return ""
        fin = next((n for n in range(k + 1, len(lignes)) if lignes[n].startswith("  ") and not lignes[n].startswith("    ")), len(lignes))
        return "\n".join(lignes[k:fin])

    dire("Vigie" in bloc("veille") and "Autre" in bloc("veille"), "outil partagé : les deux agents y figurent")
    dire("Vigie" in bloc("serveur") and "Autre" not in bloc("serveur"), "outil réservé : seul son agent y figure")
    dire("personne" in bloc("oublie"), "outil attribué à aucun agent : « personne »")
    dire("lecture : etat" in bloc("serveur") and "redemarrer" in bloc("serveur") and "validée par toi" in bloc("serveur"),
         "verbes de lecture et d'écriture (écriture marquée « validée par toi »)")
    b = bloc("veille")
    dire(re.search(r"Vigie\s+dernier usage aujourd'hui", b) and re.search(r"Autre\s+dernier usage jamais", b),
         "dernier usage : appel accepté = aujourd'hui ; appel REFUSÉ ne compte pas (« jamais »)")
    dire("il y a 40 j" in bloc("serveur"), "dernier usage ancien : « il y a 40 j »")
    dire("deleguer:vigie" in vue, "droit spécial (délégation) listé avec son agent")
    dire("partagee" in vue and "pivot" in vue, "méthodes : partagées et propres à un agent")
    dire("Bash|Read" in vue and "secrets-avant.py" in vue, "garde-fous listés")
    dire(VALEUR_COFFRE not in r.stdout and VALEUR_COFFRE not in r.stderr and "erp.cle" not in vue, "AUCUNE valeur ni chemin du coffre affiché")

sys.exit(1 if ko else 0)
