# Portes allégées : une demande « documentation seule » passe une porte courte (spec)

Règle de go : **cas 1** (courtier, règles de validation). Le lot 1 touche `courtier/outils/_portes.py`, `equipe_dev.py`,
`equipe_chef.py` et `courtier/courtier` : il attend le go du propriétaire, **inscrit** sur CE fichier, avant la première ligne de code.
Les lots 2 et 3 ne touchent ni courtier ni droits (coordinateur). Cette spec n'est que du texte. Origine : « go accélération » du 28/10.

## Constat (mesuré sur `main`, 928e51e)

- **Quatre portes, toujours toutes** : `PORTES = ("verify","tests","gate","pret")` (`_portes.py:17`) ; `jouer()` (`:43`) les joue
  dans l'ordre. Rien ne regarde ce que la demande change : une faute de frappe dans `docs/` rejoue `tests/suites.sh`
  (≈ 17 min, `delai = 1500` dans `config.toml`).
- **Un seul chemin** pour le développeur et pour le chef : `demander_fusion` du développeur (`equipe_dev.py:76`) → `jouer_portes`
  (`:67`) ; côté chef `demander_fusion` (`equipe_chef.py:258`), `rejouer` (`:328`) et `fusionner` (`:380`) passent par `jouer_portes`
  (`:296`, copie jetable). À la fusion en avance rapide seule `pret` est rejouée (`:391`) ; si `main` a avancé, les 4 le sont sur le
  commit de mise à jour (`portes_integration`, `:476`).
- **Le périmètre du diff se lit déjà** : `controler_demande` (`_portes.py:95`) lit `git diff --name-only origin/main...tete`
  (règle du correctif) ; `MOTIF_TESTS` (`:21`) reconnaît les fichiers de test.
- **Contrôles documentaires existants** : `tests/syntaxe.sh` (verify), `berger verifier-depot` (`bin/berger:3470`, marques et
  données personnelles), `tests/marques-produit.py`, `tests/vitrine.py` (empreinte sha256 du corps du manuel `:50`, liens locaux
  `liens_invalides` `:23`). Aucun n'est joué seul aujourd'hui.
- **Bug `mettre-a-jour`** (28/10, `version-0-2-0`) : le verbe est `git fetch … && git merge --no-edit origin/{principale}`
  (`equipe_dev.py:39`), lancé par `copie.py:executer` (`:57-60`) avec pour seul ajout d'environnement `ENV_GIT` (hooks et fsmonitor,
  `_commandes.py:23`). Aucune identité git. Reproduit à la main : une vraie fusion (branches divergentes) sans `user.name` ni
  `user.email` répond `fatal : impossible de détecter automatiquement l'adresse ('…@omarchy.(none)' trouvé)`. Une avance rapide
  passe, d'où des tests verts : `tests/equipe.py:56` joue `mettre-a-jour` avec l'identité de la machine de test.
  Le chef a déjà ce qui manque : `AUTEUR` (`equipe_chef.py:31`, « berger (courtier) »), utilisé pour ses propres commits (`:81`).
