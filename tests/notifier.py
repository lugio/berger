#!/usr/bin/env python3
"""Tests de la notification au propriétaire (berger notifier) — sans installation, sans réseau, sans vrai Herdr.
Un faux « herdr » (dans le ~/.local/bin d'un dossier personnel temporaire, placé en tête du PATH par Berger) note
ses arguments. Usage : python3 tests/notifier.py   (code de retour 0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

PRODUIT = Path(__file__).resolve().parent.parent
echecs = 0


def dire(ok, quoi):
    global echecs
    if not ok: echecs += 1
    print(f"{'ok' if ok else 'ÉCHEC':6} {quoi}")


def notifier(maison, titre, texte, code_herdr=None):
    """Lance « berger notifier » dans une installation temporaire ; code_herdr=None : pas de herdr installé."""
    inst = maison / "installation"; (inst / "courtier").mkdir(parents=True, exist_ok=True)
    (inst / "config.toml").write_text('proprietaire = "Essai"\n')
    binaire = maison / ".local/bin"; binaire.mkdir(parents=True, exist_ok=True)
    faux = binaire / "herdr"; trace = maison / "herdr-args.txt"; trace.unlink(missing_ok=True)
    if code_herdr is None: faux.unlink(missing_ok=True)
    else:
        faux.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{trace}"\nexit {code_herdr}\n'); faux.chmod(0o755)
    # Le lanceur du clone frais impose une sentinelle BERGER_HERDR : ce test
    # doit nommer SON double au lieu de dépendre de la variable héritée.
    env = dict(os.environ, HOME=str(maison), BERGER_DIR=str(inst),
               BERGER_HERDR=str(faux), BERGER_NOTIFY_SEND="/bin/true")
    r = subprocess.run([sys.executable, str(PRODUIT / "bin/berger"), "notifier", "--stdin"], input=json.dumps([titre, texte]), env=env,
                       capture_output=True, text=True, timeout=60)
    journal = (inst / "courtier/notifications.log")
    return r, (trace.read_text().splitlines() if trace.exists() else None), (journal.read_text() if journal.exists() else "")


with tempfile.TemporaryDirectory() as t:
    maison = Path(t)
    long = "demande " + "x" * 400
    r, args, journal = notifier(maison, "Berger · validation n° 7", long, code_herdr=0)
    dire(r.returncode == 0, "herdr présent : berger notifier réussit")
    dire(args is not None and args[:3] == ["notification", "show", "Berger"], "herdr présent : notification show avec un titre générique")
    dire(args is not None and "--sound" in args and args[args.index("--sound") + 1] == "request", "herdr présent : son « request »")
    dire(args is not None and "--body" in args and len(args[args.index("--body") + 1]) <= 200, "herdr présent : texte limité à 200 caractères")
    dire("Berger · validation n° 7" in journal and "échec" not in journal, "herdr présent : journal écrit, sans échec")

    r, args, journal = notifier(maison, "Berger · essai", "herdr en panne", code_herdr=3)
    dire(r.returncode == 0, "herdr en échec : berger notifier réussit quand même (le courtier n'est jamais bloqué)")
    dire("herdr en panne" in journal and "[herdr : échec, code 3]" in journal, "herdr en échec : l'échec est écrit dans le journal")

    p = ":".join(d for d in os.environ.get("PATH", "").split(":") if d and not Path(d, "herdr").exists())
    if shutil.which("herdr", path=f"/usr/local/bin:/usr/bin:/bin:{p}"):
        print("INFO   herdr installé dans un dossier système : cas « sans herdr » non testé sur cette machine")
    else:
        os.environ["PATH"] = p
        r, args, journal = notifier(maison, "Berger · sans herdr", "journal seul", code_herdr=None)
        dire(r.returncode == 0 and args is None and "journal seul" in journal, "sans herdr : journal seul, sans erreur")

print(f"---- {echecs} échec(s)")
sys.exit(1 if echecs else 0)
