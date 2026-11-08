# Extensions : installer et retirer une skill, un serveur MCP, une vue ou un outil du courtier — spec courte (07/11/2026)

Règle de go : cas 1, droits et gestion des secrets. Une extension donne un droit à un agent (méthode, serveur MCP, outil du
courtier qui détient des clés), et un outil ou un MCP peut nommer une clé du coffre ou demander le réseau. Demande du
propriétaire du 07/11. Cette spec ne contient **aucun code** : le code attend le go. La page web en écriture est un lot séparé, plus tard,
sur un go à part. Pas de dépôt distant : la source est un dossier local ou un dépôt git local.

## Mesure : comment on ajoute aujourd'hui (main 39c50dd)

| Genre | Ce qu'on édite à la main | Ensuite | Contrôle automatique | Mal fait |
|---|---|---|---|---|
| Skill | `skills/<nom>/SKILL.md` (catalogue, ou `[skills] dossier`), `commun/skills/` (produit) ou `agents/<a>/skills-agent/` ; `skills =` dans `agent.conf` ou `[equipes.<p>] skills` | `berger regenerer` (liens `.claude/skills`, `.agents/skills`, `lier_skills`) | `motif_refus_skill` : nom du fichier du coffre et regex `[skills] interdits`, sur le catalogue et le produit **seulement** | Un secret dans `~/.claude/skills` ou `skills-agent/` passe **sans bruit** (seul `secrets audit` le verrait, si la zone est couverte) ; les **valeurs** du coffre ne sont jamais cherchées |
| Serveur MCP | `[mcp.<nom>]` dans `config.toml` (`commande` = liste, `ecriture`, `env`, `reseau`, `web`, `navigateur`, `max_reponse`, `max_par_minute`) ; `mcp =` (et `outils = web`) dans `agent.conf` | `berger regenerer` (`.mcp-berger.json`, profil Codex) ; relance de l'agent | `serveur_mcp`, source unique des refus : `npx`/`uvx`, exécutable introuvable, écriture hors dossier, `env` au nom de secret ou portant une valeur du coffre, `web` + `reseau` ; bwrap obligatoire ; réponses filtrées | `reseau = true` est **accepté sans validation ni signalement au propriétaire** (seulement « réseau » au journal de session) |
| Vue | `bin/vues/<type>.py` (+ `.schema.json`), `bin/page/icones.json`, `DEDIES` dans `bin/page/app.js` : **fichiers du produit** | aucun (chargée à chaque `berger`) ; en installation : forge puis `berger installer` | chargement (`VUES_REFUSEES`, nommée dans `etat` et `vues`) ; `tests/vues.py` ; `tests/contrat-noyau.py` (imports, noms libres) | Vue cassée : écartée et nommée (bien) ; mais ajouter une vue = modifier le produit : impossible sans fusion |
| Outil du courtier | `courtier/outils/<type>.py` (classe `Outil`, `verbes`, `ecritures`, `hotes()`) : **fichier du produit** ; `[outils.<nom>]` dans `config.toml` ; `outils =` dans `agent.conf` | `berger courtier redemarrer` (`CONFIG` lu au démarrage) | au démarrage : nom réservé ou en double, verbes de `portes_outil`/`installer_outil`/`consigne` ; une écriture passe toujours par validation | Une erreur au chargement **fait tomber tout le courtier** ; un verbe sans docstring **casse l'aide** (`fn.__doc__.strip()`), sans test ; aucun test de contrat commun à tous les outils |

Il n'existe **aucune** notion de paquet, de manifeste, de version ni de désinstallation d'extension. Ce qui s'en approche :
`berger installer` (le produit entier, avec `verifier-depot`, redémarrage contrôlé et retour arrière), l'empreinte d'une
proposition d'agent (`agent apercu|appliquer`), qui **refuse** déjà d'ajouter un outil, un MCP ou une méthode non déclarés (« s'ajoute à la main »).

Trois défauts relevés en passant, à corriger **dans le lot qui touche le genre** (chacun avec son test rouge) : skills de
`skills-agent/` et `~/.claude/skills` non contrôlées ; `reseau = true` muet ; docstring absente qui casse l'aide.

## Cible

### 1. Commandes (propriétaire seul, au terminal)

```
berger extension verifier  <genre> <source>              # tous les contrôles, rien n'est écrit ; dit ce qui serait installé et les droits demandés
berger extension ajouter   <genre> <source> [--agents a,b] [--reseau]
berger extension retirer   <genre> <nom>
berger extension revenir   <genre> <nom>                  # la version d'avant (retour arrière)
berger extension liste     [--json]
```
`<genre>` : `skill`, `mcp`, `vue`, `outil`. `<source>` : chemin absolu d'un dossier local, ou `git:<dépôt local>@<commit>`
(un commit complet, jamais une branche : ce qui est vérifié est ce qui est installé).

- **Qui y a droit** : le propriétaire seul. `ajouter`, `retirer` et `revenir` refusent un appel venu d'un agent (même
  contrôle que `valider`) ; aucun verbe du courtier ne les expose.
