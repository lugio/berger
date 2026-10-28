#!/usr/bin/env python3
"""Tests de la disposition sur mesure par agent, agents/<a>/espace.toml (spec docs/plans/2026-10-16-espace-agent-spec.md) —
installation jetable, FAUX Herdr à état (jamais le vrai), sans modèle. espace.toml prime sur [espaces.<a>] de config.toml
(qui continue de marcher) ; vide de clés ou illisible, il est sans effet ; il se change par une proposition d'agent
(=== espace.toml : aperçu avant → après, application validée, sans relance, espace auto l'applique) ; un élément inconnu
est refusé à la proposition et affiché comme un message s'il est écrit à la main ; l'agent ne peut pas l'écrire (Claude et
Codex). Usage : python3 tests/espace-agent.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


# Faux Herdr à état (comme tests/espace-auto.py) : espaces, onglets, panneaux, agents vus ; chaque appel noté dans appels.log.
FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["FAUX_HERDR"]; f = T + "/etat.json"; a = sys.argv[1:]
e = json.load(open(f)) if os.path.exists(f) else {"n": 0, "ws": [], "tabs": [], "panes": [], "agents": []}
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
elif a[:2] == ["pane", "get"]: r = {"pane": dict(pane(a[2]), agent_status="working")} if pane(a[2]) else {}
elif a[:2] == ["pane", "list"]:
    tabs = {t["tab_id"] for t in e["tabs"] if t["workspace_id"] == opt("--workspace")}
    r = {"panes": [p for p in e["panes"] if p["tab_id"] in tabs]}
elif a[:2] == ["pane", "close"]: e["panes"] = [p for p in e["panes"] if p["pane_id"] != a[2]]
elif a[:2] == ["agent", "list"]: r = {"agents": [{"pane_id": p} for p in e["agents"] if pane(p)]}
json.dump(e, open(f, "w"))
print(json.dumps({"result": r}))
'''

CONFIG = '''
[outils.berger-admin]
type = "commandes"
dossier = "{t}"
[outils.berger-admin.lecture]
agent-apercu = "bin/berger agent apercu {agent} {arg}"
[outils.berger-admin.actions]
agent-appliquer = "bin/berger agent appliquer {agent} {arg}"

[espaces.carto]
a_cote = ["checklists"]
onglets = { "Suivi" = ["checklists:mise"] }

[espaces.vide]
a_cote = ["panneau:missions"]

[espaces.casse]
a_cote = ["panneau:missions"]

[espaces.perso]
a_cote = ["checklists"]
'''

AGENTS = {
    "master": "moteur = claude\npanneaux = claude\nsuperviseur = oui\noutils = berger-admin\n",
    "carto": "moteur = claude\npanneaux = claude\n",
    "perso": "moteur = claude\npanneaux = claude\ndomaine = echo ignore\n",
    "vide": "moteur = claude\npanneaux = claude\n",
    "casse": "moteur = claude\npanneaux = claude\n",
    "simple": "moteur = claude\npanneaux = claude\ndomaine = echo un\n",
    "main": "moteur = claude\npanneaux = claude\n",
    "cible": "moteur = claude\npanneaux = claude\n",
    "moteur-codex": "moteur = codex\npanneaux = codex\n",
}

# Dans le processus : espace() et conformer_espaces() avec le faux Herdr ; démarrer / arrêter / relancer un agent = relevé.
CODE = r'''
import datetime, json, os, sys
g = {"__name__": "essai", "__file__": sys.argv[1]}
exec(compile(open(sys.argv[1]).read(), sys.argv[1], "exec"), g)
etat = os.environ["FAUX_HERDR"] + "/etat.json"; out = {"interdits": [], "gestes": None}
def demarrer(a, m, p, reprise=None):
    e = json.load(open(etat)); e["agents"].append(p); json.dump(e, open(etat, "w"))
g["demarrer_agent"] = demarrer
g["message_remettre"] = lambda a: True
g["time"].sleep = lambda s: None
for geste in json.loads(sys.argv[2]):
    if geste[0] == "espace": g["espace"](geste[1])
    else:
        for f in ("demarrer_agent", "arreter_agent", "relancer"): g[f] = lambda *x, f=f, **k: out["interdits"].append([f, *x])
        out["gestes"] = g["conformer_espaces"](datetime.datetime.fromisoformat(geste[1]))
print("@@" + json.dumps(out))
'''


with tempfile.TemporaryDirectory() as td:
    m = Path(td); t = m / "berger"
    _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    (t / "coffre.json").write_text("{}")
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n' + CONFIG.replace("{t}", str(t)))
    for a, c in AGENTS.items():
        d = t / "agents" / a; (d / "memory").mkdir(parents=True); (d / "propositions").mkdir()
        (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nicone = ●\nheures = aucune\n{c}")
        (d / "SOUL.md").write_text(f"# {a}\n")
    (t / "faux").mkdir(); (t / "faux/herdr").write_text(FAUX_HERDR); os.chmod(t / "faux/herdr", 0o755)
    (t / "courtier/dernier-audit.txt").write_text("")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(t), "FAUX_HERDR": str(t / "faux"), "BERGER_HERDR": str(t / "faux/herdr"),
           "PATH": f"{t}/faux:" + os.environ["PATH"]}
    def berger(*args): return subprocess.run([sys.executable, str(t / "bin/berger"), *args], env=env, capture_output=True, text=True, timeout=120)
    def gestes(*g):
        r = subprocess.run([sys.executable, "-c", CODE, str(t / "bin/berger"), json.dumps(g)], env=env, capture_output=True, text=True, timeout=120)
        if r.returncode: sys.exit(f"ARRÊT : gestes {g} en échec : {r.stderr[-900:]}")
        return json.loads(r.stdout.rsplit("@@", 1)[1])
    def voulu(a):
        r = berger("espace-voulu", a, "--json")
        try: return json.loads(r.stdout)["donnees"]
        except (ValueError, KeyError): sys.exit(f"ARRÊT : espace-voulu {a} illisible : {r.stderr[-400:]}")
    def travail(a): return [(p["cle"], p["commande"]) for p in voulu(a)["onglets"][0]["panneaux"] if p["genre"] == "panneau"]
    def libelles(a): return [o["libelle"] for o in voulu(a)["onglets"]]
    def raisons(a): return " | ".join(o["raison"] + " " + " ".join(p["raison"] for p in o["panneaux"]) for o in voulu(a)["onglets"])
    def journal(a): return "".join(f.read_text() for f in sorted((t / "agents" / a / "memory").glob("*.md")))
    def empreinte(sortie): return next((l.split("Empreinte : ")[1].strip() for l in sortie.splitlines() if "Empreinte : " in l), "")
    P = t / "agents/master/propositions"
    def proposer(cible, blocs): (P / f"{cible}.md").write_text("".join(f"=== {n}\n{c}" for n, c in blocs.items()))
    E = lambda a: t / "agents" / a / "espace.toml"

    # ── écriture refusée à l'agent : regenerer crée le fichier (vide de clés) et le protège, Claude et Codex ──
    E("perso").write_text('a_cote = ["panneau:missions", "checklists:perso"]\nonglets = { "Notes" = ["source:alertes", "fichiers"] }\n')
    contenu_perso = E("perso").read_text()
    r = berger("regenerer")
    dire(r.returncode == 0 and all(E(a).is_file() for a in AGENTS), f"regenerer : chaque agent a son espace.toml ({r.stderr[-200:]})")
    dire(E("perso").read_text() == contenu_perso, "regenerer : un espace.toml existant n'est jamais réécrit")
    dire(not [k for k in __import__("tomllib").loads(E("simple").read_text())], "regenerer : le fichier créé est vide de clés (commentaires seulement)")
    for a in ("perso", "simple"):
        s = json.loads((t / "agents" / a / ".claude/settings.json").read_text())
        dire(f"Edit(~/berger/agents/{a}/espace.toml)" in s["permissions"]["deny"] and str(E(a)) in s["sandbox"]["filesystem"]["denyWrite"],
             f"Claude ({a}) : espace.toml refusé à l'édition et en écriture (bac à sable), comme agent.conf")
    cx = (t / ".codex/config.toml").read_text()
    sect = cx.split("[permissions.moteur-codex.filesystem]")[1].split("[projects.")[0]
    dire(f'"{E("moteur-codex")}" = "read"' in sect, "Codex : espace.toml en lecture seule dans le profil de l'agent")
    autres = [a for a in AGENTS if f'"{E(a)}" = "read"' not in cx.split(f"[permissions.{a}.filesystem]")[1].split("[projects.")[0]]
    dire(not autres, f"Codex : la même protection pour chaque agent ({autres})")
    proposer("master", {"espace.toml": 'a_cote = ["checklists"]\n'})
    r = berger("agent", "apercu", "master", "master")
    dire(r.returncode != 0 and "propres réglages" in r.stdout, "un agent ne propose pas sa propre disposition")
    (P / "master.md").unlink()

    # ── priorité ──
    dire(travail("carto")[1:] == [("cote-1", f"{t}/bin/berger panneau checklists")] and any("Suivi" in x for x in libelles("carto")),
         f"config.toml seul ([espaces.carto]) : sa disposition, comme avant ({travail('carto')[1:]})")
    dire("[espaces.carto].a_cote" in raisons("carto") and "[espaces.carto].onglets" in raisons("carto"), "config.toml seul : les raisons nomment [espaces.carto]")
    tp = travail("perso")
    dire([k for k, _ in tp] == ["encours", "cote-1", "cote-2"] and tp[1][1].endswith("panneau missions perso") and tp[2][1].endswith("panneau checklists perso"),
         f"espace.toml PRIME sur [espaces.perso] : ses panneaux à côté ({tp})")
    dire(any("Notes" in x for x in libelles("perso")) and "agents/perso/espace.toml › a_cote" in raisons("perso")
         and "agents/perso/espace.toml › onglets" in raisons("perso"), "espace.toml : son onglet, raisons qui nomment le fichier")
    E("vide").write_text("# rien que des commentaires\n")
    E("casse").write_text('a_cote = ["checklists"\n')
    dire([k for k, _ in travail("vide")] == ["encours", "cote-1"] and travail("vide")[1][1].endswith("panneau missions vide"),
         "espace.toml vide de clés : la disposition de config.toml s'applique")
    dire([k for k, _ in travail("casse")] == ["encours", "cote-1"] and travail("casse")[1][1].endswith("panneau missions casse"),
         "espace.toml illisible : ignoré, la disposition de config.toml s'applique")
    r = berger("regenerer")
    dire("casse : espace.toml illisible" in r.stdout and E("casse").read_text() == 'a_cote = ["checklists"\n', "regenerer : un espace.toml illisible est signalé, jamais réécrit")
    dire(travail("simple") == [("encours", f"{t}/bin/berger panneau encours simple"), ("domaine-1", "echo un")],
         "ni espace.toml ni [espaces.simple] : le domaine d'agent.conf")

    # ── élément inconnu ──
    E("main").write_text('a_cote = ["bidule:x"]\n')
    tm = travail("main")
    dire(len(tm) == 2 and tm[1][1].startswith("echo ") and "élément inconnu dans agents/main/espace.toml : bidule:x" in tm[1][1],
         f"écrit à la main, un élément inconnu s'affiche comme un message, jamais exécuté ({tm[1:]})")
    cas = [('a_cote = ["bidule:x"]\n', "élément inconnu", "élément inconnu"),
           ('a_cote = ["source:a;rm"]\n', "élément inconnu", "source avec un caractère interdit"),
           ('a_cote = ["panneau:Missions"]\n', "élément inconnu", "panneau hors [a-z]+"),
           ('onglets = { "X" = ["checklists", "fichiers", "panneau:journal", "checklists:a", "source:b"] }\n', "4 au plus", "5 éléments dans un onglet"),
           ('a_cote = ["checklists", "fichiers", "panneau:journal", "checklists:a"]\n', "3 au plus", "4 éléments à côté"),
           ('autre = 1\n', "clé inconnue", "clé inconnue"),
           ('a_cote = ["checklists"\n', "TOML invalide", "TOML invalide"),
           ('onglets = { "" = ["checklists"] }\n', "libellé", "libellé vide"),
           ('onglets = { "Y" = [] }\n', "vide", "onglet vide")]
    for texte, motif, lib in cas:
        proposer("cible", {"espace.toml": texte})
        r = berger("agent", "apercu", "master", "cible")
        a2 = berger("agent", "appliquer", "master", f"cible.{empreinte(r.stdout) or '000000000000'}")
        dire(r.returncode != 0 and "REFUSÉ" in r.stdout and motif in r.stdout and a2.returncode != 0 and "Disposition" in E("cible").read_text(),
             f"proposition refusée à l'aperçu et à l'application, rien écrit : {lib}")

    # ── proposition appliquée : aperçu avant → après, application validée sans relance, espace auto l'applique ──
    gestes(["espace", "carto"])
    T0 = datetime.datetime.now().replace(second=0, microsecond=0)
    gestes(["conformer", T0.isoformat()])                                   # première passe : carto est déjà conforme
    passes = json.loads((t / ".espace-auto.json").read_text())
    dire("carto" in passes, "espace auto : une passe inscrite pour carto")
    ids = json.loads((t / "agents/carto/.herdr.json").read_text()); conv = ids["agents"]["claude"]
    proposer("carto", {"espace.toml": 'a_cote = ["checklists", "panneau:missions"]\nonglets = { "Suivi" = ["checklists:mise"], "Veille" = ["source:alertes"] }\n'})
    r = berger("agent", "apercu", "master", "carto"); e = empreinte(r.stdout)
    dire(r.returncode == 0 and e and "DISPOSITION (avant → après)" in r.stdout and "avant ([espaces.carto])" in r.stdout
         and "après (agents/carto/espace.toml)" in r.stdout and "panneau:missions" in r.stdout and "onglet « Veille » : source:alertes" in r.stdout
         and "aucun changement de droits" in r.stdout, "aperçu : disposition effective avant (config.toml) → après (espace.toml), droits inchangés")
    (t / "faux/appels.log").unlink(missing_ok=True)
    r = berger("agent", "appliquer", "master", f"carto.{e}")
    dire(r.returncode == 0 and "panneau:missions" in E("carto").read_text() and len(list((t / "agents/carto").glob("espace.toml.avant-*"))) == 1,
         f"application : espace.toml écrit, ancien sauvegardé (.avant-<date>) ({(r.stdout + r.stderr)[-200:]})")
    appels = [json.loads(l) for l in (t / "faux/appels.log").read_text().splitlines()] if (t / "faux/appels.log").exists() else []
    dire("sans le relancer" in r.stdout and not (t / "agents/carto/.relance-en-attente").exists() and not [x for x in appels if conv in x],
         "application : l'agent n'est pas relancé (sa conversation n'en dépend pas), aucun appel vers elle")
    dire("carto" not in json.loads((t / ".espace-auto.json").read_text()), "application : la passe d'espace auto de carto est effacée")
    r = gestes(["conformer", (T0 + datetime.timedelta(minutes=1)).isoformat()])
    e2 = json.loads((t / "faux/etat.json").read_text()); ws = json.loads((t / "agents/carto/.herdr.json").read_text())
    tabs = [o["label"] for o in e2["tabs"] if o["workspace_id"] == ws["workspace"]]
    dire(any("Veille" in x for x in tabs) and "cote-2" in ws["panneaux"] and "onglet-Veille-1" in ws["panneaux"] and not r["interdits"],
         f"espace auto (minute suivante) : panneau et onglet nouveaux ajoutés, sans démarrer ni relancer ({r['gestes'].get('carto')})")
    dire("ajouté le panneau « cote-2 »" in journal("carto") and "Veille" in journal("carto"), "espace auto : chaque geste noté au journal de l'agent")
    dire(conv in {p["pane_id"] for p in e2["panes"]}, "la conversation de l'agent est intacte")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
