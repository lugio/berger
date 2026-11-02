#!/usr/bin/env python3
"""Tests de l'en-tête d'appelant (entete_appelant de config.toml → ANTHROPIC_CUSTOM_HEADERS « <en-tête>: <agent> »).
Pour les quatre murs (strict / ouvert, dans son dossier / dans un dossier existant) : l'en-tête est dans les réglages
que lit Claude, au nom de L'agent, sans retirer un réglage existant ; sans réglage ou avec un nom douteux : rien.
Usage : python3 tests/appelant.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def installer(t, entete):
    _produit.copier(SRC, t, ("bin", "courtier", "commun")); _produit.admettre_moteurs(t)
    (t / "coffre.json").write_text("{}")
    ligne = f'entete_appelant = "{entete}"\n' if entete is not None else ""
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n{ligne}')
    (t / "role-existant").mkdir()
    for a, extra in (("strict-ici", ""), ("strict-ailleurs", f"dossier = {t}/role-existant\n"),
                     ("ouvert-ici", "mur = ouvert\n"), ("ouvert-ailleurs", f"mur = ouvert\ndossier = {t}/role-existant\n")):
        d = t / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\nheures = aucune\n{extra}")
    env = dict(os.environ, BERGER_DIR=str(t), HOME=str(t))
    b = lambda *x: subprocess.run([sys.executable, str(t / "bin/berger"), *x], env=env, capture_output=True, text=True, timeout=60)
    r = b("regenerer")
    return b, r


def entete_de(chemin):
    try: return (json.loads(Path(chemin).read_text()).get("env") or {}).get("ANTHROPIC_CUSTOM_HEADERS")
    except (OSError, ValueError): return None


def reglages_lus(b, a):
    """Les fichiers de réglages que Claude lira pour cet agent : --settings donné, sinon le settings.json du projet."""
    r = b("args", a, "claude", "--non-interactif")
    try: args = json.loads(r.stdout)["args"]
    except (ValueError, KeyError): return None, r.stderr[-200:]
    return args, (args[args.index("--settings") + 1] if "--settings" in args else None)


with tempfile.TemporaryDirectory() as td:
    t = Path(td); b, r = installer(t, "X-AOS-Agent")
    dire(r.returncode == 0, f"regenerer passe ({r.stderr.strip()[-160:]})")
    s = t / "agents/strict-ici/.claude/settings.json"
    dire(entete_de(s) == "X-AOS-Agent: strict-ici", "strict dans son dossier : en-tête au nom de l'agent dans ses réglages de projet")
    d = json.loads(s.read_text())
    dire(d["permissions"]["defaultMode"] == "bypassPermissions" and d["sandbox"]["enabled"] and d["permissions"]["deny"],
         "strict : permissions, bac à sable et refus conservés")
    args, f = reglages_lus(b, "strict-ici")
    dire(args is not None and args[:2] == ["--setting-sources", "project,local"], "strict : Claude lit bien les réglages de projet")
    args, f = reglages_lus(b, "strict-ailleurs")
    dire(f is not None and entete_de(f) == "X-AOS-Agent: strict-ailleurs", "strict dans un dossier existant : en-tête dans .reglages-claude.json")
    dire(f is not None and json.loads(Path(f).read_text())["sandbox"]["enabled"], "strict ailleurs : bac à sable conservé")
    dire(not (t / "role-existant/.claude").exists(), "strict ailleurs : rien écrit dans le dossier existant")
    o = t / "agents/ouvert-ici/.claude/settings.json"
    dire(entete_de(o) == "X-AOS-Agent: ouvert-ici" and json.loads(o.read_text())["permissions"]["defaultMode"] == "bypassPermissions",
         "ouvert dans son dossier : en-tête + mode conservé")
    args, f = reglages_lus(b, "ouvert-ailleurs")
    dire(f is not None and entete_de(f) == "X-AOS-Agent: ouvert-ailleurs" and Path(f).parent == t / "agents/ouvert-ailleurs",
         "ouvert dans un dossier existant : en-tête par --settings, fichier dans le dossier Berger de l'agent")
    dire(not (t / "agents/ouvert-ailleurs/.reglages-claude.json").exists(), "ouvert ailleurs : pas de .reglages-claude.json (réservé au mur strict)")

for entete, quoi in ((None, "sans réglage"), ("X AOS; rm", "nom d'en-tête douteux")):
    with tempfile.TemporaryDirectory() as td:
        t = Path(td); b, r = installer(t, entete)
        vus = [entete_de(t / f"agents/{a}/.claude/settings.json") for a in ("strict-ici", "ouvert-ici")]
        args, f = reglages_lus(b, "strict-ailleurs"); vus.append(entete_de(f) if f else None)
        args, f = reglages_lus(b, "ouvert-ailleurs")
        dire(r.returncode == 0 and vus == [None, None, None] and f is None, f"{quoi} : aucun en-tête, aucun --settings en plus")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
