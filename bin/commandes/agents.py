"""Les agents et leur mur (modulaire, lot 4d, partie « mur ») : régénérer les règles et les réglages de tous les agents, créer un agent, montrer puis
appliquer la proposition qu'un agent fait pour un autre.

Les verbes ne font qu'aiguiller : les ACTIONS passent par les services du noyau (regenerer_agents, creer_agent, apercu_agent, appliquer_agent :
noyau/actions.py), dont le geste reste au cœur. Aucun contrôle ici : le calcul du mur (masques, cloisons, réglages Claude et Codex, réseau, serveurs MCP,
skills, temporaires) et le contrôle d'une proposition (fichiers et clés permis, clés interdites, mur strict seul, outils, coffre, empreinte) sont dans le
geste ; l'application attend la validation du propriétaire, au courtier. Corps des verbes : ceux de bin/berger, mot pour mot."""

FAMILLE = "agents"


def verbe_nouveau(args, prive=False): creer_agent(args[0], args[1] if len(args) > 1 else None)
def verbe_regenerer(args, prive=False): regenerer_agents()

def verbe_agent(args, prive=False):
    if args[:1] == ["apercu"] and len(args) == 3: sys.exit(apercu_agent(args[1], args[2]))
    elif args[:1] == ["appliquer"] and len(args) == 3: print(appliquer_agent(args[1], args[2]))
    else: return NotImplemented


VERBES = {"regenerer": verbe_regenerer, "nouveau": verbe_nouveau, "agent": verbe_agent}
AIDE = {
    "nouveau": "berger nouveau <agent> \"<Nom>\"      crée un agent à partir des modèles",
    "regenerer": "berger regenerer                    reconstruit AGENTS.md, réglages Claude/Codex, liens de skills de TOUS les agents",
    "agent": "berger agent apercu <demandeur> <agent> | appliquer <demandeur> <agent>.<empreinte>   proposition de modification d'un agent",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}
# Ce qui passe sans écarter la famille : l'IndexError d'un argument manquant (comme avant), un refus d'usage (Refus) et une panne du CŒUR sortie d'un
# service d'action (ErreurService : commandes.lancer ressort l'exception d'origine, telle qu'avant). Toute autre erreur dans la famille l'écarte, nommée.
PASSE = {v: (IndexError, Refus, ErreurService) for v in VERBES}
