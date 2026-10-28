#!/usr/bin/env python3
"""Tests « moins de validations » (docs/plans/2026-10-13-moins-validations-spec.md) — sans modèle, installations, forges et
faux programmes JETABLES (Herdr, systemctl, systemd-run) ; le test s'arrête s'il parlerait aux vrais.
1. relancer : sans validation (verbe de LECTURE de berger-admin dans config.exemple.toml), AU REPOS seulement — refus
   s'il travaille, par le courtier ET en ligne de commande ; --force du propriétaire tracé ; --force refusé à un agent.
2. config.exemple.toml : relancer en lecture ; installer, agent-appliquer, publier en actions ; installer_outil.
3. courtier : installer_outil branché sur l'action déclarée ; refusé si ce n'est pas une action ou sans fusion_par.
4. etiqueter SANS validation sur le commit d'une fusion validée (version la plus récente du journal) ; sinon validation.
5. fusion du projet qui EST l'installation : l'installation suit seule, une fois, après le push ; en échec → « fusion
   faite » et code ≠ 0 (« validé mais ÉCHEC ») ; un autre projet : rien. Résumé en avance rapide : portes de la demande datées.
6. berger installer : succès ; verifier-depot rouge → retour arrière prouvé ; avance rapide refusée → rien changé ;
   courtier inactif après redémarrage → retour arrière, redémarrage sur l'ancien code, tracé et notifié.
Usage : python3 tests/moins-validations.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.machinery, importlib.util, json, os, re, subprocess, sys, tempfile, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0
ENV_GIT = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def git(d, *a): return subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True, env={**os.environ, **ENV_GIT})


def erreur(f, args):
    try: f(args); return ""
    except (ValueError, RuntimeError, PermissionError) as e: return str(e)


def bloc_exemple(entete):
    """Le bloc commenté de config.exemple.toml qui commence à la ligne « # <entete> », décommenté et lu en TOML."""
    lignes, dedans = [], False
    for l in (SRC / "config.exemple.toml").read_text().splitlines():
        if l.startswith(f"# {entete}"): dedans = True
        elif dedans and not l.startswith("#"): break
        elif dedans and re.match(r"# \[(?!outils\.berger-admin|equipes\.berger)", l): break
        if dedans: lignes.append(l[2:] if l.startswith("# ") else "")
    return tomllib.loads("\n".join(lignes))


