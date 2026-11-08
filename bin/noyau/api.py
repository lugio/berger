"""L'API du noyau : la liste NOMMÉE de ce qu'un module (vue, commande, moteur) peut employer. Tout le reste du noyau est privé.

Ajouter un nom = une ligne ici ET un test (tests/contrat-noyau.py vérifie que chaque nom existe et que chaque module n'emploie rien d'autre).
Les modules de la bibliothèque standard (STDLIB) restent employables tels quels ; ils ne sont pas des noms du cœur."""
import datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, tomllib, unicodedata, textwrap
from pathlib import Path

STDLIB = {"datetime": datetime, "json": json, "os": os, "re": re, "shlex": shlex, "shutil": shutil, "subprocess": subprocess,
          "sys": sys, "tempfile": tempfile, "time": time, "tomllib": tomllib, "unicodedata": unicodedata, "textwrap": textwrap,
          "Path": Path}

GROUPES = {
    "Constantes et chemins (config.py)": ("BERGER", "HOME", "AGENTS", "EQUIPES", "MISSIONS", "ECHANGES", "GARDES", "PROPRIETAIRE",
                                          "PANNEAUX_SOURCES", "LECTEURS_CONSO", "STATUTS", "RUBRIQUES_FICHE", "CONFIG"),
    "Agents et fichiers (agents.py)": ("agents", "dossier", "conf", "agent_court", "lire", "json_ou_rien", "aujourdhui", "quand_iso",
                                       "checklist", "cases", "dossier_skills", "skills_demandees", "methode", "hote_mission",
                                       "reglages_mission", "trace_mission"),
    "Herdr (herdr.py)": ("herdr", "herdr_api", "socket_herdr", "statut_herdr", "herdr_ids"),
    "Transport privé (transport.py)": ("entree_privee",),   # transport (executer, executer_shell, lancer) : aux seuls moteurs (lot 4d)
    "Affichage (affichage.py)": ("ANSI", "R", "GRAS", "PALE", "BLEU", "JAUNE", "VERT", "ROUGE", "CYAN", "INV", "TONS", "COLONNES_TONS",
                                 "vlen", "pad", "couper", "plat", "plier", "titre_section", "entete", "mini_entete", "section",
                                 "rendre_markdown", "kilo", "ligne_texte", "carte_colonne", "statuts_texte", "colonnes_tableau_texte"),
    "Lectures en lecture seule (lectures.py)": ("documents", "documents_a_lire", "lus", "id_document", "livrables", "decisions",
                                                "dossier_checklists", "checklist_donnees", "statuts_donnees", "validation_donnees",
                                                "en_attente", "alertes_synthese", "cartes_donnees", "tableau_donnees", "etat_source",
                                                "gravite", "propre", "depuis", "courtier_actif", "droits_agents", "derniere_action",
                                                "derniers_usages", "collecter_conso", "quota_moteurs", "quand_remise", "verbes_outil", "LECTURES", "EXTENSIONS",
                                                "besoins", "phrase_patron",
                                                "fil_conversation", "conversations_ouvertes", "transcription_locale", "masquer_secret", "vivant_herdr",
                                                "reglages_donnees"),
    "Liste des vues et refus d'usage (registre.py)": ("liste_vues", "Refus", "ErreurService"),
    "Écrans de terminal (ecrans.py)": ("etat", "validations"),
    "Missions, lecture (missions.py)": ("suivi", "rapport_mission"),
    "Équipes, lecture (equipes.py)": ("equipe_liste", "projet_liste", "domaines_projet"),
    "Extensions, lecture (extensions.py)": ("extensions_donnees",),   # lot 2 : la page « Extensions », filtrée, sans coffre (spec 2026-11-07 § 6)
}
API = tuple(n for g in GROUPES.values() for n in g)

# L'API d'ACTION (lot 4a) : des services du noyau (noyau/actions.py) qui gardent leurs contrôles eux-mêmes. Donnée aux SEULES familles de commandes,
# jamais aux vues ni aux moteurs. Ici, seulement les NOMS : aucun accès aux services (renvoi n° 83) ; seul le chargeur de commandes les prend, dans
# noyau/actions.py (services_commandes). Ajouter un service = une ligne ici, sa fonction dans noyau/actions.py ET un test (tests/contrat-noyau.py, 1f et 6).
# Lot 4b : les messages et les besoins (1g et 7), puis journal et notifier, qui ÉCRIVENT (le journal d'un agent, notifications.log) : sortis de l'API de lecture.
# Lot 4c : les équipes (1h et 8), puis lire_document, lire_interactif (marquent un document lu), mettre_a_jour_titres (renomme les panneaux Herdr) et
# statusline (relève le quota), qui ÉCRIVENT aussi : sortis de l'API de lecture.
# Lot 4d, partie « courtier » : décider d'une validation, redémarrer le courtier, lancer un agent, ouvrir un moteur de plus, paramètres du moteur pour un pont (1j et 9).
# Lot 4d, partie « mur » : régénérer les règles et réglages des agents, créer un agent, montrer puis appliquer une proposition (1j bis et 10).
# Lot 4d, partie « secrets » : auditer les valeurs du coffre en clair, sauvegarder le coffre chiffré ou purger ses copies (1j ter et 11). Le coffre n'est lu qu'au cœur.
# Lot 4d, partie « dépôt » : neutralité du dépôt, installer depuis la forge, main en ligne, sauvegarde des données, restauration, vérification (1j quater et 12).
# Extensions, lot 1 (spec 2026-11-07) : vérifier, ajouter, retirer, revenir, lister une extension (1l et 14). noyau/extensions.py reste hors de toute API.
ACTIONS = ("confier_mission", "terminer_mission",
           "deposer_message", "remettre_messages", "suivre_delegation", "poser_question", "parler_agent", "tracer_echange",
           "ranger_besoin", "clore_besoin", "annoncer_outil",
           "journal", "notifier",
           "ouvrir_developpeur", "fermer_developpeur", "changer_domaine", "inscrire_go", "ouvrir_projet", "fermer_projet", "jouer_crochet",
           "lire_document", "lire_interactif", "mettre_a_jour_titres", "statusline",
           "decider_validation", "redemarrer_courtier", "lancer_agent", "ouvrir_moteur", "parametres_moteur",
           "regenerer_agents", "creer_agent", "apercu_agent", "appliquer_agent",
           "auditer_secrets", "sauvegarder_coffre",
           "verifier_neutralite", "installer_forge", "publier_en_ligne", "sauvegarder_donnees", "restaurer_archive", "verifier_sauvegarde_distante",
           "gerer_extension")


def espace(noyau_globals):
    """Ce que reçoit un module : les noms de l'API (pris dans `noyau_globals`, l'espace où les modules du noyau sont importés)
    plus la bibliothèque standard. Un nom absent de la liste n'existe pas pour lui."""
    manque = [n for n in API if n not in noyau_globals]
    if manque: raise NameError(f"API du noyau : nom(s) absent(s) {', '.join(manque)}")
    return {**STDLIB, **{n: noyau_globals[n] for n in API}}
