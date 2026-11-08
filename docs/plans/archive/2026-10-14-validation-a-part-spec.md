# Une validation longue s'exécute à part : le courtier continue de servir les autres agents

Spec, 14/10/2026 (mission de master ; go du propriétaire du 14/10 pour le sujet — cœur du courtier : spec d'abord, aucun
code avant l'accord de master).

## Constat (vécu du 14/10)

Le propriétaire valide la n° 94 (fusion) juste après la n° 93. `main` a avancé : le courtier met la 94 à jour puis rejoue
les portes (`tests/suites.sh`, deux passages, environ 16 min). Pendant ce temps, **aucun appel n'est servi**
(`appels.log` muet de 10:35:17 à 10:51:44, panneaux arrêtés) et le redémarrage contrôlé de l'installation de la 93 attend
derrière (« 1 demande(s) en cours (validation n° 94) : j'attends… »). Tout repart seul ensuite.

**Cause, dans le code.** `courtier/courtier` :
- l. 727-746, `main()` : UNE boucle fait tout, dans cet ordre, toutes les 0,3 s : relever les boîtes aux lettres
  (chaque demande part dans son fil, l. 740), puis `traiter_decisions(); panneaux_dus(prochain)` (l. 743).
- l. 468-525, `traiter_decisions()` : exécute l'action validée **dans le fil de la boucle**
  (`ECRITURES[outil][verbe][1](args)`). Une fusion qui rejoue les portes (`equipe_chef.fusionner`, l. 315-347 ;
  `jouer_portes` l. 332) bloque donc la boucle : plus aucune demande relevée, plus aucun panneau lancé. Les demandes
  déjà parties dans leur fil continuent ; les nouvelles s'entassent dans `courrier/demandes/`.
- l. 470 : `sorted(VALIDATIONS.glob("*.decision"))` trie les noms **comme du texte** : `10.decision` passe avant
  `9.decision`. L'ordre d'exécution n'est donc pas garanti aujourd'hui (défaut à corriger au passage).

`bin/berger` : `courtier redemarrer` (l. 4073-4081) attend qu'il n'y ait plus aucune demande dans `courrier/encours/` ni
aucune marque `validations/*.execution` (15 min au plus, sinon « redémarrage NON fait »). `installer` (l. 3740-3771)
lance ce redémarrage détaché (`systemd-run … courtier redemarrer --controle <avant>`, l. 3764).

## Comportement attendu

1. **Un fil d'exécution dédié** (« l'exécuteur ») est lancé par `main()` au démarrage. Il fait, en boucle (0,3 s) :
   `traiter_decisions()` — **la même fonction**, inchangée dans ce qu'elle écrit. La boucle principale ne l'appelle plus :
   elle ne fait plus que relever les boîtes, lancer les panneaux et surveiller l'exécuteur.
2. **Une à la fois, dans l'ordre.** Un seul exécuteur, donc une seule action validée à la fois. Ordre : celui des
   **décisions** (date du fichier `<n>.decision`, puis le numéro en cas d'égalité) — le propriétaire valide la 93 puis la
   94 : la 93 s'exécute d'abord. Les refus passent aussi par l'exécuteur (une seule main sur `courtier/validations/`).
3. **Rien ne change dans ce qui est écrit** : marque `<n>.execution` posée avant l'action et retirée après,
   `<n>.fait.json` inscrit d'abord, journal de l'agent, `appels.log`, message au demandeur, Échanges. Aucun nouveau
   fichier, aucun mécanisme parallèle.
4. **Redémarrage pendant une exécution** : comme aujourd'hui. `courtier redemarrer` voit la marque `.execution` et
   attend ; un arrêt brutal (plantage, `systemctl restart` direct) laisse la marque, et `reprendre_executions()` dit au
   démarrage « état inconnu, à vérifier » — **jamais rejouée**. Les décisions qui attendaient leur tour (`.decision`)
   ne sont pas touchées par un redémarrage : elles s'exécutent après, dans l'ordre.
5. **Après une installation, la file se tient.** Au démarrage, le courtier note le commit de l'installation (HEAD du
   dépôt `BERGER_DIR`, s'il en est un). Avant de prendre une nouvelle décision, l'exécuteur relit ce HEAD : s'il a changé
   (une installation vient de poser du nouveau code et le redémarrage contrôlé est en route), il **n'en prend aucune**
   jusqu'au redémarrage. Ainsi le redémarrage contrôlé de la 93 passe tout de suite (plus de `.execution` derrière
   laquelle attendre) et la 94 s'exécute ensuite avec le code neuf. Si l'installation revient en arrière (HEAD = celui
   du démarrage), la file repart d'elle-même. Garde-fou : si au bout de 20 min aucun redémarrage n'est venu, notification
   urgente au propriétaire (une fois) et la file repart (comportement d'aujourd'hui : exécution avec le code chargé).
   Aucun nom de projet ni de verbe dans cette règle : elle vaut pour l'installation automatique après fusion
   (`installer_outil`) comme pour `installer` validée à la main.
6. **Exécuteur arrêté = courtier arrêté.** Une exception non prévue dans l'exécuteur est rattrapée par décision (même
   traitement qu'aujourd'hui) ; si le fil meurt malgré tout, la boucle principale le voit, l'écrit sur la sortie
   d'erreur et arrête le processus (code ≠ 0) : systemd le relance (`Restart=on-failure`), et la marque laissée donne
   « état inconnu ». Jamais une file muette.

## Choix : un fil, pas un processus

- **Mêmes objets que la boucle** : les outils sont chargés une fois au démarrage (`OUTILS`, `ECRITURES`, `OBJETS`,
  `installer_par`, filtre des secrets). Un processus à part devrait tout recharger depuis le disque — et après une
  installation, le disque porte déjà le **nouveau** code alors que la validation a été demandée et contrôlée avec
  l'ancien : deux versions du courtier en même temps, exactement la divergence à éviter.
