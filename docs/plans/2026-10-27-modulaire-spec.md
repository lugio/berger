# Berger modulaire : un cœur mince, un socle à API explicite, des modules écartables (spec)

Règle de go : **mixte**. Les lots 1 à 3 ne touchent ni courtier, ni mur, ni secret : le coordinateur décide seul. Le **lot 4 est cas 1**
(courtier, gardes, droits, règles de validation) : il attend le go du propriétaire, **inscrit** sur CE fichier, avant la première ligne de code.
Cette spec elle-même n'est que du texte : aucun code n'est écrit tant que le lot concerné n'a pas son go.
Rien de propre à un moteur : `moteurs/` isole précisément ce qui l'est.

## Constat (mesuré sur `main`, 37488cd)

**`bin/berger`** : un seul fichier de **6 089 lignes**, 374 fonctions, 126 affectations globales (118 noms distincts), 30 sections
(commentaires `# ───`), aucune classe. Sections les plus lourdes : équipes de développement 527 lignes, serveurs MCP 472, réveils et
tâches 421, À lire 346, admission d'un moteur 335, installer 318, missions 325. `main()` aiguille par une chaîne de
`elif cmd == "…"` sur **58 verbes** ; la liste des verbes à entrée privée (`mission`, `message-deposer`, `equipe`, `projet`) est
écrite en dur dans `main()`. L'aide du programme est une seule docstring de 68 lignes, séparée du code des verbes.
Le fichier est chargé de deux façons : lancé (`main(sys.argv)`), et **importé par chemin** par une partie des tests
(`SourceFileLoader`, ex. `tests/echanges.py`) ; 87 des 133 fichiers de `tests/` le nomment.

