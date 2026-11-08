"""Les extensions (spec docs/plans/2026-11-07-extensions-spec.md, lot 1) : `berger extension verifier|ajouter|retirer|revenir|liste`.

Le verbe ne fait qu'aiguiller : l'ACTION passe par le service du noyau gerer_extension (noyau/actions.py), dont le geste (noyau/extensions.py) reçoit du
cœur les valeurs du coffre et regenerer. Cette famille ne lit NI le coffre, NI extensions.toml, NI un agent.conf, NI l'appelant : le refus à un agent
(ajouter, retirer, revenir : propriétaire seul, au terminal) est dans le geste. Ce qui est imprimé nomme un fichier, une ligne, une clé — jamais une valeur."""

FAMILLE = "extensions"


def verbe_extension(args, prive=False):
    sys.exit(gerer_extension(list(args)))


VERBES = {"extension": verbe_extension}
AIDE = {
    "extension": "berger extension verifier|ajouter <genre> <source> [--agents a,b] [--reseau] | retirer|revenir <genre> <nom> | liste [--json]"
                 "   skill, MCP, vue ou outil du courtier : contrôlé, sauvegardé, retour arrière automatique (propriétaire seul pour changer)",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}
# Ce qui passe sans écarter la famille : un refus d'usage (Refus) et une panne du CŒUR sortie du service (ErreurService : commandes.lancer ressort
# l'exception d'origine, telle qu'avant). Toute autre erreur dans la famille l'écarte, nommée.
PASSE = {v: (Refus, ErreurService) for v in VERBES}
