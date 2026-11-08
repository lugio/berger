# Extensions — décisions prises en cours de chantier (spec `2026-11-07-extensions-spec.md`, go n° 181)

Ce que la spec ne tranchait pas, décidé par le chef de projet DANS la spec (sans nouveau go). Une décision qui changerait la spec
demanderait un nouveau go.

## Lot 3 — serveur MCP (07/11/2026)

1. **« reseau = true » signalé au propriétaire** (spec, découpage 3 : « y compris pour les `[mcp]` de `config.toml` ») :
   - une ligne `⚠ réseau ouvert : serveur MCP <nom> (<extension|config.toml>) pour <agents>` dans la sortie de `berger regenerer`,
     pour chaque serveur à réseau qu'au moins un agent a dans son `mcp =` ;
   - le badge « réseau » de la page Extensions et la mention `RÉSEAU` de `berger extension liste` (déjà là depuis les lots 1 et 2) ;
   - un champ `mcp_reseau` dans `berger etat --json` : `[{serveur, origine, agents}]`, pour que l'Accueil puisse le montrer plus tard ;
   - **aucune** notification à chaque `regenerer`.
2. **Variables d'environnement d'un serveur MCP d'extension** : le manifeste ne porte que des **noms** (`[droits] env = [...]`) ; chacune
   est donnée au serveur avec une valeur **vide** (le serveur doit s'en passer). Un serveur d'extension dont le nom est déjà un
   `[mcp.<nom>]` de `config.toml` est refusé (« nom pris »). Donner une valeur depuis le coffre, par son nom, est un **autre sujet**
   (spec et go à part), noté pour plus tard.
3. **Ce que lance un serveur MCP d'extension** (renvoi n° 187, point 1 ; règle choisie, la plus simple) :
   - **aucun interpréteur** en `commande[0]` (`python*`, `pypy`, `node`, `bun`, `deno`, `ruby`, `perl`, `php`, `lua`, shells, `env`,
     `busybox`, `awk`, `sed`, `xargs`, `nohup`, `timeout`, `sudo`…, nom du chemin ou de sa cible) : un serveur écrit dans un langage de
     script se déclare par son exécutable installé (sa ligne `#!` est contrôlée comme un argument) ;
   - **chaque mot qui désigne un chemin** — `commande[0]`, chaque argument, la valeur d'un `--option=valeur`, les mots de la ligne `#!` de
     `commande[0]` — est refusé s'il tombe, tel quel ou résolu (liens compris), dans un dossier d'agent, dans `extensions/` ou dans un
     dossier inscriptible par un agent : son dossier de travail, sa mémoire, ses `ecrire_aussi` (dont la copie d'un développeur), la
     bibliothèque, les temporaires des agents (`/tmp/bt`, `/tmp/claude-<uid>`). Un chemin relatif (`a/b`, `./x`, `.`, `..`) ou sous `~` est
     refusé : le serveur le lirait depuis son dossier courant, le dossier d'écriture de l'agent. Une URL (`schéma://…`) n'est pas un chemin ;
   - **lanceurs** : `npx`, `uvx`, `bunx`, `pnpx` toujours ; `npm`, `pnpm`, `yarn`, `bun`, `uv`, `pipx` dès qu'une sous-commande `exec`,
     `dlx`, `x`, `run` ou `tool` figure parmi TOUS les arguments. Une seule fonction (`telecharge`), aussi pour un `[mcp]` de `config.toml`
     (`serveur_mcp`) : un `uv run …` ou `npm run …` déclaré à la main est désormais refusé lui aussi ;
   - **limite écrite** : un agent en mur ouvert, hors bac à sable, n'est borné par aucun dossier ; il ne reçoit pas de serveur MCP
     (`serveur_mcp`), mais rien ne l'empêche d'écrire ailleurs dans le dossier personnel : ce mur est un choix du propriétaire.
4. **`revenir` et le réseau** (renvoi n° 187, point 2) : l'accord `--reseau` est enregistré version par version (`reseau_versions` dans
   `extensions.toml`, à l'ajout) ; `revenir` reprend l'accord de la version qu'il rend active, jamais un accord nouveau, et refuse une version
   qui demande le réseau sans accord enregistré.

## Lot 4 — vue d'extension : tests rouges prévus (écrits avant le code, 07/11/2026)

Ordre fixé par le chef de projet : n° 185 (lot 2), puis demande du lot 3, puis le lot 4 sur `main` à jour. Une vue d'extension charge
du code extérieur dans les processus de Berger (ceux du propriétaire) : chaque garde ci-dessous est un test rouge AVANT le code.
Suite prévue : `tests/extensions-vue.py` (installation jetable, données fictives) ; les suites `vues`, `contrat-noyau`, `interface`
restent vertes sans assertion affaiblie.

Refus, rien d'écrit (un test par cas) :
1. contrat statique — l'analyse de `tests/contrat-noyau.py` IMPORTÉE, jamais recopiée : import hors `noyau.api`, nom libre hors API,
   alias de `getattr` / `globals` / `vars` / `__dict__`, `__globals__`, `sys.modules`, `importlib`, `open` d'un fichier hors API ;
2. API d'action dans une vue (un service de `noyau/actions.py`) ;
3. constantes `TITRE`, `ONGLET`, `ORDRE` absentes ; `rendre` absente ; `donnees` sans `rendu_texte` ou sans schéma ; schéma invalide ;
4. icône inconnue de `bin/page/icones.json` ;
5. nom de la vue = une vue du produit (`bin/vues/<nom>.py`) ou un type réservé ;
6. chargement à blanc en échec DANS UN PROCESSUS À PART (exception, `sys.exit`, boucle : délai borné) — le processus du propriétaire ne
   l'exécute jamais avant qu'il ait réussi ;
7. une vue qui, au chargement à blanc, écrit un fichier, ouvre une connexion ou lance un programme (relevé par un crochet d'audit
   `sys.addaudithook` dans le processus à part) ;
8. paquet : plus d'un module Python, fichier hors `<nom>.py` / `<nom>.schema.json` / `extension.toml`, et les refus communs (coffre,
   marque, lien, taille, échappements, noms de fichiers).

Positifs :
9. ajout → la vue chargée depuis `extensions/vue/<nom>/actuelle/`, marquée « extension » dans le registre (`berger vues --json`), jamais
   dans la liste fixe des onglets du produit ni dans l'espace Herdr ; `berger vue <nom>` et `--json` (schéma validé) ;
10. empreinte revérifiée à CHAQUE chargement : copie modifiée → vue écartée et nommée (`berger etat`), les autres tournent ;
11. vue cassée après coup (fichier remplacé par le propriétaire, module qui lève) → écartée et nommée, comme une vue du produit ;
12. retrait → plus chargée, état d'avant à l'octet près ; `revenir` → version d'avant, empreinte revérifiée ;
13. page Extensions : « dernier usage » d'une vue = son dernier chargement réussi (ou « non mesuré » si rien ne le trace) ;
14. une vue d'extension ne reçoit que l'API de lecture : à l'exécution, ni service d'action, ni `transport`, ni coffre (même preuve
    que la section 13 de `tests/contrat-noyau.py`).
