# Verbe `prod` : mettre une version en production, sauvegarde vérifiée d'abord — spec

Spec courte, 15/10/2026 (mission de master, sujet `verbe-prod`). **Go du propriétaire du 15/10** sur la spec du coordinateur
(« mise en prod de l'outil du projet », À lire du 14/10) : « écris le script ». Rien n'est propre à un moteur ni à un
projet : le script ne contient ni adresse ni nom ; tout vient d'un fichier de réglages posé SUR le serveur.

**Correctif du 16/10** (relecture de l'agent d'infrastructure sur l'état réel du serveur de production, même go, même périmètre) : migrations SQL
génériques (l'image de prod n'a ni l'outil de migration du projet ni psql), prérequis contrôlés tôt (gpg absent du
serveur), commandes `avant` / `apres` et seuil de disque, plus de HEAD détachée, connexion ssh coupée testée.
Cause racine : la première version supposait que l'appli joue elle-même ses migrations (`migrer`, une commande de l'image)
et que le serveur a tout ce qu'il faut ; elle n'avait pas été confrontée à un serveur réel.

## Constat

Mettre une version en production se fait à la main sur la machine du projet. Rien ne garantit qu'une sauvegarde de la
base existe et se relit avant, ni que la version servie après est la bonne, ni qu'on revient en arrière si elle ne l'est
pas. Le verbe tourne SUR la machine de production, appelé par ssh à **commande forcée** ; il y est installé par le
propriétaire lui-même (notice : `docs/verbe-prod-installation.md`). Ce dépôt n'y accède pas.

## Le script : `bin/serveur/berger-prod`

Python 3.11 ou plus (`tomllib`), sans dépendance. Rangé sous
`bin/` : un nouveau dossier racine aurait demandé de l'ajouter à la liste blanche du dépôt ET à `PRODUIT` (`bin/berger`,
protections des agents), soit le cœur de l'installation ; `bin/` est déjà protégé.

```
berger-prod [--config <fichier>] prod [--essai] vX.Y.Z | compte-rendu | aide       # appel direct
restrict,command="sudo -n /usr/local/sbin/berger-prod --config /etc/berger-prod.toml --ssh \"$SSH_ORIGINAL_COMMAND\"" <clé>
```
Réglages : `--config`, sinon `$BERGER_PROD_CONFIG`, sinon `/etc/berger-prod.toml`. Modèle commenté :
`bin/serveur/berger-prod.exemple.toml`. Par ssh, la commande reçue (`--ssh`, ou `SSH_ORIGINAL_COMMAND` seule) ne contient
que lettres, chiffres, espace, `. _ -` (64 au plus), sinon refus. Verbes : `prod`, `prod --essai` (étapes 1 à 3 puis arrêt :
rien ne change), `compte-rendu` (le dernier, lecture), `aide`. Le script tourne en root (sudo limité à cette commande) ;
git tourne sous `git_utilisateur` (le compte qui possède la copie et sa clé vers origin) par `runuser`. La coupure de la
connexion ssh (le courtier coupe à 180 s) est ignorée : le travail va au bout, `compte-rendu` le relit.

## Qui le lance

Le **chef de projet** seul, par le courtier : un outil de type `ssh` existant (aucun code du courtier changé), déclaré dans
`config.toml` avec `compte-rendu` en lecture et `essai` / `prod` en **actions** : chaque lancement attend la validation du
propriétaire. L'outil est ajouté à la ligne `outils =` de l'`agent.conf` du chef — le plus simple : `[equipes.<p>]` n'a pas
d'option « outils du chef », et l'ajouter toucherait aux droits (cœur). Les développeurs ne l'ont jamais (leurs outils sont
calculés : `<projet>-dev` + `outils_developpeur`).

## Étapes — chacune avec son refus

0. **Prérequis, réglages, verrou, disque.** Python ≥ 3.11, `git`, `gpg` (réglage `gpg`), `docker compose` (réglage `docker`) :
   l'un absent → refus qui le nomme, **avant tout geste** — pour `aide` comme pour `prod` et `--essai`. Réglage retiré
   (`migrer`, `migrations_en_attente`), `docker system prune` dans `avant` / `apres` / `controles_sante`, `disque_seuil` hors 1–100, nom de
   table ou de colonne SQL douteux → refus. Verrou (`<sauvegardes>/.berger-prod.verrou`) : une mise en production à la
   fois. Disque de `depot`, `sauvegardes` et `/var/lib/docker` occupé à `disque_seuil` % ou plus (défaut 92, compté comme
   `df`) → refus.
1. **Version** : `<version>` doit être `vX.Y.Z` (SemVer, chiffres seuls) ; `git fetch --tags origin <principale>` ; l'étiquette
   existe, son commit est contenu dans `origin/<principale>` (`git merge-base --is-ancestor`). Copie du serveur modifiée
   (`git status --porcelain` non vide) → refus. Sinon refus, **rien n'est fait**.
