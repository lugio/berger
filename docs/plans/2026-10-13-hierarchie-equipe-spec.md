# Hiérarchie d'équipe générique — coordinateur → chef de projet → développeurs

Spec courte, 13/10/2026 (mission de master ; cible décidée par le propriétaire le 13/10). Touche des **droits** (règle de
go, cas 1) : la cible est la décision du propriétaire ; la fusion reste validée par lui seul (`fusion_par` du projet berger).

## Constat

- Le **coordinateur** (droit `equipe:<projet>` écrit à la main dans son `agent.conf`) ouvre et ferme les développeurs ;
  le **chef de projet** ne voit leur travail qu'à la demande de fusion.
- Les alertes de la supervision (blocage, `sans_avancee_min`, `max_renvois`, « fusionnée mais encore ouvert ») vont au
  coordinateur.
- Mesuré en réel le 13/10 : le coordinateur d'un projet a été **refusé** pour écrire au chef (pas de `ecrire:<chef>`) ;
  le chef n'a **aucun droit** pour écrire à un développeur, le suivre ou le relancer. Ajout manuel provisoire.
- Confier une mission à un agent **déjà vivant** (le chef) depuis un espace ouvert lançait une **seconde** instance
  dans l'onglet Missions de celui qui confie ; la terminer **fermait l'espace** de l'agent (pour un chef : l'onglet
  Équipe et ses développeurs avec).

## Comportement

Tout vient de `[equipes.<projet>]` (`coordinateur`, `chef_projet`) et de l'`agent.conf` des développeurs
(`projet`, `sujet`). Aucun nom de projet ni d'agent dans le code. Les **droits d'équipe** sont calculés par le courtier
à chaque appel, en plus de ceux de `outils =` ; rien à écrire dans un `agent.conf`.

