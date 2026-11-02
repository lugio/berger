"""Les services d'ACTION du noyau (modulaire, lots 4a, 4b et 4c) : ce qu'une famille de commandes peut FAIRE, par un nom fixe et une signature fixe.

L'API de lecture (noyau/api.py API) est donnée à tous les modules ; l'API d'action (noyau/api.py ACTIONS = les noms ci-dessous) aux SEULES familles de
commandes, jamais à une vue ni à un moteur. Un service garde ses contrôles lui-même (agent inscrit, une mission à la fois, plafond [missions] max,
moteur et modèle par noyau.modeles, checklist finie, refus de fusion…) : la commande n'en fait aucun, et l'appeler sans elle ne les contourne pas.
Ce qui passe par demarrer_agent ou le mur (ouvrir un agent en mission, fermer son panneau) reste dans le cœur : bin/berger y branche au démarrage
la fonction qui fait le geste (`brancher`, une fois par processus, liste fermée). Ce branchement disparaît quand le lancement d'un agent
quittera bin/berger (suite du lot 4). Ce qui sort du geste (une Exception, jamais sys.exit) est enveloppé dans ErreurService, l'origine gardée en
cause : la famille le déclare dans PASSE et commandes.lancer ressort l'origine, telle qu'avant. Seul import : noyau.ecarts, qui n'en a aucun
(bin/commandes/ charge l'API sans config.toml).
Lot 4b : les messages (déposer, remettre, suivre une délégation, poser une question, parler, tracer un échange) et les besoins (ranger, clore, annoncer
un outil) : mêmes règles, gestes au cœur. Plus `journal` et `notifier`, fonctions du NOYAU qui écrivent (le journal d'un agent, notifications.log) :
sorties de l'API de lecture, données aux seules familles telles quelles (aucun contrôle à garder, rien à envelopper : une erreur sort comme avant).
Lot 4c : les équipes (ouvrir et fermer un développeur, changer un site permis, inscrire un go, ouvrir et fermer un projet, jouer le crochet d'un développeur) :
mêmes règles, gestes au cœur. Plus lire_document, lire_interactif (marquent un document lu), mettre_a_jour_titres (renomme les panneaux Herdr) et
statusline (relève le quota) : fonctions du NOYAU qui écrivent, sorties de l'API de lecture comme journal et notifier."""
from noyau.ecarts import ErreurService

NOMS = ("confier_mission", "terminer_mission", "deposer_message", "remettre_messages", "suivre_delegation", "poser_question", "parler_agent",
        "tracer_echange", "ranger_besoin", "clore_besoin", "annoncer_outil", "journal", "notifier",
        "ouvrir_developpeur", "fermer_developpeur", "changer_domaine", "inscrire_go", "ouvrir_projet", "fermer_projet", "jouer_crochet",
        "lire_document", "lire_interactif", "mettre_a_jour_titres", "statusline")
DU_NOYAU = ("journal", "notifier", "lire_document", "lire_interactif", "mettre_a_jour_titres", "statusline")   # fonctions du noyau, prises dans leur module
                                                # au chargement des commandes (pas de geste du cœur à brancher)
_SERVICES = {}                                  # nom -> fonction du cœur qui fait le geste (posée par bin/berger)


def brancher(services):
    """Pose les fonctions du cœur derrière les services : seulement des noms de NOMS, seulement des fonctions."""
    hors = sorted(set(services) - set(NOMS))
    if hors: raise NameError(f"service hors de la liste ACTIONS : {', '.join(hors)}")
    du_noyau = sorted(set(services) & set(DU_NOYAU))
    if du_noyau: raise NameError(f"service du noyau, jamais branché par le cœur : {', '.join(du_noyau)}")
    for nom, f in services.items():
        if not callable(f): raise TypeError(f"service {nom} : pas une fonction")
    _SERVICES.update(services)


def _service(nom):
    f = _SERVICES.get(nom)
    if f is None: raise RuntimeError(f"service {nom} non branché (bin/berger le pose au démarrage)")
    return f


