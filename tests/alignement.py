#!/usr/bin/env python3
"""Tests de l'alignement après une mise en production (docs/plans/2026-10-16-alignement-spec.md) — sans modèle, installation
JETABLE (forge, dépôt du chef, outils à commandes fixées qui rejouent un compte rendu) ; rien ne parle au vrai Berger.
1. Déclaration dans [equipes.<p>] : acceptée ; chaque refus au chargement du courtier (élément inconnu, prod_outil qui n'est
   pas une action, compte_rendu_outil / version_servie_outil qui ne sont pas des lectures, wiki hors zones, avec « .. », vide,
   outil wiki absent, relire mal formé) ; un projet sans alignement : rien ne change (mêmes outils, mêmes droits).
Usage : python3 tests/alignement.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.machinery, importlib.util, json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0
ENV_GIT = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def git(d, *a): return subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True, env={**os.environ, **ENV_GIT})


N = [0]
def charger_courtier(i):
    N[0] += 1; nom = f"courtier_al{N[0]}"
    loader = importlib.machinery.SourceFileLoader(nom, str(i / "courtier/courtier"))
    spec = importlib.util.spec_from_loader(nom, loader); c = importlib.util.module_from_spec(spec); loader.exec_module(c); return c


def chargement(i, conf):
    """(courtier, None) si chargé ; (None, motif) si refusé au chargement."""
    (i / "config.toml").write_text(conf)
    try: return charger_courtier(i), None
    except SystemExit as e: return None, str(e)


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"; _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    forge, depot = m / "projets/monprojet.git", m / "projets/monprojet"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    (depot / "README").write_text("départ\n"); git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
    wiki = m / "outils-wiki"; wiki.mkdir()
    (wiki / "reglages.json").write_text(json.dumps({"zones": ["service_info/", "Manuel/RCA"], "ecriture_interdite": ["service_info/procedures"]}))
    (wiki / "arbre.py").write_text("print('0 page')\n")
    (m / "coffre.json").write_text("{}")
    for a in ("chef-mp", "coord"):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = {a}\npanneaux = claude\nheures = aucune\noutils =\n")
    os.environ.update(HOME=str(m), BERGER_DIR=str(i))

    BASE = (f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n\n'
            f'[outils.mp-prod]\ntype = "commandes"\ndossier = "{m}"\n[outils.mp-prod.lecture]\ncompte-rendu = "cat cr.json"\nversion = "cat version.txt"\n'
            f'[outils.mp-prod.actions]\nprod = "cat cr.json"\n\n'
            f'[outils.wikijs-lecture]\ntype = "scripts"\ndossier = "{wiki}"\nautorises = ["arbre.py"]\n\n'
            f'[equipes.monprojet]\ndepot = "{depot}"\nchef_projet = "chef-mp"\ncoordinateur = "coord"\npret = "true"\n')
    DECL = ('alignement = ["changelog", "wiki", "memoire", "skills", "versions"]\nprod_outil = "mp-prod prod"\n'
            'compte_rendu_outil = "mp-prod compte-rendu"\nversion_servie_outil = "mp-prod version"\nwiki = "service_info/monprojet"\n')
    MODS = ('[equipes.monprojet.modules]\nfactu = { chemins = ["app/factu/"], relire = ["wiki:service_info/monprojet/factu", "skill:facturation"] }\n')

    # ── 1. déclaration ──
    sans, motif = chargement(i, BASE)
    dire(sans is not None, f"sans alignement : le courtier se charge comme avant ({motif or 'chargé'})")
    avec, motif = chargement(i, BASE + DECL + MODS)
    dire(avec is not None, f"déclaration complète (alignement, prod_outil, compte_rendu_outil, version_servie_outil, wiki, modules) acceptée ({motif or 'chargé'})")
    if sans and avec:
        dire(set(sans.OUTILS) == set(avec.OUTILS) and sans.droits_equipe("chef-mp") == avec.droits_equipe("chef-mp"),
             "déclaration : mêmes outils, mêmes droits (aucun droit ajouté par le point 1)")
    for plus, quoi in ((DECL.replace('"versions"]', '"versions", "photos"]'), "élément inconnu dans alignement"),
                       (DECL.replace('alignement = [', 'alignement = "changelog" #['), "alignement qui n'est pas une liste"),
                       (DECL.replace('prod_outil = "mp-prod prod"', 'prod_outil = "mp-prod compte-rendu"'), "prod_outil qui est une lecture"),
                       (DECL.replace('prod_outil = "mp-prod prod"', 'prod_outil = "inconnu prod"'), "prod_outil d'un outil inconnu"),
                       (DECL.replace('compte_rendu_outil = "mp-prod compte-rendu"', 'compte_rendu_outil = "mp-prod prod"'), "compte_rendu_outil qui est une action"),
                       (DECL.replace('version_servie_outil = "mp-prod version"', 'version_servie_outil = "mp-prod prod"'), "version_servie_outil qui est une action"),
                       (DECL.replace('version_servie_outil = "mp-prod version"', 'version_servie_outil = "mp-prod absent"'), "version_servie_outil inconnu"),
                       (DECL.replace('wiki = "service_info/monprojet"', 'wiki = "autre_espace/monprojet"'), "wiki hors des zones de l'outil"),
                       (DECL.replace('wiki = "service_info/monprojet"', 'wiki = "service_inf"'), "wiki qui n'est qu'un début de nom de zone"),
                       (DECL.replace('wiki = "service_info/monprojet"', 'wiki = "service_info/../secret"'), "wiki avec « .. »"),
                       (DECL.replace('wiki = "service_info/monprojet"', 'wiki = ""'), "wiki vide"),
                       (DECL + MODS.replace('"skill:facturation"', '"page:facturation"'), "relire qui n'est ni wiki: ni skill: ni memoire:"),
                       (DECL + MODS.replace('chemins = ["app/factu/"]', 'chemins = ["../ailleurs/"]'), "chemins de module avec « .. »")):
        c, motif = chargement(i, BASE + plus)
        dire(c is None and "alignement refusé" in (motif or ""), f"refus au chargement : {quoi} ({(motif or 'CHARGÉ').splitlines()[-1][:110]})")
    c, motif = chargement(i, BASE.replace("[outils.wikijs-lecture]", "[outils.autre-wiki]") + DECL)
    dire(c is None and "introuvables" in (motif or ""), "refus au chargement : wiki déclaré sans outil wiki de lecture")
    (wiki / "reglages.json").write_text(json.dumps({"ecriture_interdite": []}))
    c, motif = chargement(i, BASE + DECL)
    dire(c is None and "introuvables" in (motif or ""), "refus au chargement : outil wiki sans zones")
    c, motif = chargement(i, BASE.replace('autorises = ["arbre.py"]', 'autorises = ["arbre.py"]\nzones = ["service_info/monprojet"]') + DECL)
    dire(c is not None, f"zones lues dans [outils.wikijs-lecture] zones si présentes ({motif or 'chargé'})")
    autre = BASE.replace("[outils.wikijs-lecture]", "[outils.mon-wiki]").replace('autorises = ["arbre.py"]', 'autorises = ["arbre.py"]\nzones = ["service_info/"]')
    c, motif = chargement(i, autre + DECL + '\n[wiki]\nlecture = "mon-wiki"\n')
    dire(c is not None, f"[wiki] lecture = \"mon-wiki\" : un autre nom d'outil wiki ({motif or 'chargé'})")
    exemple = (SRC / "config.exemple.toml").read_text()
    dire(all(k in exemple for k in ("alignement = [", "prod_outil =", "compte_rendu_outil =", "version_servie_outil =", "[equipes.monprojet.modules]")),
         "config.exemple.toml : la déclaration d'alignement y est, commentée")

print(f"\n{'tout passe' if not ko else f'{ko} échec(s)'}")
sys.exit(1 if ko else 0)
