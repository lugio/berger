#!/usr/bin/env python3
"""Tests de `berger abonnement-claude <type> <palier>` — sur un FAUX fichier d'identifiants, jamais le vrai.
Vérifie : seuls subscriptionType et rateLimitTier changent (les autres champs, faux, restent identiques), droits 0600,
pas de .tmp laissé, aucune valeur du fichier dans la sortie ; type inconnu, palier illisible, fichier sans connexion par
compte → refus, fichier inchangé. Usage : python3 tests/abonnement.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\nicone_berger = "🐑"\n')
    (m / ".claude").mkdir()
    f = m / ".claude/.credentials.json"
    faux = {"claudeAiOauth": {"accessToken": "FAUX-JETON-A", "refreshToken": "FAUX-JETON-R", "expiresAt": 1, "scopes": ["user:inference"],
                              "subscriptionType": None, "rateLimitTier": None}, "autre": {"x": 1}}
    f.write_text(json.dumps(faux)); os.chmod(f, 0o600)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=60)

    r = b("abonnement-claude", "max", "default_claude_max_20x")
    d = json.loads(f.read_text()); o = d["claudeAiOauth"]
    dire(r.returncode == 0 and r.stdout.startswith("ok"), f"écriture acceptée ({r.stdout.strip()[:80]}{r.stderr.strip()[-200:]})")
    dire(o["subscriptionType"] == "max" and o["rateLimitTier"] == "default_claude_max_20x", "les deux champs sont écrits")
    attendu = {**faux["claudeAiOauth"], "subscriptionType": "max", "rateLimitTier": "default_claude_max_20x"}
    dire(o == attendu and d["autre"] == faux["autre"], "aucun autre champ modifié")
    dire(oct(f.stat().st_mode & 0o777) == "0o600", "droits 0600 conservés")
    dire(not list(f.parent.glob("*.tmp")), "pas de fichier temporaire laissé")
    dire("FAUX-JETON" not in r.stdout + r.stderr, "aucune valeur du fichier dans la sortie")

    avant = f.read_bytes()
    for args, quoi in ((("illimite", "x_tier"), "type inconnu"), (("max", "palier; rm"), "palier illisible")):
        r = b("abonnement-claude", *args)
        dire(r.returncode != 0 and f.read_bytes() == avant, f"{quoi} → refus, fichier inchangé")
    f.write_text(json.dumps({"autre": 1})); avant = f.read_bytes()
    r = b("abonnement-claude", "max", "default_claude_max_20x")
    dire(r.returncode != 0 and f.read_bytes() == avant, "pas de connexion par compte → refus, fichier inchangé")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
