# Contexte propre à chaque appel du courtier

Spec courte, 12/10/2026 (mission de master, correction urgente).

## Constat

`equipes/berger/demandes/*.json` portaient le MAUVAIS agent (`sql-base-chemin.json` → `berger-domaines-projet`, et
inversement) : les renvois du chef de projet partaient au mauvais développeur.

## Cause

Le courtier traite chaque demande dans son propre fil (`traiter_a_part`). Mais `contexte(outil, agent)` écrivait
`o.contexte` sur l'OBJET OUTIL, unique et partagé par tous les fils. Un appel long (`demander-fusion` : fetch, verify de
plusieurs minutes) relisait `self.contexte` (ou `self.valeurs()`, qui le lit) bien après qu'un autre agent l'avait
réécrit. Même risque pour tout outil qui lit `self.contexte` : `copie`/`equipe_dev` (valeurs de la copie : `{copie}`,
`{branche}`… → commandes lancées dans la copie d'un AUTRE développeur), `_commandes` (`{agent}`), `scripts`
(`BERGER_AGENT`), `projets` (qui demande), `nextcloud` et `pages_publiques` (dossier de l'agent), `SitesPermis` du courtier.
Les panneaux (`collecter`, chacun dans son fil) posaient aussi `o.contexte` sur l'objet partagé.

## Correction

Le contexte appartient à l'APPEL (au fil qui le traite), plus à l'objet :

- Un descripteur commun `courtier/outils/_contexte.py` (`ContexteDeLAppel(defaut)`) : `o.contexte = …` range la valeur
  dans un `threading.local` propre à l'objet ; `o.contexte` rend la valeur posée DANS CE FIL, sinon la valeur par défaut
  de l'outil (`{}` ou `None`, comme avant). Chaque demande a son fil neuf : rien ne passe d'une demande à l'autre.
- Chaque outil qui avait `contexte` le déclare au niveau de la classe : `contexte = _contexte.ContexteDeLAppel({})`
  (au lieu de `self.contexte = {}` dans `__init__`, ou de l'attribut de classe `contexte = None`).
- Le courtier ne change pas de forme : `contexte(outil, agent)` (demandes, aperçus et exécutions de validations) et
  `collecter` (panneaux) posent toujours `o.contexte = …`, désormais propre au fil appelant.
- Les outils sans contexte (`equipe_chef`, `dolibarr`, `github`, `imap`, `ssh`, `sql_lecture`, `essai`) ne changent pas
  (le courtier ne leur pose rien, comme avant).

Aucun comportement visible ne change : mêmes verbes, mêmes valeurs par défaut, même affectation `o.contexte = …`
(les tests existants qui la posent à la main continuent de fonctionner).

## Hors de cette correction

`deleguer` et `message_*` / `ecrire` (autre développeur). Ils ne lisent pas `o.contexte`.

## Tests (`tests/contexte-appel.py`, dans `tests/suites.sh`)

1. Avec le VRAI courtier (installation jetable, équipe `p`, deux développeurs, deux copies, verify lent) : deux
   `demander-fusion` concurrents → chaque demande (`demandes/<sujet>.json`) porte SON agent, et chaque verify a tourné
   dans SA copie. Échoue avant la correction (l'agent de la demande est celui du dernier appel).
2. Pour chaque outil qui a un `contexte` (découverts par grep, pour qu'un nouvel outil ne soit pas oublié) : deux fils
   posent chacun leur contexte ; chacun relit le sien après que l'autre a écrit. Un fil qui n'a rien posé voit la valeur
   par défaut, jamais le contexte d'un autre.
3. Panneau : la collecte (« panneau:<nom> ») ne change pas le contexte d'une demande en cours dans un autre fil.
