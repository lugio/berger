#!/usr/bin/env python3
"""Sonde de tests/shims-mise.py (18/10/2026) : bin/berger d'une installation JETABLE, lancé par son « #!/usr/bin/env python3 »
(comme le courtier le lance), sous un HOME JETABLE (comme les suites). 0 = il démarre."""
import os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"; _produit.copier(Path(__file__).resolve().parent.parent, i, ("bin", "courtier"))
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    r = subprocess.run([str(i / "bin/berger"), "aide"], env={**os.environ, "HOME": str(m), "BERGER_DIR": str(i)},
                       capture_output=True, text=True, timeout=60)
    ok = r.returncode == 0 and "berger" in r.stdout
    print(("ok    " if ok else "ÉCHEC ") + "bin/berger lancé par son shebang sous un HOME jetable"
          + ("" if ok else f" — code {r.returncode} : {' '.join(r.stderr.split())[-160:]}"))
    sys.exit(0 if ok else 1)
