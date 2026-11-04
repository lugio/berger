# Publication automatique vers le dépôt en ligne après une installation réussie (spec)

Règle de go : **cas 1** (installation, courtier, règles de validation ; un envoi vers un service extérieur). Les lots touchent
`bin/berger` (`installer`, `redemarrer_controle`) et la règle « Qui valide quoi » : **aucune ligne de code avant le go du
propriétaire, inscrit sur CE fichier**, même en local. Origine : accord « go push » vers le dépôt en ligne du 29/10 (accord de principe, pas
un go inscrit). Cette spec n'est que du texte.

## Constat (mesuré sur `main`, 07b80d2)

- **Rien ne publie seul.** `fusionner` pousse vers `origin` = la forge locale (`courtier/outils/equipe_chef.py:439`) ;
  `installer` (`bin/berger:3548-3580`) fait `pull --ff-only` depuis la forge, `verifier-depot`, `regenerer`, puis lance à part
  `courtier redemarrer --controle` (`:3572`) ; `redemarrer_controle` (`:3653-3672`) inscrit « courtier redémarré » (`:3663`) et
  s'arrête là. Aucun appel réseau. Après les validations n° 48, 54, 74/75, 80, 82 et 84, le propriétaire a poussé à la main.
- **`publier` n'a jamais tourné** : `courtier/appels.log` (2 572 lignes) ne compte aucun appel à `publier`.
- **Lancé, il échouerait.** `config.toml:129` : `push -q publication main`. La forge n'a qu'un remote, `origin` (le dépôt en
  ligne), fetch `+refs/heads/*:refs/remotes/forge/*` ; `git remote get-url publication` → « Pas de serveur distant
  'publication' ». Même texte dans `config.exemple.toml:308`, et l'étape « `remote add publication` » (`:257`) ; le manuel
  (`docs/manuel.md:942`, `:976-979`) décrit `publier` sans nommer le remote.
- `synchroniser` (`config.toml:130`) et `exporter` (`:131`) n'utilisent que `origin` et `forge/main` : **justes**.
- **Étiquettes** : `poser_etiquette` (`equipe_chef.py:573-578`) crée `v<x.y.z>` annotée et la pousse vers la forge locale
  seulement (`:575`). Rien ne l'envoie en ligne.

## Comportement

