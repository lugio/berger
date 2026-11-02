#!/usr/bin/env python3
"""Tests de `berger memoire verifier|valider|refuser` — sans modèle, sans Herdr, installation JETABLE (07/10/2026, porte de
perte avant application de la mémoire) : ajout accepté puis appliqué (sauvegarde `.avant-`, proposition retirée,
journal) ; ajout refusé au-delà de 3 000 car. ; remplacement accepté quand liens, dates et montants restent (« 120,00 » → « 120 »
passe) ; refusé pour un lien perdu ; refusé au-delà de 25 % de dates perdues ; mémoire EXTERNE (`memoire = …`) : le bon
fichier est visé ; `refuser` retire et journalise ; agent implicite par BERGER_AGENT. Usage : python3 tests/memoire.py (0 = OK)."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as td:
    t = Path(td); _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    (t / "coffre.json").write_text("{}")
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n')
    env = {**os.environ, "BERGER_DIR": str(t)}
    for a, conf_ in (("a1", "nom = Un\n"), ("a2", "nom = Deux\nmemoire = memoire\n")):
        (t / "agents" / a / "pending").mkdir(parents=True); (t / "agents" / a / "agent.conf").write_text(conf_)
    A1, A2 = t / "agents/a1", t / "agents/a2"
    (A2 / "memoire").mkdir()

    def berger(*args, agent_env=None):
        e = dict(env); e.update(agent_env or {})
        return subprocess.run([sys.executable, str(t / "bin/berger"), "memoire", *args], env=e, capture_output=True, text=True, timeout=60)

    def prop(a, nom, texte):
        p = t / "agents" / a / "pending" / nom; p.write_text(f"type: memoire\npourquoi: test\n---\n{texte}\n"); return p

    journal = lambda a: (t / "agents" / a / "memory" / f"{datetime.date.today().isoformat()}.md")
    sauvegardes = lambda d: sorted(d.glob("MEMORY.md.avant-*"))

    # 1. ajout accepté, puis appliqué
    (A1 / "MEMORY.md").write_text("# Mémoire longue\n\n- [2026-10-01] premier fait\n")
    p = prop("a1", "2026-10-07_ajout.md", "- [2026-10-07] second fait")
    r = berger("verifier", "a1", "2026-10-07_ajout.md")
    dire(r.returncode == 0 and "ajout" in r.stdout and "acceptable" in r.stdout, f"ajout : verifier accepte (code {r.returncode}, {r.stdout.strip()[:80]!r})")
    r = berger("valider", "a1", str(p))
    m = (A1 / "MEMORY.md").read_text()
    dire(r.returncode == 0 and m.endswith("- [2026-10-01] premier fait\n- [2026-10-07] second fait\n"), f"ajout : valider écrit la ligne à la fin ({m!r})")
    s = sauvegardes(A1)
    dire(len(s) == 1 and s[0].read_text() == "# Mémoire longue\n\n- [2026-10-01] premier fait\n", f"ajout : sauvegarde MEMORY.md.avant-… = l'ancien contenu ({[x.name for x in s]})")
    dire(not p.exists(), "ajout : la proposition est retirée de pending/")
    dire(journal("a1").exists() and "validée" in journal("a1").read_text() and "2026-10-07_ajout.md" in journal("a1").read_text(), "ajout : ligne au journal de l'agent")

    # 2. ajout refusé : plus de 3 000 caractères
    p = prop("a1", "2026-10-07_trop.md", "- [2026-10-07] " + "x" * 3100)
    avant = (A1 / "MEMORY.md").read_text(); r = berger("valider", "a1", "2026-10-07_trop.md")
    dire(r.returncode == 1 and "3000" in r.stdout and (A1 / "MEMORY.md").read_text() == avant and p.exists() and len(sauvegardes(A1)) == 1,
         f"ajout > 3 000 : refusé, rien écrit, proposition gardée (code {r.returncode})")

    # 3. remplacement accepté sur une mémoire EXTERNE (index + fiches) : liens, dates et montants conservés, 120,00 → 120
    index = ("# Index\n\n- [Chèques 04/09/2026](cheques.md) — 299,98 € : Breysse 60 ; Benachir 120,00 sans facture\n"
             "- [Dolibarr](dolibarr.md) — brouillons PROV306, échues au 2026-10-01\n- [MCF](mcf.md) — panne 01/09 → 03/09, 16/16 déposées\n")
    (A2 / "memoire/MEMORY.md").write_text(index); (A2 / "MEMORY.md").write_text("# pas celui-là\n")
    p = prop("a2", "2026-10-07_condense.md", "# Index\n- [Chèques 04/09/2026](cheques.md) — 299,98 : Benachir 120 sans facture\n"
                                            "- [Dolibarr](dolibarr.md) — PROV306, échues 2026-10-01\n- [MCF](mcf.md) — panne 01/09 → 03/09, 16/16")
    r = berger("valider", "a2", "2026-10-07_condense.md")
    dire(r.returncode == 0 and (A2 / "memoire/MEMORY.md").read_text().startswith("# Index\n- [Chèques") and (A2 / "MEMORY.md").read_text() == "# pas celui-là\n",
         f"remplacement (mémoire externe) : accepté, le fichier de `memoire =` est visé, pas MEMORY.md du dossier (code {r.returncode}, {r.stdout.strip()[:100]!r})")
    dire(len(sauvegardes(A2 / "memoire")) == 1 and sauvegardes(A2 / "memoire")[0].read_text() == index, "remplacement : sauvegarde à côté de la mémoire externe")

    # 4. remplacement refusé : un lien vers une fiche perdu
    actuel = (A2 / "memoire/MEMORY.md").read_text()
    p = prop("a2", "2026-10-07_lien.md", "# Index\n- [Chèques 04/09/2026](cheques.md) — 299,98 : Benachir 120\n- [MCF](mcf.md) — panne 01/09 → 03/09, 16/16 ; PROV306 2026-10-01")
    r = berger("verifier", "a2", "2026-10-07_lien.md")
    dire(r.returncode == 1 and "dolibarr.md" in r.stdout and (A2 / "memoire/MEMORY.md").read_text() == actuel, f"remplacement : lien perdu → refusé et nommé ({r.stdout.strip()[-80:]!r})")

    # 5. remplacement refusé : plus de 25 % des dates et montants perdus (ici 2 sur 6)
    p = prop("a2", "2026-10-07_dates.md", "# Index\n- [Chèques 04/09/2026](cheques.md) — Benachir 120\n- [Dolibarr](dolibarr.md) — PROV306, échues 2026-10-01\n- [MCF](mcf.md) — panne 01/09, 16/16")
    r = berger("valider", "a2", "2026-10-07_dates.md")
    dire(r.returncode == 1 and "REFUS" in r.stdout and "03/09" in r.stdout and (A2 / "memoire/MEMORY.md").read_text() == actuel and p.exists(),
         f"remplacement : > 25 % des dates/montants perdus → refusé, rien écrit ({r.stdout.strip().splitlines()[-1][:90]!r})")
    # … et une petite perte (1 sur 6) passe avec un avertissement nommé
    p = prop("a2", "2026-10-07_petite.md", "# Index\n- [Chèques 04/09/2026](cheques.md) — 299,98 : Benachir 120\n- [Dolibarr](dolibarr.md) — PROV306, échues 2026-10-01\n- [MCF](mcf.md) — panne 01/09, 16/16")
    r = berger("verifier", "a2", "2026-10-07_petite.md")
    dire(r.returncode == 0 and "attention" in r.stdout and "03/09" in r.stdout, f"remplacement : 1 date perdue sur 6 → acceptable avec avertissement nommé ({r.stdout.strip().splitlines()[-1][:90]!r})")

    # 6. refuser : retire et journalise ; 7. agent implicite par BERGER_AGENT
    r = berger("refuser", "2026-10-07_petite.md", agent_env={"BERGER_AGENT": "a2"})
    dire(r.returncode == 0 and not p.exists() and "refusée" in journal("a2").read_text(), f"refuser (agent implicite BERGER_AGENT) : proposition retirée, ligne au journal (code {r.returncode})")
    r = berger("verifier", "introuvable.md", agent_env={"BERGER_AGENT": "a2"})
    dire(r.returncode != 0 and "introuvable" in r.stderr, "proposition inconnue : erreur nommée, rien d'écrit")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
