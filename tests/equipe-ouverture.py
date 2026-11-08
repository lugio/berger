#!/usr/bin/env python3
"""Ouverture d'un développeur d'équipe — sans modèle ni Herdr, dans une installation jetable : (1) un modèle non permis
est refusé AVANT de rien créer (ni copie ni agent) ; (2) deux ouvertures simultanées ne prennent jamais le même port ; (3) outils_developpeur : seuls les outils
déclarés sont donnés en plus.
Vécus le 07/10 : modèle refusé après création (développeurs à moitié créés) et deux développeurs sur le port 5291.
Usage : python3 tests/equipe-ouverture.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

DEPOT = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def git(d, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True)


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"; i.mkdir()
    for f in subprocess.run(["git", "-C", str(DEPOT), "ls-files"], capture_output=True, text=True).stdout.split():
        (i / f).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(DEPOT / f, i / f)
    forge, depot = m / "forge.git", m / "depot"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)]); subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    (depot / "a").write_text("a"); git(depot, "add", "a"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
    (i / "config.toml").write_text(f'proprietaire = "Essai"\ncoffre = "{m}/coffre.json"\n[missions]\nmax = 4\nmodeles_claude = ["sonnet"]\n'
                                   f'[outils.navigateur]\ntype = "commandes"\ndossier = "{m}"\n'
                                   f'[equipes.p]\ndepot = "{depot}"\ncopies = "{m}/copies"\nmoteur = "claude"\nports = [5291, 5292, 5293]\n'
                                   f'outils_developpeur = ["navigateur", "inconnu"]\n')
    (m / "coffre.json").write_text("{}")
    env = {**{k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}, "HOME": str(m), "BERGER_DIR": str(i), "PATH": "/usr/bin:/bin"}       # sans herdr : la mission échoue après l'agent
    def berger(*a):
        # L'interpréteur du test, pas le shebang : le python3 de /usr/bin peut être antérieur à 3.11 (runner ubuntu-22.04 : 3.10).
        p = subprocess.Popen([sys.executable, str(i / "bin/berger"), "--stdin"], env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p.stdin.write(json.dumps(list(a))); p.stdin.close(); p.stdin = None
        return p

    r = berger("equipe", "ouvrir", "p", "haiku-essai", "une mission d'essai", "--modele", "haiku"); out, err = r.communicate(timeout=120)
    dire(r.returncode != 0 and "non permis" in (err + out), "modèle non permis : refusé")
    dire(not (i / "agents/p-haiku-essai").exists() and not (m / "copies/p-haiku-essai").exists(), "modèle non permis : RIEN n'a été créé (ni agent ni copie)")

    a, b = berger("equipe", "ouvrir", "p", "un", "mission un"), berger("equipe", "ouvrir", "p", "deux", "mission deux")
    a.communicate(timeout=300); b.communicate(timeout=300)
    port = lambda s: next((l.split("=", 1)[1].strip() for l in (i / f"agents/p-{s}/agent.conf").read_text().splitlines() if l.startswith("port")), None) \
        if (i / f"agents/p-{s}/agent.conf").is_file() else None
    pa, pb = port("un"), port("deux")
    dire(pa and pb and pa != pb, f"deux ouvertures simultanées : deux ports différents ({pa}, {pb})")
    outils = next((l.split("=", 1)[1].strip() for l in (i / "agents/p-un/agent.conf").read_text().splitlines() if l.startswith("outils")), "") \
        if (i / "agents/p-un/agent.conf").is_file() else ""
    dire(outils == "p-dev, navigateur", f"outils_developpeur : l'outil déclaré est donné, l'inconnu ignoré ({outils})")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
