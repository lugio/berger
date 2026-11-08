#!/usr/bin/env python3
"""Journal en fragments (spec docs/plans/2026-11-04-changelog-fragments-spec.md) : tests/changelog.py `verifier` (un cas rouge par
refus) et `regrouper` (trois fragments qui se recouvrent, sortie figée, fragments supprimés). Sans modèle, dans des dossiers
jetables. Usage : python3 tests/changelog-fragments.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import os, subprocess, sys, tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "changelog.py"
ko = 0
TETE = "# Changelog\n\nIntro.\n\n## [Unreleased]\n\n"
ANCIEN = "## [0.1.0] - 2026-01-01\n\n### Added\n\n- First.\n"
REPERE = "<!-- Entries go in changelog.d/<topic>.md (see CONTRIBUTING.md): this section stays empty. -->"


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def lancer(*args):
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def depot(t, journal=TETE + ANCIEN, frags=None):
    d = Path(tempfile.mkdtemp(dir=t)); (d / "CHANGELOG.md").write_text(journal)
    for nom, texte in (frags or {}).items():
        p = d / "changelog.d" / nom; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(texte)
    return d


BON = "### Added\n\n- A thing.\n"
with tempfile.TemporaryDirectory() as t:
    # ── verifier : vert ──
    rc, out = lancer("verifier", depot(t, frags={"un-sujet.md": BON}))
    dire(rc == 0 and "1 fragment" in out, f"verifier : un fragment bien formé → vert ({out.strip()[:80]})")
    rc, out = lancer(depot(t))
    dire(rc == 0, "verifier (sans verbe) : aucun fragment, [Unreleased] vide → vert")
    rc, out = lancer(depot(t, TETE + "### Fixed\n\n- Old style line.\n\n" + ANCIEN))
    dire(rc == 0 and "transition" in out, "transition : une ligne sous [Unreleased] avant le premier regroupement → permise (demandes en cours)")
    rc, out = lancer(depot(t, frags={"multi.md": "### Fixed\n\n- Long line\n  continued here.\n\n### Security\n\n- Other.\n"}))
    dire(rc == 0, "verifier : puce sur plusieurs lignes et deux sections → vert")

    # ── verifier : un cas rouge par refus ──
    rouges = {
        "titre ##": ({"a.md": "## [9.9.9]\n\n### Added\n\n- x\n"}, "titre"),
        "titre #": ({"a.md": "# Titre\n\n### Added\n\n- x\n"}, "titre"),
        "section inconnue": ({"a.md": "### Improved\n\n- x\n"}, "section inconnue"),
        "fragment vide": ({"a.md": "\n  \n"}, "vide"),
        "section vide": ({"a.md": "### Added\n\n### Fixed\n\n- x\n"}, "vide"),
        "ligne hors section": ({"a.md": "- x\n"}, "hors section"),
        "nom en majuscules": ({"Sujet.md": BON}, "nom refusé"),
        "nom avec un point": ({"a.b.md": BON}, "nom refusé"),
        "pas en .md": ({"a.txt": BON}, "nom refusé"),
        "sous-dossier": ({"sous/a.md": BON}, "sous-dossier"),
    }
    for libelle, (frags, mot) in rouges.items():
        rc, out = lancer(depot(t, frags=frags))
        dire(rc != 0 and mot in out, f"verifier refuse : {libelle} ({out.strip().splitlines()[0][:90] if out.strip() else 'sans sortie'})")
    d = depot(t, frags={"cible.md": BON}); (d / "changelog.d/lien.md").symlink_to(d / "changelog.d/cible.md")
    rc, out = lancer(d); dire(rc != 0 and "lien symbolique" in out, "verifier refuse : un lien symbolique dans changelog.d/")
    d = depot(t, frags={"x.md": BON}); os.chmod(d / "changelog.d/x.md", 0o755)
    rc, out = lancer(d); dire(rc != 0 and "exécutable" in out, "verifier refuse : un fragment exécutable")
    rc, out = lancer(depot(t, TETE + REPERE + "\n\n### Added\n\n- Sneaked line.\n\n" + ANCIEN))
    dire(rc != 0 and "Sneaked line" in out and "changelog.d/<sujet>.md" in out, "verifier refuse : une ligne sous [Unreleased] après le premier regroupement")
    rc, out = lancer(depot(t, "# Changelog\n\n" + ANCIEN))
    dire(rc != 0 and "Unreleased" in out, "verifier refuse : CHANGELOG.md sans [Unreleased]")

    # ── regrouper : trois fragments qui se recouvrent (Added et Fixed dans deux fichiers), sortie figée ──
    d = depot(t, frags={"b-deux.md": "### Fixed\n\n- Fix B.\n\n### Added\n\n- Add B.\n",
                        "a-un.md": "### Added\n\n- Add A,\n  on two lines.\n\n### Fixed\n\n- Fix A.\n",
                        "c-trois.md": "### Security\n\n- Sec C.\n\n### Changed\n\n- Change C.\n"})
    rc, out = lancer("regrouper", "0.2.0", "2026-11-05", d)
    attendu = (TETE + REPERE + "\n\n## [0.2.0] - 2026-11-05\n\n### Added\n\n- Add A,\n  on two lines.\n- Add B.\n\n### Changed\n\n- Change C.\n\n"
               "### Fixed\n\n- Fix A.\n- Fix B.\n\n### Security\n\n- Sec C.\n\n" + ANCIEN)
    dire(rc == 0 and "3 fragment" in out, f"regrouper : 3 fragments regroupés ({out.strip()[:90]})")
    dire((d / "CHANGELOG.md").read_text() == attendu, "regrouper : sortie figée (ordre Keep a Changelog, puis par nom de fichier)")
    if (d / "CHANGELOG.md").read_text() != attendu: print((d / "CHANGELOG.md").read_text())
    dire(not (d / "changelog.d").exists(), "regrouper : fragments supprimés (et changelog.d/ vide retiré)")
    rc, out = lancer("verifier", d); dire(rc == 0, "après le regroupement : verifier vert ([Unreleased] ne porte que le repère)")
    rc, out = lancer("regrouper", "0.3.0", "2026-11-06", d); dire(rc != 0 and "rien à regrouper" in out, "regrouper sans fragment ni ligne → refus")

    # transition : les lignes déjà sous [Unreleased] passent en tête de la version, avant les fragments
    d = depot(t, TETE + "### Added\n\n- Old way.\n\n" + ANCIEN, {"z.md": "### Added\n\n- New way.\n"})
    rc, out = lancer("regrouper", "0.2.0", "2026-11-05", d); j = (d / "CHANGELOG.md").read_text()
    dire(rc == 0 and "## [0.2.0] - 2026-11-05\n\n### Added\n\n- Old way.\n- New way.\n" in j and j.count("Old way") == 1,
         "regrouper : les lignes de transition sont reprises une fois, avant les fragments")

    # refus : rien n'est touché
    d = depot(t, frags={"a.md": BON, "B.md": BON}); avant = (d / "CHANGELOG.md").read_text()
    rc, out = lancer("regrouper", "0.2.0", "2026-11-05", d)
    dire(rc != 0 and (d / "CHANGELOG.md").read_text() == avant and (d / "changelog.d/a.md").exists(), "regrouper avec un fragment refusé → rien n'est modifié")
    for v, dt, mot in (("v0.2.0", "2026-11-05", "SemVer"), ("0.2", "2026-11-05", "SemVer"), ("0.2.0", "05/11/2026", "date"), ("0.1.0", "2026-11-05", "déjà")):
        d = depot(t, frags={"a.md": BON}); rc, out = lancer("regrouper", v, dt, d)
        dire(rc != 0 and mot in out and (d / "changelog.d/a.md").exists(), f"regrouper {v} {dt} → refus ({mot})")

# ── la liste blanche du dépôt (.gitignore) versionne les fragments : sans elle, un fragment ne partirait jamais avec sa branche ──
with tempfile.TemporaryDirectory() as t:
    d = Path(t); (d / ".gitignore").write_text((SCRIPT.parent.parent / ".gitignore").read_text())
    (d / "changelog.d").mkdir(); (d / "changelog.d/un-sujet.md").write_text(BON); (d / "autre.md").write_text("x\n")
    subprocess.run(["git", "init", "-q", str(d)]); subprocess.run(["git", "-C", str(d), "add", "."], capture_output=True)
    suivis = subprocess.run(["git", "-C", str(d), "ls-files"], capture_output=True, text=True).stdout.split()
    dire("changelog.d/un-sujet.md" in suivis and "autre.md" not in suivis, f".gitignore (liste blanche) : changelog.d/<sujet>.md est versionné ({suivis})")

print(f"\n{'tout passe' if not ko else f'{ko} échec(s)'}")
sys.exit(1 if ko else 0)
