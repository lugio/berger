#!/usr/bin/env python3
"""Tests de la branche de finition du chef de projet et de l'en-tête de journal avec un titre
(docs/plans/2026-10-13-chef-finition-spec.md) : le chef pousse SA branche et demande la fusion par le même chemin qu'un
développeur (portes, demande au bon agent, relecture), la fusion reste au propriétaire seul ; refus (branche principale,
hors préfixe, arguments piégés, force, appelant autre que le chef) ; hook piégé jamais exécuté ; entree_journal.
Sans modèle ni installation : forge, dépôt du chef et copie de développeur jetables.
Usage : python3 tests/chef-finition.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util, json, os, subprocess, tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent; OUTILS = RACINE / "courtier/outils"
ko = 0


def charger(t):
    spec = importlib.util.spec_from_file_location(f"outil_{t}", OUTILS / f"{t}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def git(d, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True)


def erreur(f, args):
    try: f(args); return ""
    except (ValueError, RuntimeError, PermissionError) as e: return f"{type(e).__name__}: {e}"


PORTE = 'if [ -f "ROUGE-$1" ]; then echo "ÉCHEC $1"; exit 1; fi\necho "ok $1 : 3 contrôles"\n'
TOUTES = {"verify": "sh porte.sh verify", "tests": "sh porte.sh tests", "pret": "sh porte.sh pret"}

with tempfile.TemporaryDirectory() as t:
    t = Path(t); forge, depot, dem = t / "forge.git", t / "depot", t / "demandes"
    (t / "config.toml").write_text('proprietaire = "Test"\n'); os.environ["BERGER_DIR"] = str(t)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    git(depot, "config", "user.name", "t"); git(depot, "config", "user.email", "t@t.invalid")
    (depot / "porte.sh").write_text(PORTE); git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
    forge_main = lambda: git(forge, "rev-parse", "main").stdout.strip()
    sur_forge = lambda b: git(forge, "rev-parse", "--verify", "--quiet", f"refs/heads/{b}").stdout.strip()

    chef = charger("equipe_chef").Outil({"depot": str(depot), "principale": "main", "demandes": str(dem), "valide_par": "coord",
                                         "chef_projet": "chef", "prefixe": "equipe/", "travail": str(t / "portes"), **TOUTES}, None, None)
    pousser, demander = chef.verbes["pousser"], chef.verbes["demander-fusion"]

    # la branche de finition du chef, dans SON dépôt ; le dépôt revient sur main (la fusion l'exige)
    git(depot, "switch", "-q", "-c", "equipe/fin"); (depot / "fin.txt").write_text("finition\n"); git(depot, "add", "fin.txt")
    git(depot, "commit", "-qm", "feat: finition du sujet"); git(depot, "switch", "-q", "main")

    # ── un développeur ne peut pas s'en servir ──
    agent = t / "agent-dev"; agent.mkdir()
    (agent / "agent.conf").write_text(f"projet = p\nsujet = autre\ncopie = {depot}\nbranche = equipe/autre\nport = 0\n")
    dev = charger("equipe_dev").Outil({"principale": "main", "demandes": str(dem), **TOUTES}, None, None)
    dev.contexte = {"agent": "p-autre", "dossier": str(agent)}
    dire("aucun argument" in erreur(dev.verbes["pousser"], ["equipe/fin"]), "développeur : son « pousser » ne vise jamais une autre branche (aucun argument)")
    chef.contexte = {"agent": "p-autre", "dossier": str(agent)}
    dire(all(erreur(f, a).startswith("PermissionError") for f, a in ((pousser, ["equipe/fin"]), (demander, ["equipe/fin", "livré : la finition"]))),
         "outil du chef appelé par un développeur : pousser et demander-fusion refusés")
    chef.contexte = {}
    dire(erreur(pousser, ["equipe/fin"]).startswith("PermissionError") and not sur_forge("equipe/fin"), "appelant inconnu : refusé, rien poussé")
    chef.contexte = {"agent": "chef", "dossier": str(t)}

    # ── refus : branche principale, hors préfixe, arguments piégés, force ──
    for a, quoi in ((["main"], "branche principale"), (["autre/fin"], "hors du préfixe"), (["equipe/../main"], "« .. »"),
                    (["equipe/-x"], "tiret initial"), (["-x"], "option"), (["equipe/a b"], "espace"), (["equipe/"], "nom vide"),
                    (["--force"], "--force"), (["+equipe/fin"], "« + » (force)"), (["equipe/fin", "--force"], "argument en plus (--force)"),
                    (["equipe/fin:main"], "refspec vers main"), (["equipe/absente"], "branche absente du dépôt")):
        e = erreur(pousser, a)
        dire(e.startswith("ValueError") and forge_main() == git(depot, "rev-parse", "main").stdout.strip() and not sur_forge("equipe/fin"),
             f"pousser refusé : {quoi}")
    dire(erreur(demander, ["main", "livré : la finition du sujet"]).startswith("ValueError"), "demander-fusion refusé : branche principale")

    # ── hook piégé (dans .git/hooks et par core.hooksPath) : jamais exécuté ──
    piege = t / "piege"
    for d in (depot / ".git/hooks", t / "crochets"):
        d.mkdir(exist_ok=True); (d / "pre-push").write_text(f"#!/bin/sh\ntouch {piege}\n"); (d / "pre-push").chmod(0o755)
    dire("pas poussée" in erreur(demander, ["equipe/fin", "livré : la finition du sujet"]), "demande avant le push : refusée (pas poussée)")
    r = pousser(["equipe/fin"])
    dire(sur_forge("equipe/fin") == git(depot, "rev-parse", "equipe/fin").stdout.strip() and r["poussée"] == "equipe/fin", "pousser : SA branche de finition est sur la forge")
    dire(not piege.exists(), "hook pre-push piégé dans .git/hooks : jamais exécuté")
    git(depot, "config", "core.hooksPath", str(t / "crochets"))
    git(depot, "switch", "-q", "equipe/fin"); (depot / "fin2.txt").write_text("suite\n"); git(depot, "add", "fin2.txt")
    git(depot, "commit", "-qm", "feat: suite de la finition"); git(depot, "switch", "-q", "main"); pousser(["equipe/fin"])
    dire(not piege.exists() and sur_forge("equipe/fin") == git(depot, "rev-parse", "equipe/fin").stdout.strip(),
         "hook pre-push piégé par core.hooksPath : jamais exécuté (le push, lui, est passé)")
    ordinaire = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG_")}   # la porte du courtier désactive les hooks pour tout git
    for a in (["main:refs/heads/temoin"], ["--delete", "temoin"]):
        subprocess.run(["git", "-C", str(depot), "push", "-q", "origin", *a], capture_output=True, env=ordinaire)
    dire(piege.exists(), "témoin : le même piège se déclenche avec un git ordinaire (le contrôle ci-dessus prouve quelque chose)")
    piege.unlink(missing_ok=True); git(depot, "config", "--unset", "core.hooksPath")

    # ── jamais de force : un historique réécrit est refusé ──
    pousse = sur_forge("equipe/fin")
    git(depot, "switch", "-q", "equipe/fin"); git(depot, "commit", "-q", "--amend", "-m", "feat: finition réécrite")
    e = erreur(pousser, ["equipe/fin"])
    dire(e.startswith("RuntimeError") and sur_forge("equipe/fin") == pousse, "historique réécrit : push refusé, la forge garde le commit poussé")
    git(depot, "reset", "-q", "--hard", pousse)

    # ── demande : mêmes contrôles qu'un développeur ──
    (depot / "fin.txt").write_text("pas commité\n")
    dire("non commités" in erreur(demander, ["equipe/fin", "livré : la finition du sujet"]), "branche extraite avec des changements non commités : refusée")
    git(depot, "checkout", "-q", "--", "fin.txt"); git(depot, "switch", "-q", "main")
    dire("résumé" in erreur(demander, ["equipe/fin", "court"]), "résumé illisible : refusé")
    dem.mkdir(); (dem / "fin.json").write_text(json.dumps({"sujet": "fin", "branche": "equipe/fin-autre", "etat": "à relire"}))
    dire("déjà" in erreur(demander, ["equipe/fin", "livré : la finition du sujet"]), "sujet déjà pris par la demande d'une autre branche : refusé")
    (dem / "fin.json").unlink()

    r = demander(["equipe/fin", "livré : la finition du sujet, portes jouées"])
    d = json.loads((dem / "fin.json").read_text())
    dire([x["sujet"] for x in chef.verbes["demandes"]([])] == ["fin"] and d["agent"] == "chef" and d["branche"] == "equipe/fin" and d["finition"] is True,
         "demande inscrite : visible dans « demandes », au nom de l'agent appelant (le chef), marquée finition")
    dire(d["commit"] == sur_forge("equipe/fin") and all(d["portes"][p]["etat"] == "vert" for p in ("verify", "tests", "pret")) and d["portes"]["gate"] == {"etat": "non mesuré"},
         "portes jouées sur le commit poussé (copie jetable) : vertes, gate « non mesuré »")
    dire(not list((t / "portes").glob("*")), "copie jetable des portes effacée")
    dire(chef.verbes["rejouer"](["fin"])["recompte"] == "conforme à l'annonce", "relecture : rejouer est conforme à l'annonce")

    # ── la fusion reste au propriétaire seul ──
    dire("fusionner" not in chef.verbes and "fusionner" in chef.ecritures, "fusionner n'est qu'une écriture (soumise à validation)")
    dire(chef.valideur("fusionner", ["fin"]) is None, "fusion d'une finition du chef : validée par le propriétaire seul (aucun agent valideur)")
    (dem / "dev.json").write_text(json.dumps({"sujet": "dev", "branche": "equipe/dev", "agent": "p-dev", "etat": "à relire"}))
    (dem / "coord.json").write_text(json.dumps({"sujet": "coord", "branche": "equipe/coord", "agent": "coord", "etat": "à relire"}))
    dire(chef.valideur("fusionner", ["dev"]) == "coord" and chef.valideur("fusionner", ["coord"]) is None,
         "demande d'un développeur : le coordinateur ; demande écrite par le valideur lui-même : le propriétaire")
    (dem / "dev.json").unlink(); (dem / "coord.json").unlink()
    chef.ecritures["fusionner"][1](["fin"])                           # ce que le courtier lance une fois la validation donnée
    dire(git(forge, "cat-file", "-e", "main:fin.txt").returncode == 0 and json.loads((dem / "fin.json").read_text())["etat"] == "fusionnée"
         and not sur_forge("equipe/fin"), "validée : avance rapide dans main, demande fusionnée, branche effacée de la forge")

    # ── branche rouge : pas de demande ──
    git(depot, "switch", "-q", "-c", "equipe/rouge"); (depot / "ROUGE-tests").write_text("x"); git(depot, "add", "-A")
    git(depot, "commit", "-qm", "feat: casse les tests"); git(depot, "switch", "-q", "main"); pousser(["equipe/rouge"])
    e = erreur(demander, ["equipe/rouge", "livré : un sujet aux tests rouges"])
    dire("tests : rouge" in e and not (dem / "rouge.json").exists(), "porte rouge : pas de demande (comme pour un développeur)")

# ── entree_journal : un titre après la date (MonCab), rien d'autre ──
ej = charger("_portes").entree_journal
J = ("# Journal\n\n## [3.480.20] - 2026-10-06\n- voisine\n\n## [3.480.2] - 2026-10-05 — *Guichet plus rapide*\n- détail\n\n"
     "## [3.480.1] - 2026-10-01\n- seul\n\nx ## [3.480.0] - 2026-09-30\n- texte avant\n\n## [3.479.9] - 2026-13-45\n- date invalide\n\n"
     "## [3.479.8] - 2026-10-05x\n- date collée\n")
dire((ej(J, "3.480.1") or "").startswith("## [3.480.1] - 2026-10-01\n- seul"), "en-tête seul : accepté")
dire((ej(J, "3.480.2") or "").startswith("## [3.480.2] - 2026-10-05 — *Guichet plus rapide*\n- détail") and "voisine" not in ej(J, "3.480.2"),
     "en-tête + « — *Titre* » : accepté, et la version voisine (3.480.20) n'est pas prise")
dire(ej(J, "3.480.0") is None, "texte avant « ## » : refusé")
dire(ej(J, "3.479.9") is None and ej(J, "3.479.8") is None, "date invalide (2026-13-45) ou collée à un texte : refusée")
dire(ej(J, "3.480") is None and ej("## [3.480.20] - 2026-10-06\n- x\n", "3.480.2") is None, "version voisine seule : jamais prise pour la version demandée")

raise SystemExit(ko)
