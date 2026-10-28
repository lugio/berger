"""Ce que les commandes de lecture affichent dans le terminal : état, validations en attente, documents À lire (modulaire, lot 3 bis).

Code déplacé de bin/berger : aucun comportement changé."""
import datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, tomllib, unicodedata
import importlib.util
import shutil as _sh, textwrap
from pathlib import Path
from noyau.config import *
from noyau.transport import *
from noyau.affichage import *
from noyau.agents import *
from noyau.herdr import *
from noyau.lectures import *
from noyau.registre import *


def donnees_etat():
    """Les données de `berger etat` (schéma bin/schemas/etat.schema.json) : le texte ci-dessous et `--json` en viennent."""
    return {"vues_ecartees": [{"vue": n, "cause": e} for n, e in sorted(VUES_REFUSEES.items())],
            "moteurs_ecartes": ecartes_moteurs(),
            "commandes_ecartees": ecartes_commandes(),
            "agents": [{"agent": agent_court(a), "statuts": statuts_donnees(a), "checklist": checklist_donnees(checklist(a)),
                        "a_faire": sum(not fait for fait, _ in cases(lire(dossier(a) / "TODO.md"))), "a_valider": len(pendants(a)),
                        "memoire": len(lire(fichier_memoire(a))), "memoire_max": MEMOIRE_MAX} for a in agents()]}


def etat(_=None, en_json=False):
    """Version texte simple (pour un terminal ou un script) ; le panneau « ensemble » en est la version mise en page."""
    d = donnees_etat()
    if en_json: print(json.dumps(enveloppe("etat", SCHEMAS / "etat.schema.json", d), ensure_ascii=False, indent=1)); return
    for v in d["vues_ecartees"]: print(f"⚠ vue écartée : bin/vues/{v['vue']}.py — {v['cause']}")
    for v in d["moteurs_ecartes"]: print(f"⚠ moteur écarté : bin/moteurs/{v['moteur']}.py — {v['cause']}")
    for v in d["commandes_ecartees"]: print(f"⚠ commandes écartées : bin/commandes/{v['commandes']}.py — {v['cause']}")
    for x in d["agents"]:
        ck = x["checklist"]
        st = ", ".join(f"{s['moteur']} {STATUTS.get(s['etat'], ('?',))[0]}" for s in x["statuts"]) or "pas d'espace Herdr"
        print(f"{x['agent']['icone']} {x['agent']['nom']} ({st})")
        print(f"   en cours : {ck['titre']} {ck['faites']}/{ck['total']}" + (f" — BLOQUÉ : {ck['bloque']}" if ck["bloque"] else "")
              if ck and not ck["fini"] else "   en cours : rien")
        print(f"   à faire : {x['a_faire']} · à valider : {x['a_valider']} · mémoire : {x['memoire']}/{x['memoire_max']}\n")


def validations(en_json=False):
    """Écritures demandées par les agents, en attente de ta décision."""
    l = [validation_donnees(d) for d in en_attente()]
    if en_json: print(json.dumps(enveloppe("validations", SCHEMAS / "validations.schema.json", {"validations": l}), ensure_ascii=False, indent=1)); return
    if not l: print("aucune écriture en attente de validation"); return
    for d in l:
        print(f"n° {'?' if d['n'] is None else d['n']}  {d['demande'][5:16].replace('T', ' ')}  {d['agent']['nom']} · {d['outil']} {d['verbe']}\n      {d['apercu']}")
    print("\n→ berger valider <n°>   ou   berger refuser <n°>")


def marquer_lu(doc):
    vus = lus() | {doc["cle"]}
    vus = {c for c in vus if Path(c.rsplit(":", 1)[0]).exists()}                # oublier les documents disparus
    tmp = LECTURES.with_suffix(".tmp"); tmp.write_text(json.dumps(sorted(vus))); os.replace(tmp, LECTURES)


def lire_document(n, sans_pager=False):
    docs = documents_a_lire()
    if not 1 <= n <= len(docs): print(f"pas de document n° {n} (il y en a {len(docs)})"); return 1
    d = docs[n - 1]; w = _sh.get_terminal_size((100, 40)).columns
    texte = "\n".join(rendre_markdown(lire(d["chemin"]), w)) + "\n"
    if sans_pager or not sys.stdout.isatty(): sys.stdout.write(texte)
    else: subprocess.run(["less", "-R", "-S", "-X", "-F"] if shutil.which("less") else ["cat"], input=texte, text=True)
    marquer_lu(d); return 0


def lire_interactif():
    """L'onglet « À lire » : la liste, un numéro pour ouvrir (q dans le document pour revenir), Entrée pour rafraîchir."""
    while True:
        w, h = _sh.get_terminal_size((100, 40))
        sys.stdout.write("\033[H\033[J" + "\n".join(VUES["alire"].vue_alire(w - 1, h)) + "\n\n" + PALE + "  numéro pour lire · Entrée pour rafraîchir · q pour quitter" + R + "\n  › ")
        sys.stdout.flush()
        try: choix = input().strip()
        except (EOFError, KeyboardInterrupt): return
        if choix.lower() == "q": return
        if choix.isdigit(): lire_document(int(choix))


__all__ = ('donnees_etat', 'etat', 'validations', 'marquer_lu', 'lire_document', 'lire_interactif',)
