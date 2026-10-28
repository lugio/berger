# Fusion de la ligne de l'installation avec la ligne de développement : les conflits et leur résolution

Spec : `docs/plans/2026-10-26-fusion-vm-spec.md` (règle de go, cas 1). Branche `berger/fusion-vm`.
Commit de fusion : `git merge dev/main` (a195814) sur la ligne de l'installation (db14325 + la spec, f3ec2ac). Ancêtre commun
d6eb28e. Aucun rebase, aucun cherry-pick, aucune réécriture : les deux historiques restent entiers.

Règles appliquées quand les deux lignes se contredisent (spec, « Comportement ») :
(a) transport privé de la ligne de développement ; (b) neutralité ; (c) CI de la ligne de développement ; (d) sinon le plus
prudent, avec le choix écrit ci-dessous.

## Les 11 fichiers en conflit

### 1. `README.md`
- **Développement** : le README devient la vitrine anglaise courte ; le manuel français complet part dans `docs/manuel.md`
  (corps figé par empreinte dans `tests/vitrine.py`), et `README.fr.md` naît.
- **Installation** : ajouts au manuel d'alors — verbe `prod`, `verifier-depot` qui cherche le nom du propriétaire aussi dans
  un mot, `berger-outil besoin`, règle de go (`equipe go`), demande mise en attente (`attente`/`reprendre`), besoin et annonce
  d'un changement d'outil, gardien → chef de chaque équipe, relance d'un agent en boucle, redémarrage du courtier avec
  fermeture, « À lire » qui se vide, Livrables et Documents, temps réel, garde-fou anti-boucle.
- **Résolution** : `README.md` = la vitrine du développement. Les ajouts de l'installation sont reportés dans `docs/manuel.md`
  (même texte, aux mêmes endroits ; deux sections nouvelles, « Mise en production d'un projet : le verbe prod » et
  « Garde-fou anti-boucle », ajoutées au sommaire). Les commandes citées passent à la forme du transport privé (`--fichier
  .transport/requete.json`, paramètres en JSON). L'empreinte du manuel dans `tests/vitrine.py` est mise à jour, comme la
  ligne de développement le fait à chaque changement voulu du manuel (f7c1281) ; le contrôle reste entier.
- Neutralité (b) : dans le texte reporté, le nom de la machine d'infrastructure, les noms d'agents réels et le nom de l'outil de
  vérification d'un projet sont remplacés par des termes génériques (voir « Neutralité » plus bas).

### 2. `bin/berger` (8 blocs)
1. **Aide** : développement = `berger --stdin` pour mission / equipe / projet, commandes web ; installation = `berger besoin
   [liste]`, `besoin clore`, aide du redémarrage du courtier. → les deux.
2. **`parler`** : développement = remise par l'API Herdr (`herdr_api("agent.prompt")`, le texte n'est plus un argument de
   `herdr`) ; installation = `solliciter(a)` après la remise (anti-boucle). → l'API Herdr (a) **et** `solliciter`.
   L'appel `herdr agent prompt <cible> <texte>` de l'installation est retiré (il mettait le texte dans les arguments).
3. et 4. **`decider`** : développement = `--duree` d'un accès web (`module_web`) ; installation = `file_tenue_texte()` (la
   réponse dit « file tenue » pendant une installation ou un redémarrage). → les deux : la durée est contrôlée, la décision
   écrite avec sa durée, puis la file tenue est dite.
5. **Synthèse** : `alertes_consignes()` (installation) et `alertes_moteurs()` (développement). → les deux.
6. **Décisions** : installation = une note dont l'objet lié est réglé (« Lié à : ») ne demande plus de décision ;
   développement = `decision_document_resolue(texte)`. → les deux conditions.
7. **`verifier_depot`** : installation = le nom du propriétaire cherché AUSSI à l'intérieur d'un mot ; développement =
   exception de l'URL du dépôt public, marque privée refusée même collée à un point, un tiret ou un souligné. → la version du
   développement, plus la règle de l'installation pour le nom du propriétaire (le plus strict des deux, (d)).
8. **`equipe`** : développement = contrôle d'usage commun (`besoin`/`usage`, projet inconnu) ; installation = `equipe go`.
   → la structure du développement avec `go` (4 paramètres) ajouté au contrôle et à l'usage.

