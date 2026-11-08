# Portes tests sérialisées : une seule porte `tests` à la fois sur la machine (spec)

Règle de go : **cas 1 pour l'option A** (courtier : une file dans `copie.py`/`_portes.py`, règles de validation) : elle attend le go du
propriétaire, **inscrit** sur CE fichier, avant la première ligne de code. L'option B ne touche que `tests/suites.sh` (outillage de tests,
coordinateur) ; elle est proposée et prouvée ici, **sans toucher au courtier**. Origine : relecture Codex de la n° 76 (RAM de 15 Go).

## Constat (mesuré sur `main`, 3017478 + branche `berger/tests-paralleles`)

- **Chaque porte a son `/tmp` privé.** `copie.py:62` lance la commande par `_base.bac_a_sable(args, copie, masques, reseau)` ; sans
  `tmp`, `_commandes.py:43` monte `--tmpfs /tmp`, après `--ro-bind / /`, `--unshare-pid`, `--unshare-net`, `--new-session`. Un fichier
  de verrou dans `/tmp` est donc **un fichier différent pour chaque porte** : le `flock` de la n° 76 ne sérialise rien entre deux
  développeurs (il ne protège que deux `suites.sh` dans la même porte). Il avait déjà échoué sur `/run/user/1000` (lecture seule dans
  la porte : « verrou illisible, passe NON JOUÉE », 29/10).
- **Le seul passage commun** à toutes les portes `tests` (développeurs et chef) est le courtier : `_portes.jouer()` (`:43`), qui
  appelle `executer` (`copie.py:55`). Les processus d'une porte ne voient pas ceux d'une autre (`--unshare-pid`).
- **Mesure du 29/10** (porte `tests`, machine libre, 113 suites) : n = 1 : 596 s, −183 Mo de `MemAvailable` ; n = 4 : 222 s, −406 Mo ;
  plus gros pic d'une suite 1,06 Go. Le risque est donc moins une suite qu'**un cumul de portes** (trois portes ≈ trois passes).

## Option B : un chemin de verrou visible de tous les bacs à sable — EXISTE (vérifié)

Un `flock` verrouille l'**inode**, pas le chemin : il vaut d'un bac à sable à l'autre, et se prend sur un descripteur **ouvert en lecture
seule**, dans un fichier d'un montage en lecture seule. Expérience (29/10) : un processus du bac de l'agent tient `flock` sur
`~/projets/berger.git/description` (ouvert `rb`) ; la porte `verify` d'une copie, lancée par le courtier pendant ce temps
(script temporaire, retiré), reçoit `EAGAIN` : **l'exclusion est vue d'une porte à l'autre**. Le fichier est le dépôt « forge locale » de
l'équipe (`remote.origin.url`), même inode pour toutes les copies du projet, déjà visible (`--ro-bind / /`) et jamais masqué.

## Comportement (option B, `tests/suites.sh` seul)

1. Le verrou global porte sur `<forge nue>/description`, ouvert en lecture seule. La forge se trouve en **remontant d'origine en origine**
   (`remote.origin.url`, chemin ou `file://`, puis les alternates d'un clone `--shared`) jusqu'au dépôt `core.bare`, six maillons au plus : le
   rejeu du chef (`equipe_chef.py:326`, clone `--shared` de SON dépôt de travail) arrive à la même forge que le développeur, sans toucher au courtier. **Pourquoi ce fichier** : il est créé une fois par `git init --bare` et jamais réécrit ensuite. Mesuré (29/10) :
   `push`, `fetch`, `gc`, `repack`, `config` et `symbolic-ref` laissent son inode intact, alors que `HEAD` et `config` sont réécrits par
   renommage (nouvel inode : un verrou posé dessus se romprait en silence). Deux copies du projet prennent le même chemin, donc le même
   inode (test). `BERGER_SUITES_VERROU=<fichier existant>` le remplace (tests).
2. Le suivant **attend son tour** (message, `BERGER_SUITES_ATTENTE`, 600 s par défaut) puis s'arrête **sans aucun verdict vert**
   (« passe NON JOUÉE »). L'attente compte dans le délai de la porte (`delai`, 1500 s) : deux portes ≈ 2 × 10 min passent, trois non.
3. Le lanceur qui tient le verrou le dit à ses descendants (déjà fait : `BERGER_SUITES_VERROU_TENU`) ; son descripteur n'est transmis
   à aucune suite (corrigé : ni `_jouer`, ni les témoins, ni un descendant d'une autre session ne le gardent après sa mort).

## Option A : file d'attente dans le courtier (go requis)

Le courtier tient un verrou unique pour les portes `tests` de tous les développeurs et du chef, **avant** de démarrer le délai de la
porte (l'attente ne consomme pas `delai`), avec un message « porte tests en attente derrière <agent> » et un délai d'attente (≈ 30 min)
au bout duquel la porte est refusée **sans verdict**. Elle sérialise aussi tout autre usage lourd et ordonne les demandes ; elle
coûte du code dans `_portes.py`/`copie.py` et un test d'intégration. À ne faire que si le propriétaire veut cette équité ou
d'autres portes lourdes.

## Refus

Forge locale sans fichier `description` (introuvable), fichier illisible ou non verrouillable, flock absent, délai d'attente dépassé : passe
**NON JOUÉE**, code de retour non nul, **jamais** de vert et **jamais** de repli sur `/tmp`, qui ne sérialiserait rien dans une porte. Le
seul verrou `/tmp` (`/tmp/berger-suites-<uid>.lock`) est celui d'un dépôt **sans aucune origine locale** (https, ssh, sans remote) ; une origine locale (chemin ou `file://`) qui ne mène pas à une description verrouillable, une boucle ou plus de six maillons : NON JOUÉE : il n'est pas
dans une porte de Berger, et la passe le dit à l'écran.

## Tests

- `tests/parallele-memoire.py` : deux descripteurs en lecture seule sur le même fichier s'excluent (shell et Python) ; l'attente dit son
  message ; repli `/tmp` dit ; avec `bwrap` disponible, deux bacs aux `/tmp` différents s'excluent via le fichier partagé (sinon
  `NON JOUÉ`) ; le descripteur 9 n'est hérité d'aucun descendant (même après `SIGKILL` du lanceur).
- Option A : test du courtier (deux portes simultanées, la seconde en attente puis passée, délai d'attente refusé) — après le go.

## Décision attendue

`Décision attendue : option B seule (recommandée : prouvée, sans code du courtier, livrée dans la demande tests-paralleles) ou A en plus`
