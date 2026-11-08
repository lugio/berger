#!/usr/bin/env python3
"""Empreintes du manuel par section (lot D, option (b), de docs/plans/2026-11-04-acceleration-fusions-spec.md) : une section
modifiée sans recalcul reste rouge et le message la nomme ; une section ajoutée ou retirée est détectée ; deux branches sur deux
sections différentes n'ont plus de fichier commun hors docs/manuel.md ; tests/vitrine.py ne contient plus aucune empreinte.
Sans réseau, dans des dossiers jetables. Usage : python3 tests/manuel-sections.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import re, shutil, subprocess, sys, tempfile
from pathlib import Path
import _manuel_sections as M

SRC = Path(__file__).resolve().parent.parent
SCRIPT = SRC / "tests/manuel-empreintes.py"
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def git(d, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True)


MANUEL = ("# Manuel\n\nIntro.\n\n## Sommaire\n\n- [Principes](#principes)\n- [Courtier](#courtier)\n- [Missions](#missions)\n\n"
          "## Principes\n\nUn.\n\n```\n## pas un titre (bloc de code)\n```\n\n## Courtier\n\nDeux.\n\n## Missions\n\nTrois.\n")


def depot(t, manuel=MANUEL):
    d = Path(tempfile.mkdtemp(dir=t)); (d / "docs").mkdir(); (d / "docs/manuel.md").write_text(manuel)
    (d / "tests").mkdir(); shutil.copy(SCRIPT, d / "tests"); shutil.copy(SRC / "tests/_manuel_sections.py", d / "tests")
    shutil.copy(SRC / "tests/_herdr_isole.py", d / "tests")
    M.recalculer(d); return d


def lancer(d, *a):
    r = subprocess.run([sys.executable, "-I", str(d / "tests/manuel-empreintes.py"), *a], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


with tempfile.TemporaryDirectory() as t:
    d = depot(t)
    noms = [n for _, n, _ in M.sections(MANUEL)]
    dire(noms == ["en-tete", "principes", "courtier", "missions"], f"sections : en-tête puis chaque « ## » hors sommaire et hors blocs de code ({noms})")
    dire(sorted(f.name for f in (d / M.ATTENDUS).iterdir()) == sorted(f"{n}.sha256" for n in noms), "une empreinte par section dans tests/attendus/manuel/")
    rc, out = lancer(d); dire(rc == 0 and "4 sections" in out, f"manuel intact → vert ({out.strip()})")

    # modifiée sans recalcul : rouge, la section est nommée ; recalculée : verte
    (d / "docs/manuel.md").write_text(MANUEL.replace("Deux.", "Deux, modifié."))
    rc, out = lancer(d)
    dire(rc != 0 and "« Courtier » modifiée sans recalcul" in out and "recalculer courtier" in out and "Missions" not in out,
         f"section modifiée sans recalcul → rouge, nommée, avec la commande ({out.strip()[:120]})")
    rc, _ = lancer(d, "recalculer", "courtier"); rc2, out = lancer(d)
    dire(rc == 0 and rc2 == 0, "recalculer courtier → vert")
    (d / "docs/manuel.md").write_text(MANUEL.replace("Intro.", "Intro changée."))
    rc, out = lancer(d); dire(rc != 0 and "« (en-tête) » modifiée" in out, "le texte avant le premier titre (en-tête) est figé aussi")
    d = depot(t); (d / "docs/manuel.md").write_text(MANUEL.replace("- [Missions](#missions)\n", "- [Missions](#missions)\n- [Autre](#autre)\n"))
    rc, out = lancer(d); dire(rc == 0, "le sommaire n'est pas figé (vitrine.py vérifie qu'il suit les titres)")

    # ajoutée, retirée, doublon
    d = depot(t); (d / "docs/manuel.md").write_text(MANUEL + "\n## Nouvelle partie\n\nQuatre.\n")
    rc, out = lancer(d); dire(rc != 0 and "section ajoutée « Nouvelle partie »" in out and "nouvelle-partie.sha256" in out, f"section ajoutée → détectée ({out.strip()[:100]})")
    d = depot(t); (d / "docs/manuel.md").write_text(MANUEL.split("## Missions")[0])
    rc, out = lancer(d); dire(rc != 0 and "section retirée « missions »" in out, f"section retirée → détectée ({out.strip()[:100]})")
    rc, out = lancer(d, "recalculer", "missions"); rc2, _ = lancer(d)
    dire(rc == 0 and "empreinte supprimée" in out and rc2 == 0 and not (d / M.ATTENDUS / "missions.sha256").exists(), "recalculer une section retirée supprime son empreinte")
    d = depot(t); (d / "docs/manuel.md").write_text(MANUEL + "\n## Courtier !\n\nDouble.\n")
    rc, out = lancer(d); dire(rc != 0 and "deux sections au même nom « courtier »" in out, "deux titres au même nom → refus nommé")
    rc, out = lancer(d, "recalculer", "../x"); dire(rc != 0 and "refusé" in out, "recalculer : nom de section hors [a-z0-9-] refusé")

    # deux branches sur deux sections : aucune empreinte commune, seul docs/manuel.md l'est (git le fusionne sans conflit)
    d = depot(t); git(d, "init", "-q", "-b", "main"); git(d, "add", "-A"); git(d, "commit", "-qm", "départ")
    for b, avant, apres, n in (("a", "Deux.", "Deux (a).", "courtier"), ("b", "Trois.", "Trois (b).", "missions")):
        git(d, "switch", "-q", "-c", b, "main"); m = d / "docs/manuel.md"; m.write_text(m.read_text().replace(avant, apres))
        M.recalculer(d, [n]); git(d, "commit", "-qam", b)
    ca = set(git(d, "diff", "--name-only", "main", "a").stdout.split()); cb = set(git(d, "diff", "--name-only", "main", "b").stdout.split())
    dire(ca & cb == {"docs/manuel.md"}, f"deux branches sur deux sections : seul docs/manuel.md est commun, aucune empreinte ({sorted(ca & cb)})")
    r = git(d, "merge-tree", "--write-tree", "a", "b")
    dire(r.returncode == 0, "… et git les fusionne sans conflit")
    git(d, "switch", "-q", "a"); git(d, "merge", "-q", "--no-edit", "b"); rc, out = lancer(d)
    dire(rc == 0, f"après la fusion des deux branches : vert sans rien recalculer ({out.strip()})")

# le dépôt lui-même : vitrine.py sans empreinte en dur, le vrai manuel à jour de ses empreintes
dire(not re.search(r"[0-9a-f]{64}", (SRC / "tests/vitrine.py").read_text()), "tests/vitrine.py ne contient plus aucune empreinte en dur")
refus, n = M.verifier(SRC)
dire(not refus, f"docs/manuel.md : {n} sections, chacune à son empreinte {refus[:2] if refus else ''}")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
