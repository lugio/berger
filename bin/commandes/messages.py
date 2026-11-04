"""Les messages (modulaire, lot 4b) : déposer un message à sens unique, remettre une file, suivre une délégation, poser une question, parler à un agent,
tracer un échange.

Les verbes ne font qu'aiguiller : les ACTIONS passent par les services du noyau (deposer_message, remettre_messages, suivre_delegation, poser_question,
parler_agent, tracer_echange : noyau/actions.py), dont le geste reste au cœur. Aucun contrôle ici : droits entre agents (ecrire:<agent>, deleguer:<agent>),
texte, secrets et débit d'ecrire sont au courtier, avant l'appel ; file et verrou, agent sans panneau, bac à sable et bascule de moteur, dans le geste.
Corps des verbes : ceux de bin/berger, mot pour mot, sauf leurs refus d'usage, levés par `Refus` (ils sortent en ValueError, même message, comme avant)."""

FAMILLE = "messages"


def _opt(args, nom): return args[args.index(nom) + 1] if nom in args else None


def _entree(decoder=False):
    """L'entrée que le courtier passe sur stdin (lue, décodée en JSON si `decoder`). Ses erreurs de lecture et de décodage (UnicodeDecodeError,
    JSONDecodeError, ValueError d'un entier trop long, RecursionError d'une imbrication trop profonde : renvoi n° 89) sortent telles qu'avant, sans écarter
    la famille : portées par ErreurService, dont commandes.lancer ressort l'origine. À cet endroit seulement : PASSE ne s'élargit pas."""
    try:
        texte = sys.stdin.buffer.read().decode("utf-8")
        return json.loads(texte) if decoder else texte
    except (ValueError, RecursionError) as e: raise ErreurService("entrée illisible", e) from e


def verbe_message_deposer(args, prive=False): print(deposer_message(args[0], args[1], " ".join(args[2:])))   # usage interne (courtier, berger-outil ecrire)
def verbe_message_remettre(args, prive=False): print("file vide" if remettre_messages(args[0]) else "messages en attente")   # usage interne
def verbe_delegation_suivi(args, prive=False): print(suivre_delegation(args[0], args[1], _entree(decoder=True)))  # usage interne (courtier, deleguer)

def verbe_echange(args, prive=False):                                 # usage interne (courtier, outils d'équipe) : de a genre texte
    tracer_echange(args[0], args[1], args[2], _entree() if args[3:] == ["--stdin"] else " ".join(args[3:]))

def verbe_demander(args, prive=False):
    opt = lambda nom: _opt(args, nom)
    if not args:
        sys.exit("usage : berger demander <agent> --stdin [--moteur m] [--sortie f]")
    if len(args) < 2 or args[1] != "--stdin":
        raise Refus("berger demander <agent> --stdin [--moteur m] [--sortie f] ; texte positionnel refusé")
    reste = args[2:]
    if len(reste) % 2 or any(reste[i] not in ("--moteur", "--sortie") for i in range(0, len(reste), 2)):
        raise Refus("options de demander invalides")
    texte, m, echecs = poser_question(args[0], entree_privee(), opt("--moteur"), opt("--sortie"))
    for e in echecs: print(e, file=sys.stderr)
    print(f"moteur : {m or 'aucun'}", file=sys.stderr); print(texte); sys.exit(0 if m else 1)

def verbe_parler(args, prive=False):
    if len(args) < 2 or args[1] != "--stdin":
        raise Refus("berger parler <agent> --stdin [--moteur m] [--de qui] [--sans-echange] ; texte positionnel refusé")
    options = {}; reste = iter(args[2:])
    for x in reste:
        if x not in ("--moteur", "--de", "--sans-echange") or x in options:
            raise Refus("options de parler invalides")
        valeur = True if x == "--sans-echange" else next(reste, None)
        if valeur is None or (isinstance(valeur, str) and valeur.startswith("--")):
            raise Refus("option de parler sans valeur")
        options[x] = valeur
    parler_agent(args[0], entree_privee(), options.get("--moteur"),
                 de=False if "--sans-echange" in options else options.get("--de"))

def verbe_parler_interactif(args, prive=False):                       # pour la fenêtre Herdr prefix+a
    noms = agents(); print("À qui parler ?  " + "   ".join(f"{i + 1}. {conf(x)['icone']} {conf(x)['nom']}" for i, x in enumerate(noms)))
    try:
        choix = noms[int(input("numéro : ")) - 1]; msg = input(f"message pour {conf(choix)['nom']} : ").strip()
        if msg: parler_agent(choix, msg)
    except (ValueError, IndexError, EOFError): print("annulé")
    except ErreurService as e:                                        # ce que le geste levait était attrapé ici avant le service : même sortie
        if not isinstance(e.origine, (ValueError, IndexError, EOFError)): raise
        print("annulé")


VERBES = {"message-deposer": verbe_message_deposer, "message-remettre": verbe_message_remettre, "delegation-suivi": verbe_delegation_suivi,
          "echange": verbe_echange, "demander": verbe_demander, "parler": verbe_parler, "parler-interactif": verbe_parler_interactif}
AIDE = {
    "message-deposer": "berger --stdin [\"message-deposer\", de, a, texte]   (courtier, berger-outil ecrire) dépose un message à sens unique",
    "message-remettre": "berger message-remettre <agent>      remet à l'agent les messages en attente (usage interne)",
    "delegation-suivi": "berger delegation-suivi <demandeur> <cible>   (courtier, deleguer) trace d'une délégation, JSON sur stdin",
    "echange": "berger echange <de> <a> <genre> <texte>   (courtier, outils d'équipe) une ligne dans les échanges",
    "demander": "berger demander <agent> --stdin [--moteur m] [--sortie f]   une question, conversation neuve, bascule si panne",
    "parler": "berger parler <agent> --stdin       écrit à l'agent dans sa conversation en cours (Herdr)",
    "parler-interactif": "berger parler-interactif            fenêtre Herdr prefix+a : choisir l'agent, écrire le message",
}
DROITS = {v: {"prive": v == "message-deposer", "cas_go": None} for v in VERBES}
# Ce qui passe sans écarter la famille : l'IndexError d'un argument manquant (comme avant), un refus d'usage (Refus) et une panne du CŒUR sortie d'un
# service d'action (ErreurService : commandes.lancer ressort l'exception d'origine, telle qu'avant), qui porte aussi l'entrée illisible de delegation-suivi
# et d'echange (_entree). Toute autre erreur, dans la famille, l'écarte, nommée.
PASSE = {v: (IndexError, Refus, ErreurService) for v in VERBES}