- **Pas de gain à la reprise** : `systemctl restart` arrête tout le groupe du service (KillMode par défaut), processus
  enfants compris ; un processus à part ne survivrait pas mieux à un redémarrage. La garantie « jamais rejouée » vient
  de la marque `.execution`, pas du type d'exécution.
- **Déjà le modèle du courtier** : chaque demande d'agent, délégation, mission et panneau tourne déjà dans son fil
  (l. 740, 543, 596, 602, 699) ; le contexte de l'appel est propre à chaque fil (`outils/_contexte.py`, posé par
  `contexte()` dans le fil qui exécute).
- **Le verrou global de Python ne gêne pas** : une exécution longue attend des sous-processus (git, portes en bac à
  sable) ; le fil rend la main pendant ces attentes.

## Interactions

- **`courtier redemarrer`** (manuel ou contrôlé) : inchangé. Il attend `encours/` vide et aucune `.execution`. Avec la
  file tenue (point 5), une installation n'a plus de nouvelle `.execution` derrière laquelle attendre.
- **`.fait.json` puis installation** : `installer_apres` (outil `equipe_chef`, l. 373) lance `installer` ; celle-ci
  lance le redémarrage détaché qui attend que `<n>.fait.json` soit écrit et la marque retirée (inchangé, déjà testé par
  `tests/validation-fait.py`). Le seul changement : le fil qui écrit ce résultat est l'exécuteur, pas la boucle.
- **`installer_outil` et le retour arrière** : inchangés. Le redémarrage reste contrôlé (`--controle <avant>`) ; un
  courtier inactif après redémarrage → retour arrière automatique, trace dans `courtier/installations.log`, notification.
- **Décision arrivée pendant une exécution** sur la même validation (course entre `berger valider` et un valideur) : la
  marque l'a déjà renommée ; la nouvelle `.decision` est vue ensuite par l'exécuteur, `.fait.json` existe → effacée,
  jamais rejouée (inchangé).
- **Interface web** (`bin/interface.py`) : non touchée (un autre développeur y travaille). Elle lit les mêmes fichiers.

## Risques et parades

- **Le chef de projet peut maintenant appeler ses verbes pendant une fusion** (relire, rejouer, demandes, etiqueter) sur
  le MÊME dépôt du chef (`self.git`, `equipe_chef.py` l. 59). C'était déjà possible pour une demande partie juste avant
  l'exécution, mais devient courant. git protège ses références par ses propres verrous : au pire un `fetch` concurrent
  échoue (« cannot lock ref ») et la fusion finit « validé mais ÉCHEC » sans rien pousser — sûr, mais pénible. Parade
  prévue : un verrou par dépôt du chef, pris autour de CHAQUE commande git de ce dépôt (une lecture comme `status` ne
  voit jamais un `merge` à moitié fait), **jamais pendant les portes** (copie jetable à part) : les lectures attendent
  quelques secondes, pas 16 min. Attente bornée (120 s, `BERGER_ATTENTE_DEPOT`), puis refus clair « dépôt du chef
  occupé » — jamais une attente sans fin (précision de master, 14/10).
- **Une action qui ne finit jamais** bloque la file des validations (aujourd'hui : tout le courtier). Les commandes ont
  déjà leur délai (portes : `delai` 900 s par porte ; git 300 s ; installer 600 s par étape).
- **Lecture longue et redémarrage** : `courtier redemarrer` attend aussi les demandes en cours ; un `rejouer` de 16 min
  du chef le retarde (inchangé, hors sujet ; noté).
- **Numérotation** des nouvelles demandes de validation pendant une exécution : `demander_validation` compte les
  `<n>.json` et `<n>.fait.json` ; le résultat est écrit avant que la demande soit retirée → pas de numéro réutilisé.

## Tests (`tests/validation-a-part.py`, ajoutée à `tests/suites.sh`)

Installation jetable, VRAI courtier lancé (sa boucle `main()`), outil d'essai à écriture lente :
1. **Lecture servie pendant une exécution** : une validation dont l'action dure N s (N = 8) ; pendant ce temps, un appel
   de lecture d'un autre agent reçoit sa réponse en moins de 2 s ; un panneau est collecté.
2. **Deux validations à la suite** : 94 décidée juste après 93 → exécutées l'une APRÈS l'autre (horodatages sans
   chevauchement), dans l'ordre des décisions ; 9 et 10 décidées dans cet ordre → 9 d'abord (tri numérique).
3. **Redémarrage pendant l'exécution** : courtier lancé en processus, arrêté pendant l'action → au redémarrage
   « état inconnu », action exécutée UNE fois (compteur) ; la décision qui attendait son tour s'exécute ensuite, une fois.
4. **Installation automatique toujours contrôlée** : action qui change le HEAD de l'installation jetable et lance
   `courtier redemarrer` → la décision suivante n'est pas prise avant le redémarrage ; le redémarrage n'attend aucune
   `.execution` ; HEAD revenu → la file repart ; `.fait.json` inscrit avant l'appel à systemctl (contrôle existant gardé).
5. **Exécuteur mort** → le processus s'arrête avec un code ≠ 0.
7. **Verrou du dépôt du chef** : dépôt tenu → refus clair après l’attente bornée ; dépôt libre → la commande passe et rend le verrou.
6. Les suites existantes qui appellent `traiter_decisions()` directement (`validation-fait.py`, `supervision.py`,
   `agent-appliquer.py`, `domaines.py`, `bibliotheque-projets.py`) passent sans changement.
