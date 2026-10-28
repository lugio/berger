# Un dossier temporaire par agent : plus de temporaire commun entre agents stricts

Spec, 14/10/2026 (mission de master ; trou de séparation entre agents, mesuré le 14/10). **Protection = cœur de l'installation** :
aucun code avant l'accord de master ET le go du propriétaire.

## 1. Mesure (le 14/10, depuis un développeur Claude à mur strict, Claude Code 2.1.289)

**D'où vient le TMPDIR.** Ni `bin/berger` ni les réglages générés ne le posent (aucune occurrence de `TMPDIR` dans
`bin/berger` ; `env_agent`, l. 1057, n'ajoute que `BERGER_AGENT` et `BERGER_DIR`). C'est **Claude Code lui-même** :
il prend `CLAUDE_CODE_TMPDIR` s'il existe, sinon le temporaire du système (`/tmp`), y ajoute `claude-<uid>`, le crée en
700 et le donne comme `TMPDIR` aux commandes du bac à sable, inscriptible (`allowWrite` automatique « `$TMPDIR` »).
Tous les agents tournent sous le même compte : **un seul dossier, `/tmp/claude-<uid>`, pour tous**. Le mode 700 ne
protège que des autres comptes, pas des autres agents.

**Ce que voit un agent strict (sonde du 14/10, sans ouvrir de contenu)** :

| Emplacement | Lecture | Écriture |
|---|---|---|
| `/tmp` (racine) | oui | **non** (monté en lecture seule par le bac à sable) |
| `/tmp/claude-<uid>` (fichiers de travail de tous les agents : `.py`, `.js`, `.out`, `.txt`, `.json`…) | **oui** | **oui** |
| `/tmp/claude-<uid>/<dossier de l'autre agent, « / » → « - »>/<session>/tasks` (sorties des commandes en arrière-plan de l'autre agent, relues par SON moteur) | **oui** (plusieurs sessions par agent) | **oui** (`test -w` vrai) |
| le même dossier, pour MOI | oui | non (Claude protège ses propres `tasks` : `denyWithinAllow`) |
| `/tmp/claude-<uid>/bash-edit-diff` | non (Claude le masque) | — |
| `/tmp/claude-http-*.sock` (relais réseau des autres sessions) | — | connexion impossible : `socket(AF_UNIX)` refusé (« Operation not permitted ») |

Montage relevé (`/proc/self/mountinfo`) : `/tmp` en `ro`, `/tmp/claude-<uid>` en `rw` ; seul `…/<moi>/<session>/tasks`
est remonté `ro`. Commandes de la sonde (reproductibles) : `ls -ld /tmp/claude-$(id -u)`,
`test -r|-w /tmp/claude-$(id -u)/<dossier de l'autre agent, « / » → « - »>`, `grep ' /tmp' /proc/self/mountinfo`, et en
Python `socket.socket(socket.AF_UNIX)`. **Je n'ai rien écrit chez un autre agent** : l'écriture est prouvée par le
montage `rw` et `access(W_OK)`, pas par un essai.

**Ce que cela permet** : (a) lire les fichiers de travail d'un autre agent (fuite : sorties de tests, extraits de code,
réponses d'outils du courtier recopiées dans un fichier temporaire) ; (b) réécrire un fichier qu'un autre relira
(falsification, vécue : un fichier d'un développeur réécrit par un autre agent) ; (c) **le pire** : réécrire la sortie
d'une commande en arrière-plan d'un autre agent (`tasks/*.output`), que son moteur lui présente ensuite comme le
résultat de SA commande — une injection de consignes d'un agent dans un autre, y compris vers master ou securite.

**Superviseur** (`superviseur = oui`) : mêmes réglages de bac à sable qu'un strict pour `/tmp` → même trou (non mesuré
séparément, aucune différence dans `reglages_claude`, l. 568-617).

**Codex strict** : **non mesuré** — Codex n'est pas installé sur cette machine (absent du PATH). D'après ses réglages
générés (`config_codex`, l. 640) : profil `extends = ":workspace"`, rien sur `/tmp` ; or le profil « workspace » de Codex
rend inscriptibles `/tmp` et `$TMPDIR` par défaut, et `bin/berger` lui transmet le `TMPDIR` de son lanceur (souvent
absent → `/tmp`). Attendu : sous Codex, `/tmp` entier est commun en lecture ET écriture, y compris `/tmp/claude-<uid>`. À
mesurer par `tests/tout.sh` là où Codex tourne (sonde ci-dessous), avant de conclure.

**Mur ouvert** : ni bac à sable ni cloison, par définition — hors sujet (déjà documenté : réservé aux migrations).

## 2. Cible

**Un dossier temporaire par agent, que lui seul lit et écrit ; le temporaire commun interdit aux agents stricts.**

### Claude (mesuré possible, d'après le code de Claude Code 2.1.289)

- `CLAUDE_CODE_TMPDIR=<racine de l'agent>` : Claude y crée `<racine>/claude-<uid>` (700, propriétaire vérifié) et en fait
  le `TMPDIR` du bac à sable et l'emplacement de ses propres `tasks`. Le dossier commun n'est plus inscriptible
  (`/tmp` reste `ro`).
- **Piège mesuré dans le code** : si le chemin final `<racine>/claude-<uid>` dépasse **44 octets** (limite des sockets
  Unix), Claude **retombe en silence** sur `/tmp/claude-<uid>`, le dossier commun. Le dossier de l'agent
  (`~/berger/agents/<a>/…`) est donc trop long. Racine retenue : **`/tmp/bt/<id>`**, `<id>` = 12 caractères
  hexadécimaux tirés du nom de l'agent (sha256) : `/tmp/bt/<12>/claude-<uid>` = 32 octets pour un uid à 4 chiffres, 38 au pire
  (uid à 10 chiffres). `bin/berger` **refuse de lancer** l'agent si le chemin dépasse 44 octets (jamais de repli
  silencieux).