2. **Sauvegarde complète de la base, CHIFFRÉE, VÉRIFIÉE sans clé privée** (relecture de master, 15/10 : une clé privée
   sur le serveur, à côté des sauvegardes, ne protégerait plus rien). `pg_dump -Fc` (dans le conteneur de base) est lu par
   le script et envoyé, en flux, à la fois à `pg_restore --list` (dans le conteneur : le CLAIR est relu au passage) et à
   `gpg --encrypt` vers le(s) destinataire(s) : le clair ne touche jamais le disque. Fichier
   `<sauvegardes>/base-<AAAAMMJJ-HHMMSS>-avant-<version>.dump.gpg`, 600, dossier 700, écrit en `.part` puis renommé, jamais
   écrasé. **Vérifiée** : flux non vide, `pg_restore --list` réussi et non vide, gpg réussi, fichier non vide, et
   `gpg --list-only --list-packets` montre un paquet chiffré pour une clé (ou sous-clé) d'un destinataire réglé.
   **Pas de sauvegarde vérifiée = refus**, rien d'autre n'est fait (le `.part` raté est retiré : notre fichier en cours,
   chiffré). Le serveur n'a que la **clé publique** (`gpg_home`) ; la paire est créée par le propriétaire hors du serveur,
   la clé privée reste chez lui (coffre) et n'est apportée que pour restaurer.
3. **Avant** : version servie (URL de santé, champ `sante_champ`, défaut `version`) et commit en place (`git rev-parse HEAD`).
   **Migrations en attente** (si `migrations_dossier`) : les fichiers de ce dossier dans la version demandée (`git ls-tree`),
   qui répondent à `migrations_motif` (défaut : tout `*.sql`), triés par nom, moins ceux que liste la table de suivi
   (`SELECT <migrations_colonne> FROM <migrations_table>`, défauts `name` et `schema_migrations`, par `psql` dans le
   conteneur de base). Table illisible → refus ; table **vide** alors que des fichiers existent → refus (la base n'a jamais
   été inscrite : tout serait rejoué). Commandes **`avant`** (contrôles du projet, une chaîne ou une liste) : un échec →
   refus. `--essai` s'arrête ici : statut `essai`, `migrations_en_attente` dans le compte rendu, rien n'a changé.
4. **Mise en place** : `git checkout -B <principale> <étiquette>` (la copie reste sur sa branche, jamais de HEAD
   détachée) ; `construire` (défaut `docker compose -f <compose> build`) ; **migrations** relues puis jouées une par une :
   le fichier suivi de `INSERT INTO <table> (<colonne>[, <colonne_par>]) VALUES ('<fichier>'[, 'berger-prod <version>'])`,
   envoyés ensemble à `psql -v ON_ERROR_STOP=1 --single-transaction -f -` (réglage `psql`, défaut :
   `docker compose exec -T <base>` avec `POSTGRES_USER` / `POSTGRES_DB` du conteneur) — la migration et son inscription
   passent ensemble ou pas du tout ; la première en erreur arrête la suite. **Un fichier qui ouvre lui-même sa
   transaction** (une ligne `BEGIN;`, sans tenir compte de la casse — la règle de l'outil de migration du projet) est joué
   tel quel SANS `--single-transaction` (son `COMMIT` fermerait la nôtre), puis inscrit par un second `psql -c` s'il a
   réussi (une inscription en échec est dite : « jouée, NON inscrite »). `migrations_colonne_par` (facultatif, ex.
   `applied_by`) reçoit `berger-prod <version>` ; absent = la colonne n'est pas remplie (table qui ne l'a pas). Le nom du
   fichier entre dans l'INSERT entre apostrophes : un nom retenu hors de `[A-Za-z0-9._-]` (apostrophe, espace) est
   **refusé à l'étape 3**, jamais ignoré en silence (le motif par défaut est `\.sql$`, le contrôle vient après). Puis `demarrer`
   (défaut : `docker compose -f <compose>` suivi de son verbe de démarrage détaché).
5. **Santé** : l'URL de santé doit servir `<version>` (avec ou sans le « v ») avant `sante_delai` secondes (défaut 120),
   essai toutes les `sante_intervalle` secondes (défaut 5). Puis les **`controles_sante`** (une chaîne ou une liste,
   facultatif) : chacun rejoué toutes les `sante_intervalle` secondes jusqu'à réussir, dans `sante_delai` compté depuis le
   premier ; un qui n'y arrive pas = échec → retour arrière (ex. un service sans image à lui, qui réutilise celle d'un
   autre : il tourne sur l'image qui vient d'être construite, sa santé docker est `healthy`). Choisi plutôt que de
   mettre le contrôle dans `demarrer` : une santé docker met du temps à passer au vert, il faut la rejouer jusqu'au délai,
   et le motif dit quel contrôle a échoué. Puis les commandes **`apres`** (ménage : `docker image prune -f`,
   `docker builder prune -f` ; jamais `system prune`) : un échec est inscrit (`apres_en_echec`, motif), la version reste.
