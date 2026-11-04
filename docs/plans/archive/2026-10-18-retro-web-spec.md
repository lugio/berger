# Rétro : analyse web en direct par REA (voie B) — mini-spec

Statut : **proposition, rien codé**. Ce texte intègre les retours du propriétaire du 18/10 : durée réglable, session prêtée, passage de relais et juridique. Le mur n'est pas modifié.

## Constat et cas d'usage

`[mcp.rea]` a `reseau = false` : l'enveloppe bwrap de REA tourne avec `--unshare-net`. Les outils web de REA (`capture_browser_scenario`, `inspect_web_page`, `observe_web_session`…) ne peuvent donc ouvrir aucun site. Mettre `reseau = true` ouvrirait tout Internet à un processus qui lit des échantillons hostiles : c'est refusé.

Exemple : s'inspirer d'un SaaS où le propriétaire a un compte pour concevoir un module applicatif.
- Rétro observe le SaaS et décrit ce qu'il voit.
- Le développeur de l’application code à partir de cette description.
- Rétro n'a jamais le dépôt, et le développeur n'a jamais le SaaS.

## Conception

### 1. Accès à un domaine (sans compte)

1. **Demande.** Rétro lance `berger-outil web demander --fichier .transport/requete.json` (paramètres JSON, dans l’ordre : `<domaine> "<motif>" [durée]`).
   - Le domaine doit être un nom exact, avec la règle `DOMAINE` de `equipes/<p>/domaines` : pas de joker, pas d'IP, pas de `localhost`.
   - Un domaine par demande, et un seul accès ouvert à la fois au départ.
2. **Validation.** Le courtier crée la demande avec `demander_validation`, et elle s'affiche dans l'onglet Décisions.
   - **La durée se règle dans la validation** : 2 h par défaut, et jusqu'à une journée (24 h) si le propriétaire l'écrit lui-même, par exemple `berger valider <n> --duree 8h`.
   - **Prolongation** : `berger-outil web prolonger --fichier .transport/requete.json` (paramètres JSON, dans l’ordre : `<domaine> <durée>`) crée une nouvelle validation. Un simple go suffit, avec le même plafond d'une journée par go.
   - Une demande sans réponse expire, et un agent strict ne peut pas valider sa propre demande (règle actuelle).
3. **Ouverture.** Le courtier lance un **proxy à liste blanche**, un par accès, hors de l'enveloppe.
   - Le proxy écoute sur un socket UNIX propre à l'accès : `courtier/mcp/<agent>-web.sock`.
   - Dans l'enveloppe, `--unshare-net` est **gardé**. Un `socat` relie `127.0.0.1:3128` (boucle locale de l'enveloppe) à ce socket.
   - Il n'y a pas de résolution DNS dans l'enveloppe : c'est le proxy qui résout.
   - REA n'a pas d'option proxy. `REA_BROWSER_EXECUTABLE` pointe donc sur une **enveloppe de lancement** écrite par Berger. Elle ajoute à Chromium `--proxy-server=http://127.0.0.1:3128` et l'empreinte du certificat de l'accès (point 4).
4. **Le proxy déchiffre le domaine accordé, et seulement lui.** Sans déchiffrement, il ne voit pas les méthodes HTTPS et ne peut donc pas bloquer POST. La v1 de cette spec l'affirmait à tort.
   - Pour chaque accès, le courtier crée une clé et un certificat éphémères pour `<domaine>` (Python `cryptography`, présent sur la machine).
   - Le Chromium de Rétro ne fait confiance qu'à ce certificat (`--ignore-certificate-errors-spki-list=<empreinte>`). Aucune autorité n'est installée dans le système.
   - Le proxy refuse et journalise :
     - un autre nom, une IP directe, une redirection vers un autre hôte ;
     - une adresse privée ou locale **après résolution** (RFC 1918, 127/8, 169.254/16, ::1, fc00::/7), contre le DNS rebinding ;
     - un corps montant de plus de 64 Ko ;
     - les méthodes hors GET et HEAD, **par défaut**. POST est permis seulement si la validation le dit, et jamais en session prêtée.
