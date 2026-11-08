# Accélérer la chaîne de fusion — spec courte (04/11/2026)

Règle de go : **cas 1** (courtier, règles de validation). Spec seule : aucun code avant le go inscrit du propriétaire sur CE
fichier. À coder **après** le lot 1 de l'interface web v2. Demande du propriétaire du 04/11 (~21h30, « accélérer »).
Sécurité inchangée : aucune fusion sans la validation du propriétaire, portes vertes avant `main`, SHA figé, jamais de force.

## Constat du 04/11 (mesuré sur `main`, b1d5f3e)

- **~45 min par lot de 3 demandes.** Chaque demande joue la suite complète (`tests/suites.sh`, ~10 min en parallèle 3),
  une fois à `demander-fusion` et encore une fois à `fusionner` si `main` a avancé (`equipe_chef.py`, `fusionner` →
  `mise_a_jour` puis `jouer_portes`, les 4 portes).
- **Une ligne de ROADMAP rejoue toute la suite** : la porte courte « documentation seule » existe (spec 2026-10-28,
  `_portes.choisir`, `tests/portes-doc.sh` : syntaxe, marques, `vitrine.py` avec `verifier-depot` en dépôt jetable), mais
  `[equipes.berger]` ne déclare pas `doc` : sans elle, la porte complète est jouée (comportement prévu).
- **Blocage croisé** (30 min, 20h) : le tour de tests passe par des messages « LIBRE » entre agents. La session du
  développeur s'est arrêtée pendant sa porte ; chacun attendait l'autre. `suites.sh` sait déjà attendre le verrou
  (`BERGER_SUITES_ATTENTE`, 600 s), mais cette attente compte dans le délai de la porte (`delai = 2100`) : on ne peut pas
  s'y fier, d'où les messages.
- **Chaque fusion périme les autres demandes** :
  - `demander-fusion` refuse une branche qui n'est pas à jour de `main` (`_portes.controler_demande`, « ta branche n'est
    pas à jour ») ;
  - `fusionner` refuse la mise à jour automatique dès qu'un fichier est commun (`communs()`), même sans conflit.
  Les fichiers communs du jour : `CHANGELOG.md` (n° 144, 146), `docs/manuel.md` et son empreinte figée dans
  `tests/vitrine.py` (ligne 50, un sha256 qui change à chaque ligne du manuel).

## Comportement — quatre lots, une demande chacun

### Lot 0 — sans code (le propriétaire, `config.toml`)

`[equipes.berger] doc = "bash tests/portes-doc.sh"`. Le courtier choisit déjà la porte courte d'après le diff, côté
développeur et côté chef (`_portes.choisir`), y compris sur le commit de mise à jour à la fusion. Une demande de
documentation seule passe en ~1 min au lieu de ~10. C'est le gain immédiat de la piste 1.

### Lot A — le tour de tests tenu par Berger (piste 2)

1. **Le courtier prend le verrou des suites AVANT de lancer les portes**, en attente bloquante, et le garde jusqu'à la
   fin de la dernière porte. Le délai de la porte ne démarre qu'une fois le verrou obtenu. Les suites lancées par la
   porte héritent du verrou tenu (`BERGER_SUITES_VERROU_TENU`, existant).
2. **Ordre d'arrivée** : un ticket numéroté par demande d'attente, dans l'état du courtier. Le plus petit ticket vivant
   passe. Un ticket dont le processus est mort est retiré.
3. **Attente bornée** (2 h). Au-delà, refus nommé « file des tests : attente dépassée », et aucun verdict n'est inscrit.
4. **Visible** :
   - `equipe liste` et `berger-chef demandes` montrent « tests : en file (2e, derrière <sujet>) » ou « tests : en cours
     (<sujet>, depuis HH:MM) » ;
   - l'Accueil montre un jaune si la file dépasse 30 min.
5. **Les consignes des développeurs et du chef perdent la règle « demande le tour »** (texte généré par Berger) :
   l'agent lance sa porte ou `demander-fusion`, et Berger le fait attendre.
6. Les portes jouées par un agent hors du courtier (`bash tests/suites.sh` à la main) gardent le verrou actuel. Elles
   passent dans la file comme tout le monde : même fichier de verrou, même ordre.

