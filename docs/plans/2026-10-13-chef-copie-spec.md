# Branche de finition du chef : importée de SA copie de travail

Spec, 13/10/2026 (mission de master, correctif BLOQUANT du lot n°47). Corrige `docs/plans/2026-10-13-chef-finition-spec.md` § 1.

## Constat (cause racine)

Une tentative de poussée depuis la copie de travail du chef était refusée, faute de branche dans le dépôt cible. `branche_finition()` et `pousser()` cherchaient la branche dans `reglages["depot"]`. Or la session du chef
voit ce dépôt en LECTURE SEULE, et c'est voulu : c'est la cible des fusions. Le chef fait donc ses finitions là où il peut
écrire, dans SA copie de travail. **Cause racine** : le lot n°47 supposait la branche écrite dans le dépôt du chef ; ses
tests l'y créaient directement, sans jouer le vrai chemin (une copie de travail du chef, dépôt intouchable pour lui).

## Comportement

1. **La copie de travail du chef** = `copie_chef` de `[equipes.<projet>]` si déclarée, sinon
   `<dossier de l'agent appelant>/travail/<projet>-fin` (dossier = contexte de CET appel, jamais un attribut partagé).
   Refusée (configuration) si : chemin non absolu ; hors du dossier de l'agent appelant (ou égale à lui) ; un lien
   symbolique sur le chemin sous ce dossier (comparé après `realpath`, aucun lien suivi) ; elle est, contient ou est
   contenue dans le dépôt du chef ou la forge (`origin` du dépôt, si c'est un chemin local) ; elle est ou contient
   l'installation de Berger. (Les dossiers d'agents sont DANS l'installation, `<installation>/agents/<agent>` : une copie
   déclarée ailleurs dans l'installation — code, `equipes/`… — est refusée parce qu'elle sort du dossier du chef.) Son `.git` doit être un vrai dossier (ni lien, ni fichier `gitdir:` qui renverrait ailleurs).
2. **`pousser <branche>`** : contrôles inchangés (appelant = `chef_projet`, préfixe + nom simple, jamais la principale),
   joués AVANT l'import : un appelant non chef ou la branche principale n'importent rien.
   Puis le courtier **importe** la branche de la copie dans le dépôt, en **avance rapide seule** :
   `git -C <dépôt> fetch --no-tags --no-recurse-submodules --no-write-fetch-head <copie>/.git refs/heads/<b>:refs/heads/<b>`
   — sans `+` (une branche réécrite est refusée par git), avec `ENV_GIT` (crochets et fsmonitor désactivés dans le
   dépôt). Rien d'autre n'est lancé DANS la copie que `upload-pack` (le côté source du fetch, et du `ls-remote` qui le
   précède) : le courtier n'y lance jamais `status`, `log`… qui exécuteraient sa config (fsmonitor, crochets). Git
   efface les `GIT_CONFIG_*` pour un dépôt local : la sûreté ne repose donc pas sur `ENV_GIT` côté source, mais sur
   `upload-pack`, qui ne lit dans la config locale aucune clé qui exécute une commande (`uploadpack.packObjectsHook` n'est accepté que d'une config protégée —
   système, globale, ligne de commande —, jamais du dépôt) ; c'est testé. Puis push du dépôt vers `origin`, inchangé (sans force).
3. **`demander-fusion <branche>`** : le même import si nécessaire, puis la suite inchangée (contrôles, portes,
   inscription, fusion au propriétaire seul). Les trois verbes (`pousser`, `demander-fusion`, `fusionner`) voient la MÊME
   branche, dans le dépôt.
4. Copie absente, ou branche absente de la copie : rien à importer, on prend la branche du dépôt si elle y est (sinon refus
   « ni dans ta copie de travail ni dans le dépôt »).

## Refus

Tous ceux du lot n°47, plus : copie de travail hors règles du § 1 ; import non en avance rapide (branche réécrite dans la
copie, ou branche du dépôt en avance) → rien n'est importé ni poussé ; branche extraite dans le dépôt (git refuse de
l'écrire) → refus.

Reste connu : entre le contrôle du chemin et le fetch, l'agent pourrait remplacer un dossier de SA copie par un lien ; le
fetch ne lit alors que des objets git, importés dans une branche de son préfixe et soumis aux portes et à la relecture.

## Tests (`tests/chef-copie.py`, branché dans `tests/suites.sh`)

Le vrai chemin : le test n'écrit AUCUNE branche dans le dépôt du chef (comme en vrai, où il lui est en lecture seule) ; branche écrite dans
`<dossier du chef>/travail/<projet>-fin` → `pousser` la publie, `demander-fusion` l'inscrit, `fusionner` la fusionne ;
le reproducteur du bug (l'ancien code refusait). Avance rapide seule (copie réécrite refusée, forge et dépôt intacts) ;
`copie_chef` déclarée ; refus (rien importé ni poussé) : branche absente de la copie, branche principale (même écrite
dans la copie), appelant non chef (développeur, coordinateur, inconnu) ; refus des chemins (hors dossier, égale au dossier, lien symbolique, dépôt, forge, installation,
relatif, `.git` lien ou fichier, déclarée ailleurs dans l'installation) ; config locale piégée de la copie (`core.fsmonitor`, `core.hooksPath`,
`uploadpack.packObjectsHook`, `core.sshCommand`, `core.pager`, crochets de `.git/hooks`) jamais exécutée pendant
`pousser`, `demander-fusion`, `fusionner` ; témoins : `core.fsmonitor` se déclenche avec un git ordinaire lancé dans la
copie, `packObjectsHook` se déclenche pendant un fetch s'il vient d'une config protégée (globale).
