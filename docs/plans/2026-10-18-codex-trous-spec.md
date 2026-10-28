# Codex : config de projet coupée chez les agents strict (contrôle (2) du contrat) — codex-trous

Spec, 18/10/2026 (mission de master ; **cœur du mur** : go du propriétaire du 18/10). Suite de
`2026-10-17-mcp-trous-spec.md`. Second volet : le contrôle (6) du contrat (AF_UNIX), qui était un faux positif (§ 5).

## 1. Constat

Contrat Codex 0.163.0 non admis, contrôle (2) : le canari posé dans `<dossier de travail>/.codex/config.toml` est lancé.
`config_codex` déclarait le dossier de travail de chaque agent `trust_level = "trusted"`, et Codex lit le
`.codex/config.toml` d'un dossier de confiance, serveurs MCP compris (lancés hors bac à sable).

## 2. Mesure (Codex 0.163.0, CODEX_HOME et dépôt git jetables, agent dans le dépôt, sans réseau ni coffre)

| Réglage `[projects]` | `codex mcp list --json` | Interface : « Trust this folder? » |
|---|---|---|
| aucun (témoin) | `[]` | **affichée** |
| agent `trusted` + racine `trusted` (avant) | canari | non |
| agent `untrusted` + racine `trusted` (après) | `[]` | **non** |
| agent `untrusted` seul / racine `untrusted` | `[]` | — |

`hooks/list` (app-server) : les garde-fous de `CODEX_HOME/hooks.json` sont listés à l'identique, agent `trusted` ou
`untrusted` — « untrusted » ne coupe que la config, les hooks et les règles d'exécution **du projet**.

## 3. Comportement

Agent strict : son dossier et son dossier de travail en `trust_level = "untrusted"` ; la racine de Berger reste
`trusted` (sans elle, la question revient : 05/10). Mur ouvert : inchangé (`trusted`). Claude : inchangé.

## 4. Tests

`tests/mcp-trous.py` : dossiers d'un strict (Codex, Claude, dossier existant) en `untrusted`, mur ouvert et racine en
`trusted`. Preuve dans le vrai moteur : `bash tests/contrat-moteur.sh codex` (propriétaire).

## 5. Mesure (b) : AF_UNIX — le contrôle (6) mesurait la mauvaise chose

Mesure du propriétaire, hors bac à sable, `codex sandbox -p <agent strict>`, Codex 0.163.0 : `socket(AF_UNIX)` **permis**,
mais `connect()` **refusé** vers toutes les cibles essayées (Herdr, D-Bus, gpg-agent, Wayland, Hyprland, PipeWire), et
`bind` + `connect` internes refusés aussi ; le même `connect()` hors bac à sable aboutit (témoin). Créer un socket n'ouvre
aucune porte : c'est `connect()` qui compte. (Depuis un agent Claude strict, cette mesure est impossible : son bac à sable
refuse déjà la création.) **Limite** : mesuré par `codex sandbox`, pas par le Bash d'une vraie conversation — le contrat
réel le confirmera.

**Contrôle (6), nouvelle forme** (`tests/contrat-moteur.py`, sous les deux moteurs) : le contrat pose un socket AF_UNIX qui
**écoute hors du bac à sable**, dans un chemin que l'agent **voit** (son dossier temporaire, sinon son dossier ; nom marqué
`berger-contrat-canari-…`, < 100 octets). Témoin d'abord : une connexion venue du contrat (hors bac à sable) est acceptée.
La sonde de l'agent dit s'il voit le socket (`vu=`) et si `connect()` aboutit (`connect=`). **Vert** : vu, refusé, et le
serveur n'a rien accepté d'autre que le témoin. **Rouge** : connecté ; ou socket invisible (un refus ne prouverait qu'un
chemin masqué). La création du socket reste écrite, en simple information. Le socket est journalisé avant d'écouter et
retiré comme le canari (fin normale, SIGTERM puis SIGKILL de Berger, reprise par le contrat suivant ; jamais un socket
sans marque).

Test hors moteur : `tests/contrat-socket.py` (NON JOUÉ là où AF_UNIX est refusé, ex. dans un bac à sable Claude).