def charger_outil(t):
    spec = importlib.util.spec_from_file_location(f"outil_{t}", SRC / "courtier/outils" / f"{t}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def charger_courtier(i, nom):
    loader = importlib.machinery.SourceFileLoader(nom, str(i / "courtier/courtier"))
    spec = importlib.util.spec_from_loader(nom, loader); c = importlib.util.module_from_spec(spec); loader.exec_module(c); return c


# ── 2. config.exemple.toml : une seule source ──
admin = bloc_exemple("[outils.berger-admin]")["outils"]["berger-admin"]
equipe = bloc_exemple("[equipes.berger]")["equipes"]["berger"]
dire("relancer" in admin["lecture"] and "relancer" not in admin["actions"], "config.exemple : relancer est un verbe de LECTURE (sans validation)")
dire(all(v in admin["actions"] for v in ("installer", "agent-appliquer", "publier", "regenerer")),
     "config.exemple : installer, agent-appliquer, publier, regenerer restent des actions validées")
dire(admin["actions"]["installer"].startswith("bin/berger installer ") and "--force" not in admin["lecture"]["relancer"],
     "config.exemple : installer = LA commande berger installer ; relancer sans --force")
dire(equipe.get("installer_outil") == "berger-admin installer" and equipe.get("fusion_par") == "proprietaire",
     "config.exemple : [equipes.berger] installer_outil = berger-admin installer, fusion_par = proprietaire")

# ── 1. relancer : au repos seulement ──
FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["FAUX_HERDR"]; etat = json.load(open(T + "/etat.json")); a = sys.argv[1:]
with open(T + "/appels.log", "a") as f: f.write(json.dumps(a) + "\n")
r = {}
if a[:2] == ["agent", "list"]: r = {"agents": [{"name": n, "pane_id": p} for n, p in etat["agents"].items()]}
elif a[:2] == ["workspace", "list"]: r = {"workspaces": [{"workspace_id": w} for w in etat["espaces"]]}
elif a[:2] == ["pane", "get"]: r = {"pane": {"pane_id": a[2], "agent_status": etat.get("statuts", {}).get(a[2], "idle")}}
elif a[:2] == ["pane", "send-keys"] and a[3] == "ctrl+c": etat["agents"] = {n: p for n, p in etat["agents"].items() if p != a[2]}
elif a[:2] == ["agent", "start"]: etat["agents"][a[2]] = a[a.index("--pane") + 1]; r = {"agent": a[2]}
json.dump(etat, open(T + "/etat.json", "w")); print(json.dumps({"result": r}))
'''

with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"; _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    d = i / "agents/veille"; (d / "memory").mkdir(parents=True)
    (d / "agent.conf").write_text("nom = Veille\nmoteur = claude\npanneaux = claude\nmur = ouvert\nheures = aucune\n")
    (d / ".herdr.json").write_text(json.dumps({"workspace": "w1", "agents": {"claude": "p1"}}))
    conv = m / ".claude/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(d)); conv.mkdir(parents=True)
    (conv / "conv-1.jsonl").write_text('{"entrypoint":"cli"}\n'); (d / ".conversation-claude").write_text("conv-1\n")
    f = m / "faux"; f.mkdir(); b = m / ".local/bin"; b.mkdir(parents=True)
    (f / "herdr").write_text(FAUX_HERDR); (b / "claude").write_text("#!/bin/sh\nexit 0\n")
    for x in (f / "herdr", b / "claude"): os.chmod(x, 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "FAUX_HERDR": str(f), "BERGER_HERDR": str(f / "herdr"),
           "BERGER_NOTIFY_SEND": str(f / "absent")}
    env.pop("BERGER_AGENT", None)
    sonde = subprocess.run([sys.executable, "-c", f"import runpy;g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');print(g['HERDR'])"],
                           env=env, capture_output=True, text=True)
    if sonde.stdout.strip() != str(f / "herdr"): sys.exit(f"ARRÊT : Berger ne prendrait pas le faux Herdr ({sonde.stdout.strip() or sonde.stderr[-200:]})")
    def poser(statut): (f / "etat.json").write_text(json.dumps({"agents": {"veille-claude": "p1"}, "espaces": ["w1"], "statuts": {"p1": statut}}))
    def appels(): return [json.loads(l) for l in (f / "appels.log").read_text().splitlines()] if (f / "appels.log").exists() else []
    def berger(*a, e=env): return subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=e, capture_output=True, text=True, timeout=120)
    def relance_tapee(): return any(x[:2] == ["pane", "send-keys"] for x in appels()) or any(x[:2] == ["agent", "start"] for x in appels())
    journal = lambda: "".join(p.read_text() for p in (d / "memory").glob("*.md"))

    # par le courtier : le verbe de lecture de config.exemple.toml, lancé par l'outil « commandes » (hors bac à sable)
    os.environ.update({k: v for k, v in env.items() if k in ("HOME", "BERGER_DIR", "FAUX_HERDR", "BERGER_HERDR", "BERGER_NOTIFY_SEND")}); os.environ.pop("BERGER_AGENT", None)
    outil = charger_outil("commandes").Outil({"dossier": str(i), "lecture": {"relancer": admin["lecture"]["relancer"]}}, None, None)
    dire("relancer" in outil.verbes and "relancer" not in outil.ecritures, "courtier : relancer est servi sans validation (lecture)")
    poser("working"); r = outil.verbes["relancer"](["veille"])
    dire(r["code"] != 0 and "travaille : rien relancé" in r["sortie"] and not relance_tapee(),
         "courtier : agent qui TRAVAILLE → refus clair, rien tapé chez lui")
    dire("tiret" in erreur(outil.verbes["relancer"], ["--force"]) or "argument simple" in erreur(outil.verbes["relancer"], ["--force"]),
         "courtier : --force impossible (argument à tiret refusé)")
    poser("idle"); (f / "appels.log").unlink(missing_ok=True); r = outil.verbes["relancer"](["veille"])
    a = appels(); depart = next((x for x in a if x[:2] == ["agent", "start"]), [])
    dire(r["code"] == 0 and "relancé dans p1" in r["sortie"] and depart[2:3] == ["veille-claude"] and "--resume" in depart,
         "courtier : agent AU REPOS → relancé sans validation, dans SA conversation")
    dire("relancé (au repos)" in journal(), "relance tracée au journal de l'agent")
    dire(not (i / "courtier/validations").exists() or not list((i / "courtier/validations").glob("*.json")), "aucune validation créée")

    # en ligne de commande
    poser("working"); (f / "appels.log").unlink(missing_ok=True)
    r = berger("relancer", "veille", "claude")
    dire(r.returncode != 0 and "travaille : rien relancé" in r.stderr and "--force" in r.stderr and not relance_tapee(),
         "ligne de commande : agent qui travaille → refusé sans --force (rien tapé)")
    r = berger("relancer", "veille", "claude", "--force", e={**env, "BERGER_AGENT": "veille"})
    dire(r.returncode != 0 and "réservé au propriétaire" in r.stderr and not relance_tapee(), "--force refusé depuis un agent (BERGER_AGENT)")
    poser("working"); r = berger("relancer", "veille", "claude", "--force")
    dire(r.returncode == 0 and "relancé dans p1" in r.stdout and "relancé de FORCE par Proprio (travaille)" in journal(),
         "--force du propriétaire → relancé, et tracé au journal de l'agent")
    poser("blocked"); (f / "appels.log").unlink(missing_ok=True)
    r = berger("relancer", "veille")
    dire(r.returncode != 0 and "attend une réponse : rien relancé" in r.stderr and not relance_tapee(), "agent qui attend une réponse : refusé aussi (au repos seulement)")

# ── 3 à 5 : courtier, etiqueter, fusion → installation (forge, dépôt du chef, développeur jetables) ──
PORTE = 'echo "ok $1 : 3 contrôles"\n'
TOUTES = {"verify": "sh porte.sh verify", "tests": "sh porte.sh tests", "pret": "sh porte.sh pret"}
JOURNAL = "# Journal\n\n## [Unreleased]\n\n## [{v}] - 2026-10-13\n### Added\n- {quoi}\n"

with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"; _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    forge, depot = m / "projets/berger.git", m / "projets/berger"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    (depot / "porte.sh").write_text(PORTE); git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
    (m / "coffre.json").write_text("{}")
    base = (f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n\n'
            f'[outils.berger-admin]\ntype = "commandes"\ndossier = "{i}"\n[outils.berger-admin.lecture]\nrelancer = "true"\netat = "true"\n'
            f'[outils.berger-admin.actions]\ninstaller = "echo installé"\n\n'
            f'[equipes.berger]\ndepot = "{depot}"\nchef_projet = "master"\ncoordinateur = "master"\nprefixe = "berger/"\n'
            + "".join(f'{k} = "{v}"\n' for k, v in TOUTES.items()))
    for a in ("master",):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = {a}\npanneaux = claude\nheures = aucune\noutils =\n")
    os.environ.update(HOME=str(m), BERGER_DIR=str(i))

    # 3. chargement du courtier
    (i / "config.toml").write_text(base + 'fusion_par = "proprietaire"\ninstaller_outil = "berger-admin installer"\n')
    C = charger_courtier(i, "courtier_mv1")
    dire(C.OBJETS["berger-chef"].installer_par is C.ECRITURES["berger-admin"]["installer"][1],
         "courtier : installer_outil branché sur l'ACTION installer déclarée (la même commande que l'action manuelle)")
    for conf, quoi in ((base + 'fusion_par = "proprietaire"\ninstaller_outil = "berger-admin etat"\n', "un verbe de lecture"),
                       (base + 'installer_outil = "berger-admin installer"\n', "sans fusion_par = proprietaire"),
                       (base + 'fusion_par = "proprietaire"\ninstaller_outil = "inconnu installer"\n', "un outil inconnu")):
        (i / "config.toml").write_text(conf)
        try: charger_courtier(i, "courtier_mv_refus"); r = "chargé"
        except SystemExit as e: r = str(e)
        dire("installer_outil" in r, f"courtier : installer_outil refusé au chargement ({quoi})")
    (i / "config.toml").write_text(base + 'fusion_par = "proprietaire"\n')
    C2 = charger_courtier(i, "courtier_mv2")
    dire(C2.OBJETS["berger-chef"].installer_par is None, "courtier : sans installer_outil, aucune installation après une fusion")

    # un développeur livre, le chef fusionne (outil du chef chargé comme le courtier le fait)
    dem = i / "equipes/berger/demandes"
    def livrer(sujet, fichiers):
        copie, ag = m / f"copie-{sujet}", m / f"agent-{sujet}"
        subprocess.run(["git", "clone", "-q", str(forge), str(copie)], capture_output=True); git(copie, "switch", "-q", "-c", f"berger/{sujet}")
        ag.mkdir(); (ag / "agent.conf").write_text(f"projet = berger\nsujet = {sujet}\ncopie = {copie}\nbranche = berger/{sujet}\nport = 0\n")
        dev = charger_outil("equipe_dev").Outil({"principale": "main", "demandes": str(dem), **TOUTES}, None, None)
        dev.contexte = {"agent": f"berger-{sujet}", "dossier": str(ag)}
        for nom, texte in fichiers.items(): (copie / nom).write_text(texte); git(copie, "add", nom)
        git(copie, "commit", "-qm", f"feat: {sujet}"); dev.verbes["pousser"]([])
        dev.verbes["demander-fusion"]([f"livré : {sujet}, portes jouées"])
    def chef(installer):
        o = charger_outil("equipe_chef").Outil({"depot": str(depot), "principale": "main", "demandes": str(dem), "projet": "berger",
                                                "travail": str(m / "portes"), "installer_outil": "berger-admin installer" if installer else "", **TOUTES}, None, None)
        o.contexte = {"agent": "master", "dossier": str(i / "agents/master")}; return o
    forge_main = lambda: git(forge, "rev-parse", "main").stdout.strip()
    demande = lambda s: json.loads((dem / f"{s}.json").read_text())

    # 5. fusion → installation, une fois, APRÈS le push
    vu = []
    def installe_ok(args): vu.append(forge_main()); return {"code": 0, "sortie": "installée : a → b ; verifier-depot : dépôt propre"}
    livrer("un", {"un.txt": "un\n", "CHANGELOG.md": JOURNAL.format(v="1.0.0", quoi="un")})
    c = chef(True); c.installer_par = installe_ok
    r = c.ecritures["fusionner"][1](["un"])
    dire(isinstance(r, str) and "installation automatique" in r and vu == [demande("un")["commit"]],
         "fusion validée du projet qui EST l'installation : l'installation suit seule, une fois, APRÈS le push")
    dire(demande("un")["installation"] == "faite" and demande("un")["commit_fusion"] == forge_main(), "demande : installation faite, commit de fusion inscrit")
    dire("verify : vert, à la demande du " in r and "tests : vert, à la demande du " in r and "pret : vert (" in r and "gate : non mesuré" in r
         and "verify : non mesuré" not in r, "résumé en avance rapide : portes de la demande, datées ; « non mesuré » seulement pour gate (jamais jouée)")

    def installe_ko(args): vu.append("ko"); return {"code": 1, "sortie": "✗ installation en ÉCHEC : verifier-depot en échec\nretour arrière fait : HEAD = abc (vérifié)"}
    livrer("deux", {"deux.txt": "deux\n"})
    c = chef(True); c.installer_par = installe_ko
    r = c.ecritures["fusionner"][1](["deux"])
    dire(isinstance(r, dict) and r["code"] == 1 and "fusion FAITE" in r["sortie"] and "retour arrière fait" in r["sortie"],
         "installation en échec : code ≠ 0 (« validé mais ÉCHEC »), le résultat dit « fusion faite » et le retour arrière")
    dire(demande("deux")["etat"] == "fusionnée" and demande("deux")["installation"] == "en ÉCHEC", "demande : fusionnée, installation en ÉCHEC")
    livrer("trois", {"trois.txt": "trois\n"})
    vu.clear(); c = chef(False); r = c.ecritures["fusionner"][1](["trois"])
    dire(isinstance(r, str) and not vu and "installation" not in demande("trois"), "projet sans installer_outil (autre projet) : fusion seule, rien installé")

    # 4. etiqueter : sans validation sur le commit d'une fusion validée
    livrer("quatre", {"quatre.txt": "quatre\n", "CHANGELOG.md": JOURNAL.format(v="1.1.0", quoi="quatre") + "\n## [1.0.0] - 2026-10-12\n### Added\n- un\n"})
    c = chef(False); c.ecritures["fusionner"][1](["quatre"])
    dire(c.sans_validation("etiqueter", ["1.0.0"]) is None, "etiqueter une version qui n'est PAS la plus récente du journal → validation")
    libre = c.sans_validation("etiqueter", ["1.1.0"])
    dire(bool(libre) and "quatre" in libre[0], "etiqueter la dernière version sur le commit de la fusion validée → sans validation (" + (libre[0][:60] if libre else "") + ")")
    dire(c.sans_validation("fusionner", ["quatre"]) is None, "fusionner n'est jamais sans validation")
    git(depot, "pull", "-q", "--ff-only", "origin", "main"); (depot / "hors.txt").write_text("x\n"); git(depot, "add", "-A")
    git(depot, "commit", "-qm", "commit hors fusion"); git(depot, "push", "-q", "origin", "main")
    dire(c.sans_validation("etiqueter", ["1.1.0"]) is None, "tête de main qui n'est pas un commit de fusion inscrit → validation")
    libre[1]()                                                       # le geste contrôlé : sur LE commit de la fusion, pas sur la tête
    dire(git(forge, "rev-parse", "v1.1.0^{commit}").stdout.strip() == demande("quatre")["commit_fusion"] != forge_main(),
         "le geste pose l'étiquette sur le commit CONTRÔLÉ (celui de la fusion), même si main a avancé depuis")

    # par le courtier : réponse directe, aucune validation ; sinon validation comme avant
    (i / "config.toml").write_text(base + 'fusion_par = "proprietaire"\n'); C3 = charger_courtier(i, "courtier_mv3")
    livrer("cinq", {"cinq.txt": "cinq\n", "CHANGELOG.md": JOURNAL.format(v="1.2.0", quoi="cinq")})
    chef(False).ecritures["fusionner"][1](["cinq"])                  # la fusion validée (outil du chef, comme plus haut)
    boite = i / "agents/master/courrier"; (boite / "encours").mkdir(parents=True, exist_ok=True)
    def appel(n, outil, verbe, args):
        f = boite / "encours" / f"{n}.json"; f.write_text(json.dumps({"outil": outil, "verbe": verbe, "args": args}))
        C3.traiter("master", f, {}); return json.loads((boite / "reponses" / f"{n}.json").read_text())
    r = appel("e1", "berger-chef", "etiqueter", ["1.2.0"])
    V = i / "courtier/validations"
    dire(r.get("ok") and "sans_validation" in r and git(forge, "rev-parse", "v1.2.0^{commit}").stdout.strip() == forge_main()
         and not (V.exists() and list(V.glob("*.json"))), "courtier : etiqueter sur la fusion validée → fait SANS validation, aucune demande en attente")
    dire("sans validation" in (i / "courtier/appels.log").read_text() and "SANS validation" in "".join(p.read_text() for p in (i / "agents/master/memory").glob("*.md")),
         "courtier : tracé (appels.log, journal de l'agent)")
    (depot / "CHANGELOG.md").write_text(JOURNAL.format(v="1.3.0", quoi="hors fusion")); git(depot, "add", "-A")
    git(depot, "commit", "-qm", "docs: 1.3.0 sans fusion"); git(depot, "push", "-q", "origin", "main")
    r = appel("e2", "berger-chef", "etiqueter", ["1.3.0"])
    dire(r.get("ok") and r.get("en_attente") and git(forge, "rev-parse", "-q", "--verify", "v1.3.0").returncode != 0,
         "courtier : etiqueter un commit qui n'est pas une fusion → validation comme avant, rien posé")
    r = appel("e3", "berger-chef", "etiqueter", ["1.2"])
    dire(not r.get("ok") and "SemVer" in r.get("erreur", ""), "courtier : version invalide → refus clair (comme avant)")

# ── 6. berger installer : retour arrière automatique ──
with tempfile.TemporaryDirectory() as t:
    m = Path(t); forge, i, graine = m / "projets/berger.git", m / "berger", m / "graine"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(graine)], capture_output=True)
    _produit.copier(SRC, graine, ("bin", "courtier", "commun"))
    git(graine, "add", "-A"); git(graine, "commit", "-qm", "produit"); git(graine, "push", "-q", "origin", "main")
    subprocess.run(["git", "clone", "-q", str(forge), str(i)], capture_output=True)
    (m / "coffre.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Zephyrin"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    d = i / "agents/admin"; (d / "memory").mkdir(parents=True)
    (d / "agent.conf").write_text("nom = Admin\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\n")
    b = m / ".local/bin"; b.mkdir(parents=True)
    (b / "systemd-run").write_text(f'#!/bin/sh\necho "$@" >> "{m}/systemd-run.log"\nexit 0\n')
    (b / "systemctl").write_text(f'#!/bin/sh\necho "$@" >> "{m}/systemctl.log"\n'
                                 f'if [ "$2" = is-active ]; then cat "{m}/etat-courtier" 2>/dev/null || echo active; fi\nexit 0\n')
    for x in ("systemd-run", "systemctl"): os.chmod(b / x, 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": str(m / "absent"), "BERGER_NOTIFY_SEND": str(m / "absent"),
           "BERGER_CONTROLE_PAUSE": "0", **ENV_GIT}
    env.pop("BERGER_AGENT", None)
    sonde = subprocess.run([sys.executable, "-c", "import runpy,shutil;runpy.run_path(%r,run_name='x');print(shutil.which('systemctl'));print(shutil.which('systemd-run'))"
                            % str(i / "bin/berger")], env=env, capture_output=True, text=True)
    if sonde.stdout.split() != [str(b / "systemctl"), str(b / "systemd-run")]: sys.exit(f"ARRÊT : Berger prendrait le vrai systemctl ({sonde.stdout.split() or sonde.stderr[-200:]})")
    berger = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=300)
    tete = lambda: git(i, "rev-parse", "HEAD").stdout.strip()
    log = lambda: (i / "courtier/installations.log").read_text() if (i / "courtier/installations.log").exists() else ""
    notes = lambda: (i / "courtier/notifications.log").read_text() if (i / "courtier/notifications.log").exists() else ""
    def pousser(nom, texte):
        (graine / nom).parent.mkdir(parents=True, exist_ok=True); (graine / nom).write_text(texte)
        git(graine, "add", "-A"); git(graine, "commit", "-qm", f"ajoute {nom}"); git(graine, "push", "-q", "origin", "main")

    avant = tete(); pousser("commun/nouveau.md", "une nouveauté\n")
    r = berger("installer", str(forge), "main")
    lance = (m / "systemd-run.log").read_text() if (m / "systemd-run.log").exists() else ""
    dire(r.returncode == 0 and tete() == git(forge, "rev-parse", "main").stdout.strip() and (i / "commun/nouveau.md").is_file(),
         "installer : avance rapide, HEAD = main de la forge" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr)[-300:]}"))
    dire("verifier-depot : dépôt propre" in r.stdout and "regenerer" in r.stdout and (d / "AGENTS.md").is_file(), "installer : verifier-depot puis regenerer joués")
    dire(f"courtier redemarrer --controle {avant}" in lance and "--collect" in lance, "installer : redémarrage DÉTACHÉ du courtier, contrôlé (commit d'avant passé)")
    dire("\tinstallée\t" in log(), "installer : tracé dans courtier/installations.log")

    # redémarrage contrôlé : actif → rien à défaire ; inactif → retour arrière, redémarrage sur l'ancien code
    installe = tete(); r = berger("courtier", "redemarrer", "--controle", avant)
    dire(r.returncode == 0 and tete() == installe and "\tcourtier redémarré\t" in log(), "redémarrage contrôlé : courtier actif → installation gardée, tracé")
    dire("try-restart berger-interface" in (m / "systemctl.log").read_text(),
         "redémarrage contrôlé : l'interface web relit son serveur (try-restart : rien n'est démarré s'il était arrêté)")
    (m / "etat-courtier").write_text("failed\n"); (m / "systemctl.log").unlink()
    r = berger("courtier", "redemarrer", "--controle", avant)
    redemarrages = (m / "systemctl.log").read_text().count("restart berger-courtier")
    dire("try-restart berger-interface" in (m / "systemctl.log").read_text(), "retour arrière : l'interface web repart sur l'ancien code")
    dire(r.returncode == 1 and tete() == avant and not (i / "commun/nouveau.md").exists() and redemarrages == 2,
         "courtier inactif après redémarrage → RETOUR ARRIÈRE au commit d'avant (prouvé), regenerer, redémarré sur l'ancien code")
    dire("ÉCHEC" in log().splitlines()[-1] and "retour arrière fait" in log().splitlines()[-1] and "installation en échec" in notes(),
         "retour arrière tracé (installations.log) et notifié au propriétaire")
    (m / "etat-courtier").unlink()
    dire(berger("courtier", "redemarrer", "--controle", "pas-un-commit").returncode == 2, "--controle exige un commit complet")

    # verifier-depot rouge (le nom du propriétaire dans le produit) → retour arrière, rien redémarré
    pousser("commun/fuite.md", "Écrit pour Zephyrin\n"); (m / "systemd-run.log").unlink(missing_ok=True)
    r = berger("installer", str(forge), "main")
    dire(r.returncode != 0 and "verifier-depot en échec" in r.stdout and tete() == avant and not (i / "commun/fuite.md").exists(),
         "verifier-depot rouge → RETOUR ARRIÈRE automatique : HEAD = commit d'avant (vérifié), fichiers d'avant")
    dire(not (m / "systemd-run.log").exists() and "retour arrière fait" in r.stdout and "ÉCHEC, retour arrière" in log().splitlines()[-1],
         "verifier-depot rouge : courtier NON redémarré, retour arrière tracé")
    dire((i / "config.toml").is_file() and (d / "agent.conf").is_file(), "retour arrière : config et agents (non suivis) intacts")

    # avance rapide refusée (forge sans lien) → rien changé
    autre = m / "autre.git"; subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(autre)])
    g2 = m / "g2"; subprocess.run(["git", "clone", "-q", str(autre), str(g2)], capture_output=True)
    (g2 / "x.md").write_text("x\n"); git(g2, "add", "-A"); git(g2, "commit", "-qm", "x"); git(g2, "push", "-q", "origin", "main")
    r = berger("installer", str(autre), "main")
    dire(r.returncode != 0 and "avance rapide refusée" in r.stdout and tete() == avant and "\trefusée\t" in log().splitlines()[-1],
         "avance rapide refusée → rien changé (HEAD d'avant), tracé")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