**`bin/vues/`** : 22 vues + 22 schémas, **1 131 lignes** de Python, chargées par `charger_vues()` (bin/berger:6060). Ce chargeur fait
`mod.__dict__.update({k: v for k, v in globals().items() …})` : **chaque vue reçoit une copie de TOUTES les globales du cœur**
(les ≈ 500 noms de premier niveau). Aucune frontière : n'importe quelle vue peut appeler n'importe quelle fonction du cœur, y
compris celles qui écrivent. Mesuré par analyse syntaxique : les 22 vues n'emploient en réalité que **71 noms du cœur** (56 fonctions,
15 constantes) ; l'écart (≈ 500 reçus, 71 utilisés) est la frontière qui n'existe pas. Le sens inverse existe aussi :
`globals().update(vue_*)` remet dans le cœur les fonctions `vue_x` des vues, pour les appels directs (bin/berger:4380 et autres).
Ce qui marche bien et qu'on garde : une vue qui ne charge pas est **écartée et nommée** (`VUES_REFUSEES`, `berger etat`, `berger vues
--json`) et les autres s'affichent ; le contrat d'une vue (TITRE, ICONE, ONGLET, ORDRE, `rendre`, et `donnees`/`rendu_texte`/schéma).

**`courtier/outils/`** : le modèle à imiter. 19 fichiers, 3 768 lignes avec le courtier ; le plus gros outil (`equipe_chef.py`) fait
540 lignes. Chaque outil est un module qui déclare ses `verbes` (et ses écritures) ; le courtier les instancie d'après `config.toml`,
nomme l'outil en défaut et continue ; les aides communes (`_transport.py`, `_contexte.py`, `_portes.py`, `_commandes.py`) commencent par
`_` et ne sont pas des outils. Chaque outil n'a que ce que le courtier lui passe.
Limite à noter : `courtier/courtier` fait 1 485 lignes, c'est la taille de référence de la limite proposée plus bas.

**Cause racine** (pourquoi il faut un chantier et non un correctif) : Berger a grandi par ajout de sections dans un fichier unique, et le
seul mécanisme de découpage (les vues) a été fait par copie de l'espace de noms plutôt que par une interface. Un défaut dans une
section peut donc casser tout `berger` (le fichier entier ne se compile plus), et personne ne peut dire ce qu'une fonction a le droit
d'utiliser ni qui l'appelle.

## Cible

```
bin/berger               porte d'entrée mince : arguments, entrée privée, chargement, aiguillage. ≤ 250 lignes.
bin/noyau/               socle commun, API EXPLICITE (noyau/api.py = la liste nommée ci-dessous).
bin/commandes/<famille>.py   une famille de verbes par fichier, découverte comme les vues.
bin/moteurs/<moteur>.py      un fichier par moteur.
bin/vues/                inchangé dans sa forme ; n'emploie plus que l'API du noyau.
courtier/outils/         inchangé (déjà modulaire).
```

**Règle d'or** : un module (vue, commande, moteur) n'utilise que (a) le langage et la bibliothèque standard, (b) l'**API du noyau**,
(c) ses propres noms. Il ne lit jamais les globales de `bin/berger`, ne s'appelle pas d'un module à l'autre (la famille A ne
cite pas la famille B ; ce que deux familles partagent monte dans le noyau, par ajout explicite à l'API).

### Le noyau et son API

`noyau/` contient les modules `config.py`, `agents.py`, `herdr.py`, `transport.py`, `affichage.py`, `lectures.py`. Seuls les noms
listés dans `noyau/api.py` (`API = (…)`, tuple trié par groupe) sont **publics** ; tout le reste du noyau est privé (préfixe `_`
ou absent de la liste). Le chargeur donne à chaque module une vue **filtrée** de l'API : un nom absent de la liste n'existe pas pour
lui (erreur `NameError` à l'appel, donc détectée à l'écart du module, voir « Isolation »). Le code des vues ne change pas
(`couper(...)` reste `couper(...)`) : seule l'origine des noms change, de « copie de tout » à « API filtrée ».

**Liste nommée de l'API** (état de départ : les 71 noms que les vues emploient aujourd'hui, regroupés ; la liste est figée à la fin du
lot 1 et ne bouge ensuite que par une ligne ajoutée à `api.py` AVEC son test). Signature = celle de aujourd'hui.

*Constantes et chemins (`config.py`)* : `BERGER` (racine de l'installation), `HOME`, `AGENTS`, `EQUIPES`, `MISSIONS`, `ECHANGES`,
`GARDES`, `PROPRIETAIRE`, `PANNEAUX_SOURCES`, `LECTEURS_CONSO` (rempli par `moteurs/`, voir lot 2), `STATUTS`, `RUBRIQUES_FICHE`.

*Agents et fichiers (`agents.py`)* :
- `agents()` : liste des agents inscrits ; `dossier(a)` : leur dossier ; `conf(a)` : leur `agent.conf` lu ; `agent_court(a)` : nom d'affichage ;
- `lire(p, defaut='')` : texte d'un fichier ou défaut ; `json_ou_rien(f)` : JSON d'un fichier ou rien ;
- `aujourdhui()` : date du jour (Europe/Paris) ; `quand_iso(ts)` : horodatage lisible ;
- `checklist(a)` / `cases(texte)` : checklist d'un agent et ses cases ; `dossier_skills()` / `skills_demandees(a)` / `methode(nom)` : skills ;
- `hote_mission(a)`, `reglages_mission(a)` : ce qui tient à la mission en cours d'un agent.

*Herdr (`herdr.py`)* : `herdr(*args)` (appel de la commande), `herdr_api(methode, params, strict=False)`, `socket_herdr()`,
`statut_herdr(pane, ttl=15)`, `herdr_ids(a)`. Une seule porte vers Herdr ; aucune commande ne lance `herdr` elle-même.

*Transport privé (`transport.py`)* : `entree_privee()` (stdin borné à 1 Mio, UTF-8), `executer(...)`, `executer_shell(...)`, `lancer(...)`
(ceux de `courtier/outils/_transport.py`, réexportés tels quels), `ecrire_configuration(dossier, nom, texte)`. **Aucune** commande
ne construit un sous-processus autrement : c'est la garantie « aucun texte d'agent dans les arguments d'un processus ».

*Affichage (`affichage.py`)* : `ANSI`, `TONS`, `COLONNES_TONS`, `vlen(t)`, `pad(t, w)`, `couper(t, w)`, `plat(t)`, `plier(t, w, debut='',
suite=None, style='')`, `titre_section(t, couleur, w)`, `entete(c, vue, w, droite='')`, `mini_entete(c, rubrique, w)`, `section(md, titre)`,
`rendre_markdown(texte, w=100)`, `kilo(n)`, `ligne_texte(l)`, `carte_colonne(titre, lignes, larg, vif=False)`,
`statuts_texte(statuts)`, `colonnes_tableau_texte(dt_, w)`.

*Lectures en lecture seule (`lectures.py`)* : les lecteurs que les vues et les verbes partagent et qui **n'écrivent rien** :
`documents()`, `documents_a_lire()`, `lus()`, `id_document(doc)`, `livrables()`, `decisions()`, `dossier_checklists()`,
`checklist_donnees(ck)`, `statuts_donnees(a)`, `validation_donnees(d)`, `en_attente(agent=None)`, `alertes_synthese()`,
`cartes_donnees()`, `tableau_donnees(a)`, `etat_source(nom, p)`, `gravite(ligne, p)`, `propre(t)`, `depuis(al)`, `courtier_actif()`,
`droits_agents()`, `derniers_usages()`, `collecter_conso()`, `quota_moteurs()`, `quand_remise(ts)`, `verbes_outil(o)`.

Tout ce qui **écrit** (noter, déposer, mission, ecrire, besoin, réveils, sauvegarde…) n'est **pas** dans l'API : une vue n'a pas à le
faire, et c'est ce que l'API rend impossible.

### Les commandes

Un fichier par famille, découvert comme les vues (dossier lu, fichiers `_…` ignorés). Contrat d'un module de commandes :

```
FAMILLE = "alire"                       # nom court, affiché par `berger etat`
VERBES  = {"lire": fn, "livrable": fn}   # verbe -> fonction(args, prive=False)
AIDE    = {"lire": "berger lire [n] …"}  # une ligne d'aide par verbe : `berger aide` la compose, plus de docstring unique
DROITS  = {"lire": {"prive": False, "cas_go": None}}   # déclarés par verbe : entrée privée obligatoire ?  cas de la règle de go (1 à 5) ?
```

`main()` ne connaît plus aucun verbe : il cherche `cmd` dans le registre bâti au chargement (même principe que `VUES`). L'obligation
d'entrée privée (`mission`, `message-deposer`, `equipe`, `projet` aujourd'hui) vient de `DROITS[...]["prive"]`, plus d'un tuple dans
`main()`. Deux familles qui déclarent le même verbe : les DEUX sont écartées et nommées (jamais « la dernière gagne »).

**Familles prévues** (les 58 verbes actuels, répartis) : *affichage* (etat, vue, vues, panneau, statusline, titres, interface, web) ;
*alire* (lire, livrable) ; *tokens* (abonnement-claude et la lecture de consommation) ; *reveils* (reveil, tache, planificateur,
superviser, entretien, relancer, reprendre, veille, notifier) ; *espaces* (espace, espace-voulu, refaire-espace, agent, nouveau,
regenerer) ; *memoire* (noter, memoire, validations) ; *depot* (verifier-depot, installer, restaurer, sauvegarder,
verifier-sauvegarde, secrets, coffre) ; *missions* (mission, fin-mission, rapport-mission, suivi, delegation-suivi) ; *messages*
(message-deposer, message-remettre, demander, parler, parler-interactif, echange) ; *equipes* (equipe, projet, crochet-equipe) ; *besoins*
(besoin, besoin-ranger, annonce-outil) ; *courtier* (courtier, mcp-enveloppe, lancer, moteur, args). La répartition définitive est
confirmée en lot 3/4 par un tableau « verbe → famille » dans le manuel ; un verbe oublié est repéré par un test (voir Tests).

### Les moteurs

Un fichier par moteur, `moteurs/claude.py` et `moteurs/codex.py`. Contrat : `NOM`, `executable()`, `version()`, `verdict(a)` (admission :
le moteur est-il utilisable pour cet agent), `args(a, interactif=True)` (lancement), `lecteur_conso()` (lecteur de tokens : donne
`LECTEURS_CONSO[NOM]`), et ses constantes propres (les `CODEX_*` aujourd'hui dispersées dans le haut de `bin/berger`).
`MOTEURS` n'est plus écrit en dur : c'est la liste des moteurs chargés, dans l'ordre déclaré. Ce qui est vrai de tous les moteurs
(`moteur_admis`, `choisir_moteur`, `alertes_moteurs`) reste dans le cœur de `moteurs/__init__.py`. Un moteur qui ne charge pas est
écarté et nommé ; un agent qui le demande reçoit « moteur <x> écarté : <cause> » (jamais un repli silencieux sur l'autre).

### Isolation partout

Un module (vue, commande, moteur) **cassé est écarté et nommé** : l'erreur est rangée dans `…_REFUSEES[nom] = "Type: message"`,
visible par `berger etat` et `berger vues --json` (même forme que `ecartees` aujourd'hui), et **tous les autres tournent**. Exception
assumée et écrite : le **noyau** n'est pas écartable (sans lui rien ne fonctionne) ; s'il ne charge pas, `berger` s'arrête avec un
message qui nomme le fichier et la cause, comme le fait déjà le courtier pour un nom d'outil en double.

### Limite de taille

Aucun fichier de `bin/` ne dépasse **1 500 lignes** (taille actuelle du courtier). Test dédié. Pendant la migration, `bin/berger` est
dans une liste d'exceptions **décroissante** (« cliquet ») : le test refuse qu'il grossisse, et la limite descend à chaque lot ; à la
fin du lot 4 il est sous 250 lignes et la liste est vide. Les deux plus gros ensembles actuels (équipes 527 lignes, MCP 472) tiennent
chacun dans un fichier.

## Règles du chantier (valent pour les quatre lots)

1. **Déplacement pur.** Un lot déplace du code ; il ne corrige, ne renomme et n'« améliore » rien. Un défaut vu en route est noté
   (`TODO.md`, demande de leçon) et traité dans une demande à part, jamais glissé dans un déplacement.
2. **Aucun comportement changé** : mêmes verbes, mêmes options, mêmes textes d'erreur, mêmes fichiers écrits, mêmes sorties. La sortie de
   `berger aide` peut changer de présentation seulement si chaque verbe y reste, vérifié par le test de couverture des verbes.
3. **Aucun test retiré ni affaibli.** Les tests qui chargent `bin/berger` par chemin continuent de fonctionner : `bin/berger` reste
   importable sans lancer `main()` et expose toujours les noms que ces tests lisent (liste établie au lot 1 par recherche dans
   `tests/`) ; s'il faut adapter un test, c'est pour la forme d'accès, avec la même assertion, et la demande le dit ligne par ligne.
4. **`tests/tout.sh` et la CI verts à chaque fusion**, y compris le clone frais (`tests/clone-frais.sh`). Une suite qui ne peut pas
   tourner est « non mesurée », jamais « verte ».
5. **Transport privé inchangé.** `--stdin`, la limite de 1 Mio, le refus des commandes privées imbriquées, aucun texte d'agent en
   argument : strictement comme aujourd'hui (`tests/argv-*.py` et `contrat-*` restent verts, sans modification).
6. **Neutralité du dépôt inchangée** : `verifier-depot` vert, contrôle sans-marques vert ; aucun nom de projet, de personne ni
   d'éditeur réel dans les nouveaux fichiers ni dans leurs commentaires.
7. **Manuel et docs à jour à chaque lot** (`docs/manuel.md`, README, CHANGELOG, skill `berger` du dépôt) : chaque lot dit où est
   maintenant ce qu'il a déplacé.
8. **Sauvegarde d'abord** : avant chaque installation d'un lot, l'état est sauvegardé et vérifié ; le retour arrière est la commande
   existante d'`installer` (retour automatique si une vérification échoue).

## Refus

- Toute demande qui mélange déplacement et changement de comportement.
- Tout module qui lit les globales de `bin/berger` ou importe un autre module de même rang.
- Tout ajout à l'API du noyau sans test ni ligne de manuel.
- Un test retiré, désactivé ou affaibli pour faire passer un lot.
- Un lot 4 sans go inscrit du propriétaire sur cette spec.
- Un module cassé qui arrête les autres, ou qui est écarté sans être nommé.

## Tests

Existants : tout `tests/` reste vert sur chaque commit de fusion (voir règle 4). Nouveaux, chacun ajouté avec le lot qui l'exige :

- **Contrat d'API** (`tests/contrat-noyau.py`, lot 1) : analyse syntaxique de chaque module de `vues/`, `commandes/`, `moteurs/` ; chaque nom libre
  (ni local, ni builtin, ni stdlib importée) doit être dans `API`. Échoue en nommant le fichier, la ligne et le nom.
  Deuxième moitié : chaque nom de `API` existe dans le noyau (pas de nom fantôme).
- **Frontière à l'exécution** (lot 1) : un module de test qui cite un nom du cœur hors API est écarté et nommé ; une vue saine voisine
  tourne. Prouve « un module cassé n'arrête pas les autres », pour vues, commandes, moteurs (un test par rang).
- **Pas de lecture arrière** (lot 1) : après chargement, aucun `vue_*` n'est injecté dans les globales du cœur ; les appels directs
  passent par le registre.
- **Couverture des verbes** (`tests/commandes-couverture.py`, lot 3) : la liste des 58 verbes d'aujourd'hui, figée dans le test, est
  égale à l'union des `VERBES` des familles chargées ; chaque verbe a une ligne d'`AIDE` ; aucun verbe n'est déclaré deux fois.
- **Entrée privée déclarée** (lot 3/4) : les verbes `prive: True` refusent le texte positionnel avec le même message qu'aujourd'hui.
- **Équivalence des sorties** (chaque lot) : pour les verbes déplacés, la sortie (code de retour, texte, fichiers écrits) est
  comparée avant/après sur une installation jetable ; les tests existants qui le font déjà (`affichage`, `alire`, `decisions`,
  `espaces`…) restent la preuve principale, un test d'équivalence est ajouté seulement pour un verbe qu'aucun test ne couvre.
- **Taille** (`tests/taille-fichiers.py`, lot 1) : aucun fichier de `bin/` > 1 500 lignes, cliquet pour `bin/berger`.
- **Écartement et nom** (chaque rang) : un module volontairement cassé apparaît dans `berger etat` avec sa cause.
- **Neutralité et transport** : `verifier-depot`, `tests/argv-*.py`, `tests/marques-produit.py` inchangés et verts.

## Lots

Une demande de fusion par lot, dans l'ordre. Chaque lot peut s'installer seul et laisse `main` sain.

### Lot 1 — API du noyau + vues branchées dessus (aucun go spécial)

- **Déplacé** : constantes de chemins et de configuration (haut de `bin/berger`, lignes 1–118), « fichiers d'un agent » (119–368),
  transport et appels Herdr (`herdr`, `herdr_api`, `socket_herdr`, `statut_herdr`, `herdr_ids`), `entree_privee`, affichage et mise en page
  (3498–3689, ≈ 190 lignes), les lecteurs en lecture seule des vues (À lire, Décisions, Checklists, Sources, Synthèse, partie donnée
  de Tokens) vers `noyau/lectures.py`. Le code de rendu reste dans les vues.
- **Fichiers** : `bin/noyau/{__init__,api,config,agents,herdr,transport,affichage,lectures}.py` ; `charger_vues()` donne l'API filtrée
  au lieu de la copie des globales ; `globals().update(vue_*)` supprimé (registre `VUES`).
- **Tests qui le prouvent** : contrat d'API, frontière à l'exécution, pas de lecture arrière, taille ; toutes les suites de vues
  (`affichage`, `alire`, `decisions`, `demo-vues`, `catalogue`, `interface`, `tableau`…) inchangées.
- **Risques** : (a) une vue qui dépend d'un nom du cœur que l'analyse syntaxique rate (`globals()["x"]`, `eval`) : l'analyse l'interdit
  et la recherche est faite avant le lot ; (b) l'ordre de chargement du noyau (la configuration lue une fois, avant tout) ; (c) des
  tests qui lisent un nom de `bin/berger` : le répertoire de ces noms est établi au début du lot et gardé par un shim documenté dans
  le test de contrat ; (d) `LECTEURS_CONSO` : en attendant le lot 2, il reste rempli par le cœur et exposé par l'API.

### Lot 2 — `moteurs/`

- **Déplacé** : section « moteurs » (1487–1558), admission d'un moteur (1559–1893), les lecteurs de consommation (3963–4127), les
  réglages et options propres à chaque moteur (`CODEX_*`, `FEATURES_CODEX_STRICT`, `config_codex`, `reglages_claude`,
  `abonnements`), `args_moteur`/`_args_moteur`, `executable_moteur`, `version_moteur`, `verdict_moteur`.
- **Fichiers** : `bin/moteurs/{__init__,claude,codex}.py` ; `MOTEURS` dérivé.
- **Tests qui le prouvent** : `contrat-moteur.py` et `.sh`, `contrat-session.py`, `contrat-socket.py`, `codex-ouverture.py`,
  `mcp-trous.py`, `abonnement.py`, `tokens`, plus l'écartement d'un moteur cassé. Les suites qui exigent un vrai moteur absent sont
  « non mesurées », dites telles.
- **Risques** : ce lot touche le **lancement** des agents : une erreur se voit au premier agent relancé. Atténuation : install hors
  production d'abord (règle générale), `verdict_moteur` rejoué sur les deux moteurs avant/après. Ne change aucun droit ni
  aucune règle du mur (le calcul de ce que l'agent a le droit de voir reste dans le noyau, lot 4).

### Lot 3 — commandes sans risque

- **Déplacé** : *affichage* (etat, vue, vues, panneau, statusline, titres, interface, web), *alire* (lire, livrable), *tokens*,
  *reveils* (réveils, tâches, planificateur, superviser, relances : 3077–3497), *espaces* (espaces Herdr, espace voulu, espace auto :
  4819–5259), *memoire* (noter, memoire, validations). Le registre de commandes, `AIDE`/`DROITS`, et le test de couverture arrivent
  avec ce lot ; les verbes des familles du lot 4 restent dans `bin/berger` pour l'instant, **enregistrés dans le même registre** par un
  petit module de transition (un seul chemin d'aiguillage, pas deux).
- **Fichiers** : `bin/commandes/{affichage,alire,tokens,reveils,espaces,memoire}.py`, `bin/commandes/__init__.py` (découverte).
- **Tests qui le prouvent** : couverture des verbes, entrée privée déclarée, plus `affichage`, `alire`, `alire-se-vide`, `decisions`,
  `echanges`, `espaces`, `espace-agent`, `espace-auto`, `auto-test-nuit`, `abonnement`, `livrables`, `memoire-equipe` et le reste de la suite.
- **Risques** : le planificateur (réveils) lance `berger` en sous-processus : les chemins de relance doivent rester les mêmes ;
  les réveils sont en service la nuit, donc install en journée avec retour arrière prêt. Les verbes rangés dans « sans risque » qui
  appelleraient en réalité le courtier sont laissés au lot 4 (la liste est vérifiée verbe par verbe à l'ouverture du lot).

### Lot 4 — ce qui touche le courtier, le mur ou les secrets (cas 1, **go inscrit du propriétaire sur cette spec avant le code**)

- **Déplacé** : *missions* (2225–2549), *messages* (`message-deposer` (verbe `ecrire` du courtier), `message-remettre`, `parler`, `demander`),
  *besoins* (2152–2224 et annonce d'outil 498–740), *equipes* (2550–3076), *courtier* (anti-boucle 369–417, `mcp-enveloppe`, serveurs MCP
  741–1212), *depot* (audit des secrets 5260–5374, installer 5375–5692, sauvegarde, coffre), génération des réglages et du mur
  (418–497), création/modification d'un agent sur proposition (1213–1486), puis ce qui reste de `main()` (fin : `bin/berger` ≤ 250 lignes).
- **Fichiers** : `bin/commandes/{missions,messages,besoins,equipes,courtier,depot,agents}.py` ; le calcul du mur et des droits reste
  dans `noyau/` (privé, hors API des vues) pour qu'aucun module de commande ne puisse le réécrire.
- **Tests qui le prouvent** : toute la suite, en insistant sur `regle-go`, `anti-boucle`, `besoin`, `ecrire`, `ecrire-aussi`,
  `equipe*`, `hierarchie-equipe`, `installation`, `installer-master`, `mcp*`, `coffre-sauvegarde`, `argv-*`, `consignes-canari`,
  `moins-validations`, `validation-fait`, `communaute*`, `sondes-gardes` (tests/tout.sh) ; `verifier-depot` ; audit des secrets.
- **Risques** : c'est le cœur de la sécurité. (a) Un garde-fou perdu en route : le test de couverture et les tests de refus (`regle-go`,
  `anti-boucle`, sondes des gardes) doivent être identiques avant/après, et la demande liste ligne à ligne chaque garde déplacé ;
  (b) l'aiguillage des verbes privés : `DROITS["prive"]` remplace le tuple de `main()`, le test d'entrée privée prouve l'égalité ;
  (c) l'installation d'un nouveau `bin/berger` se fait par `installer` (avance rapide, vérifications, retour arrière automatique) et
  en journée ; (d) la production n'est pas touchée par ce chantier : son changement reste un go du propriétaire, à chaque fois.
  **Ce lot se découpe en demandes courtes** si la relecture l'exige (missions, puis messages/besoins, puis équipes, puis dépôt).

## Livrables du chantier

La spec (ce fichier), puis pour chaque lot : la demande de fusion, la liste des fonctions déplacées (fichier source → fichier cible), les
tests joués avec leur résultat, la ligne de manuel mise à jour, et la taille de `bin/berger` après le lot (6 089 → … → ≤ 250 lignes).

## Points ouverts (à trancher à la lecture)

- Faut-il rendre le noyau écartable par module (par exemple `herdr.py` absent = les verbes qui l'emploient disent « Herdr absent »),
  plutôt que « noyau tout ou rien » ? Proposition : non pour l'instant, à rouvrir si un second environnement le demande.
- La limite de 1 500 lignes est-elle la bonne (taille du courtier) ou préfère-t-on 800 ? Proposition : 1 500, plus 500 pour un fichier de commandes
  nouveau, sans exception acceptée.
