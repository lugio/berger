"""Le dépôt et l'installation (modulaire, lot 4d, partie « dépôt ») : la neutralité du dépôt, installer depuis la forge locale, publier main en ligne, la
sauvegarde chiffrée des données, sa restauration et sa vérification.

Les verbes ne font qu'aiguiller : les ACTIONS passent par les services du noyau (verifier_neutralite, installer_forge, publier_en_ligne, sauvegarder_donnees,
restaurer_archive, verifier_sauvegarde_distante : noyau/actions.py), dont le geste reste au cœur. Aucun contrôle ici : marques et valeurs du coffre cherchées,
avance rapide, HEAD vérifié, retour arrière automatique, redémarrage contrôlé, publication sans force, phrase du trousseau, identifiants du WebDAV lus au
coffre, rotation des archives sont dans le geste ; la validation de ces actions, au courtier. Corps des verbes : ceux de bin/berger, mot pour mot."""

FAMILLE = "depot"


def verbe_verifier_depot(args, prive=False): sys.exit(verifier_neutralite())

def verbe_installer(args, prive=False):
    if not 1 <= len(args) <= 2: return NotImplemented
    sys.exit(installer_forge(args[0], args[1] if len(args) > 1 else "main"))

def verbe_publier(args, prive=False): sys.exit(publier_en_ligne(args[0])) if len(args) == 1 else NotImplemented
def verbe_sauvegarder(args, prive=False): sys.exit(sauvegarder_donnees())
def verbe_restaurer(args, prive=False): restaurer_archive(args[0], args[1])
def verbe_verifier_sauvegarde(args, prive=False): sys.exit(verifier_sauvegarde_distante())


VERBES = {"verifier-depot": verbe_verifier_depot, "installer": verbe_installer, "publier": verbe_publier, "sauvegarder": verbe_sauvegarder,
          "restaurer": verbe_restaurer, "verifier-sauvegarde": verbe_verifier_sauvegarde}
AIDE = {
    "verifier-depot": "berger verifier-depot                contrôle de neutralité du dépôt (aucun nom de projet, de personne ni d'éditeur réel)",
    "installer": "berger installer <forge> [branche]  l'installation prend la forge locale (avance rapide), contrôle, régénère, redémarre le courtier",
    "publier": "berger publier <forge>              main de la forge part en ligne (option `publication`, sinon origin) : avance rapide seule, jamais de force",
    "sauvegarder": "berger sauvegarder                  archive chiffrée des DONNÉES vers le WebDAV de [sauvegarde] (fait seul chaque jour)",
    "restaurer": "berger restaurer <archive> <dossier>  déchiffre une sauvegarde",
    "verifier-sauvegarde": "berger verifier-sauvegarde          relit la dernière sauvegarde chiffrée du serveur",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}
# Ce qui passe sans écarter la famille : l'IndexError d'un argument manquant (comme avant), un refus d'usage (Refus) et une panne du CŒUR sortie d'un
# service d'action (ErreurService : commandes.lancer ressort l'exception d'origine, telle qu'avant). Toute autre erreur dans la famille l'écarte, nommée.
PASSE = {v: (IndexError, Refus, ErreurService) for v in VERBES}
