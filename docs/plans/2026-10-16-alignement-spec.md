# Alignement après une mise en production — spec (AUCUN code avant le go inscrit)

Spec courte, 16/10/2026 (mission de master, sujet `alignement`). **Go du propriétaire du 16/10 : « go spec alignement »** —
la spec seulement ; le go du code sera inscrit par `equipe go` sur CE fichier. Touche le cœur (courtier : exécution des
validations, droits d'équipe) et les droits (point 3 : règle de go, cas 1) : rien n'est écrit, même en local, avant ce go.
Rien de propre à un moteur ni à un projet dans le code : tout ce qui est propre au projet est dans `[equipes.<p>]`.

## Constat (le 113, 16/10)

Après une mise en production, seuls git, la forge et le `CHANGELOG.md` sont tenus. Le wiki, la mémoire, les skills et le
contrôle des versions ne le sont pas (wiki de la 3.489.0 non fait). Le chef de projet n'a aucun outil wiki, alors que
`wikijs-lecture` et `wikijs-ecriture` existent (hors dépôt, `~/outils-courtier/wikijs`, espaces permis COMMUNS à tous :
`zones` de leurs réglages). **Cause racine** : rien, dans Berger, ne relie le compte rendu `ok` de `berger-prod` à ce qui
doit suivre ; rien ne le rappelle au chef.

## (1) Ce que le projet déclare — `[equipes.<p>]` (dans `config.exemple.toml`, jamais dans le code)

```toml
alignement = ["changelog", "wiki", "memoire", "skills", "versions"]   # absent ou [] : rien de ce qui suit
prod_outil = "monprojet-prod prod"            # l'ACTION dont le compte rendu « ok » ouvre la liste
compte_rendu_outil = "monprojet-prod compte-rendu"   # sa LECTURE (connexion coupée à 180 s : le compte rendu relu)
version_servie_outil = "monprojet-prod version"      # lecture qui rend la version servie (point 5)
wiki = "service_info/monprojet"               # l'arborescence du projet au wiki (point 3)
[equipes.monprojet.modules]                   # facultatif ; sans lui, un module = un dossier de premier niveau
facturation = { chemins = ["app/factu/"], relire = ["wiki:service_info/monprojet/facturation", "skill:facturation"] }
```
**Refus au chargement du courtier** (comme `installer_outil`) : élément inconnu dans `alignement` ; `prod_outil` qui n'est pas
une action déclarée ; `compte_rendu_outil` / `version_servie_outil` qui ne sont pas des lectures ; `wiki` hors des `zones` de
l'outil, avec `..`, ou vide ; un `relire` qui n'est pas `wiki:` / `skill:` / `memoire:`. **Tests** : chaque refus, et un
projet sans `alignement` → aucun changement de comportement. **Retour arrière** : retirer les lignes. **Droits** : aucun.

## (2) La liste d'alignement, ouverte par un compte rendu `ok`

- **Quand** : dans `traiter_decisions` (courtier), après « validé et exécuté » de `prod_outil`, ET à chaque lecture de
  `compte_rendu_outil` par le chef : la sortie est lue comme le JSON de `berger-prod`. **Seul `statut = "ok"` ouvre une liste**
  ; `essai`, `refus`, `retour-arriere`, `retour-arriere-echoue`, ou un JSON illisible : rien (une ligne au journal du chef).
- **Contenu** — `equipes/<p>/alignement/<version_apres>.json` (local, non versionné) : version d'avant et d'après, commits,
  date ; les **modules touchés** = `git diff --name-only <commit_avant> <commit_apres>` dans le dépôt du chef (repli : les
  étiquettes `v<avant>..v<après>`), rangés par `[equipes.<p>.modules]` ; pour chaque module, **ce qu'il faut relire** (ses
  `relire`) ; puis une case par élément d'`alignement` : `ouvert`, `fait` ou `sans-objet`.
- **Soldé tout seul quand c'est mesurable** : `changelog` (entrée `## [x.y.z]` et ligne « Déployée » sur la principale),
  `versions` (point 5 concordant), `wiki` (pages `relire` du module modifiées après la mise en production, point 3),
  `memoire` / `skills` (une proposition `pending/` du chef qui cite la version, point 4).
  Sinon le chef clôt : `berger-outil <p>-chef alignement liste | voir <version> | clore <version> <élément>[:<module>]
  fait|sans-objet "<note>"` — lectures (simple tenue de liste, aucune validation) ; `sans-objet` exige une note ≥ 20 caractères.
- **Ne bloque rien** : ni fusion, ni étiquette, ni mise en production suivante. Une version plus récente ouvre sa propre liste.
- **Rappel tant qu'elle est ouverte, anti-boucle respecté** : par `relancer_attentes` (planificateur), un seul message au
  chef pour toutes ses listes ouvertes, **au plus une fois par 24 h**, chef **au repos** seulement (clé
  `<p>:alignement:<versions>`). Ce rappel est une sollicitation (`solliciter`) : les lectures du chef qui suivent ne comptent
  pas comme une boucle. Le chef ne relit pas la liste en attendant : il attend le rappel. `equipe liste` montre au
  coordinateur les listes ouvertes.
