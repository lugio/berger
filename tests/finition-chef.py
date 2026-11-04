#!/usr/bin/env python3
"""Tests de la finition par le chef de projet (`finition = "chef"` de [equipes.<projet>], spec
docs/plans/2026-10-13-hierarchie-equipe-spec.md › Finition par le chef) : le développeur LIVRE sa branche sans porte pret
(demande « à finir »), une porte rouge le refuse toujours ; « à finir » ne se fusionne pas ; le chef reprend la branche et
sa demande de finition remplace la livraison SEULEMENT si sa branche contient le commit livré (trace « origine » gardée) ;
`finition = "developpeur"` (défaut) : pret exigée comme avant. Sans modèle ni installation : forge, dépôt du chef et copies jetables.
Usage : python3 tests/finition-chef.py (0 = tout passe)"""
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


# porte rouge si le fichier ROUGE-<porte> est dans le commit ; « pret » exige en plus le fichier VERSION (la finition)
PORTE = ('if [ -f "ROUGE-$1" ]; then echo "ÉCHEC $1"; exit 1; fi\n'
         'if [ "$1" = pret ] && [ ! -f VERSION ]; then echo "ÉCHEC pret : pas de VERSION"; exit 1; fi\necho "ok $1 : 3 contrôles"\n')
TOUTES = {"verify": "sh porte.sh verify", "tests": "sh porte.sh tests", "pret": "sh porte.sh pret"}

