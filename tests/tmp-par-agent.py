#!/usr/bin/env python3
"""Tests du dossier temporaire PAR agent (tmp-par-agent, 14/10/2026) — sans modèle, installation JETABLE :
réglages Claude (CLAUDE_CODE_TMPDIR, denyRead du commun et des autres, refus Read/Edit), profil Codex (le sien en
écriture, les autres « none »), dossiers 700, relais réseau jamais couvert, refus de lancer au-delà de 44 octets ou sur
un dossier douteux, mur ouvert inchangé ; CLAUDE_CODE_TMPDIR dans l'environnement de CHAQUE lancement (exec, claude -p,
panneau Herdr). La preuve dans le vrai bac à sable est faite par tests/sonde-tmp.py (tout.sh).
Usage : python3 tests/tmp-par-agent.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import hashlib, json, os, stat, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
UID = os.getuid(); COMMUN = f"/tmp/claude-{UID}"; FIN = len(f"/{'0' * 12}/claude-{UID}")
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def racine_courte():
    """Une racine jetable assez courte pour Claude (≤ 44 octets au bout) : /tmp/bt…, sinon (bac à sable : /tmp en lecture
    seule) sous le TMPDIR, si la place le permet. None : impossible ici."""
    try: return Path(tempfile.mkdtemp(prefix="bt", dir="/tmp"))
    except OSError: pass
    base = Path(tempfile.gettempdir())
    for c in "0123456789abcdefghijklmnopqrstuvwxyz":
        r = base / f"b{c}"
        if len(str(r)) + FIN > 44: return None
        try: r.mkdir(mode=0o700); return r
        except FileExistsError: continue
    return None


def berger(i, env, *args):
    return subprocess.run([sys.executable, str(i / "bin/berger"), *args], env=env, capture_output=True, text=True, timeout=120)


def exiger(i, env, a):
    """exiger_tmp(a) appelé directement : (refusé ?, message)."""
    code = f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');g['exiger_tmp']({a!r});print('LANCE')"
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    return "LANCE" not in r.stdout, (r.stdout + r.stderr).strip()


LANCEMENTS = r'''
import json, os, runpy, shlex, subprocess, sys
sys.argv = ["b"]; g = runpy.run_path(BERGER, run_name="x")["lancer"].__globals__   # les VRAIES globales (run_path rend une copie)
g["bac_a_sable_ok"] = lambda: True                  # le vrai bwrap n'est pas l'objet du test (et ne démarre pas dans un bac)
g["moteurs"].moteur_admis = lambda m, a: None               # l'admission des moteurs non plus (tests/mcp-trous.py)
vu = {}
class Exec(Exception): pass
def execvpe(f, args, env): vu["env"] = dict(env); raise Exec()
def run(args, **k):
    vu["env"] = dict(k.get("env") or os.environ)
    return subprocess.CompletedProcess(args, 0, "réponse", "")
def herdr(*args):
    if args[:2] == ("pane", "run") and " export " in args[3]:
        vu["env"] = dict(x.split("=", 1) for x in shlex.split(args[3].split(" export ", 1)[1]) if "=" in x)
    return {}
g["os"].execvpe = execvpe; g["herdr"] = herdr; g["time"].sleep = lambda s: None
out = {}
for a in AGENTS:
    o = out[a] = {"lancer": {}, "demander": {}, "herdr": {}}
    for m in ("claude", "codex"):
        vu.clear()
        try: g["lancer"](a, m)
        except (Exec, SystemExit): pass
        o["lancer"][m] = vu.get("env", {})
        vu.clear()
        try: g["demarrer_agent"](a, m, "p1"); o["herdr"][m] = vu.get("env", {})
        except SystemExit: o["herdr"][m] = "REFUSÉ"
    vu.clear(); g["subprocess"].run = run; g["demander"](a, "q", "claude"); o["demander"]["claude"] = vu.get("env", {})
    g["subprocess"].run = subprocess.run
print("JSON" + json.dumps(out))
'''


def lancements(i, env, agents=("compta", "ouvert")):
    """Environnement que chaque chemin de lancement donnerait au moteur, sans le lancer : exec (lancer), subprocess.run
    (demander), export du panneau Herdr (demarrer_agent : relance, reprise, espace, mission). Intercepté dans un processus
    Python à part, sur l'installation jetable."""
    code = f"BERGER = {str(i / 'bin/berger')!r}\nAGENTS = {list(agents)!r}\n" + LANCEMENTS
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120, cwd=i)
    ligne = next((x for x in r.stdout.splitlines() if x.startswith("JSON")), None)
    if ligne is None: raise SystemExit(f"ÉCHEC lancements illisibles : {(r.stdout + r.stderr)[-400:]}")
    return json.loads(ligne[4:])


