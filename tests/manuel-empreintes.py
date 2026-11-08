#!/usr/bin/env python3
"""Empreintes du manuel par section (tests/_manuel_sections.py).
Usage :
  python3 -I tests/manuel-empreintes.py [verifier] [<racine>]                code de retour = nombre de refus
  python3 -I tests/manuel-empreintes.py recalculer [<section>…]              après avoir modifié une section (toutes si aucune)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import sys
from pathlib import Path
import _manuel_sections as M

RACINE = Path(__file__).resolve().parent.parent


def main(argv):
    if argv[:1] == ["recalculer"]:
        try: print("\n".join(M.recalculer(RACINE, argv[1:])) or "rien à faire"); return 0
        except (ValueError, OSError) as e: print(f"ÉCHEC recalculer : {e}"); return 1
    if argv[:1] == ["verifier"]: argv = argv[1:]
    if len(argv) > 1 or (argv and argv[0].startswith("-")): print(__doc__); return 2
    refus, n = M.verifier(Path(argv[0]) if argv else RACINE)
    for r in refus: print(f"ÉCHEC {r}")
    if not refus: print(f"ok manuel : {n} sections, chacune à son empreinte")
    return min(len(refus), 100)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
