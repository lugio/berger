# Règles d'espace : l'espace voulu d'un agent (2026-10-15, sujet 1/3)

Go du propriétaire le 15/10 : la disposition des espaces Herdr suit les besoins des agents — niveau C (règles fixes dans le
code, appliquées par le planificateur : sujet 2) puis B (disposition sur mesure : sujet 3). Ce sujet-ci ne fait que
**calculer** ; il ne touche jamais Herdr.

## Constat

La disposition d'un espace est écrite en dur dans plusieurs fonctions, chacune à un moment différent : `espace()` (Travail,
Fiche, onglets du rôle), `colonne_travail()`, `onglets_agent()`, `onglet_fiche()`, `ouvrir_en_mission()` (onglet Missions,
nommé Équipe chez un chef de projet), `fermer_mission()` (le ferme quand il est vide). Rien ne dit, pour un agent donné,
quelle disposition il **devrait** avoir ni **pourquoi** : impossible de comparer avec ce qui est ouvert.

## Comportement

`espace_voulu(a, maintenant=None)` (bin/berger) est une fonction **pure** : elle ne lit que des fichiers (agent.conf,
`[espaces.<a>]` et `[equipes.*]` de config.toml, MISSION.md, `.herdr.json` des agents, `historique/`) et n'appelle jamais
Herdr. Elle rend :

- `agent`, `nom`, `heberge_par` (l'hôte de sa mission, ou null) ;
- `onglets`, dans l'ordre : chacun `cle` (stable), `libelle` (tel qu'affiché), `regle` (R1…R7), `raison` (phrase),
  `conditionnel`, `condition` (null pour un onglet permanent), `depuis` (date « AAAA-MM-JJTHH:MM » ou null si inconnue),
  `panneaux` ;
- chaque panneau : `cle` (stable, celle de `.herdr.json` quand elle existe), `genre` (`agent` = la conversation d'un
  agent, `panneau` = une commande), `commande` (null pour un agent), `agent` / `moteur` (pour un agent), `protege` (true
  pour toute conversation : jamais fermée), `regle`, `raison`.

`berger espace-voulu <agent> [--json]` : texte lisible (onglets, panneaux, règle et raison de chacun) ou JSON dans
l'enveloppe commune `{vue, version, genere, donnees}`, décrit par `bin/schemas/espace-voulu.schema.json`. Lecture seule.

## Règles, une à une

- **R1 Travail** (toujours) : un panneau agent par moteur de `panneaux` (agent.conf), ou le seul moteur de la mission en
  cours (en-tête de MISSION.md) ; puis « en cours » ; puis les panneaux du métier : `[espaces.<a>].a_cote` (3 au plus),
  sinon `domaine` d'agent.conf (2 au plus, sans `etat-taches`, déjà dans « en cours »).
- **R2 Mission ailleurs** (conditionnel) : l'agent est en mission dans l'onglet Missions d'un hôte (`.herdr.json` :
  `mission.hote` et un panneau agent) → son onglet Travail s'appelle « Mission » et montre son journal à la place de la
  conversation (qui vit chez l'hôte). `depuis` = date de MISSION.md.
- **R3 Fiche** (toujours) : une page, `berger panneau fiche <a>`.
- **R4 Onglets du rôle** (toujours, si déclarés) : `[espaces.<a>].onglets`, dans l'ordre, 4 panneaux au plus chacun.
- **R5 Missions** (conditionnel) : au moins un agent est en mission chez `a` → onglet Missions : le suivi
  (`berger panneau missions <a>`) puis la conversation de chaque agent hébergé (protégée). `depuis` = la plus ancienne
  mission en cours (borne connue).
- **R6 Équipe** (conditionnel) : `a` est chef de projet (`[equipes.<p>].chef_projet`) → le même onglet s'appelle Équipe ;
  sa condition est vraie s'il héberge un agent OU si un développeur de son équipe est ouvert (agent.conf `projet`/`sujet`).
  Condition fausse : `depuis` = dernière fermeture de développeur archivée (`historique/equipe/<sujet>-AAAA-MM-JJ_HHMM`).
- **R7 Délai de 24 h** : un onglet Missions/Équipe dont la condition est fausse reste voulu tant qu'elle l'est depuis
  moins de 24 h ; au-delà, ou si la date est inconnue, il n'est plus voulu (comme aujourd'hui : l'onglet n'existe pas
  ou est fermé dès qu'il est vide). Pour Missions, la date de fin vient des agents encore inscrits dans
  `.herdr.json › missions` de l'hôte sans y être en mission (`historique/mission-AAAA-MM-JJ_HHMM.md`).

Jamais voulu ni à fermer : la conversation d'un agent (`protege`), un onglet inconnu (les règles ne parlent que des onglets
qu'elles nomment).

## Inchangé

`espace()`, `refaire_espace()`, `ouvrir_en_mission()`, `fermer_mission()` et le planificateur gardent leur résultat. Deux
petits extraits communs, à résultat identique : `moteurs_espace(a)` (moteurs de l'onglet Travail) et `domaine_travail(a)`
(panneaux du métier de la colonne Travail), utilisés par `espace()`/`colonne_travail()` et par `espace_voulu()`.

## Refus

- Agent inconnu → erreur claire, code non nul, rien d'écrit.
- `espace_voulu` n'appelle jamais Herdr (vérifié par un faux Herdr qui ne doit recevoir aucun appel). Seule exception, héritée
  de `commande_element()` : un élément `fichiers` lit le dossier de réglages du plugin lecteur de fichiers, s'il est installé.

## Tests

`tests/regles-espace.py` (installation jetable, faux Herdr à état) :
- preuve d'identité : pour un agent ordinaire, un agent avec `[espaces.<a>]` (a_cote + onglets) et un agent en mission
  avec moteur imposé, `berger espace` construit exactement les onglets et panneaux de `espace_voulu` (libellés, ordre,
  commandes, moteurs) ; idem pour l'onglet Missions construit par `ouvrir_en_mission`, et Équipe chez un chef ;
- R2 (agent hébergé : onglet « Mission » + journal), R6 (développeur ouvert sans hébergement → Équipe voulue), R7 (fin
  il y a 2 h → encore voulu ; il y a 30 h → plus voulu ; date inconnue → pas voulu) ;
- aucun appel à Herdr pendant `berger espace-voulu` ; agent inconnu refusé ;
- `--json` conforme au schéma, chaque champ produit, champs avec `x-libelle`/`x-rendu` (aussi contrôlé par tests/interface.py).
