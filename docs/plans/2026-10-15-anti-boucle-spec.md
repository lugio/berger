# Garde-fou anti-boucle, commun à tous les moteurs (spec — AUCUN code avant le go du propriétaire)

**Go reçu le 15/10 (l'agent d'infrastructure au nom du propriétaire), avec la réserve de master (relance seulement si boucle repérée).** Touche le cœur de l'installation (courtier, règle de relance) : rien n'est écrit tant que le propriétaire
n'a pas dit oui. Consigne du propriétaire : « pas de spécificité des moteurs » — l'ancienne piste (refuser des outils de planification
d'un seul moteur dans les réglages Claude) est **abandonnée**, aucun code n'en subsiste.

## Constat (mesuré)
Un agent a répété `mission suivi <chef de projet>` 1 761 fois le 15/10, jusqu'à 576 par heure. Le courtier ne limite aujourd'hui que le
débit (30 appels par minute et par agent, `courtier/courtier`, ligne « trop d'appels ») : une boucle lente passe, sans trace utile.
Le panneau de l'agent reste « travaille », donc la relance (« au repos seulement », `relancer`) ne le touche jamais.

**Cause racine.** Rien ne distingue, côté berger, un agent qui avance d'un agent qui refait le même geste sans rien recevoir :
le courtier compte des appels par minute, pas des répétitions identiques, et la relance ne lit que le statut de Herdr.

## (a) Garde-fou dans le courtier
- **Règle** : le même agent fait le même appel — `(outil, verbe, arguments)` — plus de **N** fois sur une heure glissante, sans
  **message reçu** entre deux appels (message d'un agent ou du propriétaire, mission, réveil du planificateur). L'appel N+1 est refusé.
- **Refus poli** : `{"ok": false, "erreur": "même appel répété N fois en une heure sans rien reçu : change de méthode ou demande à master"}` ;
  journalisé dans `appels.log` (détail « boucle »), comme la limite actuelle.
- **Synthèse** : une alerte jaune « boucle : <agent> <outil> <verbe> (×N, depuis HH:MM) » (`alertes_synthese`), effacée quand la boucle cesse.
- **Prévenir master** : un message de service **une seule fois** par boucle (une trace par agent+appel tant qu'elle dure ; rouverte
  après une heure sans refus), par la file de messages existante — aucun nouvel outil.
- **Réglage** : `[courtier] boucle_max = 6` (N) dans `config.toml` ; `0` = garde-fou éteint (**interrupteur**).
- **Neutre au moteur** : l'empreinte est calculée dans le courtier sur la demande reçue ; Claude et Codex passent par le même chemin.
  « Message reçu » se lit dans la file de messages et les journaux du courtier (aucune lecture du moteur).
- **Ce qui n'est pas compté** : les verbes d'aide, et les appels qui diffèrent par un argument. *(Écart de réalisation, 15/10 : la clause
  « réponse changée » est abandonnée — une réponse qui porte une heure ou un journal change toujours et aurait laissé passer la boucle
  mesurée.)*
- **Faux positifs** : une vraie attente qui relit le même état (ex. `mission suivi` d'un développeur pendant une longue tâche).
  Réponse : N = 6 par heure laisse un suivi toutes les 10 minutes ;
  le refus dit quoi faire (attendre le message du développeur, ou prévenir master). Un refus ne coûte rien : l'agent peut reprendre
  dès qu'un message arrive ou qu'une heure glisse.
- **Retour arrière** : `boucle_max = 0` puis redémarrage du courtier ; le code est isolé (une fonction avant `repondre`).

## (b) Règle écrite
`commun/REGLES.md` (donc dans les consignes de chaque agent) et le skill berger : **« Pas de boucle maison : une veille
périodique passe par ton `HEARTBEAT.md` et le planificateur, jamais par une répétition que tu t'organises toi-même. »** Aucun nom
d'outil de moteur. L'agent propose au propriétaire le texte du HEARTBEAT.md (il ne le modifie pas seul).
- Refus : sans objet (c'est une règle de conduite ; le garde-fou (a) en est le filet).
- Faux positif : aucun. Retour arrière : retirer la ligne.

## (c) Relance d'un agent « au travail » — seulement s'il est en boucle (réserve de master)
- **Règle** : un agent que Herdr dit « travaille » compte comme **au repos** pour `relancer` et `relancer_attentes` **uniquement si
  les deux conditions sont réunies** : (1) rien de berger ne l'a sollicité depuis **M** minutes (ni mission, ni message reçu, ni
  réveil du planificateur) ; (2) le garde-fou (a) a **aussi** repéré une boucle active chez lui (un refus « boucle » dans la
  dernière heure, non soldé).
- **Raison** : une conversation directe du propriétaire dans Herdr est invisible à berger ; sans la condition (2), sa longue tâche serait
  prise pour de l'inactivité et l'agent serait relancé en plein travail.
- **Réglage** : `[relance] inactif_min = 30` (M) ; `0` = comportement actuel (interrupteur).
- **Refus** : agent occupé **sans boucle repérée** → relance refusée, quelle que soit la durée ; sollicitation récente → refusée ;
  `--force` reste au propriétaire seul.
- **Faux positifs** : restent possibles seulement si l'agent boucle ET travaille vraiment à côté (rare : il aurait répété 6 fois le
  même appel sans réponse changée). Atténuation : reprise dans la **même conversation**, relance tracée au journal
  (« relancé : occupé, boucle repérée, sans sollicitation depuis M min »).
- **Retour arrière** : `inactif_min = 0`.

## (d) Tests (sans modèle, installation jetable, `tests/anti-boucle.py`)
1. N appels identiques passent, le N+1 est refusé ; master prévenu **une seule fois** (même après N+2, N+3) ; alerte en Synthèse.
2. N appels **espacés** par un message reçu passent tous ; les appels qui diffèrent d'un argument ne se cumulent pas.
3. *(abandonné : clause « réponse changée »)* Un agent qui travaille sans répéter d'appel (long travail en direct du propriétaire) n'est ni bloqué ni relançable.
4. `boucle_max = 0` : rien n'est refusé (interrupteur).
5. Relance : agent « travaille », sans sollicitation depuis plus de M minutes ET boucle repérée → relancé (boucle simulée : appels
   identiques) ; **agent occupé sans boucle repérée, même inactif depuis plus de M minutes → relance refusée** (cas d'une longue
   tâche du propriétaire dans Herdr) ; boucle repérée mais sollicitation récente → refusée ; `inactif_min = 0` → refusée comme aujourd'hui.
6. Claude et Codex : même verdict (le test appelle le courtier, pas un moteur). Pas de sonde par moteur : le garde-fou n'en dépend pas.
Une porte `pret` : tests ajoutés à `tests/suites.sh`, documentation (README, REGLES, skill) dans la même branche.

## Questions pour le propriétaire
1. N = 6 par heure, M = 30 minutes : ces valeurs vous conviennent-elles ?
2. Le message à master une seule fois, plus l'alerte Synthèse : suffisant, ou aussi une notification à vous ?
