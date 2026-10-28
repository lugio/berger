"""Commandes « alire » (modulaire, lot 3) : livrable.
Servir un livrable tel quel (interface) et lire un document d'À lire dans le terminal.

Code déplacé de bin/berger : aucun comportement changé. Contrat : FAMILLE, VERBES {verbe: fonction(args, prive=False)}, AIDE, DROITS.
Une fonction de verbe rend NotImplemented quand la forme demandée n'est pas la sienne (« commande inconnue » comme avant).
Ce module n'emploie que l'API du noyau et la bibliothèque standard : voir commandes/__init__.py."""


BRUT_MAX = 20_000_000                                                      # contenu servi tel quel : 20 Mo au plus


def livrable_brut(ident, genre):
    """berger livrable <id> --brut <genre> : le contenu tel quel d'un document (Documents ou Livrables), si son genre est bien
    celui-là (le serveur de l'interface en tire ses en-têtes : le genre n'est jamais pris de la page) ; 20 Mo au plus."""
    if not re.fullmatch(r"[0-9a-f]{16}", ident or "") or genre not in set(EXTENSIONS.values()) | {"autre"}:
        sys.exit("berger livrable <id> --brut md|html|pdf|png|jpeg|gif|webp|autre")
    x = next((x for x in documents() if x["id"] == ident), None)
    if x is None: sys.exit(f"document inconnu : {ident}")
    if x["genre"] != genre: sys.exit(f"document {ident} : genre {x['genre']}, pas {genre}")
    if x["taille"] > BRUT_MAX: sys.exit(f"document {ident} : trop grand ({x['taille']} octets ; {BRUT_MAX} au plus)")
    sys.stdout.buffer.write(x["lire"]()); sys.stdout.flush(); return 0


# ─── Les verbes (corps déplacés de main(), inchangés) ───

def verbe_livrable(args, prive=False):
    if len(args) == 3 and args[1] == "--brut": sys.exit(livrable_brut(args[0], args[2]))   # contenu tel quel (interface)
    return NotImplemented


def verbe_lire(args, prive=False):
    if not (args and args[0].isdigit()): sys.exit(lire_interactif())
    try: n = int(args[0])
    except ValueError as e: raise Refus(*e.args) from None             # « ² » est un chiffre pour isdigit() mais pas pour int() : la ValueError d'avant, la famille n'est pas écartée
    sys.exit(lire_document(n, "--sans-pager" in args))


FAMILLE = "alire"
VERBES = {"livrable": verbe_livrable, "lire": verbe_lire}
PASSE = {"lire": (Refus,)}          # le seul refus de lire (numéro que int() refuse) sort tel quel ; tout autre défaut écarte la famille
AIDE = {
    "lire": "berger lire [n°] [--sans-pager]    un document d'À lire dans le terminal (sans numéro : la liste, au choix)",
    "livrable": "berger livrable <id> --brut <genre> un document tel quel (Livrables, Documents ; genre vérifié ; pour l'interface)",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}
