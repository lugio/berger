#!/usr/bin/env python3
"""Suites sous un HOME jetable avec les raccourcis mise de la vraie maison dans le PATH (18/10/2026). Vécu : depuis un
dossier sous la vraie maison, un raccourci mise lancé avec un HOME jetable échoue (« mise ERROR … config.toml are not
trusted »), python3 compris : le « #!/usr/bin/env python3 » de bin/berger mourait avant Python, et la porte tests du
courtier était rouge pour toute branche. Un FAUX raccourci python3 (dans un dossier …/mise/shims) reproduit ce
comportement : il ne marche qu'avec le vrai HOME.
  - témoin : la sonde lancée directement, faux raccourci en tête du PATH → échoue (la reproduction est réelle) ;
  - la même sonde jouée par tests/suites.sh (SUITE_SEULE) → verte : chaque suite tourne sans « …/mise/shims » dans son
    PATH, avec un python3 qui est l'interpréteur réel.
Usage : python3 tests/shims-mise.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import os, subprocess, sys, tempfile
from pathlib import Path

T = Path(__file__).resolve().parent; ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    s = Path(t) / "maison/.local/share/mise/shims"; s.mkdir(parents=True)
    vrai = os.path.realpath(sys.executable)
    (s / "python3").write_text(f'#!/bin/sh\n[ "$HOME" = "{os.environ["HOME"]}" ] && exec "{vrai}" "$@"\n'
                               'echo "mise ERROR faux raccourci : config not trusted (HOME jetable)" >&2; exit 1\n')
    (s / "python3").chmod(0o755)
    env = {**os.environ, "PATH": f"{s}{os.pathsep}{os.environ['PATH']}"}
    r = subprocess.run([vrai, str(T / "sonde-shebang.py")], env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode != 0 and "mise ERROR" in r.stdout, "témoin : faux raccourci mise en tête du PATH, HOME jetable → bin/berger ne démarre pas")
    r = subprocess.run(["bash", str(T / "suites.sh")], env={**env, "SUITE_SEULE": "sonde-shebang.py"}, capture_output=True, text=True, timeout=300)
    dire(r.returncode == 0 and r.stdout.startswith("ok"), "suites.sh : la même sonde est verte (raccourcis mise hors du PATH des suites, python3 réel)"
         + ("" if r.returncode == 0 else f" — {' '.join(r.stdout.split())[-200:]}"))

sys.exit(1 if ko else 0)
