# -*- coding: utf-8 -*-
"""Copie du PRODUIT seul (fichiers suivis par Git) vers une installation jetable de test.

Vécu le 07/10 : les tests copiaient bin/, courtier/, commun/ en entier — avec les DONNÉES de l'installation qui les lance
(courtier/validations, courtier/panneaux…). Une vraie validation en attente sur la VM faisait échouer les tests du Tableau
et de la Synthèse. Seuls les fichiers suivis sont copiés ; hors dépôt Git, repli sur une copie sans les données connues."""
import shutil, subprocess
from pathlib import Path

DONNEES = ("*.log", "__pycache__", "validations", "panneaux", "*.jsonl", "ecrire-debit.json", "boucles.json", "sollicitations", "dernier-audit.txt", "derniere-sauvegarde.txt", "essai-ecritures.txt")


def copier(src, dst, dossiers=("bin", "courtier", "commun")):
    src, dst = Path(src), Path(dst)
    r = subprocess.run(["git", "-C", str(src), "ls-files", "--", *dossiers], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        for f in r.stdout.splitlines():
            (dst / f).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src / f, dst / f)
        return
    for d in dossiers: shutil.copytree(src / d, dst / d, ignore=shutil.ignore_patterns(*DONNEES))


def verbes_declares(src):
    """Les verbes de Berger lus SANS charger bin/berger (modulaire lot 3 : l'ancien aiguillage `cmd == …` de main() n'existe plus) :
    ceux que le registre des commandes DISPATCHE (clés de VERBES dans bin/commandes/*.py, clés de VERBES_COEUR dans bin/berger, jamais ceux
    d'une AIDE seule) ET qui ont leur ligne d'AIDE : une aide sans verbe, ou un verbe sans aide, ne passe pas ces contrôles."""
    import ast
    def cles(arbre, nom):
        for n in arbre.body:
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == nom for t in n.targets) and isinstance(n.value, ast.Dict):
                return {k.value for k in n.value.keys if isinstance(k, ast.Constant)}
        return set()
    src = Path(src); coeur = ast.parse((src / "bin/berger").read_text(encoding="utf-8"))
    verbes, aides = cles(coeur, "VERBES_COEUR"), set()
    for f in sorted((src / "bin/commandes").glob("*.py")):
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        if f.stem != "transition": verbes |= cles(arbre, "VERBES")
        aides |= cles(arbre, "AIDE")
    return verbes & aides


def admettre_moteurs(dst):
    """Moteurs admis dans l'installation jetable (mcp-trous, 17/10), pour les tests dont l'admission n'est pas l'objet
    (tests/mcp-trous.py la prouve) ; sans lui, une version jamais vue y serait non admise (contrat impossible à jouer).
    Jamais les vrais moteurs : leur version dépend de l'environnement (raccourcis mise sous un HOME jetable : « config not
    trusted » dans l'env d'un service, vécu dans la porte du courtier le 18/10). De faux exécutables qui ne répondent qu'à
    --version (tout autre appel échoue) sont mis en tête du PATH de ce processus — donc de l'env des sous-processus construits
    depuis os.environ —, et leur version est déclarée ADMIS."""
    import os
    dst = Path(dst); c = dst / "tests/contrats"; c.mkdir(parents=True, exist_ok=True); faux = dst / "faux-moteurs"; faux.mkdir(exist_ok=True)
    for m in ("claude", "codex"):
        x = faux / m
        x.write_text(f'#!/bin/sh\n[ "$1" = --version ] && {{ echo "9.9.9 (faux {m} des tests)"; exit 0; }}\n'
                     f'echo "faux {m} des tests : seul --version répond" >&2; exit 1\n'); x.chmod(0o755)
        (c / f"{m}-9.9.9.txt").write_text(f"ADMIS\nmoteur : {m} 9.9.9\n")
    os.environ["PATH"] = f"{faux}{os.pathsep}{os.environ.get('PATH', '')}"
