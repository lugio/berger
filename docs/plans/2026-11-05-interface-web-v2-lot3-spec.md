# Interface web v2, lot 3 : la page « Conversation » — spec courte (05/11/2026, version 2)

Règle de go : cas 1, authentification et droits. Le navigateur gagne une écriture : un message à un agent et un fichier
déposé dans son dossier. Version 2 : elle suit le cahier des charges validé par le propriétaire le 05/11. Le lot 3 se code
APRÈS le lot « finition UI / À lire », dont il réutilise les composants, et reprend tous les garde-fous du lot 2 (n° 160).

## Constat

Depuis le web, le propriétaire valide, refuse, répond et marque lu (lot 2). Pour parler à un agent, il doit encore ouvrir
Herdr. Il veut une page de messagerie par agent : lire le fil, écrire, coller, joindre une image, dicter.

## Comportement

### 1. La page « Conversation »

- **Une page par agent**, ouverte d'abord pour Master. Le code ne dépend pas de Master : un autre agent s'ajoute par sa
  ligne de réglage, sans code nouveau.
- **Un fil de messagerie** : le propriétaire à droite, l'agent à gauche, dans l'ordre chronologique, rafraîchi en direct
  (5 s au plus tant que la page est ouverte, par le rafraîchissement déjà en place). Une saisie en cours n'est jamais effacée.
- **Source : la vraie conversation du moteur**, lue en LECTURE seule, jamais recopiée ailleurs.
  - Claude : la transcription `.jsonl` de la conversation notée dans `.conversation-claude` (celle que suit déjà le Tableau).
  - Codex : le fichier de sa session en cours.
  - La page n'écrit jamais dans ces fichiers. Au plus 50 tours affichés, 200 Kio par réponse HTTP ; le reste reste dans Herdr.
- **Les demandes de validation de l'agent** paraissent DANS le fil, à leur heure, en carte avec Valider et Refuser. Ce sont
  les actions du lot 2, sans rien de plus : même jeton, même confirmation, même journal, même garde-fou côté serveur.
- **Le travail technique est replié** : entre deux messages, les appels d'outils (commandes, fichiers lus, écrits) forment
  une ligne « N actions », dépliable. Déplié, chaque action montre son outil et sa cible courte (la commande ou le chemin,
  200 caractères au plus). **Jamais la sortie d'un outil**, qui peut porter des données.
- **Aucun secret affiché** : chaque bloc (message, cible d'action) passe par `MOTIFS_CLES` (`courtier/_secrets.py`) et
  devient « [masqué : secret possible] » s'il y répond.
- **Copier** : un bouton sur chaque réponse et chaque bloc de code.

### 2. La zone de saisie

- **Texte** : Entrée envoie, Maj+Entrée va à la ligne. **Même chemin que `berger parler <agent> --stdin`** (`parler()` :
  `agent.prompt` de Herdr, puis `echange()` pour le panneau Échanges). C'est le même pouvoir qu'en ligne de commande.
  - 20 000 caractères au plus, UTF-8, sans caractère de contrôle autre que le saut de ligne et la tabulation.
  - **Agent vivant seulement** : un agent au repos est refusé, avec la raison « au repos : relance-le depuis Herdr ».
    Le dépôt dans sa file est « plus tard ».
- **Long collage** (plus de 4 000 caractères ou 80 lignes) : il devient une pièce jointe texte, repliée dans la zone de
  saisie, rangée comme les autres pièces (`.txt`). L'agent reçoit son chemin. Le même garde-secrets s'applique à son contenu.
- **Image** : Ctrl+V d'une capture ou glisser-déposer. Elle devient une pièce jointe ; l'agent reçoit son chemin et la lit avec
  son outil de fichiers (Claude et Codex lisent les images).
- **Audio** : bouton micro → enregistrement → transcription → le texte paraît dans la zone de saisie, **corrigeable avant
  l'envoi**. L'audio est gardé avec le message (pièce jointe).
  - **Règle du propriétaire** : le micro n'est actif QUE si un module de transcription LOCAL est déclaré :
    `[interface] transcription = "<binaire absolu>"` dans config.toml. Le binaire doit exister et être exécutable.
  - Absent ou invalide : le bouton est grisé, avec sa raison au survol et au toucher (« aucune transcription locale
    déclarée »). **Jamais de service en ligne.**
  - Le binaire reçoit le chemin du fichier en argument et écrit le texte sur sa sortie. Il tourne sans réseau, sans coffre,
    sans variable d'environnement de Berger, avec 120 s au plus. Le texte passe par le garde-secrets avant d'être montré.

### 3. Les pièces jointes

- **Où** : dans le dossier de l'agent DESTINATAIRE seulement, `entrees/AAAA-MM-JJ/HHMMSS-<n>.<ext>`.
  - Dossier en 0700, fichier en 0600, écrit en O_EXCL|O_NOFOLLOW, sans lien.
  - Le nom est fait par Berger, jamais repris du client.
  - Jamais dans le dossier d'un autre agent : le chemin est construit côté serveur, puis contrôlé une fois résolu.
- **Le message envoyé** porte une ligne par pièce : « Pièce jointe : entrees/…/….png (image, 1,2 Mio) ».
- **Types permis**, vérifiés par l'extension ET par les premiers octets (jamais le type déclaré par le navigateur) :
  - images PNG, JPEG, WebP : 10 Mio au plus ;
  - audio WebM, Ogg, WAV : 25 Mio et 10 minutes au plus (durée lue par `ffprobe`, déjà présent) ;
  - texte (long collage) : UTF-8 valide, 2 Mio au plus.
- **Refusés** : tout autre type, dont SVG, HEIC, PDF, MP3, M4A, archives, exécutables.
- **Quota** : 500 Mio par agent dans `entrees/`. Au-delà, l'envoi est refusé. Rien n'est supprimé seul.

### 4. Garde-fous (ceux du lot 2, inchangés, plus ceux-ci)

1. `[interface] actions = true` exigé. **Écoute en local seulement (127.0.0.1)** pour ce lot : pas d'envoi depuis le VPN.
2. Contrôles de Host et d'Origin, session, **jeton anti-rejeu à usage unique et nonce** : ceux des actions du lot 2.
3. **Confirmation** : l'envoi porte l'empreinte de ce qui est montré (agent, texte, chaque pièce : type, taille, sha256). Si
   elle ne correspond pas à ce que le serveur reçoit, l'envoi est refusé.
4. **Garde-secrets avant envoi** : un texte (saisi, collé ou transcrit) où une forme de clé est trouvée est refusé. Le refus
   renvoie vers le coffre ; l'interface ne lit jamais le coffre.
5. **Journal dans `interface-actions.jsonl`**, comme au lot 2 : une ligne « admis » AVANT l'action (sans elle, rien n'est fait,
   503), puis une ligne de résultat. L'échec de la ligne finale est une erreur, jamais un 200. Chaque ligne porte l'agent, la
   taille du texte, et pour chaque pièce son type, sa taille et son sha256 ; jamais le texte ni le contenu.
