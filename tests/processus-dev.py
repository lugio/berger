#!/usr/bin/env python3
"""Tests du processus de dév générique (docs/plans/2026-10-12-processus-dev-generique-spec.md) : les 4 portes
(absentes / vertes / rouges, gate absente = « non mesuré », pret obligatoire), la règle du correctif, la relecture qui
rejoue et recompte, la fusion qui rejoue pret et met à jour seule quand main a avancé (jamais avec un fichier commun),
l'étiquette de version. Sans modèle ni installation : forge, dépôt du chef et copies jetables.
Usage : python3 tests/processus-dev.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util, json, os, re, subprocess, sys, tempfile
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
    except (ValueError, RuntimeError, PermissionError) as e: return str(e)


# Une porte = « sh porte.sh <nom> » : rouge si le fichier ROUGE-<nom> est dans le commit, ou si PORTE_ROUGE=<nom> dans
# l'environnement du courtier (simule une porte qui ne passe plus chez le relecteur).
PORTE = 'if [ -f "ROUGE-$1" ] || [ "$PORTE_ROUGE" = "$1" ]; then echo "ÉCHEC $1"; exit 1; fi\necho "ok $1 : 3 contrôles"\n'
TOUTES = {"verify": "sh porte.sh verify", "tests": "sh porte.sh tests", "pret": "sh porte.sh pret"}

with tempfile.TemporaryDirectory() as t:
    t = Path(t); forge, depot, dem = t / "forge.git", t / "depot", t / "demandes"
    (t / "config.toml").write_text('proprietaire = "Test"\n'); os.environ["BERGER_DIR"] = str(t)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    git(depot, "config", "user.name", "t"); git(depot, "config", "user.email", "t@t.invalid")
    (depot / "porte.sh").write_text(PORTE); (depot / "doc.md").write_text("ligne 1\nligne 2\nligne 3\nligne 4\nligne 5\n")
    git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")

    appels = []
    def faux_controle(args):                     # verbe de lecture d'un outil (gate_outil) : reçoit une branche poussée
        appels.append(args[0])
        r = subprocess.run(["git", "--git-dir", str(forge), "cat-file", "-e", f"{args[0]}:ROUGE-gate"], capture_output=True)
        return {"code": 1 if r.returncode == 0 else 0, "sortie": f"ok gate sur {args[0]}"}

    def developpeur(sujet, reglages):
        copie, agent = t / f"copie-{sujet}", t / f"agent-{sujet}"
        subprocess.run(["git", "clone", "-q", str(forge), str(copie)], capture_output=True); git(copie, "switch", "-q", "-c", f"equipe/{sujet}")
        git(copie, "config", "user.name", "t"); git(copie, "config", "user.email", "t@t.invalid")
        agent.mkdir(); (agent / "agent.conf").write_text(f"projet = p\nsujet = {sujet}\ncopie = {copie}\nbranche = equipe/{sujet}\nport = 0\n")
        d = charger("equipe_dev").Outil({"principale": "main", "demandes": str(dem), **reglages}, None, None)
        d.portes_par = {"gate": faux_controle}; d.contexte = {"agent": f"p-{sujet}", "dossier": str(agent)}
        return d, copie

    def livrer(d, copie, fichiers, message):
        for f, texte in fichiers.items():
            (copie / f).parent.mkdir(parents=True, exist_ok=True)
            if texte is None: git(copie, "rm", "-q", f)
            else: (copie / f).write_text(texte); git(copie, "add", f)
        git(copie, "commit", "-qm", message); return d.verbes["pousser"]([])

    def avancer_main(fichiers, message):         # une autre fusion est passée : main avance sur la forge
        git(depot, "pull", "-q", "--ff-only", "origin", "main")
        for f, texte in fichiers.items(): (depot / f).write_text(texte); git(depot, "add", f)
        git(depot, "commit", "-qm", message); git(depot, "push", "-q", "origin", "main")

    forge_main = lambda: git(forge, "rev-parse", "main").stdout.strip()
    demande = lambda s: json.loads((dem / f"{s}.json").read_text())

    # ── portes déclarées : un verbe par porte, pret obligatoire ──
    a, ca = developpeur("sans-pret", {"verify": "sh porte.sh verify"})
    dire(set(a.verbes) >= {"verify"} and not {"tests", "gate", "pret"} & set(a.verbes), "portes absentes : aucun verbe tests / gate / pret")
    livrer(a, ca, {"a.txt": "a"}, "feat: a")
    dire("pret" in erreur(a.verbes["demander-fusion"], ["livré : fichier a, portes jouées"]), "pret non déclarée : demande refusée (pret obligatoire)")

    b, cb = developpeur("portes", {**TOUTES, "gate_outil": "faux controler"})
    dire({"verify", "tests", "gate", "pret"} <= set(b.verbes), "portes déclarées : un verbe chacune (verify, tests, gate, pret)")
    dire(b.verbes["tests"]([])["code"] == 0 and "ok tests" in b.verbes["tests"]([])["sortie"], "verbe tests : la porte jouée dans la copie")
    livrer(b, cb, {"b.txt": "b", "ROUGE-tests": "x"}, "feat: b (tests rouges)")
    e = erreur(b.verbes["demander-fusion"], ["livré : fichier b, portes jouées"])
    dire("tests : rouge" in e and "verify : vert" in e and "pret : vert" in e and "gate : vert" in e,
         "une porte rouge : pas de demande, et les 4 résultats sont donnés")
    dire(not (dem / "portes.json").exists(), "porte rouge : aucune demande inscrite")
    livrer(b, cb, {"ROUGE-tests": None}, "test: tests réparés")
    r = b.verbes["demander-fusion"](["livré : fichier b, 3 contrôles par porte"]); p = demande("portes")["portes"]
    dire("demande" in r and all(p[x]["etat"] == "vert" for x in ("verify", "tests", "gate", "pret")), "4 portes vertes : demande inscrite, chaque porte « vert »")
    dire(p["tests"]["bilan"] == "ok tests : 3 contrôles" and appels[-1] == "equipe/portes", "résultat inscrit : bilan de la porte ; gate_outil reçoit SA branche")
    x = demande("portes")
    dire(all(p[k]["joue_par"] == "p-portes" and p[k]["joue_le"] == x["demande"] for k in ("verify", "tests", "gate", "pret"))
         and x["resume"] == "livré : fichier b, 3 contrôles par porte" and x["tronque"] is False,
         "demande inscrite : résumé complet, chaque porte jouée signée (qui, quand) — spec interface §6.4")

    c, cc = developpeur("sans-gate", TOUTES)
    livrer(c, cc, {"c.txt": "c"}, "feat: c")
    c.verbes["demander-fusion"](["livré : fichier c, portes jouées"])
    dire(demande("sans-gate")["portes"]["gate"] == {"etat": "non mesuré"}, "gate absente : « non mesuré », jamais « vert » (et jamais signée)")
    long_ = "livré : " + "x" * 9000
    c.verbes["demander-fusion"]([long_]); x = demande("sans-gate")
    dire(x["resume"] == long_[:8000] and x["tronque"] is True, "résumé de plus de 8 000 caractères : gardé jusqu'à 8 000, « tronque » le dit")
    d_, cd = developpeur("gate-debranchee", {**TOUTES, "gate_outil": "faux controler"}); d_.portes_par = {}
    livrer(d_, cd, {"d.txt": "d"}, "feat: d")
    dire("gate : rouge" in erreur(d_.verbes["demander-fusion"], ["livré : fichier d, portes jouées"]), "gate_outil non branché : rouge (refus), jamais vert")

    # ── règle du correctif (SSDF PW.8.2 ex. 3, RV.3) ──
    f, cf = developpeur("correctif", TOUTES)
    livrer(f, cf, {"code.sh": "echo réparé\n"}, "fix: la ligne vide ne plante plus")
    e = erreur(f.verbes["demander-fusion"], ["livré : correctif de la ligne vide"])
    dire("sans test qui reproduit" in e and "cause racine" in e, "correctif sans test ni cause racine : refusé (les deux nommés)")
    livrer(f, cf, {"tests/ligne-vide.sh": "sh code.sh\n"}, "test: reproduit la ligne vide")
    e = erreur(f.verbes["demander-fusion"], ["livré : correctif de la ligne vide"])
    dire("cause racine" in e and "sans test" not in e, "correctif avec test mais sans cause racine : refusé")
    f.verbes["demander-fusion"](["livré : correctif de la ligne vide. Cause racine : la boucle lisait une ligne de trop"])
    dire(demande("correctif")["etat"] == "à relire", "correctif avec test et cause racine (dans la demande) : accepté")
    g, cg = developpeur("correctif-commit", TOUTES)
    livrer(g, cg, {"code2.sh": "echo ok\n", "tests/test_code2.py": "pass\n"}, "fix(code2): borne\n\nCause racine : borne inclusive")
    g.verbes["demander-fusion"](["livré : borne corrigée, test ajouté"])
    dire(demande("correctif-commit")["etat"] == "à relire", "correctif avec test et cause racine dans le commit : accepté")

    # ── relecture : le chef rejoue les portes et recompte l'annonce ──
    chef = charger("equipe_chef").Outil({"depot": str(depot), "principale": "main", "demandes": str(dem), "valide_par": "coord",
                                         "travail": str(t / "integration"), **TOUTES, "gate_outil": "faux controler"}, None, None)
    chef.portes_par = {"gate": faux_controle}
    dire("pret" in chef.verbes["relire"](["portes"])["demande"]["portes"], "relire : les portes annoncées sont montrées")
    chef.contexte = {"agent": "chef-p"}
    rj = chef.verbes["rejouer"](["portes"])
    dire(all(v["identique"] for v in rj["portes"].values()) and rj["recompte"] == "conforme à l'annonce", "rejouer : 4 portes rejouées, conformes à l'annonce")
    rx = demande("portes").get("rejeux") or [{}]
    dire(len(rx) == 1 and rx[0].get("par") == "chef-p" and rx[0].get("quand") and rx[0].get("recompte") == "conforme à l'annonce"
         and all(r.get("joue_par") == "chef-p" for r in rx[0].get("portes", {}).values() if r.get("etat") != "non mesuré"),
         "rejouer : le rejeu est inscrit dans la demande (qui, quand, recompte, portes signées)")
    x = demande("portes"); x["portes"]["tests"]["bilan"] = "ok tests : 99 contrôles"; (dem / "portes.json").write_text(json.dumps(x))
    rj = chef.verbes["rejouer"](["portes"])
    dire(not rj["portes"]["tests"]["identique"] and "tests" in rj["recompte"], "rejouer : une annonce gonflée est détectée (recompte)")
    dire(not list((t / "integration").glob("*")) if (t / "integration").exists() else True, "rejouer : la copie jetable du courtier est effacée")

    # ── fusion : pret rejouée, refus si elle n'est pas verte ──
    apercu, fusionner = chef.ecritures["fusionner"]
    avant = forge_main(); os.environ["PORTE_ROUGE"] = "pret"
    e = erreur(fusionner, ["portes"])
    dire("pret" in e and forge_main() == avant, "fusion : pret rouge au rejeu → REFUS, main intacte")
    del os.environ["PORTE_ROUGE"]
    sans_pret = charger("equipe_chef").Outil({"depot": str(depot), "principale": "main", "demandes": str(dem), "travail": str(t / "integration"),
                                              "verify": "sh porte.sh verify"}, None, None)
    dire("pret" in erreur(sans_pret.ecritures["fusionner"][0], ["portes"]), "fusion : projet sans porte pret → refus")
    fusionner(["portes"])
    dire(git(forge, "log", "--format=%s", "main").stdout.count("feat: b") == 1 and demande("portes")["fusion"] == "avance rapide",
         "fusion à jour : pret verte, avance rapide")

    # ── main a avancé : mise à jour automatique seulement sans fichier commun ni conflit ──
    # « sans-gate » (c.txt) : main a reçu b.txt depuis → aucun fichier commun
    dire("mise à jour automatique" in apercu(["sans-gate"]), "aperçu : main a avancé, mise à jour automatique annoncée")
    nb = len(appels); fusionner(["sans-gate"]); m = forge_main()
    parents = git(forge, "log", "-1", "--format=%P", "main").stdout.split()
    dire(len(parents) == 2 and parents[1] == demande("sans-gate")["commit"], "main avancée sans fichier commun : commit de mise à jour (main + branche) poussé")
    dire(git(forge, "cat-file", "-e", "main:c.txt").returncode == 0 and git(forge, "cat-file", "-e", "main:b.txt").returncode == 0,
         "main contient le travail des deux branches")
    dire(appels[nb:] == ["integration/sans-gate"] and not git(forge, "branch", "--list", "integration/*").stdout.strip(),
         "portes rejouées sur le résultat (gate_outil sur integration/<sujet>, effacée ensuite)")
    dire(demande("sans-gate")["fusion"].startswith("mise à jour automatique") and demande("sans-gate")["portes_fusion"]["tests"]["etat"] == "vert",
         "demande : mise à jour automatique et portes rejouées inscrites")

    h, ch = developpeur("commun", TOUTES)
    livrer(h, ch, {"doc.md": "ligne 1 corrigée\nligne 2\nligne 3\nligne 4\nligne 5\n"}, "docs: ligne 1")
    h.verbes["demander-fusion"](["livré : ligne 1 corrigée, portes jouées"])
    avancer_main({"doc.md": "ligne 1\nligne 2\nligne 3\nligne 4\nligne 5 corrigée\n"}, "docs: ligne 5 (autre fusion)")
    avant = forge_main()
    e = erreur(apercu, ["commun"]) or erreur(fusionner, ["commun"])
    dire("fichier commun" in e and "doc.md" in e and forge_main() == avant, "main avancée avec un fichier commun (même sans conflit git) → refus clair, rien poussé")
    dire("fichier commun" in erreur(fusionner, ["commun"]), "la fusion elle-même refuse aussi (pas seulement l'aperçu)")

    k, ck = developpeur("rouge-apres", TOUTES)
    livrer(k, ck, {"k.txt": "k"}, "feat: k"); k.verbes["demander-fusion"](["livré : fichier k, portes jouées"])
    avancer_main({"ROUGE-tests": "x"}, "main casse les tests")
    avant = forge_main(); e = erreur(fusionner, ["rouge-apres"])
    dire("tests" in e and "rouge" in e and forge_main() == avant, "mise à jour automatique aux portes rouges → refus, rien poussé")
    git(depot, "pull", "-q", "--ff-only", "origin", "main"); git(depot, "rm", "-q", "ROUGE-tests"); git(depot, "commit", "-qm", "répare")
    git(depot, "push", "-q", "origin", "main")

    # ── étiquette de version (SSDF PS.3, SemVer 2.0.0, Keep a Changelog 1.1.0) ──
    ap_e, etiqueter = chef.ecritures["etiqueter"]
    dire("SemVer" in erreur(ap_e, ["1.2"]) and "SemVer" in erreur(ap_e, ["v1.2.0"]), "étiquette : version non SemVer refusée")
    dire("CHANGELOG" in erreur(ap_e, ["1.0.0"]), "étiquette : sans entrée de journal (CHANGELOG.md) → refus")
    avancer_main({"CHANGELOG.md": "# Journal des modifications\n\n## [Unreleased]\n\n## [1.0.0] - 2026-10-13\n### Added\n- les portes\n"}, "docs: version 1.0.0")
    dire("v1.0.0" in ap_e(["1.0.0"]), "étiquette : aperçu sans rien écrire")
    etiqueter(["1.0.0"])
    dire(git(forge, "cat-file", "-t", "v1.0.0").stdout.strip() == "tag" and git(forge, "rev-parse", "v1.0.0^{commit}").stdout.strip() == forge_main(),
         "étiquette annotée v1.0.0 poussée sur main")
    dire("les portes" in git(forge, "tag", "-l", "--format=%(contents)", "v1.0.0").stdout, "message de l'étiquette = l'entrée du journal")
    dire("existe" in erreur(ap_e, ["1.0.0"]), "étiquette : jamais redéplacée (refus si elle existe)")
    dire("plus grande" in erreur(ap_e, ["0.9.0"]) and "plus grande" in erreur(ap_e, ["1.0.0-rc.1"]), "étiquette : refusée si pas plus grande que la dernière (SemVer §11)")
    pr = charger("_portes").precedence
    dire(pr("1.0.0-alpha") < pr("1.0.0-alpha.1") < pr("1.0.0-beta.2") < pr("1.0.0-beta.11") < pr("1.0.0-rc.1") < pr("1.0.0") < pr("2.0.0"),
         "précédence SemVer §11 (exemple de la norme)")

    # ── porte pret du projet berger (tests/pret.sh) : code sans test ni doc → rouge ──
    pb = t / "pret-berger"; subprocess.run(["git", "clone", "-q", str(forge), str(pb)], capture_output=True)
    (pb / "tests").mkdir(); (pb / "tests/pret.sh").write_text((RACINE / "tests/pret.sh").read_text())
    (pb / "tests/suites.sh").write_text(""); (pb / "tests/tout.sh").write_text("")
    git(pb, "add", "-A"); git(pb, "commit", "-qm", "base")
    git(pb, "update-ref", "refs/remotes/origin/main", "HEAD")
    pret = lambda: subprocess.run(["bash", str(pb / "tests/pret.sh")], capture_output=True, text=True)
    (pb / "bin").mkdir(); (pb / "bin/outil").write_text("echo x \n"); git(pb, "add", "-A"); git(pb, "commit", "-qm", "code seul")
    r = pret()
    dire(r.returncode and "sans test" in r.stdout and "sans documentation" in r.stdout and "espaces" in r.stdout, "pret.sh : code sans test, sans doc, avec espace final → rouge")
    (pb / "bin/outil").write_text("echo x\n"); (pb / "tests/outil.py").write_text("print('ok')\n"); (pb / "README.md").write_text("# outil\n")
    git(pb, "add", "-A"); git(pb, "commit", "-qm", "test et doc")
    r = pret()
    dire(r.returncode and "outil.py n'est jouée" in r.stdout, "pret.sh : une suite tests/*.py jouée par personne → rouge")
    (pb / "tests/suites.sh").write_text("suite outil.py\n"); git(pb, "add", "-A"); git(pb, "commit", "-qm", "suite jouée")
    r = pret(); dire(r.returncode == 0 and r.stdout.startswith("ok pret"), "pret.sh : code + test + doc + suite jouée → vert")

    # ── générique : rien de codé pour un projet nommé ──
    sources = "".join((OUTILS / x).read_text() for x in ("equipe_dev.py", "equipe_chef.py", "_portes.py"))
    sources += re.search(r"def outils_equipes\(\).*?\n\n\n", (RACINE / "courtier/courtier").read_text(), re.S).group(0)
    dire(not re.search(r"[\"'](berger|moncab)[\"']|== *[\"']\w+-dev[\"']", sources), "outils d'équipe : aucun nom de projet dans le code")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
