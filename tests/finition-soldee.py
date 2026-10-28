#!/usr/bin/env python3
"""Tests de deux défauts mesurés le 13/10/2026 sur un chef de projet (docs/plans/2026-10-13-finition-soldee-spec.md) :
1) RELANCE FAUSSE — la finition du chef (branche à sujet différent, ex. `<sujet>-fin`) reprend la livraison « à finir » du
   développeur ; sa FUSION doit solder cette livraison (« fusionnée par la finition <branche> »), la supervision ne relance
   jamais une livraison reprise ou soldée, et ses relances ne comptent pas dans la limite de débit d'`ecrire`.
2) PROPOSITION APPLIQUÉE NON PRISE — après `berger agent appliquer`, l'agent AU REPOS est relancé ; occupé, la relance est
   inscrite en attente puis faite par la supervision dès qu'il est au repos, et une seule fois.
Sans modèle : forge, dépôt du chef et copies jetables ; installation jetable avec un FAUX Herdr à état.
Usage : python3 tests/finition-soldee.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util, json, os, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit, _herdr_api_factice

SRC = Path(__file__).resolve().parent.parent; OUTILS = SRC / "courtier/outils"
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def charger(t):
    spec = importlib.util.spec_from_file_location(f"outil_{t}", OUTILS / f"{t}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def git(d, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True)


def erreur(f, args):
    try: f(args); return ""
    except (ValueError, RuntimeError, PermissionError) as e: return f"{type(e).__name__}: {e}"


# Herdr à état : statut réglable par panneau ; « ctrl+c » arrête l'agent du panneau, « agent start » l'y remet.
FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["FAUX_HERDR"]; etat = json.load(open(T + "/etat.json")); a = sys.argv[1:]
if a == ["agent", "prompt"]:
    d = json.load(sys.stdin); a += [d["target"], d["text"]]
with open(T + "/appels.log", "a") as f: f.write(json.dumps(a) + "\n")
r = {}
if a[:2] == ["agent", "list"]: r = {"agents": [{"name": n, "pane_id": p} for n, p in etat["agents"].items()]}
elif a[:2] == ["workspace", "list"]: r = {"workspaces": [{"workspace_id": w} for w in etat["espaces"]]}
elif a[:2] == ["pane", "get"]: r = {"pane": {"pane_id": a[2], "agent_status": etat["statuts"].get(a[2], "idle")}}
elif a[:2] == ["pane", "send-keys"] and a[3] == "ctrl+c": etat["agents"] = {n: p for n, p in etat["agents"].items() if p != a[2]}
elif a[:2] == ["agent", "start"]: etat["agents"][a[2]] = a[a.index("--pane") + 1]; r = {"agent": a[2]}
elif a[:2] == ["agent", "prompt"] and a[2] not in etat["agents"]: print('{"error":{"code":"agent_not_found"}}'); sys.exit(1)
json.dump(etat, open(T + "/etat.json", "w")); print(json.dumps({"result": r}))
'''

PORTE = 'echo "ok $1 : 3 contrôles"\n'
TOUTES = {"verify": "sh porte.sh verify", "tests": "sh porte.sh tests", "pret": "sh porte.sh pret"}

# ───────────── 1) la finition du chef solde la livraison « à finir » ─────────────
with tempfile.TemporaryDirectory() as t:
    t = Path(t); forge, depot, dem = t / "forge.git", t / "depot", t / "demandes"
    (t / "config.toml").write_text('proprietaire = "Test"\n'); os.environ["BERGER_DIR"] = str(t)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    git(depot, "config", "user.name", "t"); git(depot, "config", "user.email", "t@t.invalid")
    (depot / "porte.sh").write_text(PORTE); git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
    demande = lambda s: json.loads((dem / f"{s}.json").read_text())

    def developpeur(sujet):
        copie, agent = t / f"copie-{sujet}", t / f"agent-{sujet}"
        subprocess.run(["git", "clone", "-q", str(forge), str(copie)], capture_output=True); git(copie, "switch", "-q", "-c", f"equipe/{sujet}")
        git(copie, "config", "user.name", "t"); git(copie, "config", "user.email", "t@t.invalid")
        agent.mkdir(); (agent / "agent.conf").write_text(f"projet = p\nsujet = {sujet}\ncopie = {copie}\nbranche = equipe/{sujet}\nport = 0\n")
        d = charger("equipe_dev").Outil({"principale": "main", "demandes": str(dem), "finition": "chef", **TOUTES}, None, None)
        d.contexte = {"agent": f"p-{sujet}", "dossier": str(agent)}
        return d, copie

    def livrer(d, copie, nom):
        (copie / nom).write_text("x\n"); git(copie, "add", nom); git(copie, "commit", "-qm", f"feat: {nom}")
        d.verbes["pousser"]([]); d.verbes["demander-fusion"]([f"livré : {nom}, verify et tests joués"])

    chef = charger("equipe_chef").Outil({"depot": str(depot), "principale": "main", "demandes": str(dem), "valide_par": "coord",
                                         "chef_projet": "chef", "prefixe": "equipe/", "travail": str(t / "portes"), **TOUTES}, None, None)
    chef.contexte = {"agent": "chef", "dossier": str(t)}

    def finition(sujet, fin):
        """Le chef reprend la livraison `sujet` sur SA branche `<sujet>-fin` (sujet DIFFÉRENT : aucun fichier remplacé)."""
        git(depot, "fetch", "-q", "origin"); git(depot, "switch", "-q", "-c", f"equipe/{fin}", demande(sujet)["commit"])
        (depot / "VERSION").write_text("1.0.0\n"); git(depot, "add", "-A"); git(depot, "commit", "-qm", "chore: finition")
        git(depot, "switch", "-q", "main"); chef.verbes["pousser"]([f"equipe/{fin}"])
        return chef.verbes["demander-fusion"]([f"equipe/{fin}", "finition : version, pret jouée"])

    a, ca = developpeur("livre"); livrer(a, ca, "a.txt")
    b, cb = developpeur("autre"); livrer(b, cb, "b.txt")                        # une AUTRE livraison, jamais reprise
    dire(demande("livre")["etat"] == "à finir" and demande("autre")["etat"] == "à finir", "deux livraisons « à finir »")
    finition("livre", "livre-fin")
    dire(demande("livre-fin")["finition"] is True and demande("livre")["reprise_par"] == "equipe/livre-fin" and demande("livre")["etat"] == "à finir"
         and "reprise_par" not in demande("autre"), "finition demandée : la livraison reprise est marquée (reprise_par), l'autre non")
    r = chef.ecritures["fusionner"][1](["livre-fin"])
    d = demande("livre")
    dire(d["etat"] == "fusionnée" and d["fusion"] == "par la finition equipe/livre-fin" and d["soldee_par"] == "equipe/livre-fin",
         "fusion de la finition : la livraison d'origine passe à « fusionnée (par la finition equipe/livre-fin) »")
    dire("soldée" in r and "livre" in r, "le message de fusion dit quelle livraison est soldée")
    dire(demande("autre")["etat"] == "à finir" and "soldee_par" not in demande("autre"), "une livraison NON reprise reste « à finir »")
    dire(demande("livre-fin")["etat"] == "fusionnée", "la demande de finition elle-même est fusionnée")

    # même sujet (branche poursuivie par le chef) : la livraison est déjà REMPLACÉE par la demande de finition ; rien d'autre à solder
    c, cc = developpeur("meme"); livrer(c, cc, "c.txt"); livre = demande("meme")
    git(depot, "fetch", "-q", "origin"); git(depot, "switch", "-q", "-c", "equipe/meme", livre["commit"]); (depot / "V2").write_text("2\n")
    git(depot, "add", "-A"); git(depot, "commit", "-qm", "chore: finition"); git(depot, "switch", "-q", "main"); chef.verbes["pousser"](["equipe/meme"])
    chef.verbes["demander-fusion"](["equipe/meme", "finition : même sujet"])
    chef.ecritures["fusionner"][1](["meme"])
    dire(demande("meme")["etat"] == "fusionnée" and demande("meme")["agent"] == "chef",
         "reprise sous le MÊME sujet : la demande de finition remplace la livraison, fusionnée ; rien d'« à finir » ne reste")
    dire(erreur(chef.ecritures["fusionner"][1], ["livre"]) != "", "une livraison soldée ne se fusionne plus (déjà fusionnée)")

# ───────────── 2) la supervision et la limite de débit ; 3) relance après application ─────────────
def installation(t):
    _produit.copier(SRC, t, ("bin", "courtier", "commun")); _produit.admettre_moteurs(t)
    (t / "coffre.json").write_text('{"essai": {"cle": "valeur-secrete-du-test"}}')
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n\n'
                                   '[supervision]\nsans_avancee_min = 0\nescalade_min = 0\nmax_renvois = 2\n\n'
                                   f'[equipes.p]\ndepot = "{t}/depot"\nchef_projet = "chef"\ncoordinateur = "coord"\nports = [1]\n')
    panes = {"chef": "p1", "coord": "p2", "cible": "p3", "master": "p4"}
    for a, p in panes.items():
        d = t / "agents" / a; (d / "memory").mkdir(parents=True); (d / "propositions").mkdir()
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\npanneaux = claude\nheures = aucune\n" + ("superviseur = oui\n" if a == "master" else ""))
        (d / "SOUL.md").write_text(f"# {a}\n\nAncienne âme.\n")
        (d / ".herdr.json").write_text(json.dumps({"workspace": "w-" + a, "agents": {"claude": p}}))
    (t / "faux").mkdir(); (t / "faux/herdr").write_text(FAUX_HERDR); (t / "faux/notify-send").write_text("#!/bin/sh\nexit 0\n")
    for x in ("herdr", "notify-send"): os.chmod(t / "faux" / x, 0o755)
    statut(t, {}); (t / "faux/etat.json").write_text(json.dumps({"agents": {f"{a}-claude": p for a, p in panes.items()}, "statuts": {},
                                                                 "espaces": [f"w-{a}" for a in panes]}))
    return {**os.environ, "HOME": str(t), "BERGER_DIR": str(t), "FAUX_HERDR": str(t / "faux"), "PATH": f"{t}/faux:" + os.environ["PATH"],
            "BERGER_HERDR": str(t / "faux/herdr"), "BERGER_NOTIFY_SEND": str(t / "faux/notify-send")}


def statut(t, par_pane):
    f = t / "faux/etat.json"
    e = json.loads(f.read_text()) if f.exists() else {}
    e["statuts"] = par_pane; f.write_text(json.dumps(e))


def berger(t, env, *args):
    return subprocess.run([sys.executable, str(t / "bin/berger"), *args], env=env, capture_output=True, text=True, timeout=120)


def appels(t):
    return [json.loads(x) for x in (t / "faux/appels.log").read_text().splitlines()] if (t / "faux/appels.log").exists() else []


def messages(t, a): return [x[3] for x in appels(t) if x[:3] == ["agent", "prompt", f"{a}-claude"]]
def departs(t, a): return [x for x in appels(t) if x[:3] == ["agent", "start", f"{a}-claude"]]


with tempfile.TemporaryDirectory() as t:
    t = Path(t); env = _herdr_api_factice.installer(installation(t))
    sonde = subprocess.run([sys.executable, "-c", f"import runpy,sys;sys.argv=['b'];m=runpy.run_path({str(t / 'bin/berger')!r},run_name='x');print(m['HERDR'])"],
                           env=env, capture_output=True, text=True)
    if sonde.stdout.strip() != str(t / "faux/herdr"): sys.exit(f"ARRÊT : Berger n'utiliserait pas le faux Herdr ({sonde.stdout.strip() or sonde.stderr[-200:]})")

    # ── 2) supervision ──
    dem = t / "equipes/p/demandes"; dem.mkdir(parents=True)
    livraison = {"sujet": "livre", "branche": "equipe/livre", "commit": "a" * 40, "agent": "p-livre", "etat": "à finir",
                 "demande": "2026-10-13T10:00", "resume": "r"}
    (dem / "livre.json").write_text(json.dumps(livraison))
    berger(t, env, "superviser")
    dire(sum("LIVRÉE à finir" in m for m in messages(t, "chef")) == 1, "livraison « à finir » en attente : le chef est relancé (une fois)")
    debit = t / "courtier/ecrire-debit.json"
    dire(not debit.exists(), "la relance de la supervision ne passe pas par la limite de débit d'ecrire (aucun compteur créé)")
    # beaucoup de relances (le délai de relance est franchi à chaque tour) : le compteur d'ecrire reste vide, ni émetteur ni cible
    for _ in range(8):
        (t / "equipes/.relances.json").unlink(missing_ok=True); berger(t, env, "superviser")
    dire(sum("LIVRÉE à finir" in m for m in messages(t, "chef")) == 9 and not debit.exists(),
         "9 relances automatiques : toujours aucun compteur de débit (les VRAIS envois du chef restent permis)")
    # le compteur d'ecrire, lui, existe bien pour un envoi réel et ignore les relances
    courtier = subprocess.run([sys.executable, "-c", f"import runpy;g=runpy.run_path({str(t / 'courtier/courtier')!r},run_name='x');"
                               "print([g['debit_ecrire']('chef','coord') for _ in range(6)])"], env=env, capture_output=True, text=True)
    dire(courtier.stdout.strip() == "[True, True, True, True, True, False]", "les envois réels du chef : 5/h comme avant, rien consommé par les relances")
    # reprise demandée : plus de rappel
    (dem / "livre.json").write_text(json.dumps({**livraison, "reprise_par": "equipe/livre-fin"}))
    (t / "equipes/.relances.json").unlink(missing_ok=True); n = len(messages(t, "chef")); berger(t, env, "superviser")
    dire(not any("LIVRÉE à finir" in m for m in messages(t, "chef")[n:]), "finition déjà demandée (reprise_par) : plus de rappel « livrée à finir »")
    # soldée : plus de rappel, jamais
    (dem / "livre.json").write_text(json.dumps({**livraison, "etat": "fusionnée", "fusion": "par la finition equipe/livre-fin",
                                                "soldee_par": "equipe/livre-fin", "fusionnee": "2026-10-13T22:00"}))
    for _ in range(3):
        (t / "equipes/.relances.json").unlink(missing_ok=True); berger(t, env, "superviser")
    dire(not any("LIVRÉE à finir" in m for m in messages(t, "chef")[n:]), "livraison soldée : la supervision ne relance JAMAIS")

    # ── 2 bis) rattrapage : finition fusionnée AVANT le correctif de solde (aucun reprise_par, aucun soldee_par) ──
    depot = t / "depot"; depot.mkdir(); git(depot, "init", "-q", "-b", "main")
    def valider(nom):
        (depot / nom).write_text("x\n"); git(depot, "add", "-A"); git(depot, "commit", "-qm", nom); return git(depot, "rev-parse", "HEAD").stdout.strip()
    base = valider("base")
    git(depot, "switch", "-q", "-c", "livre"); livre = valider("livre"); git(depot, "switch", "-q", "main")
    git(depot, "switch", "-q", "-c", "jamais", base); jamais = valider("jamais"); git(depot, "switch", "-q", "main")
    git(depot, "merge", "-q", "--no-ff", "-m", "finition", "livre"); fin = git(depot, "rev-parse", "HEAD").stdout.strip()
    for f in dem.glob("*.json"): f.unlink()
    lire = lambda s: json.loads((dem / f"{s}.json").read_text())
    (dem / "livre.json").write_text(json.dumps({**livraison, "commit": livre}))
    (dem / "jamais.json").write_text(json.dumps({**livraison, "sujet": "jamais", "branche": "equipe/jamais", "commit": jamais}))
    (dem / "livre-fin.json").write_text(json.dumps({"sujet": "livre-fin", "branche": "equipe/livre-fin", "commit": fin, "commit_fusion": fin, "agent": "chef",
                                                    "etat": "fusionnée", "finition": True, "demande": "2026-10-12T09:00", "fusionnee": "2026-10-12T10:00"}))
    (t / "equipes/.relances.json").unlink(missing_ok=True); n = len(messages(t, "chef")); berger(t, env, "superviser")
    d = lire("livre")
    dire(d["etat"] == "fusionnée" and d["fusion"] == "par la finition equipe/livre-fin" and d["soldee_par"] == "equipe/livre-fin",
         "rattrapage : livraison à finir dont la finition est fusionnée (sans reprise_par) → soldée au premier passage")
    nouveaux = messages(t, "chef")[n:]
    dire(not any("livre » " in m and "LIVRÉE" in m for m in nouveaux) and sum("« jamais »" in m and "LIVRÉE à finir" in m for m in nouveaux) == 1,
         "…jamais rappelée ; la livraison réellement non reprise l'est toujours (une fois)")
    dire(lire("jamais")["etat"] == "à finir" and "soldee_par" not in lire("jamais"), "livraison non reprise : laissée « à finir »")
    journal_chef = "".join(x.read_text() for x in (t / "agents/chef/memory").glob("*.md"))
    dire(journal_chef.count("soldée par la finition equipe/livre-fin") == 1, "une ligne au journal du chef")
    avant = (dem / "livre.json").read_text()
    for _ in range(3):
        (t / "equipes/.relances.json").unlink(missing_ok=True); berger(t, env, "superviser")
    journal_chef = "".join(x.read_text() for x in (t / "agents/chef/memory").glob("*.md"))
    dire((dem / "livre.json").read_text() == avant and journal_chef.count("soldée par la finition equipe/livre-fin") == 1,
         "rien n'est soldé deux fois (3 passages de plus : fichier inchangé, une seule ligne de journal)")

    # ── 3) relance après application ──
    P = t / "agents/master/propositions"
    def proposer(texte): (P / "cible.md").write_text("=== SOUL.md\n" + texte)
    def appliquer(texte):
        proposer(texte); e = next(l.split("Empreinte : ")[1].strip() for l in berger(t, env, "agent", "apercu", "master", "cible").stdout.splitlines() if "Empreinte : " in l)
        return berger(t, env, "agent", "appliquer", "master", f"cible.{e}")
    marqueur = t / "agents/cible/.relance-en-attente"
    (t / "faux/appels.log").unlink(missing_ok=True)

    # agent AU REPOS : relancé tout de suite, sur sa conversation, rien en attente
    statut(t, {"p3": "idle"}); r = appliquer("# cible\n\nVersion deux.\n")
    dire(r.returncode == 0 and len(departs(t, "cible")) == 1 and not marqueur.exists() and "relancé" in r.stdout,
         "agent au repos : relancé automatiquement après l'application, aucune relance en attente")
    dire("Version deux" in (t / "agents/cible/SOUL.md").read_text(), "la nouvelle version est bien appliquée")
    dire("relancé" in "".join(x.read_text() for x in (t / "agents/cible/memory").glob("*.md")), "relance notée au journal de l'agent")

    # agent QUI TRAVAILLE : jamais coupé, relance inscrite et dite dans le message de décision
    statut(t, {"p3": "working"}); r = appliquer("# cible\n\nVersion trois.\n")
    dire(r.returncode == 0 and len(departs(t, "cible")) == 1 and marqueur.is_file() and "EN ATTENTE" in r.stdout,
         "agent qui travaille : pas relancé, relance inscrite en attente et dite dans le message de décision")
    berger(t, env, "superviser")
    dire(len(departs(t, "cible")) == 1 and marqueur.is_file(), "toujours occupé : la supervision attend (rien coupé)")
    statut(t, {"p3": "idle"}); berger(t, env, "superviser")
    dire(len(departs(t, "cible")) == 2 and not marqueur.exists(), "au repos : la supervision fait la relance en attente et retire l'inscription")
    for _ in range(3): berger(t, env, "superviser")
    dire(len(departs(t, "cible")) == 2, "rien n'est rejoué deux fois (3 passages de plus)")

    # une relance manuelle (berger relancer) lève aussi l'attente ; un agent sans panneau ouvert n'attend rien
    statut(t, {"p3": "working"}); appliquer("# cible\n\nVersion quatre.\n"); statut(t, {"p3": "idle"})
    r = berger(t, env, "relancer", "cible")
    dire(r.returncode == 0 and not marqueur.is_file(), "relance manuelle réussie : l'inscription en attente est levée")
    n = len(departs(t, "cible")); berger(t, env, "superviser")
    dire(len(departs(t, "cible")) == n, "…et la supervision ne relance pas une seconde fois")
    (t / "agents/cible/.herdr.json").write_text(json.dumps({"agents": {}})); r = appliquer("# cible\n\nVersion cinq.\n")
    dire(r.returncode == 0 and not marqueur.exists() and "prochaine ouverture" in r.stdout, "pas d'agent ouvert : rien à relancer, rien en attente, dit clairement")

raise SystemExit(ko)
