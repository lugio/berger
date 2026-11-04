#!/usr/bin/env python3
"""Tests d'une installation NEUVE — sans modèle, sans Herdr, sans toucher à l'installation : (1) le courtier démarre et
tient sans aucun agent ; (2) berger nouveau / regenerer réussissent sans ~/.claude/skills (aucun skill utilisateur) ; (3) berger verifier-depot ne signale rien sur une installation au chemin de coffre par défaut,
mais signale toujours un chemin de coffre propre à l'installation s'il est recopié dans le code.
Usage : python3 tests/installation.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import os, secrets, shutil, subprocess, sys, tempfile
from pathlib import Path

DEPOT = Path(__file__).resolve().parent.parent
ko = 0
# Nom fictif tiré à l'exécution : écrit en clair, verifier-depot le trouverait dans ce fichier même.
PROPRIO = "essai-" + secrets.token_hex(4)


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def copie_du_produit(t):
    """Les fichiers suivis par Git (état de travail), copiés dans un dépôt jetable."""
    fichiers = subprocess.run(["git", "-C", str(DEPOT), "ls-files"], capture_output=True, text=True).stdout.split()
    for f in fichiers:
        (t / f).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(DEPOT / f, t / f)
    subprocess.run(["git", "init", "-q", str(t)]); subprocess.run(["git", "-C", str(t), "add", "-A"])


with tempfile.TemporaryDirectory() as t:
    t = Path(t); (t / "config.toml").write_text(f'proprietaire = "{PROPRIO}"\ncoffre = "{t}/coffre.json"\n'); (t / "coffre.json").write_text("{}")
    env = {**os.environ, "BERGER_DIR": str(t)}
    r = subprocess.run(["timeout", "3", str(DEPOT / "courtier/courtier")], env=env, capture_output=True, text=True)
    dire(r.returncode == 124, "courtier : démarre et tient sans dossier agents/ (installation neuve)"
         + ("" if r.returncode == 124 else f" — code {r.returncode} : {(r.stderr or '').strip().splitlines()[-1:]}"))

with tempfile.TemporaryDirectory() as t:
    # 07/10 : un [outils.moncab-dev] déclaré à la main était ÉCRASÉ en silence par l'outil de l'équipe « moncab » (même nom),
    # et le courtier tombait sur un message trompeur. Le nom en double doit être refusé au démarrage, nommé.
    t = Path(t); d = t / "depot"; d.mkdir()
    (t / "config.toml").write_text(f'proprietaire = "{PROPRIO}"\ncoffre = "{t}/coffre.json"\n'
                                   '[outils.p-dev]\ntype = "commandes"\n[outils.p-dev.lecture]\netat = "true"\n'
                                   f'[equipes.p]\ndepot = "{d}"\n'); (t / "coffre.json").write_text("{}")
    r = subprocess.run(["timeout", "5", str(DEPOT / "courtier/courtier")], env={**os.environ, "BERGER_DIR": str(t)}, capture_output=True, text=True)
    dire(r.returncode not in (0, 124) and "en double : p-dev" in r.stderr, "courtier : un nom d'outil réservé à une équipe est refusé au démarrage, nommé")

with tempfile.TemporaryDirectory() as t:
    # Installation neuve dont l'utilisateur n'a AUCUN skill : ~/.claude/skills n'existe pas (constaté le 06/10 sur une VM neuve :
    # regenerer → lier_skills plantait sur FileNotFoundError, l'agent restait à moitié créé).
    m = Path(t); i = m / "berger"; i.mkdir(); copie_du_produit(i)              # l'installation est DANS le dossier personnel (exigé)
    (i / "config.toml").write_text(f'proprietaire = "{PROPRIO}"\ncoffre = "{m}/coffre.json"\n'); (m / "coffre.json").write_text("{}")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}; t = i
    r = subprocess.run([str(t / "bin/berger"), "nouveau", "essai", "Essai"], env=env, capture_output=True, text=True)
    r2 = subprocess.run([str(t / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True)
    ok = r.returncode == 0 and r2.returncode == 0 and (t / "agents/essai/.claude/skills").is_dir()
    regles = (t / "agents/essai/AGENTS.md").read_text() if (t / "agents/essai/AGENTS.md").exists() else ""
    dire("sauvegarde vérifiée AVANT" in regles and "Pas de sauvegarde vérifiée = pas de modification" in regles,
         "regenerer : la règle « sauvegarde vérifiée avant toute modification » est dans les instructions de l'agent")
    dire(ok, "nouveau + regenerer : réussissent sans ~/.claude/skills (aucun skill utilisateur)"
         + ("" if ok else f" — codes {r.returncode}/{r2.returncode} : {((r.stderr or r2.stderr) or '').strip().splitlines()[-1:]}"))

with tempfile.TemporaryDirectory() as t:
    t = Path(t); copie_du_produit(t)
    env = {**os.environ, "HOME": str(t / "maison")}
    for config, cas in ((f'proprietaire = "{PROPRIO}"\n', "implicite"),
                        (f'proprietaire = "{PROPRIO}"\ncoffre = "~/.config/berger/coffre.json"\n', "écrit dans config.toml")):
        (t / "config.toml").write_text(config)                                       # coffre au chemin PAR DÉFAUT
        r = subprocess.run([str(t / "bin/berger"), "verifier-depot"], env=env, capture_output=True, text=True)
        dire(r.returncode == 0, f"verifier-depot : propre avec le chemin de coffre PAR DÉFAUT ({cas})" + ("" if r.returncode == 0 else " — " + " ".join(r.stdout.split())[-160:]))
    (t / "config.toml").write_text(f'proprietaire = "{PROPRIO}"\ncoffre = "~/.config/zz-maison/coffre-perso.json"\n')
    (t / "README.md").write_text((t / "README.md").read_text() + "\nvoir ~/.config/zz-maison/coffre-perso.json\n")
    subprocess.run(["git", "-C", str(t), "add", "README.md"])
    r = subprocess.run([str(t / "bin/berger"), "verifier-depot"], env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and "chemin du coffre" in r.stdout, "verifier-depot : signale toujours un chemin de coffre PROPRE à l'installation")
    # le nom du propriétaire, AUSSI à l'intérieur d'un mot (14/10 : « GO_<NOM> » dans tests/tout.sh n'était pas vu en mot entier)
    (t / "config.toml").write_text(f'proprietaire = "{PROPRIO}"\n')               # coffre par défaut : la ligne ajoutée au README n'est plus une marque
    exemple = f"\n# exemple : GO_{PROPRIO.upper()}=1\n"                  # collé à « GO_ » : l'ancien contrôle (mot entier) ne le voyait pas
    (t / "tests/tout.sh").write_text((t / "tests/tout.sh").read_text() + exemple)
    subprocess.run(["git", "-C", str(t), "add", "tests/tout.sh"])
    r = subprocess.run([str(t / "bin/berger"), "verifier-depot"], env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and "tests/tout.sh — nom du propriétaire" in r.stdout,
         "verifier-depot : nom du propriétaire trouvé À L'INTÉRIEUR d'un mot (GO_<NOM>, casse ignorée)" + ("" if r.returncode == 1 else " — " + " ".join(r.stdout.split())[-160:]))
    (t / "tests/tout.sh").write_text((t / "tests/tout.sh").read_text().replace(exemple, ""))
    subprocess.run(["git", "-C", str(t), "add", "tests/tout.sh"])
    r = subprocess.run([str(t / "bin/berger"), "verifier-depot"], env=env, capture_output=True, text=True)
    dire(r.returncode == 0, "verifier-depot : la mention retirée → dépôt propre" + ("" if r.returncode == 0 else " — " + " ".join(r.stdout.split())[-160:]))

sys.exit(1 if ko else 0)
