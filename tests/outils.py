#!/usr/bin/env python3
"""Tests des outils à commandes fixées (types « commandes », « ssh » et « scripts ») — sans réseau, sans installation, sans coffre.
Usage : python3 tests/outils.py   (code de retour 0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util, sys, tempfile
from pathlib import Path

OUTILS = Path(__file__).resolve().parent.parent / "courtier/outils"
ko = 0


def charger(t):
    spec = importlib.util.spec_from_file_location(f"outil_{t}", OUTILS / f"{t}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def refuse(f, args):
    try: f(args); return False
    except ValueError: return True


with tempfile.TemporaryDirectory() as d:
    temoin = Path(d) / "temoin"
    o = charger("commandes").Outil({"dossier": d, "lecture": {"bonjour": "echo bonjour", "afficher": "echo {arg}"},
                                    "actions": {"creer": f"touch {temoin}"}}, None, None)
    r = o.verbes["bonjour"]([])
    dire(r["code"] == 0 and r["sortie"].strip() == "bonjour", "commandes : une lecture tourne dans son dossier")
    dire(o.verbes["afficher"](["feat/essai-1.2"])["sortie"].strip() == "feat/essai-1.2", "commandes : un argument simple passe (branche feat/…)")
    for mauvais in (["a; touch x"], ["$(id)"], ["`id`"], ["../etc"], ["--force"], ["+main"], ["a b"], ["x" * 65], [], ["a", "b"]):
        dire(refuse(o.verbes["afficher"], mauvais), f"commandes : argument refusé {str(mauvais)[:30]}")
    dire(refuse(o.verbes["bonjour"], ["x"]), "commandes : argument refusé quand la commande n'en prend pas")
    apercu, executer = o.ecritures["creer"]
    texte = apercu([])
    dire(not temoin.exists() and "touch" in texte, "commandes : l'aperçu d'une action ne l'exécute PAS")
    executer([]); dire(temoin.exists(), "commandes : l'action s'exécute seulement quand le courtier l'appelle (après validation)")
    dire("bonjour" not in o.ecritures and "creer" not in o.verbes, "commandes : lectures et actions bien séparées")
    # {agent} = l'agent QUI DEMANDE, posé par le courtier (contexte), jamais une valeur fournie par l'agent
    q = charger("commandes").Outil({"dossier": d, "lecture": {"qui": "echo {agent}:{arg}"}}, None, None)
    dire(refuse(q.verbes["qui"], ["x"]), "commandes : {agent} refusé sans appelant connu (aucun contexte posé)")
    q.contexte = {"agent": "assistante"}
    dire(q.verbes["qui"](["x"])["sortie"].strip() == "assistante:x", "commandes : {agent} = l'appelant posé par le courtier")
    q.contexte = {"agent": "a; touch x"}
    dire(refuse(q.verbes["qui"], ["x"]), "commandes : un nom d'appelant douteux est refusé")

s = charger("ssh").Outil({"hote": "serveur.exemple", "port": 2222, "utilisateur": "admin", "cle_fichier": "~/.ssh/cle",
                          "lecture": {"logs": "docker logs --tail 50 {arg}"}, "actions": {"redemarrer": "docker restart {arg}"}}, None, None)
dire(s.ecritures["redemarrer"][0](["web"]) == "sur admin@serveur.exemple : docker restart web", "ssh : aperçu exact de l'action")
dire(refuse(s.verbes["logs"], ["web; reboot"]) and refuse(s.ecritures["redemarrer"][0], ["$(reboot)"]), "ssh : injection refusée (lecture et action)")
# Exécution RÉELLE de l'outil ssh (pas seulement l'aperçu) : un faux « ssh » dans le PATH rend ses arguments.
# (Défaut trouvé à l'installation : l'outil ssh n'acceptait pas le verbe passé par la base → TypeError, outil inutilisable.)
with tempfile.TemporaryDirectory() as d:
    faux = Path(d) / "ssh"; faux.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n'); faux.chmod(0o755)
    import os as _os
    ancien = _os.environ["PATH"]; _os.environ["PATH"] = f"{d}:{ancien}"
    try:
        r = s.verbes["logs"](["web"]); a_ = s.ecritures["redemarrer"][1](["web"])
        dire(r["code"] == 0 and "admin@serveur.exemple" in r["sortie"] and "docker logs --tail 50 web" in r["sortie"].replace("'", ""),
             "ssh : la LECTURE s'exécute (commande fixée envoyée au serveur)")
        dire(a_["code"] == 0 and "docker restart web" in a_["sortie"].replace("'", ""), "ssh : l'ACTION validée s'exécute")
        dire("-o\nBatchMode=yes" in r["sortie"] and "StrictHostKeyChecking=yes" in r["sortie"], "ssh : sans mot de passe, hôte vérifié (BatchMode, StrictHostKeyChecking)")
    except Exception as e:
        dire(False, f"ssh : exécution en erreur ({type(e).__name__} : {e})")
    finally:
        _os.environ["PATH"] = ancien

with tempfile.TemporaryDirectory() as d:
    (Path(d) / "qui.py").write_text("import os, sys\nprint(os.environ.get('BERGER_AGENT', 'ABSENT'), *sys.argv[1:])\n")
    o = charger("scripts").Outil({"dossier": d, "autorises": ["qui.py"]}, None, None)
    dire(o.verbes["qui.py"](["a"])["sortie"].split() == ["a"], "scripts : sans contexte, BERGER_AGENT est vide (jamais hérité ni inventé)")
    o.contexte = {"agent": "vigie", "dossier": d}                          # ce que pose le courtier avant chaque appel
    dire(o.verbes["qui.py"](["a"])["sortie"].split() == ["vigie", "a"], "scripts : le script reçoit l'agent qui demande (BERGER_AGENT)")
    for mauvais in (["a b"], ["$(id)"], ["a;b"]):
        dire(refuse(o.verbes["qui.py"], mauvais), f"scripts : argument refusé {mauvais}")
    dire("autre.py" not in o.verbes, "scripts : seul un script autorisé devient un verbe")

print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
