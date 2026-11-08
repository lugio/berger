"""Les services d'ACTION du noyau (modulaire, lots 4a, 4b et 4c) : ce qu'une famille de commandes peut FAIRE, par un nom fixe et une signature fixe.

L'API de lecture (noyau/api.py API) est donnée à tous les modules ; l'API d'action (noyau/api.py ACTIONS = les noms ci-dessous) aux SEULES familles de
commandes, jamais à une vue ni à un moteur. Un service garde ses contrôles lui-même (agent inscrit, une mission à la fois, plafond [missions] max,
moteur et modèle par noyau.modeles, checklist finie, refus de fusion…) : la commande n'en fait aucun, et l'appeler sans elle ne les contourne pas.
Ce qui passe par demarrer_agent ou le mur (ouvrir un agent en mission, fermer son panneau) reste dans le cœur : bin/berger y branche au démarrage
la fonction qui fait le geste (`brancher`, une fois par processus, liste fermée). Ce branchement disparaît quand le lancement d'un agent
quittera bin/berger (suite du lot 4). Ce qui sort du geste (une Exception, jamais sys.exit) est enveloppé dans ErreurService, l'origine gardée en
cause : la famille le déclare dans PASSE et commandes.lancer ressort l'origine, telle qu'avant. Seuls imports : noyau.ecarts, qui n'en a aucun
(bin/commandes/ charge l'API sans config.toml), et types (bibliothèque standard).
Relecture Codex du 4d : le registre est FIGÉ au branchement (lecture seule, rien hors ACTIONS, un seul branchement par processus) et _geste
juge le nom contre ACTIONS avant tout registre : qui atteindrait ce module n'y ajoute, n'y réécrit ni n'y exécute rien hors de la liste.
Lot 4b : les messages (déposer, remettre, suivre une délégation, poser une question, parler, tracer un échange) et les besoins (ranger, clore, annoncer
un outil) : mêmes règles, gestes au cœur. Plus `journal` et `notifier`, fonctions du NOYAU qui écrivent (le journal d'un agent, notifications.log) :
sorties de l'API de lecture, données aux seules familles telles quelles (aucun contrôle à garder, rien à envelopper : une erreur sort comme avant).
Lot 4c : les équipes (ouvrir et fermer un développeur, changer un site permis, inscrire un go, ouvrir et fermer un projet, jouer le crochet d'un développeur) :
mêmes règles, gestes au cœur. Plus lire_document, lire_interactif (marquent un document lu), mettre_a_jour_titres (renomme les panneaux Herdr) et
statusline (relève le quota) : fonctions du NOYAU qui écrivent, sorties de l'API de lecture comme journal et notifier.
Lot 4d, partie « courtier » : décider d'une validation, redémarrer le courtier, lancer un agent, ouvrir un moteur de plus, donner les paramètres du moteur à un pont :
mêmes règles, gestes au cœur (le fichier de décision, la marque de fermeture et le retour arrière, le bac à sable, l'admission du moteur, demarrer_agent).
Lot 4d, partie « mur » : régénérer les règles et les réglages de tous les agents, créer un agent, montrer puis appliquer la proposition d'un agent : le calcul
du mur et le contrôle d'une proposition restent au cœur, derrière les services.
Lot 4d, partie « secrets » : auditer les valeurs du coffre en clair hors du coffre, sauvegarder le coffre chiffré ou purger ses copies : le coffre n'est lu
qu'au cœur (valeurs_coffre, coffre_sauvegarder) ; un service rend un code et imprime des NOMS de clés, jamais une valeur.
Lot 4d, partie « dépôt » : neutralité du dépôt, installer depuis la forge locale, publier main en ligne, sauvegarder les données chiffrées, restaurer une archive,
vérifier la dernière sauvegarde : git, retour arrière, redémarrage détaché, phrase du trousseau, identifiants lus au coffre restent au cœur.
Extensions, lot 1 (spec 2026-11-07) : vérifier, ajouter, retirer, revenir, lister une extension : le geste (noyau/extensions.py, à qui le cœur donne
valeurs_coffre et regenerer) reste derrière le service ; le refus à un agent est dans le geste, qui lit l'appelant lui-même."""
from types import MappingProxyType
from noyau.ecarts import ErreurService

