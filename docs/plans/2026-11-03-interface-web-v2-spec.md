# Interface web v2 : simple, lisible partout, et des actions du propriétaire — spec courte (03/11/2026)

Règle de go : cas 1, authentification et droits. Les actions depuis le navigateur sont un changement de sécurité. Demande
du propriétaire du 03/11, à partir de sa maquette validée (Accueil web) et de l'audit de l'interface du même jour.

## Constat

`berger interface servir` (`bin/interface.py`, `bin/page/`) existe depuis le 13/10. Elle est rapide et a les mêmes onglets que
Herdr, mais l'audit du 03/11 relève neuf défauts :
1. « null » s'affiche en haut de l'Accueil.
2. Des bordures colorées à gauche des alertes, ce que la règle du propriétaire interdit.
3. L'Accueil est beaucoup trop long : environ 5 500 px.
4. Les textes bruts sont techniques : SHA complets, phrases de 300 caractères.
5. Une carte du Tableau déborde de sa colonne.
6. Les agents fermés sont affichés « ? », avec une double icône et des noms coupés.
7. Sur mobile, la barre du bas coupe « Documents ».
8. Le premier chargement pèse environ 1 Mo, et une vue est demandée deux fois.
9. Aucune action n'est possible : il faut toujours taper `berger valider N` ailleurs.

## Comportement — deux lots, une demande de fusion chacun

### Lot 1 — lecture (aucun changement de sécurité)

1. **La maquette du propriétaire fait foi** : Accueil court (« pour toi » en tête, le reste replié), Tableau, À lire, Coulisses,
   et une page par agent.
2. **L'onglet Décisions est retiré, dans le web ET dans Herdr** (décision du propriétaire) : l'Accueil montre déjà ce qui
   l'attend. `berger refaire-espace berger` retire l'ancien onglet par son titre exact.
3. **Une seule source d'icônes et de libellés pour Herdr et pour le web.**
   - Les icônes sont des SVG au trait, sans aucun émoji, dans un seul fichier versionné.
   - Les libellés sont courts, et pensés pour un propriétaire non technicien : SHA courts, phrases coupées proprement.
4. **Menu latéral repliable**, dont l'état est mémorisé dans le navigateur, sur ce poste seulement.
5. **Responsive** sur bureau, tablette et mobile (aux largeurs 1440, 820 et 390), sans débordement horizontal.
6. **Fenêtres de détail** (une validation, un document À lire, un agent) au lieu de longues pages.
7. **Corriger les 8 premiers défauts de l'audit.** Une seule requête par vue, et un premier chargement plus léger.

### Lot 2 — actions du propriétaire (changement de sécurité)

Trois actions, et rien d'autre :
- **Valider** une validation en attente ;
- **Refuser**, avec un motif obligatoire ;
- **Répondre** à une question qu'un agent pose au propriétaire.

« Marquer lu » un document À lire en fait aussi partie, mais il n'écrit que l'état « lu » déjà tenu par Berger.

Garde-fous :
1. **Même chemin que la ligne de commande.** Chaque action appelle le code de `berger valider` / `berger refuser` / la
   réponse existante. Aucun pouvoir nouveau : ce que le propriétaire ne peut pas faire en ligne de commande, il ne le peut pas
   ici.
2. **Où.** L'interface n'écoute qu'en local, ou sur l'adresse VPN déjà permise par `[interface] adresse` et `sources`.
   - Les actions sont refusées sur toute autre source, même authentifiée.
   - Une option `[interface] actions = true` les active ; elle est absente par défaut, et le lot 1 reste en lecture seule
     sans elle.
3. **Session.** L'authentification ne change pas : jeton échangé une fois contre un cookie dérivé, HttpOnly, SameSite=Strict
   et Secure derrière TLS.
   - Chaque action porte en plus un **jeton anti-rejeu** dérivé de la session (déjà prévu par `deriver`).
   - Une requête POST sans ce jeton ou d'une autre origine est refusée.
4. **Confirmation.** Avant d'agir, l'interface montre ce qui sera fait : numéro, aperçu exact, empreinte de la demande.
   L'action est refusée si la demande a changé entre l'affichage et le clic, sur la même empreinte que l'aperçu.
5. **Journal.** Chaque action est journalisée comme en ligne de commande, avec « via l'interface web », l'heure et la source.
   Un refus est journalisé aussi.
6. **Débit.** Au plus 30 actions par heure. Aucun secret n'est affiché, et rien d'un agent n'est exécuté.
7. **Hors périmètre :** la production, les gestes qui demandent déjà une confirmation hors Berger, toute action d'un agent,
   les réglages.

## Refus

- Actions sans `[interface] actions = true`, depuis une source hors local/VPN, sans jeton anti-rejeu, d'une autre origine ou
  sur une demande modifiée : refusées avec un message nommé.
- Refuser sans motif : refusé.

## Tests

- **Lot 1** (sans navigateur réel, et avec Playwright s'il est présent) :
  - aucune bordure gauche colorée ni aucun émoji ;
  - pas de débordement aux trois largeurs ;
  - « null » absent ;
  - Décisions absent du web et de Herdr ;
  - une seule source d'icônes, lue par les deux ;
  - le menu replié est mémorisé.
- **Lot 2 :** chaque refus ci-dessus, la valeur égale à la ligne de commande (même effet, même journal plus
  « via l'interface web »), la confirmation périmée refusée, le débit.

Doc : manuel (interface) et CHANGELOG. Relecture Codex enregistrée avec chaque demande.
