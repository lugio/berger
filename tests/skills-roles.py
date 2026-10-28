#!/usr/bin/env python3
"""Tests des méthodes PAR RÔLE (catalogue skills/ + agent.conf `skills = …`) — sans modèle, sans Herdr, installation JETABLE.
Vérifie : un agent ne reçoit QUE les méthodes de son rôle (pour les deux moteurs), une méthode retirée de son agent.conf
disparaît au regenerer, une méthode absente du catalogue est signalée sans rien casser, une méthode qui cite le coffre ou un
motif interdit (skills.interdits) est refusée, la méthode propre de l'agent (skills-agent/) prime, rien d'autre qu'un lien
n'est supprimé, et la fiche + le Catalogue le montrent.
Usage : python3 tests/skills-roles.py (0 = tout passe)"""
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


def liens(i, a, sous=".claude/skills"):
    d = i / "agents" / a / sous
    return sorted(p.name for p in d.iterdir() if p.is_symlink()) if d.is_dir() else []


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n\n'
                                   '[skills]\ninterdits = ["MOT_INTERDIT_[0-9]+"]\n')
    cat = i / "skills"
    for n in ("pare-feu", "wiki", "courrier"): methode(cat, n)
    methode(cat, "fuite-coffre", "les identifiants sont dans coffre-essai.json")
    methode(cat, "fuite-motif", "voir MOT_INTERDIT_42")
    (cat / "image-seule").mkdir(); (cat / "image-seule/SKILL.md").write_text("ok\n"); (cat / "image-seule/a.bin").write_bytes(b"\xff\xfe\x00MOT_INTERDIT_7")
    for a, nom, skills in (("vigie", "Vigie", "wiki, courrier"), ("intendant", "Intendant", "pare-feu, wiki, inconnue"),
                           ("sans", "Sans", ""), ("garde", "Garde", "fuite-coffre, fuite-motif, image-seule, pare-feu")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {nom}\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\nskills = {skills}\n")
    methode(i / "agents/vigie/skills-agent", "wiki", "la version de Vigie")             # méthode propre : prime sur le catalogue
    (i / "agents/vigie/.claude/skills").mkdir(parents=True); (i / "agents/vigie/.claude/skills/notes.txt").write_text("à garder")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    berger = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=120)

    r = berger("regenerer"); sortie = r.stdout + r.stderr
    dire(r.returncode == 0, "regenerer réussit avec un catalogue" + ("" if r.returncode == 0 else f" — {sortie.strip()[-200:]}"))
    dire(liens(i, "intendant") == ["pare-feu", "wiki"], f"Intendant : seulement les méthodes de son rôle ({liens(i, 'intendant')})")
    dire(liens(i, "intendant", ".agents/skills") == ["pare-feu", "wiki"], "même chose pour l'autre moteur (.agents/skills)")
    dire(liens(i, "sans") == [], "agent sans `skills =` : aucune méthode du catalogue")
    dire("« inconnue » absente du catalogue" in sortie, "méthode absente du catalogue : signalée, nommée")
    g = liens(i, "garde")
    dire("fuite-coffre" not in g and "fuite-motif" not in g and "image-seule" not in g and "pare-feu" in g,
         f"méthode qui cite le coffre ou un motif interdit (même dans un binaire) : refusée, les autres données ({g})")
    dire("fuite-coffre" in sortie and "refusée" in sortie and "coffre-essai.json" in sortie, "refus nommé avec son motif")
    w = i / "agents/vigie/.claude/skills/wiki"
    dire(w.is_symlink() and w.resolve() == (i / "agents/vigie/skills-agent/wiki").resolve(), "la méthode propre de l'agent prime sur celle du catalogue")
    dire((i / "agents/vigie/.claude/skills/notes.txt").read_text() == "à garder", "un fichier qui n'est pas un lien n'est jamais supprimé")

    conf = i / "agents/intendant/agent.conf"; conf.write_text(conf.read_text().replace("pare-feu, wiki, inconnue", "wiki"))
    berger("regenerer")
    dire(liens(i, "intendant") == ["wiki"], "méthode retirée de agent.conf : son lien disparaît au regenerer")

    code = (f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
            "print('\\n'.join(g['VUES']['catalogue'].vue_catalogue(160, 400)));print('\\n'.join(g['fiche_capacites']('intendant', 160, 60)))")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    vue = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", r.stdout)
    dire(r.returncode == 0 and "catalogue des rôles" in vue and "Vigie : wiki, courrier" in vue,
         "Catalogue : les méthodes du catalogue et qui les reçoit" + ("" if r.returncode == 0 else f" — {r.stderr.strip()[-200:]}"))
    dire("fuite-motif" in vue and "données à personne" not in vue.split("catalogue des rôles")[0], "Catalogue : liste aussi les méthodes refusées (à corriger)")
    dire("1 de son rôle" in vue and ": wiki" in vue, "fiche de l'agent : ses méthodes de rôle comptées et nommées")

with tempfile.TemporaryDirectory() as t:
    # 08/10 : ~/.claude/skills était lié chez TOUS les agents (101 skills chez un agent strict), alors que le README disait
    # « Claude le charge » — faux sous --setting-sources project,local. `[skills] partager_utilisateur = false` l'arrête.
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}")
    methode(m / ".claude/skills", "perso-utilisateur"); methode(i / "skills", "wiki")
    d = i / "agents/vigie"; (d / "memory").mkdir(parents=True)
    (d / "agent.conf").write_text("nom = Vigie\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\nskills = wiki\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    for option, attendu, cas in (("", ["perso-utilisateur", "wiki"], "sans option : ~/.claude/skills partagé (comme avant)"),
                                 ("partager_utilisateur = false\n", ["wiki"], "partager_utilisateur = false : SEULEMENT son rôle")):
        (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n\n[skills]\n{option}')
        r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
        dire(r.returncode == 0 and liens(i, "vigie") == attendu, f"{cas} ({liens(i, 'vigie')})")
    dire(liens(i, "vigie", ".agents/skills") == ["wiki"], "même chose pour l'autre moteur (.agents/skills)")

sys.exit(1 if ko else 0)
