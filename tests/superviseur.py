#!/usr/bin/env python3
"""Tests de `superviseur = oui` (agent.conf, 09/10/2026) — sans modèle, sans Herdr, installation JETABLE.
Le gardien de Berger LIT les dossiers des autres agents et leur bibliothèque (ni refus de lecture Claude, ni « none » Codex),
mais n'y ÉCRIT pas (refus d'édition inchangés) ; le coffre et les sources des outils restent illisibles ; son agent.conf
reste en lecture seule pour lui. Un agent sans la clé reste cloisonné, y compris envers le superviseur.
La méthode `berger` du produit (commun/skills/) lui est donnée quand il la nomme. L'effet réel du mur (sur le disque)
est prouvé par tests/tout.sh (sonde-mur). Usage : python3 tests/superviseur.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / ".config/berger").mkdir(parents=True); (m / ".config/berger/coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = [".config/berger"]\ncoffre = "{m}/.config/berger/coffre-essai.json"\n')
    agents = {"master": "claude", "voisin": "codex", "libre": "claude"}
    for a, moteur in agents.items():
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = {moteur}\npanneaux = {moteur}\nheures = aucune\noutils =\nbibliotheque = oui\n"
                                      + ("superviseur = oui\nskills = berger\n" if a == "master" else ""))
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0, "regenerer réussit avec un superviseur" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr).strip()[-200:]}"))

    def reglages(a): return json.loads((i / "agents" / a / ".claude/settings.json").read_text())
    def lecture_refusee(s, p): return f"Read(~/{p.relative_to(m)}/**)" in s["permissions"]["deny"]
    def edition_refusee(s, p, motif="/**"): return f"Edit(~/{p.relative_to(m)}{motif})" in s["permissions"]["deny"]
    A, B = i / "agents", i / "bibliotheque/agents"
    s = reglages("master")
    dire(not lecture_refusee(s, A / "voisin") and not lecture_refusee(s, A / "libre"), "Claude, superviseur : lit les dossiers des autres agents")
    dire(not lecture_refusee(s, B / "voisin"), "Claude, superviseur : lit leur dossier de bibliothèque")
    dire(lecture_refusee(s, m / ".config/berger"), "Claude, superviseur : le coffre reste illisible")
    dire(lecture_refusee(s, i / "courtier/panneaux"), "Claude, superviseur : les sources des outils restent illisibles")
    dire(edition_refusee(s, A / "voisin") and edition_refusee(s, A / "libre"), "Claude, superviseur : n'écrit pas chez les autres agents")
    dire(edition_refusee(s, i / "commun") and edition_refusee(s, i / "bin") and edition_refusee(s, i / "config.toml", ""),
         "Claude, superviseur : ni commun/, ni bin/, ni config.toml")
    dire(edition_refusee(s, A / "master/agent.conf", "") and str(A / "master/agent.conf") in s["sandbox"]["filesystem"]["denyWrite"],
         "Claude, superviseur : son agent.conf reste en lecture seule pour lui")
    dire(s["sandbox"]["enabled"] and s["sandbox"]["network"]["deniedDomains"] == ["*"], "Claude, superviseur : bac à sable et réseau refusé, comme tout agent strict")
    s = reglages("libre")
    dire(lecture_refusee(s, A / "master") and lecture_refusee(s, A / "voisin") and lecture_refusee(s, B / "master"),
         "Claude, sans la clé : cloisonné, y compris envers le superviseur")

    cx = (i / ".codex/config.toml").read_text()
    def profil(a): return cx.split(f"[permissions.{a}.filesystem]", 1)[1].split("\n[", 1)[0]
    pm, pv = profil("master"), profil("voisin")
    dire(f'"{A / "voisin"}" = "none"' not in pm and f'"{B / "voisin"}" = "none"' not in pm, "Codex, superviseur : aucun autre agent en « none »")
    dire(f'"{m / ".config/berger"}" = "none"' in pm and f'"{A / "master/agent.conf"}" = "read"' in pm,
         "Codex, superviseur : coffre « none », son agent.conf « read »")
    dire(f'"{A / "master"}" = "none"' in pv, "Codex, sans la clé : le superviseur reste « none »")

    lien = A / "master/.claude/skills/berger"
    dire(lien.is_symlink() and lien.resolve() == (i / "commun/skills/berger").resolve(), "méthode `berger` du produit donnée au superviseur (commun/skills/)")
    dire(not (A / "libre/.claude/skills/berger").exists(), "méthode `berger` : pas aux agents qui ne la nomment pas")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
