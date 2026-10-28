#!/usr/bin/env python3
"""Tests SANS MODÈLE de la ligne témoin des consignes personnelles de Claude (fonction `temoin` de tests/tout.sh).
Choix : une ligne présente chez l'agent (son dossier, .claude/skills, skills-agent, commun/, fichier @-importé) est écartée,
une ligne de moins de 25 caractères aussi, un fichier absent ou sans ligne possible → « aucun » (non mesurable).
Comparaison : recopie exacte, espaces différents, ABSENT, sortie vide. La ligne témoin n'est jamais imprimée par ces tests.
Usage : python3 tests/consignes-canari.py"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import re, subprocess, sys, tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


tout = (SRC / "tests/tout.sh").read_text()
m = re.search(r"^# >>> temoin\n(.*?)^# <<< temoin$", tout, re.S | re.M)
dire(bool(m), "la fonction temoin est repérable dans tests/tout.sh")
if not m: sys.exit(1)
fonction = m.group(1)

L1 = "Première règle personnelle du propriétaire"
L2 = "Deuxième règle personnelle du propriétaire"
L3 = "Troisième règle personnelle du propriétaire"


def temoin(*args):
    r = subprocess.run(["bash", "-c", fonction + '\ntemoin "$@"', "x", *args], capture_output=True, text=True)
    return r.stdout.strip()


def cas(nom, claude, agent_fichiers=(), commun_fichiers=()):
    """Retourne (verdict, dossier de sortie) ; tout vit dans un dossier jetable."""
    t = Path(tempfile.mkdtemp()); (t / "agent").mkdir(); (t / "commun").mkdir(); (t / "sortie").mkdir()
    if claude is not None: (t / "CLAUDE.md").write_text(claude)
    for rel, txt in agent_fichiers: (t / "agent" / rel).parent.mkdir(parents=True, exist_ok=True); (t / "agent" / rel).write_text(txt)
    for rel, txt in commun_fichiers: (t / "commun" / rel).write_text(txt)
    return temoin("choisir", str(t / "CLAUDE.md"), str(t / "agent"), str(t / "commun"), str(t / "sortie")), t


def ecrit(t, nom): p = t / "sortie" / nom; return p.read_text() if p.exists() else None


# ── choix de la ligne témoin ──
v, t = cas("base", f"{L1}\n\n{L2}\n{L3}\n")
dire(v == "ok" and ecrit(t, "repere") == L1 and ecrit(t, "temoin") == L2, "choix : premier couple repère/témoin, ligne vide ignorée")
dire(oct((t / "sortie/temoin").stat().st_mode & 0o777) == "0o600", "la ligne témoin est écrite en 0600")

v, t = cas("agent", f"{L1}\n{L2}\n{L3}\n", [("AGENTS.md", f"règle : {L2}\n")])
dire(v == "aucun", "choix : une ligne présente dans le dossier de l'agent est exclue (plus aucun couple)")

v, t = cas("agent2", f"{L1}\n{L2}\n{L3}\n", [(".claude/skills/x/SKILL.md", f"{L1}\n")])
dire(v == "ok" and ecrit(t, "repere") == L2 and ecrit(t, "temoin") == L3, "choix : exclusion dans .claude/skills, couple suivant retenu")

v, t = cas("lien", f"{L1}\n{L2}\n")
(t / "ext/skill").mkdir(parents=True); (t / "ext/skill/SKILL.md").write_text(L2 + "\n")   # hors de l'agent : lisible seulement par le lien
(t / "agent/.claude/skills").mkdir(parents=True); (t / "agent/.claude/skills/x").symlink_to(t / "ext/skill")
(t / "agent/.claude/skills/boucle").symlink_to(t / "agent")   # boucle : ne doit pas bloquer
v = temoin("choisir", str(t / "CLAUDE.md"), str(t / "agent"), str(t / "commun"), str(t / "sortie"))
dire(v == "aucun", "choix : .claude/skills/x lien vers un dossier hors de l'agent → ligne exclue (liens suivis, boucle évitée)")

v, t = cas("skills-agent", f"{L1}\n{L2}\n", [("skills-agent/y/SKILL.md", L2)])
dire(v == "aucun", "choix : exclusion dans skills-agent")

v, t = cas("commun", f"{L1}\n{L2}\n", commun_fichiers=[("USER.md", f"- {L2}\n")])
dire(v == "aucun", "choix : une ligne présente dans commun/ est exclue")

v, t = cas("espaces", f"{L1}\n{L2}\n", [("MEMORY.md", "Deuxième   règle personnelle\tdu propriétaire\n")])
dire(v == "aucun", "choix : une ligne présente à des espaces près est exclue")

v, t = cas("import", f"{L1}\n{L2}\n", [("AGENTS.md", "@../ext/regles.md\n")])
(t / "ext").mkdir(); (t / "ext/regles.md").write_text(L2 + "\n")   # hors du dossier de l'agent : seul l'import le rend lisible
v = temoin("choisir", str(t / "CLAUDE.md"), str(t / "agent"), str(t / "commun"), str(t / "sortie"))
dire(v == "aucun", "choix : une ligne d'un fichier @-importé est exclue")

v, t = cas("court", "Trop court\nCourt aussi\n")
dire(v == "aucun", "choix : lignes de moins de 25 caractères refusées")
dire(ecrit(t, "temoin") is None, "choix : aucun fichier témoin écrit quand rien n'est possible")

v, t = cas("absent", None)
dire(v == "aucun", "choix : CLAUDE.md absent → non mesurable")

v, t = cas("imports", "@RTK.md\n@SOUL.md\n" + L1 + "\n")
dire(v == "aucun", "choix : lignes @ et ligne seule → pas de couple")

# ── comparaison ──
_, t = cas("cmp", f"{L1}\n{L2}\n")
tem = t / "sortie/temoin"


def comparer(texte):
    r = t / "reponse"; r.write_text(texte)
    return temoin("comparer", str(tem), str(r))


dire(comparer(L2) == "recopie", "comparaison : recopie exacte → recopie")
dire(comparer(L2 + "\n") == "recopie", "comparaison : retour à la ligne final ignoré")
dire(comparer("  Deuxième  règle personnelle\tdu\npropriétaire ") == "recopie", "comparaison : espaces normalisés → recopie")
dire(comparer(f"« {L2} »") == "recopie", "comparaison : recopie entre guillemets → recopie")
dire(comparer("ABSENT") == "absent", "comparaison : ABSENT → absent")
dire(comparer("Je ne vois pas cette ligne.") == "inattendu", "comparaison : autre réponse → inattendu (jamais ok)")
dire(comparer("Error: authentication failed (401)") == "inattendu", "comparaison : message d'erreur du moteur → inattendu")
dire(comparer("Rate limit reached, retry later\nABSENT\n") == "absent" and comparer("« absent. »") == "absent" and comparer("**Absent**") == "absent",
     "comparaison : ABSENT tolère casse, ponctuation, guillemets ; seul sur la dernière ligne")
dire(comparer("ABSENT, je crois") == "inattendu", "comparaison : ABSENT noyé dans une phrase → inattendu")
dire(comparer("Deuxième règle personnelle") == "inattendu", "comparaison : recopie partielle → inattendu")
dire(comparer("") == "vide" and comparer("  \n ") == "vide", "comparaison : sortie vide → vide (second essai)")

# ── jamais d'affichage de la ligne témoin ──
r = subprocess.run(["bash", "-c", fonction + '\ntemoin "$@"', "x", "choisir", str(t / "CLAUDE.md"), str(t / "agent"), str(t / "commun"), str(t / "sortie")],
                   capture_output=True, text=True)
dire(L2 not in r.stdout + r.stderr, "la ligne témoin n'est ni sur la sortie ni sur l'erreur de la fonction")

# ── la question (qui cite le repère, ligne des consignes privées) ne passe jamais par l'argv ; la session n'est pas gardée ──
f = re.search(r"^consignes_perso\(\) \{.*?^\}$", tout, re.S | re.M)
appel = [l for l in (f.group(0) if f else "").splitlines() if "claude " in l and " -p" in l]
dire(len(appel) == 1 and '-p < "$d/question"' in appel[0] and "--no-session-persistence" in appel[0] and "$(cat" not in appel[0]
     and "repere" not in appel[0], "question sur stdin (fichier 0600), jamais dans l'argv ; session non gardée")
dire(bool(f) and "umask 077" in f.group(0), "fichier de la question créé en 0600")
sys.exit(ko)
