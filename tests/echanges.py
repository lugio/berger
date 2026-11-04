#!/usr/bin/env python3
"""Tests du journal et du panneau Échanges — sans modèle, sans Herdr, sans toucher à l'installation : une installation
jetable (BERGER_DIR) avec deux agents. Usage : python3 tests/echanges.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.machinery, importlib.util, json, os, re, subprocess, sys, tempfile
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin/berger"
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    t = Path(t); env = {**os.environ, "BERGER_DIR": str(t)}
    (t / "config.toml").write_text('proprietaire = "Camille"\n')
    for a, nom in (("compta", "Léa"), ("veille", "Hugo")):
        (t / "agents" / a).mkdir(parents=True); (t / "agents" / a / "agent.conf").write_text(f"nom = {nom}\n")
    b = lambda *x: subprocess.run([str(BIN), *x], env=env, capture_output=True, text=True)

    b("echange", "compta", "veille", "question", "Quelle  est la date\n de clôture ?")
    b("echange", "veille", "compta", "réponse", "Le 31/12.")
    b("echange", "compta", "Camille", "validation demandée", "n° 3 : envoyer la relance")
    lignes = [json.loads(l) for l in (t / "courtier/echanges.jsonl").read_text().splitlines()]
    dire(len(lignes) == 3, "trois échanges écrits, une ligne JSON chacun")
    dire(lignes[0]["texte"] == "Quelle est la date de clôture ?", "texte remis sur une ligne (espaces et retours repliés)")
    dire(all({"quand", "de", "a", "genre", "texte"} <= set(l) for l in lignes), "chaque échange a quand / de / a / genre / texte")
    b("echange", "compta", "veille", "question", "x" * 5000)
    dire(len(json.loads((t / "courtier/echanges.jsonl").read_text().splitlines()[-1])["texte"]) == 1500, "texte borné à 1 500 caractères")

    os.environ["BERGER_DIR"] = str(t)
    spec = importlib.util.spec_from_loader("berger", importlib.machinery.SourceFileLoader("berger", str(BIN)))
    berger = importlib.util.module_from_spec(spec); spec.loader.exec_module(berger)
    nu = lambda lignes: re.sub(r"\033\[[0-9;]*m", "", "\n".join(lignes))
    tout = nu(berger.VUES["echanges"].vue_echanges(None, 100, 40))
    dire("Léa → Hugo" in tout and "Hugo → Léa" in tout, "vue d'ensemble : agents désignés par leur NOM (agent.conf)")
    dire("Camille" in tout and "validation demandée" in tout, "le propriétaire et le genre d'échange apparaissent")
    dire(tout.index("clôture") < tout.index("31/12"), "ordre chronologique : le plus récent en bas")
    b("echange", "Camille", "compta", "message", "Bonjour")
    seul = nu(berger.VUES["echanges"].vue_echanges("veille", 100, 40))
    dire("31/12" in seul and "Bonjour" not in seul, "vue d'un agent : seulement ce qu'il a reçu ou envoyé")
    for i in range(40): b("echange", "Camille", "compta", "message", f"message {i}")
    court = berger.VUES["echanges"].vue_echanges(None, 100, 20)
    dire(len(court) <= 20 and "message 39" in nu(court) and "plus haut" in nu(court), "écran court : derniers échanges, le reste signalé « plus haut »")
    (t / "courtier/echanges.jsonl").write_text((t / "courtier/echanges.jsonl").read_text() + "ligne abîmée\n")
    dire("message 39" in nu(berger.VUES["echanges"].vue_echanges(None, 100, 20)), "une ligne illisible est ignorée, le panneau continue")

    r = subprocess.run([str(BIN), "echange", "compta", "veille", "message", "--stdin"], input="aperçu transmis sur stdin", env=env, capture_output=True, text=True)
    dernier = json.loads((t / "courtier/echanges.jsonl").read_text().splitlines()[-1])
    dire(r.returncode == 0 and dernier["texte"] == "aperçu transmis sur stdin", "transport stdin conservé jusqu’au journal")

sys.exit(1 if ko else 0)
