#!/usr/bin/env python3
"""Tests de l'onglet « Tableau » (colonnes, même présentation que le Tableau du 113) — sans modèle, avec un FAUX Herdr : une
installation JETABLE, trois agents. Vérifie : chaque carte dans la bonne colonne (bloqué, validation, document non lu → ATTEND
<PROPRIÉTAIRE> ; validation déléguée → ATTEND UN AGENT ; au repos ; checklist terminée < 24 h → LIVRÉ), largeur jamais dépassée, colonnes
empilées dans un pane étroit, onglet déclaré avec son icône. Usage : python3 tests/tableau.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, shutil, subprocess, sys, tempfile, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


net = lambda t: re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", t)
larg = lambda s: sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)
with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    (t / "herdr").write_text('#!/bin/sh\ncase "$1 $2 $3" in "pane get p-vigie") echo \'{"result": {"pane": {"agent_status": "working"}}}\' ;; '
                             '*) echo \'{"result": {}}\' ;; esac\n'); os.chmod(t / "herdr", 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": str(t / "herdr")}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=60)
    for a, n in (("vigie", "Vigie"), ("scribe", "Scribe"), ("garde", "Garde")): b("nouveau", a, n)
    (i / "agents/vigie/.herdr.json").write_text(json.dumps({"agents": {"claude": "p-vigie"}}))
    (i / "agents/vigie/CHECKLIST.md").write_text("# Contrôle DMARC\n- [x] lire\n- [ ] comparer ← en cours\n")
    (i / "agents/scribe/CHECKLIST.md").write_text("# Inventaire des sauvegardes\n- [x] lister\n- [ ] croiser\n⚠ Bloqué : accès PBS refusé\n")
    (i / "agents/garde/CHECKLIST.md").write_text("# Ménage des journaux\n- [x] a\n- [x] b\nTerminé\n")
    (i / "a-lire").mkdir(exist_ok=True); (i / "a-lire/2026-10-07_plan.md").write_text("# Plan de la VM\n")
    v = i / "courtier/validations"; v.mkdir(parents=True, exist_ok=True)
    (v / "4.json").write_text(json.dumps({"n": 4, "agent": "vigie", "apercu": "passer DMARC en quarantine sur mise-à-jour-des-politiques.exemple.fr"}))
    (v / "6.json").write_text('{"n": 6, "agent": "vig')                                         # à moitié écrit
    (v / "7.json").write_text(json.dumps({"n": 7, "agent": "garde", "verbe": "fusionner", "args": ["pages"], "apercu": "fusionner pages"}))
    (i / "config.toml").write_text((i / "config.toml").read_text() + '[equipes.app]\nchef_projet = "vigie"\n')
    dm = i / "equipes/app/demandes"; dm.mkdir(parents=True)
    (dm / "pages.json").write_text(json.dumps({"sujet": "pages", "etat": "à relire", "agent": "garde"}))
    (dm / "menu.json").write_text(json.dumps({"sujet": "menu", "etat": "renvoyée", "agent": "garde"}))
    (v / "5.json").write_text(json.dumps({"n": 5, "agent": "garde", "apercu": "purger les journaux", "valideur": "vigie"}))
    code = (f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
            "print(json.dumps({'cartes':[[c,t] for c,t,_,_ in g['cartes_tableau']()],'large':g['VUES']['colonnes'].vue_colonnes(160,40),'etroit':g['VUES']['colonnes'].vue_colonnes(70,40),"
            "'onglets':g['ONGLETS_BERGER'],'icone':g['ICONES_ONGLETS'].get('Tableau')}))")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    x = json.loads(r.stdout); c = {tuple(k) for k in x["cartes"]}
    dire(("proprio", "● Scribe") in c, "agent bloqué (⚠ dans sa checklist) → ATTEND <PROPRIÉTAIRE>")
    dire(("proprio", "validation n° 4") in c and ("agent", "validation n° 5") in c, "validation pour le propriétaire → ATTEND <PROPRIÉTAIRE> ; déléguée à un agent → ATTEND UN AGENT")
    dire(("proprio", "📖 à lire (1)") in c, "document non lu → ATTEND <PROPRIÉTAIRE>")
    dire(("cours", "● Vigie") in c and ("repos", "● Scribe") not in c, "agent que Herdr voit au travail → EN COURS")
    dire(("repos", "● Garde") in c and ("livre", "● Garde") in c, "agent sans terminal → AU REPOS ; checklist terminée < 24 h → LIVRÉ · 24 h")
    dire(r.returncode == 0 and not any(t_ == "validation n° 6" for _, t_ in c), "validation à moitié écrite : ignorée, le panneau ne casse pas")
    dire(("proprio", "validation n° 7") in c and ("agent", "fusion app") in c and sum(1 for k in x["cartes"] if tuple(k) == ("agent", "fusion app")) == 1,
         "fusion déjà en validation : une seule carte (la validation) ; l'autre demande (renvoyée) attend son agent")
    grand = [net(l) for l in x["large"]]; petit = [net(l) for l in x["etroit"]]
    dire(all(larg(l) <= 160 for l in grand) and all(larg(l) <= 70 for l in petit), f"largeur jamais dépassée (max {max(map(larg, grand))}/160, {max(map(larg, petit))}/70)")
    dire("EN COURS (1)" in grand[2] and "LIVRÉ · 24 h (1)" in grand[2], "pane large : les 5 colonnes côte à côte, avec leur compte")
    dire(any(l.startswith("ATTEND PROPRIO (4)") for l in petit) and any(l.startswith("AU REPOS") for l in petit), "pane étroit : colonnes empilées")
    dire(not any(re.search(r"\w-\s*│?\s*$", l.replace("│", "").rstrip()) or "mise- " in l or "à- " in l for l in grand),
         "texte plié sans couper un mot à son trait d'union (mise-à-jour-des-politiques)")
    dire(x["onglets"][:3] == [["Livrables", "livrables"], ["Documents", "documents"], ["Tableau", "colonnes"]] and x["icone"] == "📋",
         "onglet « 📋 Tableau » déclaré juste après Livrables et Documents (en tête depuis le 14/10, demandes du propriétaire), après Accueil")
    # Tableau de l'AGENT (vue tableau) d'un agent qui a une écriture en attente : il cassait (13/10, « 'dict' / 'str' »)
    code = (f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
            "print(json.dumps(g['VUES']['tableau'].rendre(120, 40, 'vigie'), ensure_ascii=False))")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    dire(r.returncode == 0 and "écriture n° 4" in net(r.stdout), f"Tableau de l'agent avec une écriture en attente : rendu, sans erreur ({r.stderr.strip()[-120:]})")

sys.exit(1 if ko else 0)