def _geste(nom, *args):
    """Le geste du cœur derrière le service : ce qu'il lève (Exception) sort en ErreurService, l'origine en cause ; sys.exit et Ctrl-C passent tels quels."""
    f = _service(nom)
    try: return f(*args)
    except Exception as e: raise ErreurService(f"{nom} : {type(e).__name__}: {e}", e) from e


def confier_mission(a, texte, par, moteur=None, modele=None):
    """Confie une mission à `a` de la part de `par` (MISSION.md, journal, échange, agent ouvert puis prévenu). Refus (sys.exit nommé) : agent
    inconnu, mission déjà en cours, plafond [missions] max (hors chef de projet), moteur ou modèle non permis, mission vide. → le texte de résultat."""
    return _geste("confier_mission", a, texte, par, moteur, modele)


def terminer_mission(a, par, motif=None):
    """Range la mission de `a` (historique/) et ferme son panneau (un chef de projet garde son espace). Refus (sys.exit nommé) : pas de mission en
    cours ; hors propriétaire, checklist qui ne finit pas par « Terminé » ou « Abandonné » (sauf refus de fusion du propriétaire). → le texte de résultat."""
    return _geste("terminer_mission", a, par, motif)


def deposer_message(de, a, texte):
    """Dépose un message de `de` dans la file de `a` (messages/attente/) et le remet s'il tourne. Le courtier a vérifié le droit (ecrire:<agent>), le texte,
    les secrets et le débit avant d'appeler berger. Refus (sys.exit nommé) : agent inconnu. → « remis à … » ou « déposé : … »."""
    return _geste("deposer_message", de, a, texte)


def remettre_messages(a):
    """Remet, dans l'ordre et sous verrou, les messages en attente de `a` s'il tourne. → True si la file est vide à la fin."""
    return _geste("remettre_messages", a)


def suivre_delegation(demandeur, cible, d):
    """Suivi d'une délégation (le courtier a lu ENGAGEMENTS et retiré les secrets) : engagements au TODO.md de la cible, résumé dans sa file. → le texte du dépôt."""
    return _geste("suivre_delegation", demandeur, cible, d)


def poser_question(a, consigne, moteur=None, sortie=None):
    """Une question à `a` dans une conversation neuve, bac à sable et dossier temporaire vérifiés, bascule sur l'autre moteur en cas d'échec.
    → (texte, moteur utilisé ou None, échecs)."""
    return _geste("poser_question", a, consigne, moteur, sortie)


def parler_agent(a, message, moteur=None, de=None):
    """Écrit à `a` dans sa conversation en cours (Herdr, jamais en tapant dans le panneau) ; `de` : qui parle (False = service, non tracé).
    Refus (sys.exit nommé) : agent sans panneau, remise Herdr impossible."""
    return _geste("parler_agent", a, message, moteur, de)


def tracer_echange(de, a, genre, texte):
    """Une ligne dans les échanges (courtier/echanges.jsonl), écrite hors bac à sable."""
    return _geste("tracer_echange", de, a, genre, texte)


def ranger_besoin(de, genre, texte):
    """Range un besoin Berger (numéro jamais réutilisé, sous verrou), le trace et le remet au gardien. Refus (sys.exit nommé) : aucun gardien déclaré."""
    return _geste("ranger_besoin", de, genre, texte)


def clore_besoin(n, etat, suite, par=None):
    """Clôt le besoin n° n (le gardien par le courtier, ou le propriétaire) ; l'émetteur reçoit la suite. Refus (sys.exit nommé) : état inconnu,
    un autre que le gardien, besoin introuvable ou déjà clos."""
    return _geste("clore_besoin", n, etat, suite, par)


def annoncer_outil(o, premiere=False):
    """Régénère les consignes des agents qui ont l'outil `o` et, hors première lecture, leur annonce le changement. Refus (sys.exit nommé) : aucune consigne rangée."""
    return _geste("annoncer_outil", o, premiere)


def ouvrir_developpeur(projet, sujet, texte, par, moteur=None, modele=None):
    """Un développeur pour UN sujet : son clone du dépôt sur sa branche, sa pile, un agent jetable strict, puis sa mission. Refus (sys.exit nommé) :
    projet inconnu, dépôt = installation, autre que le chef de projet ou le propriétaire, sujet invalide ou trop long, moteur ou modèle non permis,
    développeur ou copie existants, plafond [missions] max, sujet de la règle de go sans go inscrit, plus de port libre. → le texte de résultat."""
    return _geste("ouvrir_developpeur", projet, sujet, texte, par, moteur, modele)