NOMS = ("confier_mission", "terminer_mission", "deposer_message", "remettre_messages", "suivre_delegation", "poser_question", "parler_agent",
        "tracer_echange", "ranger_besoin", "clore_besoin", "annoncer_outil", "journal", "notifier",
        "ouvrir_developpeur", "fermer_developpeur", "changer_domaine", "inscrire_go", "ouvrir_projet", "fermer_projet", "jouer_crochet",
        "lire_document", "lire_interactif", "mettre_a_jour_titres", "statusline",
        "decider_validation", "redemarrer_courtier", "lancer_agent", "ouvrir_moteur", "parametres_moteur",
        "regenerer_agents", "creer_agent", "apercu_agent", "appliquer_agent",
        "auditer_secrets", "sauvegarder_coffre",
        "verifier_neutralite", "installer_forge", "publier_en_ligne", "sauvegarder_donnees", "restaurer_archive", "verifier_sauvegarde_distante",
        "gerer_extension")
DU_NOYAU = ("journal", "notifier", "lire_document", "lire_interactif", "mettre_a_jour_titres", "statusline")   # fonctions du noyau, prises dans leur module
                                                # au chargement des commandes (pas de geste du cœur à brancher)
_SERVICES = MappingProxyType({})                # nom -> fonction du cœur qui fait le geste (posée par bin/berger) ; lecture seule


def brancher(services):
    """Pose les fonctions du cœur derrière les services, UNE fois par processus : seulement des noms de NOMS, seulement des fonctions ;
    le registre est ensuite en lecture seule (ni ajout, ni réécriture, ni second branchement)."""
    global _SERVICES
    hors = sorted(set(services) - set(NOMS))
    if hors: raise NameError(f"service hors de la liste ACTIONS : {', '.join(hors)}")
    du_noyau = sorted(set(services) & set(DU_NOYAU))
    if du_noyau: raise NameError(f"service du noyau, jamais branché par le cœur : {', '.join(du_noyau)}")
    for nom, f in services.items():
        if not callable(f): raise TypeError(f"service {nom} : pas une fonction")
    if _SERVICES: raise RuntimeError("services déjà branchés : un seul branchement par processus (bin/berger, au démarrage)")
    _SERVICES = MappingProxyType(dict(services))


def _service(nom):
    if nom not in NOMS or nom in DU_NOYAU: raise NameError(f"service hors de la liste ACTIONS : {nom}")
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


def decider_validation(n, decision, duree=None, empreinte=None):
    """Ta décision sur la validation n° n (« valider » ou « refuser ») : fichier .decision atomique, sous le verrou des décisions, que le courtier exécute ;
    `duree` : celle d'un accès web ; `empreinte` (interface web) : le sha256 de la demande vue, revérifié sous le verrou. Refus (sys.exit nommé) : déjà faite
    ou déjà décidée, aucune demande en attente, demande modifiée depuis l'aperçu, durée sur un refus, hors accès web ou invalide. Imprime l'état, ou que la
    file est tenue."""
    return _geste("decider_validation", n, decision, duree, empreinte)


def redemarrer_courtier(controle=None, essai=1, publier=None):
    """Redémarre le courtier SANS couper une demande en cours (marque de fermeture, attente bornée) ; `controle` : après une installation, contrôlé, retour
    arrière automatique s'il ne reste pas actif ; abandon tracé, notifié, nouvel essai lancé à part. → le code de sortie."""
    return _geste("redemarrer_courtier", controle, essai, publier)


def lancer_agent(a, moteur=None):
    """Ouvre `a` en interactif dans ce terminal (remplace le processus) : bac à sable exigé, dossier temporaire vérifié, moteur admis (bascule sur l'autre),
    arguments stricts du moteur. Refus (sys.exit nommé) : bac à sable absent, temporaire refusé, aucun moteur admis, moteur inconnu."""
    return _geste("lancer_agent", a, moteur)


def ouvrir_moteur(a, m):
    """Ouvre un moteur de plus pour `a`, dans un nouveau panneau de son onglet Agent (demarrer_agent : le mur). Refus (sys.exit nommé) : agent inconnu."""
    return _geste("ouvrir_moteur", a, m)


def parametres_moteur(args):
    """Pour un pont (ex. une messagerie) : dossier, arguments et variables du moteur de l'agent (JSON imprimé), comme les lance Herdr. `args` : ceux du verbe,
    lus PAR LE GESTE (le bac à sable est exigé avant de lire le moteur, comme avant). Refus (sys.exit nommé) : bac à sable absent, moteur non admis."""
    return _geste("parametres_moteur", args)


def regenerer_agents():
    """Reconstruit les règles, les réglages du mur (Claude, Codex : masques, cloisons, réseau, MCP, temporaires), les liens de skills et les profils Codex de
    TOUS les agents ; imprime ce qui est signalé et « regénéré : … »."""
    return _geste("regenerer_agents")


