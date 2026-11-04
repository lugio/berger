#!/usr/bin/env python3
"""Portes allégées (spec 2026-10-28-portes-allegees-spec.md) : la porte courte « documentation seule » décidée par le courtier
d'après le diff, « mettre-a-jour » sans identité git, et /courtier/consignes/ ignoré. Sans modèle, sans installation : une forge,
un dépôt de chef de projet et une copie de développeur jetables. Usage : python3 tests/portes-allegees.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import importlib.util, json, os, subprocess, tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
OUTILS = RACINE / "courtier/outils"
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


_portes = charger("_portes")

# ── la machine de test n'a AUCUNE identité git : ni configuration, ni variables (c'est le cas du bug de « mettre-a-jour ») ──
for k in [k for k in os.environ if k.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_")) or k in ("EMAIL", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM")]: del os.environ[k]
with tempfile.TemporaryDirectory() as t:
    t = Path(t); forge, depot, copie, agent, dem = t / "forge.git", t / "depot", t / "copie", t / "agent", t / "demandes"
    fige = lambda s: [s, json.loads((dem / f"{s}.json").read_text())["commit"]]   # ce que la validation fige à l'aperçu (spec 2026-10-29-sha-fige)
    (t / "config.toml").write_text('proprietaire = "Test"\n'); os.environ["BERGER_DIR"] = str(t)
    os.environ["HOME"] = str(t / "maison"); (t / "maison").mkdir(); os.environ["GIT_CONFIG_GLOBAL"] = "/dev/null"; os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
    os.environ["XDG_CONFIG_HOME"] = str(t / "maison")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    for f, c in (("verifier.sh", '[ ! -f rouge ]\n'), ("tests.sh", 'echo TESTS-COMPLETS\n'), ("doc.sh", 'echo DOC-COURTE\n'),
                 ("docs/guide.md", "# g\n"), ("docs/scripts/x.sh", "echo x\n"), ("bin/x.py", "x = 1\n"), ("commun/regle.md", "r\n"), ("tests/t.md", "t\n")):
        (depot / f).parent.mkdir(parents=True, exist_ok=True); (depot / f).write_text(c)
    git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
    subprocess.run(["git", "clone", "-q", str(forge), str(copie)], capture_output=True); git(copie, "switch", "-q", "-c", "equipe/demo")
    agent.mkdir(); (agent / "agent.conf").write_text(f"projet = p\nsujet = demo\ncopie = {copie}\nbranche = equipe/demo\nport = 0\n")
    reglages = {"principale": "main", "demandes": str(dem), "verify": "sh verifier.sh", "tests": "sh tests.sh", "pret": "true", "regle_go": False}

    # ── 1. BUG : mettre-a-jour sans identité git (vraie fusion, branches divergentes) ──
    (copie / "a").write_text("a"); git(copie, "add", "a"); git(copie, "commit", "-qm", "feat: a"); git(copie, "push", "-q", "-u", "origin", "equipe/demo")
    (depot / "b").write_text("b"); git(depot, "add", "b"); git(depot, "commit", "-qm", "main avance"); git(depot, "push", "-q", "origin", "main")
    git(copie, "fetch", "-q", "origin")
    nu = subprocess.run(["git", "-C", str(copie), "merge", "--no-edit", "--no-ff", "-q", "origin/main"], capture_output=True, text=True)
    dire(nu.returncode != 0, "témoin : la copie n'a bien aucune identité git (un merge nu échoue)")
    subprocess.run(["git", "-C", str(copie), "merge", "--abort"], capture_output=True)
    dev = charger("equipe_dev").Outil(reglages, None, None); dev.contexte = {"agent": "p-demo", "dossier": str(agent)}
    r = dev.verbes["mettre-a-jour"]([])
    dire(r["code"] == 0, "mettre-a-jour : la fusion réussit sans identité git" + ("" if r["code"] == 0 else f" — {r['sortie'][-200:]}"))
    dire((copie / "b").is_file(), "mettre-a-jour : main est bien intégrée dans la branche")
    dire(git(copie, "log", "-1", "--format=%an <%ae>").stdout.strip() == "berger (courtier) <courtier@berger.invalid>",
         "mettre-a-jour : le commit de fusion est signé « berger (courtier) »")
    dire(subprocess.run(["git", "-C", str(copie), "config", "--local", "--get", "user.name"], capture_output=True, text=True).stdout.strip() == "", "mettre-a-jour : la configuration de la copie n'est pas modifiée")
    dev.verbes["pousser"]([])

    # ── 2. décision : documentation_seule(git, base, tete) ──
    def decision(modif, mode=None, motif=None):
        """Branche jetable depuis main, modif = {chemin: contenu | None (supprimé) | ("lien", cible)} → (bool, raison)."""
        git(depot, "switch", "-q", "-C", "essai", "origin/main")
        for f, c in modif.items():
            p = depot / f; p.parent.mkdir(parents=True, exist_ok=True)
            if c is None: p.unlink()
            elif isinstance(c, tuple): p.unlink(missing_ok=True); p.symlink_to(c[1])
            else: p.write_text(c)
            if mode and f in mode: os.chmod(p, mode[f])
        git(depot, "add", "-A"); git(depot, "commit", "-qm", "essai", "--allow-empty")
        res = _portes.documentation_seule(lambda *a: git(depot, *a), "origin/main", "essai", **({"motif_tests": motif} if motif else {}))
        git(depot, "switch", "-q", "main"); git(depot, "branch", "-qD", "essai"); return res
    git(depot, "fetch", "-q", "origin")
    ok, raison = decision({"docs/guide.md": "# g2\n", "README.md": "# r\n"})
    dire(ok and "2 fichiers" in raison, f"documentation seule : .md et docs/ → porte courte ({raison})")
    dire(decision({"docs/schema.png": "x", "docs/note.txt": "n"})[0], "documentation seule : image et texte sous docs/ → porte courte")
    dire(decision({"docs/guide.md": None})[0], "documentation seule : suppression d'un .md → porte courte")
    ok, raison = decision({"docs/guide.md": "# g3\n", "bin/x.py": "x = 2\n"})
    dire(not ok and "bin/x.py" in raison, f"un fichier de code → porte complète, le message le nomme ({raison})")
    dire(not decision({"docs/scripts/x.sh": "echo y\n"})[0], "docs/scripts/x.sh : un script sous docs/ n'est pas de la documentation")
    dire(not decision({"tests/t.md": "t2\n"})[0], "un .md sous tests/ → porte complète")
    dire(not decision({"commun/regle.md": "r2\n"})[0], "un .md sous commun/ (consignes des agents) → porte complète")
    # renvoi n°67 (relecture Codex) : liste POSITIVE (docs/** hors docs/scripts/, *.md à la racine) + exclusions incompressibles
    for sonde in ("bin/run.md", "courtier/AGENTS.md", "crochets/hook.md", "hooks/run.md", "docs/scripts/run.txt", "herdr-plugin/notes.md", "AGENTS.md", "SOUL.md",
                  "HEARTBEAT.md", "CLAUDE.md", "docs/AGENTS.md", "docs/consignes/x.md", "skills/x/SKILL.md", "docs/modeles/m.md", "lib/notes.md", "run.sh"):
        ok, raison = decision({sonde: "x\n"})
        dire(not ok and sonde in raison, f"sonde de la relecture : {sonde} → porte complète, le message le nomme")
    dire(not decision({"tests/x.md": "x\n"}, motif="^zzz-aucun$")[0], "tests/x.md reste refusé même avec un motif_tests personnalisé (exclusion incompressible)")
    dire(not decision({"bin/run.md": "x\n"}, motif="^zzz-aucun$")[0], "bin/run.md reste refusé avec un motif_tests personnalisé")
    # renvoi n°69 : racine = liste FERMÉE ; sous docs/ : noms interdits (agents, claude, soul, gemini, codex, heartbeat, mission, memory, skill, consigne)
    for sonde in ("AGENTS.override.md", "CLAUDE.local.md", "docs/AGENTS.override.md", "docs/CLAUDE.local.md", "GEMINI.md", "NOTES.md", "docs/Soul-notes.md",
                  "docs/gemini.md", "docs/guide-codex.md", "docs/heartbeat.md", "docs/mission-x.md", "docs/memory.md", "docs/SKILL.md", "docs/consignes-chef.md"):
        ok, raison = decision({sonde: "x\n"})
        dire(not ok and sonde in raison, f"renvoi n°69 : {sonde} → porte complète, le message le nomme")
    ok, raison = decision({n: "x\n" for n in ("README.md", "README.fr.md", "CHANGELOG.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md")})
    dire(ok and "6 fichiers" in raison, f"la liste fermée de la racine : les 6 documents publics → porte courte ({raison})")
    # un chemin désigné comme consigne par agent.conf (consigne_fichier) n'est jamais de la documentation, même sous docs/
    (t / "agents/chef-dev").mkdir(parents=True)
    conf_agent = t / "agents/chef-dev/agent.conf"
    for valeur, fichier, libelle in (("../../docs/chef-dev.md", "docs/chef-dev.md", "chemin relatif au dossier de l'agent (../../)"),
                                     (f"{t}/docs/chef-dev.md  # rôle du chef", "docs/chef-dev.md", "chemin absolu suivi d'un commentaire"),
                                     ("../../docs/chef-dev2.md # rôle", "docs/chef-dev2.md", "chemin relatif suivi d'un commentaire"),
                                     ("../../docs/a/../chef-dev3.md", "docs/chef-dev3.md", "chemin non normalisé (a/../)")):
        conf_agent.write_text(f"nom = Chef\nconsigne_fichier = {valeur}\n")
        ok, raison = decision({fichier: "x\n"})
        dire(not ok and fichier in raison, f"consigne_fichier ({libelle}) → {fichier} porte complète ({raison})")
    (t / "agents/chef2").mkdir(parents=True)
    (t / "agents/chef2/agent.conf").write_text(f"nom = Chef2\nconsigne_fichier = {t}/agents/chef2/travail/projet/docs/guide-du-projet.md\n")
    ok, raison = decision({"docs/guide-du-projet.md": "x\n"})
    dire(not ok and "docs/guide-du-projet.md" in raison, f"consigne_fichier dans une copie de projet sous l'installation (agents/chef2/travail/projet/docs/…) → porte complète ({raison})")
    dire(not _portes.chemin_documentaire("docs/guide-du-projet.md", {f"{t}/agents/chef2/travail/projet/docs/guide-du-projet.md"}),
         "comparaison par suffixe : le chemin résolu absolu se termine par /docs/guide-du-projet.md, sans le repli par nom")
    conf_agent.write_text("nom = Chef\nconsigne_fichier = ../../docs/chef-dev.md\n")
    dire(decision({"docs/autre-guide.md": "x\n"})[0], "un autre fichier sous docs/ reste de la documentation")
    lien = t / "agents/chef-dev/lien"; lien.symlink_to(t / "docs")                  # un lien symbolique dans le chemin est résolu
    conf_agent.write_text("nom = Chef\nconsigne_fichier = lien/par-lien.md\n")
    dire(not decision({"docs/par-lien.md": "x\n"})[0], "consigne_fichier passant par un lien symbolique → résolu (realpath)")
    conf_agent.write_text("nom = Chef\nconsigne_fichier = /ailleurs/hors-depot/guide-du-chef.md\n")
    dire(not decision({"docs/guide-du-chef.md": "x\n"})[0] and not decision({"docs/sous/guide-du-chef.md": "x\n"})[0],
         "consigne_fichier hors de tout dépôt (irréductible) → refus prudent sur le même nom de fichier")
    conf_agent.write_text("nom = Chef\nconsigne_fichier = ../../docs/chef-dev.md\n")
    ok, raison = decision({"CHANGELOG.md": "# c\n", "docs/a/b.md": "b\n", "README.md": "r\n"})
    dire(ok and "3 fichiers" in raison, f"CHANGELOG.md, README.md à la racine et docs/** profond → porte courte ({raison})")
    dire(not decision({"docs/lien.md": ("lien", "../bin/x.py")})[0], "un lien symbolique .md → porte complète")
    dire(not decision({"docs/guide.md": "# g4\n"}, mode={"docs/guide.md": 0o755})[0], "un .md rendu exécutable → porte complète")
    git(depot, "switch", "-q", "-C", "renom", "origin/main"); git(depot, "mv", "bin/x.py", "docs/x.md"); git(depot, "commit", "-qm", "renom")
    dire(not _portes.documentation_seule(lambda *a: git(depot, *a), "origin/main", "renom")[0], "renommage bin/x.py → docs/x.md : la source est du code → porte complète")
    git(depot, "switch", "-q", "main"); git(depot, "branch", "-qD", "renom")
    dire(not _portes.documentation_seule(lambda *a: git(depot, *a), "origin/main", "origin/main")[0], "diff vide → porte complète, jamais courte par défaut")
    dire(not _portes.documentation_seule(lambda *a: git(depot, *a), "origin/main", "n-existe-pas")[0], "diff illisible → porte complète")

    # ── 3. développeur : la porte courte remplace « tests », verify et pret restent jouées ──
    avec_doc = {**reglages, "doc": "sh doc.sh"}
    def nouvelle_demande(modif, regl):
        global dev
        git(copie, "switch", "-q", "-C", "equipe/demo", "origin/main")
        for f, c in modif.items(): (copie / f).parent.mkdir(parents=True, exist_ok=True); (copie / f).write_text(c)
        git(copie, "add", "-A"); git(copie, "commit", "-qm", "docs: texte"); git(copie, "push", "-qf", "origin", "equipe/demo")
        dev = charger("equipe_dev").Outil(regl, None, None); dev.contexte = {"agent": "p-demo", "dossier": str(agent)}
        (dem / "demo.json").unlink(missing_ok=True)
        return dev.verbes["demander-fusion"](["livré : documentation seule, contrôles joués"])
    r = nouvelle_demande({"docs/guide.md": "# g5\n"}, avec_doc)
    d = json.loads((dem / "demo.json").read_text())
    dire(d["portes"]["tests"].get("court") == "documentation seule" and "DOC-COURTE" in d["portes"]["tests"]["bilan"],
         "demande doc seule : « tests » est la porte doc, marquée courte")
    dire(d["portes"]["verify"]["etat"] == "vert" and d["portes"]["pret"]["etat"] == "vert" and "court" not in d["portes"]["verify"],
         "demande doc seule : verify et pret sont jouées normalement")
    dire("porte courte" in r["mode"] and "tests complets non joués" in r["mode"], f"le message dit la porte courte ({r['mode']})")
    r = nouvelle_demande({"docs/guide.md": "# g6\n", "bin/x.py": "x = 3\n", "tests/y.py": "y = 1\n"}, avec_doc)
    d = json.loads((dem / "demo.json").read_text())
    dire("TESTS-COMPLETS" in d["portes"]["tests"]["bilan"] and "court" not in d["portes"]["tests"], "demande avec du code : porte complète")
    dire("porte complète" in r["mode"] and "bin/x.py" in r["mode"], f"le message nomme le fichier hors périmètre ({r['mode']})")
    r = nouvelle_demande({"docs/guide.md": "# g7\n"}, reglages)
    d = json.loads((dem / "demo.json").read_text())
    dire("TESTS-COMPLETS" in d["portes"]["tests"]["bilan"] and "mode" not in r, "sans « doc » déclarée : rien ne change (porte complète)")
    dire(refuse(dev.verbes["demander-fusion"], [], "résumé"), "aucun argument ne choisit le mode : seul le résumé est lu")
    (agent / "agent.conf").write_text((agent / "agent.conf").read_text() + "porte_courte = oui\ndoc = true\n")
    r = nouvelle_demande({"docs/guide.md": "# g8\n", "bin/x.py": "x = 4\n", "tests/y.py": "y = 2\n"}, avec_doc)
    dire("porte complète" in r["mode"], "agent.conf ne peut pas déclarer la porte courte")

    # ── 4. chef : il recalcule le mode ; l'annonce complète rejouée en court (ou l'inverse) est un écart ──
    chef = charger("equipe_chef").Outil({"depot": str(depot), "principale": "main", "demandes": str(dem), "valide_par": "coord", "regle_go": False,
                                         **{k: v for k, v in avec_doc.items() if k in ("verify", "tests", "pret", "doc")},
                                         "travail": str(t / "integration")}, None, None)
    chef.contexte = {"agent": "chef"}
    git(depot, "fetch", "-q", "origin")
    r = nouvelle_demande({"docs/guide.md": "# g9\n"}, avec_doc)
    j = chef.verbes["rejouer"](["demo"])
    dire(j["recompte"].startswith("conforme") and "porte courte" in j["sorties"]["mode"], f"chef : rejouer recalcule la porte courte, recompte conforme ({j['recompte']})")
    d = json.loads((dem / "demo.json").read_text()); d["portes"]["tests"] = {"etat": "vert", "code": 0, "bilan": "TESTS-COMPLETS"}   # annonce complète
    (dem / "demo.json").write_text(json.dumps(d))
    dire(chef.verbes["rejouer"](["demo"])["recompte"].startswith("ÉCART"), "chef : annonce complète, mesure courte → écart signalé")
    nouvelle_demande({"docs/guide.md": "# g10\n", "bin/x.py": "x = 5\n", "tests/y.py": "y = 3\n"}, avec_doc)
    d = json.loads((dem / "demo.json").read_text()); d["portes"]["tests"] = {"etat": "vert", "code": 0, "bilan": "DOC-COURTE", "court": "documentation seule"}
    (dem / "demo.json").write_text(json.dumps(d))
    j = chef.verbes["rejouer"](["demo"])
    dire(j["recompte"].startswith("ÉCART") and "porte complète" in j["sorties"]["mode"], "chef : annonce courte pour une demande qui touche du code → écart signalé")

    # ── 5. fusion : pret rejouée avant l'avance rapide ; main avancé → mode recalculé sur le commit de mise à jour ──
    nouvelle_demande({"docs/guide.md": "# g11\n"}, avec_doc)
    appels = []
    vrai = chef.jouer_portes; chef.jouer_portes = lambda c, seules=None: (appels.append(seules), vrai(c, seules))[1]
    chef.ecritures["fusionner"][1](fige("demo"))
    dire(appels and appels[0] == {"pret"}, "fusion en avance rapide : seule pret est rejouée (inchangé)")
    git(copie, "switch", "-q", "-C", "equipe/demo2", "origin/main")
    (depot / "c").write_text("c"); git(depot, "add", "c"); git(depot, "commit", "-qm", "main avance encore"); git(depot, "push", "-q", "origin", "main")
    (copie / "docs").mkdir(exist_ok=True); (copie / "docs/autre.md").write_text("# a\n"); git(copie, "add", "-A"); git(copie, "commit", "-qm", "docs: autre")
    git(copie, "push", "-q", "origin", "equipe/demo2")
    git(depot, "fetch", "-q", "origin"); cible = chef.mise_a_jour({"branche": "equipe/demo2", "commit": git(copie, "rev-parse", "HEAD").stdout.strip()})
    res, sorties = chef.jouer_portes(cible)
    dire(res["tests"].get("court") == "documentation seule", "main avancé : le mode est recalculé sur le commit de mise à jour (documentation seule)")

    # ── 5b. sécurité : la copie du développeur ment sur sa base → le chef recalcule à la fusion (dépôt du chef) ──
    git(copie, "switch", "-q", "-C", "equipe/triche", "origin/main")
    (copie / "bin").mkdir(exist_ok=True); (copie / "bin/triche.py").write_text("import os\n"); git(copie, "add", "-A"); git(copie, "commit", "-qm", "feat: code")
    git(copie, "push", "-q", "origin", "equipe/triche"); tete = git(copie, "rev-parse", "HEAD").stdout.strip()
    git(copie, "update-ref", "refs/remotes/origin/main", tete)                      # la copie déplace sa base : le diff paraît vide
    dire(not _portes.documentation_seule(lambda *a: git(copie, *a), "origin/main", tete)[0], "témoin : base déplacée dans la copie → diff vide, donc jamais « documentation seule »")
    dem.mkdir(exist_ok=True)
    (dem / "triche.json").write_text(json.dumps({"sujet": "triche", "branche": "equipe/triche", "commit": tete, "etat": "à relire", "resume": "x", "agent": "p-triche",
        "portes": {"verify": {"etat": "vert"}, "tests": {"etat": "vert", "code": 0, "bilan": "DOC-COURTE", "court": "documentation seule"}, "pret": {"etat": "vert"}}}))
    git(depot, "fetch", "-q", "origin")
    avant = git(forge, "rev-parse", "main").stdout
    ar = chef.ecritures["fusionner"][1]
    dire(refuse(ar, fige("triche"), "n'est pas de la documentation seule") and refuse(ar, fige("triche"), "bin/triche.py"), "fusion : annonce courte pour du code (base de la copie déplacée) → refusée, fichier nommé")
    dire(git(forge, "rev-parse", "main").stdout == avant, "fusion refusée : rien n'est poussé dans main")

    # ── 5c. aperçu : le chef récupère (fetch) et ffige ses références AVANT le contrôle du mode (commit pas encore connu de lui) ──
    git(copie, "fetch", "-q", "origin"); git(copie, "update-ref", "refs/remotes/origin/main", git(forge, "rev-parse", "main").stdout.strip())     # la copie retrouve la vraie base
    git(copie, "switch", "-q", "-C", "equipe/inconnue", "origin/main"); (copie / "docs/neuf.md").write_text("# n\n"); git(copie, "add", "-A"); git(copie, "commit", "-qm", "docs: neuf")
    git(copie, "push", "-q", "origin", "equipe/inconnue"); inconnu = git(copie, "rev-parse", "HEAD").stdout.strip()
    dire(git(depot, "cat-file", "-e", inconnu).returncode != 0, "témoin : le commit n'est pas encore connu du dépôt du chef")
    (dem / "inconnue.json").write_text(json.dumps({"sujet": "inconnue", "branche": "equipe/inconnue", "commit": inconnu, "etat": "à relire", "resume": "docs", "agent": "p-inconnue",
        "portes": {"verify": {"etat": "vert"}, "tests": {"etat": "vert", "code": 0, "bilan": "DOC-COURTE", "court": "documentation seule"}, "pret": {"etat": "vert"}}}))
    try: apercu = chef.apercu_fusion(["inconnue"])
    except Exception as e: apercu = f"EXC {e}"
    dire(not str(apercu).startswith("EXC") and "docs" in str(apercu), f"aperçu d'une demande documentaire au commit inconnu : fetch d'abord, pas de refus à tort ({str(apercu)[:100]})")
    # la consigne d'un agent vit dans une copie de projet sous l'installation : le chef refuse aussi la porte courte annoncée
    git(copie, "switch", "-q", "-C", "equipe/copiecons", "origin/main"); (copie / "docs/guide-du-projet.md").write_text("# consigne\n")
    git(copie, "add", "-A"); git(copie, "commit", "-qm", "docs: guide"); git(copie, "push", "-q", "origin", "equipe/copiecons")
    (dem / "copiecons.json").write_text(json.dumps({"sujet": "copiecons", "branche": "equipe/copiecons", "commit": git(copie, "rev-parse", "HEAD").stdout.strip(), "etat": "à relire",
        "resume": "docs", "agent": "p-copiecons", "portes": {"verify": {"etat": "vert"}, "tests": {"etat": "vert", "code": 0, "bilan": "DOC-COURTE", "court": "documentation seule"}, "pret": {"etat": "vert"}}}))
    dire(refuse(chef.apercu_fusion, ["copiecons"], "docs/guide-du-projet.md"), "chef : annonce courte pour un fichier désigné consigne (copie de projet sous l'installation) → refusée")
    # fetch échoué : l'aperçu ne continue pas avec d'anciennes références
    url = git(depot, "remote", "get-url", "origin").stdout.strip(); git(depot, "remote", "set-url", "origin", str(t / "forge-absente.git"))
    dire(refuse(chef.apercu_fusion, ["inconnue"], "fetch"), "fetch échoué : l'aperçu est refusé (jamais d'anciennes références)")
    git(depot, "remote", "set-url", "origin", url)

# ── 6. .gitignore : courtier/consignes/ ne salit jamais git status ──
with tempfile.TemporaryDirectory() as t:
    t = Path(t); sous = t / "depot"; sous.mkdir()
    subprocess.run(["git", "-C", str(sous), "init", "-q"]); (sous / ".gitignore").write_text((RACINE / ".gitignore").read_text())
    (sous / "courtier/consignes").mkdir(parents=True); (sous / "courtier/consignes/outil.log").write_text("version: 1\n"); (sous / "courtier/consignes/outil.json").write_text("{}")
    st = subprocess.run(["git", "-C", str(sous), "status", "--porcelain", "-uall"], capture_output=True, text=True).stdout
    dire("consignes" not in st, f"courtier/consignes/ créé avec des fichiers : git status reste propre ({st.strip()[:80]!r})")
    ig = subprocess.run(["git", "-C", str(sous), "check-ignore", "-q", "courtier/consignes/outil.log"]).returncode
    dire(ig == 0, "courtier/consignes/ est ignoré par la liste blanche")

print(f"==== {ko} échec(s)"); raise SystemExit(1 if ko else 0)
