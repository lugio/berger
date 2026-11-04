#!/usr/bin/env python3
"""Équivalence des verbes de mission (modulaire, lot 4a, docs/plans/2026-10-27-modulaire-spec.md § Tests « Équivalence des sorties ») :
`mission`, `suivi`, `rapport-mission`, `fin-mission`, mesurés sur une installation JETABLE, puis comparés à ce que mesurait `main` avant le
déplacement (tests/attendus/equivalence-missions.json). Pour chaque scénario : code de sortie, sortie standard, dernière ligne d'erreur, et les
fichiers écrits (MISSION.md, historique/, journal, CHECKLIST.md, .herdr.json, échanges, validations) ; plus les appels à Herdr (un faux Herdr à
état, posé par BERGER_HERDR) et le lancement strict (agent, moteur, panneau et arguments du moteur rendus par le cœur au démarrage).
Trois voies : la ligne de commande seule (refus, transport privé, plafond), la ligne de commande avec démarrage et remise doublés (le cœur reste
le même : demarrer_agent, espace, parler sont du cœur des deux côtés), et le courtier (droits entre agents : mission:<agent>, chef, coordinateur).
Ce qui varie d'une exécution à l'autre est normalisé (chemin de l'installation, dates, heures, identifiants de conversation, numéros de ligne).
Usage : python3 tests/equivalence-missions.py               mesure ce dépôt et compare (0 = identique)
        python3 tests/equivalence-missions.py --mesurer <source>   imprime la mesure d'un autre arbre (ex. un `git archive` de main)
        python3 tests/equivalence-missions.py --produire <source> <fichier>   écrit la mesure de <source> dans <fichier> (les attendus)
Les attendus (tests/attendus/equivalence-missions.json) ont été produits sur main 5767d99, avant le lot 4a :
        d=$(mktemp -d) && git archive 5767d99 | tar -x -C "$d" && python3 tests/equivalence-missions.py --produire "$d" tests/attendus/equivalence-missions.json"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ATTENDU = SRC / "tests/attendus/equivalence-missions.json"

# Un faux Herdr À ÉTAT (espaces, onglets, panneaux) : chaque appel est tracé ; ce qu'il ne connaît pas rend {"result": {}}.
FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
etat = Path(os.environ["FAUX_ETAT"]); d = json.loads(etat.read_text()) if etat.exists() else {"n": 0, "ws": [], "tabs": {}, "panes": {}}
a = sys.argv[1:]
with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(a) + "\n")
def opt(n): return a[a.index(n) + 1] if n in a else None
def neuf(p): d["n"] += 1; return f"{p}{d['n']}"
r = {}
if a[:2] == ["pane", "get"]:
    p = d["panes"].get(a[2]); r = {"pane": {**p, "pane_id": a[2], "agent_status": "idle"}} if p else {}
elif a[:2] == ["workspace", "list"]: r = {"workspaces": [{"workspace_id": w} for w in d["ws"]]}
elif a[:2] == ["tab", "list"]: r = {"tabs": [{"tab_id": t} for t, w in d["tabs"].items() if w == opt("--workspace")]}
elif a[:2] == ["tab", "create"]:
    t = neuf("t"); p = neuf("p"); d["tabs"][t] = opt("--workspace"); d["panes"][p] = {"tab_id": t, "workspace_id": opt("--workspace")}
    r = {"tab": {"tab_id": t}, "root_pane": {"pane_id": p}}
elif a[:2] == ["pane", "split"]:
    base = d["panes"].get(opt("--pane")) or {}; p = neuf("p"); d["panes"][p] = dict(base); r = {"pane": {"pane_id": p}}
elif a[:2] == ["pane", "list"]: r = {"panes": [{"pane_id": p, **v} for p, v in d["panes"].items() if v.get("workspace_id") == opt("--workspace")]}
elif a[:2] == ["pane", "close"]: d["panes"].pop(a[2], None)
elif a[:2] == ["tab", "close"]:
    d["tabs"].pop(a[2], None); d["panes"] = {p: v for p, v in d["panes"].items() if v.get("tab_id") != a[2]}
elif a[:2] == ["workspace", "close"]:
    d["ws"] = [w for w in d["ws"] if w != a[2]]; d["panes"] = {p: v for p, v in d["panes"].items() if v.get("workspace_id") != a[2]}
elif a[:2] == ["agent", "list"]: r = {"agents": []}
etat.write_text(json.dumps(d)); print(json.dumps({"result": r}))
'''

# La ligne de commande, dans le processus : le démarrage d'un moteur, l'espace complet et la remise du message (fonctions du cœur, des deux côtés)
# sont relevés au lieu d'être faits ; le relevé du démarrage garde ce que le cœur aurait lancé (moteurs.args_moteur : le lancement strict).
LANCEUR = r'''
import json, os, sys
src = sys.argv[1]; g = {"__name__": "essai", "__file__": src}
exec(compile(open(src).read(), src, "exec"), g)
def trace(*x):
    with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(["@"] + [str(v) for v in x]) + "\n")
def demarrer(a, m, p, reprise=None):
    try: lance = g["moteurs"].args_moteur(a, m)
    except BaseException as e: lance = f"{type(e).__name__}: {e}"
    trace("demarrer", a, m, p, json.dumps(lance)); return m
def espace(a):
    ids = g["herdr_ids"](a); ids.update({"workspace": f"ws-{a}", "agents": {g["conf"](a)["moteur"]: f"pe-{a}"}})
    (g["dossier"](a) / ".herdr.json").write_text(json.dumps(ids)); trace("espace", a)
g["demarrer_agent"] = demarrer; g["espace"] = espace
g["parler"] = lambda a, message, moteur=None, de=None: trace("parler", a, moteur, de, message)
g["time"].sleep = lambda s: None
g["main"](sys.argv[2:])
'''

# Le courtier, appelé directement (comme tests/missions.py) : ses droits entre agents, puis berger en sous-processus.
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

AGENTS = {
    "chef": "moteur = claude\noutils = mission:cible\n",
    "coord": "moteur = claude\n",
    "dev": "moteur = claude\nprojet = p\nsujet = s\nbranche = p/s\n",
    "cible": "moteur = claude\n",
    "autre": "moteur = claude\n",
    "troisieme": "moteur = claude\n",
    "intrus": "moteur = claude\n",
}


def normaliser(texte, t):
    texte = str(texte).replace(str(t), "<T>")
    texte = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<UUID>", texte)
    texte = re.sub(r"\d{4}-\d{2}-\d{2}[T _]\d{2}:?\d{2}(:\d{2})?", "<DATE-HEURE>", texte)
    texte = re.sub(r"\d{4}-\d{2}-\d{2}", "<DATE>", texte)
    texte = re.sub(r"\b\d{2}:\d{2}(:\d{2})?\b", "<HEURE>", texte)
    texte = re.sub(r"line \d+", "line <N>", texte)
    return re.sub(r"/tmp/[^\s\"']*herdr-absent-\d+\.sock", "<SOCKET>", texte)


def fichiers(t):
    """Ce que les verbes de mission écrivent : dossiers d'agents (hors ce que le moteur prépare), échanges, validations."""
    out = {}
    for a in sorted(AGENTS):
        d = t / "agents" / a
        for f in sorted(d.rglob("*")):
            r = f.relative_to(d)
            if f.is_file() and (r.parts[0] in ("MISSION.md", "CHECKLIST.md", ".herdr.json", "historique", "memory", "a-lire")):
                out[normaliser(f"{a}/{r}", t)] = normaliser(f.read_text(), t)
    e = t / "courtier/echanges.jsonl"
    out["courtier/echanges.jsonl"] = normaliser(e.read_text(), t) if e.exists() else None
    v = t / "courtier/validations"
    out["courtier/validations"] = sorted(x.name for x in v.iterdir()) if v.is_dir() else []
    return out


