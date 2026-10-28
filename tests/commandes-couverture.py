#!/usr/bin/env python3
"""Couverture des commandes (modulaire, lot 3, docs/plans/2026-10-27-modulaire-spec.md § Tests) : les 60 verbes de bin/berger au 27/10/2026 (figés ici)
sont EXACTEMENT l'union des VERBES des familles de bin/commandes/ ; chaque verbe a une ligne d'AIDE et des DROITS ; aucun verbe n'est déclaré deux
fois (les deux familles seraient écartées et nommées) ; le tableau verbe → famille du manuel dit la même chose que le registre ; les verbes à entrée
privée sont ceux de DROITS et refusent le texte positionnel avec le MÊME message qu'avant ; un verbe inconnu garde son message. Une installation JETABLE.
Usage : python3 tests/commandes-couverture.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    print(("ok     " if ok else "ÉCHEC  ") + texte); ko += 0 if ok else 1


# Les 60 verbes d'aujourd'hui (le `cmd == …` de l'ancien main(), valider et refuser compris), figés : un verbe oublié ou ajouté sans test échoue ici.
VERBES_FIGES = """abonnement-claude agent annonce-outil args besoin besoin-ranger coffre courtier crochet-equipe delegation-suivi demander echange entretien
equipe espace espace-voulu etat fin-mission installer interface lancer lire livrable mcp-enveloppe memoire message-deposer message-remettre mission
moteur noter notifier nouveau panneau parler parler-interactif planificateur projet rapport-mission refaire-espace refuser regenerer relancer
reprendre restaurer reveil sauvegarder secrets statusline suivi superviser tache titres validations valider veille verifier-depot
verifier-sauvegarde vue vues web""".split()
PRIVES = {"mission", "message-deposer", "equipe", "projet"}                    # le tuple écrit en dur dans l'ancien main()
# Les verbes déplacés (lot 3, puis lot 3 bis), avec leur famille : seuls ceux qui n'emploient QUE l'API du noyau (relecture du 28/10 : plus aucun emprunt au
# cœur ni au noyau hors API). Les 50 autres sont inscrits par `transition`, au cœur jusqu'au lot 4.
LOT3 = {"livrable": "alire", "veille": "veille"}
LOT3BIS = {"lire": "alire", "etat": "etat", "validations": "etat", "vues": "vues", "titres": "bureau", "statusline": "bureau", "notifier": "bureau", "noter": "journal"}
# Le tri : ces verbes appellent le mur, le coffre, les secrets, le courtier, les missions, les messages, les équipes, l'installation, la
# sauvegarde ou l'audit (directement ou par la fonction qu'ils appellent) : ils RESTENT au cœur pour le lot 4.
RESTENT = {"planificateur", "superviser", "entretien", "espace", "nouveau", "regenerer", "agent", "web", "interface", "valider", "refuser"}
# Renvoyés au cœur par la relecture : identifiants (abonnement-claude), bac à sable et réglages moteur du mur et du MCP (reprendre, relancer, par demarrer_agent).
RENVOYES = {"abonnement-claude", "reprendre", "relancer", "memoire", "vue"}   # vue : `vue fiche --json` atteint masques (le mur) par vues/fiche.py ; memoire : écrit MEMORY.md (que l'agent ne peut pas écrire) avec une sauvegarde .avant

dire(len(VERBES_FIGES) == 60 and len(set(VERBES_FIGES)) == 60, "la liste figée compte 60 verbes distincts")
dire(set(LOT3) | set(LOT3BIS) | RESTENT | RENVOYES <= set(VERBES_FIGES) and not (set(LOT3) | set(LOT3BIS)) & (RESTENT | RENVOYES), "le tri : aucun verbe déplacé ne figure parmi ceux qui restent au cœur pour le mur, le coffre, les identifiants ou le courtier")

with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp); _produit.copier(SRC, t); (t / "config.toml").write_text('proprietaire = "Camille"\n')
    env = {**os.environ, "BERGER_DIR": str(t), "HOME": str(t)}
    prog = ("import json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); c = g['commandes']\n"
            "print(json.dumps({'verbes': sorted(c.VERBES), 'aide': c.AIDES, 'droits': c.DROITS, 'famille': c.FAMILLE_DE, 'refusees': c.COMMANDES_REFUSEES,\n"
            "                  'par_famille': {n: sorted(m.VERBES) for n, m in c.FAMILLES.items()}}))\n") % str(t / "bin/berger")
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {"verbes": [], "aide": {}, "droits": {}, "famille": {}, "refusees": {}, "par_famille": {}}; print(r.stderr[-400:])
    dire(not x["refusees"], f"aucune famille écartée dans une installation saine ({x['refusees'] or 'aucune'})")
    dire(sorted(x["verbes"]) == sorted(VERBES_FIGES), "l'union des VERBES des familles chargées EST la liste figée des 60 verbes"
         + ("" if sorted(x["verbes"]) == sorted(VERBES_FIGES) else f" — en trop : {sorted(set(x['verbes']) - set(VERBES_FIGES))}, manquants : {sorted(set(VERBES_FIGES) - set(x['verbes']))}"))
    total = sum(len(v) for v in x["par_famille"].values())
    dire(total == len(x["verbes"]) == 60, f"aucun verbe n'est déclaré par deux familles ({total} déclarations pour {len(x['verbes'])} verbes)")
    manque = [v for v in VERBES_FIGES if not (x["aide"].get(v) or "").strip()]
    dire(not manque, f"une ligne d'AIDE par verbe (sans aide : {manque or 'aucun'})")
    dire(all(f"berger {v}" in x["aide"][v] or v in x["aide"][v] for v in x["aide"]), "chaque ligne d'AIDE nomme son verbe")
    dire(all(set(d) == {"prive", "cas_go"} for d in x["droits"].values()) and set(x["droits"]) == set(x["verbes"]), "des DROITS déclarés pour chaque verbe (prive, cas_go)")
    dire({v for v, d in x["droits"].items() if d["prive"]} == PRIVES, f"les verbes à entrée privée déclarés sont exactement {sorted(PRIVES)}")
    dire(all(x["famille"].get(v) == f for v, f in {**LOT3, **LOT3BIS}.items()), "les 10 verbes déplacés sont dans leur famille : " + ", ".join(sorted(set(LOT3.values()) | set(LOT3BIS.values()))))
    dire(all(x["famille"].get(v) == "transition" for v in RESTENT | RENVOYES), "les verbes triés « au cœur » (dont abonnement-claude, reprendre, relancer) sont inscrits par la famille de transition, dans le même registre")
    dire(sum(1 for f in x["famille"].values() if f == "transition") == 50, "50 verbes restent au cœur jusqu'au lot 4 (inscrits par `transition`)")
    dire(set(x["aide"]) == set(x["verbes"]), "l'AIDE et les VERBES décrivent exactement les mêmes verbes (une aide seule ne couvre rien)")
    dire(_produit.verbes_declares(SRC) == set(VERBES_FIGES), "la lecture statique des verbes (tests/_produit.py : VERBES et VERBES_COEUR recoupés avec AIDE) donne les 60 verbes")

    # le tableau verbe → famille du manuel dit la même chose que le registre
    manuel = (SRC / "docs/manuel.md").read_text(encoding="utf-8")
    lignes = {m.group(1): m.group(2) for m in re.finditer(r"^\s*\| `([a-z-]+)` \| ([a-z]+) \|", manuel, re.M)}
    dire(lignes == x["famille"], "le tableau « verbe → famille » du manuel est celui du registre"
         + ("" if lignes == x["famille"] else f" — écarts : {sorted(k for k in set(lignes) | set(x['famille']) if lignes.get(k) != x['famille'].get(k))}"))

    # entrée privée déclarée : le MÊME refus qu'avant (texte positionnel), et le même pour un verbe qui n'est pas privé
    refus = "usage : berger --stdin ; commande et paramètres dans un tableau JSON UTF-8, texte positionnel refusé"
    for v in sorted(PRIVES):
        r = subprocess.run([str(t / "bin/berger"), v, "x", "y"], env=env, capture_output=True, text=True)
        dire(r.returncode == 1 and r.stderr.strip() == refus and not r.stdout, f"{v} sans --stdin : refusé avec le message d'avant ({r.stderr.strip()[:80]!r})")
    r = subprocess.run([str(t / "bin/berger"), "--stdin"], input=json.dumps(["equipe"]), env=env, capture_output=True, text=True)
    dire(r.returncode != 0 and r.stderr.strip() != refus and "berger equipe ouvrir" in r.stderr, "en tableau JSON, le même verbe est servi (son propre usage, plus le refus positionnel)")
    r = subprocess.run([str(t / "bin/berger"), "--stdin"], input=json.dumps(["--stdin"]), env=env, capture_output=True, text=True)
    dire(r.returncode != 0 and "commande privée : tableau de textes requis" in r.stderr + r.stdout, "un tableau JSON qui rappelle --stdin reste refusé")
    # un verbe inconnu, et une forme inconnue d'un verbe connu : « commande inconnue » suivi de l'aide, comme avant
    for argv in (["zzz"], ["coffre", "zzz"], ["livrable", "x"], ["veille", "x"], ["installer"]):
        r = subprocess.run([str(t / "bin/berger"), *argv], env=env, capture_output=True, text=True)
        dire(r.returncode == 1 and r.stderr.startswith(f"commande inconnue : {argv[0]}\n\nberger — des agents en fichiers texte"), f"berger {' '.join(argv)} : « commande inconnue » et l'aide du programme")
    # l'aide du programme n'a pas changé de présentation : chaque verbe annoncé y reste
    r = subprocess.run([str(t / "bin/berger"), "aide"], env=env, capture_output=True, text=True)
    dire(r.returncode == 0 and "berger etat [--json]" in r.stdout and "berger courtier redemarrer" in r.stdout, "berger aide : la même aide qu'avant")

sys.exit(1 if ko else 0)
