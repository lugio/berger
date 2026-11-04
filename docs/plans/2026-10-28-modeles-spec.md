# Choix des moteurs et des modèles : une table, une règle écrite, un choix tracé (spec)

Règle de go : **mixte**. Le **courtier fait partie du cœur** (courtier, gardes, droits, coffre, règles de validation : le go explicite
du propriétaire est requis **même en local**). Classement des lots, vérifié contre le code (voir « Lots ») :
- **Lots 1 et 2 : aucun go spécial, coordinateur seul.** Ils ne modifient **aucun fichier de `courtier/`** : le type de travail voyage dans une
  ligne `Type : <type>` du texte de mission (comme `Règle de go :` et `Hors go :`), donc ni les verbes ni le plafond de paramètres ne changent.
  Si, à la relecture, un lot devait toucher `courtier/`, il passe **cas 1**.
- **Lots 3, 4 et 5 : cas 1, go du propriétaire inscrit sur CE fichier avant la première ligne de code.** Lot 3 : admission d'un modèle
  (règle de validation). Lot 4 : bascule, il modifie `demander()`, `demarrer_agent()` et l'ordre d'admission `choisir_moteur()` : le lancement
  des agents sous mur strict. Lot 5 : garde du chef de projet (`courtier/outils/equipe_chef.py`).
- **Ordre avec le chantier modulaire** : le lot 4 de CETTE spec passe **après** le lot 4 du chantier modulaire (cas 1 aussi, il déplace
  `demander`, missions et équipes), jamais avant ni en parallèle (point « Lots »).
Cette spec n'est que du texte : aucun code n'est écrit tant que le lot concerné n'a pas son go. Rien de propre à un moteur dans le
cœur : ce qui l'est va dans `bin/moteurs/<moteur>.py`.

## Constat (mesuré sur `main`, 83e1436)

1. **Le choix existe et personne ne l'emploie.** `mission()` (bin/berger:1775) et `equipe_ouvrir()` (bin/berger:1953) acceptent `moteur` et
   `modele`, via `berger mission … --moteur/--modele`, `berger equipe ouvrir … --moteur/--modele`, et les verbes du courtier
   (`courtier/courtier:593-596` pour `equipe ouvrir`, `:610` pour `mission confier` : ils passent `[claude|codex] [modèle]`). Aucun `MISSION.md` lisible
   depuis un développeur ne porte « modèle : » (`grep "modèle :" agents/*/MISSION.md` : aucun résultat ; les dossiers des autres agents ne
   sont pas lisibles ici, le chef de projet confirme `modele = null` chez lui) ; aucun `agent.conf` lisible n'a de clé de modèle. Conséquence mesurée : partout, le modèle par défaut du moteur.