def creer_agent(a, nom=None):
    """Crée l'agent `a` à partir des modèles (SOUL d'un rôle s'il existe), puis regenerer. Refus (sys.exit nommé) : nom trop long pour Herdr, agent existant."""
    return _geste("creer_agent", a, nom)


def apercu_agent(demandeur, cible):
    """Ce que changerait la proposition propositions/<cible>.md du demandeur : droits avant → après, fichiers (valeurs du coffre masquées), refus, empreinte.
    Refus (sys.exit nommé) : proposition introuvable. → 0 si applicable, 1 sinon."""
    return _geste("apercu_agent", demandeur, cible)


def appliquer_agent(demandeur, cible_empreinte):
    """Applique EXACTEMENT la proposition montrée (même empreinte) : sauvegardes .avant, fichiers proposés seulement, regenerer, journaux, relance au repos.
    Refus (sys.exit nommé) : usage, proposition introuvable ou refusée (mêmes contrôles que l'aperçu), empreinte changée. → le texte de résultat."""
    return _geste("appliquer_agent", demandeur, cible_empreinte)


def auditer_secrets():
    """Cherche les valeurs SECRÈTES du coffre en clair hors du coffre (dossiers des agents, journaux, transcriptions des moteurs, zones en plus) ; imprime les
    fichiers et le NOM des clés, jamais une valeur ; écrit courtier/dernier-audit.txt. → 0 sans fuite, 1 sinon."""
    return _geste("auditer_secrets")


def sauvegarder_coffre(motif=None):
    """Copie CHIFFRÉE (age, vers la clé PUBLIQUE de [coffre_sauvegarde]) du coffre avant de le modifier, vérifiée (en-tête, taille), puis purge des copies
    anciennes ; sans motif : la purge seule. Refus (sys.exit nommé) : destinataire absent, motif invalide, age absent, chiffrement en échec, copie non conforme.
    → 0 (copie faite), ou le nombre de copies effacées (purge seule)."""
    return _geste("sauvegarder_coffre", motif)


def verifier_neutralite():
    """Le dépôt ne contient QUE le produit : aucune donnée d'agent ni configuration locale, aucune marque de l'installation, aucune valeur du coffre (fichiers
    suivis et prêts à être enregistrés). Imprime les fichiers fautifs et leur motif, jamais une valeur. → 0 (propre) ou 1."""
    return _geste("verifier_neutralite")


def installer_forge(forge, branche="main"):
    """L'installation prend <branche> de la forge locale : avance rapide seule, HEAD vérifié, verifier-depot et regenerer du NOUVEAU code, redémarrage détaché et
    contrôlé du courtier ; une vérification en échec → retour arrière automatique, tracé et notifié. → le code de sortie."""
    return _geste("installer_forge", forge, branche)


def publier_en_ligne(forge):
    """main de la forge part en ligne (le dépôt en ligne de l'équipe, sinon origin) : avance rapide seule, jamais de force ; tracé, échec notifié. → le code."""
    return _geste("publier_en_ligne", forge)


def sauvegarder_donnees():
    """Archive les DONNÉES de l'installation, chiffrée (phrase du trousseau), envoyée au WebDAV de [sauvegarde] (identifiants lus au coffre, passés sur
    l'entrée standard), en gardant les N dernières. → 0, 1 (envoi en échec) ou 2 (pas de section)."""
    return _geste("sauvegarder_donnees")


def restaurer_archive(archive, destination):
    """Déchiffre une archive de sauvegarde (fichier local) dans un dossier, pour vérifier ou récupérer."""
    return _geste("restaurer_archive", archive, destination)


def verifier_sauvegarde_distante():
    """Télécharge la dernière archive du WebDAV, la déchiffre dans un dossier temporaire et compare aux fichiers locaux (empreintes). → 0 ou 1."""
    return _geste("verifier_sauvegarde_distante")


def gerer_extension(args):
    """`berger extension verifier|ajouter|retirer|revenir|liste …` (spec 2026-11-07) : paquet copié sans lien, manifeste, contrôles du genre, aucune
    valeur du coffre, sauvegarde vérifiée de extensions.toml et des agent.conf, regenerer, retour arrière automatique. Refus (écrit sur la sortie
    d'erreur, nommé, jamais une valeur) : forme ou genre inconnus, paquet refusé, un agent qui ajoute, retire ou revient (BERGER_AGENT, lu par le geste).
    → le code de sortie (0, ou 1 pour un refus)."""
    return _geste("gerer_extension", args)


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
