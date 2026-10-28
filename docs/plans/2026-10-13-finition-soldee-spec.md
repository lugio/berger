# Finition soldée et relance après application — spec courte

## Constat (mesuré le 13/10 au soir sur un chef de projet)
1. **Relance fausse.** Le chef finit un sujet par SA branche `<sujet>-fin` (sujet différent de celui du développeur), fusionnée
   puis étiquetée. La demande « à finir » du développeur reste « à finir » : la supervision répète « livrée à finir depuis… »
   toutes les ~15 min, et le chef y répond (messages `ecrire`) jusqu'à saturer sa limite de débit (5/h), qui refuse ensuite ses vrais envois.
   **Cause racine** : rien ne reliait la fusion d'une branche de finition aux livraisons qu'elle reprend (`reprise_a_finir` ne
   reconnaît que le même sujet, donc la même branche).
2. **Proposition appliquée non prise.** Après `agent appliquer`, l'agent garde l'ancienne version jusqu'à une relance que personne ne demande.

## Comportement
- Une livraison « à finir » est *reprise* par une demande de finition si son `origine` la désigne ou si son commit livré est dans
  la branche de finition. Dès la demande : `reprise_par: <branche>` (la supervision ne rappelle plus). À la **fusion** : la livraison
  passe à `fusionnée`, `fusion: par la finition <branche>`, `soldee_par`. Une livraison non reprise reste « à finir ».
- **Rattrapage** (14/10 : une livraison dont la finition avait été fusionnée AVANT ce correctif, sans `reprise_par`, rappelée 65 fois) :
  avant de rappeler, `relancer_attentes()` appelle `equipe_chef.solder_deja_finies()`, qui rejoue pour chaque finition déjà fusionnée
  le MÊME test (`livraisons_reprises`) et le MÊME solde (`solder_livraisons`) qu'à la fusion ; une ligne au journal du chef ; rien
  n'est soldé deux fois (une livraison soldée n'est plus « à finir »). Dépôt illisible : rien n'est soldé, la relance reste.
- Les relances de la supervision passent par `berger parler`, jamais par le compteur d'`ecrire` (ni émetteur ni cible) : testé.
- Après `agent appliquer` (modification) : agent **au repos** (même source d'état que `berger relancer`) → relancé aussitôt ;
  **occupé** → `.relance-en-attente` dans son dossier, relance faite par la supervision dès qu'il est au repos, dite dans le
  message de décision ; toute relance réussie lève l'inscription (rien n'est rejoué) ; pas d'agent ouvert → rien à faire.

## Refus / limites
Aucune relance forcée d'un agent qui travaille. Aucun nom de projet ou d'agent dans le code.

## Tests
`tests/finition-soldee.py` (branché dans `tests/suites.sh`) : reprise puis fusion, livraison non reprise intacte, supervision sans
relance après reprise ou solde, débit d'`ecrire` intact après 9 relances, agent au repos / occupé / relance manuelle / sans panneau ; rattrapage d'une finition fusionnée avant le correctif (soldée au premier
passage, jamais rappelée, non reprise toujours rappelée, rien soldé deux fois).
