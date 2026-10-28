# Modulaire : décisions du propriétaire (27/10/2026)

Complète `docs/plans/2026-10-27-modulaire-spec.md` (go du propriétaire sur le commit 0c2abc4, lots 1 à 3 ; le lot 4 attend un go inscrit à part).
Nom du propriétaire neutralisé dans la spec (4 lignes) et ici : « le propriétaire », sens inchangé.
La spec n'est pas modifiée (hors cette neutralisation) : ses deux « points ouverts » sont tranchés ici.

1. **Taille des fichiers** : 1 500 lignes au plus par fichier de `bin/`, plus 500 pour un fichier de commandes NOUVEAU
   (`bin/commandes/`, donc 2 000), **sans exception**. Seule dérogation, le **cliquet décroissant** de `bin/berger` pendant la
   migration : sa taille ne peut que baisser, la valeur est abaissée à chaque lot, et le lot 4 l'amène sous 250 lignes.
   Vérifié par `tests/taille-fichiers.py` (rouge si un fichier dépasse, ou si `bin/berger` dépasse son cliquet).
2. **Noyau « tout ou rien »** : le noyau n'est pas écartable module par module ; s'il ne charge pas, `berger` s'arrête en disant
   pourquoi. Les vues, commandes et moteurs restent écartables un à un, nommés. Vérifié par `tests/contrat-noyau.py` (une vue
   cassée est écartée et nommée, les autres tournent) ; l'absence d'écartement du noyau découle de `from noyau… import *` en tête de `bin/berger`.

## Écarts à la spec constatés au lot 1 (à lire)

- L'API mesurée n'avait pas relevé les couleurs d'affichage (`R`, `GRAS`, `PALE`, `BLEU`, `JAUNE`, `VERT`, `ROUGE`, `CYAN`, `INV` :
  affectation multiple non vue par l'analyse) ni `CONFIG` (lu par deux vues) : les vues emploient en réalité 80 noms du cœur (au lieu
  de 71), plus sept modules de la bibliothèque standard. Ils entrent dans l'API, qui compte au total **88 noms** avec la porte Herdr et le transport.
- Transport : la spec parlait de réexporter `executer`, `executer_shell`, `lancer`, `ecrire_configuration`. `lancer` existe déjà dans le cœur
  (commande « lancer un agent ») : l'API expose donc `transport` (le module de `courtier/outils/_transport.py`) et ses fonctions s'appellent
  `transport.executer(…)`, etc. Aucun comportement changé.
- Les fonctions `vue_<type>` ne sont plus remises dans les globales du cœur (« pas de lecture arrière ») : un appel direct passe par
  `VUES["<type>"]`. Deux accès adaptés, même assertion : `bin/berger` (panneau À lire) et `tests/echanges.py` (4 appels).
- Moteurs : l'admission (`executable_moteur`, `version_moteur`, `verdict_moteur`, `alertes_moteurs`, `MOTEURS`, `CONTRATS`) RESTE dans
  `bin/berger` (des tests la remplacent dans ses globales : `mcp-trous`) jusqu'au lot 2. `alertes_synthese` (noyau, lue par la vue Synthèse)
  appelle `alertes_moteurs` : `bin/berger` la branche dans `noyau.lectures` au démarrage (une ligne, retirée au lot 2). Seuls
  `lire_conso_claude`, `lire_conso_codex` et `LECTEURS_CONSO` (lus par la vue Tokens) ont suivi leurs lecteurs dans `noyau/lectures.py` ;
  ils repartent dans `moteurs/` au lot 2.
- `masques` et `cloisons` (le calcul du mur) RESTENT dans `bin/berger`, à l'identique, jusqu'au lot 4 (cas 1, go inscrit). `droits_agents` et
  `statuts_donnees` (noyau) les appellent : `bin/berger` les branche dans `noyau.lectures` au démarrage (une ligne, retirée au lot 4).
  Les assistants que ces deux fonctions utilisaient seules (`projets_de`, `registre_projets`…) restent aussi au cœur.

## Tests dont seule la FORME d'accès change (même assertion)

Le code a changé de fichier ; ces tests lisaient `bin/berger` ou ses globales. Aucun n'est retiré ni affaibli.
- `vue_<type>` : `g['vue_x']` devient `g['VUES']['x'].vue_x` dans `alire`, `catalogue`, `decisions`, `roles`, `skills-roles`, `skill-produit`,
  `skills-equipes`, `synthese`, `tokens`, `tableau`, `echanges`. `tests/vues.py` : « les fonctions vue_<nom> restent appelables depuis le
  cœur » devient « … par le registre VUES », et une assertion s'ajoute (plus aucune `vue_*` dans les globales du cœur).
- `entree_privee` est lue dans `bin/noyau/transport.py` (`argv-cli`, `argv-prive`). `web-profils-masques` est identique à `main`.
- `tests/vitrine.py` épingle l'empreinte du corps du manuel : elle est recalculée parce que le manuel est mis à jour (règle 7 de la spec).

## Lot 1 : fonctions déplacées de `bin/berger` vers `bin/noyau/` (taille de `bin/berger` : 6 089 → 4 944 lignes)

