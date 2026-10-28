#!/usr/bin/env python3
"""Tests de l'équipe de développement (outils equipe_dev / equipe_chef) — sans modèle, sans installation : une forge,
un dépôt de chef de projet et une copie de développeur jetables. Usage : python3 tests/equipe.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util, json, os, subprocess, sys, tempfile
from pathlib import Path

OUTILS = Path(__file__).resolve().parent.parent / "courtier/outils"
ko = non_joue = 0


def charger(t):
    spec = importlib.util.spec_from_file_location(f"outil_{t}", OUTILS / f"{t}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def git(d, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True)


def refuse(f, args, mot):
    try: f(args); return False
    except (ValueError, RuntimeError, PermissionError) as e: return mot in str(e)


with tempfile.TemporaryDirectory() as t:
    t = Path(t); forge, depot, copie, agent, dem = t / "forge.git", t / "depot", t / "copie", t / "agent", t / "demandes"
    (t / "config.toml").write_text('proprietaire = "Test"\n'); os.environ["BERGER_DIR"] = str(t)   # traces (Échanges) dans le jetable
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    (depot / "verifier.sh").write_text('[ ! -f rouge ]\n'); git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
    subprocess.run(["git", "clone", "-q", str(forge), str(copie)], capture_output=True); git(copie, "switch", "-q", "-c", "equipe/demo")
    for d in (depot, copie): git(d, "config", "user.name", "t"); git(d, "config", "user.email", "t@t.invalid")   # identité de la machine
    agent.mkdir(); (agent / "agent.conf").write_text(f"projet = p\nsujet = demo\ncopie = {copie}\nbranche = equipe/demo\nport = 0\n")
    dev = charger("equipe_dev").Outil({"principale": "main", "demandes": str(dem), "verify": "sh verifier.sh", "pret": "true"}, None, None)
    dev.contexte = {"agent": "p-demo", "dossier": str(agent)}
    chef = charger("equipe_chef").Outil({"depot": str(depot), "principale": "main", "demandes": str(dem), "valide_par": "coord",
                                         "pret": "true", "travail": str(t / "integration")}, None, None)
    fusion = lambda: dev.verbes["demander-fusion"](["livré : fichier a, tests joués"])

    dire(refuse(lambda a: fusion(), [], "aucun commit"), "demande refusée : aucun commit")
    (copie / "a").write_text("a"); dire(refuse(lambda a: fusion(), [], "non commités"), "demande refusée : changements non commités")
    git(copie, "add", "a"); git(copie, "commit", "-qm", "feat: a")
    dire(refuse(lambda a: fusion(), [], "pas poussée"), "demande refusée : branche pas poussée")
    dire(dev.verbes["pousser"]([])["code"] == 0, "pousser : SA branche part sur la forge")
    (copie / "rouge").write_text("x"); git(copie, "add", "rouge"); git(copie, "commit", "-qm", "casse"); dev.verbes["pousser"]([])
    dire(refuse(lambda a: fusion(), [], "verify : rouge"), "demande refusée : tests rouges")
    git(copie, "rm", "-q", "rouge"); git(copie, "commit", "-qm", "répare"); dev.verbes["pousser"]([])
    (depot / "b").write_text("b"); git(depot, "add", "b"); git(depot, "commit", "-qm", "main avance"); git(depot, "push", "-q", "origin", "main")
    dire(refuse(lambda a: fusion(), [], "pas à jour"), "demande refusée : branche pas à jour avec main")
    dire(dev.verbes["mettre-a-jour"]([])["code"] == 0, "mettre-a-jour : main intégrée dans la branche"); dev.verbes["pousser"]([])
    r = fusion(); dire("demande" in r and (dem / "demo.json").is_file(), "demande acceptée : propre, poussée, à jour, tests verts")
    dire(chef.verbes["demandes"]([])[0]["etat"] == "à relire", "chef de projet : la demande est « à relire »")
    dire("feat: a" in chef.verbes["relire"](["demo"])["commits"], "chef de projet : relire montre les commits")
    dire(chef.valide_par == "coord", "fusion validée par le coordinateur (valide_par)")
    apercu, fusionner = chef.ecritures["fusionner"]
    dire("equipe/demo" in apercu(["demo"]), "fusion : aperçu sans rien exécuter")
    (copie / "c").write_text("c"); git(copie, "add", "c"); git(copie, "commit", "-qm", "après demande"); dev.verbes["pousser"]([])
    dire(refuse(fusionner, ["demo"], "a changé"), "fusion refusée : la branche a changé depuis la demande")
    fusion(); fusionner(["demo"])
    dire(git(forge, "log", "--oneline", "main").stdout.count("feat: a") == 1, "fusion : main de la forge contient le travail (avance rapide)")
    dire(git(forge, "branch", "--list", "equipe/demo").stdout.strip() == "", "fusion : branche du développeur supprimée sur la forge")
    dire(json.loads((dem / "demo.json").read_text())["etat"] == "fusionnée", "demande marquée « fusionnée »")
    dire(refuse(apercu, ["demo"], "fusionnée"), "une demande déjà fusionnée ne se refusionne pas")
    dire(refuse(dev.verbes["pousser"], ["main"], "aucun argument"), "pousser n'accepte aucune branche (jamais main)")
    (copie / ".git/hooks/pre-push").write_text(f"#!/bin/sh\ntouch {t}/HOOK\n"); os.chmod(copie / ".git/hooks/pre-push", 0o755)
    (copie / "d").write_text("d"); git(copie, "add", "d"); git(copie, "commit", "-qm", "d"); dev.verbes["pousser"]([])
    dire(not (t / "HOOK").exists(), "un hook piégé dans la copie n'est PAS exécuté par le courtier")
    # verify = code écrit par le développeur, lancé par le courtier : DANS un bac à sable (secret masqué, rien hors copie, pas de réseau)
    # Le piège a besoin d'un dossier HORS de /tmp (le bac à sable a son propre /tmp : un secret posé dans /tmp y serait
    # invisible sans rien prouver). Hors bac (tout.sh) : ~/.cache ou ~. Sous verify (déjà dans le bac à sable du courtier,
    # 12/10) : ~ est en lecture seule, seule la copie du développeur est inscriptible → le dossier du projet, hors de la copie
    # jetable, que le bac à sable imbriqué doit masquer et protéger comme le reste. Aucun lieu : contrôles « non joués ».
    hors = None
    for lieu in (Path.home() / ".cache", Path.home(), OUTILS.parent.parent):
        if any(lieu.resolve().is_relative_to(x) for x in (Path("/tmp").resolve(), Path(tempfile.gettempdir()).resolve())): continue
        try: hors = Path(tempfile.mkdtemp(prefix=".equipe-piege-", dir=lieu)); break
        except OSError: pass
    if hors is None:
        for texte in ("le secret masqué reste illisible", "aucune écriture hors de la copie", "pas de réseau"):
            non_joue += 1; print(f"NON JOUÉ verify piégé : {texte} (aucun dossier inscriptible hors de /tmp)")
    else:
        try:
            secret = hors / "coffre"; secret.mkdir(); (secret / "cle").write_text("valeur-secrete-factice-du-test")
            piege = hors / "piege"
            (copie / "verifier.sh").write_text(f'cat {secret}/cle 2>/dev/null && echo FUITE-SECRET; touch {piege} 2>/dev/null && echo ECRIT-HORS-COPIE; '
                                               'curl -s -m 5 -o /dev/null https://example.com && echo RESEAU-OUVERT; echo FIN-PIEGE\n')
            dev2 = charger("equipe_dev").Outil({"principale": "main", "demandes": str(dem), "verify": "sh verifier.sh", "masques": [str(secret)]}, None, None)
            dev2.contexte = dev.contexte
            sortie = dev2.verbes["verify"]([])["sortie"]
            dire("FIN-PIEGE" in sortie and "FUITE-SECRET" not in sortie, "verify piégé : le secret masqué reste illisible")
            dire("ECRIT-HORS-COPIE" not in sortie and not piege.exists(), "verify piégé : aucune écriture hors de la copie")
            dire("RESEAU-OUVERT" not in sortie, "verify piégé : pas de réseau")
        finally:
            git(copie, "checkout", "-q", "--", "verifier.sh"); __import__("shutil").rmtree(hors)
    agent2 = t / "agent2"; agent2.mkdir(); (agent2 / "agent.conf").write_text("projet = p\n")
    dev.contexte = {"agent": "intrus", "dossier": str(agent2)}
    dire(refuse(dev.verbes["etat"], [], "réservé"), "outil développeur refusé à un agent qui n'est pas développeur")
print(f"---- {ko} échec(s)" + (f", {non_joue} non joué(s)" if non_joue else ""))
sys.exit(1 if ko else 0)
