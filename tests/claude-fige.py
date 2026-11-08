#!/usr/bin/env python3
"""Tests « Claude Code ne se met pas à jour seul » (figer-claude, 04/11/2026) — sans modèle, installation JETABLE.
Cause : les agents sont lancés avec --setting-sources project,local, donc le réglage de l'utilisateur n'est pas lu ; seul
l'environnement du PROCESSUS compte. Berger y pose DISABLE_AUTOUPDATER=1 dans CHAQUE lancement de Claude (exec, claude -p,
panneau Herdr, `berger args` du contrat moteur et des accès externes), strict ou ouvert, et jamais chez Codex.
Usage : python3 tests/claude-fige.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0
CLE = "DISABLE_AUTOUPDATER"


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


LANCEMENTS = r'''
import json, os, runpy, shlex, subprocess, sys
sys.argv = ["b"]; g = runpy.run_path(BERGER, run_name="x")["lancer"].__globals__
g["bac_a_sable_ok"] = lambda: True
g["TMP_MAX"] = 10**6      # la longueur du dossier temporaire (limite de Claude) n'est pas l'objet : racine jetable
g["moteurs"].moteur_admis = lambda m, a: None
vu = {}
class Exec(Exception): pass
def execvpe(f, args, env): vu["env"] = dict(env); raise Exec()
def run(args, **k):
    vu["env"] = dict(k.get("env") or os.environ); vu.setdefault("appels", []).append([args[0], dict(vu["env"])])
    return subprocess.CompletedProcess(args, 0, "réponse", "")
def herdr(*args):
    if args[:2] == ("pane", "run") and " export " in args[3]:
        vu["env"] = dict(x.split("=", 1) for x in shlex.split(args[3].split(" export ", 1)[1]) if "=" in x)
    return {}
g["os"].execvpe = execvpe; g["herdr"] = herdr; g["time"].sleep = lambda s: None
out = {}
for a in AGENTS:
    o = out[a] = {"lancer": {}, "demander": {}, "herdr": {}, "args": {}}
    for m in ("claude", "codex"):
        vu.clear()
        try: g["lancer"](a, m)
        except (Exec, SystemExit): pass
        o["lancer"][m] = vu.get("env", {})
        vu.clear()
        try: g["demarrer_agent"](a, m, "p1"); o["herdr"][m] = vu.get("env", {})
        except SystemExit: o["herdr"][m] = "REFUSÉ"
    g["subprocess"].run = run
    for m in ("claude", "codex"):        # codex ne répond pas ici : l'appel bascule sur claude ; on garde l'environnement de CHAQUE programme lancé
        vu.clear(); g["demander"](a, "q", m); o["demander"][m] = {x[0]: x[1] for x in vu.get("appels", [])}
    g["subprocess"].run = subprocess.run
print("JSON" + json.dumps(out))
'''


def lancements(i, env, agents):
    code = f"BERGER = {str(i / 'bin/berger')!r}\nAGENTS = {list(agents)!r}\n" + LANCEMENTS
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120, cwd=i)
    ligne = next((x for x in r.stdout.splitlines() if x.startswith("JSON")), None)
    if ligne is None: raise SystemExit(f"ÉCHEC lancements illisibles : {(r.stdout + r.stderr)[-400:]}")
    return json.loads(ligne[4:])


def args_berger(i, env, a, m):
    """`berger args <agent> <moteur> --contrat` : ce que lisent le contrat moteur et les accès externes (ponts)."""
    code = (f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');g=g['lancer'].__globals__\n"
            f"g['TMP_MAX']=10**6;g['moteurs'].moteur_admis=lambda m,a:None;g['bac_a_sable_ok']=lambda:True;g['arguments_pont']([{a!r},{m!r},'--contrat'])")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    try: return json.loads(r.stdout)["env"]
    except (ValueError, KeyError): return {"_erreur": (r.stdout + r.stderr)[-300:]}


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    for a, mur in (("compta", "strict"), ("ouvert", "ouvert")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\npanneaux = claude\nmur = {mur}\nheures = aucune\noutils =\n")
    env = {k: v for k, v in os.environ.items() if k != CLE}
    env.update({"HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": "/bin/false", "BERGER_TMP_AGENTS": str(m / "tmp")})
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0, "regenerer réussit" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr)[-200:]}"))

    lan = lancements(i, env, ("compta", "ouvert"))
    for a in ("compta", "ouvert"):
        for quoi, mo in (("lancer", "claude"), ("demander", "claude"), ("herdr", "claude")):
            v = lan[a][quoi][mo] if quoi != "demander" else lan[a][quoi][mo]["claude"]
            dire(v.get(CLE) == "1", f"{quoi} Claude ({a}) : {CLE}=1 dans l'environnement du processus — vu : {v.get(CLE)}")
        for quoi, mo in (("lancer", "codex"), ("herdr", "codex")):
            dire(CLE not in lan[a][quoi][mo], f"{quoi} Codex ({a}) : {CLE} non posé (Codex inchangé)")
        dire(CLE not in lan[a]["demander"]["codex"]["codex"] and lan[a]["demander"]["codex"]["claude"].get(CLE) == "1",
             f"demander ({a}) : Codex sans {CLE}, la bascule sur Claude avec")
        dire(args_berger(i, env, a, "claude").get(CLE) == "1", f"berger args Claude ({a}, contrat moteur / ponts) : {CLE}=1")
        dire(CLE not in args_berger(i, env, a, "codex"), f"berger args Codex ({a}) : {CLE} non posé")

sys.exit(1 if ko else 0)
