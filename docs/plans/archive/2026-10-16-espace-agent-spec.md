# Disposition sur mesure par agent : agents/<a>/espace.toml (2026-10-16, sujet 3/3)

Go du propriétaire le 15/10, niveau B : après les règles fixes (R1…R7, sujet 1) et leur application par le planificateur
(espace auto, sujet 2), chaque agent peut avoir SA disposition, rangée dans son dossier et changée par le circuit validé
des propositions d'agent.

## Constat

La disposition propre à un rôle (`a_cote`, `onglets`) ne vit que dans `[espaces.<a>]` de `config.toml`, que le propriétaire
seul retouche à la main. Un agent gardien (outil `berger-admin`) peut proposer de changer l'`agent.conf` ou le `SOUL.md`
d'un agent, avec aperçu et validation, mais pas sa disposition.

## Comportement

- **Fichier** `agents/<a>/espace.toml`, mêmes clés que `[espaces.<a>]` :
  `a_cote = ["checklists", "panneau:missions"]` (3 au plus) et `onglets = { "Suivi" = ["source:alertes"] }` (4 éléments au
  plus par onglet). Éléments : ceux de `commande_element` (`source:a,b`, `checklists[:mots]`, `panneau:<type>`, `fichiers`).
- **Priorité** : `espace_conf(a)` rend la table de `espace.toml` s'il porte au moins une des clés `a_cote` / `onglets`, sinon
  `[espaces.<a>]` de `config.toml` (qui continue de marcher), sinon rien (le `domaine` d'agent.conf). Le fichier est relu à
  chaque appel (le planificateur voit un changement sans redémarrage). Toutes les lectures passent par lui :
  `elements_cote`, `onglets_agent_conf`, `domaine_travail`, `commandes_panneaux` (reprise), `espace_voulu` (dont les raisons
  nomment la source : « agents/<a>/espace.toml » ou « [espaces.<a>] »).
- **Fichier vide de clés** (seulement des commentaires) : sans effet, la disposition de `config.toml` s'applique.
  `berger regenerer` le crée ainsi pour chaque agent qui n'en a pas (voir Protection) ; il ne réécrit jamais un fichier existant.
- **Fichier illisible** (TOML invalide) : ignoré, la disposition de `config.toml` s'applique ; `regenerer` le signale
  (`⚠ <a> : espace.toml illisible …`). Une clé inconnue est ignorée et signalée de même.
- **Éléments contrôlés comme aujourd'hui** : un élément inconnu écrit à la main s'affiche comme un message
  (`élément inconnu dans agents/<a>/espace.toml : …`), jamais exécuté.
- **Proposition d'agent** : un bloc `=== espace.toml` dans `propositions/<agent>.md` est accepté. `agent-apercu` montre la
  différence du fichier ET une section `DISPOSITION (avant → après)` : la disposition effective avant (avec sa source :
  config.toml ou espace.toml) et après. `agent-appliquer` (validé par le propriétaire) l'écrit avec sauvegarde
  `.avant-<date>`, comme les autres fichiers. Une proposition qui ne change QUE `espace.toml` ne relance pas l'agent (sa
  conversation n'en dépend pas) : sa dernière passe d'espace auto est effacée, le planificateur applique la disposition à
  son passage suivant (la minute d'après) et note chaque geste au journal de l'agent.
- **Protection** : l'agent lit son `espace.toml` mais ne l'écrit pas, comme son `agent.conf` : Claude (refus d'édition
  `Edit(...)` + `sandbox.filesystem.denyWrite`), Codex (`"<chemin>" = "read"`). Codex refuse de démarrer sur un chemin
  absent : c'est pourquoi `regenerer` crée le fichier vide avant d'écrire les réglages.

## Refus (à l'aperçu ET à l'application)

- `espace.toml` en TOML invalide ;
- une clé autre que `a_cote` / `onglets` ;
- `a_cote` qui n'est pas une liste de textes, ou plus de 3 éléments ;
- `onglets` qui n'est pas une table de listes, plus de 4 éléments dans un onglet, un onglet vide, un libellé vide, de plus
  de 30 caractères ou avec un caractère de contrôle ;
- un élément inconnu (genre hors de `source`, `checklists`, `panneau`, `fichiers` ; `source:` sans nom ou avec autre
  chose que lettres, chiffres, `,` `.` `_` `-` ; `panneau:` hors de `[a-z]+`) ;
- et les refus communs : ses propres réglages (`cible == demandeur`), un développeur d'équipe, le coffre cité.

## Tests

`tests/espace-agent.py` (installation jetable, faux Herdr, jamais le vrai), dans `tests/suites.sh` :
- **priorité** : `[espaces.x]` dans config.toml seul → sa disposition ; `espace.toml` avec clés → la sienne (Travail,
  onglets, raisons qui nomment le fichier) ; `espace.toml` sans clé ou illisible → celle de config.toml ; agent sans les
  deux → `domaine` ;
- **proposition appliquée** : aperçu avec `DISPOSITION (avant → après)`, empreinte ; application → fichier écrit,
  sauvegarde, pas de relance de l'agent, passe d'espace auto effacée ; puis la passe d'espace auto ajoute le panneau et
  l'onglet nouveaux dans le faux Herdr ;
- **élément inconnu** : refusé à l'aperçu et à l'application (rien écrit) ; écrit à la main → affiché comme message ;
  clé inconnue, trop d'éléments, TOML invalide refusés ;
- **écriture refusée à l'agent** : après `regenerer`, `espace.toml` existe ; réglages Claude (`Edit` refusé + `denyWrite`)
  et profil Codex (`read`) le protègent ; un fichier existant n'est pas réécrit ; l'agent ne propose pas le sien.
- `tests/agent-appliquer.py` et `tests/regles-espace.py` restent verts.
