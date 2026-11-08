# Interface web v2 : page « Réglages » en lecture seule — spec courte (05/11/2026)

Règle de go : cas 1, secret visible. La page montre `config.toml`, qui nomme le coffre, les hôtes et les noms de clés des
outils : l'affichage doit garantir qu'aucune de ces valeurs ne sort. Demande du propriétaire du 05/11. Lecture seule : la
modification depuis le web est un lot séparé, plus tard, sur un go à part.

## Place dans la suite

Après le petit lot « logo et QA », et **après le lot 3** (« Conversation », go n° 166) :
- le lot 3 a déjà son développeur, sur les mêmes fichiers (`bin/page/`, `bin/interface.py`) ; deux développeurs sur les mêmes
  fichiers en même temps sont exclus, et l'interrompre bloquerait plus qu'attendre ;
- la page signale les réglages que le lot 3 introduit (`[interface] transcription`, micro grisé) : elle les montre complets
  une fois le lot 3 installé.

Si le propriétaire veut la page plus tôt, elle passe entre deux étapes du lot 3, par le même développeur, en demande à part.

## Comportement

- **Un onglet « Réglages »**, en lecture seule, dans le groupe des pages de l'installation.
- **Par sections**, dans l'ordre du fichier : propriétaire et généralités, interface, équipes, outils, panneaux, missions,
  skills, mcp, tests, gardes, sauvegarde, et toute autre section présente.
  - Chaque réglage montre sa clé, sa valeur (ou « [masqué] ») et **une phrase simple** quand le réglage est connu
    (catalogue tenu côté serveur, à côté du lecteur). Un réglage inconnu du catalogue est affiché « réglage non décrit ».
  - Une section répétée (`[[gardes]]`) ou une famille (`[outils.<nom>]`) montre une carte par entrée.
- **Rien de secret ni de sensible** n'est affiché. Le serveur décide, jamais le navigateur :
  1. **liste fermée de clés masquées**, quelle que soit la section : `coffre`, `cle`, `cle_fichier`, `utilisateur_cle`,
     `mot_de_passe_cle`, `port_cle`, `hote`, `hotes`, `ip_secours`, `webdav`, `adresse`, `sources`, `marques_privees`,
     `masques`, `masques_si_presents`, `masque_fichier`, `chemins_bloques`, `entete_appelant`, et toute clé dont le nom
     contient `cle`, `secret`, `jeton`, `token`, `pass`, `mot_de_passe`, `hote`, `ip` ou `url` ;
  2. **toute valeur restante** passe par `MOTIFS_CLES` (`courtier/_secrets.py`) : une forme de clé devient « [masqué] » ;
  3. **une liste** est masquée si l'un de ses éléments l'est ; **une table** est parcourue clé par clé ;
  4. le **coffre n'est jamais lu**, même pour dire s'il existe.
  Le masquage a lieu AVANT la sérialisation : la valeur masquée n'est jamais dans la réponse HTTP, ni dans le journal.
- **Aucune écriture** : aucune route en écriture, aucun bouton qui modifie. En tête de page : « Ces réglages se changent dans
  ~/berger/config.toml » (chemin affiché tel quel ; c'est le seul chemin montré).
- **Ce qui manque ou est invalide** est signalé, avec sa conséquence en clair :
  - `[interface] transcription` absent ou non exécutable → « micro grisé dans Conversation » ;
  - `[interface] actions` absent → « décisions en lecture seule dans la page » ;
  - un outil déclaré sans son fichier dans `courtier/outils/`, une équipe sans `depot` lisible ;
  - un fichier `config.toml` illisible ou invalide : la page le dit, sans montrer son contenu.
- **Mise à jour** : relu à chaque ouverture de l'onglet (pas en direct).

## Refus

- Toute méthode autre que GET sur la route des réglages : 405.
- Hors 127.0.0.1 ou VPN déclaré : comme les autres vues en lecture.

## Tests

- **Aucune valeur masquée ne sort** : un `config.toml` d'essai porte, dans chaque clé de la liste fermée et dans des valeurs à
  forme de clé, des marqueurs uniques ; la réponse HTTP complète (corps et en-têtes) n'en contient aucun, ni le journal.
- Une clé nouvelle au nom sensible (`api_token`, `hote_secours`) est masquée sans être dans la liste exacte.
- Une liste avec un élément sensible est masquée en entier ; une table imbriquée est parcourue.
- Le coffre n'est pas ouvert (faux chemin de coffre surveillé : aucun accès).
- Signalements : transcription absente, actions absentes, outil sans fichier, config invalide.
- Aucune route en écriture (POST, PUT, DELETE : 405).
- **Navigateur** (Playwright, sinon « non mesuré ») : mesures de la finition UI aux 4 largeurs et dans les 2 thèmes ; page
  rendue sans « null » ni « undefined ».

Doc : le manuel (section interface, empreinte recalculée), `changelog.d/interface-reglages.md`. Relecture Codex avec la demande.
