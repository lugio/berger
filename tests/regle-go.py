#!/usr/bin/env python3
"""Tests de la spec 2026-10-15-regle-go (docs/plans/2026-10-15-regle-go-spec.md) — sans modèle, installation JETABLE et
FAUX Herdr, joués avec `moteur = claude` PUIS `moteur = codex` (rien n'y est propre à un moteur).
Point (d), vécu le 15/10 : une demande renvoyée exprès (spec seule) relançait son développeur sans fin, même après
« Terminé ». Vérifie : renvoyée + checklist en cours ou finie AVANT le renvoi → rappel (inchangé) ; finie APRÈS le renvoi
(en place ou rangée dans historique/) → plus de rappel au développeur, UNE alerte au chef ; verbes du chef « attente » et
« reprendre » (refus, aucun rappel ni alerte de renvois, fusion refusée en attente, reprise → à relire).
Point (b) : `equipe go` (refus, marquage « demandé », inscription après la décision du propriétaire, spec changée), ouverture
refusée sans go AVANT de rien créer (mots, cas déclarés, go demandé), « Hors go : » tracé et signalé, mission portant la
référence du go, go recopié dans la demande de fusion et recontrôlé à la fusion, regle_go = false.
Usage : python3 tests/regle-go.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, importlib.util, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit, _herdr_api_factice

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["FAUX_HERDR"]; etat = json.load(open(T + "/etat.json")); a = sys.argv[1:]
if a == ["agent", "prompt"]:                                              # API Herdr (adaptateur) : corps sur stdin
    d = json.load(sys.stdin); a += [d["target"], d["text"]]
with open(T + "/appels.log", "a") as f: f.write(json.dumps(a) + "\n")
r = {}
if a[:2] == ["agent", "list"]: r = {"agents": [{"name": n, "pane_id": p} for n, p in etat["agents"].items()]}
elif a[:2] == ["pane", "get"]:
    r = {"pane": {"pane_id": a[2], "agent_status": etat["statuts"].get(a[2], "idle")}} if a[2] in etat["statuts"] else {}
elif a[:2] == ["workspace", "list"]: r = {"workspaces": [{"workspace_id": w} for w in etat.get("espaces", [])]}
elif a[:2] == ["agent", "prompt"] and a[2] not in etat["agents"]: print('{"error":{"code":"agent_not_found"}}'); sys.exit(1)
print(json.dumps({"result": r}))
'''


def installation(t, moteur):
    _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    (t / "coffre.json").write_text("{}")
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n\n[missions]\nmax = 3\n\n'
                                   '[supervision]\nsans_avancee_min = 0\nescalade_min = 0\nmax_renvois = 2\n\n'
                                   f'[equipes.p]\ndepot = "{t}/depot"\nchef_projet = "chef"\ncoordinateur = "coord"\nports = [1]\n')
    panes = {"chef": "p1", "coord": "p2", "p-dev": "p3"}
    for a, p in panes.items():
        d = t / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = {moteur}\npanneaux = {moteur}\nheures = aucune\n"
                                      + ("projet = p\nsujet = dev\ncopie = /nulle-part\nbranche = equipe/dev\nport = 1\n" if a == "p-dev" else ""))
        (d / ".herdr.json").write_text(json.dumps({"workspace": "w-" + a, "agents": {moteur: p}}))
    (t / "agents/p-dev/MISSION.md").write_text(f"# Mission confiée par chef — test\nmoteur : {moteur}\n\nfaire x\n")
    vieux = time.time() - 7200
    os.utime(t / "agents/p-dev/MISSION.md", (vieux, vieux))
    (t / "faux").mkdir(); (t / "faux/herdr").write_text(FAUX_HERDR); (t / "faux/notify-send").write_text("#!/bin/sh\nexit 0\n")
    for x in ("herdr", "notify-send"): os.chmod(t / "faux" / x, 0o755)
    etat = {"agents": {f"{a}-{moteur}": p for a, p in panes.items()}, "statuts": {p: "idle" for p in panes.values()},
            "espaces": [f"w-{a}" for a in panes]}
    (t / "faux/etat.json").write_text(json.dumps(etat))
    return _herdr_api_factice.installer({**os.environ, "BERGER_DIR": str(t), "FAUX_HERDR": str(t / "faux"), "PATH": f"{t}/faux:" + os.environ["PATH"],
            "BERGER_HERDR": str(t / "faux/herdr"), "BERGER_NOTIFY_SEND": str(t / "faux/notify-send")})


def charger_chef(t):
    spec = importlib.util.spec_from_file_location("outil_equipe_chef", t / "courtier/outils/equipe_chef.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    o = m.Outil({"depot": str(t / "depot"), "principale": "main", "demandes": str(t / "equipes/p/demandes"), "chef_projet": "chef",
                 "projet": "p"}, None, None)
    o.contexte = {"agent": "chef", "dossier": str(t / "agents/chef")}
    return o


def erreur(f, args):
    try: f(args); return ""
    except (ValueError, RuntimeError) as e: return str(e)


for moteur in ("claude", "codex"):
    with tempfile.TemporaryDirectory() as t:
        t = Path(t); env = installation(t, moteur)
        sonde = subprocess.run([sys.executable, "-c", f"import runpy,sys;sys.argv=['b'];m=runpy.run_path({str(t / 'bin/berger')!r},run_name='x');print(m['HERDR'])"],
                               env=env, capture_output=True, text=True)
        if sonde.stdout.strip() != str(t / "faux/herdr"): sys.exit(f"ARRÊT : Berger n'utiliserait pas le faux Herdr ({sonde.stdout.strip() or sonde.stderr[-200:]})")

        def superviser(fois=1, oublier=True):
            for _ in range(fois):
                if oublier: (t / "equipes/.relances.json").unlink(missing_ok=True)      # délai entre deux rappels levé
                subprocess.run([sys.executable, str(t / "bin/berger"), "superviser"], env=env, capture_output=True, text=True, timeout=60)

        def messages(a):
            f = t / "faux/appels.log"
            l = [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []
            return [x[3] for x in l if x[:3] == ["agent", "prompt", f"{a}-{moteur}"]]

        dem = t / "equipes/p/demandes"; dem.mkdir(parents=True)
        il_y_a = lambda minutes: (datetime.datetime.now() - datetime.timedelta(minutes=minutes)).isoformat(timespec="minutes")
        def renvoyee(quand):
            (dem / "dev.json").write_text(json.dumps({"sujet": "dev", "branche": "equipe/dev", "commit": "abc", "agent": "p-dev", "etat": "renvoyée",
                                                      "renvoyee": quand, "motif": "corrige y", "renvois": 1}))
        ck = t / "agents/p-dev/CHECKLIST.md"
        def date(f, minutes): x = time.time() - minutes * 60; os.utime(f, (x, x))
        rappels = lambda depuis: [m for m in messages("p-dev")[depuis:] if "RENVOYÉE" in m]
        alertes = lambda depuis: [m for m in messages("chef")[depuis:] if "sans redemander la fusion" in m]

        # 1. renvoyée, checklist en cours → rappel (comportement inchangé)
        renvoyee(il_y_a(30)); ck.write_text("# correction\n- [ ] corriger\n")
        superviser()
        dire(len(rappels(0)) == 1, f"[{moteur}] renvoyée, checklist en cours → le développeur est rappelé")

        # 2. checklist « Terminé » écrite AVANT le renvoi (cas normal : demande de fusion puis Terminé) → rappel
        ck.write_text("# x\n- [x] fait\nTerminé 2026-10-15 10:00\n"); date(ck, 60)
        n = len(messages("p-dev")); superviser()
        dire(len(rappels(n)) == 1, f"[{moteur}] « Terminé » écrit AVANT le renvoi → le vrai renvoi est toujours rappelé")

        # 3. « Terminé » APRÈS le renvoi, sans redemande → plus de rappel au développeur, UNE alerte au chef
        ck.write_text("# x\n- [x] fait\nTerminé 2026-10-15 18:00\n"); date(ck, 5)
        n, nc = len(messages("p-dev")), len(messages("chef"))
        for _ in range(3): superviser(oublier=False); (t / "equipes/.relances.json").write_text(json.dumps({
            k: v for k, v in json.loads((t / "equipes/.relances.json").read_text()).items() if "fini-sans-redemande" in k}))
        dire(not rappels(n), f"[{moteur}] « Terminé » APRÈS le renvoi → aucun rappel au développeur")
        a = alertes(nc)
        dire(len(a) == 1 and "attente --fichier .transport/requete.json, JSON : dev" in a[0], f"[{moteur}] … et UNE seule alerte au chef (sur trois passages), qui propose « attente »")

        # 4. même chose, checklist rangée dans historique/ par le planificateur
        ck.unlink(); (t / "agents/p-dev/historique").mkdir(exist_ok=True)
        rangee = t / "agents/p-dev/historique" / f"{datetime.datetime.now():%Y-%m-%d_%H%M}_x.md"
        rangee.write_text("# x\n- [x] fait\nTerminé\n")
        renvoyee(il_y_a(10)); n = len(messages("p-dev")); superviser(2)
        dire(not rappels(n), f"[{moteur}] « Terminé » après le renvoi, rangé dans historique/ → aucun rappel au développeur")
        rangee.unlink()
        n = len(messages("p-dev")); superviser()
        dire(len(rappels(n)) == 1, f"[{moteur}] plus de checklist finie après le renvoi → rappel de nouveau")
        # date de renvoi illisible : on ne sait pas → rappel comme avant (jamais un renvoi oublié)
        ck.write_text("# x\nTerminé\n"); renvoyee("x"); n = len(messages("p-dev")); superviser()
        dire(len(rappels(n)) == 1, f"[{moteur}] date de renvoi illisible → rappel comme avant")

        # 5. verbes du chef : attente / reprendre
        chef = charger_chef(t); renvoyee(il_y_a(10)); ck.write_text("# x\n- [ ] corriger\n")
        dire("motif" in erreur(chef.verbes["attente"], ["dev", "court"]), f"[{moteur}] attente : motif de moins de 10 caractères → refus")
        dire("aucune demande" in erreur(chef.verbes["attente"], ["inconnu", "spec seule, avec le code plus tard"]), f"[{moteur}] attente : sujet inconnu → refus")
        dire("en attente" in erreur(chef.verbes["reprendre"], ["dev"]), f"[{moteur}] reprendre une demande qui n'est pas en attente → refus")
        r = chef.verbes["attente"](["dev", "spec seule, à fusionner avec le code plus tard"])
        d = json.loads((dem / "dev.json").read_text())
        dire(d["etat"] == "en attente" and d["motif_attente"].startswith("spec seule") and d["attente_par"] == "chef" and r.get("en attente") == "dev",
             f"[{moteur}] attente → demande « en attente », motif et auteur inscrits")
        dire(any(x.get("etat") == "en attente" and x.get("motif_attente") for x in chef.verbes["demandes"]([])), f"[{moteur}] « demandes » montre l'attente et son motif")
        dire("en attente" in erreur(chef.verbes["attente"], ["dev", "deuxième mise en attente"]), f"[{moteur}] attente d'une demande déjà en attente → refus")
        try: chef.controler(d); fusion = "acceptée"
        except ValueError as e: fusion = str(e)
        dire("à relire" in fusion, f"[{moteur}] demande en attente → la fusion est refusée")
        d["renvois"] = 5; (dem / "dev.json").write_text(json.dumps(d))
        n, nc, no = len(messages("p-dev")), len(messages("chef")), len(messages("coord"))
        (t / ".supervision.json").unlink(missing_ok=True); superviser(2)
        dire(len(messages("p-dev")) == n, f"[{moteur}] en attente → aucun rappel au développeur (ni renvoi, ni « n'avance plus »)")
        dire(len(messages("chef")) == nc and len(messages("coord")) == no, f"[{moteur}] en attente → ni rappel de relecture ni alerte de renvois au chef ou au coordinateur")
        r = chef.verbes["reprendre"](["dev"]); d = json.loads((dem / "dev.json").read_text())
        dire(d["etat"] == "à relire" and "motif_attente" not in d, f"[{moteur}] reprendre → de nouveau « à relire »")
        superviser()
        dire(any("attend ta relecture" in m for m in messages("chef")[nc:]), f"[{moteur}] reprise → le chef est de nouveau rappelé pour la relecture")
        d["etat"] = "fusionnée"; (dem / "dev.json").write_text(json.dumps(d))
        dire("rien à mettre en attente" in erreur(chef.verbes["attente"], ["dev", "trop tard pour garer"]), f"[{moteur}] attente d'une demande fusionnée → refus")
        # le développeur n'a pas l'outil du chef : le courtier le lui refuse (droits calculés depuis [equipes.p])
        code = (f"import runpy,sys;sys.argv=['courtier'];g=runpy.run_path({str(t / 'courtier/courtier')!r},run_name='essai');"
                "print('p-chef' in g['droits_equipe']('p-dev'), 'p-chef' in g['droits_equipe']('chef'))")
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
        dire(r.stdout.strip().splitlines()[-1:] == ["False True"], f"[{moteur}] attente/reprendre : outil du chef seul, jamais du développeur")
# ───────────── (b) le go inscrit : equipe go, ouverture, demande de fusion, fusion ─────────────
def git(d, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True)


SPEC = "# Spec essai\n\nConstat, comportement, refus, tests.\n"
for moteur in ("claude", "codex"):
    with tempfile.TemporaryDirectory() as t:
        m = Path(t); i = m / "berger"; i.mkdir()
        for f in subprocess.run(["git", "-C", str(SRC), "ls-files"], capture_output=True, text=True).stdout.split():
            if (SRC / f).is_file(): (i / f).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(SRC / f, i / f)
        forge, depot = m / "forge.git", m / "depot"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)]); subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
        (depot / "docs").mkdir(); (depot / "docs/spec.md").write_text(SPEC); (depot / "docs/fuite.md").write_text("# x\nValeur-Factice-Du-Coffre\n")
        git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
        (m / "coffre.json").write_text(json.dumps({"essai": {"mot_de_passe": "Valeur-Factice-Du-Coffre"}}))
        (i / "config.toml").write_text(f'proprietaire = "Proprio"\ncoffre = "{m}/coffre.json"\n[missions]\nmax = 9\n'
                                       f'[equipes.p]\ndepot = "{depot}"\ncopies = "{m}/copies"\nmoteur = "{moteur}"\nports = [5301, 5302, 5303, 5304, 5305, 5306]\n'
                                       'chef_projet = "chef"\ncoordinateur = "coord"\n')
        for a in ("coord",):                                     # le chef n'est pas créé : son espace Herdr serait ouvert à l'ouverture
            d = i / "agents" / a; (d / "memory").mkdir(parents=True)
            (d / "agent.conf").write_text(f"nom = {a}\nmoteur = {moteur}\npanneaux = {moteur}\nheures = aucune\n")
        # sans Herdr : la mission échoue APRÈS l'agent ; l'interpréteur du test en tête : le courtier relance bin/berger par
        # « python3 » (shebang, _transport) et /usr/bin/python3 peut être antérieur à 3.11 (runner ubuntu-22.04 : 3.10, sans tomllib)
        env = {**{k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}, "HOME": str(m), "BERGER_DIR": str(i), "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin"}

        def berger(*a):                                          # transport privé : equipe/mission/projet en tableau JSON sur stdin
            prive = a[0] in ("mission", "equipe", "projet", "message-deposer")
            r = subprocess.run([sys.executable, str(i / "bin/berger"), *(["--stdin"] if prive else a)], input=json.dumps(list(a)) if prive else None,
                               env=env, capture_output=True, text=True, timeout=300)
            return r.returncode, r.stdout + r.stderr
        cree = lambda s: (i / f"agents/p-{s}").exists() or (m / f"copies/p-{s}").exists()
        go = i / "equipes/p/go"; M = f"[{moteur}]"
        sp0 = importlib.util.spec_from_file_location("p_", i / "courtier/outils/_portes.py"); pm_ = importlib.util.module_from_spec(sp0); sp0.loader.exec_module(pm_)

        c, o = berger("equipe", "ouvrir", "p", "mdp", "changer le mot de passe du compte de service", "--par", "chef", "--moteur", moteur)
        dire(c != 0 and "règle de go" in o and "mots : mot de passe" in o and not cree("mdp"), f"{M} mission avec « mot de passe », sans go → refus, RIEN créé")
        # cas 1 complété le 16/10 (remarque de l'agent d'infrastructure) : « identifiants du portail fiscal » passait sans go
        c, o = berger("equipe", "ouvrir", "p", "fiscal", "récupérer les avis avec les identifiants du portail fiscal du cabinet", "--par", "chef", "--moteur", moteur)
        dire(c != 0 and "mots : identifiants" in o and not cree("fiscal"), f"{M} mission « identifiants du portail fiscal », sans go → refus, RIEN créé")
        sp = importlib.util.spec_from_file_location("p0", i / "courtier/outils/_portes.py"); p0 = importlib.util.module_from_spec(sp); sp.loader.exec_module(p0)
        for texte, mot in (("changer le MDP du compte", "mdp"), ("renouveler le jeton du guichet", "jeton"), ("le token OAuth expire", "token"),
                           ("poser la clé d'API du registre", "clé d'api"), ("poser la clé d’API du registre", "clé d’api"),
                           ("lire les credentials du service", "credentials"), ("vérifier l'identifiant de connexion", "identifiant")):
            dire(mot in p0.mots_go(texte), f"{M} mot du cas 1 reconnu : « {texte} » → {mot}")
        dire(not p0.mots_go("tokenisation du texte, identifiantation, mdpx"), f"{M} mots entiers seulement : « tokenisation » n'est pas « token »")
        c, o = berger("equipe", "ouvrir", "p", "secr", "ranger le secrétariat\nRègle de go : cas 1", "--par", "chef", "--moteur", moteur)
        dire(c != 0 and "déclaré : cas 1" in o and not cree("secr"), f"{M} « Règle de go : cas 1 » déclaré par le chef, sans go → refus")
        c, o = berger("equipe", "ouvrir", "p", "secr", "ranger le secrétariat des dossiers", "--par", "chef", "--moteur", moteur)
        dire("règle de go" not in o and cree("secr"), f"{M} « secrétariat » n'est pas « secret » : sujet non marqué, ouvert comme avant")
        c, o = berger("equipe", "ouvrir", "p", "lect", "lire la production en lecture seule\nHors go : lecture seule, aucun changement en production",
                      "--par", "chef", "--moteur", moteur)
        h = json.loads((go / "lect.hors-go.json").read_text()) if (go / "lect.hors-go.json").is_file() else {}
        ech = (i / "courtier/echanges.jsonl").read_text() if (i / "courtier/echanges.jsonl").exists() else ""
        dire(cree("lect") and h.get("raison", "").startswith("lecture seule") and h.get("par") == "chef", f"{M} « Hors go : <raison> » → ouvert, raison tracée")
        dire('"hors go"' in ech and "coord" in ech, f"{M} hors go → dans Échanges, adressé au coordinateur (alerte)")
        c, o = berger("equipe", "ouvrir", "p", "court", "le mot de passe\nHors go : trop court", "--par", "chef", "--moteur", moteur)
        dire(c != 0 and not cree("court"), f"{M} raison « Hors go » de moins de 20 caractères → refus")

        c, o = berger("equipe", "go", "p", "mdp", "1", "docs/spec.md", "--par", "p-secr", "--essai")
        dire(c != 0 and "seuls le chef" in o and not (go / "mdp.json").exists(), f"{M} equipe go par un développeur → refus")
        # défaut vu le 16/10 : spec poussée SEULEMENT sur la forge (branche du sujet), le dépôt du chef ne l'a jamais récupérée
        sp_ = "docs/spec-forge.md"; autre = m / "autre"; subprocess.run(["git", "clone", "-q", str(forge), str(autre)], capture_output=True)
        git(autre, "checkout", "-q", "-b", "equipe/forge"); (autre / sp_).write_text(SPEC + "seulement sur la forge\n")
        git(autre, "add", "-A"); git(autre, "commit", "-qm", "spec sur la branche"); git(autre, "push", "-q", "origin", "equipe/forge")
        dire(git(depot, "rev-parse", "--verify", "--quiet", "origin/equipe/forge").returncode != 0, f"{M} (préparation) le dépôt du chef ne connaît pas la branche")
        c, o = berger("equipe", "go", "p", "forge", "1", sp_, "--par", "chef", "--essai")
        emp = pm_.empreinte((autre / sp_).read_text()) if (autre / sp_).is_file() else ""
        g = json.loads((go / "forge.json").read_text()) if (go / "forge.json").is_file() else {}
        dire(c == 0 and "seulement sur la forge" in o and "equipe/forge" in o and g.get("empreinte") == emp and len(emp) == 64,
             f"{M} spec poussée seulement sur la forge → trouvée, empreinte identique à celle du fichier")
        c, o = berger("equipe", "go", "p", "forge", "1", "docs/absente-aussi.md", "--par", "chef", "--essai")
        dire(c != 0 and "introuvable" in o, f"{M} spec absente de la forge → refus comme avant")
        (go / "forge.json").unlink(missing_ok=True)
        for cas, spec, attendu, nom in (("6", "docs/spec.md", "cas : 1 à 5", "cas hors 1..5"), ("1", "../x.md", "spec : un chemin", "chemin avec .."),
                                        ("1", "docs/absente.md", "introuvable", "spec absente"), ("1", "docs/fuite.md", "valeur du coffre", "spec avec un secret")):
            c, o = berger("equipe", "go", "p", "mdp", cas, spec, "--par", "chef", "--essai")
            dire(c != 0 and attendu in o and not (go / "mdp.json").exists(), f"{M} equipe go : {nom} → refus, rien marqué")
        c, o = berger("equipe", "go", "p", "mdp", "1", "docs/spec.md", "--par", "chef", "--essai")
        g = json.loads((go / "mdp.json").read_text()) if (go / "mdp.json").is_file() else {}
        dire(c == 0 and "GO du propriétaire" in o and "Constat, comportement" in o and g.get("etat") == "demandé",
             f"{M} demande de go : aperçu (titre, début, empreinte), sujet marqué « demandé »")
        c, o = berger("equipe", "ouvrir", "p", "mdp", "tâche anodine\nHors go : rien à voir avec la règle de go ici", "--par", "chef", "--moteur", moteur)
        dire(c != 0 and "go demandé" in o and not cree("mdp"), f"{M} go demandé, pas inscrit : « Hors go » ne lève rien → refus")
        # la décision du propriétaire, simulée : la demande n° 7 est « en cours d'exécution » par le courtier (fichier .execution)
        v = i / "courtier/validations"; v.mkdir(parents=True, exist_ok=True)
        (v / "7.json").write_text(json.dumps({"n": 7, "agent": "chef", "outil": "equipe", "verbe": "go", "args": ["p", "mdp", "1", "docs/spec.md"]}))
        (v / "7.execution").write_text("")
        (depot / "docs/spec.md").write_text(SPEC + "ajout après la demande\n"); git(depot, "commit", "-qam", "spec changée"); git(depot, "push", "-q", "origin", "main")
        c, o = berger("equipe", "go", "p", "mdp", "1", "docs/spec.md", "--par", "chef")
        dire(c != 0 and "a changé depuis la demande" in o and json.loads((go / "mdp.json").read_text())["etat"] == "demandé",
             f"{M} spec changée entre la demande et la décision → rien inscrit")
        git(depot, "revert", "--no-edit", "HEAD"); git(depot, "push", "-q", "origin", "main")
        c, o = berger("equipe", "go", "p", "mdp", "1", "docs/spec.md", "--par", "chef")
        g = json.loads((go / "mdp.json").read_text())
        dire(c == 0 and g.get("etat") == "inscrit" and g.get("validation") == 7 and g.get("par") == "Proprio",
             f"{M} décision → go INSCRIT, n° de la validation (7), par le propriétaire")
        c, o = berger("equipe", "go", "p", "mdp", "1", "docs/spec.md", "--par", "chef", "--essai")
        dire(c != 0 and "déjà inscrit" in o, f"{M} même spec, même empreinte → « déjà inscrit »")
        c, o = berger("equipe", "ouvrir", "p", "mdp", "changer le mot de passe du compte de service", "--par", "chef", "--moteur", moteur)
        mi = (i / "agents/p-mdp/MISSION.md").read_text() if (i / "agents/p-mdp/MISSION.md").exists() else ""
        dire(cree("mdp") and "Go du propriétaire : validation n° 7, spec docs/spec.md" in (mi + o), f"{M} go inscrit → ouvert, la mission porte la référence du go")

        # le courtier : l'écriture « go » n'est jamais proposée à un agent (le propriétaire seul) ; « domaine » reste
        code = (f"import runpy,sys;sys.argv=['courtier'];g=runpy.run_path({str(i / 'courtier/courtier')!r},run_name='essai');"
                "print(g['OBJETS']['equipe'].valideur('go', ['p','mdp','1','docs/spec.md']), 'go' in g['ECRITURES']['equipe'], 'domaine' in g['ECRITURES']['equipe'])")
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
        dire(r.stdout.strip().splitlines()[-1:] == ["None True True"],
             f"{M} courtier : écriture go au propriétaire seul ; domaine toujours là ({r.stdout.strip()[-80:] or r.stderr.strip()[-200:]})")

        # le chemin complet par le courtier : le coordinateur DEMANDE le go → une validation en attente, au propriétaire seul
        # (défaut trouvé le 15/10 en jouant toutes les suites : le message de réponse plantait, ce contrôle manquait)
        code = (f"import importlib.machinery, importlib.util, json, time\n"
                f"l = importlib.machinery.SourceFileLoader('c', {str(i / 'courtier/courtier')!r}); s = importlib.util.spec_from_loader('c', l)\n"
                "C = importlib.util.module_from_spec(s); l.exec_module(C)\n"
                "def demande(agent, *a):\n"
                f"    enc = __import__('pathlib').Path({str(i / 'agents')!r}) / agent / 'courrier/encours'; enc.mkdir(parents=True, exist_ok=True)\n"
                "    f = enc / f'go-{time.time_ns()}.json'; f.write_text(json.dumps({'outil': 'equipe', 'verbe': 'go', 'args': list(a)})); C.traiter(agent, f, {})\n"
                "    for _ in range(300):\n"
                "        if (f.parent.parent / 'reponses' / f.name).exists(): break\n"
                "        time.sleep(0.1)\n"
                "    return json.loads((f.parent.parent / 'reponses' / f.name).read_text())\n"
                "r = demande('coord', 'p', 'neuf', '1', 'docs/spec.md')\n"
                "v = json.loads((C.VALIDATIONS / f\"{r.get('en_attente')}.json\").read_text()) if r.get('en_attente') else {}\n"
                "print(json.dumps({'coord': r, 'valideur': v.get('valideur', 'absent'), 'dev': demande('p-secr', 'p', 'neuf', '1', 'docs/spec.md')}))\n")
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
        try: x = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError): x = {"erreur": (r.stdout + r.stderr)[-300:]}
        dire(x.get("coord", {}).get("ok") and x["coord"].get("en_attente") and "RIEN n'est inscrit" in x["coord"].get("message", "")
             and x.get("valideur") is None and (go / "neuf.json").is_file(),
             f"{M} courtier : le coordinateur demande le go → validation en attente, valideur = le propriétaire seul, sujet marqué ({str(x)[:160]})")
        dire(x.get("dev", {}).get("ok") is False, f"{M} courtier : un développeur ne demande pas de go")

        # la demande de fusion : le go recopié comme les portes ; refus si la spec a changé, ou go seulement demandé
        spec_ok = lambda chemin: SPEC
        sp = importlib.util.spec_from_file_location("p_", i / "courtier/outils/_portes.py"); pm = importlib.util.module_from_spec(sp); sp.loader.exec_module(pm)
        r = pm.go_de_la_demande(go, "mdp", "", spec_ok)
        dire(r and r["validation"] == 7 and r["spec_dans_branche"] and r["empreinte"] == g["empreinte"], f"{M} demande : le go (n°, spec, empreinte) est recopié")

        def refus(*a):
            try: pm.go_de_la_demande(*a); return "acceptée"
            except ValueError as e: return str(e)
        dire("a changé depuis le go n° 7" in refus(go, "mdp", "", lambda c: SPEC + "modifiée\n"), f"{M} demande : spec modifiée dans la branche après le go → refus")
        (go / "autre.json").write_text(json.dumps({"etat": "demandé", "spec": "docs/spec.md", "empreinte": "x"}))
        dire("sans go inscrit" in refus(go, "autre", "", spec_ok), f"{M} demande : go demandé mais pas inscrit → refus")
        dire("mots : pare-feu" in refus(go, "neuf", "ouvrir le pare-feu", spec_ok), f"{M} demande d'un sujet ouvert avant ce contrôle, mission marquée, sans go → refus (rattrapage)")
        dire(pm.go_de_la_demande(go, "lect", "lire la production", spec_ok) == {"hors_go": h.get("raison")}, f"{M} demande hors go : la raison est recopiée")
        dire(pm.go_de_la_demande(go, "secr", "ranger le secrétariat", spec_ok) is None, f"{M} demande hors règle de go : rien ne change")
        # la fusion recontrôle : une demande sans le go inscrit (faite avant lui) est refusée
        sc = importlib.util.spec_from_file_location("c_", i / "courtier/outils/equipe_chef.py"); ch = importlib.util.module_from_spec(sc); sc.loader.exec_module(ch)
        chef = ch.Outil({"depot": str(depot), "demandes": str(i / "equipes/p/demandes"), "projet": "p"}, None, None)

        def fusion(d):
            try: chef.controler_go(d); return "acceptée"
            except ValueError as e: return str(e)
        dire("ne porte pas le go inscrit" in fusion({"sujet": "mdp"}), f"{M} fusion : demande sans le go inscrit → refus")
        dire(fusion({"sujet": "mdp", "go": r}) == "acceptée", f"{M} fusion : demande qui porte le go inscrit → passe")
        # retour arrière : regle_go = false coupe le contrôle, sans toucher aux fichiers de go
        (i / "config.toml").write_text((i / "config.toml").read_text() + "regle_go = false\n")
        c, o = berger("equipe", "ouvrir", "p", "pf", "ouvrir le pare-feu", "--par", "chef", "--moteur", moteur)
        dire(cree("pf") and (go / "mdp.json").is_file(), f"{M} regle_go = false : contrôle coupé, fichiers de go gardés")
print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