### 3. `bin/vues/decisions.schema.json`
Genres `besoin` (installation) et `proposition`, `signalement` (développement). → les trois.

### 4. `commun/REGLES.md`
- Développement : paramètres privés en JSON (`--stdin`, `--fichier`), `deleguer`/`ecrire` sous cette forme, blocage d'un garde-fou
  signalé sans contourner.
- Installation : `berger-outil besoin`, annonce d'un changement d'outil.
- **Résolution** : les deux ; `besoin` et `equipe go` (venus de l'installation) écrits à la forme du transport privé (a) ;
  le nom de la machine d'infrastructure remplacé par « jamais à un autre agent » (b).

### 5. `commun/modeles/equipe-chef-de-projet.md`
Installation : règle de go (`equipe go`, `Hors go`), verbes `attente` / `reprendre`. Développement : toutes les commandes en
`--fichier`. → le texte de l'installation, chaque commande à la forme du développement.

### 6. `commun/skills/berger/SKILL.md`
Installation : description complète de `berger courtier redemarrer`, règle de go, `attente`/`reprendre`. Développement : tableau des
commandes en `--stdin`, développeur et chef de projet en `--fichier`. → la forme du développement, le contenu de l'installation
réinséré (règle de go, `attente`/`reprendre`, redémarrage) ; `besoin` et `besoin clore` à la forme privée ; le nom de la machine d'infrastructure →
« jamais un autre agent ».

### 7. `config.exemple.toml`
Installation : `[besoins]`, `[courtier]` (anti-boucle, `mission_max`, redémarrage), `[relance]`, `[annonces]`. Développement :
`[web]`. → les deux blocs (le fichier se lit en TOML).

### 8. `courtier/berger-outil`
- Développement : client réécrit — paramètres en tableau JSON par `--stdin` ou `--fichier .transport/…` (fichier 600 dans un dossier
  700, consommé), aucun contenu positionnel, réponse privée relue sans suivre de lien.
- Installation : une demande rangée dans `courrier/attente/` (courtier en redémarrage) fait repartir les délais ;
  `BERGER_OUTIL_PRISE` (délai de prise, pour les tests).
- **Résolution** : le client du développement (a), avec le dossier `attente` ouvert comme les autres (700, propriétaire vérifié)
  et les deux comportements de l'installation.

### 9. `courtier/courtier` (4 blocs)
1. **Exécuteur** : `file_tenue()` toutes les 2 s (installation) et `expirer_web()` (développement). → les deux.
2. **Anti-boucle + `trop_long`** (installation) et **`ecrire_reponse_privee`** (développement). → les deux ; toutes les
   réponses, y compris celles des verbes de l'installation, passent par `ecrire_reponse_privee`.
3. **Démarrage** : `reprendre_executions(); WEB.nettoyer()` (développement) puis fin de la fermeture (installation). → les deux.
4. **Boucle principale** : `consignes_dues` (installation) et `WEB.tour()`, `sockets_mcp()` (développement). → les trois.

Hors des blocs, pour tenir (a) : les appels de l'installation vers `bin/berger` qui portaient un texte d'agent dans leurs
arguments passent par `_transport.executer` (corps et arguments sur stdin) : `equipe go`, `besoin clore`, `besoin-ranger`,
`message-deposer` (alerte de boucle au gardien) et `annonce-outil`. Sans cela, `message-deposer` et `equipe` étaient de toute
façon refusés par `bin/berger` hors transport privé.

**Coupure silencieuse** : la ligne `str(a)[:2000 if … else 80]` a disparu (l'installation l'avait déjà remplacée par un refus :
`trop_long`, `mission_max`). Deux coupures restaient dans les DEUX lignes et sont retirées (d) :
- le sixième argument d'une demande tombait en silence (`[:5]`) → refusé, « trop d'arguments (5 au plus) » ;
- un argument de panneau (`config.toml`) était coupé à 80 caractères → le panneau est refusé, avec l'erreur.
Test : `tests/courtier-textes.py` (six arguments refusés, cinq intacts ; panneau 81 refusé, 80 intact ; contrôle du source :
plus aucun `str(a)[:N]`, `args[:5]` ni texte joint coupé).

### 10. `tests/interface.py`
`NEES_APRES` gagne `documents` (installation) ; `VUES_REVISEES` (développement) est gardé. → les deux.

### 11. `tests/suites.sh`
Suites des deux lignes : `regle-go`, `anti-boucle`, `verbe-prod`, `temps-reel`, `alire-se-vide` (installation) et `modele-soul`,
`regles-espace`, `espace-auto`, `espace-agent`, `vitrine-*`, `communaute*`, `installer-master`, `mcp*`, `web*`, `contrat-*`,
`shims-mise` (développement). → toutes, aucune retirée.

## Adaptations hors conflit (même commit de fusion)

- Messages qui citent une commande à un agent, venus de l'installation, réécrits à la forme du transport privé : rappel du
  besoin au gardien (`besoin clore`), refus d'ouverture sans go (`equipe go`), alerte « fini sans redemander » (`attente`),
  refus du besoin (`ecrire`, `besoin`), refus de `_portes.py` (`equipe go`).
- Tests de l'installation adaptés au transport, jamais affaiblis : `redemarrage-courtier` (vrai client en `--stdin`),
  `regle-go` (`berger --stdin` pour `equipe`), `anti-boucle` (`parler --stdin`), `besoin`, `annonce-outil`,
  `courtier-textes`, `regle-go` (faux Herdr branché sur l'API par `tests/_herdr_api_factice.py`, comme les tests de la ligne de
  développement), `besoin` et `memoire-equipe` (la commande attendue est la forme privée).
- `tests/_herdr_api_factice.py` : la création du socket est dans le `try` ; un bac qui interdit AF_UNIX donne « NON JOUÉ »
  au lieu d'une trace Python (le cas prévu par ce fichier).
- Tests de la ligne de développement qui chargent une fonction seule et lui donnent ses dépendances : les fonctions
  appelées en plus par la ligne de l'installation leur sont données — `argv-client` (le vrai `trop_long` / `mission_max`,
  `controle_boucle` neutre), `argv-prive` (`solliciter` neutre), `web-security-review` (`fermeture_active` à faux).
