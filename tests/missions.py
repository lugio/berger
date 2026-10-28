#!/usr/bin/env python3
"""Tests des agents de mission en LECTURE SEULE (`lecture_seule = oui`) — sans modèle, sans Herdr, sans toucher à
l'installation : une installation JETABLE, le courtier appelé directement. Usage : python3 tests/missions.py (0 = OK).
Un agent en lecture seule lit avec ses outils, mais le courtier lui refuse toute écriture (même soumise à validation),
toute mission, délégation, ouverture d'équipe et décision de validation ; un agent ordinaire garde son circuit de validation."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


APPEL = r'''
import json, runpy, sys
from pathlib import Path
g = runpy.run_path(sys.argv[1], run_name="essai")
agent, req = sys.argv[2], json.loads(sys.argv[3])
d = g["AGENTS"] / agent / "courrier"; (d / "encours").mkdir(parents=True, exist_ok=True)
f = d / "encours" / "1.json"; f.write_text(json.dumps(req))
g["traiter"](agent, f, {})
import time
for _ in range(100):
    r = d / "reponses" / "1.json"
    if r.exists(): print(r.read_text()); r.unlink(); break
    time.sleep(0.1)
'''

with tempfile.TemporaryDirectory() as td:
    t = Path(td)
    _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    (t / "coffre.json").write_text('{"essai": {"cle": "valeur-secrete-du-test"}}')
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n\n[missions]\nmax = 2\n\n'
                                   '[outils.essai]\ntype = "essai"\n')
    for a, extra in (("eclaireur", "lecture_seule = oui   # agent de mission\n"), ("ordinaire", ""), ("cible", "")):
        d = t / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\nheures = aucune\n"
                                      f"outils = essai, mission:cible, deleguer:cible\n{extra}")
    env = dict(os.environ, BERGER_DIR=str(t), PATH=f"{t}/faux:{os.environ['PATH']}")
    (t / "faux").mkdir(); (t / "faux/notify-send").write_text("#!/bin/sh\nexit 0\n"); os.chmod(t / "faux/notify-send", 0o755)

    def appel(agent, outil, verbe, *args):
        r = subprocess.run([sys.executable, "-c", APPEL, str(t / "courtier/courtier"), agent,
                            json.dumps({"outil": outil, "verbe": verbe, "args": list(args)})],
                           env=env, capture_output=True, text=True, timeout=60)
        try: return json.loads(r.stdout)
        except ValueError: return {"ok": None, "erreur": (r.stderr or r.stdout)[-300:]}

    r = appel("eclaireur", "essai", "lire")
    dire(r.get("ok") is True, "lecture seule : une LECTURE passe (essai lire)")
    r = appel("cible", "deleguer", "ordinaire", "question témoin")
    dire(r.get("ok") is False and r.get("erreur") == "cible n'a pas le droit de déléguer à ordinaire",
         "délégation sans droit : refus exact du vrai courtier, sans lancer de moteur")
    r = appel("eclaireur", "essai", "noter", "écrire quelque chose")
    dire(r.get("ok") is False and "LECTURE SEULE" in r.get("erreur", ""), "lecture seule : une écriture est refusée net")
    v = t / "courtier/validations"
    dire(not any(v.glob("*.json")) if v.is_dir() else True, "lecture seule : AUCUNE demande de validation créée (rien à faire valider)")
    dire(not (t / "courtier/essai-ecritures.txt").exists(), "lecture seule : rien n'est écrit")
    for outil, verbe, args, quoi in (("mission", "confier", ["cible", "faire x"], "confier une mission"),
                                     ("deleguer", "cible", ["question"], "déléguer"),
                                     ("equipe", "ouvrir", ["p", "s", "x"], "ouvrir une équipe"),
                                     ("validation", "accepter", ["1"], "décider une validation")):
        r = appel("eclaireur", outil, verbe, *args)
        dire(r.get("ok") is False and "LECTURE SEULE" in r.get("erreur", ""), f"lecture seule : {quoi} est refusé")
    r = appel("eclaireur", "validation", "liste")
    dire(r.get("ok") is True, "lecture seule : la liste des validations reste lisible")
    # témoin : l'agent ordinaire, lui, garde son circuit (demande mise en attente, rien écrit avant décision)
    r = appel("ordinaire", "essai", "noter", "écrire quelque chose")
    dire(r.get("ok") is True and r.get("en_attente"), "agent ordinaire : l'écriture part en validation (témoin)")
    dire(not (t / "courtier/essai-ecritures.txt").exists(), "agent ordinaire : rien n'est écrit avant la décision")
    # panneau Fiche › limites : la lecture seule s'y voit
    code = ("import runpy, sys, re; g = runpy.run_path(%r, run_name='essai'); "
            "print(re.sub(r'\\x1b\\[[0-9;]*m', '', '\\n'.join(g['fiche_limites']('eclaireur', 100, 40))))" % str(t / "bin/berger"))
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30)
    dire("LECTURE SEULE" in r.stdout, "Fiche › limites : « LECTURE SEULE » affiché" + ("" if r.returncode == 0 else f" (erreur : {r.stderr[-200:]})"))
    # rapport de mission : seuls les documents écrits DEPUIS le début de la mission reviennent à qui l'a confiée
    import time as _t
    d = t / "agents/cible"; (d / "a-lire").mkdir(exist_ok=True)
    vieux = d / "a-lire/2026-01-01_ancien.md"; vieux.write_text("# Ancien rapport\n"); os.utime(vieux, (_t.time() - 3600,) * 2)
    (d / "MISSION.md").write_text("# Mission confiée par ordinaire — test\nmoteur : claude\n\nvérifier x\n")
    (d / "a-lire/2026-10-07_x.md").write_text("# Rapport x\nconstat\n")
    r = subprocess.run([str(t / "bin/berger"), "rapport-mission", "cible"], env=env, capture_output=True, text=True, timeout=30)
    try: docs = json.loads(r.stdout)["documents"]
    except (ValueError, KeyError): docs = None
    dire(docs is not None and [x["fichier"] for x in docs] == ["2026-10-07_x.md"] and docs[0]["texte"].startswith("# Rapport x"),
         "rapport de mission : le document de la mission revient, pas l'ancien" + ("" if docs is not None else f" ({(r.stderr or r.stdout)[-160:]})"))
    (d / "MISSION.md").unlink()
    r = subprocess.run([str(t / "bin/berger"), "rapport-mission", "cible"], env=env, capture_output=True, text=True, timeout=30)
    dire(r.returncode != 0 and "pas de mission" in r.stderr, "rapport de mission : refusé sans mission en cours")
    # identité de l'agent posée dans le shell du panneau avant le moteur (pas seulement l'environnement de l'espace Herdr)
    code = ("import runpy, sys, json; g = runpy.run_path(%r, run_name='essai')['demarrer_agent'].__globals__; appels = []; "
            "g['herdr'] = lambda *a: appels.append(list(a)) or {'ok': 1}; g['exiger_bac_a_sable'] = lambda a: None; g['moteurs'].moteur_admis = lambda m, a: None; "
            "g['confiance_claude'] = lambda a: None; g['time'].sleep = lambda s: None; "
            "g['demarrer_agent']('cible', 'claude', 'p9'); print(json.dumps(appels))" % str(t / "bin/berger"))
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30)
    try: appels = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): appels = []
    run = next((a for a in appels if a[:2] == ["pane", "run"]), [])
    dep = next((i for i, a in enumerate(appels) if a[:2] == ["agent", "start"]), -1)
    dire(run and "export BERGER_AGENT=cible " in run[-1] and f"BERGER_DIR={t}" in run[-1] and 0 <= appels.index(run) < dep,
         "démarrage : BERGER_AGENT et BERGER_DIR posés dans le panneau AVANT le moteur" + ("" if run else f" ({r.stderr[-160:]})"))
print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
