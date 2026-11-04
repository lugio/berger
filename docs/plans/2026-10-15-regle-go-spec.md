# Règle de go : un go se lit, il ne se devine pas — spec

Spec courte, 15/10/2026 (mission de master, sujet `regle-go`). **Touche une règle de validation (cœur de l'installation) :
aucun code avant le go explicite du propriétaire.** **Multi-moteur** : tout passe par `berger-outil`, `bin/berger` et les
consignes générées (`AGENTS.md`, `CLAUDE.md` → `@AGENTS.md`) ; chaque test est joué avec `moteur = claude` puis `moteur = codex`.

## Constat (15/10, transmis par l'agent d'infrastructure à la demande du propriétaire)

1. **Une réponse prise pour un go.** le chef de projet d'un projet métier a lancé du code sur un sujet de la règle de go (mots de passe, cas 1) :
   le propriétaire avait répondu à ses questions, sans dire « go ». Rien, ni dans les règles ni dans Berger, ne distingue une
   réponse d'un go : `commun/REGLES.md` › « Qui valide quoi » dit « un go se demande par un verbe d'écriture (validation) »,
   mais aucun verbe n'existe pour le go d'une spec, et `equipe ouvrir` (`bin/berger`, `equipe_ouvrir`) ne demande rien.
2. **« Ça n'existe pas » sans avoir cherché au bon endroit.** le chef de projet d'un projet métier a dit que le lecteur de captcha n'existait pas ;
   il était dans la mémoire de l'équipe et dans son skill. Il n'avait cherché que dans le code. Fait lu dans le code : la
   mémoire d'équipe n'est injectée dans les règles que des **développeurs** (`memoire_equipe` → `developpeur(a)`), pas du
   chef de projet (à confirmer côté chef de projet : son dossier m'est fermé).
3. **Rappel sans fin d'une demande renvoyée exprès.** `relancer_attentes` (`bin/berger`) relance toutes les 15 min
   (`RELANCE_MIN`) tout développeur dont la demande est « renvoyée » et qui est au repos ; il ne regarde ni sa checklist ni
   l'intention du chef. Une spec renvoyée « à fusionner plus tard avec le code » relance donc son développeur sans fin,
   même après « Terminé ».

## (a) La règle écrite : ce qu'est un go

Ajout à `commun/REGLES.md` › « Règle de go », repris en une ligne dans `commun/modeles/equipe-processus.md` (étape 0) et
dans les modèles chef de projet et coordinateur :

> **Un go est un mot explicite du propriétaire** — « go », « valide », « lance » — **sur une spec écrite et nommée**
> (chemin du fichier). **Une réponse à des questions n'est pas un go**, ni un « ok », un « d'accord », un silence, un go donné
> pour une autre spec ou une version plus ancienne. Pour un sujet de la règle de go, le go oral s'**inscrit** :
> `berger valider <n°>` sur la demande de go (b). Pas de go inscrit = pas de code, même en local. Dans le doute, tu
> demandes : « ⚠ Go attendu : <spec> — <chemin> ».

**Refus** : aucun mécanisme — c'est une règle ; le contrôle est en (b). **Faux positifs** : un « ok » qui voulait dire go
coûte une commande (`berger valider <n°>`), c'est voulu. **Tests** : `tests/roles.py` (ou `processus-dev.py`) vérifie que les
règles générées d'un développeur, d'un chef et d'un coordinateur contiennent la phrase « une réponse à des questions n'est
pas un go », en claude et en codex. **Retour arrière** : retirer le paragraphe, `berger regenerer`.

## (b) Le contrôle : `equipe ouvrir` exige le go d'un sujet marqué

**Demande de go** — nouvelle écriture de l'outil `equipe` (même chemin que `equipe domaine`, `SitesPermis` → une classe `Go`) :
`berger-outil equipe go <projet> <sujet> <cas> <spec>` (coordinateur ou chef du projet ; `cas` = `1..5`, liste de la règle,
plusieurs séparés par des virgules ; `spec` = chemin dans le dépôt du projet, sur la branche principale ou la branche du
sujet). L'aperçu donne le titre de la spec, ses 15 premières lignes et son **empreinte** (sha256 du fichier). Valideur :
**le propriétaire seul**, toujours (le `valideur()` de l'outil rend `None`). Acceptée → `bin/berger` écrit
`equipes/<projet>/go/<sujet>.json` : `sujet`, `cas`, `spec`, `empreinte`, `validation` (n°), `quand`, `par`. Refusée → rien.

**Marquage** — un sujet est « règle de go » si l'une de ces trois choses est vraie :
1. un fichier `equipes/<p>/go/<sujet>.json` existe, même encore en attente (`demande` posée, go non inscrit) ;
2. le texte de la mission d'`equipe ouvrir` contient un mot de la liste `go_mots` de `[equipes.<p>]` (défaut : mot de passe,
   secret, coffre, droits, authentification, logiciel métier en écriture, production, pare-feu — seulement des mots
   des cinq cas ; « courtier » et « garde » n'y sont pas, réserve de master du 15/10 : ils relèvent de l'exception du
   cœur de l'installation (REGLES › « Demande de fusion en attente »), pas de la règle de go, et presque tous les sujets
   Berger les citent ; cas 1 complété le 16/10, remarque de l'agent d'infrastructure relayée par master : mdp, identifiants, jeton, token,
   clé d'API, credentials) ;
3. le chef le déclare : `equipe ouvrir … --go <cas>`.

**Contrôle à l'ouverture** (`equipe_ouvrir`, AVANT de rien créer, comme le moteur et le modèle) : sujet marqué et pas de go
inscrit pour ce sujet → refus « sujet de la règle de go (cas <n>) : demande le go (`berger-outil equipe go …`), puis rouvre ».
Go inscrit → la mission reçoit en tête « Go du propriétaire : validation n° <n>, spec <chemin> (empreinte <8 car.>) ».
Faux positif du point 2 (le mot « secret » dans « secrétariat », ou une lecture seule du logiciel métier) : `--hors-go "<raison>"`
(≥ 20 caractères) ouvre quand même ; la raison est **tracée** dans la demande, au journal du chef, dans Échanges, et une
alerte va au coordinateur (il voit, il peut demander le go). `--hors-go` ne lève jamais les points 1 et 3.
**Écart d'implémentation (accepté par master le 15/10)** : `--go <cas>` et `--hors-go "<raison>"` sont des LIGNES de la mission
(« Règle de go : cas <n> », « Hors go : <raison> »), parce que le courtier ne passe que 5 arguments au plus à `equipe ouvrir`.

**Trace dans la demande, comme les portes** — `demander-fusion` (développeur et finition du chef) recopie dans
`equipes/<p>/demandes/<sujet>.json` un champ `go` : `{"validation", "spec", "empreinte", "spec_dans_branche": même empreinte
ou non}` ou `{"hors_go": "<raison>"}`. Sujet marqué sans go inscrit → **refus** de la demande (une ouverture faite avant ce
contrôle est rattrapée ici). Spec modifiée dans la branche après le go (empreinte différente) → refus « la spec a changé
depuis le go n° <n> : redemande le go ». `relire` affiche ce champ ; `fusionner` le recontrôle.

**Refus, dans l'ordre** : demandeur ni chef ni coordinateur du projet ; `cas` hors 1..5 ; spec absente du dépôt, vide ou
contenant un secret (`contient_secret`) ; un go déjà inscrit avec la même empreinte (« déjà inscrit : n° <n> ») ;
`lecture_seule` ; en délégation.

**Tests** (`tests/regle-go.py`, installation jetable, faux Herdr, claude puis codex) : ouvrir un sujet dont la mission dit
« mot de passe » sans go → refus, **rien créé** (ni copie, ni agent, ni port) ; même chose avec `--hors-go "…"` → ouvert,
raison dans la demande, Échanges, alerte au coordinateur ; `--hors-go` sur un sujet ayant un fichier de go en attente →
refus ; `equipe go` par un développeur → refus ; validation proposée à un agent → jamais (valideur `None`) ; acceptée →
fichier de go, mission avec la référence ; spec modifiée puis `demander-fusion` → refus ; sujet non marqué → aucun changement
de comportement (non-régression de `tests/equipe-ouverture.py`).

**Retour arrière** : `[equipes.<p>] regle_go = false` coupe le contrôle (ouverture et demande) sans toucher aux fichiers de go ;
sinon revert du commit de fusion, puis `berger installer`. Les fichiers `equipes/<p>/go/` restent, inertes.

## (c) La consigne : chercher avant de dire « ça n'existe pas »

Ajout aux trois modèles d'équipe (développeur, chef, coordinateur) et à `commun/REGLES.md` › « Retrouver une conversation » :

> **Avant de dire qu'une chose n'existe pas** (un outil, un script, une fonction, une règle), tu cherches dans cet ordre :
> 1. la **mémoire de l'équipe** (`grep -ril "<mot>" <mémoire d'équipe>`) et ta mémoire ; 2. les **skills** du projet et les
> tiennes ; 3. le **code** et la doc du projet. Tu dis où tu as cherché : « absent de la mémoire d'équipe, des skills et du
> code (cherché : <mots>) ». Sans ces trois recherches, tu dis « je ne l'ai pas trouvé dans <où> », jamais « ça n'existe pas ».

Et le défaut lu en constat 2 : le **chef de projet** reçoit lui aussi, dans ses règles, le chemin de la mémoire de son
équipe en lecture (même bloc que le développeur, sans « tu ne l'écris jamais » s'il en est l'auteur par proposition).

**Refus** : aucun (consigne). **Faux positifs** : aucun — une recherche de plus. **Tests** : `tests/memoire-equipe.py` —
le chef de projet d'une équipe avec `memoire` a désormais le bloc dans ses règles (claude, codex) ; les trois modèles
contiennent « avant de dire qu'une chose n'existe pas ». **Retour arrière** : retirer les paragraphes, `berger regenerer`.

## (d) Les rappels : une demande mise en attente, et plus de rappel après « Terminé »

**Mise en attente par le chef** — nouveau verbe de `<projet>-chef` : `attente <sujet> "<motif>"` (≥ 10 caractères, ex.
« spec seule, à fusionner avec le code du sujet x »). État `en attente` (champs `motif_attente`, `attente_depuis`, `par`).
Une demande en attente : ni rappel au développeur, ni rappel « à relire » au chef, ni alerte de renvois, ne se fusionne pas.
Elle en sort par `reprendre <sujet>` (→ « à relire ») ou par un nouveau `demander-fusion` (→ « à relire », portes rejouées).
`demandes` et `equipe liste` l'affichent ; `fermer` reste possible (la branche poussée est gardée sur la forge).

**Plus de rappel après « Terminé »** — dans `relancer_attentes`, le rappel « renvoyée » n'est fait que si le développeur
n'a pas **fini une checklist après le renvoi** : on réutilise `mission_finie(a)`, avec la date de `renvoyee` comme début
(au lieu de la date de `MISSION.md`), et la `CHECKLIST.md` en place ne compte que si elle a été modifiée après le renvoi — la checklist « Terminé » écrite AVANT le renvoi (cas normal : il a demandé la fusion
puis fini) ne coupe donc pas le rappel d'un vrai renvoi. Développeur fini après le renvoi sans avoir redemandé la fusion → plus
de rappel à lui ; **une** alerte au chef : « <dev> a terminé sans redemander la fusion de <sujet> : mets-la en attente
(`attente`), ferme-le, ou renvoie-la ».

**Refus** : `attente` par un autre que le chef du projet ; sur une demande « fusionnée » ; motif trop court ; `reprendre`
sur une demande qui n'est pas en attente. **Faux positifs** : un développeur qui écrit « Terminé » par erreur après un renvoi
n'est plus relancé — le chef, alerté, le relance (`ecrire`). **Tests** (`tests/regle-go.py`, ou `tests/hierarchie-equipe.py`) :
renvoyée + checklist en cours → rappel (inchangé) ; renvoyée + « Terminé » écrit avant le renvoi → rappel ; renvoyée +
« Terminé » après le renvoi (en place ou rangé dans `historique/`) → aucun rappel au développeur, une seule alerte au chef sur
plusieurs passages ; `attente` → aucun rappel ni au développeur ni au chef, `fusionner` refusé ; `reprendre` → « à relire »
et rappel au chef ; `attente` par le développeur → refus. **Retour arrière** : revert du commit (l'état `en attente` d'une
demande déjà posée se remet à `renvoyée` par `reprendre`, avant le revert).

## Ordre proposé après le go

(d) puis (c) puis (a) puis (b) : (d) supprime une nuisance mesurée et ne touche aucun droit ; (b) est le plus lourd et
touche une règle de validation. Une demande de fusion par point.
