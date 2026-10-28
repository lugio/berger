#!/usr/bin/env python3
"""Tests de `proteges` (agent.conf) — parties du dossier de l'agent lues mais jamais réécrites, comme son agent.conf —
sans modèle, installation JETABLE : réglages Claude (refus d'édition + denyWrite) et Codex (`read`), chemins refusés
(absolu, « .. », hors du dossier) ou absents nommés au regenerer, sans effet nommé pour un agent ouvert.
La preuve dans le vrai bac à sable est faite par la sonde du mur (tests/tout.sh).
Usage : python3 tests/proteges.py (0 = tout passe)"""
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
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    for a, mur, prot in (("compta", "strict", "scripts, notes.md, ../voisin, /etc, absent, scripts/../../voisin"),
                         ("voisin", "strict", ""), ("ouvert", "ouvert", "scripts")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True); (d / "scripts").mkdir()
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\npanneaux = claude\nmur = {mur}\nheures = aucune\noutils =\n"
                                      + (f"proteges = {prot}   # essai\n" if prot else ""))
    (i / "agents/compta/notes.md").write_text("x\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": "/bin/false"}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    sortie = r.stdout + r.stderr
    dire(r.returncode == 0, "regenerer réussit avec `proteges`" + ("" if r.returncode == 0 else f" — {sortie.strip()[-200:]}"))

    c = i / "agents/compta"; s = json.loads((c / ".claude/settings.json").read_text())
    dw = s["sandbox"]["filesystem"]["denyWrite"]; deny = s["permissions"]["deny"]
    dire(str(c / "scripts") in dw and str(c / "notes.md") in dw, "Claude : dossier et fichier protégés dans denyWrite (bac à sable)")
    dire("Edit(~/berger/agents/compta/scripts/**)" in deny and "Edit(~/berger/agents/compta/notes.md)" in deny,
         "Claude : refus d'édition (dossier : /**, fichier : lui-même)")
    dire(str(c / "agent.conf") in dw, "son agent.conf reste protégé (rien de perdu)")
    cx = (i / ".codex/config.toml").read_text().split("[permissions.compta.filesystem]")[1].split("[permissions.")[0]
    dire(f'"{c / "scripts"}" = "read"' in cx and f'"{c / "notes.md"}" = "read"' in cx, "Codex : dossier et fichier protégés en `read`")
    lus = sorted(l.split('"')[1] for l in cx.splitlines() if l.endswith('= "read"'))
    # les réglages passés par --settings (.reseau-claude.json, .reglages-claude.json : sites permis, 12/10) sont protégés pour TOUS
    passes = [str(c / ".reseau-claude.json"), str(c / ".reglages-claude.json")]
    mcp = lambda d: [str(d / x) for x in (".mcp.json", ".claude/settings.json", ".claude/settings.local.json", ".codex", ".mcp-berger.json")]   # mcp-trous, 17/10 ; berger-mcp, 18/10
    dire(sorted(dw) == sorted([str(c / "agent.conf"), str(c / "espace.toml"), str(c / "scripts"), str(c / "notes.md")] + passes + mcp(c))
         and sorted(x for x in dw if x not in passes) == lus,
         f"rien d'autre n'est protégé, refusés et absent écartés (Claude {len(dw)}, Codex {len(lus)})")
    for x, motif in (("../voisin", "refusé"), ("/etc", "refusé"), ("scripts/../../voisin", "refusé"), ("absent", "absent")):
        dire(f"compta : proteges « {x} » {motif}" in sortie, f"« {x} » : {motif}, nommé au regenerer")
    v = json.loads((i / "agents/voisin/.claude/settings.json").read_text())
    dire(v["sandbox"]["filesystem"]["denyWrite"] == [str(i / "agents/voisin" / x) for x in ("agent.conf", "espace.toml", ".reseau-claude.json", ".reglages-claude.json")] + mcp(i / "agents/voisin"),
         "agent sans `proteges` : réglages inchangés (son agent.conf, ses réglages passés par --settings, ses fichiers MCP)")
    dire("ouvert : proteges sans effet : mur = ouvert" in sortie, "agent `mur = ouvert` : `proteges` dit sans effet, nommé")

sys.exit(1 if ko else 0)
