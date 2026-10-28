## Le circuit de développement de {projet} (le même pour toutes les équipes)

`spec → tests → code → doc → portes → demande de fusion → relecture → fusion validée → (version) → installation`

**Qui fait quoi** (tout vient de `[equipes.{projet}]`) — chaîne : développeur → chef de projet ({chef_projet}) →
coordinateur ({coordinateur}) → {proprietaire}.
- Le **coordinateur** découpe le travail et confie chaque sujet au chef (`mission confier` : spec courte + go) ; il suit
  le chef (`mission suivi`, `equipe liste`) ; il n'ouvre pas de développeur.
- Le **chef de projet** ouvre, suit, relance et ferme ses développeurs (`equipe ouvrir|fermer|liste`, `mission suivi`,
  `ecrire`), relit et demande la fusion ; il rend compte au coordinateur.
- Le **développeur** travaille sur SA branche et rend compte à son chef (checklist, `ecrire`, demande de fusion).
- Les alertes (blocage, travail qui n'avance plus, trop de renvois, développeur fusionné encore ouvert) vont au chef, puis
  remontent la chaîne si rien ne bouge.
- **Avant de dire qu'une chose n'existe pas** : la mémoire de l'équipe, puis les skills du projet, puis le code — et tu dis
  où tu as cherché (`REGLES` › « Avant de dire qu'une chose n'existe pas »).

0. **Règle de go** (`REGLES` › « Règle de go ») : si le travail touche un secret visible ou les droits / l'authentification /
   la gestion des secrets, une écriture dans un logiciel métier, la production, le pare-feu, ou ajoute des appels vers un service
   extérieur, la spec courte va à {proprietaire} et attend son go AVANT le code ; sinon le coordinateur décide seul (son go
   accompagne le sujet qu'il confie au chef). Un go = « go », « valide » ou « lance » de {proprietaire} sur une spec écrite
   et nommée, inscrit par sa validation ; **une réponse à des questions n'est pas un go**.
1. **Spec** courte avant le code (`docs/plans/AAAA-MM-JJ-<sujet>-spec.md` si le projet en a) : constat, comportement,
   refus, tests. **Tests** qui prouvent le comportement, écrits avant ou avec le **code** ; la **doc** suit dans la même branche.
   **Tout livrable destiné à {proprietaire}** (spec, maquette, rapport) est déposé là où il le voit, jamais seulement dans une
   branche : une note dans `a-lire/` de l'agent qui le présente (l'essentiel et le chemin exact des fichiers), et les fichiers
   copiés dans `bibliotheque/agents/<agent qui présente>/travail/<sujet>/`. Le développeur, sans bibliothèque, remet les siens à
   son chef de projet, qui les dépose et les présente.
2. **Correctif** (commit `fix…`) : la branche ajoute le **test qui reproduit le bug**, et le commit (ou la demande) écrit sa
   **cause racine** (`Cause racine : …`) — sinon la demande est refusée.
3. **Portes** du projet, dans l'ordre : {portes}. Chacune se lance seule (`berger-outil {projet}-dev <porte>`) ;
   une porte non déclarée est « non mesuré », jamais « vert ». **pret** (finition du projet) est obligatoire — pour le
   développeur, sauf `finition = "chef"` : il livre sa branche « à finir » et le chef passe `pret` sur SA branche de finition.
4. **Demande de fusion** (`demander-fusion`) : copie propre, poussée, à jour avec `{principale}`, puis les 4 portes jouées
   et chaque résultat inscrit — une porte rouge = pas de demande.
5. **Relecture** par le chef de projet ({chef_projet}) : il lit le code, **rejoue les portes** (`rejouer <sujet>`) et
   **recompte** l'annonce du développeur ; un écart ou un défaut = renvoi.
   **Contrôle officiel du projet** : si l'outil de vérification du projet a un verbe de CONTRÔLE (il joue en lecture seule les
   scripts de contrôle d'une branche), c'est le chef de projet qui le lance, sur la branche qu'il relit et sur sa branche de
   finition, avant de demander la fusion. Un contrôleur extérieur, s'il y en a un, ne fait que contre-vérifier.
6. **Fusion validée** par {valideur_fusion} : `pret` rejouée (rouge = refus) ; si `{principale}` a avancé, mise à jour
   automatique SEULEMENT sans fichier commun ni conflit, portes rejouées sur le résultat, sinon refus clair (le développeur
   se met à jour lui-même) ; avance rapide, jamais de push forcé.
7. **Version publiée** : une entrée `## [x.y.z] - AAAA-MM-JJ` (un titre peut suivre la date) dans `CHANGELOG.md` (arrivée par une demande de fusion), puis
   `etiqueter x.y.z` (étiquette `vx.y.z`, SemVer, jamais déplacée) : SANS validation sur le commit d'une fusion validée quand
   c'est la version la plus récente du journal ; sinon validée comme une fusion.
8. **Installation** : hors production, go de {valideur_fusion} ; **production : go de {proprietaire}, à chaque fois.**

**Demande en attente de {proprietaire}** (la nuit, absence) : le développeur n'est pas arrêté. Il poursuit les étapes
suivantes de son chantier **en local**, dans le périmètre du go déjà donné : une pile de commits non poussée (une étiquette
locale), intégrée ensuite par **fusion de `{principale}`**, jamais par réécriture de ce qui est publié. **Exception** : le
cœur de l'installation (courtier, gardes, droits, coffre, règles de validation) attend le go explicite de {proprietaire},
même en local. Le matin, {proprietaire} valide étape par étape ; le chef de projet présente la pile en demandes courtes,
une par étape (`REGLES` › « Demande de fusion en attente »).

Sources (NIST SSDF 1.1, GitHub, DORA, Google, SemVer 2.0.0, Keep a Changelog 1.1.0) : `docs/plans/2026-10-12-processus-dev-generique-spec.md` du dépôt Berger.
