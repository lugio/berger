#!/usr/bin/env python3
"""config.exemple.toml : une fois la tête de l'exemple décommentée (jusqu'au premier outil), chaque option RACINE connue est bien à la
racine. Une option racine écrite après un `[[gardes]]` décommenté tomberait dans le garde et serait ignorée sans message."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import re
import sys
import tomllib
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
ko = 0
RACINE = ("proprietaire", "fuseau", "icone_berger", "marques_privees", "depot_public", "entete_appelant", "pied_codex",
          "codex_modele_strict", "coffre", "masques", "masques_si_presents", "masque_fichier", "codex_identifiants")


def dire(ok, message):
    global ko
    ko += not ok
    print(('ok    ' if ok else 'ÉCHEC ') + message)


lignes = (SRC / 'config.exemple.toml').read_text().splitlines()
fin = next(i for i, l in enumerate(lignes) if l.startswith('# [outils'))          # le premier outil déclaré en exemple
tete = [re.sub(r'^# ', '', l) if re.match(r'^# (\[\[?|[a-z_]+ *=)', l) else l for l in lignes[:fin]]
try:
    cfg = tomllib.loads('\n'.join(tete))
except tomllib.TOMLDecodeError as e:
    cfg = None
    dire(False, f"la tête de l'exemple, décommentée, se lit en TOML ({e})")
if cfg is not None:
    dire(True, "la tête de l'exemple, décommentée, se lit en TOML")
    for cle in RACINE:
        dire(cle in cfg, f"option racine « {cle} » : à la racine une fois décommentée (pas dans un tableau)")
    dire(set(cfg) - set(RACINE) == {"gardes"}, f"seul « gardes » s'ajoute aux options racine ({sorted(set(cfg) - set(RACINE))})")
print(f'==== {ko} échec(s)')
sys.exit(1 if ko else 0)
