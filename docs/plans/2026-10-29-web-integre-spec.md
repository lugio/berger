# Outils web intégrés du moteur refusés aux agents stricts (spec)

Règle de go : **cas 1** (mur d'un agent, droits, fuite possible de données). **Aucune ligne de code avant le go du
propriétaire, inscrit sur CE fichier**, même en local. Priorité : avant le lot 4d modulaire. Cette spec n'est que du texte.

## Constat (mesuré le 29/10 sur une installation réelle, et dans le code de `main`)

- Un agent Claude en mur **strict** (`defaultMode: bypassPermissions`, bac à sable réseau `deniedDomains: ["*"]`)
  utilise **sans refus** les outils intégrés **WebFetch** et **WebSearch** de Claude Code : un WebFetch d'un site public
  rend la page.
- Le bac à sable ne coupe le réseau que pour **Bash**. `reglages_claude` (`bin/berger`) ne met ni `WebFetch` ni
  `WebSearch` dans `permissions.deny`, et ces outils ne passent pas par le courtier : **rien n'est journalisé**.
- Conséquence : tout agent strict peut lire n'importe quel site, et **faire sortir des données dans l'URL ou la requête**
  (par exemple sur l'injection d'une page lue), hors du journal du courtier. Le mur réseau est contourné.
- Le contrat d'admission (`tests/contrat-moteur.py`, contrôle 1 : « outils vus = ceux du moteur seul ») ne l'a pas vu :
  ces outils SONT des outils du moteur.
- Codex : son outil de recherche web intégré (`web_search`, réglage du moteur) n'est pas réglé par Berger — son état par
  défaut dans la version installée est *à vérifier* ; il suit la même règle.

## Comportement prévu

1. **Refus par défaut.** Pour tout agent strict, `reglages_claude` ajoute `WebFetch` et `WebSearch` à
   `permissions.deny` ; les arguments du moteur Codex désactivent sa recherche web. Rien à écrire dans un `agent.conf`.
2. **Permission explicite, par agent.** Une ligne `web_integre = <domaine>, <domaine>… | recherche` dans l'`agent.conf`
   de l'agent (que l'agent ne peut pas réécrire, déjà refusé en écriture) lève le refus pour lui seul :
   - `WebFetch` est permis vers les seuls domaines listés (noms exacts, mêmes règles que les sites permis d'un projet :
     ni joker, ni IP, ni port) ; une **garde** `PreToolUse` refuse toute autre URL, et toute URL qui porte des
     identifiants ou une valeur du coffre ;
   - `recherche` permet `WebSearch` ;
   - chaque appel (agent, outil, domaine ou requête, heure, verdict) est **journalisé** dans `courtier/appels.log` par
     cette garde, permis ou refusé.
   Écrire ou modifier cette ligne est un changement de droits : **validation du propriétaire**, comme `outils =`.
3. **Le contrat moteur** gagne un contrôle (12) : pour un agent strict SANS `web_integre`, `WebFetch` et `WebSearch` sont
   **absents** des outils vus (événement init de Claude) et la recherche web de Codex est désactivée (source machine).
   Avec `web_integre`, une URL hors liste est refusée par la garde, et l'appel est au journal (faux site local, aucun
   site extérieur joint).
4. **Après l'installation** : `berger regenerer` réécrit les réglages de chaque agent ; le propriétaire relance les
   agents ouverts (leurs réglages actuels sont lus au démarrage).

## Refus nommés

WebFetch ou WebSearch sans `web_integre` ; domaine hors liste ; nom inexact (joker, IP, port) ; URL avec identifiants ou
valeur du coffre ; `web_integre` écrit par l'agent lui-même.

## Tests (rouges d'abord, sans réseau)

- Réglages générés : `WebFetch` et `WebSearch` dans `deny` d'un agent strict ; absents du `deny` (et garde présente)
  avec `web_integre` ; inchangés pour un agent non strict.
- Garde : domaine permis → accepté et journalisé ; hors liste, IP, identifiants, valeur factice du coffre → refusés et
  journalisés.
- Codex : la recherche web désactivée dans ses arguments.
- Contrat moteur (12), joué par le propriétaire sur les deux moteurs.

## Lots

1. Refus par défaut (Claude et Codex) + contrôle (12) du contrat — cas 1.
2. `web_integre` : garde, journal, validation — cas 1.
Une demande de fusion par lot. Le lot 1 ferme la fuite seul ; l'agent qui en a besoin attend le lot 2.
