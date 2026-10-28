#!/usr/bin/env python3
"""Tests du VRAI chemin de la branche de finition du chef (docs/plans/2026-10-13-chef-copie-spec.md) : le chef écrit sa
branche dans SA copie de travail (<son dossier>/travail/<projet>-fin, ou copie_chef), jamais dans le dépôt (en lecture
seule pour lui) ; le courtier l'importe en avance rapide seule, puis pousse, inscrit la demande, fusionne. Refus des
chemins (hors dossier, lien, dépôt, forge, installation) ; principale et appelant non chef refusés avant tout import ; config locale piégée de la copie jamais exécutée, avec témoins.
Sans modèle ni installation : forge, dépôt, dossier du chef et copie jetables.
Usage : python3 tests/chef-copie.py (0 = tout passe)"""
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


def git(d, *a, env=None):                    # par défaut protégé comme le courtier : le test ne déclenche pas lui-même les pièges
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True, env=env or SUR)


def erreur(f, args):
    try: f(args); return ""
    except (ValueError, RuntimeError, PermissionError) as e: return f"{type(e).__name__}: {e}"


def commit(d, fichier, texte, message):
    (d / fichier).write_text(texte); git(d, "add", fichier); git(d, "commit", "-qm", message)
    return git(d, "rev-parse", "HEAD").stdout.strip()


PORTE = 'echo "ok $1 : 3 contrôles"\n'
TOUTES = {"verify": "sh porte.sh verify", "tests": "sh porte.sh tests", "pret": "sh porte.sh pret"}
ORDINAIRE = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG_")}   # un git sans les protections du courtier
equipe_chef = charger("equipe_chef"); SUR = {**ORDINAIRE, **equipe_chef.ENV_GIT}

