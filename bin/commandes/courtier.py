"""Le courtier (modulaire, lot 4d, partie « courtier ») : décider d'une validation, redémarrer le courtier, lancer un agent ou un moteur de plus, donner les
paramètres du moteur à un pont.

Les verbes ne font qu'aiguiller : les ACTIONS passent par les services du noyau (decider_validation, redemarrer_courtier, lancer_agent, ouvrir_moteur,
parametres_moteur : noyau/actions.py), dont le geste reste au cœur. Aucun contrôle ici : la décision (fichier atomique, durée d'un accès web, file tenue), le
redémarrage (marque de fermeture, attente, contrôle, retour arrière), le lancement (bac à sable, dossier temporaire, admission et bascule du moteur, arguments
stricts) sont dans le geste ; les droits entre agents et les règles de validation au courtier. Corps des verbes : ceux de bin/berger, mot pour mot, sauf
`--essai`, lu par `_entier` (son refus sort tel qu'avant), et `args`, dont le corps entier est le geste (il exige le bac à sable avant de lire le moteur)."""

FAMILLE = "courtier"


def _opt(args, nom): return args[args.index(nom) + 1] if nom in args else None


def _entier(texte):
    """int() d'une option (--essai) : son refus est la ValueError d'avant, même message (Refus, qui ne fait pas écarter la famille)."""
    try: return int(texte)
    except ValueError as e: raise Refus(*e.args) from None


def verbe_valider(args, prive=False): decider_validation(args[0], "valider", _opt(args, "--duree"), _opt(args, "--empreinte"))
def verbe_refuser(args, prive=False): decider_validation(args[0], "refuser", _opt(args, "--duree"), _opt(args, "--empreinte"))

def verbe_courtier(args, prive=False):                                # n'interrompt jamais une demande en cours
    if args[:1] != ["redemarrer"]: return NotImplemented
    sys.exit(redemarrer_courtier(_opt(args, "--controle"), _entier(_opt(args, "--essai") or 1), _opt(args, "--publier")))

def verbe_lancer(args, prive=False): lancer_agent(args[0], args[1] if len(args) > 1 else None)
def verbe_moteur(args, prive=False): ouvrir_moteur(args[0], args[1])
def verbe_args(args, prive=False): parametres_moteur(args)             # pour un autre accès (ex. pont Telegram) : mêmes réglages qu'Herdr


VERBES = {"valider": verbe_valider, "refuser": verbe_refuser, "courtier": verbe_courtier, "lancer": verbe_lancer, "moteur": verbe_moteur, "args": verbe_args}
AIDE = {
    "valider": "berger valider <n°> [--duree 8h]    ta décision : le courtier exécute (accès web d'un agent : fixe sa durée)",
    "refuser": "berger refuser <n°>                 ta décision : le courtier abandonne",
    "courtier": "berger courtier redemarrer [--controle <commit>]   redémarre le courtier SANS couper une demande en cours",
    "lancer": "berger lancer <agent> [moteur]      ouvre l'agent en interactif dans ce terminal",
    "moteur": "berger moteur <agent> <moteur>      ouvre un moteur de plus pour l'agent, à la demande",
    "args": "berger args <agent> <moteur> [--non-interactif]   dossier, arguments et variables du moteur (JSON), pour un pont",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}
# Ce qui passe sans écarter la famille : l'IndexError d'un argument manquant (comme avant), un refus d'usage (Refus : --essai illisible) et une panne du CŒUR
# sortie d'un service d'action (ErreurService : commandes.lancer ressort l'exception d'origine, telle qu'avant). Toute autre erreur dans la famille l'écarte, nommée.
PASSE = {v: (IndexError, Refus, ErreurService) for v in VERBES}
