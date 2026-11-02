"""Verbes qui restent au cœur jusqu'au lot 4 (modulaire, lot 3) : « module de transition ».

Chaque verbe ci-dessous appelle, directement ou par une fonction du cœur, le courtier, le mur (masques, cloisons, réglages), les droits,
le coffre ou les secrets, les missions, les messages et besoins, les équipes, l'installation, la sauvegarde ou l'audit : son code et ses
fonctions RESTENT dans bin/berger (tri : docs/plans/2026-10-27-modulaire-decisions.md). Ce module ne fait que les inscrire dans le MÊME registre que
les autres familles (un seul chemin d'aiguillage, pas deux) : leurs fonctions sont celles que bin/berger prête (VERBES_COEUR).
Chaque famille du lot 4 prendra ses verbes ici (4a : les missions, dans commandes/missions.py ; 4b : les messages et les besoins, dans
commandes/messages.py et commandes/besoins.py ; 4c : les équipes, dans commandes/equipes.py), puis ce module sera supprimé."""

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
    "nouveau": "berger nouveau <agent> \"<Nom>\"      crée un agent à partir des modèles",
    "regenerer": "berger regenerer                    reconstruit AGENTS.md, réglages Claude/Codex, liens de skills de TOUS les agents",
    "lancer": "berger lancer <agent> [moteur]      ouvre l'agent en interactif dans ce terminal",
    "planificateur": "berger planificateur                appelé chaque minute par le timer : réveils, tâches, rangement, titres Herdr",
    "espace": "berger espace <agent>|ensemble      crée (ou recrée) l'espace Herdr",
    "interface": "berger interface lien|servir|certificat   lien d'entrée, serveur et certificat interne de l'interface web (propriétaire seul)",
    "web": "berger web [fermer <agent>|connecter <domaine>]   accès web ouverts ; fermer celui d'un agent ; connexion visible du propriétaire",
    "secrets": "berger secrets audit                cherche les valeurs du coffre en clair hors du coffre (n'affiche que des NOMS)",
    "coffre": "berger coffre sauvegarder <motif> | purger   copie CHIFFRÉE (age) du coffre avant de le modifier ; efface les copies anciennes",
    "verifier-depot": "berger verifier-depot                contrôle de neutralité du dépôt (aucun nom de projet, de personne ni d'éditeur réel)",
    "mcp-enveloppe": "berger mcp-enveloppe <agent> <serveur>   (courtier) comment lancer le serveur MCP de l'agent, enfermé (JSON) — ou le refus",
    "sauvegarder": "berger sauvegarder                  archive chiffrée des DONNÉES vers le WebDAV de [sauvegarde] (fait seul chaque jour)",
    "restaurer": "berger restaurer <archive> <dossier>  déchiffre une sauvegarde",
    "verifier-sauvegarde": "berger verifier-sauvegarde          relit la dernière sauvegarde chiffrée du serveur",
    "moteur": "berger moteur <agent> <moteur>      ouvre un moteur de plus pour l'agent, à la demande",
    "superviser": "berger superviser                   un passage de la supervision (relances, alertes, finitions)",
    "entretien": "berger entretien                    range journaux, réveils et sorties anciens (fait seul chaque jour)",
    "valider": "berger valider <n°> [--duree 8h]    ta décision : le courtier exécute (accès web d'un agent : fixe sa durée)",
    "refuser": "berger refuser <n°>                 ta décision : le courtier abandonne",
    "installer": "berger installer <forge> [branche]  l'installation prend la forge locale (avance rapide), contrôle, régénère, redémarre le courtier",
    "publier": "berger publier <forge>              main de la forge part en ligne (option `publication`, sinon origin) : avance rapide seule, jamais de force",
    "courtier": "berger courtier redemarrer [--controle <commit>]   redémarre le courtier SANS couper une demande en cours",
    "agent": "berger agent apercu <demandeur> <agent> | appliquer <demandeur> <agent>.<empreinte>   proposition de modification d'un agent",
    "args": "berger args <agent> <moteur> [--non-interactif]   dossier, arguments et variables du moteur (JSON), pour un pont",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}   # cas_go : à qualifier verbe par verbe au lot 4 ; plus aucun verbe privé ici (lot 4c)