- `noyau/config.py` : constantes seules (en-tête de bin/berger : chemins, config.toml, programmes externes, coffre, masques, bibliothèque, garde-fous)
- `noyau/transport.py` : entree_privee
- `noyau/affichage.py` : _l, vlen, couper, pad, plat, plier, entete, titre_section, statuts_texte, jauge, date_fin, colonnes_tableau_texte, puces, section, mini_entete, prochaine
- `noyau/agents.py` : agents, dossier, conf, conf_texte, travail, externe, memoire_dossier, ecritures_en_plus, fichier_memoire, ouvert, superviseur, lire, aujourdhui, cases, checklist, pendants, signale_aujourdhui
- `noyau/herdr.py` : herdr_ids, herdr, socket_herdr, herdr_api, statut_herdr
- `noyau/lectures.py` : derniere_sollicitation, boucles_actives, alertes_consignes, approbations_hooks, dossier_skills, methode, developpeur, skills_demandees, conversation_claude, gardien, besoins, hote_mission, reglages_mission, json_ou_rien, en_attente, validation_donnees, reglage_tache, tableau_donnees, identite_donnees, identite_texte, capacites_donnees, capacites_texte, verbes_outil, ecritures_outil, limites_donnees, limites_texte, memoire_donnees, memoire_texte, veille_donnees, veille_texte, alertes_auto_test, activite_donnees, activite_texte, courtier_actif, droits_agents, derniers_usages, agent_du_dossier, lignes_neuves, lire_conso_claude, lire_conso_codex, collecter_conso, quand_remise, quota_moteurs, kilo, derniere_action, lien_regle, documents_a_lire, lus, genre_document, titre_document, documents, livrables, rendre_markdown, carte_colonne, seg, ligne_texte, cartes_donnees, propre, gravite, etat_source, alertes_synthese, depuis, question_en_attente, decision_document_resolue, propositions_decidables, decisions, dossier_checklists, agent_court, statuts_donnees, checklist_donnees, quand_iso, id_document

Les constantes qui accompagnent ces fonctions (couleurs, `STATUTS`, `TONS`, `LECTEURS_CONSO`, `PANNEAUX_SOURCES`…) ont suivi leurs fonctions ; la liste des noms publics est `noyau/api.py`. Trois noms de `noyau/lectures.py` (`alertes_moteurs`, `masques`, `cloisons`) ne sont que des points de branchement posés par `bin/berger`.

## Lot 2 : `bin/moteurs/` (taille de `bin/berger` : 4 944 → 4 664 lignes ; cliquet 4 670)

Déplacement pur, aucun comportement changé. Un fichier par moteur ; ce qui vaut pour tous reste dans `moteurs/__init__.py`.

**Fonctions déplacées**
- `moteurs/__init__.py` (de `bin/berger`) : `CONTRATS`, `DELAI_CONTRAT`, `GRACE_CONTRAT`, `_VERSIONS`, `executable_moteur`, `version_moteur`, `fichier_contrat`,
  `verdict_moteur`, `jouer_contrat`, `moteur_admis`, `signaler_non_admis`, `choisir_moteur`, `alertes_moteurs`, `args_moteur`. `MOTEURS` n'est plus écrit en dur :
  c'est la liste des moteurs chargés (ordre `ORDRE`). Nouveaux : `charger`, `brancher`, `module`, `ecartes`, `MODULES`, `MOTEURS_REFUSES`.
- `moteurs/claude.py` : `_args_moteur` (branche Claude, devenue `args`), `abonnement_claude`, `ABONNEMENTS_CLAUDE`, `lire_conso_claude` (de `noyau/lectures.py`).
- `moteurs/codex.py` : `_args_moteur` (branche Codex, devenue `args`), `ecrire_profil_ouvert`, `lire_conso_codex` (de `noyau/lectures.py`), `CODEX_OUVERTURE_DELAI`,
  `CODEX_RECEPTION_DELAI`, `CODEX_SCRUTATION`, `CODEX_MISSION_TENTATIVES`, `CODEX_TITRE_CONFIANCE`, `CODEX_OPTION_RESTREINTE`, `CODEX_OPTION_QUITTER`,
  `CODEX_VALIDATION_RESTREINTE`, `dialogue_confiance_codex`, `ecran_developpeur_codex`, `mission_codex_recue`, `attendre_developpeur_codex`, `remettre_mission_codex`.
- `noyau/lectures.py` : `LECTEURS_CONSO` est vide au départ et rempli au chargement des moteurs (un lecteur par moteur chargé) ; la ligne
  `noyau.lectures.alertes_moteurs = …` de `bin/berger` et le stub `alertes_moteurs` sont retirés : `alertes_synthese` lit `SOURCES_ALERTES` (le paquet moteurs y
  pose `alertes_moteurs`). `lire_conso_*` quittent l'API du module (`__all__`).
- `bin/berger` : appelle `moteurs.<nom>(…)` ; charge le paquet à chaque exécution (comme les vues, donc un test qui remplace une fonction ne touche que SA copie).

**Écarts à la spec**
- **Restent au cœur** (le mur, lot 4, cas 1) : `masques`, `cloisons`, `reglages_claude`, `reglages_strict_externe`, `config_codex`, `hooks_codex`, `FEATURES_CODEX_STRICT`,
  `env_codex`, `env_agent`, `env_tmp`, `fichiers_mcp` et la génération MCP. La spec rangeait `config_codex`/`reglages_claude`/`FEATURES_CODEX_STRICT` au lot 2 ;
  la mission du lot l'interdit (« tout calcul du mur reste au cœur »), et ces fonctions SONT ce calcul. Idem `confiance_claude`, `demarrer_agent`, `relancer`,
  `lancer`, `demander` (verbes, lots 3/4).
