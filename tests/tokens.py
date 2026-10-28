#!/usr/bin/env python3
"""Tests du suivi des tokens — sans modèle, sans Herdr : une installation JETABLE avec deux agents sur deux moteurs
(Claude et Codex) et de faux journaux au format de chaque moteur. Vérifie : attribution à l'agent par son dossier, les
deux moteurs comptés, doublon compté une fois, lecture qui avance (un 2e passage n'ajoute rien), quota par moteur (barre
d'état Claude, journaux Codex), « non mesuré » sans donnée, barre d'état qui relève le quota, réglage statusLine posé.
Usage : python3 tests/tokens.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def iso(dt): return dt.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    for a, nom, moteur in (("vigie", "Vigie", "claude"), ("scribe", "Scribe", "codex")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {nom}\nicone = ●\nmoteur = {moteur}\npanneaux = {moteur}\nheures = aucune\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    maint = datetime.datetime.now(datetime.timezone.utc)

    # Claude : dossier de projet = dossier de travail en tirets ; une réponse écrite DEUX fois (même id) ; une autre agent inconnu
    pj = m / ".claude/projects" / re.sub(r"[^A-Za-z0-9-]", "-", str(i / "agents/vigie")); pj.mkdir(parents=True)
    rep = lambda mid, n, quand: json.dumps({"timestamp": iso(quand), "message": {"id": mid, "model": "claude-sonnet-5-5",
                                           "usage": {"input_tokens": 10, "cache_read_input_tokens": n, "output_tokens": 200}}})
    (pj / "s1.jsonl").write_text("\n".join([rep("msg_1", 1000, maint), rep("msg_1", 1000, maint), rep("msg_2", 5000, maint)]) + "\n")
    autre = m / ".claude/projects/-tmp-ailleurs"; autre.mkdir(parents=True)
    (autre / "x.jsonl").write_text(rep("msg_9", 99999, maint) + "\n")
    # Codex : session_meta (cwd) puis token_count (dernier tour + limites d'usage)
    cx = i / ".codex/sessions/2026/10/06"; cx.mkdir(parents=True)
    remise = (maint + datetime.timedelta(hours=2)).timestamp()
    (cx / "rollout-1.jsonl").write_text("\n".join(json.dumps(x) for x in (
        {"timestamp": iso(maint), "type": "session_meta", "payload": {"cwd": str(i / "agents/scribe")}},
        {"timestamp": iso(maint), "type": "turn_context", "payload": {"model": "gpt-6-luna"}},
        {"timestamp": iso(maint), "type": "event_msg", "payload": {"type": "token_count",
         "info": {"last_token_usage": {"input_tokens": 3000, "output_tokens": 40, "reasoning_output_tokens": 60}},
         "rate_limits": {"primary": {"used_percent": 42, "window_minutes": 300, "resets_at": remise},
                         "secondary": {"used_percent": 85, "window_minutes": 10080, "resets_in_seconds": 3600}}}})) + "\n")

    def vue():
        code = f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');print('\\n'.join(g['VUES']['tokens'].vue_tokens(160, 200)))"
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
        return r, re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", r.stdout)

    r, v = vue()
    dire(r.returncode == 0 and "TOKENS" in v, "la vue se construit" + ("" if r.returncode == 0 else f" — {r.stderr.strip()[-200:]}"))
    lignes = {l.split()[1]: l for l in v.splitlines() if l.strip().startswith("●")}
    dire("Vigie" in lignes and "claude" in lignes.get("Vigie", ""), "agent Claude reconnu par son dossier de projet")
    dire("Scribe" in lignes and "codex" in lignes.get("Scribe", ""), "agent Codex reconnu par le dossier de sa session")
    dire("6 k / 400 " in lignes.get("Vigie", ""), f"Claude : doublon compté UNE fois (6 k lus / 400 écrits ; compté deux fois = 7 k) — {lignes.get('Vigie', '').strip()[:90]}")
    dire("3 k / 100 " in lignes.get("Scribe", ""), f"Codex : entrée 3 k, écrits = sortie + raisonnement (100) — {lignes.get('Scribe', '').strip()[:90]}")
    dire("99999" not in v and "100 k" not in v, "journal d'un dossier hors agents : ignoré")
    q = {l.split()[0]: l for l in v.splitlines() if l.strip().split()[:1] and l.strip().split()[0] in ("claude", "codex")}
    dire("non mesuré" in q.get("claude", ""), "quota Claude : « non mesuré » sans barre d'état (passerelle muette)")
    dire("5 h 42 %" in q.get("codex", "") and "7 j" in q.get("codex", "") and "85 %" in q.get("codex", ""), f"quota Codex lu dans ses journaux — {q.get('codex', '').strip()[:90]}")
    r2, v2 = vue()
    l2 = {l.split()[1]: l for l in v2.splitlines() if l.strip().startswith("●")}
    dire(l2.get("Vigie") == lignes.get("Vigie") and l2.get("Scribe") == lignes.get("Scribe"), "2e passage : rien compté deux fois (lecture qui avance)")

    # barre d'état : relève le quota de l'abonnement Claude → le panneau l'affiche
    entree = {"model": {"display_name": "Sonnet 5.5"}, "rate_limits": {"five_hour": {"used_percentage": 3, "resets_at": remise},
                                                                         "seven_day": {"used_percentage": 62, "resets_at": remise + 86400}}}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "statusline", "vigie"], input=json.dumps(entree), env=env,
                       capture_output=True, text=True, timeout=30)
    dire(r.returncode == 0 and "Sonnet 5.5" in r.stdout and "5 h 3 %" in r.stdout and "7 j 62 %" in r.stdout, f"barre d'état affichée — {r.stdout.strip()}")
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "statusline", "vigie"], input="pas du json", env=env, capture_output=True, text=True, timeout=30)
    dire(r.returncode == 0 and r.stdout.strip() == "Claude", "barre d'état : entrée illisible → sortie minimale, jamais d'erreur")
    _, v3 = vue()
    q3 = next((l for l in v3.splitlines() if l.strip().startswith("claude ")), "")
    dire("5 h 3 %" in q3 and "7 j 62 %" in q3, f"quota Claude relevé par la barre d'état puis affiché — {q3.strip()[:90]}")

    # regenerer pose le réglage statusLine dans les réglages Claude de l'agent
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=60)
    try: sl = json.loads((i / "agents/vigie/.claude/settings.json").read_text()).get("statusLine", {})
    except (OSError, ValueError): sl = {}
    dire(sl.get("type") == "command" and sl.get("command", "").endswith("berger statusline vigie"), f"regenerer : statusLine posé ({sl or r.stderr.strip()[-120:]})")

    # pied de page Claude : badge coloré (icône + NOM), « quota non transmis » sans limites, contexte ; couleur réglable
    sl = lambda a, entree: subprocess.run([sys.executable, str(i / "bin/berger"), "statusline", a], input=json.dumps(entree),
                                          env=env, capture_output=True, text=True, timeout=30).stdout
    o = sl("vigie", {"model": {"display_name": "Sonnet 5.5"}, "context_window": {"used_percentage": 8}})
    dire("\x1b[1;" in o and "● VIGIE" in o, f"pied de page Claude : badge coloré « ● VIGIE » — {o.strip()!r}")
    dire("quota non transmis" in o and "contexte 8 %" in o, "pied de page Claude : « quota non transmis » sans limites, contexte affiché")
    conf_v = i / "agents/vigie/agent.conf"; conf_v.write_text(conf_v.read_text() + "couleur = 41;97\n")
    dire("\x1b[1;41;97m" in sl("vigie", {}) and "\x1b[1;41;97m" not in o,
         "pied de page Claude : couleur du badge réglable (couleur = 41;97, différente de celle par défaut)")
    # pied de page Codex : réglage officiel [tui] status_line, éléments intégrés (pas de script possible)
    import tomllib
    try: tui = tomllib.loads((i / ".codex/config.toml").read_text()).get("tui", {})
    except (OSError, ValueError) as e: tui = {"erreur": str(e)}
    dire(tui.get("status_line") == ["model-with-reasoning", "current-dir", "context-used", "used-tokens", "five-hour-limit", "weekly-limit"],
         f"pied de page Codex : [tui] status_line posé par regenerer (obtenu {tui})")

sys.exit(1 if ko else 0)