with tempfile.TemporaryDirectory() as t:
    t = Path(t); forge, depot, dem, inst = t / "forge.git", t / "depot", t / "demandes", t / "installation"
    chef_dir = inst / "agents/chef"; copie = chef_dir / "travail/p-fin"; chef_dir.mkdir(parents=True)   # comme en vrai : <installation>/agents/<agent>
    (t / "config.toml").write_text('proprietaire = "Test"\n'); os.environ["BERGER_DIR"] = str(t)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    (depot / "porte.sh").write_text(PORTE); git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
    forge_main = lambda: git(forge, "rev-parse", "main").stdout.strip()
    sur_forge = lambda b: git(forge, "rev-parse", "--verify", "--quiet", f"refs/heads/{b}").stdout.strip()
    au_depot = lambda b: git(depot, "rev-parse", "--verify", "--quiet", f"refs/heads/{b}").stdout.strip()

    def outil(**plus):
        o = equipe_chef.Outil({"depot": str(depot), "principale": "main", "demandes": str(dem), "valide_par": "coord", "projet": "p",
                               "chef_projet": "chef", "prefixe": "equipe/", "travail": str(t / "portes"), "installation": str(inst),
                               **TOUTES, **plus}, None, None)
        o.contexte = {"agent": "chef", "dossier": str(chef_dir)}; return o
    chef = outil(); pousser, demander = chef.verbes["pousser"], chef.verbes["demander-fusion"]

    # la copie de travail du chef (clone du dépôt), SA branche de finition — jamais créée dans le dépôt
    subprocess.run(["git", "clone", "-q", str(depot), str(copie)], capture_output=True)
    git(copie, "switch", "-q", "-c", "equipe/fin"); c1 = commit(copie, "fin.txt", "finition\n", "feat: finition du sujet")

    # ── config locale piégée de la copie (et crochets du dépôt) : rien ne doit s'exécuter pendant l'import ──
    piege, piege_pack = t / "piege", t / "piege-pack"; script, script_pack = t / "piege.sh", t / "piege-pack.sh"
    for f, x in ((script, piege), (script_pack, piege_pack)): f.write_text(f'#!/bin/sh\ntouch {x}\nexec "$@"\n'); f.chmod(0o755)
    crochets = t / "crochets"; crochets.mkdir()
    noms = ("pre-push", "post-checkout", "reference-transaction", "post-merge", "pre-auto-gc", "post-update", "update",
            "pre-receive", "push-to-checkout", "fsmonitor-watchman", "pre-commit", "post-rewrite")
    for d in (copie / ".git/hooks", crochets, depot / ".git/hooks"):
        for h in noms: (d / h).write_text(f"#!/bin/sh\ntouch {piege}\n"); (d / h).chmod(0o755)
    for k, v in (("core.fsmonitor", str(script)), ("core.hooksPath", str(crochets)), ("uploadpack.packObjectsHook", str(script_pack)),
                 ("core.sshCommand", str(script)), ("core.pager", str(script))):
        git(copie, "config", k, v)

    # ── le bug du n°47 : la branche n'est que dans la copie du chef ──
    dire(not au_depot("equipe/fin"), "départ : la branche de finition n'est QUE dans la copie de travail du chef (dépôt intouché)")
    r = erreur(pousser, ["equipe/fin"])
    dire(r == "" and sur_forge("equipe/fin") == c1 and au_depot("equipe/fin") == c1,
         f"pousser : importée de la copie dans le dépôt puis poussée sur la forge (le n°47 refusait : « pas de branche ») {r}")
    dire(not piege.exists() and not piege_pack.exists(), "config locale piégée de la copie (fsmonitor, hooksPath, packObjectsHook, sshCommand, pager, crochets) : rien exécuté")

    # ── témoins : les mêmes pièges se déclenchent avec un git ordinaire (les contrôles ci-dessus prouvent quelque chose) ──
    git(copie, "status", env=ORDINAIRE)
    dire(piege.exists(), "témoin : core.fsmonitor de la copie se déclenche avec un git ordinaire lancé DANS la copie"); piege.unlink(missing_ok=True)
    autre = t / "temoin"; subprocess.run(["git", "init", "-q", str(autre)])
    (t / "global.cfg").write_text(f"[uploadpack]\n\tpackObjectsHook = {script_pack}\n")
    git(autre, "fetch", "-q", str(copie / ".git"), "refs/heads/equipe/fin:refs/heads/x", env={**ORDINAIRE, "GIT_CONFIG_GLOBAL": str(t / "global.cfg")})
    dire(piege_pack.exists(), "témoin : packObjectsHook se déclenche s'il vient d'une config protégée (globale) — pas de la config de la copie")
    piege.unlink(missing_ok=True); piege_pack.unlink(missing_ok=True)

    # ── avance rapide seule : une branche réécrite dans la copie est refusée, rien n'est importé ni poussé ──
    git(copie, "commit", "-q", "--amend", "-m", "feat: finition réécrite")
    e = erreur(pousser, ["equipe/fin"])
    dire(e.startswith("RuntimeError") and "avance rapide" in e and au_depot("equipe/fin") == c1 and sur_forge("equipe/fin") == c1,
         "copie réécrite : import refusé (avance rapide seule), dépôt et forge gardent le commit poussé")
    dire("avance rapide" in erreur(demander, ["equipe/fin", "livré : la finition du sujet"]), "copie réécrite : demander-fusion refusé de même")
    git(copie, "reset", "-q", "--hard", c1)

    # ── demander-fusion : même import ; pas poussée → refus ; poussée → demande ; fusionner voit la MÊME branche ──
    c2 = commit(copie, "fin2.txt", "suite\n", "feat: suite")
    e = erreur(demander, ["equipe/fin", "livré : la finition du sujet, portes jouées"])
    dire("pas poussée" in e and au_depot("equipe/fin") == c2, "demander-fusion : importe la suite (avance rapide) puis refuse, pas poussée")
    pousser(["equipe/fin"]); demander(["equipe/fin", "livré : la finition du sujet, portes jouées"])
    d = json.loads((dem / "fin.json").read_text())
    dire(d["commit"] == c2 == sur_forge("equipe/fin") and d["agent"] == "chef" and d["finition"] is True
         and all(d["portes"][p]["etat"] == "vert" for p in ("verify", "tests", "pret")),
         "demande inscrite sur le commit de la copie, au nom du chef, portes vertes")
    dire(chef.valideur("fusionner", ["fin"]) is None, "fusion : propriétaire seul")
    chef.ecritures["fusionner"][1](["fin"])
    dire(forge_main() == c2 and not sur_forge("equipe/fin") and json.loads((dem / "fin.json").read_text())["etat"] == "fusionnée",
         "fusionner : la MÊME branche, en avance rapide dans main")
    dire(not piege.exists() and not piege_pack.exists(), "tout le parcours (pousser, demander, fusionner) : aucun piège de la copie ni du dépôt exécuté")

    # ── copie_chef déclarée ──
    ailleurs = chef_dir / "ailleurs/x"; subprocess.run(["git", "clone", "-q", str(depot), str(ailleurs)], capture_output=True)
    git(ailleurs, "switch", "-q", "-c", "equipe/deux"); c3 = commit(ailleurs, "deux.txt", "2\n", "feat: deux")
    o = outil(copie_chef=str(ailleurs))
    dire(erreur(o.verbes["pousser"], ["equipe/deux"]) == "" and sur_forge("equipe/deux") == c3, "copie_chef déclarée : la branche y est prise")
    dire("ni dans ta copie" in erreur(pousser, ["equipe/absente"]) and not sur_forge("equipe/absente"), "branche absente de la copie (et du dépôt) : refusée, rien poussé")
    git(copie, "switch", "-q", "main"); commit(copie, "main.txt", "x\n", "feat: main écrit dans la copie")
    avant = forge_main(); e = erreur(pousser, ["main"])
    dire(e.startswith("ValueError") and forge_main() == avant and "main.txt" not in git(depot, "ls-tree", "main").stdout,
         "branche principale (même écrite dans la copie) : refusée, ni importée ni poussée")
    git(copie, "switch", "-q", "-c", "equipe/trois"); c4 = commit(copie, "trois.txt", "3\n", "feat: trois")
    for ctx, quoi in (({"agent": "p-dev", "dossier": str(chef_dir)}, "un développeur (même avec le dossier du chef)"),
                      ({"agent": "coord", "dossier": str(chef_dir)}, "le coordinateur"), ({}, "appelant inconnu")):
        chef.contexte = ctx; e = erreur(pousser, ["equipe/trois"])
        dire(e.startswith("PermissionError") and not au_depot("equipe/trois") and not sur_forge("equipe/trois"),
             f"appelant non chef ({quoi}) : refusé AVANT l'import, rien dans le dépôt ni sur la forge")
    chef.contexte = {"agent": "chef", "dossier": str(chef_dir)}

    # ── reprise d'une livraison « à finir » (finition = chef) : la branche du chef, venue de SA copie, doit contenir le commit livré ──
    git(copie, "fetch", "-q", "origin"); git(copie, "switch", "-q", "-c", "equipe/quatre", "origin/main")
    livre = commit(copie, "dev.txt", "livré\n", "feat: livré par le développeur"); commit(copie, "fin4.txt", "fini\n", "feat: fini par le chef")
    git(copie, "switch", "-q", "-c", "equipe/cinq", "origin/main"); commit(copie, "cinq.txt", "5\n", "feat: sans le commit livré")
    for sujet in ("quatre", "cinq"):
        (dem / f"{sujet}.json").write_text(json.dumps({"sujet": sujet, "branche": f"equipe/dev-{sujet}", "etat": "à finir", "agent": "p-dev",
                                                       "commit": livre, "demande": "2026-10-13T15:00"}))
    pousser(["equipe/quatre"]); demander(["equipe/quatre", "livré : la finition reprise depuis la copie du chef"])
    d = json.loads((dem / "quatre.json").read_text())
    dire(d["branche"] == "equipe/quatre" and d["etat"] == "à relire" and d["origine"]["commit"] == livre and d["origine"]["agent"] == "p-dev",
         "reprise « à finir » : la branche importée de la copie remplace la livraison, origine du développeur gardée")
    pousser(["equipe/cinq"]); e = erreur(demander, ["equipe/cinq", "livré : une finition sans le commit livré"])
    dire("commit livré" in e and json.loads((dem / "cinq.json").read_text())["etat"] == "à finir",
         "reprise : branche de la copie sans le commit livré → refusée, la livraison reste « à finir »")

    # ── refus des chemins ──
    (chef_dir / "lien").symlink_to(ailleurs); (t / "autre").mkdir(); (chef_dir / "dlien").symlink_to(t / "autre")
    gitlien = chef_dir / "gitlien"; gitlien.mkdir(); (gitlien / ".git").symlink_to(depot / ".git")
    gitfichier = chef_dir / "gitfichier"; gitfichier.mkdir(); (gitfichier / ".git").write_text(f"gitdir: {depot / '.git'}\n")
    for c, quoi, pourquoi in (("travail/x", "chemin relatif", "absolu"), (str(t / "autre"), "hors du dossier du chef", "DANS"),
                              (str(chef_dir), "le dossier du chef lui-même", "DANS"), (str(chef_dir / "lien"), "lien symbolique", "lien"),
                              (str(chef_dir / "dlien/x"), "lien symbolique vers l'extérieur", "lien"),
                              (str(chef_dir / "travail/../../chef2"), "« .. » qui sort du dossier", "DANS"),
                              (str(inst / "equipes/p/fin"), "déclarée dans l'installation (hors du dossier du chef)", "DANS"),
                              (str(inst / "courtier"), "le code de l'installation", "DANS"),
                              (str(gitlien), ".git lien symbolique", "vrai dossier"), (str(gitfichier), ".git fichier qui renvoie ailleurs", "vrai dossier")):
        e = erreur(outil(copie_chef=c).verbes["pousser"], ["equipe/fin"])
        dire(e.startswith("ValueError") and pourquoi in e, f"copie de travail refusée : {quoi}")
    for c, quoi, pourquoi in ((depot, "le dépôt du chef", "touche le dépôt"), (depot / "sous", "dans le dépôt", "touche le dépôt"),
                              (forge, "la forge", "touche la forge"), (inst, "l'installation", "l'installation")):
        o = outil(copie_chef=str(c)); o.contexte = {"agent": "chef", "dossier": str(t)}   # un dossier d'agent qui contiendrait tout
        e = erreur(o.verbes["pousser"], ["equipe/fin"])
        dire(e.startswith("ValueError") and pourquoi in e, f"copie de travail refusée : {quoi}")
    o = outil(copie_chef=str(t / "x")); o.contexte = {"agent": "chef", "dossier": str(t)}; o.installation = [t / "x/installation"]
    dire("contient l'installation" in erreur(o.verbes["pousser"], ["equipe/fin"]), "copie de travail refusée : elle contient l'installation")
    o = outil(); o.contexte = {"agent": "chef"}
    dire(erreur(o.verbes["pousser"], ["equipe/fin"]).startswith("PermissionError"), "dossier de l'appelant inconnu : refusé")
    dire(not piege.exists() and not piege_pack.exists(), "refus des chemins : aucun piège exécuté")

raise SystemExit(ko)