- `tests/annonce-outil.py` : l'API Herdr remet le texte tel quel (retours à la ligne compris) ; le contrôle compare le
  même contenu, à plat.
- `tests/redemarrage-courtier.py` : `ignore_cleanup_errors` sur le dossier jetable ; un fils lancé à part par le courtier
  (message « Décision sur ta demande ») écrivait encore pendant le nettoyage (une fois sur trois passes, après 26 contrôles
  verts). Aucun contrôle n'est changé.

## Comportements abandonnés, et pourquoi

- `berger parler <agent> "<message>"` et `berger-outil <outil> <verbe> <texte…>` positionnels (installation) : remplacés par
  `--stdin` / `--fichier` (a). Rien d'autre n'est perdu : chaque verbe de l'installation existe sous la forme privée.
- `herdr agent prompt <cible> <texte>` : remplacé par l'API Herdr (a).
- Message remis aplati sur une ligne (`" ".join(texte.split())`, base commune) : le développement remet le texte tel quel ;
  gardé.

## Non mesuré

- `tests/tout.sh` (auto-test de l'installation : vrais agents, vrais moteurs, `config.toml` de l'installation) : ne tourne
  pas dans une copie de développeur. Le bloc de délégation par Codex est gardé par `command -v codex` dans la version de la
  ligne de développement, reprise telle quelle.

## Correctifs venus de dev/main : cause racine

Huit commits `fix…` de la ligne de développement n'écrivent pas leur cause racine. L'historique publié ne se réécrit pas :
elle est écrite ici et dans la demande (règle du correctif, `courtier/outils/_portes.py`, `correctifs`).

- `a026577` fix(vues): conserver les résultats et borner les titres longs — Cause racine : non écrite à l'origine ; d'après la
  différence : le titre d'une checklist passait à `titre_section` sans `couper(…, w)` et la ligne de sauvegarde du Courtier était
  coupée par `couper` au lieu d'être pliée : un titre long débordait, une date de sauvegarde longue perdait sa fin.