R = racine_courte()
if R is None:
    print("NON JOUÉ aucune racine temporaire assez courte n'est inscriptible ici (bac à sable) : suite jouée par les portes")
    sys.exit(0)
try:
    with tempfile.TemporaryDirectory() as t:
        m = Path(t); i = m / "berger"
        _produit.copier(SRC, i, ("bin", "courtier", "commun"))
        (m / "coffre-essai.json").write_text("{}")
        (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
        for a, mur in (("compta", "strict"), ("voisin", "strict"), ("ouvert", "ouvert")):
            d = i / "agents" / a; (d / "memory").mkdir(parents=True)
            (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\npanneaux = claude\nmur = {mur}\nheures = aucune\noutils =\n")
        env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": "/bin/false", "BERGER_TMP_AGENTS": str(R)}
        r = berger(i, env, "regenerer")
        dire(r.returncode == 0 and "dossier temporaire refusé" not in r.stdout,
             "regenerer réussit, dossiers temporaires acceptés" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr)[-200:]}"))

        tmp = {a: R / hashlib.sha256(a.encode()).hexdigest()[:12] for a in ("compta", "voisin", "ouvert")}
        s = json.loads((i / "agents/compta/.claude/settings.json").read_text())
        dire(s.get("env", {}).get("CLAUDE_CODE_TMPDIR") == str(tmp["compta"]), "Claude : CLAUDE_CODE_TMPDIR = son dossier (env des réglages)")
        dire(tmp["compta"] != tmp["voisin"], "deux agents : deux dossiers distincts")
        dr = s["sandbox"]["filesystem"].get("denyRead", [])
        dire(COMMUN in dr and str(tmp["voisin"]) in dr and str(tmp["ouvert"]) in dr, "bac à sable : le commun et les dossiers des autres refusés en lecture")
        if R.is_relative_to(COMMUN): print("NON JOUÉ son propre dossier hors de tout refus : la racine d'essai est elle-même sous le commun (bac à sable)")
        else: dire(not any(tmp["compta"].is_relative_to(x) for x in dr), "bac à sable : son propre dossier n'est sous aucun refus")
        deny = s["permissions"]["deny"]
        dire(all(f"{o}(/{p}/**)" in deny for o in ("Read", "Edit") for p in (COMMUN, str(tmp["voisin"]))),
             "outils Read/Edit : le commun et les autres refusés (chemin absolu « // »)")
        relais = "/tmp/claude-http-0123456789abcdef.sock"
        dire(not any(relais == x or relais.startswith(x.rstrip("/") + "/") for x in dr) and "/tmp" not in dr,
             "le relais réseau du bac à sable (/tmp/claude-http-*.sock) n'est couvert par aucun refus")
        mode = lambda p: stat.S_IMODE(os.stat(p).st_mode)
        dire(tmp["compta"].is_dir() and mode(tmp["compta"]) == 0o700 and mode(R) & 0o077 == 0, "dossier de l'agent créé en 700, racine fermée aux autres comptes")
        dire(len(str(tmp["compta"] / f"claude-{UID}").encode()) <= 44, "chemin final de Claude ≤ 44 octets (sinon repli silencieux)")

        o = json.loads((i / "agents/ouvert/.claude/settings.json").read_text())
        dire("CLAUDE_CODE_TMPDIR" not in o.get("env", {}) and not tmp["ouvert"].exists(), "mur ouvert : rien d'ajouté, aucun dossier créé")

        cx = (i / ".codex/config.toml").read_text().split("[permissions.compta.filesystem]")[1].split("[permissions.")[0]
        dire(f'"{tmp["compta"]}" = "write"' in cx and f'"{tmp["voisin"]}" = "none"' in cx, "Codex : le sien en écriture, celui d'un autre « none »")
        dire((f'"{COMMUN}" = "none"' in cx) == Path(COMMUN).is_dir(), "Codex : le commun de Claude « none » s'il existe (Codex refuse un chemin absent)")
        code = f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');print(g['env_codex']('compta').get('TMPDIR'),g['env_codex']('ouvert').get('TMPDIR')==g['os'].environ.get('TMPDIR'))"
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
        dire(r.stdout.split() == [str(tmp["compta"]), "True"], "Codex : TMPDIR = son dossier (strict), inchangé (mur ouvert)")

        refuse, msg = exiger(i, env, "compta")
        dire(not refuse, "lancement accepté sur un dossier sûr" + ("" if not refuse else f" — {msg[-160:]}"))
        long = R / ("x" * 30)
        refuse, msg = exiger(i, {**env, "BERGER_TMP_AGENTS": str(long)}, "compta")
        dire(refuse and "octets" in msg and not long.exists(), "chemin > 44 octets : lancement REFUSÉ, rien créé (jamais de repli sur le commun)")
        r = berger(i, {**env, "BERGER_TMP_AGENTS": str(long)}, "regenerer")
        dire("dossier temporaire refusé" in r.stdout, "regenerer le dit (⚠) sans s'arrêter")
        os.chmod(tmp["compta"], 0o755)
        refuse, msg = exiger(i, env, "compta")
        dire(refuse and "700" in msg, "dossier aux droits ouverts : lancement REFUSÉ")
        os.chmod(tmp["compta"], 0o700); os.rmdir(tmp["compta"]); os.symlink(m, tmp["compta"])
        refuse, msg = exiger(i, env, "compta")
        dire(refuse and "lien" in msg, "dossier remplacé par un lien : lancement REFUSÉ")
        os.unlink(tmp["compta"])

        # Lancement (correctif tmp-lancement, 14/10) : Claude choisit son temporaire sur l'environnement du PROCESSUS ;
        # l'env des réglages du projet / locaux / --settings est écarté pour ce choix (lu dans son code, 2.1.289). Chaque
        # chemin qui lance le moteur doit donc le porter : lancer (exec), demander (claude -p), demarrer_agent (Herdr).
        lan = lancements(i, env)
        for a in ("compta", "ouvert"):
            attendu = str(tmp[a]) if a == "compta" else None
            for quoi, mo in (("lancer", "claude"), ("lancer", "codex"), ("demander", "claude")):
                dire(lan[a][quoi][mo].get("CLAUDE_CODE_TMPDIR") == attendu,
                     f"{quoi} {mo} ({a}) : CLAUDE_CODE_TMPDIR {'= son dossier' if attendu else 'non posé (mur ouvert)'}"
                     f" dans l'environnement du processus — vu : {lan[a][quoi][mo].get('CLAUDE_CODE_TMPDIR')}")
            for mo in ("claude", "codex"):
                vu = lan[a]["herdr"][mo]
                dire(vu.get("CLAUDE_CODE_TMPDIR") == attendu,
                     f"Herdr {mo} ({a}, relance/reprise/espace/mission) : CLAUDE_CODE_TMPDIR "
                     f"{'exporté = son dossier' if attendu else 'non exporté (mur ouvert)'} — vu : {vu.get('CLAUDE_CODE_TMPDIR')}")
            dire(lan[a]["herdr"]["codex"].get("TMPDIR") == attendu,
                 f"Herdr codex ({a}) : TMPDIR {'exporté = son dossier' if attendu else 'non exporté (mur ouvert)'}"
                 f" — vu : {lan[a]['herdr']['codex'].get('TMPDIR')}")
        dire(lan["compta"]["lancer"]["codex"].get("TMPDIR") == str(tmp["compta"]), "lancer codex : TMPDIR = son dossier (inchangé)")
        os.rmdir(tmp["compta"]); os.symlink(m, tmp["compta"])
        lan = lancements(i, env, ("compta",))
        dire(lan["compta"]["herdr"]["claude"] == "REFUSÉ", "Herdr : dossier remplacé par un lien → démarrage REFUSÉ (comme lancer)")
        os.unlink(tmp["compta"])
finally:
    import shutil; shutil.rmtree(R, ignore_errors=True)

sys.exit(1 if ko else 0)
