# Courtier : textes refusés au lieu d'être coupés, canal gardien → chef, redémarrage qui aboutit (spec)

**Go du propriétaire le 16/10, cité par master : « go courtier-textes » et « go redémarrage courtier ».** Touche le cœur (courtier).
Rien de propre à un moteur : Claude et Codex passent par le même chemin (`berger-outil` → courrier → courtier).

## 1. Textes coupés en silence
**Constat.** `traiter()` coupait chaque argument à 2 000 caractères (mission, equipe, deleguer, demander-fusion, renvoyer, attente) et
à 80 ailleurs ; `deleguer` recoupait le texte joint à 2 000 ; `renvoyer` et `attente` du chef recoupaient le motif à 1 500. Une mission
de 2 500 caractères arrivait amputée de sa fin, sans que personne le sache.
**Cause racine.** Une troncature (`str(a)[:N]`) servait de garde de taille : elle ne refuse rien, elle ampute.
**Comportement.** Un argument plus long que sa limite est REFUSÉ, rien n'est fait :
`trop long (N caractères, M au plus) : mets le détail dans un fichier de ton dossier et cite son chemin`.
- textes (mission, equipe, deleguer — texte joint —, demander-fusion, renvoyer, attente) : M = `[courtier] mission_max` (6 000 par défaut) ;
- tout autre argument : M = 80, même message ; `ecrire` (2 000) et `besoin` (1 500) gardent leur refus propre, sans troncature avant.
**Tests** (`tests/courtier-textes.py`, agents claude et codex) : M+1 refusé avec ce message et sans MISSION.md ; M arrivé intact
(MISSION.md porte exactement le texte) ; 81 caractères refusés ailleurs ; délégation trop longue refusée.

## 2. Canal vers le chef
**Constat.** `droits_equipe()` ne donnait `ecrire:<chef>` qu'au coordinateur : une équipe sans coordinateur (un projet métier depuis le 16/10)
n'a plus personne qui puisse écrire à son chef.
**Cause racine.** Le seul canal descendant vers un chef passait par le rôle de coordinateur.
**Comportement.** Le gardien (chef de projet de l'équipe qui porte `installer_outil`) reçoit `ecrire:<chef_projet>` pour CHAQUE équipe,
jamais `mission:<chef>`. Le coordinateur garde ses droits.
**Tests** : gardien → chef accepté ; `mission confier` du gardien au chef refusé ; un autre agent → chef refusé ; équipe avec coordinateur
inchangée.

## 3. Redémarrage du courtier
**Constat (agent d'infrastructure, 16/10).** Après l'installation de 8 h 26, `berger courtier redemarrer` attendait qu'il n'y ait plus AUCUNE demande en cours ;
les portes des développeurs se relayaient : au bout de 15 min, abandon, exit 1, rien dans `installations.log`, aucune notification.
HEAD ≠ référence : `file_tenue()` a bloqué les décisions du propriétaire, et son délai ne partait que de la première décision vue ;
la réponse à sa décision disait « le courtier la traitera dès qu'il tourne ».
**Cause racine.** Le courtier continuait d'entamer des demandes longues pendant qu'on attendait qu'il se vide : l'attente était bornée
par le flux, pas par ce qui était en cours. L'abandon n'était qu'un `sys.exit` ; le délai de la file partait d'un évènement sans rapport.
**Comportement.**
- (a) `redemarrer` pose la marque `courtier/fermeture` (bornée dans le temps). Tant qu'elle vaut, le courtier n'ENTAME plus aucune nouvelle
  demande ni décision — générique, sans liste de verbes longs à tenir (porte, contrôle ssh, délégation…) — : la demande est rangée dans
  `courrier/attente/` (le client `berger-outil` continue d'attendre) et servie après le redémarrage. Seules passent les lectures
  instantanées du courtier lui-même : `aide`, `validation liste`, `mission suivi`, `demandes` du chef (remarque de l'agent d'infrastructure, 16/10). L'attente est
  bornée par la plus longue demande EN COURS (`[courtier] redemarrage_attente`, 900 s au plus).
- (b) Abandon : la marque est retirée (les demandes rangées repartent), une ligne `redémarrage NON fait` dans `installations.log`,
  une notification URGENTE, puis un nouvel essai lancé à part dans `[courtier] redemarrage_reessai` (300 s), `redemarrage_essais` (12)
  au plus ; le dernier le dit.
- (c) `file_tenue()` : le délai part de l'installation (heure du changement de HEAD, lue dans le reflog), vérifiée même sans décision ;
  l'état est écrit dans `courtier/file-tenue.json`. `berger valider|refuser` répond alors
  `décision enregistrée ; file tenue : installation en attente de redémarrage depuis HH h MM — …`.
**Tests** (`tests/redemarrage-courtier.py`) : trois demandes longues qui se chevauchent, redémarrage demandé pendant elles, nouvelles
demandes rangées (dont un « controle » d'un outil ssh factice) : le redémarrage se fait dès la fin de la plus longue (moins que sa durée
après la demande de redémarrage), les nouvelles sont servies après, une lecture instantanée (`validation liste`) est servie pendant ; un abandon donne trace, notification urgente et nouvel essai ; une
décision prise pendant une file tenue donne le message exact ; délai compté depuis l'installation. Agents claude et codex.
**Retour arrière** : revenir au commit d'avant (`berger installer` d'une version précédente) ; aucune donnée à migrer
(`courtier/fermeture`, `courtier/file-tenue.json` et `courrier/attente/` se recréent ou s'ignorent).