- **Un agent peut PROPOSER** : `berger-outil extension proposer` (paramètres : genre, source, raison) crée une validation
  numérotée qui porte le résultat de `verifier` et l'empreinte du paquet. Le propriétaire la valide : Berger installe
  **exactement** cette empreinte (un paquet changé après la proposition = refus, nouvelle proposition). L'agent n'installe jamais.
- `--agents` donne le droit (`skills =`, `mcp =`, `outils =`) aux agents nommés ; sans lui, l'extension est installée mais
  donnée à personne. Un développeur d'équipe ne reçoit jamais un MCP (règle actuelle gardée).

### 2. Où vont les extensions : jamais dans le produit

- Fichiers : `<installation>/extensions/<genre>/<nom>/<version>/`, copie figée (pas de lien vers la source), en lecture
  seule pour les agents ; `actuelle` désigne la version active.
- Réglages : un fichier **généré** `<installation>/extensions.toml`, lu **en plus** de `config.toml`. Berger ne réécrit jamais
  `config.toml` (ses commentaires sont ceux du propriétaire). Un même nom déclaré dans les deux = refus nommé (pas de priorité implicite).
- Le produit apprend seulement à **lire** ces emplacements : skills (une source de plus pour `lier_skills`), MCP
  (`SERVEURS_MCP` complété), vues (`charger_vues` lit aussi `extensions/vue/*/actuelle/`), outils (`charger_outils` idem).
  `verifier-depot` refuse toujours qu'un fichier de `extensions/` entre dans le dépôt.

### 3. Paquet d'extension : `extension.toml`

```toml
nom = "exemple"                 # minuscules et tirets
genre = "mcp"                   # skill | mcp | vue | outil
version = "1.2.0"               # SemVer ; ajouter refuse une version égale ou plus ancienne que l'actuelle (sauf revenir)
description = "Une phrase."

[droits]                        # ce que le paquet DEMANDE ; affiché par verifier, accordé par le propriétaire
reseau = false                  # mcp : true ne s'installe qu'avec --reseau
ecriture = []                   # mcp : dossiers relatifs au dossier de l'agent
env = []                        # mcp : NOMS de variables, jamais de valeur
hotes = []                      # outil : hôtes que l'outil contactera
secrets = []                    # outil : NOMS de clés du coffre ; le propriétaire les crée lui-même
ecritures = []                  # outil : verbes d'écriture (toujours soumis à validation)

[mcp]                           # genre mcp seulement
commande = ["/usr/bin/exemple-mcp", "--stdio"]
```
Le reste du paquet : `SKILL.md` (skill), `<nom>.py` + `<nom>.schema.json` facultatif (vue), `<nom>.py` (outil). Aucun lien
symbolique, aucun fichier hors du dossier, 1 Mio au total au plus (skill, vue, outil). Empreinte : sha256 de la liste triée
`chemin + contenu` de tous les fichiers, manifeste compris ; gardée dans `extensions.toml` et affichée par `liste`.

### 4. Contrôle à l'installation : automatique, refus net

Commun à tous : manifeste valide, nom libre (ni réservé, ni du produit, ni déjà pris par un autre genre), empreinte calculée,
aucune valeur du coffre ni nom de son fichier, aucun motif de `[skills] interdits` ni marque privée, dans **aucun** fichier du paquet.

- **skill** : `motif_refus_skill` + valeurs du coffre, sur tout le dossier (pas seulement `SKILL.md`).
- **mcp** : `commande[0]` = **chemin absolu** d'un exécutable **déjà installé**, hors des dossiers d'agents et de
  `extensions/` ; pas de `npx`/`uvx`/lanceur qui télécharge ; `reseau = false` par défaut, `true` seulement si le manifeste le
  demande ET que le propriétaire passe `--reseau` (rappelé dans `liste` et sur la page) ; puis `serveur_mcp` rejoué pour
  chaque agent de `--agents` (source unique des refus, inchangée).
- **vue** : l'analyse de `tests/contrat-noyau.py` (imports interdits, noms libres, alias de `getattr`/`globals`/`vars`/`__dict__`
  une fois le correctif en cours installé) appliquée au fichier ; chargement à blanc dans un processus à part ; contrat de
  `tests/vues.py` (constantes, `rendre`, `donnees` + `rendu_texte` + schéma valide, icône connue). Une vue d'extension n'entre pas dans la liste
  fixe des onglets du produit : elle est marquée « extension » dans le registre.
