#!/usr/bin/env python3
"""Tests de l'ORDRE des méthodes (14/10/2026) : skills-agent/ de l'agent > méthode du PRODUIT (commun/skills/<nom>) >
catalogue de l'installation (skills.dossier). Sans modèle, sans Herdr, installation JETABLE.
Vécu le 14/10 : une copie `berger` du 08/10 au catalogue masquait commun/skills/berger chez tout agent `skills = berger`.
Vérifie : le produit prime (deux moteurs) et l'homonyme ignoré est signalé (agent, nom, chemin) ; une méthode seulement au
catalogue en vient toujours ; skills-agent/ prime sur les deux ; fiche Capacités et vue Catalogue suivent le même ordre
(une méthode du produit n'y est plus « absente »).
Usage : python3 tests/skill-produit.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import os, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def methode(dossier, nom, texte="méthode d'essai"):
    (dossier / nom).mkdir(parents=True, exist_ok=True); (dossier / nom / "SKILL.md").write_text(f"---\nname: {nom}\n---\n{texte}\n")


def cible(i, a, nom, sous=".claude/skills"):
    p = i / "agents" / a / sous / nom
    return p.resolve() if p.is_symlink() else None


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    produit = (i / "commun/skills/berger").resolve()
    dire((produit / "SKILL.md").is_file(), "le produit porte sa méthode commun/skills/berger")
    cat = i / "skills"
    methode(cat, "berger", "copie ancienne du 08/10, différente du produit")                # l'homonyme qui masquait
    methode(cat, "wiki")                                                                    # seulement au catalogue
    for a, nom in (("vigie", "Vigie"), ("propre", "Propre")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {nom}\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\nskills = berger, wiki\n")
    methode(i / "agents/propre/skills-agent", "berger", "la version de l'agent")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}

    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    sortie = r.stdout + r.stderr
    dire(r.returncode == 0, "regenerer réussit" + ("" if r.returncode == 0 else f" — {sortie.strip()[-200:]}"))
    for sous in (".claude/skills", ".agents/skills"):
        dire(cible(i, "vigie", "berger", sous) == produit,
             f"{sous} : berger pointe vers commun/skills/berger, pas vers l'homonyme du catalogue ({cible(i, 'vigie', 'berger', sous)})")
        dire(cible(i, "vigie", "wiki", sous) == (cat / "wiki").resolve(), f"{sous} : une méthode seulement au catalogue en vient toujours")
        dire(cible(i, "propre", "berger", sous) == (i / "agents/propre/skills-agent/berger").resolve(),
             f"{sous} : skills-agent/ de l'agent prime sur le produit et le catalogue")
    alerte = [l for l in sortie.splitlines() if l.startswith("⚠") and "« berger »" in l and "ignoré" in l]
    dire(any("vigie" in l and str(cat / "berger") in l and "commun/skills/berger" in l for l in alerte),
         f"regenerer signale l'homonyme ignoré : agent, nom, chemin du catalogue ({alerte[:1]})")
    dire(not any("propre" in l for l in alerte), "pas d'alerte pour l'agent dont la méthode à soi prime de toute façon")
    dire(not any("« wiki »" in l for l in sortie.splitlines() if l.startswith("⚠")), "aucune alerte pour une méthode seulement au catalogue")

    code = (f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
            "print('\\n'.join(g['VUES']['catalogue'].vue_catalogue(160, 400)));print('\\n'.join(g['fiche_capacites']('vigie', 160, 60)))")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    vue = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", r.stdout)
    dire(r.returncode == 0 and "Vigie : berger, wiki" in vue and "berger (absente)" not in vue,
         "Catalogue : la méthode du produit est donnée, jamais « absente »" + ("" if r.returncode == 0 else f" — {r.stderr.strip()[-200:]}"))
    dire("2 de son rôle" in vue and ": berger, wiki" in vue, "fiche Capacités : berger (produit) et wiki (catalogue) comptés « de son rôle »")

    # Sans homonyme (cas d'une installation propre) : la méthode vient du produit, sans alerte, et n'est pas « absente »
    for f in (cat / "berger").iterdir(): f.unlink()
    (cat / "berger").rmdir()
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(cible(i, "vigie", "berger") == produit and "ignoré" not in r.stdout + r.stderr,
         "méthode seulement au produit : liée depuis commun/skills, aucune alerte")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    vue = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", r.stdout)
    dire(r.returncode == 0 and "Vigie : berger, wiki" in vue and "absente" not in vue,
         "Catalogue : une méthode seulement au produit n'est pas « absente » (elle l'était : la vue ne lisait que le catalogue)")

sys.exit(1 if ko else 0)
