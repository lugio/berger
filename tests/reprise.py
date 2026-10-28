#!/usr/bin/env python3
"""Tests de la REPRISE après un redémarrage du serveur Herdr (`berger reprendre`, crochet [[startup]] du plugin herdr-plugin/)
— sans modèle, avec un FAUX Herdr À ÉTAT (jamais le vrai). Doc Herdr « Session state and restore » : la disposition revient,
les processus non. Vérifie : panes restaurés vides → agent relancé AVEC sa conversation (claude --resume <id>), panneaux et
onglets de l'espace Berger refaits ; tout vivant → rien touché ; pas de conversation → conversation neuve, dit ; process-info
illisible → rien relancé ; manifeste du plugin valide ; regenerer lie le plugin une seule fois.
Usage : python3 tests/reprise.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, shutil, subprocess, sys, tempfile, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["FAUX_HERDR"]; f = T + "/etat.json"; e = json.load(open(f)); a = sys.argv[1:]
with open(T + "/appels.log", "a") as j: j.write(json.dumps(a) + "\n")
n = e.setdefault("n", 20); r = {}
def neuf(ws):
    e["n"] += 1; return f"{ws}:p{e['n']}"
if a[:2] == ["workspace", "list"]: r = {"workspaces": [{"workspace_id": w, "label": l} for w, l in e["espaces"].items()]}
elif a[:2] == ["tab", "list"]:
    ws = a[a.index("--workspace") + 1]; r = {"tabs": [{"tab_id": t, "label": l} for t, l in e["onglets"].items() if t.startswith(ws + ":")]}
elif a[:2] == ["pane", "list"]:
    ws = a[a.index("--workspace") + 1]; r = {"panes": [{"pane_id": p, "tab_id": x["tab"]} for p, x in e["panes"].items() if p.startswith(ws + ":")]}
elif a[:2] == ["pane", "get"]: r = {"pane": {"pane_id": a[2], "agent_status": "idle"}} if a[2] in e["panes"] else {}
elif a[:2] == ["pane", "process-info"]:
    p = a[a.index("--pane") + 1]
    if e.get("illisible"): r = {}
    elif e.get("aucun"): r = {"process_info": {"foreground_processes": []}}
    else: r = {"process_info": {"foreground_processes": [{"name": "bash" if e["panes"].get(p, {}).get("vide") else "python3"}]}}
elif a[:2] == ["agent", "list"]: r = {"agents": [{"pane_id": p, "name": "x"} for p in e.get("vivants", [])]}
elif a[:2] == ["agent", "start"]: e.setdefault("vivants", []).append(a[a.index("--pane") + 1]); r = {"agent": {"name": a[2]}}
elif a[:2] == ["tab", "create"]:
    ws = a[a.index("--workspace") + 1]; t = ws + ":t" + str(len(e["onglets"]) + 1); p = neuf(ws)
    e["onglets"][t] = a[a.index("--label") + 1]; e["panes"][p] = {"tab": t}; r = {"tab": {"tab_id": t}, "root_pane": {"pane_id": p}}
elif a[:2] == ["tab", "close"]:
    e["onglets"].pop(a[2], None); e["panes"] = {p: x for p, x in e["panes"].items() if x["tab"] != a[2]}
elif a[:2] == ["pane", "split"]:
    b = a[a.index("--pane") + 1]; p = neuf(b.split(":")[0]); e["panes"][p] = {"tab": e["panes"][b]["tab"]}; r = {"pane": {"pane_id": p}}
elif a[:2] == ["pane", "close"]: e["panes"].pop(a[2], None)
elif a[:2] == ["pane", "run"] and a[2] in e["panes"]: e["panes"][a[2]]["vide"] = False
elif a[:2] == ["plugin", "list"]: print("berger.reprise" if e.get("plugin") else "No plugins installed."); json.dump(e, open(f, "w")); sys.exit(0)
elif a[:2] == ["plugin", "link"]: e["plugin"] = True; print("linked"); json.dump(e, open(f, "w")); sys.exit(0)
json.dump(e, open(f, "w")); print(json.dumps({"result": r}))
'''


def restaure(vide=True):
    """Ce que Herdr rend après un redémarrage : la disposition d'avant, chaque pane un shell (vide) ou vivant."""
    return {"espaces": {"w2": "🐑 Berger", "w4": "● Vigie"},
            "onglets": {"w2:t1": "🏠 Accueil", "w2:t2": "📋 Tableau", "w4:t1": "💼 Travail", "w4:t2": "📇 Fiche"},
            "panes": {"w2:p1": {"tab": "w2:t1", "vide": vide}, "w2:p2": {"tab": "w2:t2", "vide": vide},
                      "w4:p1": {"tab": "w4:t1", "vide": vide}, "w4:p8": {"tab": "w4:t1", "vide": vide}, "w4:p9": {"tab": "w4:t2", "vide": vide}},
            "vivants": [] if vide else ["w4:p1"]}


