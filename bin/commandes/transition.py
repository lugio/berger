"""Verbes qui restent au cœur jusqu'au lot 4 (modulaire, lot 3) : « module de transition ».

Chaque verbe ci-dessous appelle, directement ou par une fonction du cœur, le courtier, le mur (masques, cloisons, réglages), les droits,
le coffre ou les secrets, les missions, les messages et besoins, les équipes, l'installation, la sauvegarde ou l'audit : son code et ses
fonctions RESTENT dans bin/berger (tri : docs/plans/2026-10-27-modulaire-decisions.md). Ce module ne fait que les inscrire dans le MÊME registre que
les autres familles (un seul chemin d'aiguillage, pas deux) : leurs fonctions sont celles que bin/berger prête (VERBES_COEUR).
Chaque famille du lot 4 prendra ses verbes ici, puis ce module sera supprimé."""

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
    "demander": "berger demander <agent> --stdin [--moteur m] [--sortie f]   une question, conversation neuve, bascule si panne",
    "planificateur": "berger planificateur                appelé chaque minute par le timer : réveils, tâches, rangement, titres Herdr",
    "espace": "berger espace <agent>|ensemble      crée (ou recrée) l'espace Herdr",
    "interface": "berger interface lien|servir|certificat   lien d'entrée, serveur et certificat interne de l'interface web (propriétaire seul)",
    "web": "berger web [fermer <agent>|connecter <domaine>]   accès web ouverts ; fermer celui d'un agent ; connexion visible du propriétaire",
    "crochet-equipe": "berger crochet-equipe <agent>        appelé par le moteur (crochet d'un développeur)",
    "secrets": "berger secrets audit                cherche les valeurs du coffre en clair hors du coffre (n'affiche que des NOMS)",
    "coffre": "berger coffre sauvegarder <motif> | purger   copie CHIFFRÉE (age) du coffre avant de le modifier ; efface les copies anciennes",
    "verifier-depot": "berger verifier-depot                contrôle de neutralité du dépôt (aucun nom de projet, de personne ni d'éditeur réel)",
    "mcp-enveloppe": "berger mcp-enveloppe <agent> <serveur>   (courtier) comment lancer le serveur MCP de l'agent, enfermé (JSON) — ou le refus",
    "sauvegarder": "berger sauvegarder                  archive chiffrée des DONNÉES vers le WebDAV de [sauvegarde] (fait seul chaque jour)",
    "restaurer": "berger restaurer <archive> <dossier>  déchiffre une sauvegarde",
    "verifier-sauvegarde": "berger verifier-sauvegarde          relit la dernière sauvegarde chiffrée du serveur",
    "moteur": "berger moteur <agent> <moteur>      ouvre un moteur de plus pour l'agent, à la demande",
    "parler": "berger parler <agent> --stdin       écrit à l'agent dans sa conversation en cours (Herdr)",
    "superviser": "berger superviser                   un passage de la supervision (relances, alertes, finitions)",
    "message-deposer": "berger --stdin [\"message-deposer\", de, a, texte]   (courtier, berger-outil ecrire) dépose un message à sens unique",
    "annonce-outil": "berger annonce-outil <outil> [--premiere]   (courtier) annonce aux agents la consigne changée d'un outil",
    "besoin-ranger": "berger besoin-ranger <de> <genre> <texte>   (courtier, berger-outil besoin) range un besoin Berger",
    "besoin": "berger besoin [liste] [--json] | clore <n°> fait|refuse|transmis \"<suite>\"   besoins Berger ouverts, et leur clôture",
    "message-remettre": "berger message-remettre <agent>      remet à l'agent les messages en attente (usage interne)",
    "delegation-suivi": "berger delegation-suivi <demandeur> <cible>   (courtier, deleguer) trace d'une délégation, JSON sur stdin",
    "echange": "berger echange <de> <a> <genre> <texte>   (courtier, outils d'équipe) une ligne dans les échanges",
    "parler-interactif": "berger parler-interactif            fenêtre Herdr prefix+a : choisir l'agent, écrire le message",
    "entretien": "berger entretien                    range journaux, réveils et sorties anciens (fait seul chaque jour)",
    "valider": "berger valider <n°> [--duree 8h]    ta décision : le courtier exécute (accès web d'un agent : fixe sa durée)",
    "refuser": "berger refuser <n°>                 ta décision : le courtier abandonne",
    "mission": "berger --stdin [\"mission\", agent, texte]   confie une mission ; options --moteur/--modele/--par dans le même tableau",
    "suivi": "berger suivi <agent>                état d'une mission (JSON : statut, checklist, journal, validations)",
    "rapport-mission": "berger rapport-mission <agent>       le rapport d'une mission terminée (JSON)",
    "equipe": "berger --stdin [\"equipe\", ouvrir|fermer|liste|domaine|domaines|go, projet, …]   équipes de développement",
    "projet": "berger --stdin [\"projet\", ouvrir|fermer|liste, équipe, …]   dossier partagé d'une équipe",
    "fin-mission": "berger fin-mission <agent>          range la mission et ferme l'espace de l'agent",
    "installer": "berger installer <forge> [branche]  l'installation prend la forge locale (avance rapide), contrôle, régénère, redémarre le courtier",
    "courtier": "berger courtier redemarrer [--controle <commit>]   redémarre le courtier SANS couper une demande en cours",
    "agent": "berger agent apercu <demandeur> <agent> | appliquer <demandeur> <agent>.<empreinte>   proposition de modification d'un agent",
    "args": "berger args <agent> <moteur> [--non-interactif]   dossier, arguments et variables du moteur (JSON), pour un pont",
}
DROITS = {v: {"prive": v in ("mission", "message-deposer", "equipe", "projet"), "cas_go": None} for v in VERBES}   # cas_go : à qualifier verbe par verbe au lot 4
