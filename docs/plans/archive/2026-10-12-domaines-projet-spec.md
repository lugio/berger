# Sites permis par projet — `equipes/<projet>/domaines`

Spec courte, 12/10/2026 (mission de master). À relire par la sécurité avant la fusion.

## Pourquoi

Aujourd'hui, le mur strict de **chaque** agent refuse tout réseau (`deniedDomains: ["*"]`, `bin/berger` `reglages_claude`).
Un projet a parfois besoin d'un site précis (l'API de recette d'un logiciel, un dépôt de paquets). Le pare-feu de la
machine ouvre HTTPS à toute la VM : **le mur de l'agent est le SEUL filtre**. Il doit donc rester fermé partout, sauf
vers les noms exacts qu'un projet a fait valider.

## Ce qui a été mesuré (Claude Code 2.1.289, lu dans le programme)

- `allowedDomains` seul **ne ferme rien** : un domaine hors liste déclenche une « demande » ; en mode sans permission
  (`bypassPermissions`, celui des agents) elle passe (mesuré le 04/10 : `allowedDomains: []` → curl 200).
- `deniedDomains` l'emporte toujours sur `allowedDomains` (fusionné depuis toutes les sources) : on ne peut pas garder
  `["*"]` et ouvrir une liste.
- `sandbox.network.strictAllowlist: true` refuse **sans demander** tout domaine hors `allowedDomains`. Il n'est lu
  **que** dans les réglages utilisateur, gérés, ou passés par `--settings` — **ignoré** dans le `.claude/settings.json`
  du projet (celui que génère Berger).
- On ne peut pas retirer la source « projet » (`--setting-sources local`) : elle porte aussi les skills de l'agent.

## (a) La liste et le mur généré

- **Fichier** : `equipes/<projet>/domaines` dans l'installation (à côté de `projets.json`, hors de toute écriture
  d'agent). Un nom par ligne, `#` = commentaire. Noms **exacts** : pas de joker, pas d'adresse IP, pas de port.
- **Qui en profite** : le **coordinateur** du projet (`[equipes.<projet>] coordinateur`, par exemple pour un projet applicatif) et les
  **développeurs** du projet (`projet =` + `sujet =`). Pas le chef de projet, pas les autres agents.
  Un agent coordinateur de plusieurs projets reçoit l'union des listes.
- **Projet sans fichier, ou fichier vide** : deny-all, exactement comme aujourd'hui.
- **Claude** (agent concerné) :
  - `.claude/settings.json` : `network = {"allowedDomains": [liste], "strictAllowlist": true}` (sans `deniedDomains: ["*"]`) ;
  - `.reseau-claude.json` dans le dossier de l'agent : `{"sandbox": {"network": {"allowedDomains": [liste],
    "strictAllowlist": true}}}`, passé par **`--settings`** à chaque lancement (`args_moteur` : Herdr, `demander`,
    `berger args`). C'est lui qui rend la liste stricte ;
  - ce fichier est **protégé** : `denyWrite` du bac à sable + refus `Edit(…)` (l'agent écrit dans son dossier ; sans cela
    il pourrait s'ajouter un domaine). Même protection pour `.reglages-claude.json` des agents à dossier externe ;
  - agent à dossier externe : ses réglages passent déjà entiers par `--settings` — `strictAllowlist` y est donc lu.
- **Codex** : rien ne permet ici de vérifier un filtrage par domaine (Codex n'est pas installé sur la machine de
  développement ; mesure du courtier : « ouvrir une porte réseau ouvre TOUT »). **Un agent lancé sous Codex reste sans
  réseau**, même dans un projet à domaines. Les règles de l'agent le disent. À rouvrir seulement avec une mesure.
- **Limite connue** : lancé à la main (`claude` dans son dossier, sans `berger`), un agent concerné n'aurait pas
  `strictAllowlist` → un domaine hors liste « demandé ». Tout lancement passe par `args_moteur` ; un test le vérifie.

## (b) Ajouter / retirer un domaine

- **Verbe d'écriture** du courtier, outil `equipe` (droit `equipe:<projet>` = le coordinateur) :
  `berger-outil equipe domaine --fichier .transport/requete.json` (paramètres JSON, dans l’ordre : `<projet> ajouter|retirer <domaine>`) ; lecture : `berger-outil equipe domaines --fichier .transport/requete.json` (paramètres JSON, dans l’ordre : `<projet>`).
- **Motif strict** : `^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$`, 253 caractères au plus, minuscules, au moins
  un point ; refus de `*`, IP, port, `localhost`, majuscules (pas de normalisation silencieuse). 30 domaines au plus.
- **Valideur** : le **superviseur** (agent `superviseur = oui`, master) — jamais le demandeur, ni un agent dont le mur
  changerait (coordinateur ou développeur du projet) : dans ces cas, le propriétaire. Le propriétaire peut toujours
  décider (`berger valider|refuser <n°>`).
- **Exécution** (hors bac à sable) : `berger equipe domaine <projet> ajouter|retirer <domaine> --par <agent>` réécrit la
  liste (triée, écrite puis renommée), trace dans **Échanges** (`domaine`), note au journal du demandeur, puis
  **`berger regenerer`**. Effet au prochain lancement des agents concernés (`berger relancer <agent>` pour tout de suite).
- Trace : demande et décision passent déjà par Échanges (validation demandée / validée / refusée).

## (c) Le bac du courtier qui joue les tests

bubblewrap ne filtre pas par domaine. **Ce lot n'ouvre aucun site au bac** : `reseau = false` → `--unshare-net`
(aucun réseau) ; la liste d'un projet ne change rien au bac.

Point d'attention trouvé en lisant : `reseau = true` ne fait pas `--unshare-net`, le bac partage alors **tout le
réseau de la machine** (Internet compris, puisque le pare-feu ouvre HTTPS à la VM), pas seulement localhost.
Voie sûre proposée pour un lot suivant (non codée ici) : le bac reste en `--unshare-net` ; le courtier lance, le temps des
tests, un **petit mandataire HTTPS CONNECT** sur une socket Unix montée dans le bac (relais local → socket) qui
n'accepte que les noms de la liste du projet (port 443, nom résolu par le courtier, adresses privées et locales
refusées), et `HTTPS_PROXY` pointe dessus. Jamais un bac ouvert à tout Internet.

## Identifiants

- **Recette / démo** : peuvent vivre dans la copie du développeur, dans un fichier **ignoré par git**
  (`.git/info/exclude` de la copie), jamais commité ; le garde-fou de secrets et `verifier-depot` restent en place.
- **Production** : au coffre, uniquement par un outil du courtier. Jamais dans une copie, un fichier ou un message.

## Preuves

- `tests/domaines.py` (sans modèle, installation jetable, joué par `tests/suites.sh`) : mur généré (liste → allowed +
  strict, fichier `--settings`, protection ; sans liste et liste vide → deny-all ; non-membre → deny-all ; Codex sans
  réseau) ; motif (joker, IP, port, majuscules, localhost refusés) ; ajout / retrait → liste, Échanges, réglages ;
  courtier : seul le coordinateur demande, valideur = superviseur, superviseur membre → propriétaire, rien avant la décision.
- `tests/sonde-domaines.py <agent> <moteur>` (dans le bac de l'agent) : domaine listé → répond ; domaine non listé →
  refusé ; projet sans liste → tout refusé ; Codex → tout refusé. Jouée par `tests/tout.sh` (essai réel).
