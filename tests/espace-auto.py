#!/usr/bin/env python3
"""Tests de l'espace auto (spec docs/plans/2026-10-15-espace-auto-spec.md) — installation jetable, FAUX Herdr à état qui
journalise chaque appel (jamais le vrai), sans modèle. Le planificateur met chaque espace OUVERT en conformité avec
espace_voulu() : ajout, fermeture, conversation intacte, date inconnue gardée, onglet inconnu intact, agent qui attend une
permission laissé, [espaces] auto = false, cadence de 5 min. Usage : python3 tests/espace-auto.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


# Faux Herdr à état : espaces, onglets, panneaux, agents vus et statuts dans etat.json ; chaque appel noté dans appels.log.
FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["FAUX_HERDR"]; f = T + "/etat.json"; a = sys.argv[1:]
e = json.load(open(f)) if os.path.exists(f) else {"n": 0, "ws": [], "tabs": [], "panes": [], "agents": [], "statuts": {}}
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
elif a[:2] == ["tab", "close"]:
    e["tabs"] = [t for t in e["tabs"] if t["tab_id"] != a[2]]; e["panes"] = [p for p in e["panes"] if p["tab_id"] != a[2]]
elif a[:2] == ["pane", "split"]: r = {"pane": {"pane_id": nouveau_pane(pane(opt("--pane"))["tab_id"])["pane_id"]}}
elif a[:2] == ["pane", "run"]: pane(a[2])["cmd"] = a[3]
elif a[:2] == ["pane", "get"]: r = {"pane": dict(pane(a[2]), agent_status=e["statuts"].get(a[2], "idle"))} if pane(a[2]) else {}
elif a[:2] == ["pane", "list"]:
    tabs = {t["tab_id"] for t in e["tabs"] if t["workspace_id"] == opt("--workspace")}
    r = {"panes": [p for p in e["panes"] if p["tab_id"] in tabs]}
elif a[:2] == ["pane", "close"]: e["panes"] = [p for p in e["panes"] if p["pane_id"] != a[2]]
elif a[:2] == ["agent", "list"]: r = {"agents": [{"pane_id": p} for p in e["agents"] if pane(p)]}
json.dump(e, open(f, "w"))
print(json.dumps({"result": r}))
'''

CONFIG = '''
[espaces.carto]
a_cote = ["checklists"]
onglets = { "Suivi" = ["checklists:mise"] }

[equipes.demo]
depot = "{t}/depot"
chef_projet = "chef"
'''

AGENTS = {
    "simple": "moteur = claude\npanneaux = claude\ndomaine = echo un | echo deux\n",
    "carto": "moteur = codex\npanneaux = codex\n",
    "metier": "moteur = claude\npanneaux = claude\ndomaine = echo metier\n",
    "hote": "moteur = claude\npanneaux = claude\n",
    "invite": "moteur = claude\npanneaux = claude\n",
    "flou": "moteur = claude\npanneaux = claude\n",
    "recent": "moteur = claude\npanneaux = claude\n",
    "chef": "moteur = claude\npanneaux = claude\n",
    "demo-ecran": "moteur = claude\npanneaux = claude\nprojet = demo\nsujet = ecran\n",
    "bloque": "moteur = claude\npanneaux = claude\n",
}

# Dans le processus : espace(), ouvrir_en_mission(), conformer_espaces() et planificateur() avec le faux Herdr. Démarrer,
# arrêter ou relancer un agent est remplacé par un relevé : pendant une mise en conformité, il doit rester VIDE.
CODE = r'''
import datetime, json, os, sys
g = {"__name__": "essai", "__file__": sys.argv[1]}                   # les globales MÊMES du module
exec(compile(open(sys.argv[1]).read(), sys.argv[1], "exec"), g)
etat = os.environ["FAUX_HERDR"] + "/etat.json"; out = {"demarres": {}, "interdits": [], "gestes": None, "conformes": []}
def demarrer(a, m, p, reprise=None):
    out["demarres"][p] = [a, m]; e = json.load(open(etat)); e["agents"].append(p); json.dump(e, open(etat, "w"))
g["demarrer_agent"] = demarrer
g["message_remettre"] = lambda a: True
g["time"].sleep = lambda s: None
for geste in json.loads(sys.argv[2]):
    if geste[0] == "espace": g["espace"](geste[1])
    elif geste[0] == "mission": g["ouvrir_en_mission"](geste[1], geste[2], geste[3])
    else:
        g["demarrer_agent"] = lambda *x, **k: out["interdits"].append(["demarrer", *x])
        g["arreter_agent"] = lambda *x, **k: out["interdits"].append(["arreter", *x])
        g["relancer"] = lambda *x, **k: out["interdits"].append(["relancer", *x])
        if geste[0] == "conformer": out["gestes"] = g["conformer_espaces"](datetime.datetime.fromisoformat(geste[1]))
        elif geste[0] == "planificateur":                               # le planificateur appelle-t-il la mise en conformité ?
            g["conformer_espaces"] = lambda m=None: out["conformes"].append(str(m))
            for f in ("superviser", "reveil", "tache", "entretien", "sauvegarder", "secrets_audit_silencieux"): g[f] = lambda *x, **k: 0
            g["planificateur"]()
print("@@" + json.dumps(out))
'''


def installation(t, config=CONFIG):
    _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    (t / "coffre.json").write_text("{}")
    ecrire_config(t, config)
    for a, c in AGENTS.items():
        d = t / "agents" / a; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nicone = ●\n{c}")
    (t / "faux").mkdir(); (t / "faux/herdr").write_text(FAUX_HERDR); os.chmod(t / "faux/herdr", 0o755)
    (t / "courtier").mkdir(exist_ok=True); (t / "courtier/dernier-audit.txt").write_text("")
    return {**os.environ, "BERGER_DIR": str(t), "FAUX_HERDR": str(t / "faux"), "BERGER_HERDR": str(t / "faux/herdr"),
            "PATH": f"{t}/faux:" + os.environ["PATH"]}


def ecrire_config(t, config):
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n' + config.replace("{t}", str(t)))


def gestes(t, env, *g):
    r = subprocess.run([sys.executable, "-c", CODE, str(t / "bin/berger"), json.dumps(g)], env=env, capture_output=True, text=True, timeout=120)
    if r.returncode: sys.exit(f"ARRÊT : gestes {g} en échec : {r.stderr[-900:]}")
    return json.loads(r.stdout.rsplit("@@", 1)[1])


def etat(t): return json.loads((t / "faux/etat.json").read_text())
def ecrire_etat(t, e): (t / "faux/etat.json").write_text(json.dumps(e))
def ids(t, a): return json.loads((t / "agents" / a / ".herdr.json").read_text())
def onglets(t, a): return [o["label"] for o in etat(t)["tabs"] if o["workspace_id"] == ids(t, a)["workspace"]]
def panneaux(t, a, label):
    e = etat(t); tab = next(o["tab_id"] for o in e["tabs"] if o["workspace_id"] == ids(t, a)["workspace"] and o["label"] == label)
    return [p for p in e["panes"] if p["tab_id"] == tab]
def journal(t, a):
    return "".join(f.read_text() for f in sorted((t / "agents" / a / "memory").glob("*.md")))
def appels(t):
    f = t / "faux/appels.log"; return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []
def remise_appels(t): (t / "faux/appels.log").unlink(missing_ok=True)


def fermer_onglet(t, a, label):
    e = etat(t); tab = next(o["tab_id"] for o in e["tabs"] if o["workspace_id"] == ids(t, a)["workspace"] and o["label"] == label)
    e["tabs"] = [o for o in e["tabs"] if o["tab_id"] != tab]; e["panes"] = [p for p in e["panes"] if p["tab_id"] != tab]; ecrire_etat(t, e)


T0 = datetime.datetime.now().replace(second=0, microsecond=0)
quand = lambda minutes: (T0 + datetime.timedelta(minutes=minutes)).isoformat()
il_y_a = lambda heures: (T0 - datetime.timedelta(hours=heures)).strftime("%Y-%m-%d_%H%M")


with tempfile.TemporaryDirectory() as td:
    t = Path(td); env = installation(t)
    sonde = subprocess.run([sys.executable, "-c", f"import runpy;m=runpy.run_path({str(t / 'bin/berger')!r},run_name='x');print(m['HERDR'])"],
                           env=env, capture_output=True, text=True)
    if sonde.stdout.strip() != str(t / "faux/herdr"): sys.exit(f"ARRÊT : Berger n'utiliserait pas le faux Herdr ({sonde.stdout.strip() or sonde.stderr[-200:]})")

    # Mise en place : les espaces, une mission chez l'hôte, des onglets Missions sans objet (fin 2 h / inconnue)
    gestes(t, env, *[["espace", a] for a in ("simple", "carto", "metier", "hote", "flou", "recent", "chef", "bloque")])
    (t / "agents/invite/MISSION.md").write_text("# Mission confiée par hote — 2026-10-15 09:30\nmoteur : claude\n\nlire z\n")
    gestes(t, env, ["mission", "invite", "hote", "claude"])
    for hote, residu, heures in (("flou", "ancien-flou", None), ("recent", "ancien-recent", 2)):
        (t / "agents" / residu / "memory").mkdir(parents=True)
        (t / "agents" / residu / "agent.conf").write_text("nom = R\nicone = ●\nmoteur = claude\npanneaux = claude\n")
        if heures: (t / "agents" / residu / "historique").mkdir(); (t / "agents" / residu / f"historique/mission-{il_y_a(heures)}.md").write_text("# fini\n")
        i = ids(t, hote); e = etat(t)
        tab = {"tab_id": "t-m-" + hote, "workspace_id": i["workspace"], "label": "🎯 Missions"}; suivi = {"pane_id": "p-s-" + hote, "tab_id": tab["tab_id"], "cmd": "suivi"}
        e["tabs"].append(tab); e["panes"].append(suivi); ecrire_etat(t, e)
        i["missions"] = {"tab": tab["tab_id"], "suivi": suivi["pane_id"], "agents": {residu: "p-parti"}}; (t / "agents" / hote / ".herdr.json").write_text(json.dumps(i))
    # Onglet inconnu dans l'espace de simple : « Notes » et son panneau, posés à la main
    e = etat(t); ws = ids(t, "simple")["workspace"]
    e["tabs"].append({"tab_id": "t-notes", "workspace_id": ws, "label": "Notes"}); e["panes"].append({"pane_id": "p-notes", "tab_id": "t-notes", "cmd": "vim"})
    ecrire_etat(t, e)
    convs = set(etat(t)["agents"])

    # 1. Des espaces tout juste construits sont déjà conformes — sauf le chef : `berger espace` ne crée pas l'onglet Équipe
    #    tant que personne n'y est hébergé, alors qu'un développeur de son équipe est ouvert (R6) : seul geste, l'Équipe
    remise_appels(t)
    r = gestes(t, env, ["conformer", quand(0)])
    faits = {a: g for a, g in r["gestes"].items() if g}
    lectures = (["workspace", "list"], ["tab", "list"], ["pane", "list"], ["pane", "get"], ["agent", "list"])
    ecritures = [x for x in appels(t) if x[:2] not in lectures]
    ws_chef = ids(t, "chef")["workspace"]; eq = [p for p in panneaux(t, "chef", "👥 Équipe")] if "👥 Équipe" in onglets(t, "chef") else []
    dire(list(faits) == ["chef"] and len(faits["chef"]) == 1 and len(eq) == 1 and eq[0]["cmd"].endswith("panneau missions chef")
         and ids(t, "chef")["missions"]["suivi"] == eq[0]["pane_id"] and not r["interdits"],
         f"ajout : chef avec un développeur ouvert, sans Équipe → Équipe ajoutée avec le suivi seul ({faits})")
    dire(ecritures and all(x[:2] in (["tab", "create"], ["pane", "rename"], ["pane", "run"]) for x in ecritures)
         and ecritures[0][ecritures[0].index("--workspace") + 1] == ws_chef,
         f"les autres espaces neufs sont déjà conformes : aucune autre écriture dans Herdr ({ecritures[:4]})")
    dire("flou" in r["gestes"] and "invite" not in r["gestes"], "chaque espace OUVERT passe ; un agent sans espace (en mission chez l'hôte) : rien")

    # 2. Cadence : à +2 min, aucune passe ; à +6 min, la passe a lieu
    fermer_onglet(t, "simple", "📇 Fiche")
    r = gestes(t, env, ["conformer", quand(2)])
    dire(r["gestes"] == {} and "📇 Fiche" not in onglets(t, "simple"), "cadence : deuxième passe à +2 min → aucune passe")

    # 3. Changements de règles pendant que les espaces sont ouverts, puis une passe à +6 min
    ecrire_config(t, CONFIG.replace('a_cote = ["checklists"]', 'a_cote = ["checklists", "panneau:missions"]')
                  .replace('onglets = { "Suivi" = ["checklists:mise"] }', "") + '\n[espaces.metier]\na_cote = ["checklists"]\n')
    fermer_onglet(t, "chef", "👥 Équipe")
    e = etat(t); bl = ids(t, "bloque")["agents"]["claude"]; e["statuts"][bl] = "blocked"; ecrire_etat(t, e)
    fermer_onglet(t, "bloque", "📇 Fiche")
    remise_appels(t)
    r = gestes(t, env, ["conformer", quand(6)]); g = r["gestes"]

    # Ajout
    dire(onglets(t, "simple").count("📇 Fiche") == 1 and any("Fiche" in x for x in g["simple"]) and "ajouté l'onglet « 📇 Fiche »" in journal(t, "simple"),
         f"ajout : onglet Fiche fermé à la main → recréé, noté au journal ({g['simple']})")
    fiche = panneaux(t, "simple", "📇 Fiche")
    dire(len(fiche) == 1 and fiche[0]["cmd"].endswith("panneau fiche simple") and ids(t, "simple")["panneaux"]["fiche"] == fiche[0]["pane_id"],
         "ajout : la Fiche recréée affiche sa page et est enregistrée dans .herdr.json")
    trav = [p["cmd"] for p in panneaux(t, "carto", "💼 Travail")]
    dire(any(c and c.endswith("panneau missions carto") for c in trav) and "cote-2" in ids(t, "carto")["panneaux"]
         and "ajouté le panneau « cote-2 »" in journal(t, "carto"), f"ajout : panneau du métier ajouté dans [espaces.carto].a_cote → ajouté ({g['carto']})")
    eq = [p for p in panneaux(t, "chef", "👥 Équipe")] if "👥 Équipe" in onglets(t, "chef") else []
    dire(len(eq) == 1 and eq[0]["cmd"].endswith("panneau missions chef") and ids(t, "chef")["missions"]["suivi"] == eq[0]["pane_id"],
         f"ajout : Équipe du chef fermée à la main → recréée avec le suivi seul ({g.get('chef')})")

    # Fermeture
    dire("Suivi" not in onglets(t, "carto") and not any(k.startswith("onglet-Suivi") for k in ids(t, "carto")["panneaux"]),
         "fermeture : onglet du rôle retiré de [espaces.carto].onglets → fermé, oublié de .herdr.json")
    mt = [p["cmd"] for p in panneaux(t, "metier", "💼 Travail")]
    dire("domaine-1" not in ids(t, "metier")["panneaux"] and "echo metier" not in " ".join(c or "" for c in mt) and "cote-1" in ids(t, "metier")["panneaux"]
         and "fermé le panneau « domaine-1 »" in journal(t, "metier"), f"fermeture : domaine-1 plus voulu ([espaces.metier] a_cote) → fermé, cote-1 ajouté ({g['metier']})")

    # Date inconnue / 24 h / onglet inconnu / permission
    dire("🎯 Missions" in onglets(t, "flou") and not g["flou"], "date inconnue : Missions écarté sans date de fin → gardé, aucun geste")
    dire("🎯 Missions" in onglets(t, "recent") and not g["recent"], "R7 : Missions sans objet depuis 2 h → gardé (24 h)")
    notes = [x for x in appels(t) if "t-notes" in x or "p-notes" in x]
    dire("Notes" in onglets(t, "simple") and not notes and any(p["pane_id"] == "p-notes" for p in etat(t)["panes"]),
         f"onglet inconnu « Notes » : intact, aucun appel ne le vise ({notes})")
    dire(not g["bloque"] and "📇 Fiche" not in onglets(t, "bloque"), "agent qui attend une permission (blocked) : aucun geste dans son espace")

    # Conversations intactes, partout
    vivantes = {p["pane_id"] for p in etat(t)["panes"]}
    visees = [x for x in appels(t) if x[:2] in (["pane", "close"], ["pane", "run"], ["pane", "send-keys"]) and x[2] in convs]
    dire(convs <= vivantes and not visees and not r["interdits"],
         f"conversations intactes : toutes vivantes, aucune fermée ni relancée, aucun agent démarré ({visees} {r['interdits']})")

    # 4. Missions sans objet depuis 30 h : gardé tant qu'une conversation y vit encore, fermé ensuite
    (t / "agents/invite/MISSION.md").unlink()
    i = ids(t, "invite"); conv_inv = i["agents"]["claude"]; i.pop("mission"); i["agents"] = {}; (t / "agents/invite/.herdr.json").write_text(json.dumps(i))
    (t / "agents/invite/historique").mkdir(); (t / f"agents/invite/historique/mission-{il_y_a(30)}.md").write_text("# fini\n")
    e = etat(t); e["statuts"].pop(bl); ecrire_etat(t, e)
    r = gestes(t, env, ["conformer", quand(12)])
    dire("🎯 Missions" in onglets(t, "hote") and any(p["pane_id"] == conv_inv for p in etat(t)["panes"]),
         f"conversation intacte : Missions écarté (30 h) mais une conversation y vit encore → gardé ({r['gestes'].get('hote')})")
    dire("📇 Fiche" in onglets(t, "bloque") and r["gestes"].get("bloque"), "la permission accordée (statut au repos), la passe suivante ajoute la Fiche")
    e = etat(t); e["panes"] = [p for p in e["panes"] if p["pane_id"] != conv_inv]; ecrire_etat(t, e)
    r = gestes(t, env, ["conformer", quand(18)])
    dire("🎯 Missions" not in onglets(t, "hote") and "missions" not in ids(t, "hote") and "fermé l'onglet « 🎯 Missions »" in journal(t, "hote")
         and not r["interdits"], f"fermeture : Missions sans objet depuis 30 h (fin connue), sans conversation → fermé, noté ({r['gestes'].get('hote')})")

    # 5. Idempotence après tous ces gestes : une nouvelle passe ne fait rien
    r = gestes(t, env, ["conformer", quand(24)])
    dire(not any(r["gestes"].values()), f"une passe sur des espaces conformes ne fait rien ({ {a: g for a, g in r['gestes'].items() if g} })")

    # 6. [espaces] auto = false : aucune passe, aucun appel à Herdr
    ecrire_config(t, CONFIG.replace("[espaces.carto]", "[espaces]\nauto = false\n\n[espaces.carto]"))
    fermer_onglet(t, "simple", "📇 Fiche"); remise_appels(t)
    r = gestes(t, env, ["conformer", quand(40)])
    dire(r["gestes"] == {} and not appels(t) and "📇 Fiche" not in onglets(t, "simple"), "[espaces] auto = false : aucune passe, aucun appel à Herdr")
    ecrire_config(t, CONFIG)

    # 7. Le planificateur appelle la mise en conformité (chaque minute ; la cadence est dans conformer_espaces)
    r = gestes(t, env, ["planificateur"])
    dire(len(r["conformes"]) == 1 and not r["interdits"], f"le planificateur appelle conformer_espaces à chaque passage ({r['conformes']})")

    # 8. Herdr illisible (aucun onglet rendu) : rien n'est deviné
    sauve = etat(t); e = dict(sauve); e["tabs"] = []; e["panes"] = []; ecrire_etat(t, e); remise_appels(t)
    r = gestes(t, env, ["conformer", quand(60)])
    dire(not any(r["gestes"].values()) and not [x for x in appels(t) if x[:2] in (["tab", "create"], ["pane", "split"])],
         "Herdr illisible (espaces sans onglets) : aucun geste")

sys.exit(ko)
