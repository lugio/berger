# SHA figé : la fusion validée est celle du commit présenté, les portes distantes testent ce commit (spec)

Règle de go : **cas 1** (courtier, règles de validation). Les lots 1 et 2 touchent `courtier/courtier`,
`courtier/outils/equipe_chef.py` et `courtier/outils/equipe_dev.py` : ils attendent le go du propriétaire, **inscrit** sur CE
fichier, avant la première ligne de code (même en local). Cette spec n'est que du texte. Origine : relectures Codex des
validations n° 67 et 69, accord « go 1 2 3 » du 29/10 (accord de principe, pas un go inscrit).

## Constat (mesuré sur `main`, 3017478)

- **La validation ne porte que le sujet.** `demander_validation` (`courtier/courtier:627`) appelle l'aperçu (`:630`) puis range
  `{"verbe", "args", "apercu", …}` (`:640-641`) : pour `fusionner`, `args = ["<sujet>"]`. Le commit n'apparaît que dans le
  **texte** de l'aperçu, tronqué à 10 caractères (`equipe_chef.py:402`, `d['commit'][:10]`). À l'exécution, le courtier rejoue
  l'action avec ces seuls `args` (`courtier:779`).
- **L'exécution relit la demande, pas ce qui a été validé.** `fusionner` (`equipe_chef.py:404`) relit `<sujet>.json` (`:405`) puis
  compare `origin/<branche>` à `d["commit"]` (`:409-411`) — c'est-à-dire la branche à la demande **du moment**. Scénario Codex :
  aperçu du commit A ; le développeur repousse B et refait `demander-fusion` sous le même sujet (le fichier est réécrit) ; le
  valideur accepte ce qu'il a vu (A) ; l'exécution recharge B, B = branche → **B est fusionné sans avoir été présenté**.
- **Les portes distantes reçoivent un nom de branche.** Côté chef, `jouer_portes(commit, branche)` (`equipe_chef.py:313`) clone et
  détache bien `commit` pour les commandes (`:326-327`), mais l'outil reçoit `[branche]` (`:341-344`). Appels : `rejouer` (`:356`,
  branche du développeur, contrôlée à `:353-355` puis jouée plus tard), `fusionner` en avance rapide (`:417`, porte `pret`),
  `portes_integration` (`:500-506`, branche `integration/<sujet>`). Côté développeur, `porte_distante` passe
  `self.valeurs()["branche"]` (`equipe_dev.py:67`), y compris pendant `demander_fusion` (`:96`) alors que le commit inscrit est
  `tete` (`:84`). Un push entre le contrôle et l'exécution distante fait tester B, puis inscrire ou fusionner A.
- Aucune porte `_outil` n'est déclarée dans le `config.toml` de l'installation aujourd'hui ; le contrat est documenté dans
  `config.exemple.toml:196-202` (« reçoit la branche poussée »).

## Comportement

1. **Le commit est figé à l'aperçu.** Un aperçu peut rendre `{"apercu": texte, "args": [...]}` au lieu d'un texte : le courtier
   range alors CES `args` (choisis par l'outil, jamais par l'agent). `apercu_fusion` lit la demande **une seule fois** et rend
   `args = [sujet, commit]` (SHA complet). Le texte de l'aperçu affiche ce SHA complet. Les autres outils ne changent pas.
2. **L'exécution vérifie le commit figé.** `fusionner([sujet, sha])` refuse si `d["commit"] != sha` ou si `origin/<branche> != sha`,
   puis ne travaille QUE sur `sha` (contrôles, portes, mise à jour, push). Une nouvelle demande sous le même sujet périme la
   validation : il en faut une nouvelle (le chef redemande `fusionner`).
