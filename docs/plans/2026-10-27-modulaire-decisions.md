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

## Correctif « contrat » (29/10/2026, avant le lot 4 ; relecture indépendante de Codex sur les lots 1 à 3)

Corrections fonctionnelles seulement, aucun déplacement de code. Chaque point : un test rouge, puis un commit `fix` avec sa cause racine.

1. **Contrat statique** (`tests/contrat-noyau.py`, section 1c bis) : tout nom importé devenait un nom permis (`from noyau.config import COFFRE` passait) et les portées
   étaient mélangées. Désormais, pour les vues, les familles de commandes et les moteurs : seuls la bibliothèque standard et `noyau.api` s'importent ; tout autre module du
   noyau, `import noyau.api` nu (il lie le paquet `noyau` entier), un module frère ou du cœur (`commandes.x`, `moteurs.claude`, `vues.y`, `interface`), un import relatif ou
   dynamique (`importlib`, `__import__`, `sys.modules`) et un attribut spécial (`f.__globals__`…) sont refusés ; les portées sont celles de Python (`symtable`). 18 fichiers
   jetables refusés, 8 acceptés. **Renvoi n° 77** (Codex, 7/10) : `sys.modules` passait par un alias (`from sys import modules`, `import sys as s`). Désormais l'attribut `modules`
   (et `_getframe`) est refusé sur tout objet, `from sys import modules` aussi, `getattr`/`setattr`/`hasattr` au nom calculé ou visant un de ces attributs aussi, et `vars`,
   `globals`, `locals`, `eval`, `exec`, `compile`, `__builtins__` sont refusés tout court (trop dynamiques). 30 refus, 11 acceptations. **Limite** : c'est un contrôle de relecture, pas une cloison (un `getattr` construit à l'exécution lui échappe) ; la frontière à l'exécution
   reste l'espace de noms donné au module (section 3).
2. **Moteur aux métadonnées invalides** (`bin/moteurs/__init__.py`, `charger`) : `NOM` (texte non vide), `ORDRE` (entier) et le lecteur de `lecteur_conso()` (appelé une seule
   fois) sont vérifiés dans l'interception ; le moteur fautif est écarté et nommé, les autres se chargent (section 4 bis).
3. **Écartement à l'appel** : rien ne le garde, chaque `berger` reconstruit le registre. **Choix : corriger le texte** (le plus simple qui reste juste ; une trace durable aurait
   ajouté un fichier d'état à écrire, relire et effacer). Le message dit « écartée pour cet appel seulement (rien n'est gardé : un nouveau `berger etat` ne la nomme pas) ».
4. **`AIDES` branché** : `berger aide` (et la suite de « commande inconnue ») = la docstring du cœur **inchangée**, puis « Commandes des familles (bin/commandes/) : » et la ligne
   d'`AIDE` de chaque verbe d'une famille chargée qu'elle ne documente pas. Aujourd'hui : `lire`, `notifier`, `statusline`, `titres`.

### Écarts au « déplacement pur » (relevés par Codex)

- **`SystemExit` dans les familles.** Les verbes déplacés gardent leurs `sys.exit(…)` (corps identiques) ; `commandes.lancer` ne les intercepte pas (`SystemExit` n'est pas une
  `Exception`) : ils sortent comme avant, et un `sys.exit` ne fait **jamais** écarter une famille, même s'il traduit un défaut. C'est voulu (un refus d'usage, `livrable` mal formé,
  `noter` sans `BERGER_AGENT`, `lire` sans numéro, termine le processus comme avant) ; la conséquence est que le registre ne voit pas une famille qui « sort » au lieu de lever.
  Sorties mesurées identiques à avant le lot 3 : `livrable <id> --brut` (forme et document inconnus), `noter --stdin` sans agent, `lire 99 --sans-pager`.
