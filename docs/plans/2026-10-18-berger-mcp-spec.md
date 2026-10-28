# MCP étape 2 : `berger-mcp`, serveurs déclarés par le propriétaire, enfermés dans le mur de l'agent — berger-mcp

Spec, 18/10/2026 (master). **Cœur du mur** (courtier, gardes) : go du propriétaire du 18/10 pour CETTE étape.
Suite de `2026-10-17-mcp-trous-spec.md` (étape 1, fusionnée) et `2026-10-18-codex-trous-spec.md`.
Hors de cette branche (étape 3) : REA, agent « Rétro », toute déclaration propre à l'installation.

## 1. Constat (mesuré le 17/10, contrats du 18/10)

- Un serveur MCP lancé par le moteur (Claude ou Codex) tourne HORS du bac à sable de l'agent : il lit le coffre et les
  autres agents, a le réseau, peut écrire dans `bin/`. Claude lui passe tout son environnement (identifiants de session).
- Étape 1 : un agent strict n'a plus AUCUN serveur MCP (contrat (1), (2), (5), (6) verts sous les deux moteurs).
  Il n'existe donc aujourd'hui aucun moyen sûr de lui en donner un.

## 2. Comportement

### 2.1 Déclaration (installation, `config.toml`, non versionné)
```toml
[mcp.<nom>]
commande = ["<binaire installé>", "<args>"]   # jamais un téléchargement au démarrage (npx, uvx, pipx run, bunx…) : refus
env = { CLE = "chemin" }       # jamais une valeur du coffre ni un nom de variable de secret : refus (même règle que les outils)
reseau = false                 # défaut
ecriture = ["{agent}/echantillons"]   # sous le dossier de l'agent seulement ; défaut : rien
max_par_minute = 30            # défauts prudents, comme les outils du courtier
max_reponse = "2M"
```
`agent.conf` : `mcp = <nom>[, <nom>]`. Nom absent de `config.toml` = refus (comme `outils =`). Interdit à un développeur
d'équipe ; refusé par `agent-appliquer` sur les propres réglages d'un agent (comme les autres clés de droits).
`berger etat` / fiche : « MCP : <nom> (sans réseau, écrit dans echantillons/) ». README : la clé, le relais, le contrat.

### 2.2 Un seul point d'entrée : `berger-mcp <agent> <serveur>`
- La config MCP générée (`regenerer`) ne contient, par serveur de `mcp =`, que `berger-mcp <agent> <serveur>` : jamais la
  vraie commande, un chemin d'outil ni une variable de l'outil. Claude : `--mcp-config <dossier>/.mcp-berger.json` avant une
  autre option (variadique), `--strict-mcp-config` gardé ; fichier non inscriptible par l'agent. Codex :
  `mcp_servers.<serveur>` dans le profil de l'agent, approuvé d'avance pour CE serveur seulement (clé à mesurer, 0.163.0).
  Agent sans `mcp =` : rien ne change (étape 1).
- `berger-mcp` est un **simple relais** stdio ↔ courtier : il ne lit ni le coffre ni `config.toml`.
- Le **courtier** : (1) vérifie que CET agent a droit à CE serveur, sinon refus ; (2) lance le vrai serveur ENFERMÉ (2.3),
  un processus par session, tué quand le relais se ferme ; (3) journalise chaque appel dans `courtier/appels.log` (agent,
  serveur, méthode, outil, durée, taille, verdict — aucune valeur) ; (4) filtre chaque réponse (outils, ressources, invites,
  notifications) avec `contient_secret` : réponse touchée → erreur MCP « réponse bloquée : elle contient un secret », tracée
  et notifiée ; (5) borne débit et taille (`max_par_minute`, `max_reponse`).
- Chemin relais ↔ courtier : un socket par agent, dans un dossier du courtier masqué à tous les agents. Mesuré le 18/10
  (codex-trous) : depuis le Bash d'un agent strict, `connect()` AF_UNIX est refusé (Codex permet la création, pas la
  connexion) ; contrat (6) vert. `berger-mcp` lancé depuis le Bash de l'agent n'atteint donc rien : le contrat le reprouve (§ 4).