6. **Retour arrière automatique** si (4) ou (5) échoue : `git checkout -B <principale> <commit d'avant>`, `construire`,
   `demarrer`, puis contrôle que la version d'avant est servie. **La base n'est jamais restaurée automatiquement** : si une
   migration a été tentée (jouée, ou en erreur), le compte rendu donne la
   **commande exacte de restauration** (`gpg --decrypt` avec la clé privée apportée par le propriétaire → `pg_restore --clean --if-exists`) — c'est une suppression de données, le
   propriétaire la lance lui-même.
7. **Compte rendu JSON** (sortie standard, et copie dans `<sauvegardes>/comptes-rendus/`) : `statut` (`ok`, `essai`, `refus`,
   `retour-arriere`, `retour-arriere-echoue`), `etape`, `motif`, `version_demandee`, `version_avant`, `version_apres`,
   `commit_avant`, `commit_apres`, `migrations_en_attente`, `migrations_jouees`, `apres_en_echec`, `sauvegarde` (chemin), `retour_arriere` (la commande qui remet le
   code d'avant), `restauration` (commande de la base, si migrations), `debut`, `fin`, `journal` (les commandes jouées et
   leur code). Code de sortie : 0 ok ou essai, 1 refus, 2 retour arrière fait, 3 retour arrière en échec (intervention
   humaine). **Journal du serveur** : une ligne par passage dans `<sauvegardes>/berger-prod.log` (dès que les réglages
   sont lus).

## Refus (résumé)

Prérequis absent (python 3.11, git, gpg, docker compose), réglage retiré ou douteux, `system prune`, disque au-dessus du
seuil, verbe inconnu, commande ssh avec un caractère spécial, version mal formée, étiquette absente ou hors `origin/<principale>`,
copie modifiée, réglage manquant, table de suivi illisible ou vide, commande `avant` en échec, sauvegarde vide / illisible par `pg_restore` / pas chiffrée pour le destinataire réglé, mise en production déjà en
cours. Rien ne supprime de sauvegarde (la purge des anciennes reste une décision du propriétaire).

## Tests — `tests/verbe-prod.py` (joué par `tests/suites.sh`)

Dépôt git jetable (vrai git) avec un « origin » (étiquettes sur `main` et hors `main`), docker et PostgreSQL simulés par
les commandes de la configuration, santé lue par une URL `file://` qu'écrit le faux démarrage, faux `gpg` sans clé privée (le bac à sable
des agents interdit l'agent gpg) ; plus une passe **gpg réel** quand une clé jetable peut être créée (serveur avec la seule clé publique ; le propriétaire
déchiffre à l'identique avec la sienne ; destinataire absent → refus) (sinon « NON JOUÉ »,
jamais compté ok). Faux `psql` (table de suivi dans un fichier, tout ou rien) et faux `docker` (`compose version`).
Contrôles : prérequis absents (gpg, docker compose) → `aide` et `--essai` refusent ; disque au-dessus du seuil, seuil
invalide, `system prune`, ancien réglage, nom de table douteux → refus sans sauvegarde ; table de suivi illisible ou vide →
refus, code inchangé ; essai qui liste les migrations en attente (un fichier non `.sql` ignoré) ; commande `avant` en échec
→ refus ; migration factice jouée et inscrite (seul le nom sans `migrations_colonne_par`) ; migration avec son propre
`BEGIN;` / `COMMIT;` jouée sans `--single-transaction` puis inscrite, la suivante dans une transaction unique, `applied_by`
rempli `berger-prod <version>` dans les deux cas ; nom de fichier avec une apostrophe → refus ; `controles_sante` qui ne passe pas dans le délai → retour arrière, rejoué
jusqu'à réussir (3e essai) → succès, `system prune` refusé ; migration en erreur → non inscrite, retour arrière du code, restauration
donnée ; `apres` jouée, son échec signalé ; branche principale (pas de HEAD détachée) après un succès et après un retour
arrière ; **connexion ssh coupée en pleine construction** (sortie fermée et SIGHUP au groupe, comme sshd) → la mise en
production va au bout, `compte-rendu` la relit ; version mal formée, étiquette absente, hors main, copie modifiée → refus sans sauvegarde ni
checkout ; sauvegarde vide, illisible, chiffrée pour un autre destinataire → refus, HEAD inchangé, aucun fichier laissé ; essai à blanc (rien ne
change) ; succès → fichier 600 chiffré sans le clair, HEAD sur l'étiquette, compte rendu complet avec la commande de retour
arrière ; construction en échec et santé qui ne sert pas la version → retour arrière, HEAD d'avant, commande de
restauration seulement si des migrations ont été jouées ; retour arrière en échec (code 3) ; verrou ; journal du serveur ;
ssh : injection refusée ; aucune adresse, domaine ni nom de projet dans le script et son exemple. Par le courtier (installation jetable, faux ssh qui
rejoue la commande forcée) : le chef obtient une demande en attente de validation (aperçu exact), un développeur est
refusé, un argument douteux refusé, `compte-rendu` lu sans validation.

## Retour arrière de cette livraison

Le script est neuf et n'est installé nulle part : retirer `bin/serveur/`, le test et les docs. Sur un serveur : section 6
de la notice.
