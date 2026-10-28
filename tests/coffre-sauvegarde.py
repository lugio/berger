#!/usr/bin/env python3
"""Tests de « berger coffre sauvegarder / purger » — installation JETABLE, coffre factice, paire de clés age jetable.
Couvre le 08/10 (7 copies EN CLAIR du coffre laissées par la règle « copie datée ») : refus sans destinataire (aucun fichier),
copie chiffrée 600 dans son dossier, déchiffrable à l'identique, aucune copie en clair à côté du coffre, aucune valeur
imprimée, purge au-delà de garder_jours (commande et entretien), motif refusé s'il sort du dossier.
Usage : python3 tests/coffre-sauvegarde.py (0 = tout passe ; sauté si age est absent)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


if not (shutil.which("age") and shutil.which("age-keygen")):
    print("age absent : test sauté"); print("---- 0 échec(s)"); sys.exit(0)

with tempfile.TemporaryDirectory() as t:
    t = Path(t); i = t / "berger"; _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    valeur_coffre = "valeur-secrete-du-test-coffre"
    cf = t / "conf"; cf.mkdir(); coffre = cf / "coffre.json"; coffre.write_text(json.dumps({"outil": {"cle": valeur_coffre}})); os.chmod(coffre, 0o600)
    cles = t / "cle-privee"; subprocess.run(["age-keygen", "-o", str(cles)], check=True, capture_output=True)
    pub = subprocess.run(["age-keygen", "-y", str(cles)], check=True, capture_output=True, text=True).stdout.strip()
    sv = t / "sauvegardes-coffre"
    base = f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{coffre}"\n'
    env = {**os.environ, "BERGER_DIR": str(i), "HOME": str(t)}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=60)

    (i / "config.toml").write_text(base)
    r = b("coffre", "sauvegarder", "avant-essai")
    dire(r.returncode != 0 and not sv.exists() and not (t / "sauvegardes/coffre").exists(), "sans destinataire : refus, AUCUNE sauvegarde (et on le dit)")

    (i / "config.toml").write_text(base + f'\n[coffre_sauvegarde]\ndestinataire = "{pub}"\ndossier = "{sv}"\ngarder_jours = 7\n')
    r = b("coffre", "sauvegarder", "../hors-dossier")
    dire(r.returncode != 0 and not list(t.rglob("*hors-dossier*")), "motif qui sortirait du dossier : refusé")

    r = b("coffre", "sauvegarder", "avant-essai")
    f = sorted(sv.glob("coffre-*-avant-essai.json.age"))
    dire(r.returncode == 0 and len(f) == 1, "copie chiffrée créée dans son dossier")
    if f:
        dire(oct(f[0].stat().st_mode & 0o777) == "0o600" and oct(sv.stat().st_mode & 0o777) == "0o700", "fichier 600, dossier 700")
        dire(f[0].read_bytes()[:21] == b"age-encryption.org/v1" and valeur_coffre.encode() not in f[0].read_bytes(), "en-tête age, valeur absente du fichier")
        clair = subprocess.run(["age", "-d", "-i", str(cles), str(f[0])], capture_output=True).stdout
        dire(clair == coffre.read_bytes(), "déchiffrée avec la clé privée : identique au coffre")
    dire(valeur_coffre not in r.stdout + r.stderr and "RETOUR ARRIÈRE" in r.stdout, "aucune valeur imprimée ; commande de retour arrière donnée")
    dire(sorted(p.name for p in cf.iterdir()) == ["coffre.json"], "aucune copie en clair à côté du coffre")

    vieux = sv / "coffre-20000101-000000-ancien.json.age"; vieux.write_bytes(b"age-encryption.org/v1\nx")
    os.utime(vieux, (time.time() - 8 * 86400,) * 2)
    r = b("coffre", "purger")
    dire(not vieux.exists() and len(list(sv.glob("*.age"))) == 1, "purge : au-delà de 7 jours effacée, la récente gardée")
    vieux.write_bytes(b"x"); os.utime(vieux, (time.time() - 8 * 86400,) * 2)
    b("entretien")
    dire(not vieux.exists(), "l'entretien quotidien purge aussi")
print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