def mesurer(src):
    src = Path(src).resolve(); resultats = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        _produit.copier(src, t, ("bin", "courtier", "commun"))
        (t / "coffre.json").write_text("{}")
        (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n\n[missions]\nmax = 2\n\n'
                                       f'[equipes.p]\nchef_projet = "chef"\ncoordinateur = "coord"\ndepot = "{t}/depot"\n')
        for a, c in AGENTS.items():
            d = t / "agents" / a; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nheures = aucune\n{c}")
        (t / "faux").mkdir(); herdr = t / "faux/herdr"; herdr.write_text(FAUX_HERDR); herdr.chmod(0o755)
        (t / "faux/notify-send").write_text("#!/bin/sh\nexit 0\n"); (t / "faux/notify-send").chmod(0o755)
        trace = t / "faux/trace.jsonl"
        env = dict(os.environ, BERGER_DIR=str(t), HOME=str(t), PATH=f"{t}/faux:{os.environ['PATH']}", BERGER_NOTIFY_SEND=str(t / "faux/notify-send"))
        env_faux = dict(env, BERGER_HERDR=str(herdr), FAUX_ETAT=str(t / "faux/etat.json"), FAUX_TRACE=str(trace))
        (t / "faux/etat.json").write_text(json.dumps({"n": 0, "ws": ["ws-chef", "ws-coord"], "tabs": {"t-chef": "ws-chef"},
                                                     "panes": {"pe-chef": {"tab_id": "t-chef", "workspace_id": "ws-chef"}}}))
        (t / "agents/chef/.herdr.json").write_text(json.dumps({"workspace": "ws-chef", "agents": {"claude": "pe-chef"}}))
        (t / "agents/coord/.herdr.json").write_text(json.dumps({"workspace": "ws-coord"}))
        avant = {"fichiers": fichiers(t)}

        def noter(nom, r, extra=None):
            appels = [normaliser(l, t) for l in trace.read_text().splitlines()] if trace.exists() else []
            trace.unlink(missing_ok=True)
            apres = fichiers(t)
            ecrits = {k: v for k, v in apres.items() if avant["fichiers"].get(k, "∅") != v}
            ecrits.update({k: "(supprimé)" for k in avant["fichiers"] if k not in apres})
            avant["fichiers"] = apres
            err = [l for l in r.stderr.splitlines() if l.strip()]
            resultats.append({"scenario": nom, "code": r.returncode, "stdout": normaliser(r.stdout, t),
                              "stderr_fin": normaliser(err[-1], t) if err else "", "fichiers_ecrits": ecrits, "herdr": appels, **(extra or {})})

        def cli(nom, *argv, stdin=None):
            r = subprocess.run([str(t / "bin/berger"), *argv], input=stdin, env=env, capture_output=True, timeout=120)
            r.stdout, r.stderr = r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace"); noter(nom, r)

        def doublee(nom, *argv, stdin=None):
            r = subprocess.run([sys.executable, "-c", LANCEUR, str(t / "bin/berger"), *argv], input=stdin, env=env_faux, capture_output=True, timeout=120)
            r.stdout, r.stderr = r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace"); noter(nom, r)

        def courtier(nom, agent, verbe, *args):
            req = json.dumps({"outil": "mission", "verbe": verbe, "args": list(args)})
            r = subprocess.run([sys.executable, "-c", APPEL, str(t / "courtier/courtier"), agent, req], env=env, capture_output=True, text=True, timeout=180)
            try: rep = json.loads(r.stdout)
            except ValueError: rep = {"illisible": r.stdout[-200:]}
            r.stdout = json.dumps(rep, ensure_ascii=False, sort_keys=True); noter(nom, r)

        prive = lambda *v: json.dumps(list(v)).encode()
        # 1. ligne de commande : formes et refus (aucun Herdr)
        cli("suivi sans agent", "suivi")
        cli("suivi agent inconnu", "suivi", "fantome")
        cli("suivi sans mission", "suivi", "cible")
        cli("rapport-mission sans agent", "rapport-mission")
        cli("rapport-mission sans mission", "rapport-mission", "cible")
        cli("fin-mission sans agent", "fin-mission")
        cli("fin-mission sans mission", "fin-mission", "cible")
        cli("fin-mission agent inconnu", "fin-mission", "fantome")
        cli("mission en texte positionnel", "mission", "cible", "fais x")
        cli("mission sans agent (--stdin)", "--stdin", stdin=prive("mission"))
        cli("mission agent inconnu (--stdin)", "--stdin", stdin=prive("mission", "fantome", "fais x"))
        cli("mission moteur inconnu (--stdin)", "--stdin", stdin=prive("mission", "cible", "fais x", "--moteur", "inexistant"))
        cli("mission modèle non permis (--stdin)", "--stdin", stdin=prive("mission", "cible", "fais x", "--modele", "pas-permis"))
        cli("mission vide (--stdin)", "--stdin", stdin=prive("mission", "cible", "   "))
        cli("transport : JSON invalide", "--stdin", stdin=b"[mission")
        cli("transport : pas un tableau de textes", "--stdin", stdin=b'{"mission": 1}')
        cli("transport : --stdin imbriqué", "--stdin", stdin=prive("--stdin"))
        cli("transport : UTF-8 requis", "--stdin", stdin=b'["mission", "cible", "\xff"]')
        cli("transport : plus d'un Mio", "--stdin", stdin=b"[" + b" " * (1024 * 1024) + b"]")
        cli("transport : verbe privé imbriqué", "--stdin", stdin=prive("--stdin", "mission"))
        # 2. ligne de commande, démarrage et remise relevés : confier, plafond, suivi, rapport, terminer
        doublee("mission par le propriétaire (espace)", "--stdin", stdin=prive("mission", "cible", "Fais x.\nDeux lignes."))
        doublee("mission déjà en cours", "--stdin", stdin=prive("mission", "cible", "encore"))
        doublee("mission par le chef (onglet Missions, lancement strict)", "--stdin", stdin=prive("mission", "dev", "Fais y.", "--par", "chef", "--moteur", "claude"))
        doublee("plafond : troisième mission refusée", "--stdin", stdin=prive("mission", "troisieme", "Fais z."))
        doublee("chef de projet hors plafond, déjà ouvert", "--stdin", stdin=prive("mission", "chef", "Pilote.", "--par", "coord"))
        doublee("suivi d'une mission (espace)", "suivi", "cible")
        doublee("suivi d'une mission (onglet Missions)", "suivi", "dev")
        (t / "agents/cible/a-lire").mkdir(exist_ok=True); (t / "agents/cible/a-lire/rapport.md").write_text("# Rapport\nfait\n")
        doublee("rapport-mission avec un document", "rapport-mission", "cible")
        doublee("fin-mission refusée : checklist non finie", "fin-mission", "cible", "--par", "chef")
        (t / "agents/cible/CHECKLIST.md").write_text("# Travail\n- [x] fait\nTerminé 2026-10-29 10:00\n")
        doublee("fin-mission : checklist finie (espace fermé)", "fin-mission", "cible", "--par", "chef")
        doublee("fin-mission par le propriétaire, sans checklist (motif)", "fin-mission", "dev", "--motif", "essai")
        (t / "agents/chef/CHECKLIST.md").write_text("# Pilote\n- [x] fait\nTerminé 2026-10-29 10:00\n")
        doublee("fin-mission d'un chef de projet (espace gardé)", "fin-mission", "chef", "--par", "coord")
        # 3. le courtier : droits entre agents (mission:<agent>, chef, coordinateur), puis berger
        courtier("courtier : sans droit", "intrus", "confier", "cible", "fais x")
        courtier("courtier : coordinateur vers un développeur (refusé)", "coord", "confier", "dev", "fais x")
        courtier("courtier : verbe inconnu", "chef", "lancer", "dev")
        courtier("courtier : chef, suivi de son développeur", "chef", "suivi", "dev")
        courtier("courtier : chef, rapport sans mission", "chef", "rapport", "dev")
        courtier("courtier : chef, terminer sans mission", "chef", "terminer", "dev")
        courtier("courtier : droit déclaré (mission:cible), moteur refusé", "chef", "confier", "cible", "fais x", "inexistant")
        courtier("courtier : coordinateur, modèle refusé pour son chef", "coord", "confier", "chef", "pilote", "claude", "pas-permis")
    return resultats