### 2.3 L'enfermement
`bwrap` avec les masques de l'agent tirés d'**une seule fonction** (celle qui génère son mur : `masques()` de `bin/berger`) ;
réunir avec `masques_courtier()`, ne pas recopier de liste. En plus : réseau coupé (`--unshare-net`, sauf `reseau = true`),
écriture limitée à `ecriture`, `/tmp` = le temporaire de l'agent, espace de processus à part, `--die-with-parent`,
**environnement vidé** (`--clearenv`, puis l'`env` déclaré et le strict nécessaire, `PATH`). Étendre
`courtier/outils/_commandes.py:bac_a_sable` (un seul dossier en écriture aujourd'hui), ne pas le copier. Sans `bwrap` en
état de marche : aucun serveur, jamais de repli sans enveloppe.

## 3. Refus (au chargement, par `regenerer` ou au lancement : message clair)
- serveur non déclaré, ou absent du `mcp =` de l'agent qui l'appelle (courtier) ;
- `mcp =` sur un agent `mur = ouvert` ; sur un développeur d'équipe ;
- `commande` qui télécharge au démarrage, ou introuvable ;
- `ecriture` hors du dossier de l'agent, ou sur un fichier protégé (`agent.conf`, réglages générés) ;
- `env` avec une valeur du coffre ou un nom de variable de secret ;
- `bwrap` absent ou en échec ;
- réponse contenant un secret : bloquée (la session continue, l'appel échoue).

## 4. Tests (même branche)
- `tests/mcp.py` (sans modèle, dans `suites.sh`) : relais ↔ courtier (le protocole passe tel quel) ; chaque refus du § 3 ;
  journal (une ligne par appel, sans valeur) ; filtre (valeur témoin d'un coffre d'essai, forme de clé) ; débit et taille ;
  enveloppe exécutée avec la sonde : témoin du coffre, autre agent, réseau, écriture hors et dans `ecriture`, env vidé ;
  génération : seulement des `berger-mcp` dans les configs, rien pour un agent sans `mcp =`.
- `tests/contrat-moteur.py` : conditions (3) et (4), jouées SEULEMENT si un serveur d'essai est déclaré par le contrat
  (la sonde passée par `berger-mcp`) : (3) témoin du coffre illisible, autre agent illisible, réseau fermé, `bin/` non
  inscriptible ; (4) réponse piégée bloquée et journalisée. Les conditions de l'étape 1 inchangées. Contrat réel : propriétaire.
- `berger verifier-depot` propre (aucun nom ni chemin de l'installation dans le produit).

## 5. Retour arrière
Revenir au commit d'avant la fusion (installation : retour automatique si la vérification échoue). Sans `mcp =`, rien ne
change pour aucun agent. Fichiers générés : `berger regenerer`.

## 6. Mesures (développeur berger-mcp, 18/10/2026)

- **Codex 0.163.0, approbation d'un serveur** : `mcp_servers.<serveur>.default_tools_approval_mode`, valeurs
  `auto | prompt | writes | approve` (message d'erreur de Codex sur une valeur inconnue) ; acceptée dans le profil de l'agent
  (`codex -p <agent>`, fichier `<agent>.config.toml`) ; par outil : `[mcp_servers.<serveur>.tools.<outil>] approval_mode`.
  Berger écrit `"approve"` pour chaque serveur relayé. **Non mesuré ici** (ni réseau ni modèle) : qu'aucune question ne
  s'affiche avec `approval_policy = "never"` — à confirmer par le contrat réel (propriétaire).
- **bwrap** : la source d'un `--bind` est lue sur le système hôte, pas dans l'arborescence déjà montée — un dossier
  d'écriture sous un masque (`agents/` en tmpfs) se monte donc APRÈS les masques. Un masque `--tmpfs` est inscriptible
  (sans effet sur le disque) : pour un serveur MCP, il est remonté en lecture seule (`--remount-ro`), après les dossiers
  d'écriture. `--chdir` pose `PWD` dans l'environnement vidé (seul ajout de bwrap).
- **Sockets de la session** (`$XDG_RUNTIME_DIR` : D-Bus, Herdr…) : un `connect()` AF_UNIX passe à travers un montage en
  lecture seule ; ce dossier est donc masqué en plus pour un serveur MCP (avec `courtier/mcp`).
- **Temporaire** : la limite de 44 octets est propre à Claude ; pour le `/tmp` d'un serveur enfermé, seul compte un vrai
  dossier 700 à ce compte (`preparer_tmp(a, longueur=False)`).
- **Depuis le Bash d'un agent Claude strict**, `socket(AF_UNIX)` est refusé : la partie « relais ↔ courtier par socket »
  de `tests/mcp.py` y est NON JOUÉE, et jouée par la porte `tests` (courtier).