### Lot B — une demande n'est plus périmée par la fusion d'une autre (piste 3)

1. **`demander-fusion` accepte une branche en retard sur `main`**, à une condition : ni conflit, ni fichier commun avec ce
   que `main` a gagné depuis la base de la branche. Le message dit « main a avancé : mise à jour automatique à la fusion ».
   Avec un conflit ou un fichier commun, le refus nommé reste celui d'aujourd'hui.
2. **À la validation, rien ne change du côté de la sécurité** :
   - `fusionner` fait déjà la mise à jour automatique (fusion sans fichier commun, auteur « berger (courtier) ») ;
   - il rejoue les portes sur le commit de mise à jour, choisies d'après le diff (porte courte possible), et pousse en
     avance rapide ;
   - le SHA validé reste celui de la branche présentée (spec sha-figé) : une branche qui a bougé après l'aperçu est
     refusée, et il faut une nouvelle validation.
3. **Portes rouges après la mise à jour** : rien n'est poussé. La demande passe « à corriger » avec le motif, et le
   développeur reçoit un message, comme aujourd'hui.
4. **Hors périmètre** : fusionner deux demandes en un seul passage (train de fusion). Ce sera à voir si le lot B ne
   suffit pas.

### Lot C — journal des changements en fragments (piste 4)

La spec `docs/plans/2026-11-04-changelog-fragments-spec.md` (même branche), reprise telle quelle :
- `changelog.d/<sujet>.md` par branche ;
- regroupement à la finition de version ;
- `etiqueter` refuse s'il reste un fragment ;
- `changelog.d/*.md` compte comme documentation pour la porte courte.

### Lot D — l'empreinte du manuel n'est plus un fichier commun (à trancher)

`tests/vitrine.py` fige le sha256 du corps du manuel. Deux branches qui touchent le manuel ont donc toujours un fichier
commun, même sur des sections différentes. Deux options :
- (a) **retirer l'empreinte figée**, puisque la relecture et la doc obligatoire (`pret.sh`) couvrent le manuel ;
- (b) **une empreinte par section** (`tests/attendus/manuel/<section>.sha256`), pour que deux branches sur des sections
  différentes n'aient plus de fichier commun.

**Recommandation : (b)**, qui garde l'intention du contrôle.

## Refus et invariants (testés)

- Une fusion sans validation du propriétaire est impossible : `fusion_par` reste inchangé.
- Aucune porte rouge n'entre dans `main` : le SHA est figé et le push se fait sans force.
- La porte courte reste décidée par le courtier, d'après le diff, et jamais par l'agent.
- Dans la file, deux suites ne tournent jamais en même temps : le verrou reste unique et l'ordre est respecté.
- Un ticket mort ne bloque pas la file.
- Une demande avec un fichier commun ou un conflit est refusée avec un motif nommé, comme aujourd'hui.

## Tests

- **Lot A** (`tests/file-tests.py`, sans modèle) :
  - 3 demandes simultanées passent dans l'ordre d'arrivée, et aucune paire ne se chevauche ;
  - le délai d'une porte n'inclut pas l'attente ;
  - un ticket orphelin est retiré ;
  - au-delà de l'attente maximale, refus sans verdict ;
  - les consignes générées ne contiennent plus « demande le tour ».
- **Lot B** (`tests/processus-dev.py`) :
  - une branche en retard sans fichier commun est acceptée, puis fusionnée par la mise à jour automatique ;
  - une branche avec un fichier commun est refusée à `demander-fusion` ;
  - après la mise à jour, une branche de documentation seule rejoue la porte courte ;
  - des portes rouges après la mise à jour : rien n'est poussé.
- **Lots C et D** : voir la spec des fragments. Pour D, deux branches sur deux sections du manuel n'ont aucun fichier
  commun.

## Gain attendu

- Une demande de documentation : ~1 min au lieu de ~10.
- Plus aucun message « LIBRE », donc plus de blocage croisé.
- Une demande validée ne repart plus chez le développeur parce qu'une autre a été fusionnée avant elle, sauf en cas de
  fichier commun réel.
- Ordre de livraison proposé : 0 (tout de suite), C, B, A, D.

Doc : manuel (circuit, portes), `docs/plans/README.md`, CHANGELOG (en fragment, une fois le lot C livré).