with tempfile.TemporaryDirectory() as t:
    t = Path(t); forge, depot, dem = t / "forge.git", t / "depot", t / "demandes"
    (t / "config.toml").write_text('proprietaire = "Test"\n'); os.environ["BERGER_DIR"] = str(t)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    git(depot, "config", "user.name", "t"); git(depot, "config", "user.email", "t@t.invalid")
    (depot / "porte.sh").write_text(PORTE); git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
    demande = lambda s: json.loads((dem / f"{s}.json").read_text())

    def developpeur(sujet, finition):
        copie, agent = t / f"copie-{sujet}", t / f"agent-{sujet}"
        subprocess.run(["git", "clone", "-q", str(forge), str(copie)], capture_output=True); git(copie, "switch", "-q", "-c", f"equipe/{sujet}")
        git(copie, "config", "user.name", "t"); git(copie, "config", "user.email", "t@t.invalid")
        agent.mkdir(); (agent / "agent.conf").write_text(f"projet = p\nsujet = {sujet}\ncopie = {copie}\nbranche = equipe/{sujet}\nport = 0\n")
        d = charger("equipe_dev").Outil({"principale": "main", "demandes": str(dem), "finition": finition, **TOUTES}, None, None)
        d.contexte = {"agent": f"p-{sujet}", "dossier": str(agent)}
        return d, copie

    def livrer(d, copie, fichiers, message):
        for f, texte in fichiers.items(): (copie / f).write_text(texte); git(copie, "add", f)
        git(copie, "commit", "-qm", message); return d.verbes["pousser"]([])

    dire("finition" in erreur(lambda _: charger("equipe_dev").Outil({"principale": "main", "demandes": str(dem), "finition": "chief", **TOUTES}, None, None), []),
         "finition inconnue (faute de frappe) : refusée au chargement, jamais prise pour un défaut")

    # ── finition = developpeur (défaut) : pret exigée comme avant ──
    a, ca = developpeur("classique", "developpeur"); livrer(a, ca, {"a.txt": "a\n"}, "feat: a")
    e = erreur(a.verbes["demander-fusion"], ["livré : fichier a, portes jouées"])
    dire("pret : rouge" in e and not (dem / "classique.json").exists(), "finition = developpeur : pret jouée et rouge (pas de VERSION) → pas de demande")

    # ── finition = chef : livraison sans pret, « à finir » ──
    b, cb = developpeur("livre", "chef"); livrer(b, cb, {"ROUGE-tests": "x\n"}, "feat: casse les tests")
    e = erreur(b.verbes["demander-fusion"], ["livré : sujet aux tests rouges"])
    dire("tests : rouge" in e and not (dem / "livre.json").exists(), "finition = chef : tests rouges → refus, rien de livré")
    git(cb, "rm", "-q", "ROUGE-tests"); livrer(b, cb, {"b.txt": "b\n"}, "feat: b")
    r = b.verbes["demander-fusion"](["livré : fichier b, verify et tests joués"]); d = demande("livre")
    dire(d["etat"] == "à finir" and d["portes"]["pret"] == {"etat": "non mesuré"} and all(d["portes"][p]["etat"] == "vert" for p in ("verify", "tests")),
         "finition = chef : pret ni exigée ni jouée (rouge ignorée), verify et tests verts, demande « à finir »")
    dire("livrée" in r.get("livraison", ""), "le développeur apprend que sa branche est livrée au chef")
    livre = d["commit"]

    chef = charger("equipe_chef").Outil({"depot": str(depot), "principale": "main", "demandes": str(dem), "valide_par": "coord",
                                         "chef_projet": "chef", "prefixe": "equipe/", "travail": str(t / "portes"), **TOUTES}, None, None)
    chef.contexte = {"agent": "chef", "dossier": str(t)}
    dire("à finir" in erreur(chef.ecritures["fusionner"][0], ["livre"]), "une demande « à finir » ne se fusionne pas (pret jamais jouée)")
    dire(any(x["sujet"] == "livre" and x["etat"] == "à finir" for x in chef.verbes["demandes"]([])), "le chef voit la livraison dans « demandes »")

    # ── le chef reprend : branche de finition SANS le commit livré → refus ; AVEC → remplace, trace gardée ──
    git(depot, "fetch", "-q", "origin")
    git(depot, "switch", "-q", "-c", "equipe/livre-sans", "origin/main"); (depot / "VERSION").write_text("1.0.0\n"); git(depot, "add", "-A")
    git(depot, "commit", "-qm", "chore: version sans le travail livré"); git(depot, "switch", "-q", "main")
    chef.verbes["pousser"](["equipe/livre-sans"])
    (dem / "livre-sans.json").write_text(json.dumps({**d, "sujet": "livre-sans"}))       # même livraison, sujet de cette branche
    e = erreur(chef.verbes["demander-fusion"], ["equipe/livre-sans", "finition : version du sujet livré"])
    dire("déjà" in e and "commit livré" in e and demande("livre-sans")["etat"] == "à finir",
         "branche du chef qui ne CONTIENT PAS le commit livré : refus, la livraison reste « à finir »")
    (dem / "livre-sans.json").unlink()

    git(depot, "switch", "-q", "-c", "equipe/livre-fin", livre); (depot / "VERSION").write_text("1.0.0\n"); git(depot, "add", "-A")
    git(depot, "commit", "-qm", "chore: finition (version)"); git(depot, "switch", "-q", "main"); chef.verbes["pousser"](["equipe/livre-fin"])
    (dem / "livre-fin.json").write_text(json.dumps({**d, "sujet": "livre-fin", "etat": "à relire"}))
    e = erreur(chef.verbes["demander-fusion"], ["equipe/livre-fin", "finition : version du sujet livré"])
    dire("déjà" in e, "demande existante qui n'est PAS « à finir » (à relire) : le refus actuel reste")
    (dem / "livre-fin.json").write_text(json.dumps({**d, "sujet": "livre-fin"}))
    r = chef.verbes["demander-fusion"](["equipe/livre-fin", "finition : version du sujet livré, pret jouée"]); n = demande("livre-fin")
    dire(n["branche"] == "equipe/livre-fin" and n["agent"] == "chef" and n["finition"] is True and n["etat"] == "à relire"
         and n["portes"]["pret"]["etat"] == "vert", "branche du chef contenant le commit livré : sa demande remplace « à finir », pret verte")
    dire(n.get("origine") == {"agent": "p-livre", "branche": "equipe/livre", "commit": livre, "demande": d["demande"]},
         "la demande remplacée garde la trace du développeur (origine : agent, branche, commit, date)")
    dire(chef.valideur("fusionner", ["livre-fin"]) is None, "fusion de la finition : le propriétaire seul (règle du lot chef-finition)")
    dire(any(x.get("origine") for x in chef.verbes["demandes"]([]) if x["sujet"] == "livre-fin"), "« demandes » montre l'origine au relecteur")

raise SystemExit(ko)