6. **Débit** (proposé) : 60 messages, 20 pièces jointes et 100 Mio par heure, à part des 30 actions du lot 2, recompté sur
   l'heure entière même après un redémarrage. Requête de 40 Mio au plus, lue en flux et coupée avant d'être écrite au-delà.
7. **Hors périmètre** : relancer ou arrêter un agent, la file d'un agent au repos, l'envoi à plusieurs agents, la vidéo,
   l'accès depuis le VPN, toute transcription par un service extérieur.

## Refus

Chacun avec un message nommé :
- sans `actions = true`, hors 127.0.0.1, mauvais Host ou Origin, sans jeton ou avec un jeton déjà servi, empreinte périmée ;
- agent inconnu ou au repos ;
- texte trop long, caractère de contrôle, forme de clé ;
- pièce d'un type refusé, aux premiers octets qui ne correspondent pas, trop grosse, trop longue, au-delà du quota, ou dont le
  chemin sortirait du dossier de l'agent destinataire ;
- micro sans module de transcription local déclaré (côté serveur aussi, pas seulement le bouton grisé) ;
- au-delà du débit.

## Tests

- **Envoi texte** : un faux Herdr reçoit le même `agent.prompt` que `berger parler`, Échanges reçoit la même ligne, avec
  « via l'interface web ».
- **Pièce jointe** : un long collage devient un `.txt` en 0600 sous `entrees/`, son chemin est dans le message.
- **Image** : un PNG valide est rangé en 0600 sous un nom fait par Berger ; un lien posé à l'avance n'est pas suivi.
- **Refus de type et de taille** : un PNG renommé en .wav, un SVG, un MP3, un fichier trop gros, le quota dépassé.
- **Micro grisé sans module** : sans `transcription`, le bouton est grisé avec sa raison, et le serveur refuse une
  transcription demandée quand même. Avec un faux binaire local : texte rendu, délai dépassé, forme de clé refusée.
- **Fil** : une transcription d'essai avec appels et sorties d'outils. Les messages sont rendus de chaque côté, les actions
  forment « N actions », aucune sortie d'outil n'est rendue, une forme de clé est masquée, une demande de validation paraît en
  carte et ses boutons passent par les actions du lot 2.
- **Garde-fous** : chaque refus ci-dessus ; deux envois avec le même jeton depuis deux fils (un seul passe) ; la ligne finale du
  journal qui ne s'écrit pas donne une erreur ; le débit compte encore après un redémarrage.
- **Navigateur** (Playwright, sinon « non mesuré ») : aux largeurs du lot « finition UI » et dans les 2 thèmes, la zone de
  saisie, Entrée et Maj+Entrée, le collage d'une image, le dépliage de « N actions ».

Doc : le manuel (interface) et `changelog.d/interface-web-v2-lot3.md`. La relecture Codex est enregistrée avec chaque demande.

## Choix pris faute de réponse (à corriger si besoin)

1. Un agent au repos : refus (le dépôt dans sa file est « plus tard »).
2. Quota et débit : les valeurs ci-dessus.
3. « N actions » déplié : l'outil et sa cible courte, jamais sa sortie.
