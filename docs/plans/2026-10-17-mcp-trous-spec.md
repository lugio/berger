# Fermer les trous MCP et connecteurs des agents strict (Claude et Codex) — étape 1

Spec, 17/10/2026 (mission de master ; **cœur du mur** : go explicite du propriétaire donné le 17/10 pour CETTE étape).
Hors de cette branche (étape 2) : `berger-mcp`, sections `[mcp.*]`, clé `mcp =` d'un agent.

## 1. Mesure (17/10, Claude Code 2.1.300, Codex 0.162.1, un agent strict Claude et un agent strict Codex, sonde rejouable de master)

- **Un serveur MCP lancé par le moteur tourne HORS du bac à sable**, sous les deux moteurs : la sonde lit un canari d'un
  dossier masqué, lit un autre agent, a le réseau ouvert, écrit dans `bin/`, partage l'espace de montage du lanceur.
- **Claude strict** (`--setting-sources project,local`) reçoit les **connecteurs claude.ai** du compte (événement init :
  « claude.ai Claude Docs » connecté, Drive, Gmail, Calendar à authentifier).
  `ENABLE_CLAUDEAI_MCP_SERVERS=false` dans l'environnement du PROCESSUS → aucun ; `--mcp-config f --strict-mcp-config`
  → seulement les serveurs de `f` (connecteurs écartés aussi). Les serveurs de `~/.claude.json` ne sont pas vus en strict.
- **Codex** (CODEX_HOME de Berger) a contacté le serveur MCP distant d'une app du compte (`openai-mcp.higgsfield.ai`,
  AuthRequired). Avec `features.apps`, `plugins`, `remote_plugin`, `skill_mcp_dependency_install`, `tool_suggest` à
  `false` : plus aucune tentative (mesure du propriétaire, 22:31).
- **Codex lit le `.codex/config.toml` d'un projet de confiance**, serveurs MCP compris (le serveur déclaré y est lancé ;
  ignoré en untrusted). Les dossiers d'agents sont déclarés trusted.
- **Écriture des fichiers MCP depuis un strict Claude** (installation actuelle) : `.mcp.json` et `.claude/settings*.json`
  déjà refusés ; **`<dossier>/.codex/config.toml` créable** par Bash (créé puis retiré par la sonde). `socket(AF_UNIX)` refusé.
- `codex sandbox` (imbriqué) : des règles `read` sur des chemins absents sont acceptées et leur création refusée.

## 2. Comportement

1. **Claude, tout agent strict** : `--strict-mcp-config` à chaque lancement (`args_moteur`, drapeau sans valeur, jamais
   juste après `--mcp-config`, variadique) ET `ENABLE_CLAUDEAI_MCP_SERVERS=false` dans l'environnement du processus, posé
   avec `CLAUDE_CODE_TMPDIR` (`env_tmp` : `lancer`, `demander`, panneau Herdr, `berger args`, `claude_p` de
   `tests/tout.sh`). Les deux, par défense en profondeur.
2. **Codex, tout agent strict** : `[features]` `apps`, `plugins`, `remote_plugin`, `skill_mcp_dependency_install`,
   `tool_suggest` = `false` dans le profil `<agent>.config.toml`.
3. **Fichiers MCP jamais écrits par l'agent**, sous AUCUN des deux moteurs (l'un lirait ce que l'autre a posé) :
   `.mcp.json`, `.claude/settings.json`, `.claude/settings.local.json`, `.codex/`, dans son dossier ET son dossier de
   travail. Claude : `denyWrite` du bac à sable + refus `Edit`/`Write` (`.codex/**`) ; Codex : `"…" = "read"`.
4. **Contrat d'admission** `bash tests/contrat-moteur.sh <claude|codex> [agent strict]`, le même pour chaque moteur, lu
   dans une sortie MACHINE (jamais le texte du modèle) : (1) outils vus = ceux du moteur seul ; (2) aucun serveur MCP lancé,
   même déclaré à la main chez l'agent (canari, avec témoin positif d'abord) ; (5) écriture de ces fichiers refusée ;
   (6) `socket(AF_UNIX)` refusé. Verdict par moteur ET version : `tests/contrats/<moteur>-<version>.txt` (hors dépôt),
   1re ligne `ADMIS` ou `NON ADMIS`. Joué par le propriétaire, par `tests/tout.sh` et, pour une version jamais vue, par
   Berger avant le premier lancement.
   **Jamais de canari laissé chez l'agent** : un contrat à la fois (verrou) ; un journal de pose
   (`tests/contrats/.pose.json`) est écrit avant chaque fichier posé, un fichier existant est mis de côté SUR PLACE
   (`<fichier>.avant-contrat`, jamais recopié ailleurs) ; un contrat coupé est réparé par le suivant, qui ne retire que des
   fichiers portant la marque du contrat ; SIGTERM fait passer par le nettoyage, et Berger, au délai (1 200 s), envoie
   SIGTERM puis SIGKILL 30 s plus tard seulement.
5. **Admission** (agent strict) : moteur non admis → **bascule** sur l'autre moteur s'il est admis (décision du propriétaire du
   17/10 : pas de blocage sec), notée au journal de l'agent, **rouge** dans la Synthèse, **une** notification par version.
   Contrat jamais joué : **jaune**. Aucun moteur admis : **refus** de lancer, message clair (lancer, demander, panneau,
   `berger args`). Mur ouvert : hors sujet, inchangé.

## 3. Refus

- Contrat impossible à jouer, moteur introuvable, version illisible : **non admis** (jamais admis par défaut).
- `berger args` (autre accès, ex. pont) : moteur non admis refusé ; `--contrat` réservé au script du contrat.
- Un panneau basculé ne reprend pas une conversation de l'autre moteur.

## 4. Tests

- `tests/mcp-trous.py` (sans modèle, installation jetable, `tests/suites.sh`) : génération (drapeau, variable, refus,
  features, mur ouvert inchangé), chaque lancement, admission (bascule, journal, notification unique, rouge, jaune, refus,
  contrat joué avant le lancement d'une version jamais vue, pas rejoué ensuite).
- `tests/contrat-moteur.sh` (vrais moteurs, réseau et modèle : **jamais depuis un bac à sable**), joué pour chaque moteur
  installé par `tests/tout.sh`.