- `72b6f4a` fix(vues): préserver refus et livraisons sous forte activité — Cause racine : non écrite à l'origine ; d'après la
  différence : la vue Courtier ne gardait que les 200 DERNIERS appels (`lignes[-APPELS_MAX:]`), donc une rafale de lectures
  chassait les refus du jour ; et la vue Colonnes en mode compact affichait les colonnes dans l'ordre sans budget de lignes, si
  bien que « livré » tombait hors de l'écran.
- `a1def4c` fix(vues): harmoniser les attentes et préparer les captures fictives — Cause racine : non écrite à l'origine ;
  d'après la différence : le Tableau d'un agent recalculait seul ce qui attend le propriétaire (blocage, écritures,
  propositions, signalements) au lieu de lire `decisions()` ; les deux listes divergeaient (ex. propositions techniques ou
  sondes comptées comme décisions, document à décision déjà résolue encore affiché). Corrigé par une source unique,
  `decision_document_resolue` et `propositions_decidables`.
- `ec97ba9` fix(test): terminate upstream TLS in real MCP web fixture — Cause racine : non écrite à l'origine ; d'après la
  différence : le faux site amont de `tests/mcp.py` répondait en HTTP clair même à une poignée de main TLS (premier octet
  0x16) ; le tunnel HTTPS n'était donc pas vraiment prouvé (le contrôle acceptait `marque`/`hello` sans code 200).
- `5e1b917` fix(web): prepare journaled contract poses before atomic replacement — Cause racine : non écrite à l'origine ;
  d'après la différence : `Pose.poser` (tests/contrat-moteur.py) déplaçait l'original puis écrivait le nouveau fichier par
  `write_text` ; une interruption pendant l'écriture laissait un fichier à moitié écrit à la place de l'original. Maintenant :
  fichier temporaire journalisé, écrit et synchronisé, puis remplacement atomique.
- `7020063` fix(web): journal stacked certificate poses for interrupted contracts — Cause racine : non écrite à l'origine ;
  d'après la différence : deux poses au même chemin réutilisaient la même copie `.avant-contrat` (la seconde écrasait la
  sauvegarde de l'original) et la session web gardait ses publics en mémoire (`publics`), perdus si le contrat était coupé ;
  `retirer` vidait tout le journal au lieu de la seule phase.
- `4ffd248` fix(web): réserver les cookies à l'agent de session — Cause racine : non écrite à l'origine ; d'après la
  différence : `SessionCoffre.cookie` lisait l'entrée du domaine sans filtrer par agent (`self.lire(domaine)`), donc un autre
  agent ayant accès au même domaine pouvait recevoir les cookies de la session prêtée.
- `0aa31e6` fix(contrat): les greffons livrés avec Claude Code (@builtin) ne font pas échouer le contrôle (1) — Cause racine :
  le contrôle (1) refusait tout greffon listé par `init.plugins`, y compris ceux livrés dans le moteur (source `@builtin`) depuis
  la version mesurée du moteur ; il ne distinguait pas les greffons du moteur des greffons venus d'ailleurs (message du commit).

## Les 5 tests adaptés que master relit en premier

- `tests/regle-go.py` — faux Herdr branché sur l'API (`_herdr_api_factice`, corps sur stdin) ; `equipe` appelé par
  `berger --stdin` (tableau JSON) ; l'alerte attendue est la forme privée « attente --fichier .transport/requete.json, JSON : dev ».
  Pourquoi rien n'est affaibli : mêmes 122 contrôles, mêmes conditions ; seul le chemin d'appel change (le positionnel est
  refusé par la ligne de développement) et la chaîne attendue garde le verbe ET le sujet.
- `tests/annonce-outil.py` — le texte remis est comparé après `" ".join(texte.split())`. Pourquoi : l'API Herdr remet le
  texte tel quel (retours à la ligne) au lieu de l'aplatir ; en-tête, cadre, version, contenu et verbes restent tous exigés,
  dans le même ordre ; aucune condition retirée.
- `tests/web-security-review.py` — `fermeture_active=lambda: False` ajouté aux dépendances données à `traiter_decisions`.
  Pourquoi : la ligne de l'installation fait attendre les décisions pendant une fermeture du courtier ; à faux, la fonction suit
  le même chemin qu'avant ; les deux assertions (aperçu absent des argv, fichier 600) inchangées.
