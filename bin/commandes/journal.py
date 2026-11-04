"""Commandes « journal » (modulaire, lot 3 bis) : le journal de l'agent.

Code déplacé de bin/berger (lot 3 bis) : aucun comportement changé. Contrat : FAMILLE, VERBES {verbe: fonction(args, prive=False)}, AIDE, DROITS.
Une fonction de verbe rend NotImplemented quand la forme demandée n'est pas la sienne (« commande inconnue » comme avant).
Ce module n'emploie que l'API du noyau et la bibliothèque standard : voir commandes/__init__.py."""


# ─── Les verbes (corps déplacés de bin/berger, inchangés) ───

def verbe_noter(args, prive=False):                                                  # l'agent écrit à son journal ; l'heure vient de Berger, pas du modèle
    if args != ["--stdin"]: raise Refus('berger noter --stdin ; texte positionnel refusé')
    a = os.environ.get("BERGER_AGENT") or sys.exit("noter : BERGER_AGENT absent (à lancer depuis un agent Berger)")
    texte = entree_privee().strip()
    if not texte: raise Refus('journal : texte vide refusé')
    journal(a, " ".join(texte.split())); print("noté")


FAMILLE = "journal"
VERBES = {"noter": verbe_noter}
PASSE = {"noter": (Refus,)}        # ses refus d'usage (Refus) sortent tels quels ; tout autre défaut écarte la famille
AIDE = {
    "noter": "berger noter --stdin                 (depuis un agent) une ligne horodatée, texte privé sur stdin",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}