- `/tmp/bt` est créé par `bin/berger` (hors bac à sable) en 700 ; `/tmp/bt/<id>` aussi, au lancement (le `/tmp` est
  vidé à chaque redémarrage de la machine). Propriétaire et mode vérifiés avant usage ; autre propriétaire = refus.
- Réglages générés (`reglages_claude`) : `sandbox.filesystem.denyRead` += `/tmp/claude-<uid>` et `/tmp/bt` ;
  `sandbox.filesystem.allowRead` += `/tmp/bt/<id>` (le sien, exception dans le refus) ; `permissions.deny` +=
  `Read(/tmp/claude-<uid>/**)`, `Read(/tmp/bt/**)` sauf le sien, `Edit(…)` idem — pour les outils Read/Edit du moteur,
  qui ne passent pas par le bac à sable. Les clés `denyRead`/`allowRead` existent dans cette version (lues dans le code) ;
  leur effet sera **mesuré** avant d'être annoncé.
- Où poser `CLAUDE_CODE_TMPDIR` : **une seule** source, choisie par mesure à la première étape du code. Préférée :
  `env` des réglages générés (comme `env_appelant`), qui couvre tous les chemins de lancement (Herdr, `demander`,
  `tests/tout.sh`) ; si la mesure montre que Claude calcule son temporaire AVANT d'appliquer `env`, alors `env_agent`
  (l. 1057, qui sert `lancer` et `demander`) et `claude_p` de `tests/tout.sh`.
