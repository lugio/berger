#!/usr/bin/env python3
"""Tests de l'espace VOULU d'un agent (spec docs/plans/2026-10-15-regles-espace-spec.md) — installation jetable, FAUX Herdr
à état (jamais le vrai), sans modèle. Preuve d'identité : pour chaque agent sans besoin nouveau, `espace()` construit
exactement les onglets et panneaux que `espace_voulu()` annonce ; l'onglet Missions / Équipe construit par
ouvrir_en_mission() aussi. Puis les règles une à une (R2, R6, R7), la protection des conversations, aucun appel à Herdr
pendant `berger espace-voulu`, et son JSON conforme au schéma. Usage : python3 tests/regles-espace.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit, _schema as S

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


# Faux Herdr à état : espaces, onglets et panneaux dans etat.json ; chaque appel journalisé dans appels.log.
FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["FAUX_HERDR"]; f = T + "/etat.json"; a = sys.argv[1:]
e = json.load(open(f)) if os.path.exists(f) else {"n": 0, "ws": [], "tabs": [], "panes": []}
with open(T + "/appels.log", "a") as j: j.write(json.dumps(a) + "\n")
def neuf(p): e["n"] += 1; return f"{p}{e['n']}"
def opt(k): return a[a.index(k) + 1] if k in a else None
def pane(p): return next((x for x in e["panes"] if x["pane_id"] == p), None)
def nouveau_pane(tab): p = {"pane_id": neuf("p"), "tab_id": tab, "cmd": None}; e["panes"].append(p); return p
r = {}
if a[:2] == ["workspace", "create"]:
    w = neuf("w"); e["ws"].append({"workspace_id": w, "label": opt("--label")})
    t = {"tab_id": neuf("t"), "workspace_id": w, "label": "1"}; e["tabs"].append(t); p = nouveau_pane(t["tab_id"])
    r = {"workspace": {"workspace_id": w}, "tab": {"tab_id": t["tab_id"]}, "root_pane": {"pane_id": p["pane_id"]}}
elif a[:2] == ["workspace", "list"]: r = {"workspaces": e["ws"]}
elif a[:2] == ["tab", "create"]:
    t = {"tab_id": neuf("t"), "workspace_id": opt("--workspace"), "label": opt("--label")}; e["tabs"].append(t)
    r = {"tab": {"tab_id": t["tab_id"]}, "root_pane": {"pane_id": nouveau_pane(t["tab_id"])["pane_id"]}}
elif a[:2] == ["tab", "rename"]: next(t for t in e["tabs"] if t["tab_id"] == a[2])["label"] = a[3]
elif a[:2] == ["tab", "list"]: r = {"tabs": [t for t in e["tabs"] if t["workspace_id"] == opt("--workspace")]}
elif a[:2] == ["tab", "close"]: e["tabs"] = [t for t in e["tabs"] if t["tab_id"] != a[2]]
elif a[:2] == ["pane", "split"]: r = {"pane": {"pane_id": nouveau_pane(pane(opt("--pane"))["tab_id"])["pane_id"]}}
elif a[:2] == ["pane", "run"]: pane(a[2])["cmd"] = a[3]
elif a[:2] == ["pane", "get"]: r = {"pane": pane(a[2])} if pane(a[2]) else {}
elif a[:2] == ["pane", "list"]:
    tabs = {t["tab_id"] for t in e["tabs"] if t["workspace_id"] == opt("--workspace")}
    r = {"panes": [p for p in e["panes"] if p["tab_id"] in tabs]}
elif a[:2] == ["pane", "close"]: e["panes"] = [p for p in e["panes"] if p["pane_id"] != a[2]]
json.dump(e, open(f, "w"))
print(json.dumps({"result": r}))
'''

CONFIG = '''
[espaces.carto]
a_cote = ["checklists", "panneau:missions"]
onglets = { "Suivi" = ["checklists:mise", "source:alertes", "panneau:journal"], "Vide" = [] }

[equipes.demo]
depot = "{t}/depot"
chef_projet = "chef"
'''

AGENTS = {
    "simple": "moteur = claude\npanneaux = claude, codex\ndomaine = echo un | echo deux | etat-taches x | echo trois\n",
    "carto": "moteur = codex\npanneaux = codex\ndomaine = echo ignore\n",
    "missionnaire": "moteur = claude\npanneaux = claude, codex\n",
    "hote": "moteur = claude\npanneaux = claude\n",
    "invite": "moteur = claude\npanneaux = claude\n",
    "chef": "moteur = claude\npanneaux = claude\n",
    "demo-ecran": "moteur = claude\npanneaux = claude\nprojet = demo\nsujet = ecran\n",
    "demo-pied": "moteur = codex\npanneaux = codex\nprojet = demo\nsujet = pied\n",
    "vieil-hote": "moteur = claude\npanneaux = claude\n",
    "jeune-hote": "moteur = claude\npanneaux = claude\n",
    "ancien": "moteur = claude\npanneaux = claude\n",
    "recent": "moteur = claude\npanneaux = claude\n",
}

# Dans le processus : espace(), ouvrir_en_mission() et espace_voulu() avec le faux Herdr ; le démarrage d'un moteur est
# remplacé par un relevé (pane → agent, moteur) : ni bac à sable ni moteur réel.
CODE = r'''
import json, sys
g = {"__name__": "essai", "__file__": sys.argv[1]}                   # les globales MÊMES du module (run_path n'en rend qu'une copie)
exec(compile(open(sys.argv[1]).read(), sys.argv[1], "exec"), g)
demarres = {}
g["demarrer_agent"] = lambda a, m, p, reprise=None: demarres.__setitem__(p, [a, m])
g["message_remettre"] = lambda a: True
g["time"].sleep = lambda s: None
for geste in json.loads(sys.argv[2]):
    if geste[0] == "espace": g["espace"](geste[1])
    elif geste[0] == "mission": g["ouvrir_en_mission"](geste[1], geste[2], geste[3])
print("@@" + json.dumps(demarres))
'''


def installation(t):
    _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    (t / "coffre.json").write_text("{}")
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n' + CONFIG.replace("{t}", str(t)))
    for a, c in AGENTS.items():
        d = t / "agents" / a; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nicone = ●\n{c}")
    (t / "faux").mkdir(); (t / "faux/herdr").write_text(FAUX_HERDR); os.chmod(t / "faux/herdr", 0o755)
    return {**os.environ, "BERGER_DIR": str(t), "FAUX_HERDR": str(t / "faux"), "BERGER_HERDR": str(t / "faux/herdr"),
            "PATH": f"{t}/faux:" + os.environ["PATH"]}


def gestes(t, env, *g):
    r = subprocess.run([sys.executable, "-c", CODE, str(t / "bin/berger"), json.dumps(g)], env=env, capture_output=True, text=True, timeout=120)
    if r.returncode: sys.exit(f"ARRÊT : gestes {g} en échec : {r.stderr[-600:]}")
    return json.loads(r.stdout.rsplit("@@", 1)[1])


def construit(t, ws, demarres):
    """Ce que le faux Herdr contient pour l'espace ws : [(libellé, [élément…])], élément = commande ou ['agent', a, m]."""
    e = json.loads((t / "faux/etat.json").read_text())
    return [(o["label"], [demarres.get(p["pane_id"]) and ["agent", *demarres[p["pane_id"]]] or (p["cmd"] or "").removeprefix("clear; ")
                          for p in e["panes"] if p["tab_id"] == o["tab_id"]])
            for o in e["tabs"] if o["workspace_id"] == ws]