- **`verdict()` sans agent** : le contrat d'admission est par moteur et par version, pas par agent (`verdict_moteur(m)` n'a jamais pris d'agent) ; la spec écrivait `verdict(a)`.
- **Ce que le cœur prête aux moteurs** : `consigne_systeme`, `ecrire_mcp_claude`, `ecrire_reseau_claude`, `env_appelant`, `reglages_strict_externe`, `journal`, `notifier`,
  `AU_REPOS` restent dans `bin/berger` (lots 3/4) ; `bin/berger` les BRANCHE par `moteurs.brancher(…)` (liste nommée `COEUR_*`, refus d'un nom hors liste), comme
  `masques`/`cloisons` au lot 1. Une seule ligne à retirer quand ils partiront. Hors API des vues : `BASE_NOYAU` (`ouvert`, `externe`, `travail`, `CODEX_HOME`, `CONSO`,
  `lignes_neuves`, `agent_du_dossier`), que seuls les moteurs reçoivent.
- **`berger etat`** nomme les moteurs écartés (texte : « ⚠ moteur écarté : bin/moteurs/<x>.py — cause » ; JSON : `moteurs_ecartes`, ajouté au schéma `etat.schema.json`).
  Un moteur écarté n'est ni lancé ni remplacé : « moteur <x> écarté : <cause> » (`choisir_moteur`, `args_moteur`, `moteur_admis`).

**Tests dont seule la FORME d'accès change (même assertion)** : `argv-config` et `argv-prive` (la fonction extraite vit dans `bin/moteurs/codex.py` / `claude.py` /
`__init__.py` ; `transport` au lieu de `_transport` ; `demander` reçoit `moteurs=`), `codex-ouverture` (constantes et horloge de Codex patchées sur
`g['moteurs'].MODULES['codex']` ; le dialogue est lu dans `codex.py`), `mcp` et `mcp-trous` (`g["_args_moteur"](a, "claude")` devient `g["moteurs"].MODULES["claude"].args(a)` ;
`version_moteur`, `verdict_moteur`, `choisir_moteur`, `moteur_admis`, `jouer_contrat`, `alertes_moteurs`, `CONTRATS` et `notifier` sont lus/remplacés sur `g["moteurs"]` ;
les exécutions « vraies » prennent `…["moteurs"].__dict__`), `missions` et `tmp-par-agent` (`moteur_admis` remplacé sur `g["moteurs"]`), `sonde-codex-confiance`
(`args_moteur` par `g["moteurs"]`), `interface` (`$.moteurs_ecartes` fait partie des champs produits seulement quand un moteur est piégé, comme `vues_ecartees`),
`vitrine` (empreinte du manuel recalculée : le manuel est à jour), `taille-fichiers` (cliquet 4 950 → 4 670). Aucun test retiré ni affaibli.
**Ajoutés** (`tests/contrat-noyau.py`) : chaque moteur n'emploie que l'API, `BASE_NOYAU` et ce que le cœur prête ; chaque nom de `BASE_NOYAU` existe ; **moteur cassé écarté
et nommé** (erreur au chargement, contrat absent, deux fichiers de même `NOM`), les autres tournent, `choisir_moteur`/`args_moteur` refusent le moteur écarté,
`LECTEURS_CONSO` ne porte que les moteurs chargés.

## Lot 3 : `bin/commandes/` (taille de `bin/berger` : 4 664 → 4 439 lignes ; cliquet 4 445)

