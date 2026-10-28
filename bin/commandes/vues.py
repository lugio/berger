"""Commandes « vues » (modulaire, lot 3 bis) : les vues, une fois (texte ou données JSON).

Code déplacé de bin/berger (lot 3 bis) : aucun comportement changé. Contrat : FAMILLE, VERBES {verbe: fonction(args, prive=False)}, AIDE, DROITS.
Une fonction de verbe rend NotImplemented quand la forme demandée n'est pas la sienne (« commande inconnue » comme avant).
Ce module n'emploie que l'API du noyau et la bibliothèque standard : voir commandes/__init__.py."""


# ─── Les verbes (corps déplacés de bin/berger, inchangés) ───

def verbe_vues(args, prive=False):
    l = liste_vues()
    if "--json" in args: print(json.dumps(l, ensure_ascii=False, indent=1))
    else: print("\n".join(f"{v['type']:<12} {v['onglet']:<7} {v['titre']}" + ("" if v["donnees"] else "  (texte seulement)") for v in l["vues"]))


FAMILLE = "vues"
VERBES = {"vues": verbe_vues}
AIDE = {
    "vues": "berger vues [--json]                les vues connues (type, onglet, titre, données ou texte seulement)",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}