if __name__ == "__main__":
    if sys.argv[1:2] == ["--mesurer"]:
        print(json.dumps(mesurer(sys.argv[2]), ensure_ascii=False, indent=1)); sys.exit(0)
    if sys.argv[1:2] == ["--produire"] and len(sys.argv) == 4:
        Path(sys.argv[3]).write_text(json.dumps(mesurer(sys.argv[2]), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"attendus écrits : {sys.argv[3]} (mesurés sur {sys.argv[2]})"); sys.exit(0)
    mesure, attendu = mesurer(SRC), json.loads(ATTENDU.read_text(encoding="utf-8"))
    ko = 0
    par_nom = {x["scenario"]: x for x in attendu}
    for m in mesure:
        a = par_nom.pop(m["scenario"], None)
        ok = a == m
        ko += not ok
        print(("ok     " if ok else "ÉCHEC  ") + f"{m['scenario']} : code {m['code']}, " + (m["stderr_fin"][:90] or m["stdout"].strip()[:90]))
        if not ok and a is not None:
            for k in sorted(set(a) | set(m)):
                if a.get(k) != m.get(k): print(f"         {k} : avant {json.dumps(a.get(k), ensure_ascii=False)[:400]}\n         {' ' * len(k)}   après {json.dumps(m.get(k), ensure_ascii=False)[:400]}")
    for nom in par_nom: ko += 1; print(f"ÉCHEC  {nom} : mesuré avant, absent après")
    print(f"---- {ko} écart(s) sur {len(mesure)} scénario(s)")
    sys.exit(1 if ko else 0)