- **outil** : même analyse statique, adaptée au courtier (imports permis listés) ; chargement à blanc de la classe `Outil` dans
  un processus à part, **sans** secret (valeurs factices) ; chaque verbe a une docstring ; chaque écriture est un couple
  (aperçu, exécution) ; `hotes()` ⊆ `[droits] hotes` ; clés lues ⊆ `[droits] secrets`.

### 5. Sauvegarde, empreinte, retour arrière

- Avant toute écriture : `extensions.toml.avant-<nom>-<AAAAMMJJHHMM>` (copie vérifiée : existe, se relit), version précédente
  gardée dans `extensions/<genre>/<nom>/`. `agent.conf` modifiés : même sauvegarde `.avant-`. Aucun de ces fichiers ne porte de secret.
- Après : `regenerer` (skill, mcp) ou redémarrage **contrôlé** du courtier (outil), comme `installer`. Échec → retour
  automatique à l'état sauvegardé, refus nommé, rien de demi-installé.
- `retirer` : retire les droits des agents, puis `extensions.toml`, puis déplace les fichiers dans `extensions/.retirees/`
  (jamais d'effacement), avec la même sauvegarde. `revenir` : la version précédente, mêmes contrôles qu'un ajout.
- Une extension cassée **après** coup (vue ou outil qui ne charge plus) est écartée et nommée, comme une famille du produit ;
  un outil d'extension qui échoue au chargement **n'arrête jamais le courtier** (seul cet outil est écarté).
- Chaque geste : une ligne au journal de Berger (genre, nom, version, empreinte, agents, droits accordés).

### 6. Page « Extensions » de l'interface (lecture seule)

Un onglet dans le groupe de l'installation, sur le modèle de « Réglages » : une carte par extension avec genre, nom, version,
empreinte courte, agents qui l'ont, droits accordés (réseau en évidence), date d'installation, dernier usage (journal du
courtier pour les outils et MCP, chargement pour les vues ; « non mesuré » pour les skills) et état (active, écartée avec la
raison). Même filtre de sortie que Réglages (aucun secret, aucun chemin privé). GET seulement, 405 sinon. Pas de bouton.

## Refus (chacun nommé, code ≠ 0, rien d'écrit)

Appel venu d'un agent ; manifeste absent ou invalide ; nom pris ; version non plus récente ; lien symbolique ou fichier hors
du paquet ; taille ; valeur ou fichier du coffre, motif interdit, marque ; MCP : commande relative, introuvable, dans un dossier
d'agent, lanceur qui télécharge, réseau sans `--reseau`, `web` + `reseau` ; vue ou outil : contrat statique, chargement à blanc
en échec, docstring absente, hôte ou clé non déclarés ; agent inconnu ou développeur pour un MCP ; nom en double avec `config.toml` ;
source git : commit absent ou abrégé ; proposition dont l'empreinte a changé.

## Tests (données fictives, installation jetable)

Un test rouge par refus ci-dessus ; un ajout puis `liste` puis `retirer` par genre (état d'avant retrouvé, à l'octet près pour
`extensions.toml` et les `agent.conf`) ; retour automatique quand `regenerer` ou le redémarrage du courtier échoue ; un outil
d'extension cassé n'arrête pas le courtier ; `verifier-depot` refuse `extensions/` ; un agent qui appelle `ajouter` est refusé,
`proposer` crée une validation et rien n'est installé avant elle ; page : GET seul, aucun secret sur une configuration
piégée (mêmes cas que Réglages), Playwright aux 4 largeurs et 2 thèmes, sinon « non mesuré ». Les suites de sécurité
existantes (mcp, mcp-trous, skills-roles, contrat-noyau, vues, coffre, verifier-depot) restent vertes sans assertion affaiblie.

## Découpage (une demande de fusion par lot)

1. **Socle + skill** : manifeste, empreinte, `extensions.toml`, `verifier|ajouter|retirer|revenir|liste`, sauvegarde et
   retour arrière ; genre `skill` (et contrôle des skills de `skills-agent/`).
2. **Page « Extensions »** en lecture seule.
3. **MCP** (et `reseau = true` signalé au propriétaire, y compris pour les `[mcp]` de `config.toml`).
4. **Vue** d'extension (après le correctif du contrat en cours).
5. **Outil du courtier** : cœur de l'installation, opus, relecture Codex renforcée ; docstring absente corrigée.
6. **Proposition par un agent** (`berger-outil extension proposer`, validation, installation de l'empreinte proposée).
Plus tard, go à part : installer depuis la page web.

Doc : le manuel (nouvelle section « Extensions », empreinte recalculée), `changelog.d/extensions-<lot>.md` à chaque lot.
Relecture Codex à chaque demande.