3. **Les portes distantes reçoivent le SHA, jamais une branche.** `<porte>_outil` reçoit `[sha]` (40 caractères hexadécimaux) :
   `jouer_portes` (chef) passe `commit` ; `porte_distante` (développeur) passe `tete` déjà contrôlé (`HEAD` = `origin/<branche>`).
   `portes_integration` garde son push `integration/<sujet>` (l'outil distant doit pouvoir récupérer le commit) mais passe `cible`.
   **Contrat de l'outil** : il récupère le dépôt, se place en tête détachée sur ce SHA (refus s'il est absent) et écrit dans sa
   sortie une ligne `commit testé : <sha>`. Le courtier ne compte **vert** qu'une sortie qui porte cette ligne avec le SHA envoyé.

## Refus (messages clairs, rien n'est fusionné ni poussé)

- `fusionner` demandé avec un 2e argument par l'agent : « le commit est figé par le courtier à l'aperçu, pas choisi par l'agent ».
- Validation sans SHA (rangée avant l'installation) : « validation n° N antérieure au SHA figé : redemande la fusion (nouvel aperçu) ».
- `d["commit"] != sha` : « la demande « s » a changé depuis l'aperçu (validé : A, demandé maintenant : B) : nouvelle validation nécessaire ».
- `origin/<branche> != sha` : « la branche a bougé depuis l'aperçu (validé : A, branche : B) : le développeur redemande la fusion ».
- SHA mal formé (ni 40 ni 64 hexadécimaux) : refus avant tout git.
- Porte distante dont la sortie n'atteste pas `commit testé : <sha>` (absente ou autre SHA) : porte **rouge** (« l'outil n'a pas
  prouvé avoir testé <sha> »), jamais verte par défaut.

## Tests (un test rouge d'abord par point, nouveau `tests/sha-fige.py`, dépôts git temporaires, aucun test lourd)

1. Aperçu A, nouvelle demande B sous le même sujet (branche poussée sur B), exécution de la validation → refus, `main` intact.
2. Aperçu A, branche repoussée sur B sans nouvelle demande → refus « la branche a bougé », `main` intact.
3. Aperçu A, rien ne bouge → fusion de A (non-régression ; `tests/equipe.py`, `processus-dev.py` restent verts).
4. Validation rangée sous l'ancienne forme `["<sujet>"]` → refus « antérieure au SHA figé » ; `fusionner` avec 2 args agent → refus.
5. Faux outil de porte (comme `tests/equipe-verif.py:49`) : il reçoit un SHA de 40 caractères, jamais un nom de branche, côté chef
   (`rejouer`, `fusionner`, `portes_integration`) et côté développeur (`demander-fusion`, verbe `<porte>` seul).
6. Faux outil qui répond vert sans la ligne `commit testé`, ou avec un autre SHA → porte rouge, pas de demande ni de fusion.

## Lots

- **Lot 1 (cas 1)** — points 1, 2 et refus associés : `courtier/courtier` (aperçu qui fige ses `args`), `equipe_chef.py`
  (`apercu_fusion`, `fusionner`). Tests 1 à 4.
- **Lot 2 (cas 1)** — point 3 : `equipe_chef.py` (`jouer_portes`, `rejouer`, `portes_integration`), `equipe_dev.py`
  (`porte_distante`, `fabriquer_distant`, `jouer_portes`), `_portes.py` (attestation du SHA). Tests 5 et 6.
- **Lot 3 (doc, coordinateur)** — `config.exemple.toml:197` (« reçoit le SHA contrôlé »), manuel et skill du projet, CHANGELOG.

## Compatibilité : validations `fusionner` déjà en attente à l'installation

- **Proposé : refus clair** (point 4). Le chef redemande `fusionner` ; le nouvel aperçu porte le SHA complet. Coût : une
  validation à refaire par demande en attente. `berger valider` affiche ce refus, rien n'est fusionné.
- Écarté : migrer en relisant les 10 caractères du texte d'aperçu (`equipe_chef.py:402`) — 40 bits seulement, un préfixe
  fabriqué est à la portée d'un calcul ordinaire ; ce serait figer une preuve faible.
- Les autres écritures (`etiqueter`, autres outils) gardent leur forme : non touchées.

Décision attendue : go inscrit du propriétaire sur ce fichier (lots 1 et 2) ; choix « refus clair » pour les validations en attente.
