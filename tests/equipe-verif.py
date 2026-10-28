#!/usr/bin/env python3
"""Tests de l'équipe : porte de tests par un OUTIL du courtier (verify_outil) et conflits vus par le chef de projet
(avec la branche principale, entre demandes). Sans modèle ni installation : forge, dépôt du chef et deux copies
jetables. Usage : python3 tests/equipe-verif.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util, json, os, subprocess, sys, tempfile
from pathlib import Path

OUTILS = Path(__file__).resolve().parent.parent / "courtier/outils"
ko = 0


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
    t = Path(t); forge, depot, dem = t / "forge.git", t / "depot", t / "demandes"
    (t / "config.toml").write_text('proprietaire = "Test"\n'); os.environ["BERGER_DIR"] = str(t)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    (depot / "doc.md").write_text("ligne 1\nligne 2\nligne 3\n"); (depot / "autre.md").write_text("autre\n")
    git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")

    appels = []
    def faux_controle(args):                     # le verbe de lecture d'un outil distant : rend {code, sortie}
        appels.append(args); return {"code": 1 if (t / "ROUGE").exists() else 0, "sortie": "contrôles : " + " ".join(args)}

    def developpeur(sujet):
        copie, agent = t / f"copie-{sujet}", t / f"agent-{sujet}"
        subprocess.run(["git", "clone", "-q", str(forge), str(copie)], capture_output=True); git(copie, "switch", "-q", "-c", f"equipe/{sujet}")
        git(copie, "config", "user.name", "t"); git(copie, "config", "user.email", "t@t.invalid")
        agent.mkdir(); (agent / "agent.conf").write_text(f"projet = p\nsujet = {sujet}\ncopie = {copie}\nbranche = equipe/{sujet}\nport = 0\n")
        d = charger("equipe_dev").Outil({"principale": "main", "demandes": str(dem), "verify_outil": "distant controler", "pret": "true"}, None, None)
        d.portes_par = {"verify": faux_controle}; d.contexte = {"agent": f"p-{sujet}", "dossier": str(agent)}
        return d, copie

    def livrer(d, copie, fichier, texte, message):
        (copie / fichier).write_text(texte); git(copie, "add", fichier); git(copie, "commit", "-qm", message); d.verbes["pousser"]([])

    # ── porte de tests par un outil du courtier ──
    a, ca = developpeur("liens")
    dire("verify" in a.verbes, "verify_outil : le développeur a un verbe verify")
    livrer(a, ca, "doc.md", "ligne 1 corrigée\nligne 2\nligne 3\n", "docs: ligne 1")
    dire(a.verbes["verify"]([])["code"] == 0 and appels[-1] == ["equipe/liens"], "verify : l'outil reçoit SA branche (jamais un argument de l'agent)")
    dire(refuse(a.verbes["verify"], ["main"], "aucun argument"), "verify n'accepte aucun argument (impossible de viser main)")
    (t / "ROUGE").write_text("x")
    dire(refuse(lambda x: a.verbes["demander-fusion"](["livré : ligne 1 corrigée, verify joué"]), [], "verify : rouge"), "demande refusée : verify distant rouge")
    (t / "ROUGE").unlink()
    r = a.verbes["demander-fusion"](["livré : ligne 1 corrigée, verify joué"])
    dire("demande" in r and json.loads((dem / "liens.json").read_text())["portes"]["verify"]["etat"] == "vert", "demande acceptée : verify distant au vert")
    a.portes_par = {}
    dire(refuse(a.verbes["verify"], [], "indisponible"), "verify_outil non branché : refus net, jamais « au vert » par défaut")
    a.portes_par = {"verify": faux_controle}

    # ── deux développeurs en parallèle, fichiers différents : aucun conflit ──
    b, cb = developpeur("autre")
    livrer(b, cb, "autre.md", "autre corrigé\n", "docs: autre"); b.verbes["demander-fusion"](["livré : autre.md corrigé, verify joué"])
    chef = charger("equipe_chef").Outil({"depot": str(depot), "principale": "main", "demandes": str(dem), "valide_par": None,
                                         "pret": "true", "travail": str(t / "integration")}, None, None)
    dire(chef.verbes["relire"](["autre"])["conflits"] == "aucun", "relire : deux fichiers différents → aucun conflit")
    dire(chef.verbes["relire"](["liens"])["conflits"] == "aucun", "relire : la première demande non plus")

    # ── un troisième sur la MÊME ligne : conflit vu, demande renvoyée proprement ──
    c, cc = developpeur("concurrent")
    livrer(c, cc, "doc.md", "ligne 1 autrement\nligne 2\nligne 3\n", "docs: ligne 1 autrement"); c.verbes["demander-fusion"](["livré : ligne 1 reformulée, verify joué"])
    conf = chef.verbes["relire"](["concurrent"])["conflits"]
    dire(isinstance(conf, dict) and conf.get("avec la demande liens") == ["doc.md"], f"relire : conflit avec la demande « liens » sur doc.md ({conf})")
    dire("avec main" not in conf, "relire : pas de conflit avec main (main n'a pas bougé)")
    r = chef.verbes["renvoyer"](["concurrent", "conflit avec la demande liens sur doc.md : attends sa fusion puis mets-toi à jour"])
    dire(json.loads((dem / "concurrent.json").read_text())["etat"] == "renvoyée", "le chef renvoie la demande en conflit (état « renvoyée »)")

    # ── main avance (la 1re demande fusionnée) : la concurrente est REFUSÉE à la fusion ──
    apercu, fusionner = chef.ecritures["fusionner"]
    fusionner(["liens"])
    d = json.loads((dem / "concurrent.json").read_text()); d["etat"] = "à relire"; (dem / "concurrent.json").write_text(json.dumps(d))
    dire(refuse(apercu, ["concurrent"], "en conflit avec main"), "fusion refusée : la demande est en conflit avec main (rien n'est poussé)")
    dire(git(forge, "log", "--oneline", "main").stdout.count("autrement") == 0, "main de la forge n'a pas reçu la ligne concurrente")
    dire("doc.md" in str(chef.verbes["relire"](["concurrent"])["conflits"].get("avec main")), "relire : conflit désormais AVEC main, nommé")
    dire("autre" in apercu(["autre"]), "la demande sans conflit reste fusionnable")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
