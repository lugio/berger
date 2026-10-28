#!/usr/bin/env python3
"""Tests de l'équipe qui corrige Berger (09/10/2026) — sans modèle, sans Herdr, installation JETABLE.
1. Une équipe ne peut pas avoir l'installation EN SERVICE pour dépôt : une fusion y serait un déploiement sans relecture
   (`berger equipe ouvrir` refuse, rien n'est créé).
2. Le circuit de la forge LOCALE, avec les commandes EXACTES de config.exemple.toml ([outils.berger-admin.actions]) :
   une fusion de l'équipe ne part pas en ligne ; « exporter » remet un bundle vérifié ; « publier » envoie la forge locale
   en ligne en avance rapide SEULEMENT (jamais de force : refus si la forge en ligne a divergé, rien d'écrasé) ;
   « synchroniser » ramène ce qui a changé en ligne, en avance rapide seulement.
   (« installer » — l'installation prend la forge locale — se prouve sur l'installation réelle.)
Usage : python3 tests/equipe-berger.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, subprocess, sys, tempfile, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def commande_exemple(verbe):
    """La commande `verbe` de [outils.berger-admin.actions], telle qu'écrite (commentée) dans config.exemple.toml."""
    for ligne in (SRC / "config.exemple.toml").read_text().splitlines():
        if re.match(rf"# {verbe} = ", ligne): return tomllib.loads(ligne[2:])[verbe]
    raise SystemExit(f"{verbe} absent de config.exemple.toml")


def git(d, *a): return subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True, env=ENV)


ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n\n'
                                   f'[equipes.berger]\ndepot = "{i}"\nchef_projet = "master"\ncoordinateur = "master"\nfusion_par = "proprietaire"\n')
    d = i / "agents/master"; (d / "memory").mkdir(parents=True)
    (d / "agent.conf").write_text("nom = Master\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils = equipe:berger\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "--stdin"],
                       input=json.dumps(["equipe", "ouvrir", "berger", "correctif", "mission", "--par", "master"]),
                       env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode != 0 and "ne peut pas être l'installation" in r.stderr, "dépôt = l'installation en service : ouverture refusée")
    dire(not (i / "agents/berger-correctif").exists() and not (m / "berger-copies").exists(), "dépôt = l'installation : rien n'est créé")

with tempfile.TemporaryDirectory() as t:
    m = Path(t); ENV["HOME"] = str(m); i = m / "berger"; (i / "a-lire").mkdir(parents=True)
    enligne, forge, chef = m / "enligne.git", m / "projets/berger.git", m / "projets/berger"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(enligne)])
    graine = m / "graine"; subprocess.run(["git", "clone", "-q", str(enligne), str(graine)], capture_output=True)
    (graine / "README.md").write_text("v1\n"); git(graine, "add", "-A"); git(graine, "commit", "-qm", "v1"); git(graine, "push", "-q", "origin", "main")
    # mise en place, comme dans config.exemple.toml
    subprocess.run(["git", "clone", "-q", "--bare", str(enligne), str(forge)], capture_output=True)
    git(forge, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/forge/*")
    git(forge, "remote", "add", "publication", str(enligne))      # en réel : l'alias ssh de la clé d'écriture du courtier
    subprocess.run(["git", "clone", "-q", str(forge), str(chef)], capture_output=True)
    def action(verbe): return subprocess.run(["bash", "-c", commande_exemple(verbe)], cwd=i, capture_output=True, text=True, env=ENV, timeout=60)

    # l'équipe fusionne (le chef pousse sur la forge LOCALE, comme equipe_chef.fusionner)
    (chef / "README.md").write_text("v2 par l'équipe\n"); git(chef, "commit", "-qam", "fix: par l'équipe"); git(chef, "push", "-q", "origin", "main")
    dire(git(enligne, "log", "--oneline", "main").stdout.count("\n") == 1, "fusion de l'équipe : rien n'est parti en ligne")
    r = action("exporter"); bundles = list((i / "a-lire").glob("berger-*.bundle"))
    dire(r.returncode == 0 and len(bundles) == 1, "exporter : un bundle dans a-lire/" + ("" if r.returncode == 0 else f" — {r.stderr[-200:]}"))
    lu = subprocess.run(["git", "bundle", "list-heads", str(bundles[0])], capture_output=True, text=True).stdout if bundles else ""
    dire(git(forge, "rev-parse", "main").stdout.strip() in lu, "exporter : le bundle porte exactement le main de l'équipe")
    r = action("publier")
    dire(r.returncode == 0 and git(enligne, "rev-parse", "main").stdout == git(forge, "rev-parse", "main").stdout,
         "publier : la fusion de l'équipe part en ligne (avance rapide)" + ("" if r.returncode == 0 else f" — {r.stderr[-200:]}"))
    r = action("exporter")
    dire(r.returncode != 0 and len(list((i / "a-lire").glob("berger-*.bundle"))) == 1, "exporter : rien à remettre quand tout est déjà en ligne")
    # le propriétaire change quelque chose en ligne
    proprio = m / "proprio"; subprocess.run(["git", "clone", "-q", str(enligne), str(proprio)], capture_output=True)
    (proprio / "AUTRE.md").write_text("par le propriétaire\n"); git(proprio, "add", "-A"); git(proprio, "commit", "-qm", "en ligne"); git(proprio, "push", "-q", "origin", "main")
    r = action("synchroniser")
    dire(r.returncode == 0 and git(forge, "rev-parse", "main").stdout == git(enligne, "rev-parse", "main").stdout,
         "synchroniser : la forge locale rejoint la forge en ligne" + ("" if r.returncode == 0 else f" — {r.stderr[-200:]}"))
    dire((chef / "AUTRE.md").is_file(), "synchroniser : le clone du chef aussi (avance rapide)")
    # divergence : l'équipe a fusionné en local ET la forge en ligne a avancé → ni publier ni synchroniser n'écrasent rien
    (chef / "README.md").write_text("v3\n"); git(chef, "commit", "-qam", "local"); git(chef, "push", "-q", "origin", "main")
    (proprio / "AUTRE.md").write_text("encore\n"); git(proprio, "commit", "-qam", "en ligne 2"); git(proprio, "push", "-q", "origin", "main")
    en_ligne, local = git(enligne, "rev-parse", "main").stdout, git(forge, "rev-parse", "main").stdout
    r = action("publier")
    dire(r.returncode != 0 and git(enligne, "rev-parse", "main").stdout == en_ligne, "publier : forge en ligne divergente → refus, JAMAIS de force")
    r = action("synchroniser")
    dire(r.returncode != 0 and git(forge, "rev-parse", "main").stdout == local, "synchroniser : forge locale divergente → refus, rien d'écrasé")
    dire("--force" not in commande_exemple("publier") and " +" not in commande_exemple("publier") and "-f " not in commande_exemple("publier"),
         "publier : la commande ne contient aucune forme de force")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
