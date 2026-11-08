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

## Lot 4d : le courtier, le mur, les secrets et le dépôt (29/10/2026 ; go du propriétaire n° 58, cas 1) — INVENTAIRE, avant le code

Dernier sous-lot du lot 4. Même méthode que 4a, 4b et 4c : le verbe (lecture des arguments) part dans une famille ; les LECTURES passent par l'API ; les
ACTIONS par des services de `noyau/actions.py` (liste fermée `ACTIONS`) ; le GESTE et ses contrôles restent au cœur, branchés derrière les services.
Règle de tri : une garde (mur, bac à sable, droits entre agents, coffre, règles de validation, `verifier-depot`) ne s'affaiblit jamais ; dans le doute, elle
reste au cœur. Une demande de fusion par partie (courtier, mur, secrets, dépôt), dans cet ordre.

### Les verbes encore au cœur (`transition`, 34 verbes) : ceux du 4d, et les autres

| Verbe | Partie | Famille proposée | Service (geste au cœur, inchangé) |
|---|---|---|---|
| `valider`, `refuser` | courtier | `courtier` | `decider_validation(n, decision, duree)` → `decider` (fichier `.decision` atomique, `--duree` par `courtier/_web.py`, file tenue) |
| `courtier redemarrer` | courtier | `courtier` | `redemarrer_courtier(controle, essai, publier)` → `redemarrer` (marque de fermeture, attente, contrôle, retour arrière) |
| `lancer` | courtier | `courtier` | `lancer_agent(a, moteur)` → `lancer` (bac à sable, temporaire, choix du moteur, `execvpe` des arguments stricts) |
| `moteur` | courtier | `courtier` | `ouvrir_moteur(a, m)` → `moteur_a_la_demande` (`demarrer_agent`, le mur) |
| `args` | courtier | `courtier` | `parametres_moteur(args)` → le corps actuel de `verbe_args`, recopié tel quel dans une fonction du cœur (bac à sable exigé AVANT de lire le moteur, admission, temporaire, variables) |
| `regenerer` | mur | `agents` | `regenerer_agents()` → `regenerer` (règles, réglages Claude/Codex, masques, cloisons, réseau, MCP, skills) |
| `nouveau` | mur | `agents` | `creer_agent(a, nom)` → `nouveau` |
| `agent apercu`, `agent appliquer` | mur | `agents` | `apercu_agent(dem, a)`, `appliquer_agent(dem, ref)` → `agent_apercu`, `agent_appliquer` (clés permises et interdites, empreinte, droits) |
| `secrets audit` | secrets | `secrets` | `auditer_secrets()` → `secrets_audit` (lit le coffre ; n'affiche que des NOMS) |
| `coffre sauvegarder <motif>`, `coffre purger` | secrets | `secrets` | `sauvegarder_coffre(motif=None)` → `coffre_sauvegarder` (age vers la clé PUBLIQUE, en-tête et taille vérifiés) |
| `verifier-depot` | dépôt | `depot` | `verifier_neutralite()` → `verifier_depot` (lit le coffre et les marques privées) |
| `installer` | dépôt | `depot` | `installer_forge(forge, branche)` → `installer` (avance rapide, `verifier-depot`, `regenerer`, retour arrière) |
| `publier` | dépôt | `depot` | `publier_forge(forge)` → `publier_main` (noyau/publication.py, avance rapide seule) |
| `sauvegarder`, `restaurer`, `verifier-sauvegarde` | dépôt | `depot` | `sauvegarder_donnees()`, `restaurer_archive(archive, dest)`, `verifier_sauvegarde_distante()` → `sauvegarder`, `restaurer`, `verifier_sauvegarde` (coffre WebDAV, phrase du trousseau) |

**Restent au cœur, hors du 4d (dit tel quel, pas oublié)** :
- `mcp-enveloppe` et `web` : `serveur_mcp`, `enveloppe_web`, la classe `Acces`, le proxy web, `courtier/_web.py`, `courtier/_mcp.py` sont gelés tant que le
  développeur `berger-acces-web-envoi` est ouvert (consigne de la mission). `decider` LIT `courtier/_web.py` (`module_web`) sans le changer.
- `interface` (lien, certificat, servir) : le jeton d'entrée et la clé TLS sont des secrets de l'installation ; rien ne justifie de les rapprocher d'une famille.
- Les 15 verbes revenus au cœur au lot 3 (`panneau`, `reveil`, `tache`, `relancer`, `espace-voulu`, `refaire-espace`, `reprendre`, `memoire`, `vue`,
  `planificateur`, `espace`, `superviser`, `entretien`, `abonnement-claude`, et `publier` traité ci-dessus) : espaces Herdr, réveils et affichage, pas le
  courtier, le mur, les secrets ni le dépôt. Ils passent par `demarrer_agent`, `regenerer` ou les réglages : un lot à part s'il faut les sortir.
  Conséquence : `transition` ne disparaît pas au 4d ; `bin/berger` ne descend pas sous 250 lignes à la fin du lot 4 (écart à la spec, à trancher).

### Fonctions : ce qui RESTE au cœur (toutes), et pourquoi

Aucune fonction du mur, des secrets ni du dépôt ne quitte `bin/berger` dans ce sous-lot ; seules les lignes des verbes (≈ 40) partent dans les familles.
- **Mur et bac à sable** : `masques`, `cloisons`, `reseau_claude`, `ecrire_reseau_claude`, `domaines_de`, `reglages_claude`, `config_codex`, `hooks_codex`,
  `fichiers_mcp` / `FICHIERS_MCP`, `REGLAGES_PASSES`, `FEATURES_CODEX_STRICT`, `proteges`, `dossiers_seuls`, `tmp_*`, `preparer_tmp`, `env_*`,
  `reglages_strict_externe`, `bac_a_sable_ok`, `exiger_bac_a_sable`, `exiger_tmp`, `demarrer_agent`, `confiance_claude`, `lier_skills`, `motif_refus_skill`,
  `regles_agent` et les consignes, `regenerer`, `nouveau`. La spec proposait de ranger ce calcul dans `noyau/` (privé) : je propose de NE PAS le faire au 4d.
  Dans `bin/berger`, aucun module ne peut l'atteindre (le contrat refuse tout import du cœur) ; dans `noyau/`, il deviendrait un module de plus que le
  contrat doit fermer, pour aucun gain de sécurité. C'est le cas « dans le doute, reste au cœur ».
- **Proposition de modification d'un agent** : `lire_proposition`, `controler_proposition` (`CLES_AGENT`, `CLES_INTERDITES`, `DROITS`), `empreinte_proposition`,
  `agent_apercu`, `agent_appliquer`, `relance_apres_application`, `relancer_en_attente`.
- **Secrets et coffre** : `valeurs_coffre`, `secrets_audit`, `secrets_audit_silencieux`, `coffre_sauvegarder`, `phrase_sauvegarde`. Aucune n'entre ni dans l'API
  de lecture ni dans une vue ou un moteur : un service rend un CODE de sortie et imprime ce que le geste imprimait (des noms, jamais une valeur).
- **Dépôt** : `verifier_depot`, `git_installation`, `tete_installation`, `retour_arriere`, `installer`, `courtier_reste_actif`, `reglage_courtier`,
  `en_cours_courtier`, `noms_en_cours`, `redemarrer`, `redemarrage_abandonne`, `redemarrer_controle`, `sauvegarder`, `verifier_sauvegarde`, `restaurer`.
- **Courtier et validations** : `decider`, `file_tenue_texte`, `module_web`, `relancable_en_boucle`, `solliciter` (anti-boucle), `roles_equipe`, `a_l_outil`,
  `consignes_outils`. Les règles de validation sont dans `courtier/courtier` (inchangé : aucun fichier de `courtier/` ne change au 4d).

### Écarts du 4d, à confirmer par le propriétaire

Accord du chef de projet (29/10) ; la spec n'est pas modifiée. Chacun avec sa raison :
1. **Le calcul du mur reste dans `bin/berger`**, pas dans `noyau/` (privé) comme le prévoyait la spec (§ Lot 4, « Fichiers »). Raison : dans `bin/berger`,
   aucun module (vue, famille, moteur) ne peut l'atteindre, le contrat refusant tout import du cœur ; déplacé dans `noyau/`, il deviendrait un module de
   plus que le contrat doit fermer, sans aucun gain de sécurité, et un déplacement de plus du code le plus sensible. Règle de la mission : une garde ne
   s'affaiblit jamais ; dans le doute, elle reste au cœur.
2. **Le module de transition (`bin/commandes/transition.py`) ne disparaît pas à la fin du lot 4.** Raison : il garde `mcp-enveloppe` et `web` (gelés tant que
   le développeur `berger-acces-web-envoi` est ouvert), `interface` (jeton d'entrée et clé TLS de l'interface, des secrets) et les 15 verbes revenus au cœur à la
   relecture du lot 3 (espaces Herdr, réveils, affichage), qui passent par `demarrer_agent`, `regenerer` ou les réglages du mur. Aucun n'est le courtier, le
   mur, les secrets ou le dépôt au sens de ce sous-lot ; les sortir demanderait de nouveaux services autour du lancement d'un agent : un lot à part.
3. **`bin/berger` reste au-dessus de 250 lignes** (la spec visait ≤ 250 à la fin du lot 4). Raison : conséquence directe des points 1 et 2 — les gestes, les
   gardes et les fonctions des verbes restés au cœur y demeurent. Le cliquet de `tests/taille-fichiers.py` continue de baisser à chaque demande.

### Ce qui reste à trancher (renvoyé au 4d par le 4c)

- **`transport` dans l'API de LECTURE** (`courtier/outils/_transport.py`, avec `executer_shell`) : une vue ou une famille peut lancer un programme sans
  service. Mesuré : aucune vue ni famille ne l'emploie ; seuls les moteurs l'emploient (`transport.ecrire_configuration`, `claude.py`, `codex.py`).
  **Proposition** : `transport` sort de `API` et passe dans `BASE_NOYAU` de `bin/moteurs/__init__.py` (les moteurs le reçoivent par leur chargeur, comme
  `travail` ou `CODEX_HOME`) ; une vue ou une famille qui le cite est refusée (contrat). Une garde de plus, aucune de moins ; aucune sortie ne change.
  **Décidé (chef de projet, 29/10)** : un commit à part, EN TÊTE de la demande « courtier », avec son test rouge.

### Tests prévus (rouges d'abord)

1. `contrat-noyau` 1i (statique) et 9 (exécution), comme 1h et 8 : imports interdits propres au 4d (`noyau.actions`, `.actions` par alias, `getattr`,
   le module du noyau qui porterait un geste), accès indirect aux actions par trois rangs ; aucune vue ni aucun moteur ne reçoit un service du 4d ;
   **aucun nom de l'API, et aucune fonction atteinte depuis l'API (fermeture d'appels), ne lit `COFFRE`, `valeurs_coffre`, `phrase_sauvegarde`, le jeton
   ou la clé de l'interface** ; familles sans contrôle ni geste ; services appelés seuls qui refusent comme avant ; `PASSE` = `(IndexError, Refus,
   ErreurService)` pour chaque verbe ; famille cassée écartée et nommée, ses verbes inconnus, le reste tourne ; panne du cœur qui ressort telle qu'avant.
2. Équivalence AVANT/APRÈS, une par partie : `tests/equivalence-courtier.py`, `-mur.py`, `-secrets.py`, `-depot.py`, référence produite sur `main`
   (`--produire`, commande exacte ici), instantané qui garde CHAQUE fichier et vérifie le début des journaux (`controler_instantane`, `controler_journal`).
3. Suites de sécurité inchangées et vertes : `sonde-mur`, `coffre-sauvegarde`, `argv-prive`, `argv-*`, `marques-produit`, `verifier-depot`, `proteges`,
   `tmp-par-agent`, `mcp-trous`, `agent-appliquer`, `installation`, `installer-master`, `moins-validations`, `redemarrage-courtier`, `validation-fait`,
   `anti-boucle`, `regle-go`. Une assertion déplacée sera dite ici.

### Partie « courtier » (demande 1 du 4d ; taille de `bin/berger` : 4 050 → 4 044 lignes ; cliquet 4 044)

Cette demande ne contient QUE la partie courtier (ni le mur, ni les secrets, ni le dépôt ; aucun fichier sous `courtier/` ne change ; `reglages_claude`,
`serveur_mcp`, `enveloppe_web`, `courtier/_web.py` et `courtier/_mcp.py` ne changent pas). Même méthode que 4a, 4b et 4c.

**En tête, un commit à part : `transport` quitte l'API de lecture** (décision du chef de projet). Test rouge d'abord (`contrat-noyau` 1i, et à l'exécution :
`transport` n'est dans l'espace d'aucune vue ni famille, seulement des deux moteurs), puis le correctif : `noyau/api.py` (groupe « Transport privé » réduit
à `entree_privee`) et `BASE_NOYAU` de `bin/moteurs/__init__.py` (+ `transport`). Aucune sortie ne change (aucune vue ni famille ne l'employait).

**Le tri** : `valider`, `refuser`, `courtier`, `lancer`, `moteur`, `args` → famille `courtier` (`bin/commandes/courtier.py`).
**Action** : cinq services dans `noyau/actions.py` (liste fermée `ACTIONS`) : `decider_validation(n, decision, duree=None)` → `decider` ;
`redemarrer_courtier(controle=None, essai=1, publier=None)` → `redemarrer` ; `lancer_agent(a, moteur=None)` → `lancer` ; `ouvrir_moteur(a, m)` →
`moteur_a_la_demande` ; `parametres_moteur(args)` → `arguments_pont`. **Lecture** : aucune propre à ces verbes. `ErreurService` et `PASSE` inchangés :
`(IndexError, Refus, ErreurService)` pour chacun des six verbes, aucune dispense propre à un verbe.

**Les contrôles, ligne à ligne : aucun n'a bougé** (la famille n'en fait aucun : `contrat-noyau` 1j, ni décision, ni service système, ni bac à sable, ni
moteur, ni Herdr, ni `transport`).
- **valider / refuser** : déjà faite, aucune demande, `--duree` sur un refus, hors accès web, durée invalide (`courtier/_web.py`, lu), écriture atomique du
  fichier `.decision`, file tenue (installation en attente, redémarrage en cours) : dans `decider` ;
- **courtier redemarrer** : marque de fermeture rafraîchie, attente bornée, abandon tracé et notifié avec nouvel essai, `--controle` qui n'est pas un commit
  complet, redémarrage contrôlé et retour arrière automatique : dans `redemarrer`, `redemarrage_abandonne`, `redemarrer_controle` ;
- **lancer** : bac à sable exigé (mur strict), dossier temporaire vérifié, admission du moteur et bascule (`moteurs.choisir_moteur`), arguments stricts :
  dans `lancer` ; **moteur** : `demarrer_agent` (le mur) dans `moteur_a_la_demande` ;
- **args** : bac à sable exigé AVANT de lire le moteur, admission (sauf `--contrat`), variables du lancement strict : dans `arguments_pont` ;
- **règles de validation** et droits entre agents : au courtier (`courtier/courtier`), inchangés.
Preuve : les services appelés SANS la famille refusent comme avant (`contrat-noyau` 9 : validation absente, durée sur un refus, hors accès web,
`--controle` court, agent inconnu ; rien n'est décidé).

**Écarts au « déplacement pur »**
- **`verbe_args` devient `arguments_pont(args)`, au cœur, corps identique** : le verbe exige le bac à sable AVANT de lire son second argument ; un service
  aux arguments déjà lus (`a, m`) aurait inversé cet ordre (`berger args chef` : IndexError avant le refus du bac à sable). Le geste reçoit donc la liste
  des arguments, comme le verbe d'avant.
- **`--essai` est lu par `_entier`** (`commandes/courtier.py`) : une `ValueError` de `int()` dans la famille l'écarterait ; `_entier` la rend en `Refus`
  (déclaré dans `PASSE`), que `commandes.lancer` ressort en `ValueError` de même message, dans le même ordre de lecture des options (même règle qu'au lot 3 bis
  pour `lire ²`). Dernière ligne d'erreur identique (mesurée).
- **`_opt` recopié** (une ligne) dans `commandes/courtier.py`, comme en 4a, 4b et 4c. **`cas_go` = `None`** pour les six verbes (règles au courtier).

**Sorties qui changent** : mesurées par `tests/equivalence-courtier.py`, **48 scénarios** sur une installation jetable (faux Herdr, faux moteurs qui
répondent `--version` et disent leurs arguments et les NOMS des variables de Berger, faux bubblewrap, `systemctl`, `systemd-run` ; l'installation est un dépôt
git pour le retour arrière) : code de sortie, sortie standard, dernière ligne d'erreur, fichiers écrits (dossiers d'agents, temporaires, contrats des moteurs,
fichiers d'état du courtier : décisions, fermeture, `installations.log`, `notifications.log`), appels. Refus : validation absente ou faite, durée, file
tenue ; bac à sable absent, temporaire trop long, moteur jamais vu (bascule), aucun moteur admis, moteur inconnu ; redémarrage abandonné, contrôle raté
(retour arrière) ; arguments manquants ; voie privée. **0 écart.** L'instantané garde CHAQUE fichier, les journaux sont vérifiés au début
(`controler_instantane`, `controler_journal`). Seule autre sortie changée : **`berger aide`** a **1 ligne de plus** (`refuser`, que la docstring documente
sous la forme `berger valider|refuser`). Référence :
```
d=$(mktemp -d) && git archive 4f69605 | tar -x -C "$d" && python3 tests/equivalence-courtier.py --produire "$d" tests/attendus/equivalence-courtier.json
```
Rejoué : deux mesures successives de `main` identiques octet pour octet ; la branche : 0 écart sur 48, aussi avec un autre `TMPDIR` et un autre
`BERGER_TMP_AGENTS` hérités (le test pose les siens dans l'installation jetable et retire les variables `CLAUDE_CODE_*`, `CODEX_*` de la session).

**Tests dont seule la FORME d'accès change (même assertion)**
- `contrat-noyau` 1h : `ACTIONS[13:24]` au lieu de `ACTIONS[13:]` (la liste s'allonge des services du courtier). Section 6 (4a) : l'exemple de nom HORS
  de la liste passé à `brancher` était `lancer_agent`, devenu un service ; il devient `lancer_un_agent` (même assertion : `NameError`).
- `commandes-couverture` : 33 verbes en famille (6 de plus, famille `courtier`), 28 au cœur (au lieu de 34) ; `valider`, `refuser` quittent `RESTENT`.
  `taille-fichiers` : cliquet 4 050 → 4 044. `vitrine` : empreinte du manuel recalculée (règle 7).
- **Ajoutés** : `contrat-noyau` 1i (transport), 1j (famille courtier : 14 refus et 1 acceptation propres, vues et moteurs privés des services, accès indirect :
  6 formes × 3 rangs), 1k (aucun nom de l'API de lecture ni de `BASE_NOYAU` n'atteint le coffre, ses valeurs, la phrase des sauvegardes, le jeton ou la clé de
  l'interface, ni un geste qui les lit ; preuve d'abord que la fermeture les voit) et 9 (exécution) ; `tests/equivalence-courtier.py` et sa référence.

### Partie « mur » (demande 2 du 4d, pile locale ; taille de `bin/berger` : 4 044 → 4 038 lignes ; cliquet 4 038)

Ne contient QUE la partie mur. Aucune fonction du mur ne bouge ; `reglages_claude` n'est pas touché (correctif de sécurité en cours, consigne du chef de projet).

**Le tri** : `regenerer`, `nouveau`, `agent apercu|appliquer` → famille `agents` (`bin/commandes/agents.py`, nom prévu par la spec). **Action** : quatre services
(`regenerer_agents()` → `regenerer` ; `creer_agent(a, nom=None)` → `nouveau` ; `apercu_agent(demandeur, cible)` → `agent_apercu` ;
`appliquer_agent(demandeur, cible_empreinte)` → `agent_appliquer`). **Lecture** : aucune. `PASSE` = `(IndexError, Refus, ErreurService)` pour chaque verbe.

**Les contrôles, ligne à ligne : aucun n'a bougé** (la famille n'en fait aucun : `contrat-noyau` 1j bis).
- **regenerer** : dossiers créés AVANT les réglages (bibliothèque, projets, temporaires, `espace.toml`), `proteges` refusés et dits, sites permis du projet
  (`.reseau-claude.json`), serveurs MCP relayés, règles (`ecrire_regles`), réglages du mur (`reglages_claude`, réglages d'un agent ouvert), skills
  (`lier_skills`), hooks et profils Codex (`features` fermées pour un strict), plugin Herdr : dans `regenerer` et les fonctions qu'il appelle, au cœur ;
- **nouveau** : nom trop long pour Herdr, agent existant, modèle de SOUL d'un rôle (nom dans `[\w-]`) : dans `nouveau` ;
- **agent apercu / appliquer** : identifiant, un agent qui se propose lui-même, développeur d'équipe, fichiers permis, `espace.toml`, création sans `SOUL.md`,
  clés interdites (supervision, dossier externe, clés d'équipe) et inconnues, mur strict seul, moteur, heures, outils (agent inconnu, pouvoir sur soi, équipe,
  outil non déclaré), serveurs MCP, méthodes, `ecrire_aussi` hors installation ou sur le produit, chemin et valeurs du coffre (masquées dans l'aperçu), empreinte
  identique à l'aperçu, sauvegardes `.avant`, relance au repos : dans `controler_proposition`, `agent_apercu`, `agent_appliquer` ;
- **validation** de l'application et du `regenerer` demandés par un agent (outil d'administration) : au courtier, inchangée.
Preuve : les services appelés SANS la famille refusent comme avant (`contrat-noyau` 10 : agent existant, nom trop long, proposition introuvable, usage,
supervision proposée ; rien n'est créé).

**Écarts au « déplacement pur »** : aucun dans les verbes (corps mot pour mot). Dans le test rouge, `DROITS` retiré de la liste des noms qu'une famille ne doit
pas citer : c'est aussi le nom du contrat de TOUTE famille (`DROITS = {…}`) ; la constante du cœur du même nom n'est de toute façon pas atteignable (contrat).

**Sorties qui changent** : `tests/equivalence-mur.py`, **28 scénarios** (ligne de commande ET voie du courtier : outil d'administration, aperçu en lecture,
application et `regenerer` qui attendent la validation, agent sans l'outil refusé), mesurés sur l'installation jetable ENTIÈRE hors du produit (consignes et
réglages par empreinte, liens de skills avec leur cible, profils Codex, bibliothèque, temporaires, sauvegardes `.avant`, journaux vérifiés au début).
**0 écart** ; `berger aide` inchangé (la docstring documente déjà les trois verbes). Référence :
```
d=$(mktemp -d) && git archive 4f69605 | tar -x -C "$d" && python3 tests/equivalence-mur.py --produire "$d" tests/attendus/equivalence-mur.json
```
Rejoué : deux mesures de `main` identiques octet pour octet ; la branche : 0 écart sur 28, aussi avec un autre `TMPDIR` et `BERGER_TMP_AGENTS`.

**Tests dont seule la FORME d'accès change** : `commandes-couverture` (36 verbes en famille, 25 au cœur ; `nouveau`, `regenerer`, `agent` quittent `RESTENT`),
`taille-fichiers` (cliquet 4 044 → 4 038), `vitrine` (empreinte du manuel). **Ajoutés** : `contrat-noyau` 1j bis (13 refus, 1 acceptation, vues et moteurs privés
des services, accès indirect 6 formes × 3 rangs) et 10 ; `tests/equivalence-mur.py` et sa référence.

### Partie « secrets » (demande 3 du 4d, pile locale ; taille de `bin/berger` : 4 038 → 4 030 lignes ; cliquet 4 030)

Ne contient QUE la partie secrets. Aucune fonction ne bouge : `valeurs_coffre`, `secrets_audit`, `secrets_audit_silencieux`, `coffre_sauvegarder`,
`phrase_sauvegarde` restent dans `bin/berger`.

**Le tri** : `secrets audit`, `coffre sauvegarder|purger` → famille `secrets` (`bin/commandes/secrets.py`). La spec les rangeait dans *depot* ; ils en sont
séparés pour une demande courte par partie (consigne de la mission : courtier, mur, secrets, dépôt). **Action** : deux services (`auditer_secrets()` →
`secrets_audit` ; `sauvegarder_coffre(motif=None)` → `coffre_sauvegarder`). **Lecture** : aucune ; **aucune lecture du coffre ni d'un secret par l'API de
lecture** (`contrat-noyau` 1k, pour TOUS les noms de l'API et de `BASE_NOYAU`). `PASSE` = `(IndexError, Refus, ErreurService)` pour les deux verbes.

**Les contrôles, ligne à ligne : aucun n'a bougé** (la famille ne lit ni le coffre, ni ses valeurs, ni la configuration : `contrat-noyau` 1j ter).
- **audit** : valeurs « secrètes » seulement (clé parlante, 8 caractères au moins, ni mot ordinaire, ni URL, ni chemin), zones (installation, transcriptions des
  moteurs, dossiers externes, `audit_zones_en_plus`), fichiers de plus de 50 Mo et liens ignorés, NOM de la clé seulement, jamais la valeur : dans `secrets_audit` ;
- **copie du coffre** : destinataire = clé PUBLIQUE `age1…`, motif, `age` présent, chiffrement, en-tête `age-encryption.org/v1` et taille vérifiés (copie non
  conforme supprimée), fichier 600 dans un dossier 700, ligne de retour arrière, purge au-delà de `garder_jours` : dans `coffre_sauvegarder`.
Preuve : les services appelés SANS la famille refusent comme avant et ne fuient rien (`contrat-noyau` 11 : audit qui nomme la clé sans la valeur, destinataire
absent, purge seule).

**Écarts au « déplacement pur »** : aucun dans les verbes (corps mot pour mot). Dans le test rouge, deux erreurs du test lui-même corrigées avant le code :
`CONFIG` retiré de la liste « absent de l'espace de la famille » à l'exécution (il est dans l'API de lecture depuis le lot 1, pour tous les modules, et ne
porte aucune valeur du coffre ; le contrôle statique vérifie que la famille ne le cite pas) ; le fichier d'audit écrit par le service appelé seul est effacé
avant de vérifier qu'une famille cassée n'en fait aucun.

**Sorties qui changent** : `tests/equivalence-secrets.py`, **18 scénarios + une garde** (faux `age` : destinataire et noms de fichiers relevés, jamais le
contenu ; une fuite posée dans le dossier d'un agent et dans une transcription de moteur ; une valeur faite de mots ordinaires ; copies horodatées gardées
une à une). **Garde propre au test** : aucune valeur du coffre dans une sortie, un appel ni un fichier écrit par berger, contrôlé à chaque scénario
(« fuites : aucune » avant et après). La valeur factice est masquée dans la référence (`<VALEUR DU COFFRE>`, après la garde). Normalisés : le nombre de
fichiers parcourus par l'audit (il compte les fichiers du PRODUIT copié, qui change à chaque lot) et le dossier des transcriptions (dérivé du chemin de
l'installation jetable). **0 écart** ; `berger aide` inchangé. Référence :
```
d=$(mktemp -d) && git archive 4f69605 | tar -x -C "$d" && python3 tests/equivalence-secrets.py --produire "$d" tests/attendus/equivalence-secrets.json
```
Rejoué : deux mesures de `main` identiques octet pour octet ; la branche : 0 écart sur 19.

**Tests dont seule la FORME d'accès change** : `commandes-couverture` (38 verbes en famille, 23 au cœur), `taille-fichiers` (cliquet 4 038 → 4 030),
`vitrine` (empreinte du manuel). **Ajoutés** : `contrat-noyau` 1j ter (9 refus dont l'import du chemin du coffre, 1 acceptation, vues et moteurs privés des
services, accès indirect 6 formes × 3 rangs) et 11 ; `tests/equivalence-secrets.py` et sa référence. Inchangés et verts : `coffre-sauvegarde`,
`cles-parlantes`, `web-session`, `web-connecter` (qui sauvegarde le coffre par `berger coffre sauvegarder`), `web-profils-masques`, `synthese`, `marques-produit`.

### Partie « dépôt » (demande 4 du 4d, pile locale ; taille de `bin/berger` : 4 030 → 4 021 lignes ; cliquet 4 021)

Ne contient QUE la partie dépôt. Aucune fonction ne bouge : `verifier_depot`, `git_installation`, `tete_installation`, `retour_arriere`, `installer`,
`redemarrer*`, `phrase_sauvegarde`, `sauvegarder`, `verifier_sauvegarde`, `restaurer` restent dans `bin/berger` ; `publier_main` reste dans
`bin/noyau/publication.py`, hors de toute API (`tests/publication.py` inchangé et vert ; `contrat-noyau` 1j quater : ni `api.py` ni la famille ne le nomment).

**Le tri** : `verifier-depot`, `installer`, `publier`, `sauvegarder`, `restaurer`, `verifier-sauvegarde` → famille `depot` (`bin/commandes/depot.py`).
`publier` était rangé « au cœur » au lot 3 (il appelait une fonction hors API) ; il rejoint le dépôt par un service. **Action** : six services
(`verifier_neutralite()` → `verifier_depot` ; `installer_forge(forge, branche="main")` → `installer` ; `publier_en_ligne(forge)` → `publier_main` ;
`sauvegarder_donnees()` → `sauvegarder` ; `restaurer_archive(archive, destination)` → `restaurer` ; `verifier_sauvegarde_distante()` → `verifier_sauvegarde`).
**Lecture** : aucune. `PASSE` = `(IndexError, Refus, ErreurService)` pour les six verbes.

**Les contrôles, ligne à ligne : aucun n'a bougé** (la famille ne fait ni git, ni chiffrement, ni WebDAV, ni lecture du coffre : `contrat-noyau` 1j quater).
- **neutralité** : fichiers suivis et prêts, chemins de données interdits, nom du propriétaire (aussi dans un mot), dossier personnel, marques fixes et
  privées, chemin du coffre propre à l'installation, réglages des outils, valeurs du coffre, exception de l'URL exacte du dépôt public : dans `verifier_depot` ;
- **installer** : dépôt git, avance rapide seule, HEAD = branche de la forge, `verifier-depot` et `regenerer` du NOUVEAU code, redémarrage détaché et
  contrôlé, retour arrière automatique (`reset --keep`, regenerer), trace et notification : dans `installer`, `retour_arriere` ;
- **publier** : équipe de la forge, option ambiguë, commit complet, avance rapide sans force, trace et notification : dans `publier_main` (noyau/publication.py) ;
- **sauvegarde** : section, phrase du trousseau (ou fichier 600 dans un dossier masqué), identifiants lus au coffre et passés à curl sur l'entrée standard,
  dossier temporaire 700, rotation, relecture par empreintes : dans `sauvegarder`, `verifier_sauvegarde`, `restaurer`, `phrase_sauvegarde` ;
- **validation** des actions `installer`, `publier`, `regenerer` demandées par un agent (outil d'administration) : au courtier, inchangée.
Preuve : les services appelés SANS la famille refusent comme avant (`contrat-noyau` 12 : installation qui n'est pas un dépôt git, sauvegarde sans section,
vérification sans section qui sort la `KeyError` d'avant).

**Écarts au « déplacement pur »** : aucun dans les verbes (corps mot pour mot). Dans le test rouge, deux contrôles du test lui-même resserrés avant le code :
le mot « publication » est permis dans l'AIDE de la famille (c'est le nom de l'option de `config.toml`, ligne d'aide reprise mot pour mot) — ce qui est
refusé, c'est d'importer ou de nommer le module `noyau.publication` ; la recherche des gestes (git, gpg, curl, WebDAV…) porte sur le code des verbes, pas
sur leur aide ni la docstring.

**Sorties qui changent** : `tests/equivalence-depot.py`, **24 scénarios + une garde**, sur une installation jetable qui est un dépôt git, avec sa forge locale
et un dépôt « en ligne » (origin de la forge), un WebDAV factice (un dossier), `gpg`, `secret-tool`, `curl`, `systemd-run` factices (verbe et fichiers relevés,
jamais la phrase ni les identifiants) ; le temporaire de la sauvegarde est HORS de l'installation (sinon l'archive le contiendrait). Garde propre au test : ni
la phrase de chiffrement ni le mot de passe du WebDAV dans une sortie, un appel ou un fichier relevé (« fuites : aucune » avant et après). Normalisés : le
nombre de fichiers suivis (celui du produit, qui change à chaque lot), la taille d'une archive et le nombre de fichiers comparés (dates des fichiers).
**0 écart.** Seule autre sortie changée : **`berger aide`** a **3 lignes de plus** (`publier`, `verifier-depot`, `verifier-sauvegarde`, que la docstring
du cœur ne documente pas sous la forme `berger <verbe>`). Référence :
```
d=$(mktemp -d) && git archive 4f69605 | tar -x -C "$d" && python3 tests/equivalence-depot.py --produire "$d" tests/attendus/equivalence-depot.json
```
Rejoué : deux mesures de `main` identiques octet pour octet ; la branche : 0 écart sur 25, aussi avec un autre `TMPDIR`.

**Tests dont seule la FORME d'accès change** : `commandes-couverture` (44 verbes en famille, 17 au cœur ; `publier` quitte `RESTENT`), `taille-fichiers`
(cliquet 4 030 → 4 021), `vitrine` (empreinte du manuel). **Ajoutés** : `contrat-noyau` 1j quater (9 refus dont l'import du module de publication, 1
acceptation, vues et moteurs privés des services, accès indirect 6 formes × 3 rangs) et 12 ; `tests/equivalence-depot.py` et sa référence. Inchangés et
verts : `publication`, `installer-master`, `redemarrage-courtier`, `verbe-prod`, `marques-produit`, `sha-fige`, `coherences-vps` ; `installation` donne dans
mon bac les deux MÊMES échecs que sur `main` 4f69605.

### Bilan du 4d (les quatre parties)

`bin/berger` : 4 050 → 4 021 lignes. 17 verbes déplacés dans 4 familles (`courtier` 6, `agents` 3, `secrets` 2, `depot` 6), 17 services ajoutés à `ACTIONS`
(41 au total), `transport` sorti de l'API de lecture. **Restent au cœur** (`transition`, 17 verbes) : `mcp-enveloppe`, `web`, `interface`, `planificateur`,
`espace`, `superviser`, `entretien`, `panneau`, `abonnement-claude`, `reveil`, `tache`, `relancer`, `espace-voulu`, `refaire-espace`, `reprendre`, `memoire`,
`vue` (voir « Écarts du 4d »). Équivalences : courtier 0/48, mur 0/28, secrets 0/19, dépôt 0/25 ; celles des sous-lots précédents inchangées (missions 0/40,
messages 0/86, équipes 0/99).

### Mise à jour depuis `main` a1cec6a (0.3.0, correctif web)

Fusion de `main` (6bf19a6), sans réécrire l'historique poussé. Deux conflits : `CHANGELOG.md` (la 0.3.0 résume les lots 4a à 4c ; les quatre entrées du
4d vont dans `[Unreleased]` › Changed) et `tests/vitrine.py` (empreinte du corps du manuel fusionné). `bin/berger` reste à 4 021 lignes (cliquet inchangé).
Contrat du noyau : 759 ok, 0 échec. Secrets 0/19 et dépôt 0/25 sans rien changer ; missions 0/40, messages 0/86, équipes 0/99.

**Références du courtier et du mur refaites sur `main` a1cec6a**, parce que `main` change leurs sorties, pas le 4d :
- un verdict `ADMIS` sans le contrôle (12) n'admet plus (`bin/moteurs/__init__.py` › `verdict_moteur`) : le faux verdict de `equivalence-courtier.py`
  porte désormais les deux lignes (12) de `_produit.LIGNES_12` (même assertion : « claude admis », puis « aucun moteur admis » sur un verdict `NON ADMIS`) ;
- réglages Claude générés (refus des outils web), arguments Codex (`web_search="disabled"`, `features.*=false`) et empreintes des fichiers générés.
Codes de sortie identiques dans les 76 scénarios ; seuls changent ces fichiers écrits, appels et sorties. Commandes :
```
d=$(mktemp -d) && git archive a1cec6a | tar -x -C "$d" && python3 tests/equivalence-courtier.py --produire "$d" tests/attendus/equivalence-courtier.json
d=$(mktemp -d) && git archive a1cec6a | tar -x -C "$d" && python3 tests/equivalence-mur.py --produire "$d" tests/attendus/equivalence-mur.json
```
La branche : courtier 0/48, mur 0/28.

### Mise à jour depuis `main` b8d1831 (interface web v2, réglages, fragments du journal)

Fusion de `main` (8562700), sans réécrire l'historique poussé. Sept conflits : `bin/berger` (`valider`, `refuser`, `installer` restent dans leurs familles
`courtier` et `depot` ; le décideur du cœur prend la version de `main`), `bin/moteurs/__init__.py` (`ACCORD_BYPASS` de `main` et `transport` du 4d),
`docs/manuel.md` (tableau verbe → famille : `action`, `conversation` de `main`), `tests/commandes-couverture.py` (63 verbes, 46 déplacés),
`tests/taille-fichiers.py`, `tests/vitrine.py` (empreintes par section de `main` ; « Dans Herdr », qui porte le paragraphe du 4d, recalculée par
`tests/manuel-empreintes.py`) et `CHANGELOG.md` (la ligne du 4d passe dans `changelog.d/modulaire-lot4.md`, règle des fragments).
`bin/berger` : 4 034 lignes sur `main`, 4 005 après la fusion (les 29 lignes du 4d) : cliquet 4 005.

**Garde reportée dans la famille `courtier`** : `main` donne au décideur du cœur (`decider`) l'option `--empreinte` (interface web : le sha256 de la
demande vue, revérifié sous le verrou des décisions) et le refus « déjà décidée ». Le geste et ses contrôles restent au cœur ; la famille et le service
`decider_validation` passent seulement `--empreinte` comme ils passent `--duree`. Sans ce report, `berger valider <n> --empreinte <x>` aurait ignoré
l'empreinte : cinq scénarios de plus dans `tests/equivalence-courtier.py` (empreinte fausse en validant et en refusant, sans valeur, juste, déjà décidée),
rouges sans le report (4 écarts sur 53), verts avec (0 sur 53).

**Références du courtier, du mur, des secrets et du dépôt refaites sur `main` b8d1831** : `main` y ajoute `.claude/settings.local.json` (accord du mode
bypass) aux fichiers écrits par `regenerer` et change les empreintes des réglages générés ; secrets inchangés. Commandes :
```
d=$(mktemp -d) && git archive b8d1831 | tar -x -C "$d" && python3 tests/equivalence-courtier.py --produire "$d" tests/attendus/equivalence-courtier.json
d=$(mktemp -d) && git archive b8d1831 | tar -x -C "$d" && python3 tests/equivalence-mur.py --produire "$d" tests/attendus/equivalence-mur.json
d=$(mktemp -d) && git archive b8d1831 | tar -x -C "$d" && python3 tests/equivalence-secrets.py --produire "$d" tests/attendus/equivalence-secrets.json
d=$(mktemp -d) && git archive b8d1831 | tar -x -C "$d" && python3 tests/equivalence-depot.py --produire "$d" tests/attendus/equivalence-depot.json
```
La branche : courtier 0/53, mur 0/28, secrets 0/19, dépôt 0/25 ; missions 0/40, messages 0/86, équipes 0/99. Contrat du noyau : 763 ok, 0 échec.

**Suite complète après la fusion de b8d1831 : quatre échecs, corrigés sans affaiblir une assertion.**
- `web-integre`, `codex-modele-strict` (arrivés avec `main` a1cec6a) et `claude-fige` (arrivé avec b8d1831) appelaient `verbe_args` dans l'espace de
  `bin/berger` ; depuis la partie « courtier », ce corps s'appelle `arguments_pont` (au cœur, corps identique). **Forme d'accès seule** : ils appellent
  `arguments_pont` ; mêmes assertions (outils web coupés, `-m` imposé au strict Codex, `DISABLE_AUTOUPDATER=1` chez Claude seulement).
- `equivalence-mur` dépendait de la longueur de `TMPDIR` : le dossier temporaire des agents de l'installation jetable le suit, et la limite de 44 octets
  (`TMP_MAX`) le refusait avec un chemin long (ma session) mais pas avec un chemin court (la suite) ; la référence d'avant portait ce défaut. Le test
  desserre la limite des deux côtés (`TMP_MAX = 400`, comme `equivalence-courtier`, qui garde un scénario du refus) ; référence refaite sur b8d1831, plus
  aucun avertissement de dossier temporaire ; la branche : 0 écart sur 28.
- `equivalence-mur` dépendait aussi de la MACHINE : `.codex/config.toml` interdit le temporaire commun de Claude (`/tmp/claude-<UID>`) seulement
  s'il existe (`tmp_des_autres`, `is_dir()`) ; présent pour la porte, caché dans le bac à sable où la référence était produite. Le test le place dans
  l'installation jetable (`TMP_COMMUN`, créé, des deux côtés) ; la ligne ÉCHEC nomme désormais le premier écart (champ, fichier), seule ligne que garde la
  porte. Référence refaite sur b8d1831 ; 0 écart sur 28.

## Après le 4d : deux faiblesses antérieures relevées par la relecture Codex (07/11/2026 ; go du propriétaire n° 58)

La relecture Codex du 4d (7/10) n'a perdu aucune garde ; elle relève deux faiblesses ANTÉRIEURES au lot. Un test rouge par voie, puis le correctif.

**1. Contrat du noyau.** `imports_interdits` ne jugeait `getattr` que sous la forme `getattr(o, 'littéral')` : `g = getattr` (ou en argument, en valeur
par défaut, dans un tuple, `operator.attrgetter`, `methodcaller`) passait, et `g(entree_privee, '__globals__')` rendait l'espace de `noyau.transport`
(chemin du coffre, transport, `sys`), d'où `noyau.actions._SERVICES`, registre mutable : une vue y ajoutait un service hors `ACTIONS` et le faisait
servir par `_geste` (prouvé de bout en bout, section 13).
- (a) Contrat statique : `getattr`, `setattr`, `delattr`, `hasattr` acceptés seulement appelés directement, au nom littéral non spécial ; tout autre emploi
  du nom est refusé (« alias de … ») ; `attrgetter` et `methodcaller` fermés (attribut et import) ; un import d'un nom fermé, de tout module, refusé ;
  une chaîne qui porte un nom d'attribut spécial (`__\w+__`), hors docstring, refusée. Les alias de `globals` et `vars` et `.__dict__` étaient déjà
  refusés : leurs preuves sont ajoutées. Aucun module actuel touché.
- (b) `_SERVICES` figé : `MappingProxyType`, posé UNE fois par `brancher` (un second branchement : `RuntimeError`), rien hors `ACTIONS` ; `_service`
  juge le nom contre `ACTIONS` avant tout registre (même un registre substitué ne sert pas `hors_actions`). Limite connue : en Python, du code qui tient
  l'espace d'un module peut toujours relier le nom `_SERVICES` ; c'est le contrat statique (a) qui interdit d'atteindre cet espace, le gel en limite l'effet.
- Tests : les preuves de panne du cœur (sections 6 à 12) rebranchaient un service APRÈS le chargement ; elles posent désormais la panne derrière le
  branchement de `bin/berger`, AVANT le chargement (`_PANNES`, `SURCHARGE[nom]`) : mêmes assertions. Contrat du noyau : 763 → 791 contrôles, 0 échec.

**2. Publication.** `publier_forge` poussait sans rejouer `verifier-depot` (module du cœur sans accès à `bin/berger`). Le cœur lui passe désormais
`verifier_depot` (argument `controle` obligatoire), rejoué après les contrôles du remote, juste avant le premier push, en publication manuelle comme
automatique. En échec : fichiers fautifs montrés (jamais une valeur), « publication échouée : dépôt non neutre (verifier-depot en échec) : rien n'est
poussé » tracé et notifié en urgence, code 1 (après une installation aussi : l'installation reste). Propre : sortie inchangée. Tests : `tests/publication.py`
section 11 (dépôt sale → refus et zéro push ; propre → contrôle avant l'envoi, un push de main), 40 → 45 contrôles.
**Le contrôle porte sur le commit QUI PART** (demande de master, test rouge ca7d29b, correctif b084073) : rejoué d'abord sur l'arbre installé,
il laissait partir `main` de la forge en avance avec une donnée privée. `verifier_depot(forge=…, commit=…)` lit désormais les chemins et fichiers du
commit poussé dans les objets git de la forge (`contenu_commit` : `ls-tree`, `cat-file --batch`), en manuel comme en automatique ; ni extraction
(une archive omettrait les fichiers `export-ignore`), ni fichier écrit ; une lecture en échec fait échouer la publication sans envoi. Sans commit,
`verifier-depot` contrôle l'installation comme avant. `equivalence-depot` : le scénario « publier » poussait un commit portant le nom du
propriétaire (resté dans la forge après le retour arrière du cas précédent) ; refusé désormais (écart voulu), la marque est retirée de la forge
avant de mesurer la publication propre ; référence refaite sur `main` 39c50dd, 0 écart sur 25.
**Limite qui reste** : le contrôle juge l'ARBRE du commit poussé ; ses ancêtres partent avec lui. Un fichier privé ajouté puis retiré dans
l'historique non encore en ligne partirait. Contrôler chaque commit nouveau (absent du dépôt en ligne) est possible : non fait ici, à décider.
