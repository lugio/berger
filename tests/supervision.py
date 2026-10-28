#!/usr/bin/env python3
"""Tests de la supervision et des validations — sans modèle, sans toucher aux vrais agents : une installation Berger
JETABLE (copie du produit) et un FAUX Herdr qui note ce qu'on lui demande. Usage : python3 tests/supervision.py (0 = OK).
Couvre les trous du 05/10 : relances (relecture, validation, renvoi), « rien n'avance », blocage → coordinateur puis
propriétaire (une seule fois chacun : empreinte stable), décision de validation jamais lue à moitié (course)."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, shutil, subprocess, sys, tempfile, time
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
    r = {"pane": {"pane_id": a[2], "agent_status": etat["statuts"].get(a[2], "idle")}} if a[2] in etat["statuts"] else {}
elif a[:2] == ["workspace", "list"]: r = {"workspaces": [{"workspace_id": w} for w in etat.get("espaces", [])]}
elif a[:2] == ["agent", "prompt"] and a[2] not in etat["agents"]: print('{"error":{"code":"agent_not_found"}}'); sys.exit(1)
print(json.dumps({"result": r}))
'''


def installation(t):
    _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    (t / "coffre.json").write_text('{"essai": {"cle": "valeur-secrete-du-test"}}')
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n\n[missions]\nmax = 3\n\n'
                                   '[supervision]\nsans_avancee_min = 0\nescalade_min = 0\nmax_renvois = 2\n\n'
                                   f'[equipes.p]\ndepot = "{t}/depot"\nchef_projet = "chef"\ncoordinateur = "coord"\nports = [1]\n')
    panes = {"chef": "p1", "coord": "p2", "p-dev": "p3"}
    for a, p in panes.items():
        d = t / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\npanneaux = claude\nheures = aucune\n"
                                      + ("projet = p\nsujet = dev\ncopie = /nulle-part\nbranche = equipe/dev\nport = 1\n" if a == "p-dev" else ""))
        (d / ".herdr.json").write_text(json.dumps({"workspace": "w-" + a, "agents": {"claude": p}}))
    vieux = time.time() - 3600
    (t / "agents/p-dev/MISSION.md").write_text("# Mission confiée par coord — test\nmoteur : claude\n\nfaire x\n")
    (t / "agents/p-dev/CHECKLIST.md").write_text("# x\n- [ ] étape\n")
    for f in (t / "agents/p-dev").rglob("*"): os.utime(f, (vieux, vieux))           # rien n'a bougé depuis 1 h
    (t / "faux").mkdir(); (t / "faux/herdr").write_text(FAUX_HERDR); (t / "faux/notify-send").write_text("#!/bin/sh\nexit 0\n")
    for x in ("herdr", "notify-send"): os.chmod(t / "faux" / x, 0o755)
    etat = {"agents": {f"{a}-claude": p for a, p in panes.items()}, "statuts": {p: "idle" for p in panes.values()},
            "espaces": [f"w-{a}" for a in panes]}
    (t / "faux/etat.json").write_text(json.dumps(etat))
    return {**os.environ, "BERGER_DIR": str(t), "FAUX_HERDR": str(t / "faux"), "PATH": f"{t}/faux:" + os.environ["PATH"],
            "BERGER_HERDR": str(t / "faux/herdr"), "BERGER_NOTIFY_SEND": str(t / "faux/notify-send")}


def berger(t, env, *args):
    return subprocess.run([sys.executable, str(t / "bin/berger"), *args], env=env, capture_output=True, text=True, timeout=60)


def messages(t, a):
    l = (t / "faux/appels.log").read_text().splitlines() if (t / "faux/appels.log").exists() else []
    return [json.loads(x)[3] for x in l if json.loads(x)[:3] == ["agent", "prompt", f"{a}-claude"]]


with tempfile.TemporaryDirectory() as t:
    t = Path(t); env = _herdr_api_factice.installer(installation(t))
    # SÉCURITÉ DU TEST : il ne doit parler QU'AU faux Herdr (jamais à tes vrais agents) — sinon on s'arrête tout de suite
    sonde = subprocess.run([sys.executable, "-c", f"import runpy,sys;sys.argv=['b'];m=runpy.run_path({str(t / 'bin/berger')!r},run_name='x');print(m['HERDR'])"],
                           env=env, capture_output=True, text=True)
    if sonde.stdout.strip() != str(t / "faux/herdr"): sys.exit(f"ARRÊT : Berger n'utiliserait pas le faux Herdr ({sonde.stdout.strip() or sonde.stderr[-200:]})")
    dem = t / "equipes/p/demandes"; dem.mkdir(parents=True)
    (dem / "dev.json").write_text(json.dumps({"sujet": "dev", "branche": "equipe/dev", "commit": "abc", "agent": "p-dev",
                                              "etat": "à relire", "demande": "2026-10-05T10:00", "resume": "r"}))
    berger(t, env, "superviser")
    dire(any("attend ta relecture" in m for m in messages(t, "chef")), "demande à relire → le chef de projet est relancé")
    dire(not any("n'avance plus" in m for m in messages(t, "p-dev")), "demande « à relire » : le développeur attend une décision, jamais relancé « n'avance plus »")
    (dem / "dev.json").write_text(json.dumps({"sujet": "dev", "branche": "equipe/dev", "commit": "abc", "agent": "p-dev",
                                              "etat": "à finir", "demande": "2026-10-05T10:00", "resume": "r"}))
    berger(t, env, "superviser"); (t / ".supervision.json").unlink(missing_ok=True)
    dire(not any("n'avance plus" in m for m in messages(t, "p-dev")), "demande « à finir » : idem")
    (dem / "dev.json").write_text(json.dumps({"sujet": "dev", "branche": "equipe/dev", "commit": "abc", "agent": "p-dev",
                                              "etat": "à relire", "demande": "2026-10-05T10:00", "resume": "r"}))
    (t / ".supervision.json").unlink(missing_ok=True)
    n = len(messages(t, "chef")); berger(t, env, "superviser")
    dire(len(messages(t, "chef")) == n, "pas de relance répétée avant le délai (15 min)")

    # 07-08/10 : fusion déjà demandée par le chef, en attente du PROPRIÉTAIRE → plus aucun rappel « à relire » au chef
    v = t / "courtier/validations"; v.mkdir(parents=True, exist_ok=True)
    (v / "5.json").write_text(json.dumps({"n": 5, "agent": "chef", "outil": "p-chef", "verbe": "fusionner", "args": ["dev"],
                                          "apercu": "fusionner equipe/dev", "valideur": None, "demande": "2026-10-07T21:34"}))
    (t / "equipes/.relances.json").unlink(missing_ok=True); n = len(messages(t, "chef"))
    for _ in range(3): berger(t, env, "superviser"); (t / "equipes/.relances.json").unlink(missing_ok=True)   # délai levé à chaque tour
    dire(not any("attend ta relecture" in m for m in messages(t, "chef")[n:]), "fusion demandée, en attente du propriétaire → 0 rappel au chef")
    # même demande d'un AUTRE projet : la clé (outil, sujet) ne doit pas masquer un sujet homonyme
    (v / "5.json").write_text(json.dumps({"n": 5, "agent": "chef", "outil": "autre-chef", "verbe": "fusionner", "args": ["dev"],
                                          "apercu": "x", "valideur": None}))
    berger(t, env, "superviser")
    dire(any("attend ta relecture" in m for m in messages(t, "chef")[n:]), "fusion demandée dans un autre projet → la demande de p reste à relire")
    # validation sortie de la file (échec ou refus → <n>.fait.json) : la demande redevient à relire, le chef est relancé
    (v / "5.json").write_text(json.dumps({"n": 5, "agent": "chef", "outil": "p-chef", "verbe": "fusionner", "args": ["dev"],
                                          "apercu": "fusionner equipe/dev", "valideur": None}))
    (t / "equipes/.relances.json").unlink(missing_ok=True); berger(t, env, "superviser"); n = len(messages(t, "chef"))
    (v / "5.json").rename(v / "5.fait.json"); (t / "equipes/.relances.json").unlink(missing_ok=True); berger(t, env, "superviser")
    dire(any("attend ta relecture" in m for m in messages(t, "chef")[n:]), "validation sortie de la file (échec/refus) → le chef est de nouveau relancé")
    (v / "5.fait.json").unlink()

    # 08/10 : demande fusionnée, développeur encore ouvert → le CHEF DE PROJET (qui ferme, spec 2026-10-13) est invité à le fermer, au plus une fois par jour
    (dem / "dev.json").write_text(json.dumps({"sujet": "dev", "branche": "equipe/dev", "commit": "abc", "agent": "p-dev",
                                              "etat": "fusionnée", "fusionnee": "2026-10-08T06:22", "resume": "r"}))
    (t / "equipes/.relances.json").unlink(missing_ok=True); n = len(messages(t, "coord")); nc = len(messages(t, "chef"))
    for _ in range(3): berger(t, env, "superviser")
    fermer = [m for m in messages(t, "chef")[nc:] if "toujours ouvert" in m]
    dire(len(fermer) == 1 and "equipe fermer --fichier .transport/requete.json (JSON : p, dev)" in fermer[0], "fusionnée, développeur ouvert → chef de projet invité à le fermer, UNE fois (pas toutes les 15 min)")
    dire(not any("toujours ouvert" in m for m in messages(t, "coord")[n:]), "fusionnée → rien au coordinateur (il ne ferme plus)")
    dire(not any("attend ta relecture" in m for m in messages(t, "chef")[nc:]), "fusionnée → aucun rappel de relecture au chef")
    dire(os.path.isdir(t / "agents/p-dev"), "jamais de fermeture automatique (copie et pile ne sont pas supprimées par la supervision)")

    # 13/10 : la demande de FINITION du chef (finition=True, agent = le chef) fusionnée → aucune invitation à « fermer »
    (dem / "fin.json").write_text(json.dumps({"sujet": "fin", "branche": "equipe/fin", "commit": "abc", "agent": "chef", "finition": True,
                                              "etat": "fusionnée", "fusionnee": "2026-10-13T06:22", "resume": "r"}))
    (dem / "fin2.json").write_text(json.dumps({"sujet": "fin2", "branche": "equipe/fin2", "commit": "abc", "agent": "chef",
                                               "etat": "fusionnée", "fusionnee": "2026-10-13T06:22", "resume": "r"}))
    (t / "equipes/.relances.json").unlink(missing_ok=True); nc = len(messages(t, "chef"))
    for _ in range(2): berger(t, env, "superviser"); (t / "equipes/.relances.json").unlink(missing_ok=True)
    fermer = [m for m in messages(t, "chef")[nc:] if "toujours ouvert" in m]
    dire(not any("fin" in m.split("«")[1].split("»")[0] for m in fermer), "finition du chef fusionnée (finition=True, ou agent = chef) → aucune invitation à fermer")
    dire(any("equipe fermer --fichier .transport/requete.json (JSON : p, dev)" in m for m in fermer), "…alors que celle d'un développeur fusionnée, encore ouvert, invite toujours à fermer")
    (dem / "fin.json").unlink(); (dem / "fin2.json").unlink(); (t / "equipes/.relances.json").unlink(missing_ok=True)

    (dem / "dev.json").write_text(json.dumps({"sujet": "dev", "agent": "p-dev", "etat": "renvoyée", "renvoyee": "x", "motif": "corrige y", "renvois": 2}))
    (t / ".supervision.json").unlink(); (t / "equipes/.relances.json").unlink(missing_ok=True)
    berger(t, env, "superviser")
    dire(any("RENVOYÉE" in m for m in messages(t, "p-dev")), "demande renvoyée → le développeur est relancé")
    dire(any("renvoyée 2 fois" in m for m in messages(t, "chef")), "trop de renvois (condition d'arrêt, N) → le chef de projet est alerté")
    dire(not any("renvoyée" in m for m in messages(t, "coord")), "N renvois → pas encore le coordinateur")
    d = json.loads((dem / "dev.json").read_text()); d["renvois"] = 3; (dem / "dev.json").write_text(json.dumps(d)); berger(t, env, "superviser")
    dire(any("renvoyée 3 fois" in m for m in messages(t, "coord")), "N+1 renvois → le coordinateur est alerté (escalade)")

    (t / "agents/p-dev/CHECKLIST.md").write_text("# x\n- [ ] étape\n⚠ Bloqué : droit manquant\n")
    for _ in range(3): berger(t, env, "superviser")
    dire(sum("BLOQUÉ" in m for m in messages(t, "chef")) == 1, "blocage → chef de projet prévenu UNE seule fois (empreinte stable)")
    dire(sum("BLOQUÉ" in m for m in messages(t, "coord")) == 1, "blocage persistant → coordinateur prévenu ensuite, UNE seule fois")
    notes = (t / "courtier/notifications.log").read_text() if (t / "courtier/notifications.log").exists() else ""
    dire(notes.count("décision nécessaire") >= 1, "blocage persistant → le propriétaire est notifié")

    etat = json.loads((t / "faux/etat.json").read_text()); del etat["agents"]["p-dev-claude"]; (t / "faux/etat.json").write_text(json.dumps(etat))
    (t / "agents/p-dev/CHECKLIST.md").write_text("# x\n- [ ] étape\n")
    berger(t, env, "superviser")
    appels = (t / "faux/appels.log").read_text()
    dire('"rouvert automatiquement' in (t / f"agents/p-dev/memory/{time.strftime('%Y-%m-%d')}.md").read_text() or "split" in appels or "workspace\", \"create" in appels,
         "agent de mission arrêté → réouverture automatique tentée")

    # décision de validation : un fichier vide (en cours d'écriture) n'est JAMAIS un refus
    v = t / "courtier/validations"; v.mkdir(parents=True, exist_ok=True)
    (v / "7.json").write_text(json.dumps({"n": 7, "agent": "chef", "outil": "inconnu", "verbe": "x", "args": [], "apercu": "test", "valideur": "coord"}))
    (v / "7.decision").write_text("")
    code = ("import runpy, sys; sys.argv=['courtier']; g = runpy.run_path(sys.argv[0] if False else %r, run_name='essai'); g['traiter_decisions']()"
            % str(t / "courtier/courtier"))
    subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    dire((v / "7.json").exists() and not (v / "7.fait.json").exists(), "décision illisible (fichier vide) : ni refus ni acceptation, relue plus tard")
    (v / "7.decision").write_text("refuser\npar=coord\n")
    subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    f = json.loads((v / "7.fait.json").read_text()) if (v / "7.fait.json").exists() else {}
    dire(f.get("etat") == "refusé" and f.get("par") == "coord", "décision complète : appliquée et attribuée au bon décideur (pas au propriétaire)")
    for _ in range(40):                                                   # envoyée en arrière-plan : on attend jusqu'à 10 s
        if any("Décision sur ta demande n° 7" in m for m in messages(t, "chef")): break
        time.sleep(0.25)
    dire(any("Décision sur ta demande n° 7" in m for m in messages(t, "chef")), "la décision est ENVOYÉE au demandeur")

    # 13/10 : alertes signées de la supervision (jamais du propriétaire), et plus aucune alerte quand la mission est terminée
    def echanges():
        f = t / "courtier/echanges.jsonl"
        return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []
    sig = [e for e in echanges() if e["genre"] in ("alerte", "message") and e["a"] in ("chef", "coord", "p-dev", "Proprio")]
    dire(any(e["genre"] == "alerte" for e in sig) and all(e["de"] == "Berger (supervision)" for e in sig if e["genre"] == "alerte"),
         "alertes automatiques signées « Berger (supervision) »")
    dire(not any(e["de"] == "Proprio" for e in echanges()), "aucun échange automatique signé du nom du propriétaire")
    etat = json.loads((t / "faux/etat.json").read_text()); etat["agents"]["p-dev-claude"] = "p3"; (t / "faux/etat.json").write_text(json.dumps(etat))
    (dem / "dev.json").unlink(); (t / ".supervision.json").unlink(missing_ok=True); (t / "equipes/.relances.json").unlink(missing_ok=True)
    (t / "agents/p-dev/CHECKLIST.md").write_text("# x\n- [x] étape\nTerminé 2026-10-13 12:00\n")
    vieux = time.time() - 3600
    for f in (t / "agents/p-dev").rglob("*"): os.utime(f, (vieux, vieux))
    n = len(messages(t, "p-dev")); ne = len(echanges())
    for _ in range(3): berger(t, env, "superviser"); (t / ".supervision.json").unlink(missing_ok=True)
    dire(len(messages(t, "p-dev")) == n and not any(e["a"] in ("chef", "coord") and "p-dev" in e["texte"] for e in echanges()[ne:]),
         "checklist « Terminé » : aucune relance « n'avance plus » ni alerte")
    # 13/10 (minuit) : checklist Terminé puis RANGÉE par le planificateur (plus de CHECKLIST.md, MISSION.md reste) → aucune alerte
    (t / "agents/p-dev/CHECKLIST.md").unlink(); (t / "agents/p-dev/historique").mkdir(exist_ok=True)
    (t / "agents/p-dev/historique/2999-01-01_2320_x.md").write_text("# x\n- [x] étape\nTerminé 2999-01-01 23:20\n")
    ne = len(echanges())
    for _ in range(3): berger(t, env, "superviser"); (t / ".supervision.json").unlink(missing_ok=True)
    dire(len(messages(t, "p-dev")) == n and not any(e["a"] in ("chef", "coord") and "p-dev" in e["texte"] for e in echanges()[ne:]),
         "checklist Terminé puis rangée dans historique/ : aucune relance ni alerte")
    # une checklist rangée AVANT le début de la mission ne la termine pas : mission vraiment arrêtée → relancée comme avant
    (t / "agents/p-dev/historique/2999-01-01_2320_x.md").rename(t / "agents/p-dev/historique/2000-01-01_0000_x.md")
    berger(t, env, "superviser"); (t / ".supervision.json").unlink(missing_ok=True)
    dire(any("n'avance plus" in m for m in messages(t, "p-dev")[n:]), "checklist rangée avant la mission : mission arrêtée → relance comme avant")
    n = len(messages(t, "p-dev")); (t / "agents/p-dev/historique/2000-01-01_0000_x.md").unlink()
    (t / "agents/p-dev/CHECKLIST.md").write_text("# x\n- [ ] étape\nAbandonné : plus utile\n")
    for _ in range(2): berger(t, env, "superviser"); (t / ".supervision.json").unlink(missing_ok=True)
    dire(len(messages(t, "p-dev")) == n, "checklist « Abandonné » : aucune relance")
    (t / "agents/p-dev/CHECKLIST.md").write_text("# x\n- [ ] étape\n")
    for f in (t / "agents/p-dev").rglob("*"): os.utime(f, (vieux, vieux))
    berger(t, env, "superviser")
    dire(any("(supervision) : ta mission n'avance plus" in m for m in messages(t, "p-dev")[n:]), "mission vivante : la relance part toujours, signée supervision")
print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