def fermer_developpeur(projet, sujet, par):
    """Ferme un développeur : mission close, pile et copie supprimées, journal gardé chez le chef. Refus (sys.exit nommé) : autre que le chef de projet
    ou le propriétaire, pas un développeur ouvert du projet, travail non commité, commits ni poussés ni fusionnés, checklist non finie. → le texte de résultat."""
    return _geste("fermer_developpeur", projet, sujet, par)


def changer_domaine(projet, action, nom, par, essai=False):
    """Ajoute ou retire UN site permis au projet (après la validation du superviseur, par le courtier) ; `essai` : l'aperçu seul. Refus (sys.exit nommé) :
    projet ou action inconnus, nom inexact, déjà permis, plafond de sites, absent. → l'aperçu, ou ce qui est fait."""
    return _geste("changer_domaine", projet, action, nom, par, essai)


def inscrire_go(projet, sujet, cas, spec, par, essai=False):
    """Le go du propriétaire sur une spec nommée : `essai` marque le sujet « go demandé », sinon le go est inscrit si la spec n'a pas changé. Refus
    (sys.exit nommé) : autre que le chef, le coordinateur ou le propriétaire, sujet, cas ou chemin invalides, spec introuvable, vide ou porteuse d'une valeur
    du coffre, go déjà inscrit, spec changée depuis la demande. → l'aperçu, ou ce qui est inscrit."""
    return _geste("inscrire_go", projet, sujet, cas, spec, par, essai)


def ouvrir_projet(eq, projet, membres, par):
    """Ouvre un dossier de projet partagé (bibliothèque), lu et écrit par ses membres seuls. Refus (sys.exit nommé) : équipe inconnue, nom invalide, autre que
    le chef de projet, le coordinateur ou le propriétaire, membres hors de l'équipe, déjà ouvert, dossier existant. → le texte de résultat."""
    return _geste("ouvrir_projet", eq, projet, membres, par)


def fermer_projet(eq, projet, par):
    """Ferme un projet : son dossier part dans les archives (rien n'est supprimé), les membres perdent leurs droits. Refus (sys.exit nommé) : équipe inconnue,
    autre que le chef de projet, le coordinateur ou le propriétaire, pas de projet ouvert. → le texte de résultat."""
    return _geste("fermer_projet", eq, projet, par)


def jouer_crochet(a):
    """Le crochet d'écriture d'un développeur (appelé par son moteur) : le JSON du crochet est lu sur stdin PAR LE GESTE, le fichier visé ramené de sa copie au
    dépôt, la commande du projet jouée dans le dépôt ; sa réponse (ou « rien à dire ») est imprimée. Jamais un blocage."""
    return _geste("jouer_crochet", a)


def services_commandes():
    """Les services d'action pour le CHARGEUR de commandes (bin/commandes/__init__.py), qui les pose dans l'espace de chaque famille. Seul accès aux services :
    noyau.api n'en porte aucun, et le contrat refuse tout import de ce module (ou de `actions`) depuis une vue, un moteur ou une famille (renvoi n° 83)."""
    from noyau.api import ACTIONS
    if tuple(ACTIONS) != NOMS: raise NameError(f"API d'action : noyau/api.py ACTIONS {ACTIONS} ≠ noyau/actions.py NOMS {NOMS}")
    from noyau.agents import journal                 # au chargement des commandes, jamais à l'import de ce module (bin/commandes/ se charge sans config.toml)
    from noyau.bandeaux import mettre_a_jour_titres, notifier, statusline
    from noyau.ecrans import lire_document, lire_interactif
    return {**{n: globals()[n] for n in NOMS if n not in DU_NOYAU}, "journal": journal, "notifier": notifier, "lire_document": lire_document,
            "lire_interactif": lire_interactif, "mettre_a_jour_titres": mettre_a_jour_titres, "statusline": statusline}
