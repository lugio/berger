#!/usr/bin/env python3
"""Tests de la bibliothèque (lot 2, 08/10/2026) — sans modèle, sans Herdr, installation JETABLE.
Un agent INSCRIT (`bibliotheque = oui`) a son dossier de travail <racine>/agents/<agent>/travail/ : lui seul y écrit (Claude :
allowWrite ; Codex : « write »), les autres ne le lisent pas (refus de lecture Claude, « none » Codex) ; <racine>/commun/ est
lisible par tous et refusé en écriture à TOUS (refus d'édition + denyWrite ; Codex « read ») ; ses règles nomment ses deux
dossiers. Un agent NON inscrit n'a pas de dossier de travail ni la section des règles ; sans aucun inscrit, rien n'est créé.
La bibliothèque n'entre jamais dans le dépôt. L'effet réel du mur (sur le disque) est prouvé par tests/tout.sh (sonde-mur).
Usage : python3 tests/bibliotheque.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def installer(m, inscrits, moteurs):
    i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    for a, moteur in moteurs.items():
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = {moteur}\npanneaux = {moteur}\nheures = aucune\noutils =\n"
                                      + ("bibliotheque = oui   # agent pilote\n" if a in inscrits else ""))
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    return i, r


with tempfile.TemporaryDirectory() as t:
    m = Path(t)
    i, r = installer(m, {"pilote", "voisin"}, {"pilote": "claude", "voisin": "codex", "libre": "claude"})
    dire(r.returncode == 0, "regenerer réussit avec deux agents inscrits et un non inscrit" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr).strip()[-200:]}"))
    B = i / "bibliotheque"; tp, tv, co = B / "agents/pilote/travail", B / "agents/voisin/travail", B / "commun"
    dire(tp.is_dir() and tv.is_dir() and co.is_dir(), "dossiers créés : travail de chaque inscrit + commun")
    dire(not (B / "agents/libre").exists(), "non inscrit : pas de dossier de travail")

    def reglages(a): return json.loads((i / "agents" / a / ".claude/settings.json").read_text())
    def lecture_refusee(s, p): return f"Read(~/{p.relative_to(m)}/**)" in s["permissions"]["deny"]
    def edition_refusee(s, p): return f"Edit(~/{p.relative_to(m)}/**)" in s["permissions"]["deny"]
    s = reglages("pilote"); fs = s["sandbox"]["filesystem"]
    dire(str(tp) in fs.get("allowWrite", []) and str(tp) in s["permissions"].get("additionalDirectories", []),
         "Claude, inscrit : écrit dans SON dossier de travail (allowWrite + additionalDirectories)")
    dire(lecture_refusee(s, B / "agents/voisin") and not lecture_refusee(s, B / "agents/pilote"),
         "Claude, inscrit : le dossier du voisin est illisible, le sien non")
    dire(str(co) in fs["denyWrite"] and edition_refusee(s, co) and str(co) not in fs.get("allowWrite", []),
         "Claude, inscrit : commun refusé en écriture (denyWrite + refus d'édition)")
    dire(not lecture_refusee(s, co), "Claude, inscrit : commun lisible")
    s = reglages("libre"); fs = s["sandbox"]["filesystem"]
    dire(not any("bibliotheque" in x for x in fs.get("allowWrite", [])), "Claude, non inscrit : aucune écriture dans la bibliothèque")
    dire(lecture_refusee(s, B / "agents/pilote") and lecture_refusee(s, B / "agents/voisin"),
         "Claude, non inscrit : les dossiers de travail des inscrits sont illisibles")
    dire(str(co) in fs["denyWrite"] and edition_refusee(s, co) and not lecture_refusee(s, co),
         "Claude, non inscrit : commun lisible, refusé en écriture")

    cx = (i / ".codex/config.toml").read_text()
    def profil(a): return cx.split(f"[permissions.{a}.filesystem]", 1)[1].split("\n[", 1)[0]
    pv, pp, pl = profil("voisin"), profil("pilote"), profil("libre")
    dire(f'"{tv}" = "write"' in pv, "Codex, inscrit : « write » sur SON dossier de travail")
    dire(f'"{B / "agents/pilote"}" = "none"' in pv and f'"{B / "agents/voisin"}" = "none"' not in pv,
         "Codex, inscrit : le dossier du voisin est « none », pas le sien")
    dire(all(f'"{co}" = "read"' in p for p in (pv, pp, pl)), "Codex : commun en lecture seule pour tous")
    dire("bibliotheque" not in "".join(l for l in pl.splitlines() if l.endswith('"write"')), "Codex, non inscrit : aucune écriture dans la bibliothèque")

    rp, rl = (i / "agents/pilote/AGENTS.md").read_text(), (i / "agents/libre/AGENTS.md").read_text()
    dire(f"{tp}/" in rp and f"{co}/" in rp and "{travail_bibliotheque}" not in rp, "règles de l'inscrit : ses deux dossiers nommés")
    dire("la bibliothèque" not in rl and "{travail_bibliotheque}" not in rl and "{commun_bibliotheque}" not in rl,
         "règles du non inscrit : pas de section bibliothèque, aucun gabarit resté")

with tempfile.TemporaryDirectory() as t:
    m = Path(t)
    i, r = installer(m, set(), {"seul": "claude"})
    dire(r.returncode == 0 and not (i / "bibliotheque").exists(), "aucun inscrit : rien n'est créé")
    s = json.loads((i / "agents/seul/.claude/settings.json").read_text())
    dire("bibliotheque" not in json.dumps(s), "aucun inscrit : réglages Claude inchangés (aucune mention)")

g = subprocess.run(["git", "-C", str(SRC), "check-ignore", "-q", "bibliotheque/agents/x/travail/f.md"], capture_output=True)
dire(g.returncode == 0, "dépôt : la bibliothèque est ignorée par git (liste blanche du .gitignore)")
dire("bibliotheque/" in (SRC / "bin/berger").read_text().split("interdits_chemins = re.compile(", 1)[1].split("\n", 1)[0],
     "verifier-depot : un fichier de la bibliothèque forcé dans le dépôt serait refusé")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
