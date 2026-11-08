"""Verbes qui restent au cœur jusqu'au lot 4 (modulaire, lot 3) : « module de transition ».

Chaque verbe ci-dessous appelle, directement ou par une fonction du cœur, le courtier, le mur (masques, cloisons, réglages), les droits,
le coffre ou les secrets, les missions, les messages et besoins, les équipes, l'installation, la sauvegarde ou l'audit : son code et ses
fonctions RESTENT dans bin/berger (tri : docs/plans/2026-10-27-modulaire-decisions.md). Ce module ne fait que les inscrire dans le MÊME registre que
les autres familles (un seul chemin d'aiguillage, pas deux) : leurs fonctions sont celles que bin/berger prête (VERBES_COEUR).
Chaque famille du lot 4 prendra ses verbes ici (4a : les missions, dans commandes/missions.py ; 4b : les messages et les besoins, dans
commandes/messages.py et commandes/besoins.py ; 4c : les équipes, dans commandes/equipes.py ; 4d : le courtier, dans commandes/courtier.py, le mur, dans commandes/agents.py, les secrets, dans commandes/secrets.py, le dépôt, dans commandes/depot.py). Il reste après le lot 4 pour les verbes que
le lot 4d laisse au cœur (décisions, « Écarts du 4d »)."""

FAMILLE = "transition"
VERBES = dict(VERBES_COEUR)
AIDE = {
    "vue": "berger vue <type> [agent] [--json]  une vue, une fois (texte) ou ses données (JSON, schéma bin/vues/<type>.schema.json)",
    "panneau": "berger panneau <type> [agent]       panneau en direct : tableau | journal | fiche | ensemble | courtier | echanges",
    "abonnement-claude": "berger abonnement-claude <agent> <abonnement>   l'abonnement Claude d'un agent (moteur claude)",
    "reveil": "berger reveil <agent> [--force]     un battement de cœur",
    "tache": "berger tache <agent> <nom>          une tâche planifiée, tout de suite",
    "relancer": "berger relancer <agent> [moteur] [--force]   relance l'agent dans son panneau (après un changement de réglages) — au repos seulement",
    "espace-voulu": "berger espace-voulu <agent> [--json]   l'espace que les règles R1…R7 demandent (onglets, panneaux, raisons) — lecture seule",
    "refaire-espace": "berger refaire-espace <agent>       passe un espace existant à la mise en page « Travail · Fiche » (agent non redémarré)",
    "reprendre": "berger reprendre [--fond]           crochet de démarrage de Herdr : reprend les agents dans leurs panneaux",
    "memoire": "berger memoire verifier|valider|refuser [<agent>] <proposition>   proposition de mémoire : porte de perte + sauvegarde",
    "planificateur": "berger planificateur                appelé chaque minute par le timer : réveils, tâches, rangement, titres Herdr",
    "espace": "berger espace <agent>|ensemble      crée (ou recrée) l'espace Herdr",
    "interface": "berger interface lien|servir|certificat   lien d'entrée, serveur et certificat interne de l'interface web (propriétaire seul)",
    "web": "berger web [fermer <agent>|connecter <domaine>]   accès web ouverts ; fermer celui d'un agent ; connexion visible du propriétaire",
    "mcp-enveloppe": "berger mcp-enveloppe <agent> <serveur>   (courtier) comment lancer le serveur MCP de l'agent, enfermé (JSON) — ou le refus",
    "superviser": "berger superviser                   un passage de la supervision (relances, alertes, finitions)",
    "entretien": "berger entretien                    range journaux, réveils et sorties anciens (fait seul chaque jour)",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}   # cas_go : à qualifier verbe par verbe au lot 4 ; plus aucun verbe privé ici (lot 4c)
