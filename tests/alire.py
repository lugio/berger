#!/usr/bin/env python3
"""Tests de l'onglet « À lire » — sans modèle, sans Herdr : une installation JETABLE, deux agents et un dossier commun. Vérifie :
liste du plus récent au plus ancien, titre lu dans la 1re ligne, non-lu / lu, document modifié redevenu non lu, fichier non .md et
lien symbolique ignorés, mise en forme (titre, gras), numéro inexistant refusé, Accueil qui signale les non-lus, nouveau qui crée a-lire/,
règle commune présente dans les instructions. Usage : python3 tests/alire.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


net = lambda t: re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", t)
with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=60)
    r = b("nouveau", "vigie", "Vigie")
    dire(r.returncode == 0 and (i / "agents/vigie/a-lire").is_dir(), "nouveau : crée le dossier a-lire/ de l'agent")
    b("nouveau", "scribe", "Scribe"); b("regenerer")
    regles = (i / "agents/vigie/AGENTS.md").read_text() if (i / "agents/vigie/AGENTS.md").exists() else ""
    dire("a-lire/AAAA-MM-JJ_<sujet>.md" in regles, "la règle « un document pour le propriétaire : a-lire/ » est dans les instructions")
    (i / "agents/vigie/a-lire/2026-10-01_dns.md").write_text("# Rapport DNS\n\n**SPF** correct.\n")
    time.sleep(0.05); (i / "agents/scribe/a-lire/2026-10-02_sauvegardes.md").write_text("\n# Inventaire des sauvegardes\n- 26 machines\n")
    time.sleep(0.05); (i / "a-lire").mkdir(); (i / "a-lire/2026-10-03_plan.md").write_text("# Plan de la VM\n")
    (i / "agents/vigie/a-lire/notes.txt").write_text("pas un document")
    (i / "agents/vigie/a-lire/lien.md").symlink_to(m / "coffre.json")
    code = f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');print('\\n'.join(g['VUES']['alire'].vue_alire(140, 60)))"
    vue = lambda: net(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60).stdout)
    v = vue(); lignes = [l for l in v.splitlines() if re.match(r"^ [●✓] +\d", l)]
    dire(len(lignes) == 3, f"3 documents listés (.txt et lien symbolique ignorés) — {len(lignes)}")
    dire([re.search(r"(Plan de la VM|Inventaire des sauvegardes|Rapport DNS)", l).group(1) for l in lignes] ==
         ["Plan de la VM", "Inventaire des sauvegardes", "Rapport DNS"], "du plus récent au plus ancien ; titre = 1re ligne non vide")
    dire("3 non lus sur 3" in v and all(l.startswith(" ●") for l in lignes), "tous non lus au départ")
    dire("📌 commun" in lignes[0] and "Scribe" in lignes[1] and "Vigie" in lignes[2], "auteur affiché (commun, agent)")
    r = b("lire", "3", "--sans-pager")
    dire(r.returncode == 0 and "Rapport DNS" in net(r.stdout) and "\x1b[1m" in r.stdout and "SPF" in net(r.stdout), "lire 3 : document mis en forme (titre, gras)")
    v = vue(); dire("2 non lus sur 3" in v and re.search(r"✓ +3 ", v), "après lecture : le document passe en « lu »")
    time.sleep(0.05); (i / "agents/vigie/a-lire/2026-10-01_dns.md").write_text("# Rapport DNS (mis à jour)\n")
    v = vue(); dire("3 non lus sur 3" in v, "document modifié : redevient non lu")
    r = b("lire", "9", "--sans-pager"); dire("pas de document n° 9" in r.stdout and r.returncode == 1, "numéro inexistant : refusé proprement")
    code2 = f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');print('\\n'.join(g['VUES']['accueil'].vue_accueil(140, 60)))"
    acc = net(subprocess.run([sys.executable, "-c", code2], env=env, capture_output=True, text=True, timeout=60).stdout)
    dire("À LIRE (3)" in acc and "Plan de la VM" in acc, "Accueil : signale les documents non lus")

sys.exit(1 if ko else 0)