1. **Où : dans `redemarrer_controle`, juste après « courtier redémarré » (`:3663`)**, pas à la fin d'`installer`. Raisons : à
   la fin d'`installer` le courtier n'est pas encore redémarré, un retour arrière reste possible (`:3664-3672`) — on
   publierait du code non contrôlé ; le redémarrage tourne dans une unité à part (`systemd-run`, `:3572`), hors de la
   validation en cours, donc un réseau lent ne retient ni le résultat ni le courtier ; un redémarrage abandonné puis
   réessayé (`redemarrage_abandonne`, `:3635`) publie au bon essai. `installer` passe `--publier <forge>` à la commande
   lancée (et `redemarrage_abandonne` le garde pour l'essai suivant) quand l'option 4 est active.
2. **Quoi : le commit installé et contrôlé, rien d'autre.** `git -C <forge> push --porcelain <remote> <apres>:refs/heads/main`
   (SHA de l'installation, pas « main » : si la forge a avancé entre-temps, on n'envoie pas ce qui n'est pas installé).
   Jamais `--force`, `--force-with-lease`, `--mirror` ni refspec en `+` : git refuse tout ce qui n'est pas une avance rapide.
   Refus préalable si `remote.<remote>.mirror` est vrai. `GIT_TERMINAL_PROMPT=0`, délai borné (120 s). Puis `fetch` du
   remote (met `forge/main` à jour) et contrôle `forge/main == <apres>`.
3. **Un échec n'est jamais silencieux.** Ligne `publication échouée : <cause>` dans `courtier/installations.log`
   (`trace_installation`) et `notifier(..., urgent=True)`. Causes nommées : `remote absent (<nom>)` (contrôlé par
   `remote get-url` avant tout push), `divergence (le dépôt en ligne a des commits absents de la forge : synchroniser)`,
   `clé refusée`, `réseau`, sinon les 200 derniers caractères de git. Réussite : `publié : <apres[:10]> → <remote>`. Aucun
   nouvel essai automatique, aucun force ; la forge locale reste la référence ; l'installation n'est **pas** défaite (elle est
   saine) et le code de sortie du redémarrage reste 0.
4. **Option** `publication = "origin"` dans `[equipes.<p>]` du projet qui a `installer_outil` (nom du remote ; absente ou `""`
   = pas de publication automatique). **Défaut proposé : absente (désactivée).** Raison : publier est un envoi ; c'est le
   propriétaire qui l'ouvre, une fois, dans son `config.toml` (qu'aucun agent n'écrit), et une installation sans dépôt en
   ligne (ou clonée en lecture seule) ne reçoit pas une notification d'échec à chaque installation. L'installation du
   propriétaire la met à `"origin"` (son geste). Valeur invalide (remote inexistant) : échec nommé, pas d'arrêt.
5. **`publier` (manuel)** devient `bin/berger publier ~/projets/berger.git` : la même fonction (remote de l'option, sinon
   `origin`), mêmes refus, même trace — mais sur `main` de la forge, validé à chaque fois comme aujourd'hui.
   `synchroniser` et `exporter` : inchangés. `config.exemple.toml` : retirer `remote add publication`, nouvelle ligne `publier`,
   option `publication` commentée.
6. **Étiquettes** : à chaque publication (auto ou manuelle), les `v*` de la forge qui pointent sur un ancêtre du commit
   publié partent aussi, une par une (`refs/tags/vX:refs/tags/vX`, sans `+` : git refuse de remplacer une étiquette en
   ligne ; un tel refus = `publication échouée : étiquette vX différente en ligne`). `etiqueter` ne touche pas le réseau :
   une étiquette posée après l'installation part à la publication suivante, ou par `publier`.
7. **Règle** : `commun/REGLES.md` › « Qui valide quoi », ligne « Déjà couverts par la fusion validée » : ajouter « la
   publication du commit installé et contrôlé, si `publication` est activée ». Le reste des envois garde sa validation.

## Tests (rouges d'abord, sans réseau, dans un dossier jetable)

`tests/publication.py`, dans `tests/suites.sh` : une forge nue et un « en ligne » nu (`file://`), un clone qui pousse.
Léger (quelques `git init --bare`, aucun courtier réel : `systemctl` simulé comme dans `tests/redemarrage-courtier.py`).
- avance rapide → `publié : …`, `en ligne/main == apres`, étiquettes ancêtres présentes en ligne ;
- divergence (un commit seulement en ligne) → refus, en ligne inchangé, ligne `publication échouée : divergence`,
  notification urgente, aucune commande contenant `--force` ni `+` (journal des commandes git du test) ;
- remote absent → `publication échouée : remote absent (origin)`, aucun push tenté ;
- option absente → aucune commande réseau, rien dans `installations.log` ;
- courtier non resté actif → retour arrière, **aucune** publication ;
- `publier` manuel → même fonction (même ligne de trace) ; `config.exemple.toml` ne nomme plus de remote `publication`.

## Lots

1. Tests rouges + `publier_forge()` dans `bin/berger` + appel dans `redemarrer_controle` + `--publier` (installer, nouvel
   essai). **Cas 1 : go inscrit avant le code.**
2. `publier` manuel, `config.exemple.toml`, manuel (`:942`, `:976-979`), `commun/REGLES.md`, CHANGELOG. **Cas 1 aussi**
   (règles de validation).
3. Hors code, geste du propriétaire : `publication = "origin"` dans son `config.toml` et la nouvelle ligne `publier`.

Hors périmètre : protéger la branche en ligne, une autre forge, le réessai automatique.