| Qui | Reçoit d'office, pour SON projet seulement |
|---|---|
| chef de projet | `equipe ouvrir / fermer / liste <projet>` ; `<projet>-chef` ; `ecrire:` et `mission confier/suivi/rapport/terminer` vers chaque développeur du projet (y compris ceux ouverts avant la bascule) ; `ecrire:` vers le coordinateur (escalade) |
| coordinateur | `equipe liste <projet>` (lecture de l'état : développeurs, état de leur demande de fusion, portes, renvois, blocage) ; `equipe domaine(s)` (inchangé) ; `ecrire:` et `mission confier/suivi/rapport/terminer` vers le chef de projet |
| développeur | `ecrire:` vers son chef de projet (rendre compte) |

- **Ouvrir / fermer** un développeur : le chef de projet seul (ou le propriétaire en ligne de commande). Le coordinateur
  qui n'est pas aussi chef est refusé (courtier ET `berger equipe ouvrir|fermer --par`).
- **Source de vérité** : `coordinateur` et `chef_projet` de `[equipes.<projet>]` font foi, seuls. `equipe:<projet>` écrit
  dans un `agent.conf` ne donne **aucun** droit d'équipe : pour le coordinateur déclaré, il est simplement inutile ; pour
  un agent qui n'est PAS le coordinateur déclaré, il est ignoré et `equipe liste <projet>` porte une ligne
  d'avertissement (`{"avertissement": "<agent> déclare equipe:<projet> sans être le coordinateur déclaré : ignoré, à retirer"}`).
  Recommandation : retirer ces lignes des `agent.conf` (proposition d'agent, validée par le propriétaire).
- **Relancer** un développeur = lui écrire (`berger-outil ecrire <développeur> --fichier .transport/requete.json` (paramètres JSON, dans l’ordre : `"…"`)) ; une session arrêtée est déjà
  rouverte par la supervision.
- **Le coordinateur confie un SUJET au chef** : `berger-outil mission confier --fichier .transport/requete.json` (paramètres JSON, dans l’ordre : `<chef> "<spec courte + go>"`). Le chef vit
  déjà : la mission lui est **dite**, pas rouverte ailleurs ; elle ne prend **pas de place** dans `[missions] max`
  (aucun moteur de plus) ; la terminer range `MISSION.md` **sans fermer** l'espace du chef. Corrigé pour tout agent
  déjà vivant (jamais de seconde instance).
- **Alertes** : celui qui répond d'un développeur est son **chef de projet** (à défaut, le coordinateur). Chaîne :
  développeur → chef → coordinateur → propriétaire.
  - blocage (« ⚠ Bloqué ») : chef aussitôt ; toujours là après `escalade_min` → coordinateur (s'il est un autre agent) ;
    encore `escalade_min` plus tard → propriétaire ;
  - rien n'avance : développeur relancé, puis (×2) chef, puis (×3) coordinateur s'il est un autre agent ;
  - `max_renvois` : N renvois → chef ; N+1 → coordinateur (s'il est un autre agent) ; N+2 → propriétaire ;
  - fusionnée, développeur encore ouvert → le chef (c'est lui qui ferme).
- **coordinateur = chef_projet** (cas de berger) : un seul agent, les deux rôles ; chaque alerte une seule fois.

## Sources

Déjà relues pour le processus de développement (tableau de `docs/plans/2026-10-12-processus-dev-generique-spec.md`) :
- Google Engineering Practices, « The Standard of Code Review » : le relecteur (ici le chef de projet, qui suit ses
  développeurs et relit leurs demandes) est responsable de la santé du code qui entre ;
- GitHub, « About protected branches » (relecture obligatoire avant fusion, jamais le demandeur seul) ; GitHub flow ;
- Fowler, « Patterns for Managing Source Code Branches » (« Integration Frequency » : petits sujets courts, intégrés souvent —
  le coordinateur découpe en sujets, le chef les fait aboutir) ;
- NIST SP 800-218 (SSDF 1.1) **PO.1** (le processus écrit et tenu à jour : qui ouvre, qui suit, qui valide).

Cités de mémoire, **non revérifiés ici** (l'agent n'a pas d'accès Internet) — à confirmer avant de les reprendre ailleurs :
- SSDF **PO.2** (rôles et responsabilités définis) ;
- moindre privilège, NIST SP 800-53 **AC-6** : chaque rôle ne reçoit que ce que son travail demande, sur SON projet.

## Transition sans interruption

Rien à migrer : les droits sont calculés à chaque appel, les alertes relisent la configuration à chaque passage. Après
l'installation (courtier redémarré, `berger regenerer`), un développeur déjà ouvert (ex. ouvert par l'ancien coordinateur)
n'est **ni fermé ni relancé** ; son chef le voit (`equipe liste`), le suit, lui écrit, le ferme ; ses alertes vont au
chef ; ses consignes régénérées disent « ton chef de projet ». L'ajout manuel provisoire (`ecrire:<chef>` d'un
coordinateur) devient inutile : à retirer ensuite (proposé au propriétaire par master).

## Finition par le chef (`finition` de `[equipes.<projet>]`)

**Constat** (mesuré en réel le 13/10) : la porte `pret` d'un projet peut exiger version + `CHANGELOG.md` alors que les
règles de ce projet réservent cette finition au chef ; le développeur ne peut alors jamais demander la fusion.

**Réglage** : `finition = "developpeur"` (défaut : rien ne change) ou `"chef"`.

**finition = chef** — pas de mécanisme parallèle, le même verbe et le même fichier de demande :
- le développeur lance `demander-fusion "<résumé>"` comme d'habitude : mêmes contrôles (propre, poussée, à jour, règle
  du correctif), **sans** exiger ni jouer `pret` ; `verify`, `tests` (et `gate` si déclarée) jouées, une rouge = refus.
  La demande est inscrite avec l'état **« à finir »** (au lieu de « à relire ») : il a **livré** sa branche à son chef,
  qui est prévenu (et relancé par la supervision tant qu'elle attend) ;
- le chef crée SA branche de finition depuis celle du développeur (`git switch -c <prefixe><sujet> origin/<branche du
  développeur>` dans son dépôt), fait la finition, puis `pousser` et `demander-fusion` de son outil (lot chef-finition) :
  `pret` jouée et verte. Sa demande **remplace** celle « à finir » du même sujet (même `demandes/<sujet>.json`) SEULEMENT
  si : la demande existante est « à finir », dans le même projet (même dossier de demandes), et la branche du chef
  **contient** le commit livré par le développeur (`git merge-base --is-ancestor`). Sinon, le refus actuel reste
  (« renomme ta branche »). La demande remplacée garde la trace du développeur (`origine` : agent, branche, commit, date).
  Sa fusion est validée par le propriétaire seul (règle du lot chef-finition) ;
- `fusionner` refuse une demande « à finir » (`pret` jamais jouée).

## Refus

- coordinateur (non chef) : `equipe ouvrir|fermer` refusé ; vers un développeur : `ecrire` / `mission` refusés.
- chef ou coordinateur d'un projet : rien vers les agents d'un AUTRE projet.
- développeur : `ecrire` vers un autre que son chef refusé (sauf droit déclaré).
- `lecture_seule = oui` : tout reste refusé comme avant (les droits d'équipe ne passent pas outre).

## fusion_par : options (décision du propriétaire en attente — RIEN ne change ici)

Règle commune : **jamais le demandeur** ne valide sa propre demande (le courtier rend la décision au propriétaire).

| Valideur | Avantages | Risques |
|---|---|---|
| **propriétaire** (actuel pour berger) | contrôle humain de chaque entrée dans `main` ; obligatoire quand l'équipe corrige ses propres murs (berger) | goulot : tout attend sa disponibilité ; relances nocturnes |
| **coordinateur** (défaut sans `fusion_par`) | décide au niveau des projets, sans attendre ; distinct du chef qui demande | si coordinateur = chef (berger), la règle « jamais le demandeur » renvoie au propriétaire ; un agent valide le code d'un autre agent sans humain |
| **chef_projet** | rapide | le chef DEMANDE la fusion : il serait juge de sa propre demande → toujours renvoyé au propriétaire ; option sans effet réel |

Recommandation : propriétaire pour berger (murs des agents) ; coordinateur ailleurs quand coordinateur ≠ chef.

## Tests (`tests/hierarchie-equipe.py`, joués par `tests/suites.sh`, installation jetable, faux Herdr, courtier appelé directement)

chef ouvre (refus coordinateur, refus `--par` coordinateur en ligne de commande) ; coordinateur lit `liste`
(demandes, portes) ; coordinateur → chef : `ecrire` sans droit déclaré, `equipe:<projet>` déclaré par un non-coordinateur → aucun droit et
avertissement dans `liste`, `mission suivi` ; rien vers le chef d'un autre
projet ; chef → développeur existant (ouvert « avant », sans aucun droit écrit) : `ecrire`, `mission suivi` ; rien vers
le développeur d'un autre projet ; coordinateur → développeur refusé ; développeur → son chef permis, → coordinateur
refusé ; lecture seule respectée ; supervision : blocage → chef puis coordinateur puis propriétaire, rien n'avance → chef,
renvois → chef puis coordinateur, fusionnée → chef ; coordinateur = chef : une alerte ; transition : `regenerer` ne ferme
ni ne relance le développeur, ses consignes nomment son chef ; mission au chef vivant : pas de seconde instance, hors
`max`, fin sans fermer son espace.

## Documentation

`commun/modeles/equipe-processus.md`, `equipe-coordinateur.md`, `equipe-chef-de-projet.md`, `equipe-developpeur.md`,
`commun/REGLES.md`, skill `berger`, `config.exemple.toml`, README.

Tests de la finition (`tests/hierarchie-equipe.py`) : finition = chef → demande sans `pret` (porte `pret` rouge ignorée),
état « à finir », chef prévenu ; `tests` rouge → refus ; le chef reprend la branche et sa demande remplace « à finir »
en gardant `origine` ; refus si la branche du chef ne contient pas le commit livré, ou si la demande existante n'est pas
« à finir » ;
`fusionner` d'une demande « à finir » refusé ; finition = developpeur : `pret` exigée comme avant (suites existantes).
