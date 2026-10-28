#!/usr/bin/env python3
"""Taille des fichiers de bin/ (modulaire, docs/plans/2026-10-27-modulaire-decisions.md) : aucun fichier de bin/ ne dépasse
1 500 lignes ; un fichier de commandes NOUVEAU (bin/commandes/) en a 500 de plus au plus... soit 2 000 ; bin/berger suit un cliquet
DÉCROISSANT pendant la migration (il ne peut que diminuer) ; aucune autre exception. Usage : python3 tests/taille-fichiers.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
LIMITE, BONUS_COMMANDES = 1500, 500
# Cliquet de bin/berger : à baisser à chaque lot (jamais à relever). Lot 1 : 6 089 -> 4 944 ; lot 2 : 4 944 -> 4 664 ; lot 3 : 4 664 -> 4 439 (2 verbes déplacés, 240 lignes vides résiduelles des lots 1 et 2 retirées) ; lot 3 bis : 4 439 -> 4 242 (8 verbes et leurs fonctions déplacés ; `vue` reste au cœur).
CLIQUET_BERGER = 4248
ko = 0


def dire(ok, texte):
    global ko
    print(("ok     " if ok else "ÉCHEC  ") + texte); ko += 0 if ok else 1


def lignes(f): return len(f.read_text(encoding="utf-8").splitlines())


berger = SRC / "bin/berger"
n = lignes(berger)
dire(n <= CLIQUET_BERGER, f"bin/berger : {n} lignes, cliquet {CLIQUET_BERGER} (ne peut que baisser)")
trop = []
for f in sorted((SRC / "bin").rglob("*")):
    if not f.is_file() or f == berger or f.suffix not in (".py", ".mjs") and f.name not in ("berger-mcp", "berger-navigateur-web"): continue
    if "__pycache__" in f.parts or "page" in f.relative_to(SRC / "bin").parts[:1]: continue
    limite = LIMITE + (BONUS_COMMANDES if f.parent.name == "commandes" and f.parent.parent.name == "bin" else 0)
    if lignes(f) > limite: trop.append(f"{f.relative_to(SRC)} ({lignes(f)} > {limite})")
dire(not trop, "aucun autre fichier de bin/ au-dessus de la limite (1 500 ; 2 000 pour un fichier de bin/commandes/) : " + (", ".join(trop) or "aucun"))
dire(CLIQUET_BERGER < 6089, "le cliquet de bin/berger est sous sa taille de départ (6 089 lignes)")
sys.exit(1 if ko else 0)