Déplacement pur, aucun comportement changé : mêmes verbes, mêmes options, mêmes textes d'erreur, mêmes sorties. `main()` ne connaît plus aucun verbe : il cherche dans le
registre de `bin/commandes/__init__.py` (`prive`, `lancer`, `inconnue`). Chaque famille déclare `FAMILLE`, `VERBES`, `AIDE`, `DROITS` ; le chargement est celui des vues et des moteurs
(une famille cassée est écartée et nommée, `berger etat` › « ⚠ commandes écartées », JSON `commandes_ecartees` ajouté au schéma `etat.schema.json` ; deux familles qui déclarent le
même verbe sont écartées TOUTES LES DEUX ; un verbe qui plante À L'APPEL écarte sa famille, nommée). Le paquet `bin/commandes/__init__.py` fait partie du cœur (comme `moteurs/__init__.py`) :
il n'est pas écartable.

**Règle de la relecture (28/10)** : une famille n'emploie QUE l'API du noyau et la bibliothèque standard. Le cœur ne lui prête rien (plus de `brancher`, plus de `COEUR_*`) et aucun nom privé du noyau
ne lui est montré (plus de `COMMANDES_NOYAU`). Tout verbe dont le code appelle une fonction du cœur reste dans `bin/berger` jusqu'au lot 4, et tout verbe qui touche aux identifiants, au mur,
au bac à sable ou aux réglages moteur aussi.

**Décompte** : 60 verbes mesurés sur `c2c38ed` (la spec en annonçait 58 : elle ne comptait pas `valider` et `refuser`, qui sont des verbes à part du `cmd in (…)` de l'ancien `main()`).
**2 sont déplacés** (`livrable` dans `alire`, `veille` dans `veille`), **58 restent au cœur** et sont inscrits dans le MÊME registre par `bin/commandes/transition.py` (famille « transition », supprimée avec le lot 4).
Le premier jet en déplaçait 20 : la relecture l'a refusé (frontière de l'API contournée, verbes du lot 4 déplacés).

### Le tri, verbe par verbe (mission : « aucun verbe du lot 3 n'appelle le courtier, le mur, les droits ou le coffre »)

Méthode : graphe des appels de `bin/berger` (analyse syntaxique) ; pour chaque verbe, tout ce que son code et les fonctions qu'il appelle emploient, parmi les noms de l'API, de la bibliothèque standard, du noyau hors API et du cœur.
Un verbe dont la fermeture n'est pas contenue dans l'API reste au cœur ; la colonne « Pourquoi » dit ce qui l'en empêche.

| Verbe | Où | Pourquoi |
|---|---|---|
| livrable | `alire` | n'emploie que l'API (`documents`, `re`, `sys`) et `EXTENSIONS`, entré dans l'API |
| veille | `veille` | n'emploie que l'API (`agents`, `herdr_ids`, `statut_herdr`, `ECHANGES`, `AGENTS`…) et `LECTURES`, entré dans l'API |
| etat, vue, vues, panneau, titres | cœur | appellent `VUES`/`VUES_REFUSEES`, `enveloppe`, `SCHEMAS`, `moteurs`, `commandes`, `mettre_a_jour_titres` (cœur) |
| statusline | cœur | `badge` (couleur de l'agent), partagé avec `etat` qui reste ; `CONSO` hors API |
| lire | cœur | `lire_document` et `lire_interactif` (cœur, partagés avec d'autres appelants) |
| **abonnement-claude** | cœur | lit et réécrit le fichier d'identifiants complet (`moteurs/claude.py`) : identifiants, lot 4 |
| **reprendre** | cœur | `demarrer_agent` : contrôle du bac à sable puis arguments moteur qui écrivent les réglages du mur et du MCP |
| **relancer** | cœur | `demarrer_agent` (même raison) |
| reveil, tache, notifier | cœur | fonctions du cœur (`reveil`, `tache`, `notifier`) partagées avec le planificateur et la supervision |
| refaire-espace, espace-voulu | cœur | placement des onglets : `onglet*`, `espace_voulu`, `enveloppe`, `SCHEMAS`, `ONGLETS_BERGER` (cœur) |
| noter, memoire, validations | cœur | `journal`, `enveloppe`, `SCHEMAS`, `MEMOIRE_MAX` (cœur) ; `fichier_memoire`, `memoire_dossier` hors API |
| **planificateur** | cœur | appelle `sauvegarder` (archive chiffrée), `secrets_audit_silencieux` (audit) et `entretien` (coffre) |
| **superviser** | cœur | `rouvrir` → `ouvrir_en_mission` (missions) ; `alerter` → `echange` |
| **entretien** | cœur | `coffre_sauvegarder` (purge des copies chiffrées du coffre) |
| **espace** | cœur | `message_remettre` (remet les messages en attente : le verbe d'écriture `ecrire`) |
| **nouveau, regenerer, agent** | cœur | `ecrire_regles`, `masques`, `cloisons`, `reglages_claude`, `config_codex`, `hooks_codex`, MCP, `lier_skills` ; `agent` contrôle aussi `DROITS` et `valeurs_coffre` |
| **web** | cœur | utilise `COFFRE` (session du coffre, `coffre sauvegarder avant-session-web`) et le courtier |
| **interface** | cœur | crée et affiche le jeton d'authentification et la clé privée TLS (gestion des secrets, cas 1 de la règle de go) |
| **valider, refuser** | cœur | écrivent la décision que le courtier exécute (règles de validation) |
| lancer, demander, moteur, parler, parler-interactif, args, courtier, mcp-enveloppe, crochet-equipe | cœur | lot 4 (moteur lancé avec le mur, courtier, MCP) |
| mission, suivi, rapport-mission, fin-mission, message-deposer, message-remettre, annonce-outil, besoin, besoin-ranger, delegation-suivi, echange, equipe, projet | cœur | lot 4 (missions, messages, besoins, équipes) |
| installer, restaurer, sauvegarder, verifier-sauvegarde, verifier-depot, secrets, coffre | cœur | lot 4 (dépôt, sauvegarde, secrets, coffre) |

### Fonctions déplacées de `bin/berger` vers `bin/commandes/`

- `alire.py` : `BRUT_MAX`, `livrable_brut`.
- `veille.py` : `VEILLE_REGROUPE`, `VEILLE_PAS`, `VEILLE_STATUTS`, `VEILLE_APPELS`, `empreinte_veille`, `veille`.
- Le corps de chaque verbe (les anciens `elif cmd == …` de `main()`) devient une fonction `verbe_<nom>(args, prive=False)` : dans sa famille pour les deux verbes déplacés, dans `bin/berger` pour les 58 autres (même corps, mot
  pour mot), regroupées dans `VERBES_COEUR`, que `bin/berger` donne à `commandes.charger` et que `transition.py` inscrit. Une fonction de verbe rend `NotImplemented` quand la forme demandée n'est pas la sienne
  (les `elif cmd == "x" and args[:1] == [...]` de l'ancien code) : `main()` répond « commande inconnue » comme avant.

### Écarts à la spec

- **Deux noms entrent dans l'API du noyau : `LECTURES` et `EXTENSIONS`** (groupe « Lectures », noyau/lectures.py). Ils sont nécessaires aux deux verbes déplacés ; chacun a son test (`contrat-noyau` : existence et pas de doublon). C'est la seule
  extension de l'API, et elle vaut aussi pour les vues (elles ne l'emploient pas).
- **`transition` est la seule famille qui reçoit quelque chose du cœur** : `VERBES_COEUR`, le registre de ses propres verbes, qu'elle ne fait qu'inscrire. Elle n'est jamais écartée à l'appel (ses refus sont ceux de `bin/berger`).
- **Un verbe qui plante à l'appel écarte sa famille** (`commandes.ecarter`) : elle est nommée dans le message et dans `commandes_ecartees` du même processus. Un processus `berger` ne dure que le temps d'une commande : la cause
  n'est donc visible dans `berger etat` que si l'état est lu dans ce processus ; ailleurs, le même défaut est écarté à chaque appel.
- **Le seul tri qui change vers le haut est `reprendre`, `relancer`, `abonnement-claude`** (voir ci-dessus) ; ceux de la spec rangés dans « affichage », « espaces », « memoire » restent au cœur faute d'être autonomes.
- **Aucun chemin recalculé.** Les trois endroits de `bin/berger` qui se repèrent par `__file__` appartiennent à des verbes ou des fonctions restés au cœur.
- **Lignes vides.** 240 lignes vides résiduelles (suites de 4 lignes vides et plus, laissées par les déplacements des lots 1 et 2) sont retirées de `bin/berger` : c'est la part du cliquet qui ne vient pas du déplacement
  (4 664 → 4 439 ; sans elles, 4 679 : les 58 fonctions de verbe prennent la place de l'ancien `main()`).
- **`berger aide`** garde sa docstring telle quelle ; chaque verbe a en plus sa ligne d'`AIDE`, d'où elle sera composée quand le lot 4 aura fait disparaître la docstring unique.
- **`cas_go`** vaut `None` pour tous les verbes : le lot 3 ne touche aucun des cinq cas ; le lot 4 les qualifiera verbe par verbe.

### Tests dont seule la FORME d'accès change (même assertion)

- `installer-master` et `vitrine-readme` : « le verbe existe dans `bin/berger` » lisait les `cmd == "…"` de `main()` ; il lit maintenant les verbes DISPATCHÉS du registre (`_produit.verbes_declares` : clés de `VERBES`
  des familles et de `VERBES_COEUR`, recoupées avec les clés d'`AIDE` : une aide seule ne suffit pas, un verbe sans aide non plus).
  `interface` : `$.commandes_ecartees` fait partie des champs produits seulement quand une famille est piégée (comme `moteurs_ecartes`). `vitrine` : l'empreinte du manuel est recalculée (le manuel est à jour, règle 7).
  `taille-fichiers` : cliquet 4 670 → 4 445.
- Les autres suites (`affichage`, `reprise`, `roles`, `temps-reel`, `decisions`, `argv-cli`, `argv-prive`, `_jeu_vues`) retrouvent leur forme d'avant le lot 3 : leurs verbes sont restés au cœur.
- Aucun test retiré ni affaibli. **Ajoutés** : `tests/commandes-couverture.py` (les 60 verbes figés = l'union des `VERBES`, une `AIDE` et des `DROITS` par verbe, `AIDE` = `VERBES`, aucun doublon, tableau du manuel = registre,
  `abonnement-claude`, `reprendre` et `relancer` au cœur, entrée privée déclarée avec le message d'avant pour `mission`, `message-deposer`, `equipe`, `projet`, verbe et forme inconnus inchangés) et, dans `tests/contrat-noyau.py`,
  « API seule » pour chaque famille (aucune liste d'emprunt dans le paquet), la famille cassée / sans contrat / en doublon écartée et nommée, la famille dont un verbe plante à l'appel écartée et nommée, les autres qui tournent.

## Lot 3 bis : les commandes sans risque redéplacées (28/10/2026 ; taille de `bin/berger` : 4 439 → 4 224 lignes ; cliquet 4 230)

Dans le go « lots 1-3 » du 27/10, après le lot 3 installé (`845f2d1`). But : redéplacer dans `bin/commandes/` les commandes sans risque, **sans aucune exception à l'API du noyau**.
Déplacement pur : mêmes verbes, mêmes options, mêmes textes, les corps des `verbe_*` sont ceux de `main` mot pour mot.

### 1. Mesure : les noms du cœur dont chacun des 58 verbes de `transition.py` a besoin

Méthode : graphe des appels de `bin/berger` (analyse syntaxique, sur `845f2d1`). Pour chaque verbe : la fermeture de ce qu'appelle sa fonction (directement ou par une autre fonction du cœur) ; sont comptés les noms
définis dans `bin/berger` et les noms du noyau hors API. Les noms de l'API, la bibliothèque standard et les builtins ne comptent pas. La colonne « Chemin » est le chemin du point 2 que le verbe emprunte (« aucun » : la fermeture ne
passe par aucun). La liste est tronquée ; le compte est complet.

| Verbe | Noms du cœur | Les premiers | Chemin | Verdict |
|---|---|---|---|---|
| abonnement-claude | 2 | _spec_moteurs, moteurs | identifiants | cœur (lot 4) |
| agent | 138 | AU_REPOS, CLES_AGENT, CLES_ESPACE, CLES_INTERDITES, DOMAINE, DOMAINES_MAX, DROITS … (+131) | droits, coffre, mur | cœur (lot 4) |
| annonce-outil | 39 | DOMAINE, DOMAINES_MAX, PORTES_OUTIL, _spec_moteurs, _tete_regles, a_l_outil, annonce_outil … (+32) | messages (consignes d'outil) | cœur (lot 4) |
| args | 14 | TMP_AGENTS, _BAC, _spec_moteurs, bac_a_sable_ok, env_tmp, exiger_bac_a_sable, moteurs … (+7) | demarrer_agent, réglages moteur | cœur (lot 4) |
| besoin | 22 | MEMOIRE_MAX, SCHEMAS, VUES_REFUSEES, _opt, _spec_commandes, _spec_moteurs, besoin_clore … (+15) | besoins | cœur (lot 4) |
| besoin-ranger | 8 | besoin_ranger, echange, message_deposer, message_remettre, solliciter, BESOINS, SOLLICITATIONS … (+1) | besoins | cœur (lot 4) |
| coffre | 2 | coffre_sauvegarder, COFFRE | coffre | cœur (lot 4) |
| courtier | 30 | FERMETURE, INSTALLATIONS, MEMOIRE_MAX, SCHEMAS, VUES_REFUSEES, _opt, _spec_commandes … (+23) | courtier | cœur (lot 4) |
| crochet-equipe | 3 | lancer_crochet_equipe, _transport, developpeur | équipes | cœur (lot 4) |
| delegation-suivi | 5 | delegation_suivi, message_deposer, message_remettre, solliciter, SOLLICITATIONS | messages, courtier | cœur (lot 4) |
| demander | 21 | TMP_AGENTS, TMP_COMMUN, TMP_MAX, _BAC, _opt, _spec_moteurs, bac_a_sable_ok … (+14) | demarrer_agent, réglages moteur | cœur (lot 4) |
| echange | 1 | echange | messages (courtier, outils d'équipe) | cœur (lot 4) |
| entretien | 9 | coffre_sauvegarder, entretien, journal, notifier, COFFRE, HERDR, NOTIFY_SEND … (+2) | coffre, sauvegarde | cœur (lot 4) |
| equipe | 168 | CLES_ESPACE, DOMAINE, DOMAINES_MAX, ESPACES, ESPACE_VIDE, FEATURES_CODEX_STRICT, FICHIERS_MCP … (+161) | équipes | cœur (lot 4) |
| espace | 46 | CLES_ESPACE, ESPACES, ICONES_ONGLETS, ONGLETS_BERGER, TMP_AGENTS, TMP_COMMUN, TMP_MAX … (+39) | messages (message_remettre), demarrer_agent | cœur (lot 4) |
| espace-voulu | 28 | CLES_ESPACE, DELAI_SANS_OBJET, ESPACES, ICONES_ONGLETS, REGLES_ESPACE, SCHEMAS, _date_dans_nom … (+21) | équipes (chefs, developpeurs_ouverts) | cœur (lot 4) |
| etat | 12 | MEMOIRE_MAX, SCHEMAS, VUES_REFUSEES, _spec_commandes, _spec_moteurs, commandes, donnees_etat … (+5) | aucun | **déplacé** → `etat` |
| fin-mission | 18 | SCHEMAS, _git, _opt, agent_dans, arreter_agent, chefs, echange … (+11) | missions | cœur (lot 4) |
| installer | 22 | INSTALLATIONS, MEMOIRE_MAX, SCHEMAS, VUES_REFUSEES, _spec_commandes, _spec_moteurs, commandes … (+15) | installation | cœur (lot 4) |
| interface | 115 | CERTIFICAT_INTERFACE, CLES_ESPACE, CLE_INTERFACE, DOMAINE, DOMAINES_MAX, DOSSIER_TLS, ESPACE_VIDE … (+108) | identifiants (jeton, clé TLS) | cœur (lot 4) |
| lancer | 23 | TMP_AGENTS, TMP_COMMUN, TMP_MAX, _BAC, _spec_moteurs, bac_a_sable_ok, confiance_claude … (+16) | demarrer_agent | cœur (lot 4) |
| lire | 4 | VUES, lire_document, lire_interactif, marquer_lu | aucun | **déplacé** → `alire` |
| mcp-enveloppe | 42 | FICHIERS_MCP, NAVIGATEUR_WEB, NOM_SECRET, PORT_WEB, PROTEGES_MCP, REGLAGES_PASSES, SERVEURS_MCP … (+35) | mur (MCP), courtier | cœur (lot 4) |
| memoire | 6 | MEMOIRE_MAX, journal, memoire_appliquer, memoire_verifier, fichier_memoire, memoire_dossier | écriture de MEMORY.md, que l'agent ne peut pas écrire, avec sauvegarde .avant | cœur (lot 4) |
| message-deposer | 4 | message_deposer, message_remettre, solliciter, SOLLICITATIONS | messages | cœur (lot 4) |
| message-remettre | 1 | message_remettre | messages | cœur (lot 4) |
| mission | 59 | CLES_ESPACE, ESPACES, ICONES_ONGLETS, ONGLETS_BERGER, TMP_AGENTS, TMP_COMMUN, TMP_MAX … (+52) | missions | cœur (lot 4) |
| moteur | 22 | TMP_AGENTS, TMP_COMMUN, TMP_MAX, _BAC, _spec_moteurs, bac_a_sable_ok, confiance_claude … (+15) | demarrer_agent | cœur (lot 4) |
| noter | 1 | journal | aucun | **déplacé** → `journal` |
| notifier | 3 | notifier, HERDR, NOTIFY_SEND | aucun | **déplacé** → `bureau` |
| nouveau | 96 | CLES_ESPACE, DOMAINE, DOMAINES_MAX, ESPACE_VIDE, FEATURES_CODEX_STRICT, FICHIERS_MCP, NAVIGATEUR_WEB … (+89) | mur (masques, cloisons, réglages) | cœur (lot 4) |
| panneau | 115 | CLES_ESPACE, DOMAINE, DOMAINES_MAX, ECRAN_NORMAL, ECRAN_PANNEAU, ESPACE_VIDE, FEATURES_CODEX_STRICT … (+108) | mur et coffre, par les fiches du cœur | cœur (lot 4) |
| parler | 4 | echange, parler, solliciter, SOLLICITATIONS | messages | cœur (lot 4) |
| parler-interactif | 4 | echange, parler, solliciter, SOLLICITATIONS | messages | cœur (lot 4) |
| planificateur | 201 | AU_REPOS, CADENCE_ESPACE, CLES_ESPACE, DELAI_SANS_OBJET, DOMAINE, DOMAINES_MAX, ESPACES … (+194) | sauvegarde, audit, coffre | cœur (lot 4) |
| projet | 102 | CLES_ESPACE, DOMAINE, DOMAINES_MAX, ESPACE_VIDE, FEATURES_CODEX_STRICT, FICHIERS_MCP, NAVIGATEUR_WEB … (+95) | équipes | cœur (lot 4) |
| rapport-mission | 1 | rapport_mission | missions | cœur (lot 4) |
| refaire-espace | 30 | CLES_ESPACE, ESPACES, ICONES_ONGLETS, ONGLETS_BERGER, colonne_travail, commande_element, commande_onglet_berger … (+23) | équipes (domaine_travail) | cœur (lot 4) |
| refuser | 4 | _opt, decider, file_tenue_texte, module_web | droits (règles de validation), courtier | cœur (lot 4) |
| regenerer | 95 | CLES_ESPACE, DOMAINE, DOMAINES_MAX, ESPACE_VIDE, FEATURES_CODEX_STRICT, FICHIERS_MCP, NAVIGATEUR_WEB … (+88) | mur (masques, cloisons, réglages) | cœur (lot 4) |
| relancer | 32 | AU_REPOS, RELANCE_EN_ATTENTE, TMP_AGENTS, TMP_COMMUN, TMP_MAX, _BAC, _spec_moteurs … (+25) | demarrer_agent | cœur (lot 4) |
| reprendre | 45 | CLES_ESPACE, ESPACES, ICONES_ONGLETS, ONGLETS_BERGER, SHELLS, TMP_AGENTS, TMP_COMMUN … (+38) | demarrer_agent | cœur (lot 4) |
| restaurer | 2 | phrase_sauvegarde, restaurer | sauvegarde | cœur (lot 4) |
| reveil | 110 | CLES_ESPACE, DOMAINE, DOMAINES_MAX, ESPACE_VIDE, FEATURES_CODEX_STRICT, FICHIERS_MCP, NAVIGATEUR_WEB … (+103) | demarrer_agent, bac à sable, coffre | cœur (lot 4) |
| sauvegarder | 6 | notifier, phrase_sauvegarde, sauvegarder, COFFRE, HERDR, NOTIFY_SEND | sauvegarde | cœur (lot 4) |
| secrets | 5 | secrets_audit, valeurs_coffre, COFFRE, externe, travail | audit, coffre | cœur (lot 4) |
| statusline | 4 | COULEURS_BADGE, badge, statusline, CONSO | aucun | **déplacé** → `bureau` |
| suivi | 2 | agent_vivant, suivi | missions | cœur (lot 4) |
| superviser | 80 | AU_REPOS, CLES_ESPACE, ESPACES, ICONES_ONGLETS, ONGLETS_BERGER, RELANCE_EN_ATTENTE, RELANCE_MIN … (+73) | missions, messages | cœur (lot 4) |
| tache | 26 | TMP_AGENTS, TMP_COMMUN, TMP_MAX, _BAC, _spec_moteurs, bac_a_sable_ok, demander … (+19) | demarrer_agent, bac à sable | cœur (lot 4) |
| titres | 5 | _LIBELLES, libelles_espaces, mettre_a_jour_titres, titre_herdr, pendants | aucun | **déplacé** → `bureau` |
| validations | 3 | SCHEMAS, enveloppe, validations | aucun | **déplacé** → `etat` |
| valider | 4 | _opt, decider, file_tenue_texte, module_web | droits (règles de validation), courtier | cœur (lot 4) |
| verifier-depot | 3 | verifier_depot, COFFRE, COFFRE_DEFAUT | audit | cœur (lot 4) |
| verifier-sauvegarde | 8 | empreinte, phrase_sauvegarde, restaurer, verifier_sauvegarde, CODEX_HOME, COFFRE, RESULTATS … (+1) | sauvegarde | cœur (lot 4) |
| vue | 4 | VUES, VUES_REFUSEES, commande_vue, enveloppe | **mur** : `vue fiche <agent> --json` → `m.donnees(a)` (appel dynamique) → `vues/fiche.py` → `RUBRIQUES_FICHE` → `identite_donnees` → `masques(a)` (branché sur le cœur, crée le dossier parent du coffre). La première mesure ne suivait pas cet appel dynamique (corrigé, relecture du 28/10) | cœur (lot 4) |
| vues | 3 | VUES, VUES_REFUSEES, liste_vues | aucun | **déplacé** → `vues` |
| web | 3 | web_commande, COFFRE, _transport | coffre, courtier | cœur (lot 4) |

### 2. Tri

Un verbe reste au cœur, jusqu'au lot 4, s'il passe, même indirectement, par `demarrer_agent`, le courtier, le mur (masques, cloisons, bac à sable, réglages moteur, MCP), les fichiers d'identifiants, le coffre, les droits, les
missions, les messages ou besoins, les équipes, l'installation, la sauvegarde ou l'audit. **50 restent, 8 sont déplacés** (`etat`, `validations`, `vues`, `titres`, `statusline`, `notifier`, `noter`, `lire`) ; en plus des deux
du lot 3 (`livrable`, `veille`), 10 des 60 verbes sont donc dans une famille.

Deux jugements à connaître :
- **`memoire` reste au cœur** : il écrit `MEMORY.md` (que l'agent ne peut pas écrire lui-même) et en fait une copie `.avant-…` (une sauvegarde) ; c'est le chemin « droits / sauvegarde ». Il rejoindra sa famille au lot 4.
- **`notifier` et `validations` restent hors des chemins du point 2** : `notifier` écrit `courtier/notifications.log` et appelle `notify-send` / `herdr notification` (aucun appel au courtier) ; `validations` lit
  `courtier/validations/*.json` par `en_attente` (déjà dans l'API, lecture seule) et n'écrit rien. `valider` et `refuser` (qui écrivent la décision que le courtier exécute) restent, eux, au cœur.

### 3. API : dix noms ajoutés, chacun avec son test

| Nom | Défini dans | Employé par | Passe avec lui (hors API) |
|---|---|---|---|
| `journal` | `noyau/agents.py` | `noter` (`journal`) | |
| `liste_vues` | `noyau/registre.py` | `vues` | `VUES`, `VUES_REFUSEES` y passent, sans entrer dans l'API (liste des métadonnées : aucun appel `donnees()`) |
| `Refus` | `noyau/ecarts.py` | `noter`, `notifier` (famille `journal`, `bureau`) | classe : le refus d'usage voulu, déclaré dans `PASSE` |
| `etat`, `validations` | `noyau/ecrans.py` | `etat`, `validations` | `donnees_etat` |
| `lire_document`, `lire_interactif` | `noyau/ecrans.py` | `lire` (famille `alire`) | `marquer_lu` |
| `notifier`, `mettre_a_jour_titres`, `statusline` | `noyau/bandeaux.py` | `notifier`, `titres`, `statusline` (famille `bureau`) | `badge`, `titre_herdr`, `libelles_espaces` |

Test (`tests/contrat-noyau.py`, section 1d) : pour chaque nom, il est défini dans son module du noyau, listé dans l'API, employé par la famille indiquée, **absent du cœur** (déplacé, pas copié), et sa fermeture d'appels dans le
noyau ne contient aucun des noms d'`INTERDITS` (`demarrer_agent`, `COFFRE`, `masques`, `cloisons`, les réglages moteur et MCP, la remise de messages, `decider`, la sauvegarde, l'installation…). Les trois nouveaux modules du noyau
ne citent aucun nom du cœur. `journal` et `notifier` ne sont plus *prêtés* aux moteurs par `moteurs.brancher` : ils viennent de l'API (le cœur ne leur prête plus que `consigne_systeme`, `ecrire_mcp_claude`, `ecrire_reseau_claude`, `env_appelant`, `reglages_strict_externe` et `AU_REPOS`).

### 4. Déplacement

Quatre familles neuves et une famille complétée, **une famille par fichier**, aucune exception à l'API (`tests/contrat-noyau.py`, section 1c, « API seule » pour chacune) :
`etat` (`etat`, `validations`), `vues` (`vues`), `bureau` (`titres`, `statusline`, `notifier`), `journal` (`noter`), `alire` (`livrable` + `lire`). Les entrées de `transition` et de `VERBES_COEUR` correspondantes sont retirées.
Les fonctions déplacées de `bin/berger` vers `bin/noyau/` :
- `ecarts.py` (neuf, sans import) : `VUES`, `VUES_REFUSEES`, `MOTEURS_REFUSES`, `COMMANDES_REFUSEES`.
- `registre.py` : `SCHEMAS`, `enveloppe`, `liste_vues`, `ecartes_moteurs`, `ecartes_commandes` (et re-export des quatre dictionnaires).
- `ecrans.py` : `donnees_etat`, `etat`, `validations`, `marquer_lu`, `lire_document`, `lire_interactif`.
- `bandeaux.py` : `COULEURS_BADGE`, `badge`, `statusline`, `notifier`, `titre_herdr`, `libelles_espaces`, `mettre_a_jour_titres`.
- `agents.py` : `journal`, `MEMOIRE_MAX`.

### Écarts à la spec

- **Les registres d'écarts sont dans le noyau.** `berger etat` lisait `moteurs.ecartes()` et `commandes.ecartees()` ; une famille ne peut pas importer ces paquets (cœur). Les dictionnaires `MOTEURS_REFUSES` et
  `COMMANDES_REFUSEES` (et `VUES`, `VUES_REFUSEES`) sont donc définis dans `noyau/ecarts.py` (aucun import : `bin/commandes/` se charge toujours sans lire `config.toml`, comme les tests de forme d'accès le font), re-exportés par `noyau/registre.py`, et `bin/moteurs/` et `bin/commandes/` y écrivent (même objet : `moteurs.MOTEURS_REFUSES` et `commandes.COMMANDES_REFUSEES` existent toujours). C'est le seul changement
  de code de `donnees_etat` : `ecartes_moteurs()` et `ecartes_commandes()` à la place des deux appels de paquet (même résultat).
- **Les refus d'usage voulus passent par une déclaration explicite.** Une famille peut déclarer `PASSE = {verbe: (exceptions,)}` : ce que ce verbe laisse sortir tel quel, comme avant son déplacement. `noter` et `notifier` lèvent
  `Refus` (sous-classe de `ValueError`, dans l'API ; seuls leurs `raise ValueError` d'usage deviennent `raise Refus`, le reste du corps est inchangé) ; `statusline` déclare `IndexError` (sans agent, l'`IndexError` d'avant,
  non interceptée). Toute autre exception, une `ValueError` ordinaire comprise, est un défaut : elle écarte la famille, nommée. Tests : `contrat-noyau`, section 5 (`zz_refus`, `zz_indexe`, `zz_interne`, `statusline`, `noter`), dans le MÊME processus que l'appel.
- **Les ValueError de refus venues du noyau (relecture du 28/10, second renvoi).** `entree_privee` (noyau/transport.py) levait une `ValueError` simple (« entrée privée trop grande », « entrée privée UTF-8 requise ») que `noter` laissait sortir ; sans
  déclaration, elle aurait écarté la famille `journal`. `entree_privee` lève maintenant `Refus` (sous-classe de `ValueError` : les appelants qui attrapent `ValueError`, dont `main()` et `notifier`, sont inchangés) ; `PASSE["noter"] = (Refus,)` la laisse sortir telle quelle.
  Test : `contrat-noyau`, section 5 (entrée non UTF-8 et entrée trop grande, dans le même processus, et en ligne de commande). **Recensement** : pour chacun des 8 verbes déplacés, tous les `raise` de la fermeture de leurs appels dans le noyau
  (et des appels `herdr(…, strict=…)`) ont été listés. Résultat : `etat`, `validations`, `vues`, `titres`, `statusline`, `lire` n'en ont **aucun** ; `noter` et `notifier` n'ont que ces deux de `entree_privee`
  (`notifier` les convertit déjà : `except ValueError` → `Refus`). Aucun autre cas. Les `ValueError` de `herdr_api(strict=True)` ne sont atteintes par aucun verbe déplacé (aucun n'appelle `strict`).
- **`VUES` et `VUES_REFUSEES` restent remplis par le cœur** (`charger_vues`), qui importe les mêmes dictionnaires depuis le noyau ; le chargeur lui-même reste au cœur (il touche `ICONES_ONGLETS`, `ONGLETS_BERGER`).
- **`MEMOIRE_MAX`** passe dans `noyau/agents.py` (avec `fichier_memoire`) : `donnees_etat` l'emploie ; `memoire_verifier` du cœur l'importe.
- **`vue` revient au cœur** (relecture du 28/10) : voir la ligne du tableau. **Fermeture du test** : elle suit désormais les noms absents du noyau et les appels dynamiques vers les vues (`m.donnees`, `m.rendre`, `VUES[x].vue_x`) ; deux cas de preuve (`commande_vue`, un appel direct à `demarrer_agent`) montrent qu'elle échoue là où elle doit.
- **Corps des verbes** : identiques à `845f2d1`, vérifié par comparaison, sauf les `raise Refus` de `noter` et `notifier`.

### Tests dont seule la FORME d'accès change (même assertion)

- `commandes-couverture` : les 60 verbes figés ne changent pas ; la répartition passe de 2 à 10 verbes en famille, de 58 à 50 en transition ; `memoire` et `vue` sont ajoutés aux verbes renvoyés au cœur ; le tableau du manuel est celui du registre.
- `taille-fichiers` : cliquet 4 445 → 4 230.
- `contrat-noyau` : la liste des modules du noyau importés pour vérifier l'API contient les trois nouveaux ; la liste des familles du produit s'allonge.
- **Ajoutés** : section 1d de `contrat-noyau` (dix noms, trois modules), cas `zz_refus` (section 5).
- **Correctif du 28/10 (lot 3 bis)** : `commandes.lancer` rend un `Refus` déclaré dans `PASSE` sous la forme d'une `ValueError` ordinaire de même message (la dernière ligne du diagnostic redevient `ValueError: …`, plus `noyau.ecarts.Refus: …`) ; `berger lire ²` (`isdigit()` vrai, `int()` faux) lève de nouveau la `ValueError` d'avant via `Refus` + `PASSE["lire"]`, sans écarter la famille `alire`. Les tests comparent le stderr réel de la ligne de commande (noter, notifier, lire, entrée privée).