2. **Cause précise du « personne ne l'emploie ».** Le seul garde-fou est `MISSIONS.get("modeles_<moteur>", [])` (bin/berger:1786 et
   :1961) : la liste des modèles permis, lue dans la table `[missions]` de `config.toml`. Cette table n'existe que **en commentaire** dans
   `config.exemple.toml:113-116` et **n'existe pas** dans le `config.toml` de l'installation (aucune table `[missions]`, ni `max` : le défaut
   3 s'applique) : la liste permise est donc `[]` et tout `--modele` est refusé. **Aujourd'hui, `equipe ouvrir … <modèle>` et
   `mission confier … <modèle>` sont refusés** (« modèle non permis pour claude : sonnet (permis : aucun) ») : un chef de projet ne peut
   pas confier une tâche à Sonnet, même légère, ce qui coûte de la consommation de tokens (remarque du propriétaire, 28/10). Le chemin est
   mort par construction.
   **Pas immédiat, sans code** (à décider par le propriétaire, avant le lot 1) : écrire dans `config.toml`
   ```toml
   [missions]
   modeles_claude = ["sonnet", "opus"]
   modeles_codex  = ["gpt-6.1-sol", "gpt-6-astra"]   # équivalent Codex : noms de la table de départ, à confirmer par le propriétaire
   ```
   Vérifié dans le code que cela suffit : `CONFIG` est relu à chaque lancement de `bin/berger` (`bin/noyau/config.py:24`, `MISSIONS` à
   `bin/noyau/lectures.py:141`) et le courtier appelle `bin/berger` à chaque verbe (`courtier/courtier:595`, `:610`), donc aucun
   redémarrage ; `mission()` (bin/berger:1786-1787) et `equipe_ouvrir()` (bin/berger:1961-1962) acceptent alors tout modèle de la liste ;
   `mission()` l'écrit dans `MISSION.md` (`moteur : claude · modèle : sonnet`, bin/berger:1793, motif de `reglages_mission` compatible) et
   `args_moteur` ajoute `--model sonnet` au lancement (bin/moteurs/__init__.py:225-226). Ce que cela **ne** donne **pas** : ni règle (c'est
   l'appelant qui choisit), ni trace du niveau, ni épreuve du modèle ; un nom mal écrit n'est refusé qu'à l'usage par le moteur. `max` reste à 3.
   Le **nom exact** accepté par `claude --model` (alias `sonnet`) et par `codex -m` n'est pas vérifiable ici (pas de réseau) : le chef de projet
   fait un essai à `leger` avant d'en dépendre.
3. **Aucun niveau, aucune règle de choix.** `config.toml` n'a ni table de modèles par niveau, ni lien entre un type de travail et un
   modèle. Le modèle d'une mission ne vit que dans l'en-tête `moteur : X · modèle : Y` de `MISSION.md`, lu par `reglages_mission`
   (bin/noyau/lectures.py:144, motif `^moteur : (\w+)(?: · modèle : ([\w.-]+))?$`). Rien n'y garde un niveau ni une raison.
4. **Du propre à un moteur dans le cœur partagé.** `args_moteur` (bin/moteurs/__init__.py:223-226) ajoute `--model` pour Claude et `-m`
   pour Codex : un test `m == "claude"` dans le module commun. Codex n'a aucun réglage d'effort de raisonnement nulle part
   (`grep reasoning bin/berger` : seulement le pied de page `PIED_CODEX`).
5. **La bascule existante ne regarde ni le quota ni le modèle.** `demander()` (bin/berger:2273) essaie `premier` puis l'autre moteur ;
   un échec est une panne simulée (`AGENT_PANNE`), un moteur non admis (`moteurs.moteur_admis`), un code de retour non nul ou un délai
   de 300 s ; les échecs sont rendus à l'appelant. `choisir_moteur()` (bin/moteurs/__init__.py:196) bascule au lancement d'un agent strict
   quand le moteur n'est pas admis et l'écrit au journal de l'agent. Le **quota** (`quota_moteurs()`, bin/noyau/lectures.py:505 :
   fenêtres 5 h / 7 j de Claude, `primary`/`secondary` de Codex, en %) ne sert qu'à l'affichage : la vue Tokens colore à 80 % (jaune) et 95 %
   (rouge) mais aucune bascule ne s'en sert.
6. **L'admission est par moteur et version, pas par modèle.** `verdict_moteur(m)` lit `tests/contrats/<moteur>-<version>.txt`
   (1re ligne `ADMIS` / `NON ADMIS`) ; `moteur_admis` joue `tests/contrat-moteur.sh` si la version est « jamais vue ». Aucun modèle n'y est prouvé.
7. **Visibilité.** `suivi()` (bin/berger:1821) rend `moteur` et `modele` (nuls aujourd'hui) ; la vue Missions affiche le modèle ;
   la fiche (`identite_texte`, bin/noyau/lectures.py:208) n'affiche que « moteur par défaut » ; la vue Tokens ne garde que **le dernier
   modèle vu** par (agent, moteur) (`bin/vues/tokens.py:35`, `der["mod"]`) : pas de consommation **par modèle**, alors que chaque
   lecteur (`lire_conso_claude`, `lire_conso_codex`) range déjà `mod` dans chaque réponse.
8. **Le chef de projet fait parfois le travail.** Le gabarit du chef (commun/modeles/equipe-chef-de-projet.md:45-54) lui donne la
   finition de branche (`finition = "chef"`) et la relecture ; rien n'empêche, ni ne signale, qu'il code ou finisse lui-même une tâche
   qu'un développeur aurait pu porter. Les demandes gardent déjà `origine`, `agent`, `rejeux` (courtier/outils/equipe_chef.py:102,264,343) :
   de quoi calculer un signal sans nouvelle collecte.

**Cause racine** : le choix du modèle a été ajouté comme un paramètre libre (vérifié contre une liste vide) et non comme une politique :
rien ne dit quel modèle pour quel travail, rien ne le garde, et la panne d'un moteur n'a jamais été reliée au quota ni au niveau.

## Cible

```
config.toml              [modeles.<moteur>.<niveau>] : la table ; [modeles.types] : type de travail → niveau ; [modeles.choix] : préférence.
bin/moteurs/<moteur>.py  MODELES_DEFAUT (suggestion pour config.exemple), args_modele(modele, effort), efforts_permis : tout le propre au moteur.
bin/moteurs/__init__.py  choisir_couple(a, type, …) : le choix, indépendant du moteur ; admission d'un modèle ; trace.
MISSION.md               ligne 2 « niveau : … · raison : … » ; suivi, fiche, Tokens la montrent.
```

### 1. La table des modèles (`config.toml`)

Une table par moteur **installé et admis** et par niveau (`gros`, `moyen`, `leger`) ; chaque entrée est un modèle, avec son effort si le moteur en a :

```toml
[modeles.claude]
gros  = [{modele = "opus"}]
moyen = [{modele = "sonnet"}]
leger = [{modele = "haiku"}]
[modeles.codex]
gros  = [{modele = "gpt-6-astra", effort = "high"}]
moyen = [{modele = "gpt-6.1-sol", effort = "medium"}]
leger = [{modele = "gpt-6-luna",  effort = "low"}]
```

Un exemple **neutre** (noms déjà employés par `config.exemple.toml:115-116`) est ajouté à `config.exemple.toml`, commenté, avec la règle
de lecture. `[missions] modeles_<moteur>` (constat 2) est **remplacé** par la table : `mission()` et `equipe_ouvrir()` valident contre elle.
Un niveau peut avoir plusieurs modèles (le premier convient par défaut ; les autres servent à la préférence, point plus bas).
**Un moteur absent de la table n'entre pas dans le choix** et le refus le nomme ; **un nouveau moteur** = un fichier `bin/moteurs/<m>.py`
(contrat existant + `args_modele` + `efforts_permis`) et une section `[modeles.<m>]` : le cœur et `choisir_couple` n'ont aucune ligne à changer.
`args_moteur` n'écrit plus `--model`/`-m` : il appelle `module(m).args_modele(modele, effort)`.

### 2. La règle de choix par type de travail

`[modeles.types]` est une table **lisible par les tests** : type → niveau. Valeurs de départ, écrites dans `config.exemple.toml` :
- **gros** : `spec`, `relecture`, `securite`, `courtier`, `mur`, `decision` ;
- **moyen** : `code`, `deplacement`, `tests` ;
- **leger** : `docs`, `resume`, `surveillance`.

Le **type** voyage dans le **texte de mission**, sur une ligne seule `Type : <type>` (comme `Règle de go : cas 1` et `Hors go : …`,
`courtier/outils/_portes.py:156-157`) : **aucun paramètre de plus, aucun verbe ni aucune ligne du courtier changés**. Le plafond de paramètres
(`courtier/courtier:942`, cinq chaînes) est **déjà atteint** par `equipe ouvrir` (projet, sujet, mission, moteur, modèle ; `mission confier` en a
quatre) : un type en sixième paramètre le dépasserait. La ligne est lue par `bin/noyau/modeles.py` (motif `(?im)^\s*type\s*:\s*([a-z]+)\s*$`,
première occurrence), appelée par `mission()` et `equipe_ouvrir()` avant d'écrire `MISSION.md` ; elle reste dans le texte. Les types
(`spec`, `code`, `securite`, `courtier`…) ne sont pas des mots de la règle de go (`GO_MOTS`, `_portes.py:153`) : une ligne `Type :` ne marque
jamais un sujet à tort (un test le fige, sans modifier `_portes.py`). Le niveau vient du type ; le choix du couple (point suivant) en découle ;
un moteur et un modèle explicites (arguments existants, 4ᵉ et 5ᵉ paramètres) restent permis
**s'ils sont dans la table** (le niveau enregistré est celui de la table, la raison dit « choix explicite de <par> »). Type absent **et** modèle
absent : le niveau déclaré dans `agent.conf` (`niveau =`, facultatif) ; sinon **refus nommé** « type de travail manquant (ligne « Type : spec », « Type : code »…) ».
Deux lignes `Type :` différentes : refus nommé.
Un type inconnu est refusé avec son nom et la liste. Jamais de repli sur le gros modèle.
**Inscrit** : `MISSION.md` garde sa ligne 1 telle quelle (`moteur : X · modèle : Y`, le motif de `reglages_mission` ne change pas) et gagne une
ligne 2 `niveau : gros · raison : type spec (règle) · effort : high`. `suivi` rend `niveau`, `raison`, `effort` ; la vue Missions les affiche.

### 3. Le choix du couple moteur + modèle

Le choix porte sur **tous les couples (moteur, modèle) du niveau demandé, disponibles à l'instant**. Un couple est **disponible** quand son moteur réunit quatre conditions :
1. **autorisé** pour l'agent : `moteur` et `panneaux` de son `agent.conf` (réglage existant, `conf()` bin/noyau/agents.py:24), ou la clé facultative `moteurs =` si l'agent doit en avoir davantage ;
2. **admis** pour sa version (`moteur_admis`, constat 6) et le **modèle prouvé** (point 6) ;
3. **quota non épuisé** : aucune fenêtre de `quota_moteurs()` au-dessus de `[modeles.choix] quota_max` (95 %, la couleur rouge de la vue Tokens). Un quota **non mesuré** n'exclut pas le moteur, mais la raison le dit (« quota non mesuré ») ;
4. **pas en panne** : pas de panne constatée sur ce moteur dans les `[modeles.choix] panne_min` dernières minutes (30). La panne vient de `demander()` (échec de code, délai) et de l'ouverture d'agent ; elle est inscrite dans `courtier/pannes-moteurs.json` (écrit par Berger, jamais par un agent).

**Préférence** (plusieurs couples conviennent au même niveau) : `[modeles.choix] preference =`
- `ordre` : l'ordre de `ordre = ["claude", "codex"]` fixé par le propriétaire (**défaut**, déterministe) ;
- `moins_consomme` : le moteur dont la fenêtre la plus chargée est la plus basse ;
- `repartir` : le moteur le moins choisi sur les 24 dernières heures (compte de la trace), pour étaler entre abonnements.
**Le choix et sa raison sont tracés** : une ligne au journal de l'agent (`journal(a, …)`) et une ligne JSON dans `courtier/choix-modeles.jsonl`
(agent, type, niveau, couple retenu, couples écartés avec la cause de chacun, règle de préférence, heure) ; la raison figure aussi dans `MISSION.md`.
**Aucun couple disponible** : refus nommé « niveau gros : aucun couple disponible — claude: quota 97 % ; codex: non admis (…) ». Un **niveau
voisin** n'est permis que si `[modeles.choix] voisin = "moyen"` (par niveau demandé, absent par défaut) l'autorise ; la raison dit alors « niveau
gros indisponible, moyen employé, voulu par la règle ». Pas de clé = pas de voisin. Jamais de repli silencieux.

### 4. Le chef de projet : déléguer et superviser

Le chef de projet **reste sur le gros modèle** (la relecture, la décision et la sécurité sont du niveau gros) mais **ne code pas** et **ne fait pas lui-même
la finition** d'une tâche qu'un développeur peut porter. Trois options comparées :

| Option | Ce que ça fait | Pour | Contre |
|---|---|---|---|
| **A. Signal en Synthèse** | source d'alerte (`SOURCES_ALERTES`, comme `alertes_moteurs`) : jaune quand le chef a porté seul ≥ 2 demandes de type moyen/léger sur 7 jours | aucun blocage, mesure visible, rien dans les gardes | n'empêche rien ; se lit après coup |
| **B. Refus** | le courtier refuse `demander-fusion` du chef sur une branche de type moyen/léger sans développeur ouvert pour ce sujet | contraignant | touche une garde (cas 1) ; bloque une urgence réelle ; le chef est le gardien, un refus sans sortie le coince |
| **C. Rappel** | au moment de la demande du chef, la réponse du courtier ajoute « ce sujet est de niveau moyen : confie-le (`equipe ouvrir`, avec une ligne « Type : <type> » dans la mission) ou écris la raison » ; la raison est demandée, tracée, jamais bloquante | corrige au bon moment, garde une raison, aucune urgence bloquée | demande un champ de plus à la demande |

**Recommandation : C, puis A sur récidive, B écartée pour l'instant.** Le rappel arrive à l'instant où le chef agit (le seul où il sert) et
laisse la porte ouverte à l'urgence avec une raison écrite ; le signal A n'ajoute que le compte des raisons « urgence » répétées. B est
rouvrable si le compte A reste jaune deux semaines de suite. Le type d'une branche vient du type de la mission du développeur (`origine`
de la demande) ; une branche sans développeur compte comme `code`. C et A sont les seuls à toucher `courtier/outils/equipe_chef.py` : **cas 1**, go requis.

### 5. Bascule vers l'autre moteur (quota ou panne)

La bascule existante est celle de `demander()` (bin/berger:2273) et de `choisir_moteur()` : on **ne crée pas de seconde bascule**.
`demander()` ordonne ses moteurs par `choisir_couple` au lieu de `[premier, autre]` : un moteur épuisé ou en panne est écarté **avant**
l'essai, et un échec constaté alimente `pannes-moteurs.json` pour les choix suivants. Le moteur de bascule est pris **au niveau équivalent**
du même type de travail (le couple de la table de l'autre moteur), jamais au niveau supérieur par commodité. La bascule est tracée comme le
choix (journal + `choix-modeles.jsonl`, `raison: "bascule : claude épuisé (97 %)"`), et la mission en cours garde son niveau d'origine.
Si l'autre moteur n'a pas de modèle à ce niveau : refus nommé (point 3). L'ouverture d'un agent (`demarrer_agent`) suit la même règle.

### 6. Un modèle est prouvé avant d'être utilisé

Le contrat d'admission (`tests/contrat-moteur.sh`) reste **inchangé** : il prouve le **mur** par version de moteur (outils vus, MCP, socket). Il gagne une
épreuve de **lancement par modèle** : pour chaque modèle de la table, le moteur démarre avec ce modèle dans le même cadre strict et répond ; le résultat
est écrit dans le même fichier de verdict, sous la forme `modèle <nom> : ADMIS` ou `modèle <nom> : REFUSÉ (cause)`, **par version de moteur**.
Un modèle absent de ces lignes est « jamais vu » (contrat joué avant le premier usage, comme un moteur) ; un modèle `REFUSÉ`, **retiré** par le
moteur ou **inconnu de la table** est refusé **avec son nom** (« modèle opus-9 inconnu pour claude : table [modeles.claude] »). Un changement de version du moteur rejoue
l'épreuve. Il n'y a **jamais** de repli silencieux sur le gros modèle : le refus remonte à l'appelant et à la Synthèse (jaune « modèle <nom> jamais prouvé », rouge « refusé »).

### 7. Visibilité : suivi, fiche, Tokens

- **`suivi`** : `moteur`, `modele`, `niveau`, `raison`, `effort` (champs ajoutés à `bin/schemas/` avec le test de schéma existant).
- **Fiche** (`identite_donnees`/`identite_texte`) : une ligne « modèles autorisés » (couples disponibles par niveau, avec la cause de ceux qui ne le sont pas) et, pour un agent en mission, le couple retenu et sa raison.
- **Tokens** (`bin/vues/tokens.py`) : une section **par modèle** (lus, écrits, 24 h et 7 j, depuis le champ `mod` déjà collecté) en plus de la ligne par agent ; la ligne par agent garde le dernier modèle.

## Refus

- Une demande de fusion qui mélange le choix des modèles et un autre sujet.
- Un modèle absent de la table, retiré ou refusé par l'épreuve : refusé avec son nom (jamais remplacé).
- Un type de travail inconnu ou absent sans niveau d'agent : refusé avec la liste des types.
- Aucun couple disponible au niveau demandé, sans voisin autorisé par la règle : refus nommé avec la cause de chaque couple écarté.
- Un test `if moteur == "claude"` (ou tout nom de moteur) dans le cœur ou `choisir_couple`.
- Une écriture de `pannes-moteurs.json` ou de `choix-modeles.jsonl` par autre chose que Berger ; un agent ne peut ni la lire pour la modifier ni la réécrire.
- Le lot 3, le lot 4 ou le lot 5 sans go inscrit du propriétaire sur ce fichier ; le lot 4 avant le lot 4 du chantier modulaire.
- Un type de travail passé par un paramètre de plus, un verbe ou une ligne du courtier modifiés par le lot 1 ou 2.

## Tests

Un test et un refus par point (chacun ajouté avec le lot qui l'exige) :
- **Table** (lot 1, `tests/modeles-table.py`) : `config.exemple.toml` charge ; chaque moteur chargé a ses trois niveaux ou un refus nommé ; un moteur ajouté dans un dossier jetable (`moteurs/_essai.py` posé par le test) entre dans le choix sans modifier `bin/berger`. *Refus* : niveau inconnu, effort hors de `efforts_permis`, moteur sans section. *Garde* : aucun fichier sous `courtier/` dans le diff du lot (cf. lot 1).
- **Règle par type** (lot 1) : chaque type de `[modeles.types]` rend le niveau attendu (les 12 types figés dans le test) ; `MISSION.md` porte la ligne 2 ; `reglages_mission` lit toujours la ligne 1. une ligne `Type : securite` ne marque pas le sujet « règle de go » (`marquage`, `_portes.py`, inchangé). *Refus* : type inconnu, type manquant sans `niveau =`, deux lignes `Type :` différentes.
- **Choix du couple** (lot 2, `tests/modeles-choix.py`, moteurs et quotas simulés) : quatre conditions, une par cas ; préférences `ordre`, `moins_consomme`, `repartir` ; trace écrite (journal + jsonl) avec les couples écartés. *Refus* : aucun couple (message nomme chaque cause) ; voisin absent ⇒ refus, voisin déclaré ⇒ emploi tracé « niveau voisin ».
- **Bascule** (lot 4, **cas 1**, étend `tests/echanges.py` et `AGENT_PANNE`) : claude à 97 % ⇒ `demander` part sur codex, au niveau équivalent, trace « bascule » ; deux pannes ⇒ échecs rendus, aucun repli. un moteur non admis n'est jamais rouvert par le choix (`moteur_admis` appelée en premier, résultat inchangé) ; `demarrer_agent` sous mur strict lance le même moteur qu'avant quand rien n'est épuisé ni en panne. *Refus* : l'autre moteur sans modèle de ce niveau.
- **Épreuve de modèle** (lot 3, étend `tests/contrat-moteur.py`) : un faux moteur admis dont un modèle échoue ⇒ ligne `REFUSÉ`, couple écarté, Synthèse rouge ; version changée ⇒ épreuve rejouée. *Refus* : modèle inconnu/retiré refusé avec son nom, jamais substitué.
- **Chef de projet** (lot 5, étend `tests/equipe*.py`) : demande du chef sur un sujet moyen sans développeur ⇒ rappel dans la réponse et raison tracée ; deux raisons « urgence » en 7 jours ⇒ jaune en Synthèse ; sujet gros ⇒ aucun rappel. *Refus* : raison vide refusée quand le rappel s'applique ; aucune demande n'est bloquée par le rappel.
- **Visibilité** (lot 1 pour suivi, lot 2 pour fiche et Tokens, `tests/missions.py`, `tests/tokens.py`, schémas) : `suivi` rend les cinq champs ; la fiche montre le couple ; Tokens agrège deux modèles du même agent en deux lignes. *Refus* : un schéma sans le nouveau champ échoue.
- **Inchangés et verts** : `tests/argv-*.py`, `contrat-*`, `regle-go`, `sondes-gardes`, `marques-produit.py`, `verifier-depot`, toute la suite (`tests/tout.sh`).

## Lots

Une demande de fusion par lot, dans l'ordre ; chaque lot s'installe seul et laisse `main` sain. Le comportement actuel (aucun modèle, moteur de l'agent) reste celui d'un `config.toml` sans table `[modeles]`, tant que le propriétaire ne l'a pas écrite : **la table absente = rien ne change**, dit dans le manuel.

### Lot 1 — table, types, trace de la mission (aucun go spécial : aucun fichier de `courtier/`)
- **Fichiers** : `bin/noyau/modeles.py` (lecture de `[modeles]`, ligne `Type :`, niveaux ; sans nom de moteur), `args_modele` et `efforts_permis` dans `bin/moteurs/{claude,codex}.py`, `args_moteur` simplifié, `mission()`/`equipe_ouvrir()` (lecture de `Type :` dans le texte, validation contre la table), `reglages_mission` + ligne 2, `suivi`, `config.exemple.toml`, manuel, CHANGELOG.
- **Classement** : le lot **ne touche pas** `courtier/courtier`, `courtier/outils/*` ni `_portes.py` : les verbes `mission confier` et `equipe ouvrir` gardent leurs paramètres (4 et 5), le plafond de cinq (`courtier/courtier:942`) n'est pas approché, et la ligne `Type :` traverse le courtier comme n'importe quel texte de mission. Il ne touche ni mur, ni droits, ni secret, ni règle de validation. **Aucun go spécial.** Garde-fou : un test (`tests/modeles-table.py`) échoue si le diff du lot contient un fichier sous `courtier/` ; si la relecture en trouve un, le lot est reclassé **cas 1** et attend son go.
- **Risques** : (a) `[missions] modeles_*` retiré : les installations qui l'auraient écrit gardent leur liste lue en repli **nommé** pendant une version (le pas immédiat du constat 2 reste valable jusqu'au lot 1) ; (b) l'effort Codex se passe par un réglage du profil ou une option de ligne de commande **à vérifier sur la version installée** avant d'écrire `args_modele` ; (c) la ligne `Type :` est dans le texte libre d'une mission : un chef qui l'oublie reçoit le refus nommé du point 2, jamais un repli.

### Lot 2 — choix du couple, quatre conditions, préférence, fiche et Tokens (aucun go spécial)
- **Fichiers** : `choisir_couple` et les pannes dans `bin/moteurs/__init__.py`, trace `courtier/choix-modeles.jsonl`, vues fiche et Tokens (+ schémas). Le choix **n'applique** rien au lancement des agents tant que le lot 4 n'est pas là : il décide pour `mission`/`equipe ouvrir` seulement.
- **Risques** : un quota mal lu ne doit jamais exclure un moteur par erreur (non mesuré ⇒ disponible, dit) ; le comptage `repartir` doit supporter un journal absent.

### Lot 3 — épreuve de modèle dans l'admission (cas 1, go inscrit avant le code)
- **Fichiers** : `tests/contrat-moteur.py` (+ `.sh`), lecture des lignes `modèle …` dans `verdict_moteur`/`moteur_admis`, alerte Synthèse. Touche une **règle de validation** (l'admission) : relu ligne à ligne.
- **Risques** : un modèle prouvé à tort ouvre un moteur au mur strict ; un contrat plus long (le délai de 1 200 s est par moteur : les modèles sont éprouvés l'un après l'autre sous le même verrou, avec un plafond par modèle).

### Lot 4 — bascule par quota et panne (**cas 1**, go inscrit avant le code)
- **Fichiers** : `demander()` ordonné par `choisir_couple`, `pannes-moteurs.json`, `demarrer_agent` (même règle) et l'ordre d'admission `choisir_moteur()` (`bin/moteurs/__init__.py:196`). Le contrat de sortie de `demander` (texte, moteur, échecs) ne change pas.
- **Classement** : `demarrer_agent` (bin/berger:1326) lance les agents sous **mur strict** et `choisir_moteur` décide quel moteur est admis à ce lancement : le lot **change ce qui est lancé et dans quel ordre l'admission se prononce**. C'est une règle de validation et le lancement du mur : **cas 1**, go explicite du propriétaire inscrit sur ce fichier, même en local. Il **ne se classe pas** « coordinateur seul » (l'argument « réutilise `demander` » ne suffit pas : `demander` appelle `moteur_admis` et construit le lancement strict). Garde-fou conservé : `moteur_admis` **n'est pas modifiée** (un moteur non admis reste écarté avant tout autre critère), `choisir_couple` ne peut qu'**écarter** des moteurs de plus (quota, panne), jamais en ajouter un que l'admission refuse ; un test le prouve.
- **Ordre avec le lot 4 du chantier modulaire** (`docs/plans/2026-10-27-modulaire-spec.md`, lot 4, cas 1) : ce lot déplace dans `bin/commandes/` les missions, les équipes, les messages dont `demander`, et la génération du mur. Les deux touchent donc `demander()` et le lancement des agents. **Ordre retenu : le lot 4 modulaire d'abord** (déplacement à l'identique, un seul go), **puis le lot 4 de cette spec**, écrit sur le code déjà déplacé et sous son propre go inscrit. Jamais en parallèle, jamais avant : écrire la bascule dans `bin/berger` pour la voir ensuite déplacée double le risque sur du code de mur. Les lots 1 à 3 de cette spec, eux, n'attendent pas (ils ne touchent ni `demander` ni le lancement) ; s'ils entrent après le lot 4 modulaire, ils se rebasent par **fusion de `main`**, sans réécriture.
- **Risques** : `demarrer_agent` lance les agents : une erreur se voit au premier agent relancé ; installation hors production d'abord, en journée, retour arrière de `installer`.

### Lot 5 — garde du chef de projet (cas 1, go inscrit avant le code)
- **Fichiers** : `courtier/outils/equipe_chef.py` (rappel), source d'alerte « délégation » (signal), gabarit `equipe-chef-de-projet.md` (la règle écrite). Touche le courtier et ses gardes.
- **Risques** : un rappel qui bloque une urgence (c'est pourquoi B est écartée) ; le type d'une branche mal déduit ⇒ rappel injustifié : la raison libre reste l'issue.

## Livrables et points ouverts

Pour chaque lot : la demande de fusion, les tests joués avec leur résultat, la ligne de manuel, la table de départ proposée au propriétaire (le **choix des modèles de la table lui appartient**, la spec ne le fait pas).

À trancher à la lecture :
- **Préférence par défaut** : `ordre` (déterministe, claude d'abord) ou `repartir` (étale les abonnements) ? Proposition : `ordre`, `repartir` à activer quand un quota dépasse 80 %.
- **Épreuve de modèle** : dans le contrat existant (proposé, un seul verdict par version) ou fichier séparé `<moteur>-<version>.modeles.txt` ? Le premier garde un seul verdict ; le second n'ouvre pas la règle de validation du mur.
- **Seuils** : `quota_max` 95 % et `panne_min` 30 min : bons départs ? Le propriétaire les règle, l'exemple les montre.
- **Option du chef de projet** : C puis A recommandées ; confirmer l'abandon de B.
