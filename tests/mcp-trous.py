#!/usr/bin/env python3
"""Tests de mcp-trous (17/10/2026, docs/plans/2026-10-17-mcp-trous-spec.md) — sans modèle, installation JETABLE :
GÉNÉRATION — tout strict Claude : --strict-mcp-config et ENABLE_CLAUDEAI_MCP_SERVERS=false à chaque lancement (lancer,
demander, panneau Herdr, berger args) ; tout strict Codex : features apps/plugins/remote_plugin/skill_mcp_dependency_install/
tool_suggest = false dans son profil ; refus d'écriture de .mcp.json, .claude/settings*.json, .codex/ (Claude : refus Edit/Write
et denyWrite ; Codex : « read »), dossier de l'agent ET dossier de travail ; mur ouvert inchangé.
ADMISSION — verdict par moteur et version ; non admis : bascule sur l'autre moteur admis (lancer, demander, panneau), rouge
dans la Synthèse, une notification par version ; aucun moteur admis : refus (message clair) ; version jamais vue : contrat
joué avant le lancement ; mur ouvert : hors sujet.
La preuve dans les vrais moteurs est faite par tests/contrat-moteur.sh (tests/tout.sh).
Usage : python3 tests/mcp-trous.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, runpy, shlex, subprocess, sys, tempfile, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
FEATURES = ("apps", "plugins", "remote_plugin", "skill_mcp_dependency_install", "tool_suggest")
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"; ext = m / "projet-existant"; ext.mkdir()
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    for a, mur, moteur, plus in (("compta", "strict", "claude", "panneaux = claude"), ("essai-codex", "strict", "codex", "panneaux = codex"),
                                 ("dehors", "strict", "claude", f"panneaux = claude\ndossier = {ext}"),
                                 ("ouvert", "ouvert", "claude", "panneaux = claude, codex")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = {moteur}\n{plus}\nmur = {mur}\nheures = aucune\noutils =\n")
    racine = m / "bt"          # le dossier temporaire n'est pas l'objet du test (tests/tmp-par-agent.py) : exiger_tmp neutralisé plus bas
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": "/bin/false", "BERGER_TMP_AGENTS": str(racine)}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0, "regenerer réussit" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr).strip()[-200:]}"))

    # ── GÉNÉRATION ──
    os.environ.update({k: env[k] for k in ("HOME", "BERGER_DIR", "BERGER_HERDR", "BERGER_TMP_AGENTS")})
    sys.argv = ["berger"]; g = runpy.run_path(str(i / "bin/berger"), run_name="essai")["lancer"].__globals__
    fichiers = lambda d: [d / ".mcp.json", d / ".claude/settings.json", d / ".claude/settings.local.json", d / ".codex"]
    for a in ("compta", "dehors"):
        args = g["moteurs"].MODULES["claude"].args(a)
        dire("--strict-mcp-config" in args and "--mcp-config" not in args, f"{a} (strict Claude) : --strict-mcp-config, aucun --mcp-config")
        dire(g["env_tmp"](a, "claude").get("ENABLE_CLAUDEAI_MCP_SERVERS") == "false", f"{a} : ENABLE_CLAUDEAI_MCP_SERVERS=false avec CLAUDE_CODE_TMPDIR (env_tmp)")
    dire("--strict-mcp-config" not in g["moteurs"].MODULES["claude"].args("ouvert") and "ENABLE_CLAUDEAI_MCP_SERVERS" not in g["env_tmp"]("ouvert", "claude"),
         "mur ouvert : ni --strict-mcp-config ni variable (hors sujet)")
    rq = json.loads((i / "agents/dehors/.reglages-claude.json").read_text())
    dire("--settings" in g["moteurs"].MODULES["claude"].args("dehors") and "Edit(" + str(ext / ".mcp.json").replace(str(m), "~") + ")" in rq["permissions"]["deny"],
         "strict dans un dossier existant : réglages passés par --settings, avec le refus sur SON dossier de travail")

    for a, d in (("compta", [i / "agents/compta"]), ("dehors", [i / "agents/dehors", ext])):
        s = json.loads(((i / "agents" / a / ".claude/settings.json") if a == "compta" else (i / "agents/dehors/.reglages-claude.json")).read_text())
        dw, deny = s["sandbox"]["filesystem"]["denyWrite"], s["permissions"]["deny"]
        voulus = [f for x in d for f in fichiers(x)]
        rel = lambda f: str(f).replace(str(m), "~") + ("/**" if f.name == ".codex" else "")
        dire(all(str(f) in dw for f in voulus), f"{a} : Claude, denyWrite sur .mcp.json, .claude/settings*.json, .codex ({len(voulus)} chemins)")
        dire(all(f"{o}({rel(f)})" in deny for f in voulus for o in ("Edit", "Write")), f"{a} : Claude, refus Edit et Write des mêmes chemins (.codex/**)")
    o = json.loads((i / "agents/ouvert/.claude/settings.json").read_text())
    dire("sandbox" not in o and "deny" not in o.get("permissions", {}), "mur ouvert : réglages Claude inchangés")

    cx = (i / ".codex/config.toml").read_text()
    for a in ("compta", "essai-codex"):
        bloc = cx.split(f"[permissions.{a}.filesystem]")[1].split("[permissions.")[0].split("[projects.")[0]
        dire(all(f'"{f}" = "read"' in bloc for f in fichiers(i / "agents" / a)), f"{a} : Codex, .mcp.json, .claude/settings*.json, .codex en « read »")
        p = tomllib.loads((i / ".codex" / f"{a}.config.toml").read_text())
        dire(all(p.get("features", {}).get(x) is False for x in FEATURES), f"{a} (strict) : profil Codex, features {', '.join(FEATURES)} = false")
    p = tomllib.loads((i / ".codex/ouvert.config.toml").read_text())
    dire("features" not in p, "mur ouvert : profil Codex sans features (hors sujet)")
    # codex-trous (18/10) : Codex lit le .codex/config.toml d'un dossier trusted, serveurs MCP compris — « untrusted » explicite
    # sur ses dossiers le coupe, même sous ~/berger trusted, sans ramener « Trust this folder? » (mesuré, 0.163.0)
    pj = tomllib.loads(cx).get("projects", {}); confiance = lambda d: pj.get(str(d), {}).get("trust_level")
    for a, d in (("compta", [i / "agents/compta"]), ("essai-codex", [i / "agents/essai-codex"]), ("dehors", [i / "agents/dehors", ext])):
        dire(all(confiance(x) == "untrusted" for x in d), f"{a} (strict) : Codex, ses dossiers en trust_level « untrusted » (pas de config de projet)")
    dire(confiance(i / "agents/ouvert") == "trusted", "mur ouvert : dossier Codex toujours « trusted » (hors sujet)")
    dire(confiance(i) == "trusted", "racine de Berger toujours « trusted » : pas de question « Trust this folder? »")

    # chaque lancement porte la variable : lancer (exec), demander (claude -p), panneau Herdr (export), berger args
    vu = {}
    class Exec(Exception): pass
    def execvpe(f, args, e): vu.update(env=dict(e), args=list(args)); raise Exec()
    vrai_run = subprocess.run                  # g["subprocess"] EST ce module : le remplacer remplace aussi le nôtre
    def run(args, **k):
        if "--version" in args: return subprocess.CompletedProcess(args, 0, "", "")
        vu.update(env=dict(k.get("env") or os.environ), args=list(args))
        if "-o" in args: Path(args[args.index("-o") + 1]).write_text("réponse")      # codex exec écrit sa réponse dans -o
        return subprocess.CompletedProcess(args, 0, "réponse", "")
    def herdr(*args):
        if args[:2] == ("pane", "run") and " export " in args[3]:
            vu["env"] = dict(x.split("=", 1) for x in shlex.split(args[3].split(" export ", 1)[1]) if "=" in x)
        if args[:2] == ("agent", "start"): vu["start"] = list(args)
        if args[:2] == ("pane", "run"): vu.setdefault("runs", []).append(args[3])
        return {}
    notes = []
    g["os"].execvpe = execvpe; g["herdr"] = herdr; g["time"].sleep = lambda s: None; g["bac_a_sable_ok"] = lambda: True
    g["exiger_tmp"] = g["preparer_tmp"] = lambda a: None
    g["notifier"] = g["moteurs"].notifier = lambda titre, texte, urgent=False: notes.append(texte)   # (lot 2 : moteurs/ a SA copie branchée du cœur)
    verdicts = {}
    g["moteurs"].version_moteur = lambda mo: {"claude": "2.1.300", "codex": "0.162.1"}[mo]
    contrats = g["moteurs"].CONTRATS
    def verdict(mo, v, ok, raison="(6) socket AF_UNIX depuis son Bash : permis"):
        contrats.mkdir(parents=True, exist_ok=True)
        (contrats / f"{mo}-{v}.txt").write_text(("ADMIS" if ok else "NON ADMIS") + f"\nmoteur : {mo} {v}\n" + ("" if ok else f"✗ {raison}\n"))
        (contrats / f"{mo}-{v}.notifie").unlink(missing_ok=True)
    verdict("claude", "2.1.300", True); verdict("codex", "0.162.1", True)
    g["subprocess"].run = run
    try: g["lancer"]("compta", "claude")
    except Exec: pass
    dire(vu.get("env", {}).get("ENABLE_CLAUDEAI_MCP_SERVERS") == "false" and "--strict-mcp-config" in vu.get("args", []), "lancer : variable et drapeau dans le lancement réel")
    vu.clear(); g["demander"]("compta", "q", "claude")
    dire(vu.get("env", {}).get("ENABLE_CLAUDEAI_MCP_SERVERS") == "false" and "--strict-mcp-config" in vu.get("args", []), "demander (claude -p) : variable et drapeau")
    vu.clear(); g["demarrer_agent"]("compta", "claude", "p1")
    dire(vu.get("env", {}).get("ENABLE_CLAUDEAI_MCP_SERVERS") == "false" and "--strict-mcp-config" in vu.get("start", []), "panneau Herdr : variable exportée, drapeau passé")
    g["subprocess"].run = vrai_run
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "args", "compta", "claude", "--contrat"], env=env, capture_output=True, text=True, timeout=60)
    try: e = json.loads(r.stdout)["env"]
    except (ValueError, KeyError): e = {}
    dire(e.get("ENABLE_CLAUDEAI_MCP_SERVERS") == "false" and e.get("CLAUDE_CODE_TMPDIR"), "berger args (autre accès, ex. pont) : la variable et le temporaire dans son env")

    # ── ADMISSION ──
    dire(g["moteurs"].verdict_moteur("claude")[0] == "admis" and g["moteurs"].choisir_moteur("compta", "claude") == ("claude", None), "moteur admis : lancé tel quel")
    verdict("claude", "2.1.300", False)
    mo, pb = g["moteurs"].choisir_moteur("compta", "claude")
    dire(mo == "codex" and "non admis" in pb and "AF_UNIX" in pb, "claude non admis, codex admis : BASCULE sur codex, raison dite")
    dire(any("bascule sur codex" in l for l in (i / "agents/compta/memory").glob("*.md").__next__().read_text().splitlines()), "bascule notée au journal de l'agent")
    dire(len(notes) == 1 and "claude 2.1.300" in notes[0], "une notification (urgente) pour la version non admise")
    g["moteurs"].choisir_moteur("compta", "claude"); g["moteurs"].choisir_moteur("essai-codex", "claude")
    dire(len(notes) == 1, "pas de nouvelle notification pour la même version (une par version, pas une par lancement)")
    g["subprocess"].run = run; vu.clear()
    texte, utilise, echecs = g["demander"]("compta", "q", "claude")
    dire(utilise == "codex" and vu.get("args", [None])[0] == "codex" and any("non admis" in x for x in echecs), "demander (réveils, tâches) : bascule sur codex, échec du premier nommé")
    vu.clear()
    try: g["lancer"]("compta", "claude")
    except Exec: pass
    dire(vu.get("args", [None])[0] == "codex", "lancer : bascule sur codex")
    vu.clear(); r = g["demarrer_agent"]("compta", "claude", "p1", "conv-1")
    dire(r == "codex" and "compta-codex" in vu.get("start", []) and "--resume" not in vu.get("start", []), "panneau : démarré sous codex (nommé compta-codex, pas de reprise d'une conversation Claude)")
    dire(g["moteurs"].choisir_moteur("ouvert", "claude") == ("claude", None), "mur ouvert : hors sujet, jamais basculé")
    al = g["alertes_synthese"]()
    dire(any(c == "rouge" and "claude 2.1.300 non admis" in x for c, _, x in al), "Synthèse : « claude non admis » en ROUGE")

    verdict("codex", "0.162.1", False, "(1) apps vues (app/list) : ['x']")
    dire(g["moteurs"].choisir_moteur("compta", "claude")[0] is None and "aucun moteur admis" in g["moteurs"].choisir_moteur("compta", "claude")[1], "aucun moteur admis : refus")
    vu.clear()
    try: g["lancer"]("compta", "claude"); sortie = ""
    except SystemExit as x: sortie = str(x)
    except Exec: sortie = "LANCÉ"
    dire("NON lancé" in sortie and "aucun moteur admis" in sortie, "lancer : refusé, message clair")
    texte, utilise, echecs = g["demander"]("compta", "q", "claude")
    dire(utilise is None and len([x for x in echecs if "non admis" in x]) == 2, "demander : refusé, les deux raisons dites")
    vu.clear(); r = g["demarrer_agent"]("compta", "claude", "p1")
    dire(r is None and "start" not in vu and any("NON lancé" in x for x in vu.get("runs", [])), "panneau : rien lancé, le panneau le dit")
    g["subprocess"].run = vrai_run
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "args", "compta", "claude"], env={**env, "PATH": ""}, capture_output=True, text=True, timeout=60)
    dire(r.returncode != 0 and "non admis" in r.stderr, "berger args : moteur non admis refusé (sans --contrat)")
    dire(g["moteurs"].choisir_moteur("ouvert", "codex") == ("codex", None), "mur ouvert : toujours lancé (hors sujet)")

    # version jamais vue : contrat joué AVANT le lancement
    for f in contrats.glob("*"): f.unlink()
    joues = []
    g["moteurs"].jouer_contrat = lambda mo, a: (joues.append((mo, a)), verdict(mo, g["moteurs"].version_moteur(mo), True))
    dire(g["moteurs"].moteur_admis("claude", "compta") is None and joues == [("claude", "compta")], "version jamais vue : contrat joué avant le lancement, puis admis")
    dire(g["moteurs"].moteur_admis("claude", "compta") is None and len(joues) == 1, "version déjà vue : contrat pas rejoué")
    g["moteurs"].jouer_contrat = lambda mo, a: None
    pb = g["moteurs"].moteur_admis("codex", "essai-codex")
    dire(pb and "contrat impossible" in pb, "contrat impossible à jouer : NON admis (jamais admis par défaut)")
    al = g["moteurs"].alertes_moteurs()
    dire(any(c == "jaune" and "codex" in x for c, _, x in al), "Synthèse : contrat jamais joué en JAUNE")
    g["moteurs"].version_moteur = lambda mo: None
    dire(g["moteurs"].verdict_moteur("claude")[0] == "non admis", "moteur introuvable ou version illisible : non admis")
    dire(not g["moteurs"].alertes_moteurs(), "Synthèse : un moteur absent de la machine n'y est pas (ni rouge ni jaune)")

    # ── NETTOYAGE DU CONTRAT : jamais de canari laissé chez l'agent (contrat coupé, arrêt net, SIGTERM) ──
    C = runpy.run_path(str(SRC / "tests/contrat-moteur.py"), run_name="contrat")
    ag = m / "agent-essai"; ag.mkdir(); (ag / ".mcp.json").write_text("le mien")
    jr = m / "contrats-essai/.pose.json"
    def poser_tout(pz):
        pz.poser(ag / ".mcp.json", C["MARQUE"]); pz.poser(ag / ".claude/settings.local.json", C["MARQUE"])
        pz.poser(ag / ".codex/config.toml", "# " + C["MARQUE"])
    poser_tout(C["Pose"](jr))                                                # arrêt net : retirer() ne tourne jamais
    dire(jr.is_file() and (ag / ".mcp.json.avant-contrat").read_text() == "le mien", "pose : journal écrit, fichier existant mis de côté SUR PLACE (jamais recopié ailleurs)")
    (ag / ".codex/config.toml").write_text("écrit après coup, sans marque")
    n = C["Pose"](jr).reprendre()                                            # le contrat suivant répare
    dire(n == 3 and (ag / ".mcp.json").read_text() == "le mien" and not (ag / ".mcp.json.avant-contrat").exists()
         and not (ag / ".claude").exists() and not jr.exists(), "contrat coupé : le suivant remet tout comme avant (fichier d'origine, dossiers créés retirés, journal)")
    dire((ag / ".codex/config.toml").read_text() == "écrit après coup, sans marque", "reprise : un fichier sans la marque du contrat n'est jamais retiré")
    (ag / ".codex/config.toml").unlink(); (ag / ".codex").rmdir()
    prog = ("import os, runpy, signal, sys\nC = runpy.run_path(sys.argv[1], run_name='contrat')\nC['armer_sigterm']()\n"
            "from pathlib import Path\np = C['Pose'](Path(sys.argv[3])); ag = Path(sys.argv[2])\n"
            "try:\n    p.poser(ag / '.mcp.json', C['MARQUE']); p.poser(ag / '.codex/config.toml', C['MARQUE'])\n"
            "    os.kill(os.getpid(), signal.SIGTERM); import time; time.sleep(30)\nfinally:\n    p.retirer()\n")
    r = subprocess.run([sys.executable, "-c", prog, str(SRC / "tests/contrat-moteur.py"), str(ag), str(jr)], capture_output=True, text=True, timeout=60)
    dire(r.returncode != 0 and "SIGTERM" in r.stderr and (ag / ".mcp.json").read_text() == "le mien" and not (ag / ".codex").exists() and not jr.exists(),
         "SIGTERM pendant le contrat : fichiers posés retirés avant de finir")
    (i / "tests").mkdir(exist_ok=True)
    (i / "tests/contrat-moteur.sh").write_text(f"trap 'echo terme > {m}/terme-recu; exit 1' TERM\nsleep 60 & wait\n")
    # version relue après une mise à jour par mise : le raccourci (shims/claude → mise) et mise ne changent pas, seul le
    # chemin rendu par « mise which claude » change (installs/claude/<version>/claude)
    mi = m / "mise-essai"; (mi / "shims").mkdir(parents=True); (mi / "cible").write_text(str(mi / "v1/claude"))
    for n, ver in (("v1", "1.0.0"), ("v2", "2.0.0")):
        (mi / n).mkdir(); (mi / n / "claude").write_text(f"#!/bin/sh\necho '{ver} (Claude Code)'\n"); (mi / n / "claude").chmod(0o755)
    (mi / "mise").write_text(f'#!/bin/sh\n[ "$1" = which ] && cat {mi / "cible"}\n'); (mi / "mise").chmod(0o755)
    (mi / "shims/claude").symlink_to(mi / "mise")
    V = runpy.run_path(str(i / "bin/berger"), run_name="essai")["moteurs"].__dict__
    chemin = os.environ["PATH"]; os.environ["PATH"] = f"{mi / 'shims'}:{chemin}"
    try:
        v1 = V["version_moteur"]("claude"); (mi / "cible").write_text(str(mi / "v2/claude")); v2 = V["version_moteur"]("claude")
    finally: os.environ["PATH"] = chemin
    dire(v1 == "1.0.0" and v2 == "2.0.0", f"mise met claude à jour (même raccourci, même mise) : version relue dans le même processus ({v1} → {v2})")
    # raccourci que mise ne résout pas (« not currently active », code 1) : introuvable, jamais mise lui-même (vécu le 18/10 :
    # le courtier lançait « mise sonde-mcp.py serveur », la sonde ne démarrait jamais)
    (mi / "mise").write_text('#!/bin/sh\necho "python3 is a mise bin however it is not currently active" >&2; exit 1\n')
    (mi / "shims/python3").symlink_to(mi / "mise")
    dire(V["executable_moteur"](str(mi / "shims/python3")) is None, "raccourci mise non résolu : introuvable (None), jamais /…/mise")
    (mi / "mise").write_text(f'#!/bin/sh\n[ "$1" = which ] && echo {mi / "mise"}\n')
    dire(V["executable_moteur"](str(mi / "shims/python3")) is None, "« mise which » qui rend mise lui-même : introuvable (None)")
    J = runpy.run_path(str(i / "bin/berger"), run_name="essai")["moteurs"].__dict__   # le VRAI subprocess (g a des faux)
    J["version_moteur"] = lambda mo: "9.9.9"; J["DELAI_CONTRAT"], J["GRACE_CONTRAT"] = 1, 10
    t0 = __import__("time").monotonic(); J["jouer_contrat"]("claude", "compta")
    dire((m / "terme-recu").is_file() and __import__("time").monotonic() - t0 < 10, "jouer_contrat au délai : SIGTERM d'abord (le contrat se nettoie), pas un SIGKILL d'emblée")

sys.exit(1 if ko else 0)