- **Refus** : statut ≠ ok ; version déjà listée (aucun doublon, la liste existante est gardée) ; commit absent du dépôt →
  liste ouverte avec « modules : inconnus » (jamais d'invention) ; `clore` d'une version, d'un élément ou d'un module inconnu ;
  chef d'un autre projet ; développeur.
- **Tests** (`tests/alignement.py`, installation jetable, faux `ssh` qui rejoue un compte rendu) : `ok` → liste avec les bons
  modules et `relire` ; les quatre autres statuts et un JSON cassé → aucune liste ; lecture `compte-rendu` après coupure →
  même liste, une seule ; rappel une fois par 24 h, jamais à un chef occupé, plus aucun une fois tout soldé ; soldes
  automatiques ; `clore` refusé à un développeur, `sans-objet` sans note refusé ; une liste ouverte ne bloque pas `fusionner`.
- **Retour arrière** : `alignement = []` (plus aucune liste ni rappel ; les fichiers restent, inertes). **Droits** : aucun
  nouveau (verbe ajouté à l'outil `<p>-chef` qu'il a déjà).

## (3) Wiki : le chef lit et propose dans SON arborescence

- **Droits** : `droits_equipe` donne au chef `wikijs-lecture` et `wikijs-ecriture` quand `wiki` est déclaré — rien dans un
  `agent.conf`, rien aux développeurs ni au coordinateur.
- **Limité à l'arborescence** : le courtier passe la zone **calculée** (`wiki` de SON projet) à l'outil, jamais l'agent :
  `BERGER_WIKI_ZONE` (type `scripts`) ou `{zone_wiki}` (type `commandes`). Les scripts wiki (hors dépôt, installés par le
  propriétaire) refusent tout chemin hors de cette zone ; la zone ne fait que **rétrécir** les `zones` existantes, jamais les
  élargir ; `ecriture_interdite` reste.
- **Chaque publication validée par le propriétaire** : pour un chef d'équipe, `publier` / `schema` de `wikijs-ecriture` ne
  vont qu'au propriétaire, même si `valide_par` désigne un agent. L'`essai` reste une lecture.
- **Fraîcheur mesurée par le courtier**, hors bac à sable : il appelle lui-même `wikijs-lecture arbre <wiki>` et compare la
  date de modification des pages `relire` à la date de mise en production. Jamais un script de contrôle lancé dans un bac à
  sable (pas de réseau, et ce serait au chef de se noter lui-même).
- **Refus** : chemin hors zone (lecture ou écriture) ; chef sans `wiki` déclaré ; publication validée par un agent ;
  développeur ; projet voisin.
- **Tests** : chef lit et essaie dans sa zone ; hors zone refusé ; un autre chef refusé hors de SA zone ; publication →
  validation au propriétaire seul, `valide_par` ignoré ; développeur et coordinateur sans l'outil ; zone posée par le
  courtier même si l'agent passe un autre argument ; fraîcheur lue par faux wiki.
- **Retour arrière** : retirer `wiki` (droits retirés aussitôt, calculés) ; scripts wiki : copie datée `.avant-alignement-
  <AAAAMMJJ>` faite AVANT par le propriétaire, restaurée par `cp`.
- **Droits touchés : OUI — règle de go, cas 1** (nouveaux outils pour le chef, limite par zone). Go inscrit exigé.

## (4) Mémoire et skills : propositions du chef

Le chef écrit ses propositions dans SON `pending/` (`type: memoire` ou `type: skill`, avec `version: x.y.z` en tête pour
solder la case) ; le propriétaire valide (`berger memoire valider`, skill copiée) comme aujourd'hui. **Aucun nouveau droit,
aucun nouveau circuit** ; une skill ou une mémoire d'équipe qui vit dans le dépôt du projet change par une demande de
fusion, comme aujourd'hui. **Refus** : rien n'est écrit sans validation. **Tests** : une proposition qui cite la version
solde la case, une validée aussi ; une refusée la laisse ouverte. **Retour arrière** : retirer l'élément de `alignement`.

## (5) Versions : un verbe en lecture

`berger-outil <p>-chef versions` compare : la **version servie** (`version_servie_outil`), la **dernière étiquette** SemVer
du dépôt, et la plus haute version marquée « Déployée » du `CHANGELOG.md` de la principale (ligne `Déployée : AAAA-MM-JJ`
sous `## [x.y.z] - …`, ajoutée par le chef dans une demande de fusion). Rend « concordant » ou chaque écart nommé (ex.
« servie 3.489.0, étiquette 3.490.0 : étiquette non déployée »). **Refus** : outil de version absent → « non mesuré »,
jamais « concordant » ; sortie illisible → « non mesuré ». **Tests** : concordant ; chacun des trois écarts ; non mesuré.
**Retour arrière** : retirer `version_servie_outil`. **Droits** : aucun (lecture d'un outil déjà déclaré, par le courtier).

## Documentation, portes

`config.exemple.toml` (l'exemple ci-dessus, commenté), README, `commun/modeles/equipe-processus.md` (étape 8 :
« après l'installation, la liste d'alignement »), skill berger. Tests joués par `tests/suites.sh` ; portes `verify`, `tests`,
`pret`. Hors dépôt (installé par le propriétaire, notice dans la branche) : la zone dans les scripts wiki.
