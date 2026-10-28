#!/usr/bin/env python3
"""Tests des méthodes et du crochet d'ÉQUIPE ([equipes.<projet>] skills / crochet_ecriture) — sans modèle, sans Herdr,
installation JETABLE. Vérifie : un développeur (projet + sujet) reçoit les méthodes de son équipe en plus des siennes ;
un agent du projet qui n'est pas développeur (chef de projet) ne les reçoit pas d'office ; le crochet du projet est posé
avant Edit|Write du seul développeur et tourne depuis le DÉPÔT (jamais du code de sa copie : modifier le script dans la
copie ne change pas ce qui s'exécute ; `{copie}` refusé), le fichier visé lui arrive ramené au dépôt ; le dépôt est
interdit en écriture au développeur ; rien sans réglage ; le Catalogue montre l'équipe.
Usage : python3 tests/skills-equipes.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def liens(i, a):
    d = i / "agents" / a / ".claude/skills"
    return sorted(p.name for p in d.iterdir() if p.is_symlink()) if d.is_dir() else []


def crochets(i, a):
    r = json.loads((i / "agents" / a / ".claude/settings.json").read_text())
    return [h["command"] for e in r.get("hooks", {}).get("PreToolUse", []) if e.get("matcher") == "Edit|Write" for h in e["hooks"]]


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}"); (m / "depot").mkdir()
    (i / "config.toml").write_text(
        f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n\n'
        f'[equipes.proj]\ndepot = "{m}/depot"\nchef_projet = "proj-chef"\nskills = ["code", "domaine"]\n'
        'crochet_ecriture = "python3 {depot}/outils/quels.py"\n\n'
        f'[equipes.autre]\ndepot = "{m}/depot"\ncrochet_ecriture = "python3 {{copie}}/outils/quels.py"\n')
    # le script de confiance (dépôt) et sa version modifiée par le développeur (copie)
    script = "import json,sys,os;d=json.load(sys.stdin);print(json.dumps({'marque':'%s','fichier':d['tool_input']['file_path'],'cwd':os.getcwd()}))"
    (m / "depot/outils").mkdir(parents=True); (m / "depot/outils/quels.py").write_text(script % "DEPOT")
    for n in ("code", "domaine", "chef", "perso"):
        (i / "skills" / n).mkdir(parents=True); (i / "skills" / n / "SKILL.md").write_text(f"---\nname: {n}\n---\nx\n")
    copie = m / "copies/proj sujet"
    (copie / "outils").mkdir(parents=True); (copie / "outils/quels.py").write_text(script % "COPIE-MODIFIEE")
    (copie / "src").mkdir(); (copie / "src/a.vue").write_text("x")
    agents = {"proj-sujet": f"projet = proj\nsujet = sujet\ncopie = {copie}\nskills = perso\n",
              "proj-chef": "skills = chef\n",
              "autre-x": f"projet = autre\nsujet = x\ncopie = {m}/copies/autre-x\n"}
    for a, extra in agents.items():
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\n{extra}")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0, "regenerer réussit avec des équipes" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr).strip()[-200:]}"))
    dire(liens(i, "proj-sujet") == ["code", "domaine", "perso"], f"développeur : méthodes de l'équipe + les siennes ({liens(i, 'proj-sujet')})")
    dire(liens(i, "proj-chef") == ["chef"], f"chef de projet (pas développeur) : seulement les siennes ({liens(i, 'proj-chef')})")
    dire(liens(i, "autre-x") == [], "développeur d'une équipe sans `skills` : rien")
    c = crochets(i, "proj-sujet")
    dire(len(c) >= 1 and all(str(copie) not in x for x in c) and any("crochet-equipe" in x for x in c),
         f"crochet posé, sans aucun chemin de la copie dans la commande ({c})")
    entree = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(copie / "src/a.vue")}})
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "crochet-equipe", "proj-sujet"], env=env, input=entree,
                       capture_output=True, text=True, timeout=60)
    try: o = json.loads(r.stdout)
    except ValueError: o = {}
    dire(o.get("marque") == "DEPOT", f"le script MODIFIÉ dans la copie n'est pas exécuté : c'est celui du dépôt ({r.stdout.strip()[:120]})")
    dire(o.get("fichier") == str((m / "depot/src/a.vue").resolve()) and o.get("cwd") == str((m / "depot").resolve()),
         "le fichier visé arrive ramené au dépôt, la commande tourne dans le dépôt")
    rg = json.loads((i / "agents/proj-sujet/.claude/settings.json").read_text())
    dep = str(m / "depot")
    dire(dep in rg["sandbox"]["filesystem"]["denyWrite"] and any(dep.replace(str(m), "~") in x or dep in x for x in rg["permissions"]["deny"] if x.startswith("Edit(")),
         "le dépôt de l'équipe est interdit en écriture au développeur (bac à sable ET outil Edit)")
    dire(not any("crochet-equipe" in x for x in crochets(i, "proj-chef")), "pas de crochet de projet chez le chef de projet")
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "crochet-equipe", "autre-x"], env=env, input=entree, capture_output=True, text=True, timeout=60)
    dire(not any("crochet-equipe" in x for x in crochets(i, "autre-x")) and "suppressOutput" in r.stdout,
         "un crochet qui vise {copie} est refusé (ni posé, ni exécuté)")
    code = (f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
            "print('\\n'.join(g['VUES']['catalogue'].vue_catalogue(160, 400)))")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    vue = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", r.stdout)
    dire("équipe proj (chaque développeur) : code, domaine" in vue, "Catalogue : les méthodes de l'équipe")
    dire("données à personne" not in vue, "une méthode donnée par une équipe n'est pas « à personne »")

sys.exit(1 if ko else 0)