- `tests/argv-client.py` — `traiter` reçoit le VRAI `trop_long` / `mission_max` (et la constante des textes) lus dans le
  source, et `controle_boucle` neutre. Pourquoi : `traiter` les appelle désormais ; le refus réel des textes trop longs est sur
  le chemin testé (plus strict qu'un bouchon) ; l'anti-boucle a sa propre suite (`anti-boucle.py`) ; toutes les assertions
  du client privé inchangées.
- `tests/argv-prive.py` — `solliciter` neutre ajouté aux trois environnements qui chargent `demander`. Pourquoi : `demander`
  note une sollicitation (anti-boucle, prouvée par `anti-boucle.py`) ; le test vérifie toujours l'absence du contenu dans les
  argv, l'entrée sur stdin, les droits 600/700 et le nettoyage.

## Neutralité (renvoi du 26/10)

Les textes venus de la ligne de l'installation citaient la machine d'infrastructure, des agents et un projet réels, l'outil de
vérification de ce projet, le logiciel métier, un organisme et un pare-feu de marque. Ils sont remplacés par des termes
génériques (« l'agent d'infrastructure », « la machine distante », « un projet métier », « le chef de projet », « le coordinateur »,
« l'outil de vérification du projet », « le logiciel métier », « le serveur de production »). Les mentions déjà présentes dans
dev/main ne sont pas touchées. Contrôle : aucune ligne nommant ces marques n'existe dans la branche sans exister dans dev/main.

Effets sur le comportement :
- `GO_MOTS` (mots qui marquent un sujet de la règle de go, `courtier/outils/_portes.py`) : le nom du logiciel métier devient
  « logiciel métier » et la marque du pare-feu est retirée (« pare-feu » reste). Une installation qui veut ces noms les déclare
  dans `[equipes.<p>] go_mots` de SON `config.toml` (hors dépôt).
- `tests/verbe-prod.py` : le contrôle « script générique » ne contient plus de nom de projet écrit en clair ; il cherche les
  `marques_privees` du `config.toml` de l'installation qui le joue (et verifier-depot contrôle tout le dépôt).
- `tests/besoin.py`, `tests/regle-go.py`, `tests/annonce-outil.py` : noms d'agents et d'organisme des jeux d'essai remplacés
  par des noms fictifs ; mêmes contrôles.

## Suites affichées « 0 contrôles » (relecture du 26/10)

Mesure : chaque suite de `tests/suites.sh` jouée seule, dans le même bac (sans AF_UNIX, /tmp en lecture seule), sur un clone de
la branche (d0b6023) et sur un clone de dev/main (a195814). Résultat : **aucune suite n'est vidée par la fusion.**

- **Suites unittest** — elles jouent leurs tests, mais n'écrivent pas de ligne « ok », que `suites.sh` était seul à compter.
  Même nombre de tests joués, aucun sauté, des deux côtés : web-security-review 5, web-session-proxy 42, web-https 14,
  contrat-session 10, contrat-web 3, web-relais 12, web-relais-mission 1, web-connecter 11, web-profils-masques 3,
  web-session 10, argv-cli 6, argv-config 4, argv-connecteurs 2, argv-herdr 15, argv-imbrique 9, argv-shell 6.
  argv-prive (14) et codex-ouverture (31) : même code 1 des deux côtés dans ce bac (/tmp en lecture seule) ; verts dans la porte.
- **Suites NON JOUÉES dans ce bac** (AF_UNIX refusé), avec leurs contrôles dans la porte (hors bac) : courtier-textes,
  regle-go, anti-boucle, besoin, annonce-outil (installation) ; ecrire, hierarchie-equipe, suivi-delegations, supervision
  (développement : dans ce bac, dev/main sort en trace Python, la branche dit « NON JOUÉ » grâce à `_herdr_api_factice`) ;
  contrat-socket et tmp-par-agent : NON JOUÉ des deux côtés.
- Correction de la mesure : `suites.sh` compte maintenant aussi les tests unittest joués (« Ran N tests », moins les sautés),
  et une suite qui ne joue aucun contrôle est écrite « NON MESURÉE » sur sa ligne, jamais seulement « ok ».
