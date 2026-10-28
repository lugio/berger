#!/usr/bin/env python3
"""Tests des textes du courtier et du canal vers le chef (16/10/2026) — sans modèle, sans vrai Herdr, installation JETABLE, le
courtier appelé directement. Spec : docs/plans/2026-10-16-courtier-textes-spec.md (1 et 2). Usage : python3 tests/courtier-textes.py
1. un texte trop long est REFUSÉ, jamais coupé : mission de M+1 caractères refusée avec le message exact, sans MISSION.md ; mission de
   M caractères arrivée intacte (MISSION.md porte exactement le texte) — `[courtier] mission_max` (6 000 par défaut, réglable) ;
   ailleurs, 81 caractères refusés avec le même message ; délégation trop longue refusée ; agents Claude et Codex ;
2. le gardien (chef de l'équipe à installer_outil) écrit au chef de chaque équipe, ne lui confie pas de mission ; un autre agent
   ne lui écrit pas ; une équipe avec coordinateur est inchangée."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, subprocess, sys, tempfile
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

PANNEAU = r'''
import json, runpy, sys
g = runpy.run_path(sys.argv[1], run_name="essai")
g["collecter"]("essai", {"outil": "lent", "verbe": "lire", "args": json.loads(sys.argv[2])})
print((g["PANNEAUX"] / "essai.json").read_text())
'''

DROITS = r'''
import json, runpy, sys
g = runpy.run_path(sys.argv[1], run_name="essai")
print(json.dumps({a: sorted(g["droits"](a)) for a in sys.argv[2:]}))
'''

# Un texte sans chiffre (garde-fou de secrets) et sans double espace (la mission est remise sur une ligne) : n caractères exactement.
def texte(n): return ("mission longue sans coupure " * (n // 20 + 2))[:n - 1] + "Z"


def installation(m, plus=""):
    t = m / "berger"
    _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}")
    (t / "config.toml").write_text(
        f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n\n[missions]\nmax = 9\n\n{plus}'
        f'[equipes.socle]\ndepot = "{m}/depot-socle"\nchef_projet = "gardien"\ninstaller_outil = "lent installer"\nfusion_par = "proprietaire"\n\n'
        f'[equipes.metier]\ndepot = "{m}/depot-metier"\nchef_projet = "metier-chef"\n\n'
        f'[equipes.portail]\ndepot = "{m}/depot-portail"\nchef_projet = "portail-chef"\ncoordinateur = "coord"\n')
    agents = {"patron-claude": ("claude", "outils = mission:exec-claude, mission:exec-codex, deleguer:exec-claude, lent\n"),
              "patron-codex": ("codex", "outils = mission:exec-claude, mission:exec-codex, deleguer:exec-codex, lent\n"),
              "exec-claude": ("claude", ""), "exec-codex": ("codex", ""), "gardien": ("claude", ""), "metier-chef": ("codex", ""),
              "portail-chef": ("claude", ""), "coord": ("claude", ""), "autre": ("codex", "")}
    panes = {}
    for n, (a, (moteur, extra)) in enumerate(agents.items()):
        d = t / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = {moteur}\npanneaux = {moteur}\nheures = aucune\n{extra}")
        panes[f"{a}-{moteur}"] = f"p{n}"; (d / ".herdr.json").write_text(json.dumps({"workspace": "w-" + a, "agents": {moteur: f"p{n}"}}))
    (t / "courtier/outils/lent.py").write_text(
        "class Outil:\n    def __init__(self, reglages, secret, verifier_hote):\n        self.verbes = {'lire': self.lire}\n"
        "        self.ecritures = {'installer': (lambda a: 'installer', lambda a: 'fait')}\n    def hotes(self): return {}\n    def lire(self, args):\n        \"\"\"lecture\"\"\"\n"
        "        return [len(a) for a in args]\n")
    with open(t / "config.toml", "a") as c: c.write('\n[outils.lent]\ntype = "lent"\n')
    f = m / "faux"; f.mkdir(); (f / "herdr").write_text(FAUX_HERDR); (f / "notify-send").write_text("#!/bin/sh\nexit 0\n")
    for x in ("herdr", "notify-send"): os.chmod(f / x, 0o755)
    (f / "etat.json").write_text(json.dumps({"agents": panes, "espaces": [f"w-{a}" for a in agents]}))
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(t), "FAUX_HERDR": str(f), "BERGER_HERDR": str(f / "herdr"),
           "BERGER_NOTIFY_SEND": str(f / "notify-send")}
    _herdr_api_factice.installer(env)
    return t, env


def appel(t, env, agent, outil, verbe, *args):
    r = subprocess.run([sys.executable, "-c", APPEL, str(t / "courtier/courtier"), agent, json.dumps({"outil": outil, "verbe": verbe, "args": list(args)})],
                       env=env, capture_output=True, text=True, timeout=120)
    try: return json.loads(r.stdout)
    except ValueError: return {"ok": None, "erreur": (r.stderr or r.stdout)[-300:]}


def message_trop_long(n, m): return f"trop long ({n} caractères, {m} au plus) : mets le détail dans un fichier de ton dossier et cite son chemin"


def corps_mission(t, a):
    f = t / "agents" / a / "MISSION.md"
    return f.read_text().split("\n\n", 1)[1].rstrip("\n") if f.is_file() else None


def finir_mission(t, a):
    (t / "agents" / a / "MISSION.md").unlink(missing_ok=True)


with tempfile.TemporaryDirectory() as td:
    # ── 1 : défaut 6 000 ; Claude et Codex, dans les deux sens ──
    t, env = installation(Path(td) / "a")
    M = 6000
    for patron, cible in (("patron-claude", "exec-codex"), ("patron-codex", "exec-claude")):
        r = appel(t, env, patron, "mission", "confier", cible, texte(M + 1))
        dire(r.get("ok") is False and r.get("erreur") == message_trop_long(M + 1, M) and corps_mission(t, cible) is None,
             f"{patron} → {cible} : mission de {M + 1} caractères REFUSÉE avec le message exact, aucune MISSION.md ({r.get('erreur', '')[:70]})")
        r = appel(t, env, patron, "mission", "confier", cible, texte(M))
        dire(r.get("ok") is True and corps_mission(t, cible) == texte(M),
             f"{patron} → {cible} : mission de {M} caractères arrivée INTACTE (MISSION.md = le texte)" + ("" if r.get("ok") else f" — {r.get('erreur')}"))
        finir_mission(t, cible)
    dire(corps_mission(t, "exec-claude") is None and appel(t, env, "patron-claude", "mission", "confier", "exec-claude", texte(2500)).get("ok") is True
         and corps_mission(t, "exec-claude") == texte(2500), "mission de 2 500 caractères (coupée à 2 000 avant le 16/10) : intacte")
    finir_mission(t, "exec-claude")
    r = appel(t, env, "patron-claude", "lent", "lire", "x" * 80)
    dire(r.get("ok") is True and r.get("donnees") == [80], "argument de 80 caractères (hors texte) : accepté, intact")
    r = appel(t, env, "patron-codex", "lent", "lire", "x" * 81)
    dire(r.get("ok") is False and r.get("erreur") == message_trop_long(81, 80), "argument de 81 caractères (hors texte) : REFUSÉ, même message (M = 80)")
    r = appel(t, env, "patron-claude", "deleguer", "exec-claude", texte(M - 10), texte(20))
    dire(r.get("ok") is False and r.get("erreur") == message_trop_long(M + 11, M), "délégation : le texte joint de M+11 caractères est REFUSÉ")
    log = (t / "courtier/appels.log").read_text()
    dire("trop long" in log and texte(M + 1)[:200] not in log, "le refus est journalisé, sans recopier le texte")
    # Fusion des deux lignes (26/10) : plus aucune coupure silencieuse, ni d'un texte ni du nombre d'arguments.
    r = appel(t, env, "patron-claude", "lent", "lire", *(["x"] * 6))
    dire(r.get("ok") is False and "trop d'arguments" in r.get("erreur", ""), "six arguments : REFUSÉS (avant : le sixième tombait en silence)")
    r = appel(t, env, "patron-claude", "lent", "lire", *(["x"] * 5))
    dire(r.get("ok") is True and r.get("donnees") == [1] * 5, "cinq arguments : acceptés, intacts")
    pan = lambda args: json.loads(subprocess.run([sys.executable, "-c", PANNEAU, str(t / "courtier/courtier"), json.dumps(args)], env=env,
                                                 capture_output=True, text=True, timeout=60).stdout or "{}")
    pa, pb = pan(["x" * 81]), pan(["x" * 80])
    dire(pa.get("ok") is False and "trop longs" in pa.get("erreur", "") and pb.get("ok") is True and "80" in "".join(pb.get("lignes", [])),
         "panneau : argument de 81 caractères REFUSÉ (avant : coupé à 80), 80 accepté intact")
    source = (SRC / "courtier/courtier").read_text()
    coupes = re.findall(r"str\(a\)\s*\[:|\bargs\b[^\n#]*\]\s*\[:\s*5\s*\]|join\(args\)\s*\[:\s*\d{3,}", source)
    dire(not coupes, f"courtier/courtier : aucune coupure d'un argument (str(a)[:N], args[:5], texte joint coupé) {coupes or ''}")

    # ── 1 bis : mission_max réglable ──
    t2, env2 = installation(Path(td) / "b", "[courtier]\nmission_max = 300\n\n")
    r = appel(t2, env2, "patron-codex", "mission", "confier", "exec-codex", texte(301))
    dire(r.get("ok") is False and r.get("erreur") == message_trop_long(301, 300), "[courtier] mission_max = 300 : 301 caractères refusés")
    r = appel(t2, env2, "patron-codex", "mission", "confier", "exec-codex", texte(300))
    dire(r.get("ok") is True and corps_mission(t2, "exec-codex") == texte(300), "[courtier] mission_max = 300 : 300 caractères intacts")

    # ── 2 : canal du gardien vers chaque chef ──
    dr = json.loads(subprocess.run([sys.executable, "-c", DROITS, str(t / "courtier/courtier"), "gardien", "coord", "autre", "metier-chef"],
                                   env=env, capture_output=True, text=True, timeout=60).stdout or "{}")
    g = set(dr.get("gardien", []))
    dire({"ecrire:metier-chef", "ecrire:portail-chef"} <= g and not any(x.startswith("mission:") for x in g) and "ecrire:gardien" not in g,
         f"gardien : ecrire:<chef> pour chaque équipe, jamais mission:, jamais vers soi ({sorted(g)})")
    dire({"ecrire:portail-chef", "mission:portail-chef"} <= set(dr.get("coord", [])) and "ecrire:metier-chef" not in dr.get("coord", []),
         "équipe avec coordinateur : ses droits vers le chef inchangés, rien vers une autre équipe")
    dire(dr.get("autre") == [] and dr.get("metier-chef") == ["metier-chef"], "un autre agent, un autre chef : aucun canal ajouté")
    r = appel(t, env, "gardien", "ecrire", "metier-chef", "le canal vers toi est rouvert")
    dire(r.get("ok") is True, "gardien (claude) → chef sans coordinateur (codex) : message accepté" + ("" if r.get("ok") else f" — {r.get('erreur')}"))
    dire(appel(t, env, "gardien", "ecrire", "portail-chef", "bonjour").get("ok") is True, "gardien → chef d'une équipe avec coordinateur : accepté")
    r = appel(t, env, "gardien", "mission", "confier", "metier-chef", "une mission")
    dire(r.get("ok") is False and "pas le droit" in r.get("erreur", "") and corps_mission(t, "metier-chef") is None,
         "mission du gardien au chef : REFUSÉE, aucune MISSION.md")
    r = appel(t, env, "autre", "ecrire", "metier-chef", "bonjour")
    dire(r.get("ok") is False and "pas le droit" in r.get("erreur", ""), "un autre agent → le chef : refusé")
    dire(appel(t, env, "coord", "ecrire", "portail-chef", "bonjour").get("ok") is True, "coordinateur → son chef : toujours accepté")
print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