def installation(t, etat, conversation=True):
    m = t / "maison"; i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun", "herdr-plugin"))
    (m / "coffre.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\nicone_berger = "🐑"\n')
    f = t / "faux"; f.mkdir(); (f / "herdr").write_text(FAUX_HERDR); os.chmod(f / "herdr", 0o755)
    (f / "etat.json").write_text(json.dumps({"espaces": {}, "onglets": {}, "panes": {}, "plugin": True}))
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "FAUX_HERDR": str(f), "BERGER_HERDR": str(f / "herdr"),
           "PATH": f"{f}:" + os.environ["PATH"]}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=120)
    sonde = subprocess.run([sys.executable, "-c", f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');print(g['HERDR'])"],
                           env=env, capture_output=True, text=True)
    if sonde.stdout.strip() != str(f / "herdr"): sys.exit(f"ARRÊT : Berger n'utiliserait pas le faux Herdr ({sonde.stdout.strip() or sonde.stderr[-200:]})")
    b("nouveau", "vigie", "Vigie")
    conf = i / "agents/vigie/agent.conf"; conf.write_text(re.sub(r"(?m)^moteur = .*$", "moteur = claude", conf.read_text()) + "mur = ouvert\npanneaux = claude\n")
    (i / "agents/vigie/.herdr.json").write_text(json.dumps({"workspace": "w4", "agents": {"claude": "w4:p1"}, "panneaux": {"encours": "w4:p8", "fiche": "w4:p9"}}))
    if conversation:
        d = m / ".claude/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(i / "agents/vigie")); d.mkdir(parents=True)
        (d / "ancienne1.jsonl").write_text('{"entrypoint":"cli"}\n'); os.utime(d / "ancienne1.jsonl", (1, 1))
        (d / "derniere9.jsonl").write_text('{"entrypoint":"cli"}\n'); os.utime(d / "derniere9.jsonl", (2, 2))
        (d / "fond-planif.jsonl").write_text('{"entrypoint":"sdk-cli"}\n')        # appel claude -p, plus récent : à NE PAS reprendre
    (f / "appels.log").unlink(missing_ok=True); (f / "etat.json").write_text(json.dumps(etat))
    return i, f, b


appels = lambda f: [json.loads(x) for x in (f / "appels.log").read_text().splitlines()] if (f / "appels.log").exists() else []
mutations = lambda f: [a for a in appels(f) if a[:2] in (["agent", "start"], ["tab", "close"], ["pane", "close"], ["pane", "run"], ["tab", "create"], ["pane", "split"])]

with tempfile.TemporaryDirectory() as t:                                    # 1. tout restauré vide
    i, f, b = installation(Path(t), restaure(True))
    r = b("reprendre"); depart = [a for a in appels(f) if a[:2] == ["agent", "start"]]
    dire(r.returncode == 0 and len(depart) == 1 and depart[0][-2:] == ["--resume", "derniere9"],
         f"pane d'agent vide → agent relancé avec sa dernière conversation INTERACTIVE (pas l'appel claude -p plus récent) — {depart[0][-2:] if depart else r.stderr[-200:]}")
    dire(depart and "--dangerously-skip-permissions" in depart[0], "relancé avec les options de Berger (pas un « claude --resume » nu)")
    runs = [a[3] for a in appels(f) if a[:2] == ["pane", "run"]]
    dire(any("panneau encours vigie" in x for x in runs) and any("panneau fiche vigie" in x for x in runs), "panneaux de l'agent relancés (en cours, fiche)")
    dire(not [a for a in appels(f) if a[:2] in (["tab", "close"], ["pane", "close"])] and ["pane", "run", "w2:p1"] == next(a[:3] for a in appels(f) if a[:3] == ["pane", "run", "w2:p1"])
         and any("panneau accueil" in x for x in runs) and any("panneau colonnes" in x for x in runs),
         "espace Berger : chaque panneau relancé À SA PLACE (Accueil, Tableau), rien fermé")
    dire((i / "agents/vigie/.conversation-claude").read_text().strip() == "derniere9", "la conversation reprise est notée pour la prochaine fois")
    dire("repris après un redémarrage de Herdr (conversation derniere" in (i / "agents/vigie/memory").joinpath(next((i / "agents/vigie/memory").glob("*.md")).name).read_text(),
         "le journal de l'agent note la reprise")
    dire("Vigie (claude) repris, conversation derniere" in r.stdout, f"compte rendu clair — {r.stdout.strip()[:150]}")

with tempfile.TemporaryDirectory() as t:                                    # 2. tout vivant (ex. reprise à chaud)
    i, f, b = installation(Path(t), restaure(False))
    r = b("reprendre")
    dire(r.returncode == 0 and not mutations(f) and "rien à reprendre" in r.stdout, f"tout tourne → rien touché, rien relancé ({len(mutations(f))} geste(s))")

with tempfile.TemporaryDirectory() as t:                                    # 3. pas de conversation enregistrée
    i, f, b = installation(Path(t), restaure(True), conversation=False)
    r = b("reprendre"); depart = [a for a in appels(f) if a[:2] == ["agent", "start"]]
    dire(len(depart) == 1 and "--resume" not in depart[0] and "--session-id" in depart[0] and "conversation neuve" in r.stdout
         and (i / "agents/vigie/.conversation-claude").read_text().strip() == depart[0][depart[0].index("--session-id") + 1],
         "aucune conversation → conversation neuve, c'est dit, et son id est noté (--session-id) pour la reprendre ensuite")
with tempfile.TemporaryDirectory() as t:                                    # 3 bis. pane sans aucun processus (shell pas encore né)
    e = restaure(True); e["aucun"] = True
    i, f, b = installation(Path(t), e)
    r = subprocess.run([sys.executable, "-c", f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');print(g['pane_vide']('w4:p1'))"],
                       env={**os.environ, "HOME": str(i.parent), "BERGER_DIR": str(i), "FAUX_HERDR": str(f), "BERGER_HERDR": str(f / "herdr")}, capture_output=True, text=True)
    dire(r.stdout.strip() == "False", "pane sans aucun processus (shell pas encore prêt) : PAS considéré comme vide")

with tempfile.TemporaryDirectory() as t:                                    # 4. process-info illisible
    e = restaure(True); e["illisible"] = True
    i, f, b = installation(Path(t), e)
    r = b("reprendre")
    dire(not [a for a in appels(f) if a[:2] in (["agent", "start"], ["tab", "close"])], "process-info illisible → on ne relance rien (jamais deux agents dans un pane)")

with tempfile.TemporaryDirectory() as t:                                    # 5. regenerer lie le plugin, une fois
    i, f, b = installation(Path(t), restaure(False)); e = json.loads((f / "etat.json").read_text()); e["plugin"] = False
    (f / "etat.json").write_text(json.dumps(e))
    b("regenerer"); b("regenerer"); liens = [a for a in appels(f) if a[:2] == ["plugin", "link"]]
    dire(len(liens) == 1 and liens[0][2] == str(i / "herdr-plugin"), f"regenerer lie le plugin Herdr de Berger, une seule fois ({len(liens)})")

m = tomllib.loads((SRC / "herdr-plugin/herdr-plugin.toml").read_text())
cmd = m["startup"][0]["command"]
dire(m["id"] == "berger.reprise" and m["min_herdr_version"] == "0.9.0" and cmd[-2:] == ["reprendre", "--fond"]
     and (SRC / "herdr-plugin" / cmd[1]).resolve() == (SRC / "bin/berger").resolve(),
     "manifeste du plugin : crochet [[startup]] → bin/berger reprendre (chemin relatif au dossier du plugin, où Herdr le lance)")

sys.exit(1 if ko else 0)
