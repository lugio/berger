"""Les équipes de développement (modulaire, lot 4c) : ouvrir, fermer et lister les développeurs d'un projet, ses sites permis, le go du propriétaire,
les dossiers de projet partagés, et le crochet d'écriture d'un développeur.

Les verbes ne font qu'aiguiller : les LECTURES passent par l'API (equipe_liste, projet_liste, domaines_projet), les ACTIONS par les services du noyau
(ouvrir_developpeur, fermer_developpeur, changer_domaine, inscrire_go, ouvrir_projet, fermer_projet, jouer_crochet : noyau/actions.py), dont le geste
reste au cœur. Aucun contrôle ici : rôle (le chef seul ouvre et ferme ; chef ou coordinateur pour un go ou un projet), go inscrit, plafond [missions] max,
moteur et modèle, copie et branche, membres, nom de site exact sont dans le geste ; les droits d'équipe (chef, coordinateur, non-membre) et les
validations au courtier. Corps des verbes : ceux de bin/berger, mot pour mot (l'usage et le projet connu restent la lecture des arguments, comme avant),
sauf l'appel des trois lectures, passé par `_lire` (une donnée illisible sort telle qu'avant)."""

FAMILLE = "equipes"


def _opt(args, nom): return args[args.index(nom) + 1] if nom in args else None


def _lire(lecture):
    """Une LECTURE de l'API (equipe_liste, projet_liste, domaines_projet). Ce qu'elle lève vient d'une donnée d'équipe illisible (demande de fusion,
    checklist, registre des projets, sites permis : JSON invalide ou mal formé, non UTF-8, imbrication trop profonde ; renvoi n° 93) et sort telle qu'avant, sans
    écarter la famille : portée par ErreurService, dont commandes.lancer ressort l'origine. À cet endroit seulement : PASSE reste le même, une erreur
    ailleurs dans le verbe écarte toujours la famille ; un refus (sys.exit) passe tel quel."""
    try: return lecture()
    except Exception as e: raise ErreurService("lecture illisible", e) from e


def verbe_equipe(args, prive=False):                                  # ouvrir <projet> <sujet> "<mission>" | fermer <projet> <sujet> | liste <projet>
    opt = lambda nom: _opt(args, nom)
    q = args[1:]; pos, i = [], 0                                      # | domaine <projet> ajouter|retirer <nom> [--essai] | domaines <projet>
    while i < len(q):
        if q[i] in ("--par", "--moteur", "--modele"): i += 2; continue
        if q[i] != "--essai": pos.append(q[i])
        i += 1
    usage = ("berger equipe ouvrir <projet> <sujet> \"<mission>\" | fermer <projet> <sujet> | liste <projet> | domaine <projet> "
             f"ajouter|retirer <nom> [--essai] | domaines <projet> | go <projet> <sujet> <cas> <spec> [--essai] — équipes : {', '.join(EQUIPES) or 'aucune'}")
    besoin = {"ouvrir": 2, "fermer": 2, "liste": 1, "domaine": 3, "domaines": 1, "go": 4}
    if not args or args[0] not in besoin or len(pos) < besoin[args[0]]: sys.exit(usage)
    if pos[0] not in EQUIPES: sys.exit(f"projet d'équipe inconnu : {pos[0]} — {usage}")
    if args[0] == "ouvrir": print(ouvrir_developpeur(pos[0], pos[1], " ".join(pos[2:]), opt("--par") or PROPRIETAIRE, opt("--moteur"), opt("--modele")))
    elif args[0] == "fermer": print(fermer_developpeur(pos[0], pos[1], opt("--par") or PROPRIETAIRE))
    elif args[0] == "liste": print(json.dumps(_lire(lambda: equipe_liste(pos[0])), ensure_ascii=False, indent=1))
    elif args[0] == "domaine" and len(pos) == 3: print(changer_domaine(pos[0], pos[1], pos[2], opt("--par") or PROPRIETAIRE, "--essai" in args))
    elif args[0] == "go" and len(pos) == 4: print(inscrire_go(*pos, opt("--par") or PROPRIETAIRE, "--essai" in args))
    elif args[0] == "domaines" and len(pos) == 1: print(json.dumps(_lire(lambda: domaines_projet(pos[0], signaler=False))))
    else: sys.exit(usage)

def verbe_projet(args, prive=False):                                  # ouvrir <équipe> <projet> <membres> | fermer <équipe> <projet> | liste [<équipe>]
    opt = lambda nom: _opt(args, nom)
    q = [x for i, x in enumerate(args[1:]) if x != "--par" and (i == 0 or args[1:][i - 1] != "--par")]
    if args[:1] == ["ouvrir"] and len(q) == 3: print(ouvrir_projet(q[0], q[1], q[2], opt("--par") or PROPRIETAIRE))
    elif args[:1] == ["fermer"] and len(q) == 2: print(fermer_projet(q[0], q[1], opt("--par") or PROPRIETAIRE))
    elif args[:1] == ["liste"]: print(json.dumps(_lire(lambda: projet_liste(q[0] if q else None)), ensure_ascii=False, indent=1))
    else: sys.exit("berger projet ouvrir <équipe> <projet> <membre,membre…> | fermer <équipe> <projet> | liste [<équipe>]")

def verbe_crochet_equipe(args, prive=False): jouer_crochet(args[0])            # appelé par le moteur (crochet d'un développeur)


VERBES = {"equipe": verbe_equipe, "projet": verbe_projet, "crochet-equipe": verbe_crochet_equipe}
AIDE = {
    "equipe": "berger --stdin [\"equipe\", ouvrir|fermer|liste|domaine|domaines|go, projet, …]   équipes de développement",
    "projet": "berger --stdin [\"projet\", ouvrir|fermer|liste, équipe, …]   dossier partagé d'une équipe",
    "crochet-equipe": "berger crochet-equipe <agent>        appelé par le moteur (crochet d'un développeur)",
}
DROITS = {"equipe": {"prive": True, "cas_go": None}, "projet": {"prive": True, "cas_go": None}, "crochet-equipe": {"prive": False, "cas_go": None}}
# Ce qui passe sans écarter la famille : l'IndexError d'un argument manquant (comme avant), un refus d'usage (Refus) et une panne du CŒUR sortie d'un
# service d'action (ErreurService : commandes.lancer ressort l'exception d'origine, telle qu'avant). Toute autre erreur, dans la famille ou dans une lecture,
# écarte la famille, nommée.
PASSE = {v: (IndexError, Refus, ErreurService) for v in VERBES}