- **`.gitignore`** : liste blanche `/*` ; `!/courtier/` ré-admet tout le dossier, `courtier/consignes/` (`CONSIGNES`,
  `bin/berger:1124`, données d'annonce d'un changement d'outil) y apparaît donc `??` sur le portable et le VPS.

## Comportement

1. **Porte courte `doc`.** Nouvelle clé facultative `[equipes.<projet>] doc = "commande"` (ou `doc_outil`), même forme que `verify`.
   Pour berger : `doc = "bash tests/portes-doc.sh"` = syntaxe (`syntaxe.sh`), `verifier-depot`, `marques-produit.py` et
   `vitrine.py` (empreinte du manuel, liens). Sans `doc` déclarée : rien ne change (porte complète).
2. **Le courtier décide, jamais l'agent.** `_portes.documentation_seule(git, base, tete)` lit
   `git diff --raw --no-renames -z origin/main...tete` dans le dépôt qui porte la branche, côté développeur ET côté chef (le chef
   recalcule : il ne croit pas l'annonce). Vrai si, pour **chaque** chemin : extension `.md`, ou sous `docs/` avec extension
   `md|png|jpg|svg|webp|txt` ; et pas de fichier de test (`MOTIF_TESTS`) ; et pas sous `commun/` (consignes lues par les agents,
   donc comportement) ; et modes `100644` avant et après (ni lien symbolique, ni exécutable, ni sous-module). Diff vide ou illisible
   → faux. Un seul chemin hors périmètre → porte complète.
3. **Ce qui est joué.** En mode court : `verify` et `pret` comme avant, `gate` s'il existe, et la porte `doc` **à la place de**
   `tests`. Le résultat inscrit dans `tests` porte `court: "documentation seule"` (les 4 portes restent présentes : verdict,
   annonce, recompte, `rejouer`, résumés inchangés). Le message dit : `porte courte (documentation seule : N fichiers) — tests
   complets non joués` ; sinon, quand `doc` est déclarée : `porte complète : <chemin hors périmètre> n'est pas de la documentation`.
4. **Rien d'autre ne change.** Fusion : `pret` toujours rejouée avant l'avance rapide ; si `main` a avancé, le mode est recalculé
   sur le commit de mise à jour (même règle, même diff). Le go, les marques, le correctif, le valideur : intacts.
5. **`mettre-a-jour`** reçoit une identité git fixe (`AUTEUR` du courtier, variables d'environnement pour ce seul verbe, sans toucher
   à la config de la copie) : la fusion réussit sans identité locale ; le commit est signé « berger (courtier) ».
6. **`.gitignore`** : ajouter `/courtier/consignes/` (bloc « jamais de données locales »).

## Refus

- Porte courte demandée, déclarée ou déduite par l'agent : impossible (aucune entrée ; la décision vient du diff).
- Diff illisible, vide, ou dont un chemin est hors périmètre : porte complète, jamais courte « par défaut ».
- Porte `doc` rouge : pas de demande, comme toute porte rouge. `doc` absente : jamais « vert », la porte complète s'applique.
- `.md` sous `tests/` ou `commun/`, fichier renommé vers/depuis du code (`--no-renames` liste les deux chemins) : porte complète.

## Tests (`tests/portes-allegees.py`, ajoutée à `suites.sh`)

- Décision : doc seule → courte ; doc + un `.py` → complète et le message nomme le fichier ; `docs/scripts/x.sh`, `tests/x.md`,
  `commun/x.md`, renommage `bin/x.py → docs/x.md`, lien symbolique `.md`, mode exécutable, diff vide → complète.
- Le développeur ne peut rien forcer : aucun argument ne modifie le mode ; `agent.conf` ignoré.
- Développeur : demande « doc seule » → `tests` remplacée par `doc` (marque `court`), `pret` jouée ; chef : `rejouer` recalcule
  le même mode et le recompte reste « conforme » ; annonce complète rejouée en court (ou l'inverse) → écart signalé.
- Fusion : `pret` rejouée en avance rapide ; `main` avancé → mode recalculé sur le commit de mise à jour.
- **Bug** (`fix`, test d'abord rouge) : `mettre-a-jour` dans une copie dont HOME est vide (`GIT_CONFIG_GLOBAL=/dev/null`, sans
  `user.*`), branches divergentes → code 0 ; avant correctif : « impossible de détecter automatiquement l'adresse ».
  **Cause racine : `mettre-a-jour` lance `git merge` sans identité (seul `ENV_GIT` est posé) ; l'auteur du courtier n'existait que
  côté chef (`AUTEUR`, `equipe_chef.py:31`), et les tests passaient parce que la machine de test a une identité ou fait une avance rapide.**
- `.gitignore` : dossier `courtier/consignes/` créé avec un fichier → `git status --porcelain` vide ; `verifier-depot` vert.
- Inchangés et verts : `equipe*.py`, `hierarchie-equipe.py`, `regle-go*`, `tests/tout.sh`, CI, `verifier-depot`.

## Lots (une demande de fusion chacun)

1. **Cas 1, après go** : `_portes.documentation_seule` + substitution dans `jouer`, branchement développeur et chef, clé `doc`
   transmise par `courtier/courtier:102-106`, `tests/portes-doc.sh`, `doc = …` dans `config.exemple.toml`, test, manuel et CHANGELOG.
2. **Hors go** : `mettre-a-jour` avec identité + test + cause racine (commit `fix`). Peut partir seul avant le go : il ne change ni
   droit ni garde, mais touche `equipe_dev.py` du courtier ; par prudence il suit le lot 1 dans la même demande si le go tarde.
3. **Hors go** : `.gitignore` + test.

## Points ouverts

- `commun/*.md` en porte complète (proposé) : acceptable, ou compte-t-il comme documentation ?
- `verifier-depot` lit le coffre (`config.toml`, commentaire de `tests =`) : la porte `doc` le joue en dépôt jetable comme
  `vitrine.py` ; sans configuration privée il est « non mesuré », jamais vert. Suffisant, ou l'exige-t-on réel (`installer`) ?
