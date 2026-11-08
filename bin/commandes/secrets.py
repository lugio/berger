"""Les secrets (modulaire, lot 4d, partie « secrets ») : l'audit des valeurs du coffre en clair hors du coffre, la copie chiffrée du coffre et sa purge.

Les verbes ne font qu'aiguiller : les ACTIONS passent par les services du noyau (auditer_secrets, sauvegarder_coffre : noyau/actions.py), dont le geste reste
au cœur. Cette famille ne lit NI le coffre, NI ses valeurs, NI la configuration : les zones auditées, le destinataire age, la vérification de la copie (en-tête,
taille) et la purge sont dans le geste ; ce qui est imprimé, ce sont des NOMS de clés et des chemins, jamais une valeur. Corps des verbes : ceux de bin/berger,
mot pour mot."""

FAMILLE = "secrets"


def verbe_secrets(args, prive=False):
    if args[:1] != ["audit"]: return NotImplemented
    sys.exit(auditer_secrets())

def verbe_coffre(args, prive=False):
    if args[:1] == ["sauvegarder"] and len(args) == 2: sys.exit(sauvegarder_coffre(args[1]))
    elif args[:1] == ["purger"]: print(f"purge : {sauvegarder_coffre()} sauvegarde(s) du coffre effacée(s)")
    else: return NotImplemented


VERBES = {"secrets": verbe_secrets, "coffre": verbe_coffre}
AIDE = {
    "secrets": "berger secrets audit                cherche les valeurs du coffre en clair hors du coffre (n'affiche que des NOMS)",
    "coffre": "berger coffre sauvegarder <motif> | purger   copie CHIFFRÉE (age) du coffre avant de le modifier ; efface les copies anciennes",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}
# Ce qui passe sans écarter la famille : l'IndexError d'un argument manquant, un refus d'usage (Refus) et une panne du CŒUR sortie d'un service d'action
# (ErreurService : commandes.lancer ressort l'exception d'origine, telle qu'avant). Toute autre erreur dans la famille l'écarte, nommée.
PASSE = {v: (IndexError, Refus, ErreurService) for v in VERBES}
