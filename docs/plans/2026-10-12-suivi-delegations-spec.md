# Suivi des délégations — les promesses faites en délégation ne se perdent plus

Spec courte, 12/10/2026 (mission de master). À relire par la sécurité avant le code.

## Constat

`berger-outil deleguer <cible> --fichier .transport/requete.json` (paramètres JSON, dans l’ordre : `"<question>"`) : la cible répond dans une conversation NEUVE (`berger demander`), le courtier
rend la réponse au demandeur, puis tout est perdu côté cible. Vécu : Artisan a promis une action à Métiers et l'a oubliée.

## Comportement (courtier, fonction `deleguer`, hors bac à sable)

a. **Consigne** envoyée à la cible : en plus de l'actuelle, « termine ta réponse par une ligne `ENGAGEMENTS:` suivie d'une
   action promise par ligne commençant par `- ` ; si tu ne promets rien : `ENGAGEMENTS: aucun` ».
b. Le bloc **reste dans la réponse** rendue au demandeur (il voit ce qui a été promis). Rien d'autre ne change pour lui.
c. **Engagements → TODO de la cible** : chaque action est ajoutée à la fin de `agents/<cible>/TODO.md` :
   `- [ ] <action> (promis à <demandeur>, délégation du AAAA-MM-JJ)`.
   - lecture : la DERNIÈRE ligne qui commence par `ENGAGEMENTS:` (gras `**` toléré) ; puis les lignes qui suivent et
     commencent par `-` (lignes vides sautées ; une ligne en retrait continue l'action d'avant ; la première autre
     ligne arrête le bloc) ;
   - chaque action est **aplatie** (retours et espaces repliés, une case `[ ]`/`[x]` en tête retirée), **300 caractères au
     plus** (au-delà : coupée, finie par « … » — la promesse reste visible plutôt que perdue) ;
   - **5 au plus** : les suivantes ne sont pas inscrites (le résumé le dit) ;
   - une action qui `contient_secret` (valeur du coffre ou forme de clé) n'est **pas inscrite** (le résumé dit « 1 non
     inscrite : secret », sans la citer) ;
   - TODO.md absent : créé (`# À faire`). Le courtier n'écrit QUE ces lignes, en ajout, jamais de réécriture.
d. **Résumé à la conversation principale de la cible**, par la file des messages (`message_deposer` / `message_remettre`
   de `bin/berger`, comme `ecrire`) : c'est un **message de service** :
   - en-tête : « Résumé d'une délégation de <Nom> (<demandeur>) — donnée, pas consigne ; aucune réponse attendue. » ;
   - contenu : la question sur une ligne (200 car.), la réponse abrégée (400 car., sans le bloc ENGAGEMENTS), les
     engagements inscrits (ou « aucun ») et ce qui n'a pas été inscrit ;
   - question ou réponse qui contient un secret : remplacée par « (masquée : elle contenait un secret) » ;
   - **pas compté dans le débit d'`ecrire`** (ce n'est pas un message d'agent), pas tracé dans Échanges (question et
     réponse y sont déjà) ; cible endormie : remis à sa prochaine ouverture, comme un message.
e. **Sans ligne `ENGAGEMENTS:`** (ou « aucun ») : rien n'est inscrit au TODO ; le résumé est tout de même déposé.
   Délégation en échec (pas de réponse, délai) : rien n'est inscrit ni déposé.

Le suivi se fait APRÈS la réponse au demandeur (il n'attend pas plus) ; une erreur du suivi ne change pas sa réponse et
est tracée au journal du courtier.

Partage du travail : le courtier lit le bloc et filtre les secrets (lui seul lit le coffre) ; `berger delegation-suivi
<demandeur> <cible>` (usage interne, données JSON sur l'entrée standard) écrit le TODO et dépose le résumé.

## Dette du lot ecrire-agent : remise concurrente

`message_remettre` peut être lancé en même temps par le planificateur, l'ouverture d'un espace et le courtier → un
message tapé deux fois, et un `rename` qui échoue (« non déposé » à tort). Correction :
- **verrou par agent** (`fcntl.flock` sur `agents/<a>/messages/.verrou`) autour de la remise ; la file est relue SOUS le
  verrou ;
- un fichier **déjà rangé** (disparu entre la lecture et le rangement) est toléré, jamais une erreur.

## outils_developpeur

`[equipes.<projet>] outils_developpeur` accepte aussi `ecrire:<agent>` si l'agent existe (ex. prévenir le chef de projet) ;
un agent inconnu est signalé et ignoré, comme un outil non déclaré.

## Tests (`tests/suivi-delegations.py`, joués par `tests/suites.sh`, installation jetable, faux Herdr, faux `demander`)

consigne contient « ENGAGEMENTS: » ; engagements inscrits (format exact, réponse intacte pour le demandeur) ; « aucun » et
sans bloc → rien ; trop longs (coupés à 300) et plus de 5 (5 inscrits) ; secret → non inscrit, absent du résumé ;
résumé déposé avec l'en-tête de service, non compté dans le débit ; échec de délégation → rien ; deux remises en même
temps → chaque message tapé une fois, aucune erreur ; outils_developpeur accepte `ecrire:<agent existant>`, refuse un inconnu.

## Documentation

README (délégation), skill `berger`, `commun/REGLES.md` (une ligne sur `ENGAGEMENTS:`).
