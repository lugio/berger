# Accord du mode bypass de Claude Code — spec courte et mesure (03/11/2026)

## Constat

Après une mise à jour (Claude Code 2.1.316), au redémarrage, chaque agent Claude a affiché
« WARNING: Claude Code running in Bypass Permissions mode — No, exit / Yes, I accept » et attendu une réponse :
les agents sont restés arrêtés, sans rien dire. Berger les lance tous avec `--dangerously-skip-permissions` ;
les stricts avec `--setting-sources project,local` et `permissions.defaultMode = "bypassPermissions"` dans
`.claude/settings.json`. L'acceptation écrit `"skipDangerousModePermissionPrompt": true` dans les réglages
utilisateur, que les stricts ne lisent pas.

## Mesure (sans modèle ni réseau : l'avertissement vient avant)

Méthode : `HOME` jetable (jamais le vrai), `.claude.json` jetable marquant l'accueil fait et le dossier approuvé,
`claude --dangerously-skip-permissions` lancé dans un pseudo-terminal (Python `pty`) 8 s, écran lu.
« Avertissement » = l'écran « Yes, I accept » ; sinon Claude arrive à son invite (« bypass permissions on »).

| Clé posée dans | toutes portées | `--setting-sources project,local` |
|---|---|---|
| (nulle part) | avertissement | avertissement |
| `~/.claude/settings.json` (utilisateur) | **aucun** | avertissement |
| `.claude/settings.json` (projet) | avertissement | avertissement |
| `.claude/settings.local.json` (local) | **aucun** | **aucun** |
| fichier `--settings` | **aucun** | **aucun** |

Contre-épreuve avec des réglages de strict (`defaultMode` + `deny` dans le projet, `--setting-sources project,local`) :
sans `settings.local.json` → avertissement ; avec la clé dans `settings.local.json` → aucun.

## Comportement

`ACCORD_BYPASS = {"skipDangerousModePermissionPrompt": true}` (`bin/noyau/config.py`), écrit pour les agents lancés en bypass :
- agent dans son dossier (strict ou ouvert) : `.claude/settings.local.json` (par `regenerer`) ;
- strict dans un dossier existant : dans `.reglages-claude.json` (déjà passé par `--settings`) ;
- ouvert dans un dossier existant : `.appelant-claude.json`, désormais toujours passé par `--settings`
  (avant : seulement avec un en-tête d'appelant), dans le dossier Berger de l'agent.

Refus : jamais dans `.claude/settings.json` (portée ignorée), ni chez Codex, ni dans le dossier existant de l'agent ;
aucune autre clé, aucun changement de permissions, de refus ou de bac à sable.

## Tests

`tests/accord-bypass.py` (sans moteur) : la clé pour les quatre murs, dans la bonne portée, et nulle part ailleurs ;
réglages inchangés ; `regenerer` idempotent. `tests/appelant.py` : un ouvert ailleurs sans en-tête ne reçoit par
`--settings` que l'accord.