5. **Journal et fin.**
   - Chaque requête est journalisée (`web:<domaine>`) : méthode, chemin sans paramètres, octets, permis ou refusé.
   - À l'échéance, le proxy est arrêté, le socket et la clé sont supprimés, et la ligne « accès fermé » est écrite.
   - Le propriétaire peut fermer avant l'échéance : `berger web fermer <agent>`.
6. **Navigateur.** Le Chromium headless de REA (Playwright `chromium_headless_shell-1234`) tourne dans la même enveloppe.
   - Son profil va dans `{agent}/analyses/web-<date>/`, avec l'écriture limitée habituelle.

### 2. Session prêtée (un SaaS où le propriétaire a un compte)

1. **Demande.** Rétro lance `berger-outil web demander --fichier .transport/requete.json` (paramètres JSON, dans l’ordre : `<domaine> "<motif>" --session`). La validation dit : « prêter ta session <domaine>, en lecture seule, pour <durée> ».
2. **Capture, par le propriétaire lui-même.** `berger web connecter <domaine>` ouvre chez le propriétaire un Chromium **visible**, lancé par le courtier.
   - Ce navigateur a un profil neuf et passe par le même proxy, limité au domaine.
   - Le propriétaire s'y connecte (identifiant, mot de passe, 2FA) et ferme la fenêtre. Rétro ne voit jamais cette fenêtre, et rien de ce que le propriétaire tape ne passe par l'agent.
   - Le courtier relève alors les **cookies du domaine** et le stockage local (`storageState` de Playwright). Il les écrit **dans le coffre**, en entrée datée `web-session:<domaine>`, puis efface le profil temporaire.
   - Le coffre reste masqué à l'agent, comme aujourd'hui, et la sauvegarde chiffrée habituelle s'applique.
3. **Prêt en lecture seule.**
   - **Le cookie n'entre pas dans l'enveloppe.** C'est le proxy du courtier qui l'ajoute, en en-tête `Cookie:`, aux seules requêtes GET et HEAD vers le domaine.
   - Il retire les `Set-Cookie` des réponses : le navigateur de Rétro n'a jamais de cookie de session.
   - POST, PUT, PATCH et DELETE sont **toujours** refusés et journalisés en session prêtée, quelle que soit la validation.
   - La durée est bornée (même règle que plus haut), et chaque requête est journalisée.
   - À la fin, l'entrée du coffre est **effacée**, et la note de fin demande au propriétaire de se déconnecter ou de révoquer la session côté SaaS.