- **`Refus` levé par `entree_privee`** (`bin/noyau/transport.py`, lot 3 bis) : du code changé dans le noyau, pas déplacé. Pour les familles (`noter`, `notifier`), `lancer` le rend
  en `ValueError` de même message (inchangé). **Mais les verbes du cœur `demander` et `parler`**, qui lisent l'entrée privée sans l'attraper, finissaient sur `main` par
  « `noyau.ecarts.Refus: entrée privée …` » au lieu de « `ValueError: entrée privée …` ». **Corrigé ici** : la branche de transition de `lancer` fait la même conversion
  (test : `contrat-noyau`, section 5). La pile d'appels affichée au-dessus de la dernière ligne n'est plus la même (elle s'arrête à `lancer`, comme pour les familles).

### Sorties qui changent (mesurées : 20 commandes, avant le lot 3 `c2c38ed`, `main` et cette branche, dernière ligne d'erreur, code de sortie et sortie complète)

- `berger aide`, `-h`, `--help` et la suite de « commande inconnue » : **4 lignes de plus à la fin** (point 4) ; tout ce qui précède est identique.
- Écartement à l'appel : la **deuxième ligne** du message change (point 3) ; la première et le code de sortie non.
- `demander` / `parler --stdin`, entrée invalide : la dernière ligne **redevient** celle d'avant le lot 3.
- Aucune autre : `etat --json` (hors l'horodatage), `vues`, `vues --json`, `validations`, `statusline`, `noter`, `notifier`, `lire`, `livrable`, `mission` sans `--stdin`, `--stdin` invalide.

### Réservé au lot 4 (hors de cette demande)

Séparer l'API en lecture et action, les globales partagées entre le cœur et les modules, les `import *` du noyau.

## Lot 4a : les missions (29/10/2026 ; go du propriétaire n° 58, cas 1 ; taille de `bin/berger` : 4 237 → 4 194 lignes ; cliquet 4 194)

Premier des quatre sous-lots du lot 4 (4a missions, 4b messages et besoins, 4c équipes, 4d courtier, mur, secrets et dépôt), une demande de fusion chacun.
Cette demande ne contient QUE 4a. Déplacement pur : les corps sont ceux de `main` (5767d99), mot pour mot.

### Le tri, verbe par verbe

| Verbe | Où | Pourquoi |
|---|---|---|
| `mission` | `missions` | l'adaptateur (lecture des options) part dans la famille ; l'acte passe par le service `confier_mission` |
| `suivi` | `missions` | lecture seule : `suivi` (et `agent_vivant`) ne citent que des noms du noyau → `noyau/missions.py`, dans l'API de lecture |
| `rapport-mission` | `missions` | lecture seule : `rapport_mission` → `noyau/missions.py`, dans l'API de lecture |
| `fin-mission` | `missions` | l'adaptateur part dans la famille ; l'acte passe par le service `terminer_mission` |
| `delegation-suivi` | cœur (4b) | la spec le rangeait dans « missions » ; son code dépose un message (`message_deposer`, le verbe `ecrire`) : c'est 4b |

### Lecture et action séparées

- **Lecture** (`bin/noyau/missions.py`, groupe « Missions, lecture » de `noyau/api.py`) : `suivi`, `rapport_mission` ; `agent_vivant` les accompagne (hors API, le cœur
  l'importe par son nom). Dépendances nommées (`from noyau.agents import …`), aucun `import *` ; `bin/berger` les importe par leur nom.
- **Action** (`bin/noyau/actions.py`, liste `ACTIONS` de `noyau/api.py`) : `confier_mission(a, texte, par, moteur=None, modele=None)` et
  `terminer_mission(a, par, motif=None)`. Seules les familles de commandes les reçoivent (posés dans leur espace par le chargeur, `noyau.actions.services_commandes()` ; jamais pris dans les globales du
  cœur) ; une vue ou un moteur qui les cite est refusé par le contrat et ne les a pas dans son espace.
- **Le geste reste au cœur.** `mission` et `fin_mission` de `bin/berger` passent par `ouvrir_en_mission` → `demarrer_agent` (le mur, le bac à sable, les arguments
  stricts du moteur), `espace`, `parler`, `fermer_mission` → `arreter_agent` : rien de cela ne devient une fonction de famille. `bin/berger` les pose derrière les deux
  services au démarrage (`noyau.actions.brancher`, une ligne ; liste fermée : un nom hors `ACTIONS` → `NameError`, autre chose qu'une fonction → `TypeError`). Le
  branchement disparaît quand le lancement d'un agent quittera `bin/berger` (suite du lot 4).

### Les contrôles, ligne à ligne : aucun n'a bougé

Aucun garde-fou n'est déplacé ni recopié : chacun est resté dans la fonction qui le portait, et la famille n'en fait aucun (`tests/contrat-noyau.py`, 1f : la famille ne cite
ni `MISSIONS`, ni `missions_comptees`, ni `chefs`, ni `moteurs`, ni « MISSION.md », ni « max »).
- agent inscrit (`agent.conf`) ; une mission à la fois (`MISSION.md` existant, création exclusive `open("x")`) ; plafond `[missions] max` hors chef de projet ;
  moteur et modèle (`moteurs.decider_mission` → `noyau.modeles`, avant toute création) ; mission vide : dans `mission` (cœur), derrière `confier_mission`.
- pas de mission en cours ; checklist finie (« Terminé » / « Abandonné ») hors propriétaire ; refus de fusion du propriétaire (`refus_fusion_proprietaire`) ; motif tracé : dans
  `fin_mission` (cœur), derrière `terminer_mission`.
- droits entre agents (`mission:<agent>`, chef vers ses développeurs, coordinateur vers son chef), lecture seule, agent inconnu : dans le courtier (4d), inchangé.
- entrée privée obligatoire pour `mission` : `DROITS["mission"]["prive"]` de la famille (et retiré du tuple de `transition`).
Preuve : les services appelés SANS la famille refusent comme avant (`contrat-noyau`, section 6 : agent inconnu, mission en cours, plafond, moteur, modèle, checklist, sans mission).

### Écarts au « déplacement pur »

- **`PASSE` de la famille = `(IndexError, Refus, ErreurService)`** (renvoi de master du 29/10, après relecture de f0e4000 ; le propriétaire a déjà refusé une dispense
  générale, n° 55). Le premier jet déclarait `Exception` : plus aucune erreur n'aurait écarté la famille. Désormais : `noyau/actions.py` enveloppe ce qui sort du GESTE du cœur
  (une `Exception` ; `sys.exit` passe tel quel) dans `ErreurService` (`noyau/ecarts.py`, sans import ; dans l'API, groupe « refus d'usage », pour que la famille puisse la
  déclarer), l'origine gardée en cause (`raise … from e`) ; `commandes.lancer` ressort l'exception d'origine (`raise o from None`, un `Refus` d'origine redevient une
  `ValueError`), comme il le fait pour `Refus` : la dernière ligne d'erreur est celle d'avant. Une erreur DANS la famille hors service, ou dans une lecture (`suivi`,
  `rapport_mission`), écarte la famille, nommée, comme pour les autres familles. **Un nom de plus dans l'API** : `ErreurService` (test : `contrat-noyau`, 2 et 6).
- **`_opt` recopié** (une ligne) dans `commandes/missions.py` : le cœur le garde pour ses autres verbes ; une famille ne peut pas l'emprunter.
- **`cas_go` = `None`** pour les quatre verbes : confier, suivre, relire ou terminer une mission ne relève d'aucun des cinq cas de la règle de go (les droits sont au courtier).

### Sorties qui changent

Mesurées : `tests/equivalence-missions.py`, 40 scénarios sur une installation jetable, faux Herdr à état, mesurés sur `main` (5767d99, `git archive`) puis sur la branche :
code de sortie, sortie standard, dernière ligne d'erreur, fichiers écrits (`MISSION.md`, `historique/`, journal, `CHECKLIST.md`, `.herdr.json`, échanges, validations),
appels à Herdr, lancement strict (agent, moteur, panneau, arguments du moteur), transport privé (`--stdin` : JSON invalide, pas un tableau, imbriqué, UTF-8, plus d'un Mio),
plafond, droits entre agents par le courtier (sans droit, coordinateur vers un développeur, verbe inconnu, suivi, rapport, terminer, moteur et modèle refusés).
**0 écart.** Seule autre sortie changée : **`berger aide`** (et la suite de « commande inconnue ») a **2 lignes de plus** à la fin, celles de `mission` et `rapport-mission`
(la docstring du cœur ne les documente pas sous la forme `berger <verbe>`) : c'est le point 4 du correctif contrat (l'aide d'une famille paraît d'elle-même).

### Tests dont seule la FORME d'accès change (même assertion)

- `contrat-noyau`, section 2 : le programme qui vérifie que chaque nom de l'API existe importe aussi `noyau.missions`. Section 1c : les familles de commandes ont droit à l'API
  d'action (les vues et moteurs non). Section 1d : `suivi`, `rapport_mission` ajoutés aux noms vérifiés ; `missions` et `actions` aux modules du noyau qui ne citent aucun nom du cœur.
- `commandes-couverture` : 14 verbes en famille (4 de plus, famille `missions`), 46 au cœur (au lieu de 50). `taille-fichiers` : cliquet 4 237 → 4 194. `vitrine` : empreinte
  du manuel recalculée (règle 7).
- Inchangés et lus au même endroit : `coherences-vps` et `web-relais-mission` (`fin_mission`, `mission` lus dans `bin/berger`), `modeles-table` (`g["suivi"]`, importé par nom),
  `codex-ouverture`, `regles-espace`, `espace-auto` (`agent_vivant`, `ouvrir_en_mission`, `espace` remplacés dans les globales du cœur).
- **Ajoutés** : `contrat-noyau` 1f (API d'action, famille sans contrôle, 10 refus et 1 acceptation propres à 4a, une vue qui appelle un service refusée) et 6 (espaces à
  l'exécution, contrôles des services appelés seuls, `brancher` fermé, panne du cœur par un service qui ressort telle qu'avant sans écarter la famille, erreur dans la famille hors service qui l'écarte et la nomme, `IndexError` d'un argument manquant qui passe, famille missions cassée écartée et nommée, ses verbes inconnus, le reste tourne) ;
  `tests/equivalence-missions.py` et sa référence `tests/attendus/equivalence-missions.json`.

### Renvoi n° 83 (supervision de nuit, relecture Codex bloquante, 7/10)

- **Défaut corrigé : la séparation lecture / action était contournable.** `noyau/api.py` portait `actions()` : une vue (ou un moteur) pouvait écrire
  `from noyau.api import actions` puis `actions()["terminer_mission"](a, PROPRIETAIRE)`, le contrat acceptait l'import et l'action agissait (vérifié en rouge : la vue
  terminait la mission). Désormais `noyau/api.py` ne porte plus que la liste des NOMS (`ACTIONS`), aucun accès ; le seul accès est
  `noyau.actions.services_commandes()`, appelé par le chargeur de commandes (`bin/commandes/__init__.py`), qui pose les services dans l'espace de chaque famille
  (et vérifie `ACTIONS` = `NOMS`). Le contrat (`imports_interdits`) refuse, pour une vue, un moteur ET une famille (qui n'a rien à importer) : `from noyau.api import
  actions` (et `as`), `from noyau.api import *`, l'attribut `.actions` sous tout nom d'objet (`import noyau.api as x ; x.actions`, `from noyau import api ;
  api.actions`, un alias de l'alias), `getattr(…, "actions")`, et tout import de `noyau.actions` (règle déjà là : un module du noyau hors `noyau.api`).
  Tests : `contrat-noyau` 1f bis (9 accès × 3 rangs, rouges d'abord) et 6 (0) : `noyau.api` n'a plus d'accès, une vue réelle qui cherche l'action par `noyau.api`
  échoue (`AttributeError`) et ne termine rien.
- **Comment les attendus d'équivalence sont produits** (pour les régénérer et les vérifier) : option `--produire` de `tests/equivalence-missions.py`, sur un arbre de
  main 5767d99 (avant le lot 4a) :
  ```
  d=$(mktemp -d) && git archive 5767d99 | tar -x -C "$d" && python3 tests/equivalence-missions.py --produire "$d" tests/attendus/equivalence-missions.json
  ```
  Rejoué le 29/10 : fichier identique octet pour octet à celui du dépôt. Mesuré aussi sur main après « SHA figé » (`--mesurer`) : identique.
- **À finir en 4b et 4c (noté, pas traité ici)** : l'API dite « de lecture » expose encore des noms qui ÉCRIVENT ou agissent : `journal` (écrit le journal d'un agent),
  `notifier` (notification du bureau, `notifications.log`), `lire_document` / `lire_interactif` (marquent un document lu), `mettre_a_jour_titres` (renomme les panneaux
  Herdr), `etat` / `validations` (écrans, lecture, à confirmer). Ils y sont entrés au lot 3 bis pour des familles. La séparation globale (ces noms vers l'API d'action,
  réservée aux familles, ou leur sortie des vues) reste à faire dans les sous-lots suivants, avec son test.

## Lot 4b : les messages et les besoins (29/10/2026 ; go du propriétaire n° 58, cas 1 ; taille de `bin/berger` : 4 194 → 4 141 lignes ; cliquet 4 141, puis 4 137 après la fusion de `main` 1acc0ea)

Deuxième sous-lot du lot 4. Cette demande ne contient QUE 4b (ni les équipes, 4c, ni le courtier, le mur, les secrets ou le dépôt, 4d). Même méthode
que 4a : les corps des verbes sont ceux de ba46c43, mot pour mot, sauf les écarts listés plus bas ; les gestes restent au cœur, derrière des services.

### Le tri, verbe par verbe (relu dans `transition.py` et la spec)

| Verbe | Où | Pourquoi |
|---|---|---|
| `message-deposer` | `messages` | dépose dans la file de la cible (verbe `ecrire` du courtier) → service `deposer_message` ; entrée privée obligatoire (`DROITS`) |
| `message-remettre` | `messages` | remet la file (verrou, Herdr) → service `remettre_messages` |
| `delegation-suivi` | `messages` | laissé exprès en 4a : TODO.md de la cible et résumé déposé → service `suivre_delegation` |
| `demander` | `messages` | question en conversation neuve, bac à sable, bascule de moteur → service `poser_question` |
| `parler` | `messages` | remise Herdr et échange tracé → service `parler_agent` |
| `parler-interactif` | `messages` | lecture de la liste des agents (API : `agents`, `conf`), puis `parler_agent` |
| `echange` | `messages` | une ligne dans les échanges → service `tracer_echange` |
| `besoin` | `besoins` | liste : lecture `besoins` (API) ; clore : service `clore_besoin` |
| `besoin-ranger` | `besoins` | range, trace, dépose au gardien → service `ranger_besoin` |
| `annonce-outil` | `besoins` | consignes régénérées et message de service (la spec le range avec les besoins) → service `annoncer_outil` ; la régénération (`ecrire_regles`, réglages du mur) reste au cœur |
| `valider`, `refuser` | cœur (4d) | décision sur une validation : le courtier l'exécute (`decider`, file tenue) |
| `equipe`, `projet`, `crochet-equipe` | cœur (4c) | équipes de développement |

### Lecture et action séparées

- **Lecture** : `besoins` (déjà dans `noyau/lectures.py` depuis le lot 1) entre dans l'API, groupe « Lectures ». Aucune autre lecture n'était propre à ces verbes.
- **Action** : neuf services dans `bin/noyau/actions.py`, sur la liste fermée `ACTIONS` : `deposer_message(de, a, texte)`, `remettre_messages(a)`,
  `suivre_delegation(demandeur, cible, d)`, `poser_question(a, consigne, moteur=None, sortie=None)`, `parler_agent(a, message, moteur=None, de=None)`,
  `tracer_echange(de, a, genre, texte)`, `ranger_besoin(de, genre, texte)`, `clore_besoin(n, etat, suite, par=None)`, `annoncer_outil(o, premiere=False)`.
  Seules les familles de commandes les reçoivent, par leur chargeur (`services_commandes`), comme en 4a.
- **Le geste reste au cœur** : `message_deposer`, `message_remettre`, `delegation_suivi`, `demander`, `parler`, `echange`, `besoin_ranger`, `besoin_clore`,
  `annonce_outil` de `bin/berger`, branchés derrière les services au démarrage (`noyau.actions.brancher`, la même ligne qu'en 4a, liste fermée).
- `ErreurService` et `PASSE` restent limités comme en 4a : `PASSE` = `(IndexError, Refus, ErreurService)` pour chaque verbe, sans exception propre à un
  verbe (renvoi n° 89 : la `json.JSONDecodeError` de `delegation-suivi` en est retirée, voir écarts). Aucune dispense générale.

### `journal` et `notifier` : de l'API de lecture à l'API d'action

Ils écrivent (le journal du jour d'un agent ; `courtier/notifications.log`, le bureau et Herdr) : ils **passent dans `ACTIONS`** et sortent de `API`.
Ce sont des fonctions du NOYAU (`noyau/agents.py`, `noyau/bandeaux.py`), pas des gestes du cœur : `services_commandes()` les donne telles quelles
(importées au chargement des commandes, jamais à l'import de `noyau/actions.py`, qui se charge sans `config.toml`) ; ni enveloppe `ErreurService`, ni
branchement (`brancher` refuse ces deux noms). Une erreur sort donc exactement comme avant. Effet mesuré :
- **vues** : aucune ne les employait (analyse et contrat) ; elles ne les reçoivent plus, et une vue qui les cite est refusée (`contrat-noyau` 1g, 7) ;
- **moteurs** (`claude.py`, `codex.py`) : aucun ne les employait ; ils ne les reçoivent plus. `bin/moteurs/__init__.py` (noyau des moteurs, non écartable,
  hors contrat) les importait déjà du noyau par leur nom (`journal` pour la bascule, `notifier` pour un moteur non admis) : inchangé ;
- **familles** : `journal` (`noter`) et `bureau` (`notifier`) reçoivent les MÊMES fonctions, par l'API d'action ; aucune ligne de ces familles ne change.
Restent dans l'API de lecture, à finir en 4c/4d (noté au renvoi n° 83) : `lire_document` / `lire_interactif` (marquent un document lu),
`mettre_a_jour_titres` (renomme les panneaux Herdr), `etat` / `validations` (écrans).

### Les contrôles, ligne à ligne : aucun n'a bougé

Aucun garde-fou n'est déplacé ni recopié ; les familles n'en font aucun (`contrat-noyau` 1g : ni file, ni verrou, ni gardien, ni Herdr, ni moteur).
- droits entre agents `ecrire:<agent>`, `deleguer:<agent>`, délégation en chaîne, agent inconnu, texte vide ou trop long, secrets, **débit d'ecrire**
  (5 par heure, 20 par 24 h), lecture seule : dans le courtier, avant l'appel de berger (inchangé ; mesurés par l'équivalence, voie du courtier) ;
- besoin : désactivé, gardien seul pour liste et clôture, chaîne d'équipe, genre, longueur, secrets, doublon, plafond d'ouverts, débit : au courtier ;
- **transport privé** : `message-deposer` exige `--stdin` (`DROITS["message-deposer"]["prive"]` de la famille, retiré du tuple de `transition`) ; `demander` et
  `parler` lisent l'entrée privée (`entree_privee`, API) et refusent le texte positionnel, comme avant ;
- file de messages (écrite puis renommée, ordre, verrou par agent), remise sans repli « taper dans le panneau », agent sans panneau, sollicitation :
  dans `message_deposer`, `message_remettre`, `parler` (cœur) ;
- bac à sable et dossier temporaire d'un agent strict, admission du moteur, **bascule** sur l'autre moteur (`AGENT_PANNE`) : dans `demander` (cœur) ;
- gardien déclaré, numéro jamais réutilisé, état de clôture, « seul le gardien ou le propriétaire », besoin introuvable : dans `besoin_ranger`, `besoin_clore` ;
- consigne rangée, agents qui ont l'outil, régénération de leurs règles : dans `annonce_outil` ;
- **notifications** : `notifier` inchangé (fonction du noyau, sans contrôle) ; aucune notification n'est émise par ces verbes.
Preuve : les services appelés SANS la famille refusent comme avant (`contrat-noyau`, section 7 : agent inconnu, sans gardien, état inconnu, autre que le
gardien, besoin introuvable, agent sans panneau, consigne absente, panne de `demander`).

### Écarts au « déplacement pur »

- **`raise ValueError(…)` devient `raise Refus(…)`** dans `demander` et `parler` (6 lignes) : une `ValueError` ordinaire écarterait la famille ; `Refus`
  (déclaré dans `PASSE`) ressort de `commandes.lancer` en `ValueError` de même message. Dernière ligne d'erreur identique (mesurée). Même règle qu'au lot 3 bis
  pour `noter`, `notifier`, `lire`.
- **L'entrée de `delegation-suivi` et d'`echange --stdin` est lue par `_entree()`** (`commandes/messages.py`, renvoi n° 89). La première version
  laissait passer la seule `json.JSONDecodeError` (`PASSE`) ; or `json.loads` lève aussi une `ValueError` ordinaire (entier de plus de 4 300 chiffres) et
  une `RecursionError` (imbrication trop profonde), et `sys.stdin.read()` une `UnicodeDecodeError` (entrée non UTF-8) : avant, l'erreur d'origine ; dans
  la première version, la famille `messages` écartée (`SystemExit`). `_entree()` attrape `ValueError` et `RecursionError` **autour de la lecture et du
  décodage seulement**, et les porte par `ErreurService`, dont `commandes.lancer` ressort l'origine : dernière ligne d'erreur identique, famille servie.
  `PASSE` ne s'élargit pas (il se resserre : la `JSONDecodeError` propre au verbe est retirée) ; une `ValueError` ailleurs dans le verbe écarte toujours
  la famille (contrôlé). La docstring d'`ErreurService` nomme cette seule exception à « une erreur dans la famille n'est pas enveloppée ».
- **`parler-interactif`** : son ancien corps attrapait `ValueError`, `IndexError`, `EOFError` levées par `parler` ; derrière le service, elles arrivent en
  `ErreurService`. La famille ajoute `except ErreurService` qui imprime « annulé » si l'origine est l'une des trois, et ressort sinon. Une famille n'a pas
  droit à `__cause__` (attribut spécial refusé par le contrat) : **`ErreurService` porte l'origine dans `origine`** (`noyau/ecarts.py`, 3 lignes ;
  `noyau/actions.py` la pose). Sortie inchangée.
- **`_opt` recopié** (une ligne) dans `commandes/messages.py` et `commandes/besoins.py` : le cœur le garde pour ses autres verbes ; une famille ne
  l'emprunte pas à une autre.
- **`cas_go` = `None`** pour les dix verbes : déposer, remettre, suivre, demander, parler, tracer, ranger, clore, annoncer ne relèvent d'aucun des cinq cas
  (les droits sont au courtier).
- La conversion `Refus` → `ValueError` de la branche de transition de `commandes.lancer` (correctif contrat) ne sert plus à aucun verbe du cœur (seul `main`
  lit encore l'entrée privée, et la rend lui-même en `ValueError`) : elle reste, inoffensive, et disparaît avec `transition`.

### Sorties qui changent

Mesurées : `tests/equivalence-messages.py`, **86 scénarios** sur une installation jetable, mesurés sur ba46c43 (avant le lot 4b) puis sur la branche :
code de sortie, sortie standard, dernière ligne d'erreur, fichiers écrits (file de messages `attente/` et `remis/`, `TODO.md`, journal, échanges, besoins
ouverts et clos, consignes régénérées par empreinte, débits du courtier, sollicitations), appels à Herdr (faux Herdr à état ; l'API de remise
`agent.prompt` doublée dans le processus, un vrai socket Unix n'étant pas permis dans tous les bacs), moteur lancé par `demander` (faux `claude` et
`codex` en tête du PATH : moteur de l'agent, `--moteur`, `--sortie`, panne simulée, moteur muet, les deux en échec), transport privé (`--stdin` : JSON
invalide, imbriqué, UTF-8, plus d'un Mio, texte positionnel), entrée illisible de `delegation-suivi` (JSON invalide, entier de 5 000 chiffres,
imbrication trop profonde, non UTF-8) et d'`echange --stdin` (non UTF-8), droits entre agents par le courtier (`ecrire` sans droit, avec droit, message vide,
**débit dépassé** ; `deleguer` sans droit, agent inconnu, avec droit : `demander` puis suivi), besoins par le courtier (rangé, liste, clôture par le
gardien). **0 écart.** Seule autre sortie changée : **`berger aide`** (et la suite de « commande inconnue ») a **7 lignes de plus** à la fin, celles de
`message-deposer`, `message-remettre`, `delegation-suivi`, `echange`, `parler-interactif`, `besoin-ranger`, `annonce-outil`, que la docstring du cœur ne
documente pas (point 4 du correctif contrat). L'équivalence relève donc, pour « commande inconnue », la PREMIÈRE ligne d'erreur.
Les attendus (`tests/attendus/equivalence-messages.json`) se produisent et se vérifient ainsi :
```
d=$(mktemp -d) && git archive ba46c43 | tar -x -C "$d" && python3 tests/equivalence-messages.py --produire "$d" tests/attendus/equivalence-messages.json
```
Rejoué le 29/10 : fichier identique octet pour octet à celui du dépôt ; deux mesures successives de la branche sont identiques.
**Renvoi n° 89** : l'instantané des fichiers normalisait tous les noms horodatés d'une file en `<HORODATAGE>.json` ; ils s'écrasaient dans le dictionnaire
et seul le dernier message restait, un message antérieur modifié ou supprimé pouvait passer inaperçu. Chaque file (`messages/attente/`, `messages/remis/`)
est désormais **la liste ordonnée de ses fichiers**, chacun gardé avec son contenu, leur nombre avec ; deux autres fichiers au même nom normalisé font une
erreur. Prouvé d'abord en rouge par `controler_instantane()` (joué à chaque comparaison : un message antérieur modifié, puis supprimé, doit faire un écart).
La pile citée par la `RecursionError` de `json.loads` (« used N kB », variable) est normalisée. Attendus régénérés par la même commande, sur ba46c43, avec
les 4 scénarios ajoutés : deux productions identiques octet pour octet ; la branche : 0 écart sur 86.
**Mise à jour depuis `main` (publication en ligne, 1acc0ea)** : `commun/REGLES.md` y change, donc la consigne générée `AGENTS.md` du scénario
« annonce-outil --premiere » (seul scénario qui diffère entre ba46c43 et 1acc0ea). La référence est reproduite sur 1acc0ea, `main` à jour et sans le
lot 4b (deux productions identiques octet pour octet ; la branche fusionnée : 0 écart sur 86) :
```
d=$(mktemp -d) && git archive 1acc0ea | tar -x -C "$d" && python3 tests/equivalence-messages.py --produire "$d" tests/attendus/equivalence-messages.json
```
Le cliquet de `bin/berger` suit la fusion : 4 141 → 4 137 (4 lignes de moins venues de `main`).

### Tests dont seule la FORME d'accès change (même assertion)

- `contrat-noyau` : 1c, la liste des familles du produit s'allonge (`missions`, `messages`, `besoins`) ; 1d, `journal` et `notifier` quittent `NOUVEAUX`
  (API de lecture) pour `NOUVELLES_ACTIONS` (1g), avec les MÊMES vérifications (défini dans son module du noyau, employé par sa famille, absent du cœur,
  fermeture sans chemin réservé au lot 4) plus « listé dans `ACTIONS`, absent de `API` » ; `besoins` entre dans `NOUVEAUX` ; 1f, `ACTIONS[:2]` au lieu de
  `ACTIONS` entier, et « chaque service est une fonction de `noyau/actions.py` » hors `journal`, `notifier` (fonctions du noyau, vérifiées en 1g) ;
  section 5, le libellé de `demander` / `parler` (famille `messages`), même assertion.
- `argv-cli` : `verbe_message_deposer` est lu dans `bin/commandes/messages.py` (il appelle le service `deposer_message`, doublé à la place de
  `message_deposer`) et ses `DROITS` viennent de la famille `messages` au lieu de `transition`. Mêmes assertions (commande JSON servie ; texte positionnel
  refusé, rien exécuté).
- `argv-prive` : `test_entree_demander`, `test_demander_sans_argument`, `test_refus_positionnel` inscrivent `demander` par sa famille (`bin/commandes/messages.py`,
  le VRAI `Refus` du noyau) au lieu de `transition`, et doublent le service `poser_question` au lieu de `demander`. Mêmes assertions (stdin CLI transmis,
  usage sans argument, texte positionnel refusé en `ValueError` sans appel).
- `commandes-couverture` : 24 verbes en famille (10 de plus, familles `messages` et `besoins`), 36 au cœur (au lieu de 46). `taille-fichiers` : cliquet
  4 194 → 4 141. `vitrine` : empreinte du manuel recalculée (règle 7).
- Inchangés et verts : `annonce-outil`, `besoin`, `ecrire`, `suivi-delegations`, `echanges`, `argv-herdr`, `anti-boucle`, `regle-go`, `web`, `tmp-par-agent`,
  `modeles-table`, `equivalence-missions` (40 scénarios, 0 écart).
- **Ajoutés** : `contrat-noyau` 1g (API d'action de 4b, familles sans contrôle ni geste, 17 refus et 1 acceptation propres à 4b, vues et moteurs privés des
  services, de `journal` et de `notifier`, accès indirect : 8 formes × 3 rangs) et 7 (espaces à l'exécution, services appelés seuls, panne du cœur qui
  ressort telle qu'avant sans écarter la famille, erreur dans la famille qui l'écarte et la nomme, `IndexError`, `Refus` et entrée illisible qui passent (renvoi n° 89 : entier de 5 000 chiffres, imbrication trop profonde, non UTF-8 pour
  `delegation-suivi` et `echange` ; une `ValueError` hors décodage écarte toujours ; `PASSE` identique et limité pour chaque verbe),
  famille `messages` puis `besoins` cassée écartée et nommée, ses verbes inconnus, l'autre et les vues tournent) ; `tests/equivalence-messages.py` et sa
  référence `tests/attendus/equivalence-messages.json`, joués par la porte `tests` (`tests/suites.sh`).

## Écart de place : la publication vers le dépôt en ligne (29/10/2026, hors lots)

Spec : `docs/plans/2026-10-29-publication-github-spec.md` (go inscrit n° 88), qui place les fonctions de publication dans `bin/berger`.
**Spec : `bin/berger` ; fait : `bin/noyau/publication.py`, à cause du cliquet de taille (`tests/taille-fichiers.py` : 4 237 au moment du code, 4 194 après le lot 4a) ;
comportement identique.** Accord du chef de projet : écart de place, pas de comportement, dans le sens du chantier modulaire.

- `bin/noyau/publication.py` : `publication_active`, `equipes_installation`, `forge_absolue`, `git_publication`, `masquer`,
  `cause_publication`, `echec_publication`, `publier_forge`, `publier_installation`, `publier_main` (après le renvoi n° 90 : corrections
  de la relecture, spec inchangée). `bin/berger` ne garde que les appels : `installer` (`--publier`), `redemarrer`,
  `redemarrage_abandonne`, `redemarrer_controle`, le verbe `publier` (4 233 lignes avant le lot 4a, 4 190 après la fusion de `main` ; cliquet jamais relevé).
- `INSTALLATIONS` et `trace_installation` y sont **déplacés tels quels**, parce que c'était nécessaire pour tenir le cliquet : même
  fichier (`courtier/installations.log`), même format de ligne. Les tests d'installation (`tests/moins-validations.py`,
  `tests/redemarrage-courtier.py`) ne changent pas.
- Contrat : le module n'importe pas `bin/berger` ; il est absent de `noyau/api.py` (ni l'API de lecture ni l'API d'action), donc
  jamais exposé aux vues ni aux familles. `tests/publication.py` le vérifie.

## Lot 4c : les équipes (29/10/2026 ; go du propriétaire n° 58, cas 1 ; taille de `bin/berger` : 4 137 → 4 050 lignes ; cliquet 4 050)

Troisième sous-lot du lot 4. Cette demande ne contient QUE 4c (ni le courtier, ni le mur, ni les secrets, ni le dépôt : 4d ; aucun fichier sous
`courtier/` ne change). Même méthode que 4a et 4b : les corps des verbes sont ceux de `main` (dcb6d03), mot pour mot, sauf les écarts listés plus bas ;
les gestes restent au cœur, derrière des services.

### Le tri, verbe par verbe (relu dans `transition.py` et la spec, § « Familles prévues » : *equipes* (equipe, projet, crochet-equipe))

| Verbe | Où | Pourquoi |
|---|---|---|
| `equipe ouvrir` | `equipes` | clone, branche, pile, agent jetable strict, mission (`demarrer_agent`) → service `ouvrir_developpeur` |
| `equipe fermer` | `equipes` | fin de mission, pile et copie supprimées, journal gardé chez le chef → service `fermer_developpeur` |
| `equipe liste` | `equipes` | lecture seule : `equipe_liste` → `noyau/equipes.py`, dans l'API de lecture |
| `equipe domaine` | `equipes` | écrit `equipes/<p>/domaines`, puis `regenerer` (le mur réseau) → service `changer_domaine` |
| `equipe domaines` | `equipes` | lecture seule : `domaines_projet` → `noyau/equipes.py`, dans l'API de lecture |
| `equipe go` | `equipes` | marque ou inscrit le go (`courtier/outils/_portes.py`, `valeurs_coffre`) → service `inscrire_go` |
| `projet ouvrir`, `projet fermer` | `equipes` | dossier de la bibliothèque, registre, `regenerer` (droits des membres) → services `ouvrir_projet`, `fermer_projet` |
| `projet liste` | `equipes` | lecture seule : `projet_liste` (et `registre_projets`) → `noyau/equipes.py`, dans l'API de lecture |
| `crochet-equipe` | `equipes` | lit le JSON du crochet sur stdin et lance la commande du projet (`_transport.executer_shell`) → service `jouer_crochet` |
| `espace-voulu`, `refaire-espace` | cœur | ce sont des verbes d'*espaces* (spec) : placement des onglets Herdr (`onglet*`, `ONGLETS_BERGER`), partagé avec `espace` et `reprendre`, qui passent par `demarrer_agent` (4d). Ils ne font que LIRE les équipes (`chefs`, `developpeurs_ouverts`) |
| `valider`, `refuser` | cœur (4d) | décision sur une validation (un go ou un site d'équipe compris) : le courtier l'exécute |

**Restent au cœur pour le 4d** (courtier, gardes, droits, coffre, mur), à l'identique : `roles_equipe`, `droits_equipe` (courtier), `projets_de`,
`equipes_pilotees`, `membres_possibles`, `dossier_projet`, `domaines_de`, `reseau_claude`, `memoire_equipe`, `crochet_equipe` (la commande posée dans
les réglages du moteur), `outils_developpeur`, `chefs`, `developpeurs_ouverts` (le calcul du mur et des droits) ; `exiger_chef`, `go_ouverture`,
`tracer_hors_go`, `_portes_mod` (règle de go, une seule source avec le courtier), `_git`, `_pile`, `_registre_ecrire` (les gestes) ; `courtier/outils/equipe_chef.py`
et `equipe_dev.py` (outils du courtier). Aucun n'est appelé par la famille.

### Lecture et action séparées

- **Lecture** (`bin/noyau/equipes.py`, groupe « Équipes, lecture » de `noyau/api.py`) : `equipe_liste`, `projet_liste`, `domaines_projet`. Les accompagnent,
  hors API : `resume_portes` (employé par `equipe_liste` seul), `registre_projets`, `_equipe`, `DOMAINE`, `DOMAINES_MAX`. Dépendances nommées, aucun
  `import *` ; `bin/berger` importe par leur nom ce que ses gestes et le calcul du mur relisent (`registre_projets` pour `projets_de` et `cloisons`,
  `domaines_projet` pour `domaines_de`, `DOMAINE` et `DOMAINES_MAX` pour `equipe_domaine`, `_equipe` pour `equipe_ouvrir`, `equipe_go`, `equipe_fermer`) :
  les MÊMES objets, rien n'est recopié ; le calcul lui-même reste au cœur.
- **Action** : sept services dans `bin/noyau/actions.py`, sur la liste fermée `ACTIONS` : `ouvrir_developpeur(projet, sujet, texte, par, moteur=None, modele=None)`,
  `fermer_developpeur(projet, sujet, par)`, `changer_domaine(projet, action, nom, par, essai=False)`, `inscrire_go(projet, sujet, cas, spec, par, essai=False)`,
  `ouvrir_projet(eq, projet, membres, par)`, `fermer_projet(eq, projet, par)`, `jouer_crochet(a)`. Seules les familles de commandes les reçoivent, par leur
  chargeur (`services_commandes`), comme en 4a et 4b.
- **Le geste reste au cœur** : `equipe_ouvrir`, `equipe_fermer`, `equipe_domaine`, `equipe_go`, `projet_ouvrir`, `projet_fermer`, `lancer_crochet_equipe` de
  `bin/berger`, branchés derrière les services au démarrage (`noyau.actions.brancher`, la même ligne qu'en 4a et 4b, liste fermée).
- `ErreurService` et `PASSE` restent limités comme en 4a et 4b : `PASSE` = `(IndexError, Refus, ErreurService)` pour chacun des trois verbes, sans
  exception propre à un verbe, aucune dispense générale.

### `lire_document`, `lire_interactif`, `mettre_a_jour_titres` (et `statusline`) : de l'API de lecture à l'API d'action

Notés au 4a (renvoi n° 83) comme encore dans l'API de lecture. Tous trois ÉCRIVENT : `lire_document` marque le document lu (`marquer_lu` réécrit
`LECTURES`), `lire_interactif` l'appelle, `mettre_a_jour_titres` renomme l'espace et les panneaux Herdr. **Ils passent dans `ACTIONS`** et sortent de `API`.
Le recensement des noms qui restaient dans l'API de lecture en a trouvé un quatrième qui écrit : **`statusline`** (relève le quota dans `CONSO/quota-claude.json`) ;
il suit la même règle. `etat` et `validations` **restent** dans l'API de lecture : ils n'écrivent rien (`donnees_etat`, `en_attente`, `validation_donnees`
lisent ; la sortie est l'écran).
Ce sont des fonctions du NOYAU (`noyau/ecrans.py`, `noyau/bandeaux.py`), pas des gestes du cœur : `services_commandes()` les donne telles quelles (importées au
chargement des commandes) ; ni enveloppe, ni branchement (`brancher` refuse ces quatre noms, `DU_NOYAU`). Une erreur sort exactement comme avant. Effet mesuré :
- **vues** : aucune ne les employait (analyse et contrat) ; elles ne les reçoivent plus, et une vue qui les cite est refusée (`contrat-noyau` 1h, 8) ;
- **moteurs** : aucun ne les employait ; ils ne les reçoivent plus ;
- **familles** : `alire` (`lire`) et `bureau` (`titres`, `statusline`) reçoivent les MÊMES fonctions, par l'API d'action ; aucune ligne de ces familles ne change ;
- **cœur** : `bin/berger` les garde par `from noyau.ecrans import *` et `from noyau.bandeaux import *` (inchangé, pour ses propres appels).

### Les contrôles, ligne à ligne : aucun n'a bougé

Aucun garde-fou n'est recopié ; la famille n'en fait aucun (`contrat-noyau` 1h : ni rôle, ni go, ni plafond, ni git, ni registre, ni shell).
- **ouvrir** : projet inconnu et dépôt = installation (`_equipe`), le chef seul ou le propriétaire (`exiger_chef`), sujet (2 à 30 caractères), moteur et modèle
  permis (`moteurs.decider_mission`, avant toute création), verrou d'ouverture, nom de plus de 32 caractères pour Herdr, développeur et copie existants,
  plafond `[missions] max`, règle de go (`go_ouverture` : go inscrit, go demandé, mots, « Hors go »), port libre, pile du projet : dans `equipe_ouvrir` (cœur) ;
- **fermer** : le chef seul, développeur ouvert du projet (jamais la copie du chef), travail non commité, commits ni poussés ni fusionnés, checklist finie
  (par `fin_mission`) : dans `equipe_fermer` ;
- **domaine** : projet, action, nom exact (`DOMAINE`), déjà permis, plafond `DOMAINES_MAX`, absent : dans `equipe_domaine` ; **go** : rôle, sujet, cas, chemin,
  spec introuvable ou vide, valeur du coffre dans la spec, déjà inscrit, spec changée : dans `equipe_go` ;
- **projet** : équipe, nom, rôle (chef, coordinateur ou propriétaire), membres de l'équipe seulement, déjà ouvert, dossier existant ; archive sans suppression :
  dans `projet_ouvrir`, `projet_fermer` ;
- **crochet** : développeur et commande déclarés (jamais `{copie}`), fichier ramené de sa copie au dépôt, réponse vide en cas d'échec : dans `lancer_crochet_equipe` ;
- **droits d'équipe** (chef, coordinateur, non-membre, lecture seule, `equipe:<projet>` d'un non-coordinateur), **validations** de site (superviseur) et de go
  (propriétaire) : dans le courtier (4d), inchangés ;
- **entrée privée** obligatoire pour `equipe` et `projet` : `DROITS[...]["prive"]` de la famille (retirés du tuple de `transition`, qui n'a plus aucun verbe privé).
Preuve : les services appelés SANS la famille refusent comme avant (`contrat-noyau`, section 8 : rôle, projet inconnu, dépôt = installation, sujet, développeur
absent, nom de site inexact, action inconnue, go hors rôle, cas, projet hors rôle, membres, projet absent ; rien n'est écrit).

### Écarts au « déplacement pur »

- **`_equipe` passe dans `noyau/equipes.py`** avec `equipe_liste`, qui l'appelle : ses deux refus (projet inconnu ; dépôt = installation en service) sont
  inchangés et le cœur l'importe par son nom pour ses trois gestes (même objet). C'est le seul contrôle présent dans le module de lecture ; il ne fait
  que lire `config.toml`. De même `DOMAINE` et `DOMAINES_MAX` suivent `domaines_projet` (le cœur les importe pour `equipe_domaine`).
- **La lecture des arguments reste dans le verbe** (mot pour mot) : l'usage, le nombre d'arguments et « projet d'équipe inconnu : … — usage » (`pos[0] in EQUIPES`)
  sont la forme de la commande, pas un garde-fou (les gestes refont leur propre contrôle du projet) ; leurs messages sont mesurés identiques.
- **L'entrée du crochet est lue PAR LE GESTE** (`lancer_crochet_equipe`, au cœur), pas par la famille. Leçon du renvoi n° 89 vérifiée : JSON invalide, entier de
  5 000 chiffres, non UTF-8 (une `ValueError`, attrapée par le geste comme avant : réponse vide) ; imbrication trop profonde (`RecursionError`, qui sort
  du geste en `ErreurService` et ressort telle qu'avant, famille servie). Aucune lecture d'entrée n'est donc à protéger dans la famille.
- **`_opt` recopié** (une ligne) dans `commandes/equipes.py`, comme en 4a et 4b.
- **`cas_go` = `None`** pour les trois verbes : comme en 4a et 4b, la règle de go et les droits sont appliqués par le courtier (validations) et le geste ;
  le registre ne décide rien.
- **Limite constatée, hors 4c** : `transport` (le module `courtier/outils/_transport.py`, avec `executer_shell`) est dans l'API de LECTURE depuis le lot 1 ; une
  vue ou une famille peut donc lancer un programme sans passer par un service. Aucune n'en use (contrat : la famille `equipes` ne le cite pas). À trancher au 4d.

### Sorties qui changent

Mesurées : `tests/equivalence-equipes.py`, **89 scénarios** sur une installation jetable (forge, dépôt du chef, faux Herdr à état ; `demarrer_agent`, `espace`,
`parler` et l'API Herdr relevés au lieu d'être faits, des deux côtés), mesurés sur `main` (dcb6d03) puis sur la branche : code de sortie, sortie standard, dernière
ligne d'erreur (la première pour « commande inconnue »), fichiers écrits (dossiers d'agents, consignes et réglages régénérés par empreinte, `equipes/` : registre
des projets, sites permis, go, demandes, verrou ; bibliothèque : dossiers de projet et archives ; historique d'équipe chez le chef ; échanges ; validations),
copies (branche, origine, état), branches de la forge, appels à Herdr et lancement strict. Refus : rôle (coordinateur, non-membre, chef d'un autre rôle),
go absent ou seulement demandé, plafond, sujet et nom invalides, sujet trop long pour Herdr, modèle non permis, dépôt = installation, travail non commité,
checklist non finie, membres hors équipe ; transport privé (texte positionnel, JSON invalide, pas un tableau, imbriqué, UTF-8, plus d'un Mio) ; entrée du crochet
illisible ; voie du courtier (droits d'équipe, validations de site et de go demandées). **0 écart.** L'instantané garde CHAQUE fichier : un nom qui, normalisé,
en rejoint un autre (deux archives horodatées du même projet) donne la liste ordonnée de ses fichiers, prouvée d'abord par `controler_instantane()` (une archive
antérieure modifiée, puis supprimée, doit faire un écart). Seule autre sortie changée : **`berger aide`** (et la suite de « commande inconnue ») a **3 lignes de
plus** à la fin, celles d'`equipe`, `projet` et `crochet-equipe`, que la docstring du cœur ne documente pas sous la forme `berger <verbe>` (point 4 du correctif contrat).
Les attendus (`tests/attendus/equivalence-equipes.json`) se produisent et se vérifient ainsi :
```
d=$(mktemp -d) && git archive dcb6d03 | tar -x -C "$d" && python3 tests/equivalence-equipes.py --produire "$d" tests/attendus/equivalence-equipes.json
```
Rejoué le 29/10 : deux productions identiques octet pour octet ; deux mesures successives de la branche identiques ; la branche : 0 écart sur 89.
**Porte `tests`, premier passage** : 8 écarts, tous sur des scénarios qui régénèrent les réglages. Cause : le lanceur des suites donne à chaque suite son
propre `BERGER_TMP_AGENTS` (temporaire des agents), écrit dans les réglages régénérés et non normalisé ; la référence avait été mesurée avec `/tmp/bt`.
Reproduit hors porte (`BERGER_TMP_AGENTS=<autre dossier>` : les 8 mêmes écarts). Corrigé dans le test : il fixe son temporaire DANS l'installation jetable
(`<T>/tmp-agents`, normalisé). Référence régénérée par la même commande sur dcb6d03 ; deux productions avec deux `BERGER_TMP_AGENTS` différents identiques ;
la branche : 0 écart sur 89, avec ou sans `BERGER_TMP_AGENTS` hérité.

### Tests dont seule la FORME d'accès change (même assertion)

- `contrat-noyau` : 1c, la liste des familles du produit s'allonge (`equipes`) ; 1d, `lire_document`, `lire_interactif`, `mettre_a_jour_titres`, `statusline`
  quittent `NOUVEAUX` (API de lecture) pour `NOYAU_4C` (1h), avec les MÊMES vérifications (défini dans son module du noyau, employé par sa famille, absent du
  cœur, fermeture sans chemin réservé au lot 4) plus « listé dans `ACTIONS`, absent de `API` » ; `equipe_liste`, `projet_liste`, `domaines_projet` entrent dans
  `NOUVEAUX`, `equipes` dans les modules du noyau qui ne citent aucun nom du cœur ; 1f, « chaque service est une fonction de `noyau/actions.py` » hors les six
  fonctions du noyau (`_DU_NOYAU`) ; 1g, `ACTIONS[:13]` au lieu d'`ACTIONS` entier ; section 2, le programme qui vérifie l'API importe aussi `noyau.equipes`.
- `commandes-couverture` : 27 verbes en famille (3 de plus, famille `equipes`), 34 au cœur (au lieu de 37). `taille-fichiers` : cliquet 4 137 → 4 050.
  `vitrine` : empreinte du manuel recalculée (règle 7).
- Inchangés et verts : `argv-cli`, `argv-shell` (`lancer_crochet_equipe` lu dans `bin/berger`), `argv-imbrique`, `equipe-ouverture`, `bibliotheque-projets`,
  `alire`, `installer-master`, `vitrine-readme`, `equivalence-missions` (40, 0 écart), `equivalence-messages` (86, 0 écart). `hierarchie-equipe` et `regle-go`
  se déclarent « NON JOUÉ » dans le bac du développeur (socket Unix interdit) : joués par les portes.
- **Ajoutés** : `contrat-noyau` 1h (API d'action de 4c, famille sans contrôle ni geste, 18 refus et 1 acceptation propres à 4c, vues et moteurs privés des
  services et des quatre fonctions du noyau, lectures permises aux vues et aux moteurs, accès indirect : 11 formes × 3 rangs) et 8 (espaces à l'exécution,
  services appelés seuls, `brancher` qui refuse `statusline` et ce qui n'est pas une fonction, panne du cœur qui ressort telle qu'avant sans écarter la famille,
  erreur dans la famille ou dans une lecture qui l'écarte et la nomme, `IndexError` qui passe, `PASSE` identique et limité, entrée privée par `DROITS`,
  famille cassée écartée et nommée, ses verbes inconnus, le reste tourne) ; `tests/equivalence-equipes.py` et sa référence `tests/attendus/equivalence-equipes.json`.

### Renvoi n° 93 (relecture Codex, refus du propriétaire, 7/10) : les deux défauts du renvoi n° 89, sur les équipes

1. **Donnée d'équipe illisible.** Avec `equipes/p/demandes/<sujet>.json` à « { », `equipe liste` sortait sur `main` par la `JSONDecodeError` du lecteur ; sur
   la branche, la famille `equipes` était écartée (« famille equipes écartée ») et ses trois verbes quittaient le registre. Une donnée illisible devenait un défaut
   du module ; `contrat-noyau` 8 validait cette divergence. **Cause racine** : les lectures (`equipe_liste`, `projet_liste`, `domaines_projet`), appelées depuis la
   famille hors service, ont leurs erreurs traitées comme des erreurs de la famille ; or elles lisent des fichiers (demandes de fusion, CHECKLIST.md, agent.conf
   via `lire()`, qui n'attrape que `OSError`, `projets.json`, sites permis) dont le contenu peut lever presque n'importe quoi (`JSONDecodeError`,
   `AttributeError` d'une demande qui n'est pas un objet, `ValueError` de `int()`, `UnicodeDecodeError`, `RecursionError`). **Corrigé** comme `_entree()` au 4b :
   `_lire()` (`commandes/equipes.py`) entoure l'APPEL de chaque lecture, et seulement lui ; ce qu'elle lève est porté par `ErreurService`, dont `commandes.lancer`
   ressort l'origine : dernière ligne d'erreur identique, famille servie. `PASSE` reste `(IndexError, Refus, ErreurService)` ; une `ValueError` ailleurs dans le
   verbe écarte toujours la famille (contrôlé). L'enveloppe est dans la famille et non dans le noyau : `registre_projets` et `domaines_projet` sont aussi appelés
   par le cœur (calcul du mur), dont la sortie ne doit pas changer. Tests rouges d'abord (`contrat-noyau` 8 : 5 formes de demande illisible, `projets.json` trop
   imbriqué, sites permis non UTF-8 ; le cas qui validait l'écartement exige désormais l'équivalence) ; équivalence : 9 scénarios de plus (demande illisible ×5,
   checklist non UTF-8, sites permis non UTF-8, `projets.json` illisible ×3 ; un de ceux-ci passait déjà : `registre_projets` rend `{}`).
2. **Journal des échanges non vérifié au début.** L'équivalence ne gardait de `courtier/echanges.jsonl` que la fin, coupée à la longueur de l'ancien contenu :
   une ancienne ligne altérée (« ancien » → « ALTERE »), puis la même ligne ajoutée, donnait le même relevé qu'un ajout correct, et l'état altéré devenait la
   référence du scénario suivant. **Cause racine** : extraction par longueur sans contrôle du préfixe. **Corrigé** : `ajouts()` ne rend la fin que si l'ancien
   contenu est resté identique au début, sinon le fichier entier, marqué « début du journal modifié ». Preuve rouge d'abord : `controler_journal()`, jouée à
   chaque comparaison. Même défaut et même correctif dans `tests/equivalence-messages.py` (4b) ; aucun autre fichier n'y était relevé par suffixe
   (`equivalence-missions` garde le fichier entier). Relevés inchangés quand le début est intact : la référence des messages n'a pas à être régénérée (0 écart sur 86).
Référence des équipes régénérée par la même commande sur dcb6d03 (99 scénarios) ; reproduite à l'identique avec un autre `BERGER_TMP_AGENTS` ; la branche : 0 écart sur 99.