def voulu_projete(d):
    return [(o["libelle"], [["agent", p["agent"], p["moteur"]] if p["genre"] == "agent" else p["commande"] for p in o["panneaux"]])
            for o in d["onglets"]]


def berger(t, env, *args):
    return subprocess.run([sys.executable, str(t / "bin/berger"), *args], env=env, capture_output=True, text=True, timeout=60)


def voulu(t, env, a):
    r = berger(t, env, "espace-voulu", a, "--json")
    try: return json.loads(r.stdout)
    except ValueError: sys.exit(f"ARRÊT : espace-voulu {a} --json illisible : {r.stderr[-400:]}")


def ids(t, a):
    f = t / "agents" / a / ".herdr.json"
    return json.loads(f.read_text()) if f.exists() else {}


def il_y_a(heures):
    return (datetime.datetime.now() - datetime.timedelta(hours=heures)).strftime("%Y-%m-%d_%H%M")


with tempfile.TemporaryDirectory() as td:
    t = Path(td); env = installation(t)
    sonde = subprocess.run([sys.executable, "-c", f"import runpy;m=runpy.run_path({str(t / 'bin/berger')!r},run_name='x');print(m['HERDR'])"],
                           env=env, capture_output=True, text=True)
    if sonde.stdout.strip() != str(t / "faux/herdr"): sys.exit(f"ARRÊT : Berger n'utiliserait pas le faux Herdr ({sonde.stdout.strip() or sonde.stderr[-200:]})")
    B = str(t / "bin/berger")
    (t / "agents/missionnaire/MISSION.md").write_text("# Mission confiée par hote — 2026-10-15 08:00\nmoteur : codex · modèle : x\n\nfaire y\n")

    # 1. Preuve d'identité : espace() construit ce qu'annonce espace_voulu(), pour chaque agent sans besoin nouveau
    tous = {}
    for a, quoi in (("simple", "agent simple (2 moteurs, domaine)"), ("carto", "agent avec [espaces.carto] (a_cote, onglets)"),
                    ("missionnaire", "mission en cours chez lui (moteur imposé par MISSION.md)"), ("hote", "futur hôte, sans mission")):
        dem = gestes(t, env, ["espace", a]); tous.update(dem)
        b = construit(t, ids(t, a)["workspace"], dem); v = voulu(t, env, a)["donnees"]
        dire(b == voulu_projete(v), f"identité — {quoi} : espace() = espace_voulu()" + ("" if b == voulu_projete(v) else f"\n      construit {b}\n      voulu     {voulu_projete(v)}"))
    v = voulu(t, env, "simple")["donnees"]
    dire([o["libelle"] for o in v["onglets"]] == ["💼 Travail", "📇 Fiche"] and not v["ecartes"],
         "agent simple : Travail · Fiche, rien d'écarté (pas de Missions sans objet)")
    v = voulu(t, env, "carto")["donnees"]
    dire([o["libelle"] for o in v["onglets"]] == ["💼 Travail", "📇 Fiche", "Suivi"] and [p["cle"] for p in v["onglets"][0]["panneaux"]] == ["agent-codex", "encours", "cote-1", "cote-2"],
         "[espaces.carto] : a_cote dans Travail (le domaine d'agent.conf ignoré), onglet Suivi, onglet vide omis")

    # 2. R5 — mission en cours chez un hôte → onglet Missions, identique à ce que construit ouvrir_en_mission()
    (t / "agents/invite/MISSION.md").write_text("# Mission confiée par hote — 2026-10-15 09:30\nmoteur : claude\n\nlire z\n")
    tous.update(gestes(t, env, ["mission", "invite", "hote", "claude"]))
    b = construit(t, ids(t, "hote")["workspace"], tous); v = voulu(t, env, "hote")["donnees"]
    dire(b == voulu_projete(v), "R5 — onglet Missions de l'hôte : ouvrir_en_mission() = espace_voulu()" + ("" if b == voulu_projete(v) else f"\n      construit {b}\n      voulu     {voulu_projete(v)}"))
    m = v["onglets"][-1]
    dire(m["libelle"] == "🎯 Missions" and m["regle"] == "R5" and m["condition"] is True and m["depuis"] == "2026-10-15T09:30",
         f"R5 — Missions voulu, condition vraie depuis le début de la mission ({m['libelle']}, {m['regle']}, {m['depuis']})")

    # 3. R2 — l'invité, dont la conversation vit chez l'hôte : son espace montre « Mission » et son journal (identique à espace())
    dem = gestes(t, env, ["espace", "invite"]); v = voulu(t, env, "invite")["donnees"]
    b = construit(t, ids(t, "invite")["workspace"], dem)
    dire(b == voulu_projete(v) and v["heberge_par"] == "hote" and v["onglets"][0]["libelle"] == "Mission" and v["onglets"][0]["regle"] == "R2",
         "R2 — en mission chez un hôte : onglet « Mission » avec le journal, espace() = espace_voulu()" + ("" if b == voulu_projete(v) else f"\n      construit {b}\n      voulu     {voulu_projete(v)}"))

    # 4. R6 — chef de projet : Équipe construit par ouvrir_en_mission() = voulu ; un développeur ouvert non hébergé suffit
    tous.update(gestes(t, env, ["espace", "chef"]))
    v = voulu(t, env, "chef")["donnees"]; e = v["onglets"][-1]
    dire(e["libelle"] == "👥 Équipe" and e["regle"] == "R6" and e["condition"] is True and len(e["panneaux"]) == 1 and "demo-ecran" in e["raison"],
         f"R6 — chef avec des développeurs ouverts (aucun hébergé) : Équipe voulue, le suivi seul ({e['libelle']} : {e['raison']})")
    (t / "agents/demo-ecran/MISSION.md").write_text("# Mission confiée par chef — 2026-10-15 10:00\nmoteur : claude\n\nl'écran\n")
    tous.update(gestes(t, env, ["mission", "demo-ecran", "chef", "claude"]))
    b = construit(t, ids(t, "chef")["workspace"], tous); v = voulu(t, env, "chef")["donnees"]
    dire(b == voulu_projete(v), "R6 — onglet Équipe du chef : ouvrir_en_mission() = espace_voulu()" + ("" if b == voulu_projete(v) else f"\n      construit {b}\n      voulu     {voulu_projete(v)}"))

    # 5. R7 — plus de mission : gardé 24 h si la fin est connue, plus voulu au-delà ou si elle est inconnue
    for hote, agent_, heures in (("jeune-hote", "recent", 2), ("vieil-hote", "ancien", 30)):
        (t / f"agents/{hote}/.herdr.json").write_text(json.dumps({"missions": {"tab": "tX", "agents": {agent_: "pX"}}}))
        (t / f"agents/{agent_}/historique").mkdir(); (t / f"agents/{agent_}/historique/mission-{il_y_a(heures)}.md").write_text("# fini\n")
    v = voulu(t, env, "jeune-hote")["donnees"]; m = v["onglets"][-1]
    dire(m["cle"] == "missions" and m["regle"] == "R7" and m["condition"] is False and m["depuis"] and [p["cle"] for p in m["panneaux"]] == ["mission-suivi"],
         f"R7 — sans objet depuis 2 h : Missions encore voulu (suivi seul), condition fausse depuis {m['depuis']}")
    v = voulu(t, env, "vieil-hote")["donnees"]
    dire(all(o["cle"] != "missions" for o in v["onglets"]) and [x["regle"] for x in v["ecartes"]] == ["R7"] and v["ecartes"][0]["depuis"],
         f"R7 — sans objet depuis 30 h : Missions plus voulu, écarté avec sa date ({v['ecartes']})")
    for f in (t / "agents/ancien/historique").iterdir(): f.unlink()
    v = voulu(t, env, "vieil-hote")["donnees"]
    dire(all(o["cle"] != "missions" for o in v["onglets"]) and v["ecartes"] and v["ecartes"][0]["depuis"] is None,
         "R7 — fin de mission de date inconnue : Missions pas voulu (comme aujourd'hui), depuis = null")
    (t / f"agents/ancien/historique/mission-{il_y_a(30)}.md").write_text("# fini\n")      # remise, pour le jeu du JSON
    # Équipe sans développeur : la dernière fermeture archivée (historique/equipe/<sujet>-AAAA-MM-JJ_HHMM) date la fin
    for x in ("demo-ecran", "demo-pied"): shutil.rmtree(t / "agents" / x)   # fermés (equipe_fermer supprime leur dossier)
    (t / f"agents/chef/historique/equipe/pied-{il_y_a(1)}").mkdir(parents=True)
    v = voulu(t, env, "chef")["donnees"]; e = v["onglets"][-1]
    dire(e["libelle"] == "👥 Équipe" and e["regle"] == "R7" and e["condition"] is False,
         f"R7 — chef sans développeur, dernière fermeture il y a 1 h : Équipe gardée ({e['raison']})")

    # 6. Aucune règle ne ferme une conversation : chaque conversation ouverte est dans un espace voulu, protégée
    convs = {(a, m) for a, m in tous.values() if (t / "agents" / a).is_dir()}
    vus = set(); proteges = True
    for a in sorted(p.name for p in (t / "agents").iterdir()):
        for o in voulu(t, env, a)["donnees"]["onglets"]:
            for p in o["panneaux"]:
                if p["genre"] == "agent": vus.add((p["agent"], p["moteur"])); proteges &= p["protege"] is True
    dire(convs <= vus and proteges, f"aucune conversation ouverte n'est hors de l'espace voulu, toutes protégées (manquantes : {sorted(convs - vus)})")

    # 7. Lecture seule : aucun appel à Herdr, rien d'écrit ; agent inconnu refusé
    (t / "faux/appels.log").unlink(missing_ok=True); avant = {p: p.stat().st_mtime for p in (t / "agents").rglob("*") if p.is_file()}
    r1 = berger(t, env, "espace-voulu", "hote"); r2 = berger(t, env, "espace-voulu", "hote", "--json")
    apres = {p: p.stat().st_mtime for p in (t / "agents").rglob("*") if p.is_file()}
    dire(r1.returncode == 0 and r2.returncode == 0 and not (t / "faux/appels.log").exists() and avant == apres,
         "berger espace-voulu (texte et --json) : aucun appel à Herdr, aucun fichier écrit")
    dire("🎯 Missions" in r1.stdout and "R5" in r1.stdout and "protégée" in r1.stdout, "texte lisible : onglets, règles, conversations protégées")
    r = berger(t, env, "espace-voulu", "personne")
    dire(r.returncode != 0 and "agent inconnu" in r.stderr, "agent inconnu : refusé, code non nul")

    # 8. JSON : enveloppe, conforme au schéma, chaque champ produit par ce jeu, chaque champ avec x-libelle et x-rendu
    s = S.charger(SRC / "bin/schemas/espace-voulu.schema.json"); toutes = []; err = []
    for a in sorted(p.name for p in (t / "agents").iterdir()):
        env_ = voulu(t, env, a)
        if env_.get("vue") != "espace-voulu" or env_.get("version") != s["x-version"]: err.append(f"{a} : enveloppe")
        err += [f"{a} : {x}" for x in S.valider(env_["donnees"], s, s)]; toutes.append(env_["donnees"])
    dire(not err, f"--json conforme à espace-voulu.schema.json pour chaque agent ({err[:4]})")
    vide = lambda x: x is None or x == "" or x == [] or x == {}
    morts = [c for c, _ in S.proprietes(s, s) if all(vide(x) for d in toutes for x in S.valeurs(d, c))]
    dire(not morts, f"chaque champ du schéma est produit par le jeu (jamais produits : {morts})")
    sans = [c for c, p in S.proprietes(s, s) if not p.get("x-libelle") or not p.get("x-rendu")]
    dire(not sans, f"chaque champ a x-libelle et x-rendu (fautifs : {sans})")

sys.exit(ko)