4. **Risque résiduel.**
   - **Jeton dans la page.** Beaucoup de SaaS (applications d'une seule page) gardent un jeton d'API dans le stockage local ou dans une réponse JSON. Ce jeton est alors **visible du navigateur dans l'enveloppe**, donc de REA et de Rétro.
     - Ce qu'on en fait : ce jeton n'est pas injecté dans le navigateur. S'il apparaît dans une réponse, il est utilisable seulement à travers le proxy, donc en GET seulement, vers ce seul domaine et jusqu'à l'échéance.
     - Le filtre du courtier ajoute la valeur du cookie et les jetons connus de la session à ses valeurs à masquer dans les réponses MCP : ils n'arrivent jamais dans le texte de Rétro, ni dans `analyses/`.
     - Un jeton qui fuit malgré tout reste valable côté SaaS jusqu'à la révocation par le propriétaire. C'est pourquoi la note de fin demande la déconnexion.
   - **GET qui écrit.** Certains sites changent un état par GET (lien « marquer comme lu », export). Le proxy ne peut pas le savoir. On le borne en refusant les chemins qui contiennent `logout`, `delete`, `export`, `settings`, `payment`…, avec une liste réglable. Le reste est un risque accepté.
   - **Site inutilisable en lecture seule.** Une API qui lit par POST (GraphQL par exemple) ne s'affichera pas. Rétro le note dans son rapport, et c'est au propriétaire de décider d'une suite éventuelle.
   - **Compte réel.** Ce sont les données du propriétaire, ou de ses clients, qui s'affichent. Le rapport de Rétro ne recopie aucune donnée réelle : il décrit des champs et des parcours, avec des exemples inventés.

### 3. Passage de relais : Rétro → développeur du projet

1. Rétro écrit `{agent}/analyses/<domaine>-<date>/rapport.md`. Il contient :
   - les fonctions et les parcours ;
   - les écrans, décrits et non copiés ;
   - les champs et leurs règles ;
   - l'API **publique et documentée**, s'il y en a une ;
   - ce qui n'a pas pu être vu.
2. Rétro lance `berger-outil web remettre --fichier .transport/requete.json` (paramètres JSON, dans l’ordre : `<projet> <rapport>`).
   - Le courtier contrôle le rapport : filtre des secrets, et aucune valeur de la session.
   - Il crée une validation.
   - Sur go du propriétaire, il dépose le rapport dans la bibliothèque du projet et **confie la mission au chef de projet de l'équipe**, qui ouvre le développeur. C'est la chaîne actuelle : on ne passe pas directement au développeur.
3. Le développeur code depuis le rapport. Il n'a ni le domaine, ni la session, ni REA. Rétro n'a ni le dépôt ni l'équipe. Une question du développeur remonte par le chef, puis le coordinateur, puis le propriétaire, qui peut redemander une observation à Rétro.

## Ce qui change dans le mur

Seulement pendant un accès accordé :
- un second socket monté dans l'enveloppe ;
- l'enveloppe de lancement de Chromium ;
- un certificat éphémère.

Le reste ne bouge pas : `--unshare-net`, le coffre masqué, l'écriture limitée, le filtre des secrets sur les réponses MCP.

Le **contrat d'admission** gagne cinq conditions :
- (7) sans accès accordé, aucune sortie ;
- (8) avec un accès, un autre domaine, une IP directe ou une adresse privée sont refusés et journalisés ;
- (9) le coffre reste illisible depuis le navigateur, `file://` compris ;
- (10) en session prêtée, POST et DELETE sont refusés, et aucun cookie de session n'est lisible dans l'enveloppe ;
- (11) à l'échéance, l'entrée `web-session:` du coffre a disparu.

## Juridique

- **Permis :** s'inspirer des fonctions, des parcours et de l'organisation d'un logiciel. Les idées et les fonctionnalités ne sont pas protégées par le droit d'auteur.
- **Interdit :**
  - recopier le code, même celui du navigateur (JS, CSS) ;
  - recopier les textes, les libellés originaux, la documentation ;
  - recopier les visuels : logos, icônes, maquettes, captures reprises telles quelles ;
  - extraire une base de données en masse.
- **Dans le rapport de Rétro :** des descriptions écrites par lui, et des captures seulement pour l'analyse interne, jamais versées au dépôt de l’application.
- **À vérifier avant chaque SaaS, par le propriétaire :** les CGU. Beaucoup interdisent l'accès automatisé, le scraping ou la rétro-ingénierie, même avec son propre compte. Un accès refusé par les CGU n'est pas demandé.
  - La validation affiche un rappel : « CGU de <domaine> vérifiées ? ».
- Je ne suis pas juriste. Pour un module vendu, un avis juridique sur le SaaS visé est prudent.

## Tests (avant le code)

- **Proxy :**
  - nom permis, autre nom, IP, adresse privée après résolution, redirection, corps trop gros, méthode refusée ;
  - certificat éphémère accepté par la seule empreinte attendue ;
  - chaque cas est journalisé.
- **Cycle de l'accès :**
  - demande, puis validation avec une durée, puis ouverture, prolongation, échéance et fermeture ;
  - refus et expiration : rien n'est ouvert ;
  - auto-validation : refusée ;
  - durée de plus de 24 h : refusée.
- **Session prêtée**, avec un faux site local à connexion :
  - le cookie est ajouté au GET ;
  - POST est refusé ;
  - `Set-Cookie` est retiré ;
  - aucun cookie n'est lisible dans le profil du navigateur de l'enveloppe ;
  - les valeurs de la session sont masquées dans les réponses MCP ;
  - l'entrée du coffre est effacée à la fin.
- **Relais :**
  - un rapport qui contient une valeur de la session : refusé ;
  - un rapport validé : déposé chez le projet, et la mission va au chef.
- **Contrat** (7) à (11), sous les deux moteurs, et un essai réel REA sur un faux site.

## Estimation

| Partie | Heures |
|---|---|
| Proxy à liste blanche avec déchiffrement du seul domaine (Python, `cryptography`), et ses tests | 4–5 |
| Verbes `web demander / prolonger / fermer`, durée dans la validation, échéance, journal | 3 |
| Enveloppe (second socket, socat, lancement de Chromium) dans `_mcp.py`, génération | 2 |
| Session prêtée : `web connecter` (navigateur visible chez le propriétaire), coffre, injection, masquage, effacement | 4–5 |
| Relais `web remettre` (contrôle, validation, dépôt, mission au chef) | 1–2 |
| Contrat (7) à (11), essai réel REA, doc, marge | 3 |
| **Total** | **≈ 17–20 h** |

La découpe se fait en trois demandes de fusion :
- le proxy et le cycle ;
- l'enveloppe et le contrat (7) à (9) ;
- la session prêtée et le relais, avec (10) et (11).

La session prêtée coûte plutôt **+5–6 h que +3–4 h**. En effet, le blocage de POST impose de déchiffrer le domaine. C'est utile aussi sans session, mais une partie de ce surcoût lui revient.

Le sujet touche aux droits, à la gestion des secrets (le coffre) et à des appels extérieurs : il relève de la règle de go. Il faut donc un go du propriétaire avant le code, et un go à chaque fusion.

## Hors périmètre

- Plusieurs domaines à la fois, et les jokers.
- L'écriture dans un SaaS, même validée.
- La connexion automatique par identifiant : seul le propriétaire se connecte.
- L'accès web pour d'autres agents que Rétro.
- Electron, les applications natives, le réseau pour Ghidra et jadx.
- Le contournement d'une protection anti-robot ou d'un captcha : si le SaaS bloque, on s'arrête.

## Mesures (18/10)

- **Navigateurs sur la machine :** `/usr/bin/chromium`, `/usr/bin/firefox` et Playwright `chromium-1234` / `chromium_headless_shell-1234`.
- **REA :** utilise `playwright-core` 1.58.2 (un seul `chromium.launch` et un seul `launchPersistentContext`). Il accepte `REA_BROWSER_EXECUTABLE` et `REA_BROWSER_NO_SANDBOX`, et **n'a pas d'option proxy**, d'où l'enveloppe de lancement.
- **Outils présents :** `socat`, `openssl`, Python `cryptography` 50.0.2. Absents : `mitmproxy` et `tinyproxy`. Le proxy sera écrit en Python.
- **Chromium headless derrière le proxy dans bwrap `--unshare-net` : mesuré par le propriétaire le 18/10** (`travail/retro-web/mesure.sh`, local seulement). Les variables `http_proxy` et `--proxy-server` donnent des résultats identiques :
  - `permis.test` : page reçue (PERMIS-OK) ;
  - `interdit.test` et `93.184.215.14` : rien reçu, REFUSÉ au journal du proxy ;
  - `127.0.0.1:18765` : rien reçu, et aucune ligne au proxy. Chromium contourne le proxy pour la boucle locale, mais la boucle de l'enveloppe `--unshare-net` est vide : un service local de l'hôte reste injoignable.
  - Conséquences pour le code :
    - le point 3 tient ;
    - l'enveloppe de lancement passe `--proxy-server` (explicite, plutôt que de dépendre des variables) ;
    - le contrat (8) vérifie aussi que la boucle locale de l'hôte reste injoignable.

## Précision de sécurité — méthodes et effets côté site

Le proxy refuse `X-HTTP-Method-Override`, `X-HTTP-Method`, `X-Method-Override` et
le paramètre `_method` avant injection du Cookie et connexion amont. La politique
des chemins sensibles couvre aussi la query (`?action=delete`, par exemple).
La « lecture seule » reste dépendante du site : un GET qui écrit reste possible
sur une route dont la sémantique n'est pas connue du proxy. GET/HEAD et les refus
explicites réduisent les voies d'écriture ; ils ne prouvent pas l'absence d'effets
pour chaque route autorisée. Ce point fait partie de la validation propriétaire.
