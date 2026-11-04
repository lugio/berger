#!/usr/bin/env python3
"""Tests de la mémoire d'ÉQUIPE ([equipes.<projet>] memoire) — sans modèle, sans Herdr, installation JETABLE.
Vérifie : un développeur (projet + sujet) a dans ses règles l'index de la mémoire de son équipe et la consigne « lecture
seule » ; la mémoire est refusée en écriture (permissions Claude ET bac à sable, profil Codex en lecture) ; le chef de
projet (pas développeur) et une équipe sans `memoire` ne reçoivent rien ; un chemin relatif se résout dans l'installation.
Usage : python3 tests/memoire-equipe.py (0 = tout passe)"""
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
    (m / "coffre-essai.json").write_text("{}"); (m / "depot").mkdir()
    (i / "config.toml").write_text(
        f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n\n'
        f'[equipes.proj]\ndepot = "{m}/depot"\nchef_projet = "proj-chef"\ncoordinateur = "proj-chef"\nmemoire = "equipes/proj/memoire"\n'
        f'verify = "bash tests/syntaxe.sh"\ntests_outil = "proj-verif tests"\npret = "bash tests/pret.sh"\n\n'
        f'[equipes.autre]\ndepot = "{m}/depot"\n')
    me = i / "equipes/proj/memoire"; me.mkdir(parents=True)
    (me / "MEMORY.md").write_text("# Mémoire longue\n\n- [regle_tests](regle_tests.md) — jamais tests | tail && git push\n")
    (me / "regle_tests.md").write_text("---\nname: regle_tests\n---\nrc=$? avant push\n")
    agents = {"proj-sujet": f"projet = proj\nsujet = sujet\ncopie = {m}/copies/proj-sujet\n", "proj-chef": "",
              "autre-x": f"projet = autre\nsujet = x\ncopie = {m}/copies/autre-x\n"}
    for a, extra in agents.items():
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\n{extra}")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0, "regenerer réussit avec une mémoire d'équipe" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr).strip()[-200:]}"))

    def regles(a): return (i / "agents" / a / "AGENTS.md").read_text() if (i / "agents" / a / "AGENTS.md").exists() else ""
    def reglages(a): return json.loads((i / "agents" / a / ".claude/settings.json").read_text())
    rd = regles("proj-sujet")
    dire(f"{me}/MEMORY.md" in rd and "LECTURE SEULE" in rd, "développeur : ses règles l'envoient lire la mémoire d'équipe, en lecture seule")
    s = reglages("proj-sujet")
    formes = (str(me), "~/" + str(me.relative_to(m)))
    dire(any(x.startswith("Edit(") and any(f in x for f in formes) for x in s["permissions"]["deny"]), "développeur : édition de la mémoire refusée (permissions Claude)")
    dire(str(me) in s["sandbox"]["filesystem"]["denyWrite"], "développeur : écriture de la mémoire refusée (bac à sable)")
    dire(s.get("autoMemoryDirectory") is None or str(me) not in str(s.get("autoMemoryDirectory")),
         "développeur : la mémoire automatique ne pointe pas sur la mémoire d'équipe")
    cx = (i / ".codex/config.toml").read_text() if (i / ".codex/config.toml").exists() else ""
    dire(not cx or f'"{me}" = "read"' in cx, "profil Codex : mémoire d'équipe en lecture seule (ou Codex absent)")
    rc = regles("proj-chef")
    dire("## Mémoire de l'équipe proj — à lire" in rc and f'grep -ril "<mot>" {me}' in rc and "LECTURE SEULE" not in rc,
         "chef de projet : ses règles l'envoient lire la mémoire de son équipe (spec regle-go, point c)")
    dire(str(me) not in json.dumps(reglages("proj-chef")), "chef de projet : ses murs ne changent pas (ni refus ni écriture en plus)")
    dire("Mémoire de l'équipe" not in regles("autre-x"), "chef d'une autre équipe ou développeur d'une équipe sans `memoire` : rien")
    # consigne commune (point c) : chercher mémoire d'équipe, skills, puis code avant de dire « n'existe pas » — tous les rôles
    for a in ("proj-sujet", "proj-chef", "autre-x"):
        r = regles(a)
        dire("## Avant de dire qu'une chose n'existe pas" in r and r.index("mémoire de ton équipe") < r.index("**skills**") < r.index("**code**"),
             f"{a} : consigne « avant de dire qu'une chose n'existe pas » (mémoire, skills, puis code)")
    dire("LECTURE SEULE" not in regles("autre-x"), "développeur d'une équipe sans `memoire` : rien")
    # le circuit de développement : écrit une fois (commun/modeles/equipe-processus.md), une fois par projet et par agent
    circuit = "## Le circuit de développement de proj"
    dire(rd.count(circuit) == 1 and "**verify**, **tests**, **pret** ; gate : non déclarée" in rd,
         "développeur : le circuit de son projet, une fois, avec SES portes (gate « non mesuré »)")
    dire(regles("proj-chef").count(circuit) == 1, "chef de projet ET coordinateur : le circuit une seule fois")
    # règle de go validée le 12/10 (REGLES, pour tous) : les 5 cas tels quels, pas une autre règle
    cas = ("un **secret visible**", "**écriture dans un logiciel métier**", "la **production**", "le **pare-feu**", "**plus d'appels vers un service extérieur**")
    dire("## Règle de go" in rd and all(c in rd for c in cas) and "le **coordinateur décide seul**" in rd and "Qui donne le go" not in rd,
         "règle de go : les 5 cas validés, le coordinateur décide seul hors de ces cas")
    # même chose sous Codex (point c : rien de propre à un moteur) — chef et développeur passés en codex
    for a in ("proj-chef", "proj-sujet"):
        f = i / "agents" / a / "agent.conf"; f.write_text(f.read_text().replace("moteur = claude", "moteur = codex").replace("panneaux = claude", "panneaux = codex"))
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    rc, rd = regles("proj-chef"), regles("proj-sujet")
    dire(r.returncode == 0 and "## Mémoire de l'équipe proj — à lire" in rc and "## Avant de dire qu'une chose n'existe pas" in rc
         and "LECTURE SEULE" in rd and "## Avant de dire qu'une chose n'existe pas" in rd,
         "codex : chef et développeur ont la mémoire d'équipe et la consigne « avant de dire qu'une chose n'existe pas »")
    cx = (i / ".codex/config.toml").read_text() if (i / ".codex/config.toml").exists() else ""
    chef_cx = cx.split("[permissions.proj-chef]")[1].split("[permissions.")[0] if "[permissions.proj-chef]" in cx else ""
    dire(not cx or f'"{me}" = "write"' not in chef_cx, "codex : le profil du chef ne gagne aucune écriture sur la mémoire d'équipe")
    # ce qu'est un go (spec regle-go, point a, vécu le 15/10 : une réponse prise pour un go) — REGLES et les trois rôles
    go = "une réponse à des questions n'est pas un go"
    dire(all(go in regles(x).lower() for x in ("proj-sujet", "proj-chef", "autre-x")) and "**spec écrite et nommée**" in rd,
         "règle de go : un go = mot explicite sur une spec écrite et nommée ; une réponse n'est pas un go (claude et codex)")
    dire("tant que la demande de go par validation n'existe pas" not in rd.lower() and "berger-outil equipe go --fichier .transport/requete.json` (paramètres JSON, dans l’ordre : `<projet> <sujet> <cas> <spec>`)" in rd,
         "point b : la phrase de transition est retirée, la règle donne la demande de go par validation")
    rc = regles("proj-chef").lower()
    dire(rc.count(go) >= 4, "chef ET coordinateur : la phrase dans REGLES, le circuit, le modèle chef et le modèle coordinateur")
    ra = regles("autre-x")
    dire("pret : non déclarée (« non mesuré », demande et fusion refusées)" in ra, "équipe sans pret : la règle le dit (demande et fusion refusées)")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