- Superviseur : même règle (il lit les dossiers des autres, pas leurs temporaires : ce n'est pas de la mémoire, ce sont
  des sorties brutes, possiblement des réponses d'outils).

### Codex (à mesurer avant de promettre)

- `TMPDIR=/tmp/bt/<id>` dans l'environnement de lancement (`env_agent`, branche Codex).
- Profil `[permissions.<a>.filesystem]` : `"/tmp/bt/<id>" = "write"`, `"/tmp/bt" = "none"`, `"/tmp/claude-<uid>" = "none"`,
  et `/tmp` en lecture seule si le profil le permet. Piège déjà mesuré (README) : Codex échoue sur un chemin **absent** →
  `berger regenerer` crée ces dossiers avant d'écrire le profil.
- **Dit franchement** : si Codex ne sait pas retirer `/tmp` de son profil « workspace » (règle plus précise qui ne
  l'emporte pas, ou masque refusé par bubblewrap comme pour les fichiers isolés), alors **les agents Codex stricts
  garderont un `/tmp` commun entre eux**. On le dira dans `berger etat` (« temporaire commun : oui ») et dans le README,
  plutôt que d'annoncer une protection non prouvée. Attention : dans ce cas, un agent Codex strict pourrait aussi lire
  et écrire `/tmp/bt/<id>` des agents **Claude** (même compte : le mode 700 n'y change rien). Entre agents Claude, la
  séparation tient quand même ; vis-à-vis de Codex, seul son profil peut la fermer.

### Ce qui ne change pas

Les services hors bac à sable (courtier, planificateur, portes jouées par le courtier, interface) gardent leur
temporaire actuel : ils ne sont pas des agents. `bin/interface.py` et `bin/page/` ne sont pas touchés.

## 3. Effets de bord

- **Python `tempfile`, `mktemp`, git** : suivent `TMPDIR` → le dossier de l'agent. Rien à faire.
- **Outils qui écrivent en dur dans `/tmp`** : déjà refusés aujourd'hui (`/tmp` en lecture seule) ; inchangé. Un outil
  qui LISAIT dans `/tmp/claude-<uid>` un fichier d'un autre agent ne le pourra plus : c'est le but.
- **Sockets Unix** : la limite de 44 octets est respectée par construction ; `AF_UNIX` reste refusé dans le bac à sable.
- **Suites sous `verify`/`tests`/`pret`** : jouées par le courtier, hors bac à sable → inchangées. Jouées par un
  développeur dans son bac à sable → elles écrivent dans SON temporaire ; à vérifier par un passage complet de
  `tests/suites.sh` dans le bac à sable d'un agent après le changement.
- **Place** : `/tmp` est un tmpfs commun (≈ 6 Go) ; la somme ne change pas. Rangement : `/tmp/bt/<id>` est vidé à la
  fermeture d'un développeur (`equipe fermer`) et à la fin de mission, par `bin/berger` (son propre dossier temporaire,
  pas une donnée : pas de validation à part) ; le reste disparaît au redémarrage de la machine.
- **Agents déjà ouverts** : effet au prochain lancement (`berger regenerer` puis `relancer`, au repos). Pendant la
  transition, les sessions pas encore relancées voient encore le dossier commun.
- **Ancien contenu de `/tmp/claude-<uid>`** : rien n'est supprimé par ce changement. Le purger (il contient les sorties
  d'autres agents) est une **suppression** : proposée au propriétaire à part, après la relance de tous les agents.
- **Session du propriétaire** (son propre Claude, hors agent) : non concernée ; elle garde `/tmp/claude-<uid>`.

## 4. Tests (dans la même branche que le code)

1. **Sonde `tests/sonde-tmp.py <moi> <autre>`** (lancée DANS le bac à sable, comme `sonde-mur.py`, n'affiche aucun
   contenu) : `TMPDIR` est sous `/tmp/bt/<id de moi>` ; j'y écris et relis un témoin ; `/tmp/claude-<uid>` : liste et
   lecture REFUSÉES, création d'un fichier REFUSÉE (vérifiée hors bac à sable : sous Claude une écriture interdite peut
   « réussir » sans toucher le disque) ; `/tmp/bt/<id de l'autre>` (témoin posé par `tout.sh`) : lecture et écriture
   REFUSÉES. Une ligne finale `---- N échec(s)`.
2. **`tests/tout.sh`** : la sonde pour chaque agent strict, **Claude et Codex**, plus un témoin hors bac à sable (la même
   sonde DOIT y voir le dossier de l'autre, sinon elle ne prouve rien → INFO). Sous Codex, un échec est un ÉCHEC tant que
   la cible Codex est annoncée ; si la mesure prouve qu'elle est impossible, le test le dit en « limite connue », jamais
   en vert.
3. **Suite sans modèle `tests/tmp-par-agent.py`** (dans `suites.sh`) : réglages générés pour un agent strict et un
   superviseur → `denyRead`, `allowRead`, refus Read/Edit, `CLAUDE_CODE_TMPDIR` (là où il est posé) ; deux agents ⇒ deux
   `<id>` distincts ; **chemin > 44 octets ⇒ lancement refusé** (nom d'agent long, uid simulé) ; dossier `/tmp/bt` d'un
   autre propriétaire ou en mode ≠ 700 ⇒ refus ; mur ouvert ⇒ rien d'ajouté ; profil Codex contient les trois lignes et
   les dossiers existent.
4. **Non-régression** : `tests/syntaxe.sh`, `tests/suites.sh` (tout, hors bac à sable comme aujourd'hui) et
   `tests/pret.sh` ; plus un passage de `tests/suites.sh` lancé par un agent strict dans son bac à sable.

## 5. Retour arrière

- Le changement ne touche que du code versionné (`bin/berger`, `tests/`, README) et des fichiers **générés**.
  Retour : `git revert <commit de fusion>` dans la forge, installation, puis `berger regenerer` et `relancer` des agents :
  ils reviennent au dossier commun, comme aujourd'hui. Aucune donnée n'est déplacée ni supprimée par le changement.
- Sauvegarde avant installation : les réglages générés actuels (`agents/*/.claude/settings.json`,
  `.codex/*config.toml`) sont copiés en `<fichier>.avant-tmp-par-agent-20261014` par l'installation ; aucun ne
  contient de secret (vérifié par `berger secrets audit` avant la copie).
- Les dossiers `/tmp/bt/*` peuvent rester : ils sont vides de sens sans les réglages, et partent au redémarrage.

## Ordre proposé (après accord et go)

1. Mesure Claude de la source de `CLAUDE_CODE_TMPDIR` (`env` des réglages ou environnement) et de `denyRead`/`allowRead`.
2. Code Claude + suite `tmp-par-agent.py` + sonde ; portes.
3. Codex : profil + sonde dans `tout.sh` ; résultat dit tel quel (fermé, ou limite connue).
4. README (tableau des murs, pièges mesurés) et skill `berger` (pièges).

## Après le go (14/10) : ce que la mesure a changé

- **Source de `CLAUDE_CODE_TMPDIR`** : mesurée en lançant Claude Code avec `--setting-sources ""` et l'une puis l'autre
  source. L'`env` des réglages ET l'environnement créent tous deux `<racine>/claude-<uid>` dès le démarrage, et rien
  dans le dossier par défaut. Retenu : **l'`env` des réglages générés** (une seule source, qui couvre Herdr, `demander`
  et `tests/tout.sh`).
- **`allowRead` sous un refus : ignoré.** Le code de Claude Code 2.1.289 l'écarte quand il vient des réglages du projet
  (« filesystem grants restricted to trusted settings tiers »). Le refus de `/tmp/bt` en entier, avec une exception pour
  son propre dossier, ne tiendrait pas. Remplacé par des **refus nommés** : `/tmp/claude-<uid>` plus le dossier de chaque
  autre agent (`tmp_des_autres`), comme les cloisons entre dossiers d'agents. Même limite que celles-ci : un agent ouvert
  après coup n'est caché aux autres qu'à leur prochaine relance.
- **Relais réseau (ajout de master)** : `claude-http-*.sock` est créé dans le temporaire du processus de Claude
  (`os.tmpdir()`, donc `/tmp`), pas sous `CLAUDE_CODE_TMPDIR`. Aucun refus ne le couvre (contrôle de
  `tests/tmp-par-agent.py`). La sonde joint le mandataire de son environnement (fait le 14/10 : joignable).
- **Codex** : pas de `"/tmp" = "read"` (non mesurable ici, et un échec du profil bloquerait l'agent). Le sien est en
  `write`, ceux des autres et le commun en `none` (s'ils existent). Ce que `:workspace` laisse de `/tmp` est mesuré par
  `tout.sh` et dit tel quel.
- **Session de master (ajout de master)** : master est un agent strict, il reçoit donc les mêmes réglages. La mesure
  se fait après installation et relance : `python3 tests/sonde-tmp.py master - claude` lancée dans sa session doit dire
  `---- 0 échec(s)`, et `echo $TMPDIR` doit commencer par `/tmp/bt/`.
- **Les suites** reçoivent une racine jetable courte (`/tmp/btXXXXXX`, `tests/suites.sh`), jamais le vrai `/tmp/bt`.
  Dans un bac à sable (`/tmp` en lecture seule), `regenerer` dit « dossier temporaire refusé » et continue.

## Correctif du 14/10 (sujet tmp-lancement) : l'env des réglages ne suffit pas

- **Constat après relance, sur un agent strict** : son
  `.claude/settings.json` porte `CLAUDE_CODE_TMPDIR=/tmp/bt/<id>`, mais sa session a `TMPDIR` et `CLAUDE_CODE_TMPDIR`
  = `/tmp/claude-<uid>` (le commun, désormais refusé en lecture : chaque commande dit « Read-only file system ») ;
  `/tmp/bt/<id>` reste vide. `tests/sonde-tmp.py master - claude` : 3 échecs. La protection tient (le commun est
  refusé), mais l'agent travaille sans temporaire.
- **Cause racine (lue dans le code de Claude Code 2.1.289)** : le temporaire est choisi sur
  `{instantané de l'environnement d'avant les réglages, + env des sources de confiance}`, et ces sources excluent
  `projectSettings`, `localSettings` et, quand un fichier `--settings` est passé, `flagSettings` (liste
  `["projectSettings","localSettings"]`, liste `CLAUDE_CODE_TMPDIR`/`TMPDIR`/`TEMP`/`TMP` des variables protégées). Un
  agent strict est lancé en `--setting-sources project,local` : **aucune** source de réglages ne compte pour ce choix,
  seul l'environnement du processus. La mesure d'avant le go (`--setting-sources ""` + une source) ne reproduisait pas
  le lancement réel.
- **Correctif** : `env_tmp(a, m)` met `CLAUDE_CODE_TMPDIR` (et `TMPDIR` pour Codex) dans l'environnement du processus,
  pour un agent strict, sur **tous** les chemins de lancement : `lancer` (exec), `demander` (`claude -p`, `codex exec`),
  `demarrer_agent` (export du panneau Herdr : relance, reprise, espaces, missions, développeurs), et `claude_p` de
  `tests/tout.sh`. `demarrer_agent` appelle aussi `exiger_tmp` (comme `lancer`) : dossier douteux = démarrage refusé,
  et le dossier est recréé après un redémarrage. L'`env` des réglages et `exiger_tmp` restent.
- **Tests** : `tests/tmp-par-agent.py` intercepte l'environnement de chaque chemin (exec, `subprocess.run`, export
  Herdr) sans modèle : 7 échecs sans le correctif, 0 avec. Après installation : `berger regenerer`, relance des agents
  stricts au repos, puis la sonde de master (`---- 0 échec(s)`, `echo $TMPDIR` sous `/tmp/bt/`).
