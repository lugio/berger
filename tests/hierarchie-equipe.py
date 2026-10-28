#!/usr/bin/env python3
"""Tests de la hiérarchie d'équipe (coordinateur → chef de projet → développeurs) — sans modèle, sans vrai Herdr, sans toucher
à l'installation : une installation JETABLE, un FAUX Herdr qui note ce qu'on lui demande, le courtier appelé directement.
Spec : docs/plans/2026-10-13-hierarchie-equipe-spec.md. Usage : python3 tests/hierarchie-equipe.py (0 = OK).
Couvre : droits d'équipe calculés depuis [equipes.<projet>] (rien d'écrit dans les agent.conf) ; le chef seul ouvre et ferme ;
le coordinateur lit l'état et suit le chef, jamais les développeurs ; rien vers un autre projet ; `equipe:<projet>` d'un
non-coordinateur ignoré et signalé ; lecture seule respectée ; coordinateur = chef ; transition (un développeur ouvert AVANT
la bascule : géré par son chef, ni fermé ni relancé, alerte au chef même déjà signalée à l'ancien coordinateur) ; mission à un
chef vivant (pas de seconde instance, hors `[missions] max`, terminée sans fermer son espace)."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, subprocess, sys, tempfile, time
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
if a == ["agent", "prompt"]:
    d = json.load(sys.stdin); a += [d["target"], d["text"]]
with open(T + "/appels.log", "a") as f: f.write(json.dumps(a) + "\n")
r = {}
if a[:2] == ["agent", "list"]: r = {"agents": [{"name": n, "pane_id": p} for n, p in etat["agents"].items()]}
elif a[:2] == ["pane", "get"]:
    r = {"pane": {"pane_id": a[2], "agent_status": "idle"}} if a[2] in etat["agents"].values() else {}
elif a[:2] == ["workspace", "list"]: r = {"workspaces": [{"workspace_id": w} for w in etat.get("espaces", [])]}
elif a[:2] == ["agent", "prompt"] and a[2] not in etat["agents"]: print('{"error":{"code":"agent_not_found"}}'); sys.exit(1)
print(json.dumps({"result": r}))
'''

APPEL = r'''
import json, runpy, sys, time
g = runpy.run_path(sys.argv[1], run_name="essai")
agent, req = sys.argv[2], json.loads(sys.argv[3])
d = g["AGENTS"] / agent / "courrier"; (d / "encours").mkdir(parents=True, exist_ok=True)
f = d / "encours" / "1.json"; f.write_text(json.dumps(req))
g["traiter"](agent, f, {})
for _ in range(600):
    r = d / "reponses" / "1.json"
    if r.exists(): print(r.read_text()); r.unlink(); break
    time.sleep(0.1)
'''

DROITS = r'''
import json, runpy, sys
g = runpy.run_path(sys.argv[1], run_name="essai")
print(json.dumps({a: sorted(g["droits"](a)) for a in sys.argv[2:]}))
'''

with tempfile.TemporaryDirectory() as td:
    m = Path(td); t = m / "berger"
    _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}")
    (t / "config.toml").write_text(
        f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n\n[missions]\nmax = 1\n\n'
        '[supervision]\nsans_avancee_min = 600\nescalade_min = 0\nmax_renvois = 3\n\n'
        f'[equipes.p]\ndepot = "{m}/depot-p"\nchef_projet = "chef"\ncoordinateur = "coord"\n\n'
        f'[equipes.q]\ndepot = "{m}/depot-q"\nchef_projet = "chefq"\ncoordinateur = "coordq"\nfinition = "chef"\n\n'
        f'[equipes.b]\ndepot = "{m}/depot-b"\nchef_projet = "maitre"\ncoordinateur = "maitre"\n\n'
        f'[equipes.r]\ndepot = "{m}/depot-r"\nchef_projet = "lecteur"\ncoordinateur = "coord"\n')
    dev = lambda p, s: f"projet = {p}\nsujet = {s}\ncopie = {m}/copies/{p}-{s}\nbranche = equipe/{s}\nport = 0\n"
    # AUCUN droit d'équipe écrit : tout doit venir de [equipes.*] ; « intrus » déclare equipe:p sans être le coordinateur
    agents = {"chef": "", "coord": "", "chefq": "", "coordq": "", "maitre": "", "intrus": "outils = equipe:p\n",
              "lecteur": "lecture_seule = oui\n", "p-ancien": dev("p", "ancien"), "q-autre": dev("q", "autre"), "b-sujet": dev("b", "sujet")}
    panes = {}
    for n, (a, extra) in enumerate(agents.items()):
        d = t / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\npanneaux = claude\nheures = aucune\n{extra}")
        panes[a] = f"p{n}"; (d / ".herdr.json").write_text(json.dumps({"workspace": "w-" + a, "agents": {"claude": panes[a]}}))
    # le développeur « ancien » a été ouvert AVANT la bascule, par l'ancien coordinateur
    mission_ancien = "# Mission confiée par coord — 2026-10-13 09:00\nmoteur : claude\n\nfaire x\n"
    (t / "agents/p-ancien/MISSION.md").write_text(mission_ancien)
    (t / "agents/p-ancien/CHECKLIST.md").write_text("# x\n- [ ] étape\n")
    dem = t / "equipes/p/demandes"; dem.mkdir(parents=True)
    (dem / "ancien.json").write_text(json.dumps({"sujet": "ancien", "agent": "p-ancien", "etat": "renvoyée", "renvois": 1,
                                                 "portes": {"verify": {"etat": "vert"}, "pret": {"etat": "rouge"}}}))
    f = m / "faux"; f.mkdir(); (f / "herdr").write_text(FAUX_HERDR); (f / "notify-send").write_text("#!/bin/sh\nexit 0\n")
    for x in ("herdr", "notify-send"): os.chmod(f / x, 0o755)
    (f / "etat.json").write_text(json.dumps({"agents": {f"{a}-claude": p for a, p in panes.items()}, "espaces": [f"w-{a}" for a in agents]}))
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(t), "FAUX_HERDR": str(f), "BERGER_HERDR": str(f / "herdr"),
           "BERGER_NOTIFY_SEND": str(f / "notify-send")}
    _herdr_api_factice.installer(env)
    sonde = subprocess.run([sys.executable, "-c", f"import runpy,sys;sys.argv=['b'];m=runpy.run_path({str(t / 'bin/berger')!r},run_name='x');print(m['HERDR'])"],
                           env=env, capture_output=True, text=True)
    if sonde.stdout.strip() != str(f / "herdr"): sys.exit(f"ARRÊT : Berger n'utiliserait pas le faux Herdr ({sonde.stdout.strip() or sonde.stderr[-200:]})")

    def appel(agent, outil, verbe, *args):
        r = subprocess.run([sys.executable, "-c", APPEL, str(t / "courtier/courtier"), agent, json.dumps({"outil": outil, "verbe": verbe, "args": list(args)})],
                           env=env, capture_output=True, text=True, timeout=120)
        try: return json.loads(r.stdout)
        except ValueError: return {"ok": None, "erreur": (r.stderr or r.stdout)[-300:]}

    def berger(*args, timeout=120): return subprocess.run([sys.executable, str(t / "bin/berger"), "--stdin"], input=json.dumps(list(args)), env=env, capture_output=True, text=True, timeout=timeout)
    def appels(): return [json.loads(x) for x in (f / "appels.log").read_text().splitlines()] if (f / "appels.log").exists() else []
    def messages(a): return [x[3] for x in appels() if x[:3] == ["agent", "prompt", f"{a}-claude"]]
    def ok(r): return r.get("ok") is True
    def refus(r, mot=""): return r.get("ok") is False and mot in r.get("erreur", "")

    # ── droits calculés : rien vers soi, rien vers un autre projet ──
    dr = json.loads(subprocess.run([sys.executable, "-c", DROITS, str(t / "courtier/courtier"), "chef", "coord", "maitre", "p-ancien", "intrus"],
                                   env=env, capture_output=True, text=True, timeout=60).stdout or "{}")
    dire("p-chef" in dr.get("chef", []), "chef de projet : son outil <projet>-chef, sans ligne dans son agent.conf")
    dire({"ecrire:p-ancien", "mission:p-ancien", "ecrire:coord"} <= set(dr.get("chef", [])), "chef : écrire et missions vers SES développeurs, écrire au coordinateur")
    dire(not any("q-" in x or "chefq" in x for x in dr.get("chef", [])), "chef : rien vers un autre projet")
    dire({"ecrire:chef", "mission:chef", "ecrire:lecteur"} <= set(dr.get("coord", [])) and not any("p-ancien" in x for x in dr.get("coord", [])),
         "coordinateur : écrire et missions vers ses chefs (deux projets), rien vers un développeur")
    dire("b-chef" in dr.get("maitre", []) and not any(x.endswith(":maitre") for x in dr.get("maitre", [])),
         "coordinateur = chef : les deux rôles, jamais un droit vers soi")
    dire(dr.get("p-ancien") == ["ecrire:chef"], "développeur : écrire à son chef, rien d'autre d'office")
    dire(dr.get("intrus") == ["equipe:p"], "equipe:<projet> déclaré par un non-coordinateur : aucun droit d'équipe calculé")

    # ── ouvrir / fermer : le chef seul ──
    r = appel("coord", "equipe", "ouvrir", "p", "nouveau", "faire y")
    dire(refus(r, "seul le chef de projet"), "coordinateur (non chef) : ouvrir un développeur refusé, il confie le sujet au chef")
    r = appel("coord", "equipe", "fermer", "p", "ancien")
    dire(refus(r, "seul le chef de projet") and (t / "agents/p-ancien").is_dir(), "coordinateur : fermer refusé, rien n'est fermé")
    r = berger("equipe", "ouvrir", "p", "nouveau", "faire y", "--par", "coord")
    dire(r.returncode != 0 and "pas le chef de projet" in r.stderr and not (t / "agents/p-nouveau").exists(),
         "ligne de commande : ouvrir --par coordinateur refusé, rien n'est créé")
    r = berger("equipe", "fermer", "p", "ancien", "--par", "coord")
    dire(r.returncode != 0 and "pas le chef de projet" in r.stderr and (t / "agents/p-ancien/MISSION.md").is_file(),
         "ligne de commande : fermer --par coordinateur refusé")
    # défense (13/10) : « fermer » ne vise qu'un développeur ouvert du projet, jamais la copie de travail du chef
    # (agent « p-fin » : un dossier et une copie, mais un agent.conf SANS projet ni sujet, comme la branche de finition du chef)
    (t / "agents/p-fin").mkdir(); (t / "agents/p-fin/agent.conf").write_text(f"nom = p-fin\nmoteur = claude\ncopie = {m}/copies/travail-chef\nbranche = equipe/fin\n")
    (m / "copies/travail-chef").mkdir(parents=True); (m / "copies/travail-chef/travail.txt").write_text("à garder")
    def intact(): return (m / "copies/travail-chef/travail.txt").is_file() and (t / "agents/p-fin/agent.conf").is_file()
    r = appel("chef", "equipe", "fermer", "p", "fin")
    dire(refus(r, "pas un développeur ouvert") and intact(), "courtier : fermer sur le sujet du chef refusé, rien de supprimé")
    r = berger("equipe", "fermer", "p", "fin", "--par", "chef")
    dire(r.returncode != 0 and "pas un développeur ouvert" in r.stderr and intact(), "ligne de commande : fermer sur le sujet du chef refusé, rien de supprimé")
    r = appel("chef", "equipe", "fermer", "p", "inexistant")
    dire(refus(r, "pas un développeur ouvert"), "courtier : fermer un sujet inconnu refusé")
    r = appel("chef", "equipe", "ouvrir", "p", "nouveau", "faire y")
    dire(r.get("ok") is False and "chef" not in r.get("erreur", "") and "droit" not in r.get("erreur", ""),
         "chef : ouvrir passe les droits (ici arrêté plus loin : pas de dépôt dans l'essai)")
    dire(refus(appel("intrus", "equipe", "liste", "p"), "ni le chef de projet ni le coordinateur"), "equipe:p d'un non-coordinateur : equipe liste refusé")
    dire(refus(appel("chefq", "equipe", "ouvrir", "p", "x", "y"), "ni le chef"), "chef d'un AUTRE projet : ouvrir refusé")

    # ── lecture de l'état : liste (demande, portes, renvois) + avertissement ──
    r = appel("coord", "equipe", "liste", "p"); l = r.get("donnees") or []
    e = next((x for x in l if x.get("agent") == "p-ancien"), {})
    dire(ok(r) and e.get("demande_de_fusion") == "renvoyée" and "pret : rouge" in (e.get("portes") or "") and e.get("renvois") == 1,
         "coordinateur : equipe liste donne développeurs, état de la demande, portes et renvois")
    dire(any("intrus" in x.get("avertissement", "") for x in l), "equipe liste : avertissement pour equipe:p déclaré par un non-coordinateur")
    dire(ok(appel("chef", "equipe", "liste", "p")), "chef : equipe liste permis")
    # en ligne de commande, sans projet ou sans assez d'arguments : l'usage et les équipes, jamais une trace Python (18/10)
    for a in (["equipe"], ["equipe", "liste"], ["equipe", "ouvrir", "p"], ["equipe", "fermer"], ["equipe", "liste", "inconnu"]):
        r = berger(*a)
        dire(r.returncode != 0 and "Traceback" not in r.stderr and "berger equipe" in r.stderr + r.stdout and "équipes : p, q, b, r" in r.stderr + r.stdout,
             f"berger {' '.join(a)} : usage et équipes dits, sans trace ({(r.stderr or r.stdout).strip().splitlines()[-1:]})")

    # ── coordinateur → chef ; chef → développeurs (dont celui ouvert AVANT la bascule) ; développeur → chef ──
    dire(ok(appel("coord", "ecrire", "chef", "nouveau sujet pour toi")), "coordinateur → chef : écrire, sans droit déclaré")
    dire(refus(appel("coord", "ecrire", "chefq", "x"), "pas le droit"), "coordinateur → chef d'un autre projet : refusé")
    dire(refus(appel("coord", "ecrire", "p-ancien", "x"), "pas le droit"), "coordinateur → développeur : refusé (il passe par le chef)")
    dire(ok(appel("coord", "mission", "suivi", "chef")), "coordinateur : mission suivi du chef")
    dire(refus(appel("coord", "mission", "suivi", "p-ancien"), "pas le droit"), "coordinateur : mission suivi d'un développeur refusé")
    dire(ok(appel("chef", "ecrire", "p-ancien", "relance : où en es-tu ?")) and any("relance : où en es-tu" in x for x in messages("p-ancien")),
         "chef → développeur ouvert avant la bascule : écrire (relancer), message remis")
    r = appel("chef", "mission", "suivi", "p-ancien")
    dire(ok(r) and "faire x" in str((r.get("donnees") or {}).get("mission")), "chef : mission suivi du développeur ouvert avant la bascule")
    dire(refus(appel("chef", "ecrire", "q-autre", "x"), "pas le droit") and refus(appel("chef", "mission", "suivi", "q-autre"), "pas le droit"),
         "chef → développeur d'un autre projet : refusé")
    dire(ok(appel("chef", "ecrire", "coord", "escalade : décision nécessaire")), "chef → coordinateur : écrire (escalade)")
    dire(ok(appel("p-ancien", "ecrire", "chef", "je suis bloqué")), "développeur → son chef : écrire (rendre compte)")
    dire(refus(appel("p-ancien", "ecrire", "coord", "x"), "pas le droit"), "développeur → coordinateur : refusé (la chaîne passe par le chef)")
    dire(refus(appel("lecteur", "equipe", "liste", "r"), "LECTURE SEULE") and refus(appel("lecteur", "ecrire", "coord", "x"), "LECTURE SEULE"),
         "chef en lecture seule : les droits d'équipe ne passent pas outre")

    # ── transition : regenerer ne ferme ni ne relance ; les consignes nomment le chef ; l'alerte va au chef ──
    n = len(messages("p-ancien"))
    r = berger("regenerer")
    dire(r.returncode == 0 and (t / "agents/p-ancien/MISSION.md").read_text() == mission_ancien and len(messages("p-ancien")) == n,
         "transition : regenerer garde le développeur ouvert, sa mission, sans le relancer" + ("" if r.returncode == 0 else f" — {r.stderr[-200:]}"))
    regles = (t / "agents/p-ancien/AGENTS.md").read_text() if (t / "agents/p-ancien/AGENTS.md").exists() else ""
    dire("ton chef de projet (chef)" in regles, "transition : ses consignes régénérées disent qu'il rend compte à son chef")
    rq = (t / "agents/q-autre/AGENTS.md").read_text() if (t / "agents/q-autre/AGENTS.md").exists() else ""
    dire("finition (porte `pret`" in rq and "finition (porte `pret`" not in regles,
         "finition = chef : les consignes du développeur le disent (pas de pret, il livre) ; projet par défaut : rien")
    dq = t / "equipes/q/demandes"; dq.mkdir(parents=True)
    (dq / "autre.json").write_text(json.dumps({"sujet": "autre", "agent": "q-autre", "branche": "equipe/autre", "commit": "abcdef1234",
                                               "etat": "à finir", "demande": "2026-10-13T10:00"}))
    nq = len(messages("chefq")); berger("superviser")
    dire(any("LIVRÉE à finir" in x for x in messages("chefq")[nq:]), "livraison « à finir » en attente → le chef est relancé (supervision)")
    (dq / "autre.json").unlink()
    (t / "agents/p-ancien/CHECKLIST.md").write_text("# x\n- [ ] étape\n⚠ Bloqué : droit manquant\n")
    import hashlib
    cle = f"bloque:p-ancien:{hashlib.sha1('droit manquant'.encode()).hexdigest()[:10]}"
    (t / ".supervision.json").write_text(json.dumps({f"coord:{cle}": time.time(), f"debut:{cle}": time.time()}))   # déjà signalé à l'ancien coordinateur
    nc, nk = len(messages("chef")), len(messages("coord"))
    berger("superviser"); berger("superviser")
    dire(sum("BLOQUÉ" in x for x in messages("chef")[nc:]) == 1, "transition : un blocage déjà signalé à l'ancien coordinateur va au chef, une fois")
    dire(sum("BLOQUÉ" in x for x in messages("coord")[nk:]) == 1 and "malgré chef" in " ".join(messages("coord")[nk:]),
         "escalade : puis au coordinateur (« malgré » le chef), une fois")
    (t / "agents/p-ancien/CHECKLIST.md").write_text("# x\n- [ ] étape\n")
    nb = len(messages("maitre")); (t / "agents/b-sujet/MISSION.md").write_text("# Mission confiée par maitre — x\nmoteur : claude\n\nz\n")
    (t / "agents/b-sujet/CHECKLIST.md").write_text("# z\n- [ ] étape\n⚠ Bloqué : autre chose\n")
    berger("superviser"); berger("superviser")
    dire(sum("BLOQUÉ" in x for x in messages("maitre")[nb:]) == 1, "coordinateur = chef : une seule alerte")
    (t / "agents/b-sujet/MISSION.md").unlink()

    # ── mission au chef vivant : pas de seconde instance, hors du maximum, fin sans fermer son espace ──
    # [missions] max = 1, déjà pris par p-ancien ; le coordinateur a son espace ouvert (il serait l'hôte d'un onglet Missions)
    n0 = len(appels())
    r = berger("mission", "chef", "sujet z : spec courte + go", "--par", "coord", timeout=60)
    nouveaux = appels()[n0:]
    dire(r.returncode == 0 and (t / "agents/chef/MISSION.md").is_file(), "mission confiée au chef malgré [missions] max atteint (il ne prend pas de place)"
         + ("" if r.returncode == 0 else f" — {r.stderr[-200:]}"))
    dire(not any(x[:2] in (["pane", "split"], ["tab", "create"], ["workspace", "create"]) for x in nouveaux) and any("lis MISSION.md" in x[-1] for x in nouveaux if x[:3] == ["agent", "prompt", "chef-claude"]),
         "chef vivant : la mission lui est dite, aucune seconde instance ouverte")
    r = berger("mission", "q-autre", "autre chose", "--par", "chefq", timeout=60)
    dire(r.returncode != 0 and "maximum" in r.stdout + r.stderr, "un développeur, lui, compte toujours dans [missions] max")
    # 13/10 : « mission terminer » ne lève pas une garde — refusé tant que la checklist ne finit pas par Terminé / Abandonné
    ck = t / "agents/chef/CHECKLIST.md"; ck.write_text("# sujet z\n- [x] spec\n- [ ] code\n")
    r = berger("fin-mission", "chef", "--par", "coord", timeout=60)
    dire(r.returncode != 0 and "ne lève pas une garde" in r.stdout + r.stderr and "propriétaire" in r.stdout + r.stderr and (t / "agents/chef/MISSION.md").is_file(),
         "fin de mission refusée sans « Terminé » : message clair (ne lève pas une garde, se signale au propriétaire), MISSION.md gardée")
    ck.write_text("# sujet z\n- [x] spec\n⚠ Bloqué : garde git\n")
    r = berger("fin-mission", "chef", "--par", "coord", timeout=60)
    dire(r.returncode != 0 and (t / "agents/chef/MISSION.md").is_file(), "fin de mission refusée aussi quand la checklist est bloquée")
    ck.write_text("# sujet z\n- [x] spec\nAbandonné : sujet repris ailleurs\n")
    n0 = len(appels()); r = berger("fin-mission", "chef", "--par", "coord", timeout=60)
    dire(r.returncode == 0 and not (t / "agents/chef/MISSION.md").exists(), "fin de mission acceptée avec « Abandonné : … »")
    (t / "agents/chef/MISSION.md").write_text("# Mission confiée par coord — sujet z bis\nmoteur : claude\n\nfaire\n")
    ck.write_text("# sujet z bis\n- [x] spec\nTerminé 2026-10-13 12:00\n")
    r = berger("fin-mission", "chef", "--par", "coord", timeout=60)
    dire(r.returncode == 0 and not (t / "agents/chef/MISSION.md").exists(), "fin de mission acceptée avec « Terminé … »")
    # 14/10 : la checklist Terminé a déjà été RANGÉE par le planificateur (plus de CHECKLIST.md) → la fin est acceptée (une seule règle)
    (t / "agents/chef/MISSION.md").write_text("# Mission confiée par coord — sujet z rangé\nmoteur : claude\n\nfaire\n")
    ck.unlink(missing_ok=True); (t / "agents/chef/historique").mkdir(exist_ok=True)
    rg = t / "agents/chef/historique/2999-01-01_2320_z.md"; rg.write_text("# z\n- [x] spec\nTerminé 2999-01-01 23:20\n")
    r = berger("fin-mission", "chef", "--par", "coord", timeout=60)
    dire(r.returncode == 0 and not (t / "agents/chef/MISSION.md").exists(), "fin de mission acceptée quand la checklist Terminé est déjà rangée dans historique/")
    (t / "agents/chef/MISSION.md").write_text("# Mission confiée par coord — sujet z non fini\nmoteur : claude\n\nfaire\n")
    rg.write_text("# z\n- [x] spec\n- [ ] code\n")
    r = berger("fin-mission", "chef", "--par", "coord", timeout=60)
    dire(r.returncode != 0 and (t / "agents/chef/MISSION.md").is_file(), "checklist rangée NON finie : fin de mission refusée comme avant")
    rg.unlink()
    (t / "agents/chef/MISSION.md").write_text("# Mission confiée par coord — sujet z ter\nmoteur : claude\n\nfaire\n")
    ck.write_text("# sujet z ter\n- [ ] code\n")
    r = berger("fin-mission", "chef", "--motif", "mission lancée par erreur", timeout=60)
    jour = (t / "agents/chef/memory" / f"{time.strftime('%Y-%m-%d')}.md")
    dire(r.returncode == 0 and not (t / "agents/chef/MISSION.md").exists() and "SANS checklist finie — motif : mission lancée par erreur" in jour.read_text(),
         "le propriétaire garde son chemin en ligne de commande : checklist non finie acceptée, motif tracé au journal")
    (t / "agents/chef/MISSION.md").write_text("# Mission confiée par coord — sujet z\nmoteur : claude\n\nfaire\n")
    ck.write_text("# sujet z\n- [x] spec\nTerminé 2026-10-13 12:00\n")
    r = berger("fin-mission", "chef", "--par", "coord", timeout=60)
    dire(r.returncode == 0 and not (t / "agents/chef/MISSION.md").exists() and any((t / "agents/chef/historique").glob("mission-*.md")),
         "fin de la mission du chef : rangée dans historique/")
    dire(not any(x[:2] in (["workspace", "close"], ["pane", "close"]) for x in appels()[n0:]), "fin de la mission du chef : son espace reste ouvert")
print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
