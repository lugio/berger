#!/usr/bin/env python3
"""« À lire » qui se vide (spec docs/plans/2026-10-13-interface-spec.md §6 quinquies, point 3) — sans modèle, installation
JETABLE (tests/_jeu_vues.py, jeu avec marquages). Une note qui déclare `Lié à : validation <n>` ou `Lié à : demande
<projet>,<sujet>` compte comme LUE dès que l'objet est réglé (écriture décidée, demande fusionnée) — pour une note d'un agent
Claude (vigie) comme d'un agent Codex (scribe) — ; liée à un objet en cours, ou sans lien, elle reste à lire ; rien n'est
supprimé ; elle quitte « À toi de décider » ; le texte de Herdr dit pourquoi. Usage : python3 tests/alire-se-vide.py"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t, marquages=True)
    b = lambda *a: J.commande(i, env, *a)
    d = json.loads(b("vue", "alire", "--json").stdout)["donnees"]
    par = {x["titre"]: x for x in d["documents"]}
    go, espace = par["Il faut ton go pour redémarrer"], par["L'espace de vigie attend ta décision"]
    pied, menu = par["Le pied de page attend la fusion"], par["Le menu attend la relecture"]
    dire(go["lu"] and go["regle"] and "4" in go["regle"], f"agent Claude : note liée à une écriture DÉCIDÉE → lue d'elle-même ({go['regle']})")
    dire(pied["lu"] and pied["regle"] and "fusionnée" in pied["regle"], f"agent Codex : note liée à une demande FUSIONNÉE → lue d'elle-même ({pied['regle']})")
    dire(not espace["lu"] and espace["regle"] is None and not menu["lu"] and menu["regle"] is None,
         "liée à une écriture en attente ou à une demande à relire : reste à lire (Claude et Codex)")
    sans = par["Rétention des sauvegardes"]
    dire(not sans["lu"] and sans["regle"] is None, "note sans lien : reste à lire")
    dire(d["non_lus"] == sum(not x["lu"] for x in d["documents"]), "le compte « non lus » ne compte plus les notes réglées")
    dire(all((i / "agents" / a / "a-lire" / f).is_file() for a, f in (("vigie", "2026-10-13_go-redemarrage.md"), ("scribe", "2026-10-13_pied.md"))),
         "rien n'est supprimé : les notes réglées restent sur le disque")
    dec = json.loads(b("vue", "decisions", "--json").stdout)["donnees"]["decisions"]
    dire(not any("Il faut ton go pour redémarrer" in json.dumps(x, ensure_ascii=False) for x in dec),
         "la « Décision attendue » d'une note réglée quitte « À toi de décider »")
    texte = "\n".join(J.executer(i, env, "print(json.dumps(g['VUES']['alire'].rendre(300, 40)))"))
    dire("réglé : écriture n° 4" in texte and "réglé : demande demo,pied fusionnée" in texte, "Herdr : la ligne dit pourquoi la note est réglée")
    regles = J.executer(i, env, "print(json.dumps({a: 'Lié à : validation <n>' in g['regles_agent'](a) for a in ('vigie', 'scribe')}))")
    dire(regles == {"vigie": True, "scribe": True}, f"la règle « Lié à : » est dans les consignes d'un agent Claude et d'un agent Codex ({regles})")
    # une écriture décidée pendant que la page est ouverte : la note liée devient lue sans rien écrire d'autre
    v = i / "courtier/validations"; (v / "1.fait.json").write_text(json.dumps({**json.loads((v / "1.json").read_text()), "etat": "validé et exécuté"}))
    d2 = {x["titre"]: x for x in json.loads(b("vue", "alire", "--json").stdout)["donnees"]["documents"]}
    dire(d2["L'espace de vigie attend ta décision"]["lu"], "l'écriture liée vient d'être décidée : la note devient lue")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
