#!/usr/bin/env python3
"""Tests de l'auto-test de nuit : verrou de tests/tout.sh (jamais deux exécutions) et alertes de la Synthèse sur
tests/dernier-resultat.txt — un échec → ROUGE avec le nom des contrôles ; minuterie de nuit activée mais aucun passage
depuis 26 h, ou jamais → ROUGE ; tout passe et récent → rien ; sans minuterie, un vieux résultat vert → rien.
Unités systemd berger-tests.* : oneshot sur tests/tout.sh, nuit à 05:00, hors 02 h. Usage : python3 tests/auto-test-nuit.py"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun", "tests"))
    (m / "coffre.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    f = i / "tests/dernier-resultat.txt"; minuterie = m / ".config/systemd/user/timers.target.wants/berger-tests.timer"

    def alertes(age=0):
        if f.exists(): os.utime(f, (time.time() - age, time.time() - age))
        code = (f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
                "print(json.dumps(g['alertes_auto_test']()))")
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
        try: return json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError): return [["?", "?", r.stderr[-200:]]]

    f.write_text("07/10 05:00 — 2 échec(s) (5 agents, 2 moteurs)\n- securite claude mur système\n- - - audit : SECRET EN CLAIR trouvé\n")
    a = alertes()
    dire(len(a) == 1 and a[0][0] == "rouge" and "mur système" in a[0][2] and "audit" in a[0][2], f"échec → ROUGE avec les noms ({a})")
    f.write_text("07/10 05:00 — tout passe (5 agents, 2 moteurs)\n")
    dire(alertes() == [], "tout passe, sans minuterie → rien")
    dire(alertes(age=40 * 3600) == [], "sans minuterie de nuit : un vieux résultat vert ne crie pas")
    minuterie.parent.mkdir(parents=True); minuterie.write_text("")
    dire(alertes(age=3600) == [], "minuterie active, passage d'il y a 1 h → rien")
    a = alertes(age=27 * 3600)
    dire(len(a) == 1 and a[0][0] == "rouge" and "26 h" in a[0][2], "minuterie active, plus de 26 h sans passage → ROUGE")
    f.unlink(); a = alertes()
    dire(len(a) == 1 and a[0][0] == "rouge" and "jamais" in a[0][2], "minuterie active, jamais passé → ROUGE")

    # verrou : une exécution déjà en cours → la seconde ne lance rien (code 3)
    v = i / "tests/.tout.verrou"
    tient = subprocess.Popen(["flock", str(v), "sleep", "5"])
    time.sleep(0.5)
    r = subprocess.run(["bash", str(i / "tests/tout.sh")], env=env, capture_output=True, text=True, timeout=30)
    tient.kill(); tient.wait()
    dire(r.returncode == 3 and "déjà en cours" in r.stdout, f"verrou : seconde exécution refusée (code {r.returncode})")
    dire(not f.exists(), "verrou : la seconde exécution n'a pas écrit de résultat")

    # écriture du résultat par la fin de tout.sh (le bloc réel, extrait) : un succès doit être ENREGISTRÉ, pas seulement un
    # échec — vécu le 07/10 : sans échec, le bloc sortait en 1, le mv n'avait pas lieu, le résultat restait dans le .tmp
    tout = (i / "tests/tout.sh").read_text().splitlines()
    debut = next(n for n, l in enumerate(tout) if l.startswith('{ echo "$(date'))
    bloc = "\n".join(tout[debut:next(n for n in range(debut, len(tout)) if "dernier-resultat.txt.tmp" in tout[n]) + 1])
    for ko_, echecs, attendu in ((0, "", "tout passe"), (2, "- a claude mur\n- b codex garde", "2 échec(s)")):
        f.unlink(missing_ok=True); (i / "tests/dernier-resultat.txt.tmp").unlink(missing_ok=True)
        r = subprocess.run(["bash", "-c", f'B={str(i)!r}; ko={ko_}; AGENTS="a b"; seul=""; echecs="$1"\n{bloc}', "x", echecs],
                           capture_output=True, text=True, timeout=30)
        ecrit = f.read_text() if f.exists() else ""
        dire(attendu in ecrit and not (i / "tests/dernier-resultat.txt.tmp").exists() and (ko_ == 0 or "mur" in ecrit),
             f"résultat ENREGISTRÉ ({attendu}) : dernier-resultat.txt écrit, pas de .tmp laissé (obtenu {ecrit[:60]!r} {r.stderr[-80:]})")

    s = (SRC / "systemd/berger-tests.service").read_text(); tm = (SRC / "systemd/berger-tests.timer").read_text()
    dire("Type=oneshot" in s and "tests/tout.sh" in s, "service : oneshot sur tests/tout.sh")
    dire("OnCalendar=*-*-* 05:00:00 Europe/Paris" in tm and "02:" not in tm, "minuterie : chaque nuit à 05:00 (Paris), hors 02 h")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
