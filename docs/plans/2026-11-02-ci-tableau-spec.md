# État de la CI du dépôt en ligne dans le tableau de bord — spec courte (02/11/2026)

Règle de go : cas 5, de nouveaux appels vers un service extérieur (api.github.com, en lecture). Demande du propriétaire du
02/11.

## Constat

La v0.3.0 est publiée, mais la CI publique « Model-free checks » est en échec. Personne ne l'a vu dans Berger : rien dans
Berger ne lit l'état de la CI du dépôt en ligne. Le défaut (Python 3.11) est resté invisible du 29/10 au 02/11.

## Comportement

1. **Nouveau verbe de LECTURE `ci <dépôt> [branche]`** de l'outil de type `github` (`courtier/outils/github.py`).
   - Un seul appel : `GET https://api.github.com/repos/<dépôt>/actions/runs?branch=<branche>&per_page=1`. La branche par
     défaut est `main`. Le dépôt doit être dans la liste fermée `depots` de l'outil.
   - Le jeton est celui de l'outil (`cle`, dans le coffre). Comme pour les autres verbes, il passe à curl par l'entrée
     standard et ne part que vers api.github.com.
   - Sortie, une ligne, sans URL ni jeton :
     - « ✓ CI <workflow> verte · <sha court> · <date> » ;
     - « ✗ CI <workflow> en ÉCHEC · <sha court> · <date> » (conclusion failure, timed_out, startup_failure ou cancelled) ;
     - « ⚠ CI <workflow> en cours · … » (pas encore de conclusion).
   - Aucun run, ou réponse illisible : c'est une erreur nommée, donc la collecte échoue et la source passe ROUGE (« collecte
     en échec »). Ce n'est jamais un vert.
2. **Source déclarée par le propriétaire**, avec le mécanisme existant `[panneaux.<nom>]` (aucun nouveau mécanisme), dans
   `config.exemple.toml` :
   ```toml
   # [panneaux.ci-publique]
   # titre = "CI du dépôt en ligne"
   # outil = "github"
   # verbe = "ci"
   # args = ["<propriétaire>/berger"]
   # cadence = 900          # 4 appels par heure
   ```
   « ✗ » donne déjà du rouge, et « ⚠ » du jaune, avec `etat_ligne`. L'alerte passe donc ROUGE dans l'Accueil (Synthèse) et
   s'affiche dans Coulisses › Sources.
3. **Lecture seule.** Aucun nouveau droit d'agent, aucune écriture, aucun secret affiché. Aucun agent n'appelle ce verbe :
   seul le collecteur de sources du courtier le fait. Un agent qui a déjà l'outil `github` le peut aussi, en lecture, dans
   la même liste fermée de dépôts.

## Refus

- Un dépôt hors de `depots` est refusé (message existant).
- Un nom de branche hors de `[A-Za-z0-9._/-]{1,100}` est refusé avant tout appel.
- Rien n'est relancé, annulé ni commenté sur GitHub.

## Tests (sans réseau, faux curl)

1. Run en succès : une ligne ✓. Run en échec : une ligne ✗, que `etat_ligne` classe rouge. Run en cours : ⚠, classé jaune.
2. Aucun run, ou JSON illisible : erreur nommée, et la source passe rouge par « collecte en échec ».
3. Dépôt hors liste et branche invalide : refusés, sans appel.
4. Le jeton n'apparaît ni dans l'argv de curl ni dans la sortie.

Doc : manuel (outil github, verbe `ci` ; exemple de source) et CHANGELOG [Unreleased]. Après l'installation, le propriétaire
déclare `[panneaux.ci-publique]` dans son config.toml, puis lance `berger regenerer`.
