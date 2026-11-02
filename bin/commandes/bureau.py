"""Commandes « bureau » (modulaire, lot 3 bis) : ce qui s'affiche sur le bureau et dans les barres : titres Herdr, barre d'état Claude Code, notification.

Code déplacé de bin/berger (lot 3 bis) : aucun comportement changé. Contrat : FAMILLE, VERBES {verbe: fonction(args, prive=False)}, AIDE, DROITS.
Une fonction de verbe rend NotImplemented quand la forme demandée n'est pas la sienne (« commande inconnue » comme avant).
Ce module n'emploie que l'API du noyau et la bibliothèque standard : voir commandes/__init__.py."""


# ─── Les verbes (corps déplacés de bin/berger, inchangés) ───

def verbe_titres(args, prive=False): [mettre_a_jour_titres(a) for a in agents()]

def verbe_statusline(args, prive=False): statusline(args[0])                         # appelé par Claude Code (réglage statusLine)

def verbe_notifier(args, prive=False):
    if args not in (["--stdin"], ["--stdin", "--urgent"]):
        raise Refus("berger notifier --stdin [--urgent] ; tableau JSON titre et texte sur stdin")
    try: valeurs = json.loads(entree_privee())
    except ValueError: raise Refus("notification JSON invalide") from None
    if not isinstance(valeurs, list) or len(valeurs) != 2 or not all(isinstance(v, str) for v in valeurs):
        raise Refus("notification : deux textes requis")
    notifier(*valeurs, urgent="--urgent" in args)


FAMILLE = "bureau"
VERBES = {"titres": verbe_titres, "statusline": verbe_statusline, "notifier": verbe_notifier}
PASSE = {"notifier": (Refus,), "statusline": (IndexError,)}   # refus d'usage de notifier (Refus) ; statusline sans agent : l'IndexError d'avant, non interceptée
AIDE = {
    "titres": "berger titres                       remet à jour les titres Herdr de tous les agents",
    "statusline": "berger statusline <agent>           barre d'état de Claude Code (réglage statusLine posé par regenerer) ; relève le quota",
    "notifier": "berger notifier --stdin [--urgent]  notification du bureau : tableau JSON [titre, texte] sur stdin",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}
