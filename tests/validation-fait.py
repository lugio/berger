#!/usr/bin/env python3
"""Tests du résultat d'une validation (13/10/2026) — sans modèle, installation JETABLE, VRAI courtier chargé comme module.
Bug (n° 51 et n° 59) : l'action « installer » finit par `systemd-run … berger courtier redemarrer` ; le redémarrage ne voyait
aucune demande « en cours » (l'action tourne dans la boucle du courtier, pas dans courrier/encours/), coupait le courtier
AVANT que <n>.fait.json soit écrit, et la validation restait « en attente ».
- une action qui redémarre le courtier : <n>.fait.json existe, dit « validé et exécuté », AVANT l'appel à systemctl ;
- une décision sur une validation déjà faite : refusée « déjà faite » (berger valider|refuser et le courtier) ; l'action n'est pas rejouée ;
- action coupée en plein vol (courtier arrêté) : jamais rejouée, dite « état inconnu » ; les autres validations ne sont pas touchées.
Usage : python3 tests/validation-fait.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.machinery, importlib.util, json, os, subprocess, sys, tempfile, time
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
    d = i / "agents/admin"; (d / "memory").mkdir(parents=True)
    (d / "agent.conf").write_text("nom = admin\npanneaux = claude\nheures = aucune\noutils =\n")
    # faux systemctl : note l'instant de l'appel et l'état du fichier résultat à cet instant
    fb = m / ".local/bin"; fb.mkdir(parents=True)     # bin/berger place HOME/.local/bin en tête de son PATH
    V = i / "courtier/validations"; V.mkdir(parents=True)
    (fb / "systemctl").write_text('#!/bin/sh\nif [ -f "' + str(V) + '/1.fait.json" ]; then echo "fait present" > "' + str(m) + '/systemctl.txt"; '
                                  'else echo "fait ABSENT" > "' + str(m) + '/systemctl.txt"; fi\n'); os.chmod(fb / "systemctl", 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "PATH": f"{fb}:{os.environ['PATH']}"}
    os.environ.update(HOME=str(m), BERGER_DIR=str(i))
    berger = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=120)
    loader = importlib.machinery.SourceFileLoader("courtier_essai", str(i / "courtier/courtier"))
    spec = importlib.util.spec_from_loader("courtier_essai", loader); C = importlib.util.module_from_spec(spec); loader.exec_module(C)

    compte = m / "rejouees.txt"
    def action_installer(args):                                   # comme `installer` : lance le redémarrage détaché, puis finit son travail
        subprocess.Popen([sys.executable, str(i / "bin/berger"), "courtier", "redemarrer"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)                                           # la fin de l'action (journal, échanges) n'est pas instantanée
        with open(compte, "a") as f: f.write("x")
        return "installé"
    C.ECRITURES["essai"] = {"installer": (lambda a: "installer", action_installer), "autre": (lambda a: "autre", lambda a: "fait")}
    C.contexte = lambda *a, **k: None
    def demande(n, verbe):
        (V / f"{n}.json").write_text(json.dumps({"n": n, "agent": "admin", "outil": "essai", "verbe": verbe, "args": [], "apercu": verbe, "valideur": None}))
    def decision(n, ce="valider"): (V / f"{n}.decision").write_text(ce + "\n")

    demande(1, "installer"); demande(2, "autre"); demande(3, "autre")
    decision(1); C.traiter_decisions()
    f1 = V / "1.fait.json"
    dire(f1.exists() and json.loads(f1.read_text())["etat"] == "validé et exécuté", "action qui redémarre le courtier : 1.fait.json existe et dit « validé et exécuté »")
    for _ in range(80):
        if (m / "systemctl.txt").exists(): break
        time.sleep(0.25)
    dire((m / "systemctl.txt").exists() and (m / "systemctl.txt").read_text().strip() == "fait present",
         "le redémarrage n'a lieu qu'APRÈS l'inscription du résultat (" + ((m / "systemctl.txt").read_text().strip() if (m / "systemctl.txt").exists() else "jamais appelé") + ")")
    dire(not (V / "1.json").exists() and not list(V.glob("*.execution")), "demande rangée, plus aucune marque « en cours »")
    dire((V / "2.json").exists() and (V / "3.json").exists() and not (V / "2.fait.json").exists(), "les autres validations en attente ne sont pas touchées")

    # décision sur une validation déjà faite : refusée, action non rejouée
    r = berger("refuser", "1"); dire(r.returncode != 0 and "déjà faite" in r.stdout + r.stderr, f"berger refuser sur une validation faite : « déjà faite » ({(r.stderr or r.stdout).strip()[:90]})")
    r = berger("valider", "1"); dire(r.returncode != 0 and "déjà faite" in r.stdout + r.stderr, "berger valider sur une validation faite : « déjà faite »")
    decision(1); C.traiter_decisions()
    dire(compte.read_text() == "x" and not (V / "1.decision").exists() and json.loads(f1.read_text())["etat"] == "validé et exécuté",
         "décision arrivée après coup (course) : ignorée, l'action n'est pas rejouée, le résultat reste")
    dire(berger("valider", "2").returncode == 0 or (V / "2.decision").exists() or (V / "2.fait.json").exists(), "une validation en attente reste décidable")

    # action coupée en plein vol : jamais rejouée, dite « état inconnu »
    demande(4, "installer"); (V / "4.execution").write_text("valider\n"); demande(5, "autre")
    C.reprendre_executions()
    f4 = json.loads((V / "4.fait.json").read_text()) if (V / "4.fait.json").exists() else {}
    dire("inconnu" in str(f4.get("resultat")) and f4.get("etat") == "validé mais ÉCHEC" and not (V / "4.json").exists() and not list(V.glob("*.execution")),
         "démarrage du courtier : action coupée en plein vol → « état inconnu », marque retirée, jamais rejouée")
    dire((V / "5.json").exists() and not (V / "5.fait.json").exists(), "au démarrage, les autres validations en attente ne sont pas touchées")
print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
