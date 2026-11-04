#!/usr/bin/env python3
"""Accord du mode bypass (accord-bypass, 03/11/2026). Tout agent Claude de Berger est lancé avec --dangerously-skip-permissions :
Claude Code 2.1.316 a demandé, au redémarrage, « Bypass Permissions mode — Yes, I accept », et les agents sont restés arrêtés
en silence. Berger déclare l'accord (skipDangerousModePermissionPrompt) dans la seule portée mesurée où Claude le lit :
.claude/settings.local.json (agent dans son dossier) ou le fichier passé par --settings (agent dans un dossier existant).
JAMAIS dans .claude/settings.json (projet : ignoré, mesuré), ni chez Codex, ni dans le dossier existant de l'agent ;
permissions, refus et bac à sable inchangés. Sans moteur ni modèle : on lit ce que Berger génère et les arguments de lancement.
Usage : python3 tests/accord-bypass.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, runpy, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
CLE = "skipDangerousModePermissionPrompt"
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def lire_json(f):
    try: return json.loads(Path(f).read_text())
    except (OSError, ValueError): return None


with tempfile.TemporaryDirectory() as td:
    m = Path(td); i = m / "berger"; ext = m / "role-existant"; ext.mkdir()
    _produit.copier(SRC, i, ("bin", "courtier", "commun")); _produit.admettre_moteurs(i)
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    for a, plus in (("strict-ici", ""), ("strict-ailleurs", f"dossier = {ext}\n"), ("ouvert-ici", "mur = ouvert\n"),
                    ("ouvert-ailleurs", f"mur = ouvert\ndossier = {ext}\n"), ("essai-codex", "moteur = codex\n")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        moteur = "" if "moteur" in plus else "moteur = claude\n"
        (d / "agent.conf").write_text(f"nom = {a}\n{moteur}{plus}heures = aucune\noutils =\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": "/bin/false", "BERGER_TMP_AGENTS": str(m / "bt")}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0, "regenerer réussit" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr).strip()[-200:]}"))

    # Arguments de lancement lus directement dans le moteur (sans « berger args » : le bac à sable n'est pas l'objet du test)
    os.environ.update({k: env[k] for k in ("HOME", "BERGER_DIR", "BERGER_HERDR", "BERGER_TMP_AGENTS")})
    sys.argv = ["berger"]; g = runpy.run_path(str(i / "bin/berger"), run_name="essai")["lancer"].__globals__
    claude = g["moteurs"].MODULES["claude"]
    dire(g["ACCORD_BYPASS"] == {CLE: True}, "l'accord est une seule clé, mesurée : skipDangerousModePermissionPrompt = true")

    def settings_passe(args):
        return Path(args[args.index("--settings") + 1]) if "--settings" in args else None

    # ── strict dans son dossier : --setting-sources project,local → settings.local.json (le projet est ignoré pour cette clé) ──
    d = i / "agents/strict-ici"; x = claude.args("strict-ici")
    dire("--dangerously-skip-permissions" in x and x[:2] == ["--setting-sources", "project,local"], "strict ici : lancé en bypass, réglages projet et local lus")
    dire(lire_json(d / ".claude/settings.local.json") == {CLE: True}, "strict ici : l'accord dans .claude/settings.local.json, et rien d'autre")
    s = lire_json(d / ".claude/settings.json")
    dire(s is not None and CLE not in s, "strict ici : pas de clé dans .claude/settings.json (portée projet : ignorée par Claude)")
    dire(s["permissions"]["defaultMode"] == "bypassPermissions" and s["sandbox"]["enabled"] and s["permissions"]["deny"]
         and s["sandbox"]["network"].get("deniedDomains") == ["*"], "strict ici : permissions, refus, bac à sable et réseau inchangés")
    dire(str(d / ".claude/settings.local.json") in s["sandbox"]["filesystem"]["denyWrite"], "strict ici : settings.local.json reste protégé (denyWrite)")
    dire(settings_passe(x) is None or CLE not in (lire_json(settings_passe(x)) or {}), "strict ici : rien en double par --settings")

    # ── strict dans un dossier existant : l'accord dans .reglages-claude.json (--settings), rien chez lui ──
    x = claude.args("strict-ailleurs"); f = settings_passe(x); rq = lire_json(f) if f else None
    dire("--dangerously-skip-permissions" in x and f == i / "agents/strict-ailleurs/.reglages-claude.json", "strict ailleurs : réglages passés par --settings")
    dire(rq is not None and rq.get(CLE) is True, "strict ailleurs : l'accord dans .reglages-claude.json")
    dire(rq is not None and rq["sandbox"]["enabled"] and rq["permissions"]["defaultMode"] == "bypassPermissions" and rq["permissions"]["deny"],
         "strict ailleurs : bac à sable et refus conservés")

    # ── ouvert dans son dossier : settings.local.json (comme le strict), settings.json inchangé ──
    d = i / "agents/ouvert-ici"; x = claude.args("ouvert-ici")
    dire("--dangerously-skip-permissions" in x and lire_json(d / ".claude/settings.local.json") == {CLE: True}, "ouvert ici : l'accord dans .claude/settings.local.json")
    dire(lire_json(d / ".claude/settings.json") == {"permissions": {"defaultMode": "bypassPermissions"}}, "ouvert ici : .claude/settings.json inchangé")

    # ── ouvert dans un dossier existant : .appelant-claude.json par --settings, même sans en-tête d'appelant ──
    x = claude.args("ouvert-ailleurs"); f = settings_passe(x)
    dire("--dangerously-skip-permissions" in x and f == i / "agents/ouvert-ailleurs/.appelant-claude.json" and lire_json(f) == {CLE: True},
         "ouvert ailleurs : l'accord par --settings, dans le dossier Berger de l'agent (sans en-tête : la clé seule)")
    dire(not (i / "agents/ouvert-ailleurs/.reglages-claude.json").exists(), "ouvert ailleurs : pas de .reglages-claude.json (réservé au mur strict)")

    # ── nulle part ailleurs : ni dans le dossier existant, ni chez Codex, ni dans un autre fichier généré ──
    dire(not any(ext.rglob("*")), "dossier existant : rien n'y est écrit")
    dire(CLE not in (i / ".codex/config.toml").read_text(), "Codex : aucune trace de l'accord (réglage propre à Claude)")
    porteurs = sorted(str(p.relative_to(i)) for p in i.rglob("*") if p.is_file() and not p.is_relative_to(i / "bin")
                      and not p.is_relative_to(i / "courtier") and CLE in p.read_text(errors="replace"))
    attendus = sorted(["agents/strict-ici/.claude/settings.local.json", "agents/strict-ailleurs/.reglages-claude.json",
                       "agents/ouvert-ici/.claude/settings.local.json", "agents/ouvert-ailleurs/.appelant-claude.json",
                       "agents/essai-codex/.claude/settings.local.json"])
    dire(porteurs == attendus, f"la clé n'est que dans les fichiers lus par Claude pour un lancement en bypass — un agent Codex peut être ouvert sous Claude (mission, panneau), comme son settings.json ({porteurs})")

    # ── regenerer est idempotent : même contenu au second passage ──
    avant = {p: (i / p).read_text() for p in attendus}
    subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(all((i / p).read_text() == t for p, t in avant.items()), "regenerer deux fois : mêmes fichiers")

# ── settings.local.json déjà là (installation du 04/11, n° 141 : regenerer a échoué sur un fichier 0444 du propriétaire) ──
# regenerer n'échoue jamais pour ce fichier et ne perd aucune clé : clé déjà vraie → rien d'écrit ; sinon la clé est FUSIONNÉE
# (écriture atomique, mode d'origine gardé) ; JSON illisible → laissé tel quel, message nommé. Jamais de chmod sur le fichier.
with tempfile.TemporaryDirectory() as td:
    m = Path(td); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun")); _produit.admettre_moteurs(i)
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    # Le cas réel : Berger pose ce fichier VIDE en 0444 (mcp-trous : l'agent ne s'y déclare pas de serveur MCP) ; vide vaut {}.
    # Le propriétaire y a déjà posé l'accord à la main, en 0444, chez plusieurs agents : accepté tel quel.
    cas = {"vide-lecture-seule": ("", 0o444), "deja-pose-main": ({CLE: True}, 0o444),
           "deja-lecture-seule": ({CLE: True, "proprio": "gardé"}, 0o444), "deja-ecrivable": ({CLE: True}, 0o644),
           "autres-cles": ({"proprio": {"réglage": "à la main"}}, 0o640), "cle-fausse-lecture-seule": ({CLE: False, "proprio": 1}, 0o444),
           "illisible": ("{ pas du json", 0o644), "pas-un-objet": ([CLE], 0o644)}
    for a, (contenu, mode) in cas.items():
        d = i / "agents" / a; (d / "memory").mkdir(parents=True); (d / ".claude").mkdir()
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\nheures = aucune\noutils =\n")
        f = d / ".claude/settings.local.json"
        f.write_text(contenu if isinstance(contenu, str) else json.dumps(contenu, ensure_ascii=False, indent=2) + "\n"); f.chmod(mode)
    sl = lambda a: i / "agents" / a / ".claude/settings.local.json"
    avant = {a: (sl(a).read_bytes(), os.stat(sl(a)).st_ino, os.stat(sl(a)).st_mtime_ns) for a in cas}
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": "/bin/false", "BERGER_TMP_AGENTS": str(m / "bt")}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    sortie = r.stdout + r.stderr
    dire(r.returncode == 0 and "PermissionError" not in sortie, "fichiers existants (dont 0444) : regenerer réussit" + ("" if r.returncode == 0 else f" — {sortie.strip()[-300:]}"))
    mode = lambda a: os.stat(sl(a)).st_mode & 0o777
    dire(lire_json(sl("vide-lecture-seule")) == {CLE: True} and mode("vide-lecture-seule") == 0o444,
         "fichier vide 0444 (posé par Berger) : vaut {}, la clé y est écrite, mode 0444 gardé")
    for a in ("deja-pose-main", "deja-lecture-seule", "deja-ecrivable"):
        dire((sl(a).read_bytes(), os.stat(sl(a)).st_ino, os.stat(sl(a)).st_mtime_ns) == avant[a] and mode(a) == cas[a][1],
             f"{a} : clé déjà vraie → fichier intouché (contenu, inode, date, mode)")
    dire(lire_json(sl("autres-cles")) == {"proprio": {"réglage": "à la main"}, CLE: True} and mode("autres-cles") == 0o640,
         "autres clés du propriétaire : gardées, la clé fusionnée, mode 0640 gardé")
    dire(lire_json(sl("cle-fausse-lecture-seule")) == {CLE: True, "proprio": 1} and mode("cle-fausse-lecture-seule") == 0o444,
         "clé fausse dans un fichier 0444 : passée à vrai, autre clé gardée, mode 0444 gardé (aucun chmod du fichier)")
    for a in ("illisible", "pas-un-objet"):
        dire(sl(a).read_bytes() == avant[a][0], f"{a} : pas écrasé")
        dire(any(a in l and "settings.local.json" in l for l in sortie.splitlines()), f"{a} : message nommé (agent et fichier)")
    restes = sorted(p.name for a in cas for p in sl(a).parent.iterdir() if p.name not in ("settings.local.json", "settings.json", "skills"))
    dire(restes == [], f"aucun fichier temporaire laissé dans .claude/ ({restes})")
    # Dossier .claude/ non inscriptible (aucun temporaire possible) et clé absente : le fichier reste intact, le problème est nommé
    # (la suite de regenerer, settings.json dans ce même dossier, est hors de ce correctif)
    g_ = sl("autres-cles"); g_.write_text('{"proprio": 2}'); g_.parent.chmod(0o555)
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    g_.parent.chmod(0o755)
    sortie = r.stdout + r.stderr
    dire(lire_json(g_) == {"proprio": 2} and any("autres-cles" in l and "non écrit" in l for l in sortie.splitlines()),
         "dossier .claude/ non inscriptible : fichier intact, avertissement nommé « non écrit »")
    g_.write_text(json.dumps({"proprio": {"réglage": "à la main"}}, ensure_ascii=False))
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0 and lire_json(sl("autres-cles")) == {"proprio": {"réglage": "à la main"}, CLE: True}, "second passage : réussit, même contenu")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
