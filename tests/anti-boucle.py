#!/usr/bin/env python3
"""Tests du garde-fou anti-boucle (spec docs/plans/2026-10-15-anti-boucle-spec.md) — sans modèle, sans vrai Herdr, installation
JETABLE, NEUTRES AU MOTEUR (le courtier est appelé directement ; aucun moteur n'est lancé) :
  (a) courtier : le même appel refusé au-delà de `boucle_max` en une heure sans sollicitation ; autres arguments et « aide » non
      comptés ; appels espacés par une sollicitation acceptés ; gardien prévenu UNE seule fois ; Synthèse ; interrupteur (0) ;
  (c) relance : un agent seulement occupé n'est JAMAIS relancé (ex. longue tâche du propriétaire en direct) ; relancé seulement si
      le courtier a repéré une boucle ET rien depuis `inactif_min` minutes ; interrupteur `inactif_min = 0`.
Usage : python3 tests/anti-boucle.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit, _herdr_api_factice

SRC = Path(__file__).resolve().parent.parent
N = 3
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


# Herdr à état : « statut » = l'état annoncé des panneaux (idle / working) ; ctrl+c arrête l'agent, « agent start » le remet.
FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["FAUX_HERDR"]; etat = json.load(open(T + "/etat.json")); a = sys.argv[1:]
if a == ["agent", "prompt"]:                                              # API Herdr (adaptateur) : corps sur stdin
    d = json.load(sys.stdin); a += [d["target"], d["text"]]
with open(T + "/appels.log", "a") as f: f.write(json.dumps(a) + "\n")
r = {}
if a[:2] == ["agent", "list"]: r = {"agents": [{"name": n, "pane_id": p} for n, p in etat["agents"].items()]}
elif a[:2] == ["workspace", "list"]: r = {"workspaces": [{"workspace_id": w} for w in etat["espaces"]]}
elif a[:2] == ["pane", "get"]: r = {"pane": {"pane_id": a[2], "agent_status": etat.get("statut", "idle")}}
elif a[:2] == ["pane", "send-keys"] and a[3] == "ctrl+c": etat["agents"] = {n: p for n, p in etat["agents"].items() if p != a[2]}; etat["statut"] = "idle"
elif a[:2] == ["agent", "start"]: etat["agents"][a[2]] = a[a.index("--pane") + 1]; r = {"agent": a[2]}
json.dump(etat, open(T + "/etat.json", "w")); print(json.dumps({"result": r}))
'''
FAUX_MOTEUR = "#!/bin/sh\nexit 0\n"

# Le courtier, dans UN processus (l'historique des appels est en mémoire) : une suite d'étapes {agent, req} ou {sollicite: agent}.
SERIE = r'''
import json, os, runpy, sys, time
g = runpy.run_path(sys.argv[1], run_name="essai")
sortie = []
for n, e in enumerate(json.loads(sys.argv[2])):
    if "sollicite" in e:
        time.sleep(0.05); g["SOLLICITATIONS"].mkdir(parents=True, exist_ok=True); p = g["SOLLICITATIONS"] / e["sollicite"]; p.touch(); os.utime(p, None); time.sleep(0.05); continue
    d = g["AGENTS"] / e["agent"] / "courrier"; (d / "encours").mkdir(parents=True, exist_ok=True)
    f = d / "encours" / f"{n}.json"; f.write_text(json.dumps(e["req"]))
    g["traiter"](e["agent"], f, {})
    r = d / "reponses" / f"{n}.json"; sortie.append(json.loads(r.read_text())); r.unlink()
time.sleep(float(sys.argv[3]) if sys.argv[3:] else 0)
print("JSON" + json.dumps(sortie))
'''


def lire(a, *args): return {"agent": a, "req": {"outil": "essai", "verbe": "lire", "args": list(args)}}


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}"); (m / "depot").mkdir()

    def config(boucle_max=N, relance=""):
        (i / "config.toml").write_text(
            f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n\n[courtier]\nboucle_max = {boucle_max}\n\n{relance}'
            f'[outils.essai]\ntype = "essai"\n\n[outils.berger-admin]\ntype = "commandes"\ndossier = "{i}"\n[outils.berger-admin.lecture]\netat = "true"\n'
            f'[outils.berger-admin.actions]\ninstaller = "echo installé"\n\n'
            f'[equipes.berger]\ndepot = "{m}/depot"\nchef_projet = "chef"\ncoordinateur = "chef"\nprefixe = "berger/"\nfusion_par = "proprietaire"\ninstaller_outil = "berger-admin installer"\n')
    config()
    for a in ("chef", "boucleur", "calme", "occupe", "veille", "direct", "eteint"):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nmoteur = claude\npanneaux = claude\nmur = ouvert\nheures = aucune\noutils = essai\n")
    f = m / "faux"; f.mkdir(); b = m / ".local/bin"; b.mkdir(parents=True)
    (f / "herdr").write_text(FAUX_HERDR); (f / "notify-send").write_text("#!/bin/sh\nexit 0\n")
    for x in ("claude", "codex"): (b / x).write_text(FAUX_MOTEUR)
    for x in (f / "herdr", f / "notify-send", b / "claude", b / "codex"): os.chmod(x, 0o755)
    etat = lambda **k: (f / "etat.json").write_text(json.dumps({"agents": {}, "espaces": [], **k}))
    etat()
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "FAUX_HERDR": str(f), "BERGER_HERDR": str(f / "herdr"),
           "BERGER_NOTIFY_SEND": str(f / "notify-send"), "GARDE_TEST": "1"}
    _herdr_api_factice.installer(env)
    env.pop("AGENT_PANNE", None)

    def serie(etapes, attente=0):
        r = subprocess.run([sys.executable, "-c", SERIE, str(i / "courtier/courtier"), json.dumps(etapes), str(attente)],
                           env=env, capture_output=True, text=True, timeout=180)
        l = next((x for x in r.stdout.splitlines() if x.startswith("JSON")), None)
        if l is None: raise SystemExit(f"ÉCHEC série illisible : {(r.stdout + r.stderr)[-400:]}")
        return json.loads(l[4:])

    def berger(*args): return subprocess.run([sys.executable, str(i / "bin/berger"), *args], env=env, capture_output=True, text=True, timeout=180)
    refuse = lambda r: r.get("ok") is False and "boucle" in r.get("erreur", "")
    attente = lambda a: sorted((i / "agents" / a / "messages/attente").glob("*.json")) if (i / "agents" / a / "messages/attente").is_dir() else []

    # ── (a) le même appel, N+1 fois ──
    r = serie([lire("boucleur", "etat")] * (N + 3), attente=6)
    dire(all(x.get("ok") is True for x in r[:N]), f"les {N} premiers appels identiques passent")
    dire(all(refuse(x) for x in r[N:]), f"le {N + 1}e appel identique (et les suivants) refusés poliment, motif « boucle »")
    dire("HEARTBEAT.md" in r[N]["erreur"] and "checklist" in r[N]["erreur"], "le refus dit quoi faire (HEARTBEAT.md, ou ⚠ Bloqué dans la checklist)")
    log = (i / "courtier/appels.log").read_text()
    dire("boucle" in log, "le refus est écrit au journal du courtier (appels.log)")
    q = attente("chef")
    dire(len(q) == 1 and "boucleur" in json.loads(q[0].read_text())["texte"] and "pas prévenu de nouveau" in json.loads(q[0].read_text())["texte"],
         "le gardien (chef) est prévenu UNE seule fois malgré 3 refus")
    b_ = json.loads((i / "courtier/boucles.json").read_text())
    dire(b_.get("boucleur", {}).get("appel", "").startswith("essai lire etat") and b_["boucleur"]["n"] == N, "courtier/boucles.json : la boucle est inscrite (lue par la Synthèse et la relance)")
    code = f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');print('SYN'+repr([x for x in g['alertes_synthese']() if 'boucle' in x[2]]))"
    sy = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60).stdout
    dire("SYN[('jaune'" in sy and "boucle" in sy and "essai lire etat" in sy, "Synthèse : une alerte jaune « boucle » nomme l'agent et l'appel")

    # ── autres arguments, aide, appels espacés ──
    r = serie([lire("calme", f"x{k}") for k in range(2 * N)] + [{"agent": "calme", "req": {"outil": "essai", "verbe": "aide", "args": []}}] * (2 * N))
    dire(all(x.get("ok") is True for x in r), "des appels qui diffèrent par un argument ne se cumulent pas ; « aide » n'est jamais compté")
    r = serie([lire("calme", "a")] * N + [{"sollicite": "calme"}] + [lire("calme", "a")] * N + [{"sollicite": "calme"}] + [lire("calme", "a")] * N)
    dire(len(r) == 3 * N and all(x.get("ok") is True for x in r), f"{N} appels identiques espacés par une sollicitation (message, réveil…) : tous passent")
    r = serie([lire("direct", f"suivi{k % 2}") for k in range(2)] + [lire("direct", "x")] * N + [{"sollicite": "direct"}, lire("direct", "x")])
    dire(r[-1].get("ok") is True, "une sollicitation remet le compte à zéro même après N appels")

    # ── interrupteur ──
    config(0)
    r = serie([lire("eteint", "etat")] * (3 * N))
    dire(all(x.get("ok") is True for x in r), "boucle_max = 0 : rien n'est refusé (interrupteur)")
    config()

    # ── (c) relance d'un agent « au travail » ──
    def pret(a, statut="working"):
        d = i / "agents" / a; (d / ".herdr.json").write_text(json.dumps({"workspace": "w1", "agents": {"claude": "p1"}}))
        conv = m / ".claude/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(d)); conv.mkdir(parents=True, exist_ok=True)
        (conv / "conv-1.jsonl").write_text('{"entrypoint":"cli"}\n'); (d / ".conversation-claude").write_text("conv-1\n")
        etat(agents={f"{a}-claude": "p1"}, espaces=["w1"], statut=statut)
        (f / "appels.log").unlink(missing_ok=True)
    demarre = lambda: any(x[:2] == ["agent", "start"] for x in [json.loads(l) for l in (f / "appels.log").read_text().splitlines()]) if (f / "appels.log").exists() else False
    sol = i / "courtier/sollicitations"; sol.mkdir(parents=True, exist_ok=True)

    pret("occupe")
    r = berger("relancer", "occupe", "claude")
    dire(r.returncode != 0 and "rien relancé" in r.stdout + r.stderr and not demarre(), "agent occupé SANS boucle (longue tâche du propriétaire en direct) : relance refusée, rien arrêté")
    dire("aucune boucle repérée" in r.stdout + r.stderr, "…et le refus en donne la raison")
    (sol / "occupe").write_text(""); os.utime(sol / "occupe", (time.time() - 5 * 3600,) * 2)
    r = berger("relancer", "occupe", "claude")
    dire(r.returncode != 0 and not demarre(), "agent occupé, sans aucune sollicitation depuis 5 h mais sans boucle : TOUJOURS jamais relancé")
    r = serie([lire("occupe", f"tache{k}") for k in range(5 * N)])
    dire(all(x.get("ok") is True for x in r), "ce même agent, qui travaille sans répéter d'appel, n'est ni bloqué ni signalé")

    # boucle réelle repérée par le courtier chez « veille » (aucune sollicitation connue)
    pret("veille")
    serie([lire("veille", "etat")] * (N + 1), attente=1)
    dire("veille" in json.loads((i / "courtier/boucles.json").read_text()), "boucle repérée chez « veille »")
    (sol / "veille").write_text("")                                                # sollicité il y a 0 minute, avant le dernier refus
    os.utime(sol / "veille", (time.time() - 5, time.time() - 5))
    r = berger("relancer", "veille", "claude")
    dire(r.returncode != 0 and not demarre() and "moins de 30 minutes" in r.stdout + r.stderr, "boucle repérée mais sollicité il y a moins de 30 minutes : relance refusée")
    os.utime(sol / "veille", (time.time() - 3600, time.time() - 3600))               # sollicité il y a 1 h, boucle repérée APRÈS
    bj = json.loads((i / "courtier/boucles.json").read_text()); bj["veille"]["dernier_refus"] = time.time() - 60; bj["veille"]["depuis"] = time.time() - 600
    (i / "courtier/boucles.json").write_text(json.dumps(bj))
    config(relance="[relance]\ninactif_min = 0\n\n")
    r = berger("relancer", "veille", "claude")
    dire(r.returncode != 0 and not demarre(), "[relance] inactif_min = 0 : relance refusée même en boucle (interrupteur)")
    config()
    r = berger("relancer", "veille", "claude")
    dire(r.returncode == 0 and demarre(), "occupé + boucle repérée + rien depuis 30 minutes : relancé, dans la même conversation")
    dire("boucle repérée" in (i / "agents/veille/memory" / f"{time.strftime('%Y-%m-%d')}.md").read_text(), "…et la relance est tracée au journal (occupé, boucle repérée)")
    pret("direct")
    r = berger("relancer", "direct", "claude")
    dire(r.returncode != 0 and not demarre(), "un agent qui a seulement travaillé en direct (aucune boucle) n'est pas relançable")
    # sollicitation = effacement de la boucle (message reçu) : plus relançable
    pret("veille")
    subprocess.run([sys.executable, str(i / "bin/berger"), "parler", "veille", "--stdin", "--de", "Proprio"], input="bonjour",
                   env=env, capture_output=True, text=True, timeout=180)
    dire("veille" not in json.loads(code and subprocess.run([sys.executable, "-c", "import runpy,sys,json;sys.argv=['b'];g=runpy.run_path(%r,run_name='x');print(json.dumps(list(g['boucles_actives']())))" % str(i / 'bin/berger')],
                                                              env=env, capture_output=True, text=True).stdout), "un message reçu clôt la boucle (Synthèse et relance)")
    # la règle écrite
    regles = (SRC / "commun/REGLES.md").read_text().lower(); skill = (SRC / "commun/skills/berger/SKILL.md").read_text().lower()
    dire("pas de boucle maison" in regles and "heartbeat.md" in regles.split("pas de boucle maison")[-1][:500], "commun/REGLES.md : « pas de boucle maison », la veille passe par HEARTBEAT.md")
    dire("pas de boucle maison" in skill, "skill berger : la même règle")
    dire(not re.search(r"cron|schedulewakeup|croncreate", regles.split("pas de boucle maison")[-1][:500]), "la règle ne nomme aucun outil de moteur")

sys.exit(1 if ko else 0)
