# Une interface web pour Berger, alignée sur Berger par construction et par les tests

Spec, 13/10/2026 (mission de master ; décision du propriétaire du 13/10 : une interface dédiée, plus moderne et agréable
que Herdr, TOUJOURS alignée sur Berger). **Phase 1 : spec seule, aucun code avant la validation du propriétaire.**
Exigences : zéro divergence, zéro bricolage, zéro régression, pas d'usine à gaz.
**Règle de go** : le lot 1 ajoute une authentification (cas 1 de la règle) → go du propriétaire sur cette spec AVANT le code.

> **Pour le propriétaire, en 6 lignes.**
> 1. **Ce que tu verras** : une page web avec les écrans de Herdr (Accueil, Tableau, Échanges…), plus **« À toi de décider »** (tout ce qui t'attend, au même endroit), **le détail complet d'une demande** avant de la valider, **les livrables** des agents (specs, maquettes, rapports) et **l'état des versions** de chaque projet (fusionné, en dev, en prod). Mis à jour toutes les 5 secondes.
> 2. **Comment tu y accèdes** : à une vraie adresse, `https://berger.<domaine interne>`, sur PC et téléphone, depuis le réseau du cabinet ou le VPN (jamais depuis Internet) — lot 1c ; la première fois, un lien d'entrée donné par `berger interface lien`. En attendant le 1c : tunnel ssh et `http://localhost:8765`.
> 3. **Ce qui ne change pas** : Herdr reste le terminal des agents ; tes commandes, les validations, les murs et le courtier ne changent pas ; les écrans de Herdr restent identiques (prouvé au caractère près).
> 4. **Ce qui n'y sera jamais** : aucun secret, aucun mot de passe ; seulement ce que Herdr montre déjà ; rien ne sort de la VM.
> 5. **Lot 1 = lecture seule**, en deux temps (1a : décisions et détail des demandes ; 1b : livrables et versions). Le lot 2, après une nouvelle décision de ta part, ajoute les boutons (valider, refuser, marquer lu, parler), l'écran d'un agent en direct et la santé de Berger (installations, courtier, lecteur réseau).
> 6. **Ce que tu dois valider** : le go sur le **lot 1c** (l'adresse web) ; puis, toi-même, la règle du pare-feu de la VM (forme, sauvegarde et retour arrière écrits au §6 ter), et, côté exploitation, la règle pare-feu réseau, le site SWAG et le nom DNS interne. Le jeton secret d'entrée reste.

**Constat.** Les 16 vues de `bin/vues/*.py` ont chacune une fonction `rendre(w, h, a=None)` qui lit l'état ET fabrique
des lignes de terminal (codes couleur, largeur, pliage) dans le même geste. Certaines données du cœur sont déjà
mises en forme : `cartes_tableau()` rend des textes avec codes couleur, `sources` garde les couleurs des outils. Seules
`berger suivi` et `berger equipe liste` rendent déjà du JSON. Une interface qui relirait les fichiers elle-même
recopierait les règles (qu'est-ce qu'un agent « bloqué », une source « figée », une alerte « nouvelle ») : divergence
assurée à la première évolution. D'où le principe : **une seule fonction de données par vue ; Herdr et l'interface n'en
sont que deux rendus.**

**Herdr reste le terminal des agents** : on y parle aux agents, on y voit leur conversation, on y lance les commandes.
L'interface le complète (lire l'état d'un coup d'œil, plus tard quelques boutons), elle ne le remplace pas : pas de
terminal web, pas de conversation dans la page. Les panneaux de Herdr gardent leur rendu actuel.

## 1. Source unique : chaque vue = `donnees()` + `rendre()` + un schéma

**Comportement.** Chaque `bin/vues/<type>.py` gagne `donnees(a=None) -> dict` (pur : aucune largeur, aucun code
couleur, aucun texte de mise en page ; couleurs dites par un **ton** sémantique). Son `rendre(w, h, a)` devient
`rendu_texte(donnees(a), w, h)` : il ne lit plus aucun fichier. Le contrat de `charger_vues()` s'étend : une vue sans
`donnees` ou sans schéma est **écartée et nommée** (comme aujourd'hui une vue sans `rendre`). Le schéma est à côté de la
vue : `bin/vues/<type>.schema.json` (JSON Schema, sous-ensemble décrit au §3), versionné dans le dépôt.

**Commandes** (une seule porte vers les données, utilisée par l'interface, les scripts et les tests) :
- `berger vue <type> [agent|filtre] --json` → `donnees()` de la vue, enveloppée : `{vue, version, genere, donnees}` ;
- `berger vues --json` → la liste : `{type, titre, icone, onglet, ordre, schema}` (ce que `charger_vues()` sait déjà) ;
- `berger etat --json`, `berger validations --json` ; `berger suivi` et `berger equipe liste` gardent leur JSON, qui
  reçoit lui aussi un schéma (`bin/schemas/suivi.schema.json`, `equipe-liste.schema.json`).

**Types communs** (`bin/schemas/communs.schema.json`, référencés par `$ref`) — `quand` = date ISO 8601 locale (texte) :
- `Agent` `{id: str, nom: str, icone: str}` ; `Statut` `{moteur: str, etat: "idle"|"done"|"working"|"blocked"|"unknown"|"?"}`
- `Checklist` `{titre: str, faites: int, total: int, en_cours: str, bloque: str, fini: bool, etapes: [{fait: bool, libelle: str}]}`
- `Validation` `{n: int, agent: str, outil: str, verbe: str, apercu: str, demande: quand, valideur: str|null}` (jamais `args`)
- `Ligne` `{texte: str, ton: "rouge"|"jaune"|"vert"|"bleu"|"cyan"|"pale"|null}` (texte nu : codes de terminal retirés)

**Les vues existantes et leur schéma proposé** (champs racine de `donnees`, types ; `[X]` = liste de X) :

| Vue (onglet) | `donnees()` |
|---|---|
| `accueil` (Accueil) | `a_toi: [Validation]`, `delegues: [Validation]`, `bloques: [{agent: Agent, bloque: str}]`, `a_lire: [{id: str, titre: str}]` (non lus), `agents: [{agent: Agent, statuts: [Statut], checklist: Checklist\|null, derniere_action: str}]` (hors développeurs), `equipes: [{projet: str, membres: [{agent: Agent, sujet: str, statuts: [Statut], faites: int\|null, total: int\|null, demande: str\|null}], fusionnes: [str]}]` |
| `colonnes` (Tableau) | `colonnes: [{cle: str, libelle: str, ton: str}]`, `cartes: [{colonne: str, titre: str, lignes: [Ligne], vif: bool}]` |
| `synthese` (Synthèse) | `alertes: [{gravite: "rouge"\|"jaune", domaine: str, texte: str, depuis: quand, nouveau: bool}]`, `surveille: [str]` |
| `sources` (Sources) | `sources: [{nom: str, titre: str, outil: str, verbe: str, etat: "ok"\|"echec"\|"fige"\|"attente", quand: quand\|null, duree: num\|null, erreur: str\|null, cadence: int, max_lignes: int, lignes: [Ligne]}]`, `inconnues: [str]` |
| `decisions` (Décisions) | `decisions: [{pour: "toi"\|"agent", titre: str, detail: str, quand: str}]` |
| `checklists` (Checklists) | `dossier: str`, `listes: [{fichier: str, titre: str, faites: int, total: int, restantes: [{section: str\|null, libelle: str}]}]` |
| `alire` (À lire) | `documents: [{id: str, auteur: Agent\|null, titre: str, date: quand, lu: bool}]`, `non_lus: int` (`id` = la clé de lecture, jamais le chemin) |
| `courtier` (Courtier) | `actif: bool`, `droits: int`, `audit: str\|null`, `validations: [Validation]`, `sauvegarde: {suivie: bool, derniere: str\|null}`, `aujourdhui: {appels: int, refus: int}`, `appels: [{quand: quand, agent: str, outil: str, verbe: str, args: str, ok: bool, detail: str}]` (les 50 derniers) |
| `echanges` (Échanges) | `agent: str\|null`, `echanges: [{quand: quand, de: Agent\|str, a: Agent\|str, genre: str, texte: str}]` (les 200 derniers) |
| `catalogue` (Catalogue) | `outils: [{nom, type: str, lecture: [str], ecriture: [str], droits: [{agent: Agent, dernier_usage: quand\|null}]}]`, `autres_droits: [{droit: str, agents: [Agent]}]`, `modules: [{nom: str, utilise: bool}]`, `skills: {partagees: [str], catalogue: [str], par_agent: [{agent: Agent, skills: [{nom: str, absente: bool}]}], par_equipe: [...], orphelines: [str], propres: [...]}`, `gardes: [{moment: str, outils: str, script: str}]`, `reveils: [{agent: Agent, heures: str, taches: int}]` |
| `tokens` (Tokens) | `quotas: [{moteur: str, mesure: bool, fenetres: [{nom: str, pourcent: num, remise: quand\|null}], age_s: int\|null}]`, `par_agent: [{agent: Agent, moteur: str, auj_lus: int, auj_ecrits: int, sept_j_lus: int, sept_j_ecrits: int, contexte: int, derniere: quand, modele: str}]` |
| `tableau` (vue d'agent) | `agent: Agent`, `statuts: [Statut]`, `en_cours: Checklist\|null`, `attend_proprietaire: [{genre: "bloque"\|"validation"\|"proposition"\|"signalement", texte: str, n: int\|null}]`, `a_faire: [{libelle: str, date: str\|null}]`, `fait: [{libelle: str, date: str\|null}]`, `historique: [{titre: str, date: str}]` |
| `journal` (vue d'agent) | `agent: Agent`, `statuts: [Statut]`, `jour: str`, `lignes: [{heure: str\|null, texte: str}]`, `reveils: [str]`, `taches: [{nom: str, date: str}]` |
| `encours` (vue d'agent) | `agent: Agent`, `checklist: Checklist\|null`, `validations: [Validation]`, `a_faire: [str]`, `aujourdhui: [{heure: str, texte: str}]` |
| `missions` (vue d'agent) | `hote: Agent`, `projet: str\|null`, `en_cours: int`, `max: int`, `missions: [{agent: Agent, moteur: str, modele: str\|null, statuts: [Statut], checklist: Checklist\|null, validations: int, demande_fusion: str\|null}]` |
| `fiche` (vue d'agent) | `agent: Agent`, `statuts: [Statut]`, `rubriques: [{cle: "identite"\|"capacites"\|"limites"\|"memoire"\|"veille"\|"activite", libelle: str, champs: [{libelle: str, valeur: str, ton: str\|null}], puces: [{titre: str, texte: str}]}]` (les 6 `fiche_*` du cœur rendent des champs au lieu de lignes) |
| `berger etat --json` | `vues_ecartees: [{vue: str, cause: str}]`, `moteurs_ecartes: [{moteur: str, cause: str}]`, `commandes_ecartees: [{commandes: str, cause: str}]`, `agents: [{agent: Agent, statuts: [Statut], checklist: Checklist\|null, a_faire: int, a_valider: int, memoire: int, memoire_max: int}]` |
| `berger validations --json` | `validations: [Validation]` |

Les limites d'affichage (« 3 au plus », « ce qui tient à l'écran ») restent dans le rendu ; les listes longues ont une
borne fixe dans `donnees()` (écrite dans le schéma : `maxItems`). Les effets de bord actuels restent où ils sont :
`depuis()` (mémo des alertes) est appelé par `donnees()` de la Synthèse, comme aujourd'hui par son rendu.

## 2. Actions (lot 2 seulement) : les MÊMES commandes que la ligne de commande

L'interface n'a **aucun accès direct** aux fichiers, à git ni au courtier : pour lire, elle lance `berger vue … --json` ;
pour agir, elle lance une commande `berger` d'une **table fixe** du serveur (comme le type `commandes` du courtier :
l'argv est écrit dans le code, la page ne fournit que des valeurs vérifiées par motif) :

| Bouton | Commande lancée | Argument |
|---|---|---|
| Valider / Refuser (après confirmation qui montre l'aperçu) | `berger valider <n>` / `berger refuser <n>` | `n` : `^[0-9]{1,6}$` |
| Marquer lu | `berger lire <n> --sans-pager` (même marquage qu'aujourd'hui) | `n` : `^[0-9]{1,4}$` |
| Parler à un agent | `berger parler <agent> --stdin` | `agent` ∈ `berger vues`/`etat` ; texte ≤ 2 000 car. |

Mêmes contrôles : ce sont les commandes du propriétaire, avec leurs refus (déjà faite, inconnue, au repos…), leurs
traces (le courtier inscrit chaque décision dans `courtier/appels.log` ; `parler` dans `echanges.jsonl`). En plus,
**une ligne par action de l'interface dans `courtier/appels.log`**, au format du courtier (7 colonnes, outil
`interface`, `accepté`/`REFUSÉ`, détail = code de sortie) : la fonction `journal()` du courtier est mise en commun
(module partagé), pas recopiée — pas de second journal. Toute autre action (mission, relancer, fusion, installation…) reste dans Herdr et la ligne de commande.

### Lot 2 décidé (propriétaire, 13/10 : « on doit pouvoir déclencher les actions, valider ou répondre depuis l'interface »)

Ordre des lots : 0 → 1a → **1c** (accès, §6 ter) → **2** → 1b. Le lot 2 remplace la table ci-dessus par celle-ci, **fermée** : quatre actions,
chacune = UNE commande `berger` déjà utilisée en ligne de commande, lancée avec un argv écrit dans le serveur ; la page
ne fournit que des valeurs, vérifiées par motif AVANT tout lancement (hors motif → 400, rien lancé). Aucun argument ne
peut commencer par un tiret (donc jamais `--force`). Protection CSRF : `Origin` identique + en-tête
`X-Berger-Action` = `hmac(jeton, "action")` (§5) ; méthode `POST` seulement.

| Action | Commande lancée | Motifs | Confirmation dans la page |
|---|---|---|---|
| Valider / refuser une écriture en attente | `berger valider <n>` / `berger refuser <n>` | `n` : `^[0-9]{1,6}$` | le détail COMPLET (`berger vue validation <n> --json`, §6.4) affiché avant le bouton |
| Répondre à un agent — en particulier à un `❓ Question` ou un `⚠ Go attendu` de « À toi de décider » | `berger parler <agent> --stdin` | `agent` : `^[a-z0-9][a-z0-9-]{0,40}$` ET présent dans `berger vues`/`etat` ; texte : 1 à 2 000 caractères, sans caractère de contrôle hors saut de ligne | le texte relu ; la page pré-remplit « Réponse à « <question> » : » (modifiable) |
| Marquer un « À lire » comme lu | **`berger lu <id>`** (nouvelle commande : même `marquer_lu()` que `berger lire`, mais par l'`id` opaque de la vue `alire` — un numéro d'ordre change quand un document arrive) | `id` : `^[0-9a-f]{16}$` | aucune |
| Relancer un agent | `berger relancer <agent>` (au repos seulement, comme en ligne de commande ; jamais `--force`) | `agent` : comme ci-dessus | « relancer <nom> ? » |

- **Pas de validation de l'action elle-même** quand la commande n'en demande pas (c'est le propriétaire qui agit,
  authentifié) ; les **refus sont ceux de la ligne de commande**, montrés tels quels : déjà décidée, inconnue, agent
  qui travaille (« rien relancé »), agent pas ouvert (« ne tourne pas dans son panneau »).
- **Traces** : celles de la commande (le courtier inscrit chaque décision ; `parler` écrit l'échange
  `<propriétaire> → <agent>` « message », donc la réponse paraît dans les échanges de l'agent ; `relancer` note au
  journal de l'agent) **plus** une ligne `interface` dans `courtier/appels.log` par action (§2).
- Une `❓ Question` ou un `⚠ Go attendu` reste dans « À toi de décider » tant que l'agent n'a pas retiré la ligne de
  sa checklist : la règle ajoutée à `commun/REGLES.md` lui dit de la retirer quand il a lu la réponse.
- **Tests** (`tests/interface.py`, faux Herdr, faux courtier) : chaque action lance exactement l'argv attendu (faux
  `berger` témoin) ; argument hors motif, tiret initial, agent inconnu → 400 sans rien lancer ; sans `Origin`, autre
  `Origin`, sans ou mauvais `X-Berger-Action` → 403 sans rien lancer ; `GET` sur une action → 405 ; refus de la
  commande (validation déjà faite, agent qui travaille) rendu tel quel avec son code ; une ligne `interface` dans
  `appels.log` par action, acceptée ou refusée ; `berger lu <id>` marque le bon document même après l'arrivée d'un autre.
- **Hors de l'interface**, par leur circuit : missions, fusions, installations, `agent-appliquer`, regénération,
  espaces, `--force`.

## 3. Alignement par les tests (porte rouge = fusion refusée)

Nouvelle suite `tests/interface.py`, jouée par `tests/suites.sh` (donc par les portes `tests`, et `pret` vérifie déjà
qu'aucune suite n'est oubliée). Installation JETABLE + faux Herdr (comme `tests/vues.py`), avec un **jeu de données
qui remplit chaque branche** : agent au travail / bloqué / au repos / pas ouvert, checklist finie et en cours,
validation au propriétaire et déléguée, document lu et non lu, demande de fusion par état, source ok / échec / figée /
jamais collectée, échanges, mission en cours, développeur d'équipe. Contrôles :
1. **Chaque vue a son schéma** : `bin/vues/*.py` ↔ `bin/vues/*.schema.json`, un pour un ; un schéma orphelin est rouge.
2. **Les données respectent le schéma** : pour chaque vue (et `etat`, `validations`, `suivi`, `equipe liste`),
   `berger vue <type> --json` est validé par un validateur **en Python standard** (`tests/_schema.py`, ~80 lignes :
   `type`, `properties`, `required`, `items`, `enum`, `$ref`, `maxItems`, `additionalProperties: false`). Tous les
   champs sont `required` et `additionalProperties` est **false** partout : un champ ajouté, retiré, renommé ou retypé
   sans mettre le schéma à jour est rouge.
3. **Chaque champ est réellement produit** : chaque propriété du schéma apparaît au moins une fois avec une valeur non
   vide dans le jeu de données (sinon le schéma décrit un champ mort, ou le jeu ne couvre pas la branche) — rouge.
4. **L'interface sait afficher chaque champ requis** : chaque propriété porte `"x-rendu"` (un mot parmi un petit
   vocabulaire : `texte`, `nombre`, `quand`, `oui-non`, `ton`, `agent`, `statuts`, `checklist`, `validation`, `lignes`,
   `liste`, `cache`) et `"x-libelle"`. `bin/page/app.js` déclare ses rendus dans un bloc unique
   `const RENDUS = { … }` ; le test lit ses clés et exige que **chaque `x-rendu` de chaque schéma y soit**. La page
   affiche chaque vue à partir de son schéma (ordre, libellés, rendus) : un champ ajouté avec un `x-rendu` connu
   s'affiche sans toucher la page ; un nouveau genre de donnée exige un nouveau rendu dans `app.js`, sinon rouge.
   `cache` dit explicitement « donnée non affichée » (choix écrit, relu), jamais par défaut.
5. **Une vue de la page = une vue de Berger** : les onglets de la page viennent de `berger vues --json` (rien en dur
   dans `app.js` : le test vérifie qu'aucun nom de type de vue n'y figure comme chaîne).
6. **Zéro régression du texte** : AVANT de séparer les vues (lot 0), on fige la sortie de chaque `rendre(100, 40, a)`
   sur le jeu de données (heure fixée par une variable d'environnement de test) ; après la séparation, la sortie doit
   être **identique, octet pour octet**. Les suites existantes (`affichage`, `tableau`, `synthese`, `decisions`,
   `alire`, `echanges`, `catalogue`, `tokens`, `vues`…) restent vertes sans retouche de leurs attentes.
7. **Serveur** : écoute sur `127.0.0.1` seulement (vérifié sur la socket ouverte) ; sans jeton → 401 ; mauvais `Host`
   → 403 ; `GET /api/vue/<type>` = exactement `berger vue <type> --json` ; chemin hors des fichiers servis (`..`, lien)
   → 404 ; aucune méthode d'écriture au lot 1 (405) ; au lot 2 : action sans jeton anti-rejeu ou d'une autre origine
   → 403, argument hors motif → refus sans rien lancer, une ligne `interface` dans `appels.log` à chaque action.
8. **Mur** : depuis un agent (Claude et Codex), connexion refusée OU 401/403 sans jeton, et fichier du jeton illisible
   — sonde `tests/sonde-interface.py` jouée par `tests/tout.sh` pour chaque moteur (détail au §5).
9. **Le texte ne dépend que des données** : `rendu_texte(json.loads(json.dumps(donnees())))` = `rendre()`, octet pour octet.

## 4. La technique la plus simple

- **Charge, chiffrée** : seule la vue **visible** se rafraîchit, toutes les **5 s** ; rien quand l'onglet du navigateur
  est caché ; jamais deux demandes en cours pour une même page (la suivante attend la réponse). Chaque commande lancée
  a un **délai maximal de 10 s** (`subprocess.run(…, timeout=10)`) : au-delà, la page affiche « vue en échec : délai de
  10 s dépassé » à la place de la vue, jamais une vue vide. Au plus **4 commandes simultanées** pour tout le serveur
  (au-delà : réponse 503 « occupé », la page réessaie au tour suivant). Mesuré le 13/10 : un démarrage de `bin/berger`
  coûte ≈ 0,2 s ; une vue visible toutes les 5 s ≈ 4 % d'un des 4 cœurs de la VM (à remesurer au lot 1 sur les vues
  lourdes : `tokens` lit les journaux des moteurs, `decisions` relit la fin des conversations).
- **Serveur** : `berger interface servir`, dans `bin/berger` + `bin/interface.py` (Python standard :
  `http.server.ThreadingHTTPServer`, `json`, `subprocess`, `secrets`, `hmac`). Aucune nouvelle dépendance.
  Il ne fait que : servir 3 fichiers statiques, lancer `berger vue|vues|etat … --json`, et (lot 2) la table d'actions.
  Chaque lecture lance la commande : le code installé fait foi, aucune donnée gardée en mémoire, aucune copie de règle.
- **Page** : `bin/page/index.html`, `bin/page/app.css`, `bin/page/app.js` (dans `bin/` : le `.gitignore` du dépôt est une
  liste blanche, qu'on ne retouche pas pour un dossier de plus) — HTML/CSS/JS écrits à la main, sans
  cadriciel ni étape de construction, aucune ressource extérieure (polices, scripts). Onglets = vues ; une page
  par agent (ses vues d'agent) ; rafraîchissement de la vue visible toutes les 5 s ; thème clair/sombre selon le
  système ; lisible au clavier.
- **Livraison** : même dépôt, même circuit, même `berger installer`. Service `systemd/berger-interface.service`
  (`ExecStart=%h/berger/bin/berger interface servir`, comme le courtier). Le redémarrage contrôlé qui suit `installer`
  relance `berger-interface` s'il tourne (`systemctl --user try-restart`, aussi après un retour arrière ; testé dans
  `moins-validations.py`) ; la première activation est un geste du
  propriétaire : `cp systemd/berger-interface.service ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now berger-interface`.
- **Réglage** : `[interface] port = 8765` dans `config.toml` (facultatif ; l'adresse n'est PAS réglable).
- Pas d'application de bureau, pas de seconde chaîne de compilation, pas de base de données, pas de terminal web : les
  conversations avec les agents restent dans Herdr.

## 5. Sécurité

- **Écoute locale seulement** (`127.0.0.1`, en dur). Accès du propriétaire depuis son poste par tunnel ssh :
  `ssh -L 8765:127.0.0.1:8765 berger@<vm>` puis `http://localhost:8765` (ou par le VPN existant vers la VM).
- **Authentification, la plus simple qui tienne** : un **jeton aléatoire** (`secrets.token_urlsafe(32)`) dans
  `~/.config/berger/interface.jeton` (droits 600, dossier déjà masqué à tous les agents). `berger interface lien`
  affiche le lien d'entrée `http://localhost:8765/#jeton=…` (le jeton est dans le fragment : jamais envoyé dans
  l'adresse ni gardé dans les journaux du serveur) ; la page l'échange une fois (`POST /connexion`) contre un cookie
  `HttpOnly; SameSite=Strict; Path=/`, comparé à temps constant (`hmac.compare_digest`). Le cookie est **dérivé du
  jeton** (`hmac(jeton, "session")`) : aucune session gardée en mémoire, donc aucune session perdue quand le service
  redémarre ; `berger interface lien --nouveau` change le jeton et toute session ouverte tombe. Le fragment est effacé
  de la barre d'adresse dès la connexion (`history.replaceState`) ; le jeton n'est jamais mis dans le stockage du
  navigateur. Pas de compte, pas de mot de passe à gérer. Le fichier du jeton est hors du dépôt (liste blanche
  `.gitignore`, `berger verifier-depot`), distinct du coffre, jamais lu par le courtier ni par un agent.
- **Contre les pages piégées** : en-tête `Host` exigé (`localhost` ou `127.0.0.1` + port : contre le DNS rebinding) ;
  au lot 2 (protection CSRF), `Origin` exigé et identique, plus un jeton anti-rejeu dérivé (`hmac(jeton, "action")`)
  envoyé dans un en-tête `X-Berger-Action` qu'une page étrangère ne peut pas poser ; politique de contenu
  stricte (`Content-Security-Policy: default-src 'self'`, pas de script en ligne), `X-Frame-Options: DENY`,
  `Cache-Control: no-store` sur `/api`.
- **Données** : exactement celles que montrent déjà les panneaux de Herdr, rien de plus (pas d'`args` des
  validations, pas de chemin de document, aucune valeur du coffre : l'interface ne lit pas le coffre). Le texte
  venu d'un outil ou d'un agent est inséré comme **texte** (`textContent`), jamais comme HTML.
- Une erreur de commande s'affiche comme telle (« vue en échec : … »), jamais comme une vue vide.
- Journal du serveur (journal systemd) : méthode, chemin sans paramètres, code de réponse ; jamais le corps, le cookie
  ni le jeton (`log_message` remplacé).

**Un agent ne doit pas joindre l'interface — mesuré le 13/10, et comment c'est prouvé.**
- **Mesure** (agent Claude en mur strict, depuis son bac à sable — ce développeur) : le bac à sable a son **propre
  espace réseau** (une seule interface, `lo` ; `127.0.0.1` y est SON loopback, pas celui de la VM) : connexion directe
  à `127.0.0.1:22` et `127.0.0.1:8765` → refusée. Par le mandataire réseau du bac à sable : `http://127.0.0.1:22/`,
  `http://localhost:22/`, `http://127.0.0.1:8765/` → **403**, « host is on the deny list ». Donc fermé.
- **Non mesuré ici** : Codex (`codex sandbox`, réseau « none ») — je ne peux pas le lancer depuis ce poste ; le test
  ci-dessous le mesure dans `tests/tout.sh`.
- **Risque résiduel nommé** : un agent d'équipe a des sites permis ; un nom permis qui pointerait vers `127.0.0.1`
  serait résolu par le mandataire, côté VM. `berger equipe domaine` refuse déjà IP, `localhost` et port (motif
  `DOMAINE` de `bin/berger`), mais pas un nom qui se résout en `127.0.0.1`. Parade : la requête arrive avec
  `Host: <ce nom>` → **403** (contrôle `Host`) ; sans cookie → **401**. Deux barrières indépendantes du mur.
- **Test** (nouvelle sonde `tests/sonde-interface.py`, jouée par `tests/tout.sh` pour **chaque moteur**, comme
  `sonde-mur.py`) : `tout.sh` démarre hors bac à sable un faux serveur d'interface sur `127.0.0.1:<port libre>` (même
  code, installation jetable) ; la sonde, lancée DANS le bac à sable de l'agent, tente la connexion directe et par le
  mandataire. Vert seulement si : connexion refusée, OU réponse 401/403 sans jeton. Elle vérifie aussi que le fichier du
  jeton est illisible. Toute réponse 200 = rouge.

## 6. Périmètre du lot 1 (lecture seule)

**Écrans** (onglets tirés de `berger vues --json`, rendus depuis les schémas) : **tableau de bord** (Accueil, Tableau,
Synthèse, Décisions), **missions** (vue `missions` de chaque hôte, `suivi` de chaque agent en mission),
**validations** (liste en attente et leur détail complet, §6.4, avec la commande à taper : aucun bouton au lot 1),
**« À toi de décider »** (§6.3), **livrables** (§6.1), **versions par projet** (§6.2), **échanges**, **panneaux
d'agents** (tableau, journal, en cours, fiche) et **À lire** (liste ; le document s'ouvre par une commande en lecture
seule `berger document <id> --json` → `{titre, texte}`, qui ne le marque pas lu ; le marquage est une action du lot 2).
Les autres vues (Sources, Courtier, Checklists, Catalogue, Tokens) viennent par le même mécanisme, sans code en plus.

**Jamais montré** : aucune valeur du coffre ni secret (l'interface ne lit pas le coffre ; les données sont celles des
panneaux, déjà filtrées à la source : sorties d'outils par le courtier, échanges masqués à l'écriture) ; ni chemin
absolu de fichier (les livrables montrent un chemin relatif à leur racine) ; ni les conversations des agents (seule
la question qu'ils posent). Les arguments d'une écriture en attente ne paraissent que dans son détail (§6.4), passés
par le filtre de secrets.

**Données personnelles, au minimum** (exigence du propriétaire : recommandations de la CNIL — minimisation, sécurité,
durée de conservation) : rien de plus que ce que Herdr montre déjà ; un seul utilisateur (le propriétaire) ; rien ne
quitte la VM (aucune ressource extérieure, aucune mesure d'audience) ; **rien n'est gardé** par l'interface (pas de
cache, `Cache-Control: no-store`, journal sans contenu) : la durée de conservation reste celle de Berger (`berger
entretien`).

### Écrans ajoutés après la relecture de la maquette (13/10)

Même règle partout : **chaque donnée vient d'une vue de Berger** (`berger vue <type> --json` + son schéma, §1, §3) ;
la page ne calcule ni n'invente rien. Quand la donnée n'existe pas encore, la spec dit **quelle vue la produit** et
**d'où elle la lit**. Une vue nouvelle est un fichier `bin/vues/<type>.py` : elle apparaît AUSSI dans Herdr (même
contrat, mêmes tests) — pas d'écran réservé à la page. Aucun nom de projet dans le code : tout vient de `[equipes.<p>]`.

**6.1 Livrables — nouvelle vue `livrables`** (onglet Berger, **en tête de la navigation** : demande du propriétaire du
14/10, « la page dédiée aux maquettes » ; dans Herdr, juste après l'Accueil). Elle lit trois sources, et rien d'autre
(`livrables()` du cœur, seul mécanisme qui les liste) :
(a) `<bibliothèque>/agents/*/travail/` et ses sous-dossiers (`travail/<sujet>/`) (racine `[bibliotheque] racine`, comme
`BIBLIOTHEQUE` dans `bin/berger`) ; (b) les `a-lire/` (la même liste que `documents_a_lire()`) ; (c) les **branches en
cours** de chaque `[equipes.<p>]` — celles des développeurs ouverts (`branche` de leur `agent.conf`) et des demandes non
fusionnées (`equipes/<p>/demandes/*.json`) — lues dans le dépôt du chef (`depot`), **sans `fetch`** (aucune écriture ; la
date du dernier commit de la branche est montrée) : les fichiers **ajoutés ou modifiés sur la branche** par rapport à
`origin/<principale>` (`git diff --name-only --diff-filter=AM`, puis `git ls-tree` / `git cat-file`) sous les dossiers
déclarés `livrables = [...]` dans `[equipes.<p>]` (défaut `["docs/plans", "docs/apercu"]`) — ce qui est déjà sur main n'est
pas un livrable en cours. Ignorés : liens symboliques, fichiers cachés, fichier résolu hors de sa racine.
Schéma : `livrables: [{id: str, titre: str, auteur: Agent|null, origine: "bibliotheque"|"a_lire"|"branche",
projet: str|null, branche: str|null, chemin: str (relatif à sa racine : « travail/x.html », « docs/plans/x.md »),
genre: "md"|"html"|"autre", taille: int, date: quand, lu: bool|null, lien: Lien}]` (200 au plus, les plus récents). Titre :
1re ligne d'un `.md`, `<title>` d'un `.html`, sinon le nom du fichier.
Ouverture : vue d'objet `berger vue livrable <id> --json` → `{id, titre, auteur, origine, projet, branche, chemin, genre,
taille, date, texte: str|null, tronque: bool}` (`.md` : texte ≤ 200 Ko, rendu en texte par la page ; `.html` et autre :
`texte` null) ; `berger livrable <id> --brut <genre>` → le contenu tel quel (≤ 2 Mo), **seulement si le livrable a ce
genre** : le serveur l'appelle par `GET /api/livrable/<id>/<genre>` (id `^[0-9a-f]{16}$`, genre `html|md|autre`) et tire
ses en-têtes du genre ainsi vérifié par Berger, jamais de la page. L'`id` est une empreinte opaque, recherchée dans la liste
recalculée : jamais un chemin venu de la page.
- **Un `.html` (maquette, aperçu) dans un cadre isolé, avec son JavaScript** (décision du 14/10 : nos aperçus
  `docs/apercu/*.html` se construisent par leur script — la page rendue par `app.js` avec des réponses simulées) :
  `<iframe sandbox="allow-scripts">` (jamais `allow-same-origin`) et réponse
  `Content-Security-Policy: sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline';
  img-src data:; font-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors 'self'`, sans
  `X-Frame-Options` (remplacé par `frame-ancestors 'self'` : la page seule l'encadre).
  *Pourquoi c'est sûr* : sans `allow-same-origin`, le document a une **origine opaque**, même ouvert seul dans un onglet
  (la CSP `sandbox` vient du serveur, pas seulement du cadre) : il ne lit ni le cookie de session (de toute façon
  `HttpOnly`) ni le stockage, n'atteint pas la page qui l'encadre et ne peut pas appeler `/api/` en son nom (une requête
  d'origine opaque n'est pas « same-site » : le cookie `SameSite=Strict` ne part pas) ; `default-src`/`connect-src`/
  `form-action 'none'` : **aucune requête** (ni `fetch`, ni image, ni police, ni formulaire extérieurs) ; sans
  `allow-popups` ni `allow-top-navigation`, il n'ouvre pas de fenêtre et ne remplace pas la page. *Limite écrite* : un
  script peut encore faire naviguer son propre cadre vers une adresse extérieure (aucune directive CSP standard ne le
  bloque) ; il n'emporterait que ce qu'il contient déjà (le livrable lui-même), rien de la session.
- **Un autre genre** (`.md` tel quel, fichier quelconque) est **téléchargé** (`Content-Disposition: attachment`), avec
  `Content-Security-Policy: sandbox; default-src 'none'; frame-ancestors 'none'` s'il était ouvert.
- La vue d'objet est **fixe** dans la page : affichée à l'ouverture, pas relue toutes les 5 s (la maquette ne se recharge pas).
- **Où les agents déposent** : c'est la règle de documentation du sujet « livrables-visibles » (renvoi, pas de copie ici).
- Tests : `tests/livrables.py` (trois sources, ignorés, aucun chemin absolu, ordre, vue d'objet, `--brut` et ses refus,
  serveur : 401, CSP d'isolement, téléchargement, genre faux, 404, 405, page non encadrable ; **preuve dans un vrai navigateur** — chromium s'il est présent, sinon « NON JOUÉ », jamais vert : une sonde encadrée comme un livrable, sous `CSP_LIVRABLE`, ne lit ni un cookie pourtant lisible, ni la page, ni le stockage, et aucune de ses requêtes (fetch, image) n'arrive au serveur) ; `tests/interface.py`
  (schémas, chaque champ produit et affichable, texte = f(données), cadre de la page : `sandbox` = `allow-scripts` seul).

**6.1 bis Documents — une mini GED en consultation seule** (demande du propriétaire du 14/10, après Livrables). Parcourir,
chercher par nom et ouvrir les documents de la bibliothèque. **Aucun second mécanisme** : le lister de §6.1 devient
`documents()`, le SEUL qui liste des fichiers pour l'interface ; la vue `livrables` en est un **filtre**.
- *Racines fixes, et rien d'autre* : bibliothèque — `commun/` (origine `commun`), `equipes/<équipe>/projets/<projet>/`
  (origine `projet`, projet = `<équipe>/<projet>` ; jamais `archives/`), `agents/<agent>/travail/` (origine `travail`) ;
  les `a-lire/` (origine `a_lire`) ; les branches déclarées (origine `branche`, comme §6.1). Parcours sans suivre aucun
  lien (`os.walk`, liens de fichier ou de dossier ignorés, fichier résolu hors de sa racine ignoré), aucun fichier ni dossier
  caché ; 2 000 entrées au plus (les plus récentes), écrit dans le schéma.
- *Vue `documents`* (onglet Berger, juste après Livrables) : `{documents: [... mêmes champs que livrables ...]}`. La page les
  range par origine puis par dossier (parcourir) et **filtre par nom** ce qu'elle a reçu (présentation seulement : aucune
  donnée calculée, aucune requête de plus). *Vue `livrables`* = `documents()` dont l'origine est `travail`, `a_lire` ou
  `branche` et le genre `md`, `html` ou `pdf` (specs, maquettes, rapports).
- *Une seule ouverture* : la vue d'objet `livrable <id>` et `berger livrable <id> --brut <genre>` servent les deux pages
  (id recherché dans `documents()` recalculé, jamais un chemin ; id = empreinte de l'origine et du chemin — et du projet et
  de la branche pour une branche —, **stable quand le fichier est modifié** : ni date ni contenu dedans). Genres : `md` (texte rendu par la page, 200 Ko), `html`
  (cadre isolé de §6.1), `pdf`, les images `png`, `jpeg` (`.jpg`, `.jpeg`), `gif`, `webp` (jamais `.svg`, qui porte du
  script : `autre`), `autre`. Le genre est l'extension (table fermée `EXTENSIONS`) **confirmée par la signature** des premiers
  octets (`SIGNATURES`) : sinon `autre`. Taille d'ouverture bornée : **20 Mo** (`--brut` refuse au-delà, rien de servi).
- *Servis tels quels, avec leur type* : image → `image/<type>`, affichée par la page (`<img>`, `img-src 'self'` déjà
  permis), CSP `sandbox; default-src 'none'` si elle est ouverte seule ; pdf → `application/pdf`, ouvert dans un **nouvel
  onglet** (jamais encadré : `frame-ancestors 'none'`), CSP `default-src 'none'; object-src 'none'; frame-ancestors 'none'`
  sans `sandbox` (le lecteur PDF du navigateur refuse un document sandboxé) — le lecteur PDF n'a ni le cookie (`HttpOnly`)
  ni le DOM de la page. **Tout le reste est téléchargé** (`attachment`, CSP `sandbox; default-src 'none'`).
- *Trois conditions, parce que le pdf s'ouvre avec la MÊME origine que le cookie* (relecture du chef de projet, 14/10),
  chacune testée :
  1. **Content-Type fixé par l'extension** (table fermée du serveur : `.pdf` → `application/pdf`, `.png` → `image/png`…),
     jamais déduit du contenu, toujours avec `X-Content-Type-Options: nosniff` ;
  2. **les premiers octets vérifiés** par `berger livrable --brut` (pdf : `%PDF-` ; png, jpeg, gif, webp : leur signature) :
     un fichier qui ne les porte pas (un `.pdf` qui est en réalité du HTML) est **téléchargé de force**, jamais affiché ;
  3. **`Content-Disposition: inline` seulement pour pdf et images**, `attachment` pour tout le reste, et une CSP stricte sur
     chacune de ces réponses (ci-dessus).
- *Refus* : id inconnu ou hors motif, genre faux (vérifié par Berger, jamais pris de la page), fichier trop grand → aucun
  contenu servi. Aucune écriture (consultation seule : ni dépôt, ni suppression, ni renommage).
- *Tests* (`tests/livrables.py`, étendu) : chaque racine listée, `archives/`, liens et fichiers cachés ignorés ; Livrables =
  le filtre de Documents (même id pour le même fichier) ; pdf et image servis avec leur type et leurs en-têtes ; `.svg` et
  autres téléchargés ; > 20 Mo refusé ; page : recherche par nom dans le faux DOM ; les trois conditions du pdf : type de
  l'extension + `nosniff` même quand le contenu dit autre chose, un `.pdf` sans `%PDF-` (du HTML) servi en `attachment`
  et jamais `text/html`, `inline` pour pdf et images seulement, CSP présente sur chaque réponse.
- *Limite écrite* : l'affichage réel d'un pdf (lecteur du navigateur sous cette CSP) se vérifie dans le navigateur du
  propriétaire ; le test le prouve par les en-têtes.

**6.2 Versions par projet — nouvelle vue `versions`** (onglet Berger), une entrée par `[equipes.<p>]`.
Fusionné ≠ déployé : chaque valeur dit sa source et son âge.
- **main** : commit et date de `origin/<principale>` dans `depot` (sans `fetch`) ; version = première entrée
  `## [x.y.z]` de `CHANGELOG.md` sur cette branche (`git show`) ; étiquettes `v*` (5 dernières : nom, commit, date) ;
  `non_etiquete` = nombre de commits de main après la dernière étiquette.
- **dev** et **prod** : (1) si `[equipes.<p>.versions] dev_panneau = "<nom>"` / `prod_panneau` désignent un
  `[panneaux.<nom>]` (un verbe de lecture de l'outil de vérification du projet, ex. `dev-a-jour`, `sante`, s'il
  existe), la vue relit le résultat que le courtier a déjà rangé (même chemin que `etat_source()`, mêmes états
  ok/échec/figé/attente) et y prend les lignes `version: …`, `commit: …`, `adresse: …` (format fixé, une clé par
  ligne ; le reste est ignoré) ; (2) sinon un réglage déclaré `prod = "x.y.z"`, `dev_adresse = "…"` dans
  `[equipes.<p>.versions]`, montré « déclaré à la main » avec la date de `config.toml` ; (3) sinon « inconnu » —
  jamais deviné. Pour le projet dont la fusion EST l'installation (`installer_outil`), prod = le commit installé
  (`tete_installation()`).
- **Migrations à jouer à la main** : les sous-sections `### Migrations` des entrées du `CHANGELOG.md` de main plus
  récentes que la version en prod (précédence SemVer : `precedence()` de `courtier/outils/_portes.py`, mise en
  commun) ; prod inconnue → « à vérifier », pas de liste. Convention ajoutée à `commun/modeles/equipe-processus.md`.

Schéma : `projets: [{projet: str, main: {commit: str, date: quand, version: str|null, non_etiquete: int},
etiquettes: [{nom: str, commit: str, date: quand}], dev: Deploiement, prod: Deploiement, migrations_a_jouer:
[{version: str, texte: str}]|null}]`, avec `Deploiement = {version: str|null, commit: str|null, adresse: str|null,
source: "outil"|"declare"|"installation"|"inconnu", etat: "ok"|"echec"|"fige"|"attente"|null, quand: quand|null,
en_retard_sur_main: int|null}`.

**6.3 « À toi de décider » = tout ce qui attend le propriétaire — vue `decisions` enrichie** (l'Accueil en reprend
le haut). Chaque élément a un `genre` et une `source` :

| Genre | D'où il vient (existe déjà ?) |
|---|---|
| `validation` | écriture en attente du courtier, sans `valideur` (oui) |
| `terminal` | agent arrêté sur une permission : statut Herdr `blocked` (oui) |
| `bloque` | ligne `⚠ Bloqué : …` de la `CHECKLIST.md` d'un agent (oui ; une ligne qui attend le chef ou le coordinateur ne monte au propriétaire qu'après l'escalade de la supervision : la vue lit l'état d'escalade de `.supervision.json`) |
| `go` | **NOUVEAU marquage** : ligne `⚠ Go attendu : <quoi> — <où lire>` dans la `CHECKLIST.md` (spec, droits, mise en prod) |
| `question` | **NOUVEAU marquage** : ligne `❓ Question : <texte>` dans la `CHECKLIST.md` ; vaut pour les deux moteurs (la lecture de la fin de conversation, `question_en_attente`, ne marche que pour Claude ; gardée en repli pendant la transition) |
| `a_decider` | **NOUVEAU marquage** : document `a-lire/` dont une ligne commence par `Décision attendue :` dans ses 15 premières lignes ; reste tant que la ligne y est (lu ou non) |
| `a_lire` | documents non lus (oui) |
| `fusion` | demande de fusion sans agent responsable (oui) |

`checklist()` lit les deux nouvelles lignes comme elle lit `⚠` (champs `go`, `question` ajoutés à `Checklist`). La
règle « pour demander un go ou poser une question au propriétaire, écris cette ligne » va dans `commun/REGLES.md` et
`commun/modeles/` (même fusion, décidée par le propriétaire). Schéma : `decisions: [{pour: "toi"|"agent", genre:
(ci-dessus), titre: str, detail: str, quand: str, agent: Agent|null, n: int|null, projet: str|null, sujet: str|null,
document: str|null (id), commande: str|null (la commande à taper)}]`.

**6.4 Détail d'une demande avant de décider — nouvelles vues d'objet `validation <n>` et `demande <projet> <sujet>`.**
- `validation <n>` : tout le fichier de l'écriture en attente — `n, agent, outil, verbe, apercu` (**complet** : la
  coupe n'est que dans le rendu texte), `args` (passés par le filtre de secrets du journal, mis en commun : une valeur
  suspecte → « [masqué] »), `demande, valideur` ; et, si le verbe porte sur une demande de fusion (`fusionner`,
  `demander-fusion`), la demande liée ci-dessous.
- `demande <projet> <sujet>` : `equipes/<p>/demandes/<sujet>.json` + le dépôt du chef — `sujet, branche, commit,
  agent, etat, demande (quand), resume (texte complet), renvois, motif, commits: [{id, sujet}], fichiers: [{chemin,
  ajouts: int, retraits: int}]` (`git diff --numstat origin/<principale>...<commit>`, 300 au plus),
  `portes: [{porte, etat, code, bilan, par, quand, ou: "demande"|"rejeu"|"fusion"}]`.
- **Champs à ajouter côté Berger** (le reste existe) : `resume` est coupé à 1 500 caractères à l'inscription
  (`inscrire_demande`, `_portes.py`) → gardé jusqu'à 8 000, avec `tronque` ; chaque porte inscrite reçoit `par`
  (l'agent dont la demande a fait jouer la porte, ou le chef pour un rejeu) et `quand` ; `rejouer` (outil du chef)
  **inscrit** son résultat dans la demande (`rejeux: [{par, quand, portes, recompte}]`) au lieu de seulement le
  rendre.

## 6 bis. Ajouts au lot 2 (après un nouveau go)

**Écran d'un agent en direct, en lecture seule — nouvelle vue d'agent `direct`.** Source : `herdr pane read <pane>
--source visible --format text` (Herdr 0.9.3, vérifié par `--help`), sur les seuls panneaux de l'agent
(`herdr_ids`, comme `statut_herdr`). Schéma : `agent: Agent, moteurs: [{moteur: str, lignes: [str] (≤ 200, codes de
terminal retirés, chaque ligne passée par le filtre de secrets), quand: quand}], checklist: Checklist|null`.
Rafraîchi toutes les 3 s tant que l'écran est visible. Rien n'est envoyé au panneau (pas de clavier).

**Santé de Berger — nouvelle vue `sante`** (ses alertes rejoignent la Synthèse par `alertes_synthese()`) :
`installation: {commit, date, forge_commit, ecart: int}` (`tete_installation()` et la branche principale de la forge
de l'équipe qui a `installer_outil`) ; `installations: [{quand, avant, apres, etat, detail}]` (les 10 dernières lignes
de `courtier/installations.log`, retours arrière automatiques signalés en rouge) ; `courtier: {actif: bool,
demandes_en_cours: int, executions: int}` (`courtier_actif()`, `courrier/encours/`, `*.execution`) ;
`services: [{nom, actif: bool}]` (`berger.timer`, `berger-herdr` : `systemctl --user is-active`) ;
`montages: [{chemin, monte: bool, repond: bool, delai_ms: int|null, erreur: str|null}]` — **nouveau réglage**
`[sante] montages = ["/chemin/du/lecteur"]` : `os.path.ismount` puis lecture du dossier dans un sous-processus limité
à 3 s (un partage réseau figé bloque sans erreur : c'est ce délai qui le rend visible). Berger ne connaît aujourd'hui
aucun montage : sans ce réglage, la ligne dit « aucun montage déclaré ».

## 6 ter. Lot 1c — l'accès par une vraie adresse web (décision du propriétaire du 14/10 ; AVANT le lot 2)

Le propriétaire refuse le tunnel ssh + localhost : il veut `https://berger.<domaine interne du cabinet>`, sur PC et
téléphone, comme les autres applications du cabinet, derrière le mandataire inverse **SWAG** (conteneur à part), joignable
**seulement** depuis le réseau interne et le VPN, jamais depuis Internet. SWAG termine le TLS et relaie vers la VM en HTTP.
Le jeton d'entrée, le cookie, le contrôle Host et la politique de contenu restent ; on ajoute ce qui suit.

**1. Écoute déclarée, jamais en dur.** `[interface]` de `config.toml` gagne `adresse` (l'adresse de la VM sur son réseau)
et garde `port` (fixe). Défaut inchangé : `127.0.0.1` et 8765 — sans réglage, rien ne change (tunnel). Aucune adresse ni nom
du cabinet dans le code, les tests ni `config.exemple.toml` (exemples : `<adresse de la VM>`, `berger.<domaine interne>`) ;
`berger verifier-depot` le garde déjà. `adresse` n'accepte qu'une adresse IP littérale (jamais `0.0.0.0` ni `::`).

**2. Filtrage réseau — deux barrières, la seconde ne remplace pas la première.**
- *Adresse source du mandataire* : la mesurer après mise en place par l’exploitation dans le journal du serveur
  (adresse du pair, jamais un en-tête). Une traduction réseau peut la rendre différente de son adresse de destination.
- *Dans le serveur* : `[interface] sources = ["<adresse source de SWAG>"]` ; toute connexion d'une autre adresse → 403
  avant toute lecture (défaut : `["127.0.0.1"]`, le tunnel). Testé.
- *Pare-feu de la VM* (nftables, `/etc/nftables.conf`, entrée en `policy drop`, une règle par source — vérifié le 14/10) :
  une règle de plus dans `chain entree`, posée **par le propriétaire** :
  `ip saddr <adresse source de SWAG> tcp dport <port> accept comment "SWAG → interface berger"`.
  Sauvegarde AVANT : `cp /etc/nftables.conf /etc/nftables.conf.avant-interface-AAAAMMJJ`, vérifiée (`diff` vide, fichier
  non vide), puis contrôle de syntaxe `nft -c -f /etc/nftables.conf` avant d'appliquer `nft -f /etc/nftables.conf`.
  Retour arrière : `cp /etc/nftables.conf.avant-interface-AAAAMMJJ /etc/nftables.conf && nft -f /etc/nftables.conf`
  (effet : le port n'est plus joignable que depuis la VM elle-même).
- *Limite connue, écrite* : une connexion de la VM vers sa propre adresse passe par `lo`, accepté par le pare-feu. Un
  processus de la VM hors bac à sable (un agent en `mur = ouvert`, un service) joint donc le port ; il se heurte au filtre
  `sources` (403) puis au jeton (401). Les agents en mur strict sont mesurés (point 3).

**3. Mesure qu'un agent ne joint pas le port** (`tests/sonde-interface.py` étendue, jouée par `tests/tout.sh` pour chaque
agent et chaque moteur, Claude et Codex) : la sonde reçoit le port ET l'adresse déclarée ; elle tente `127.0.0.1:<port>` et
`<adresse>:<port>`, en direct et par le mandataire du bac à sable. Vert seulement si : refus de connexion, ou 401/403 sans
jeton ; toute réponse 200 est rouge ; le fichier du jeton reste illisible. **Témoin** : hors bac à sable, `tout.sh`
interroge le même serveur d'essai aux deux adresses et doit obtenir 401/403 — sinon la sonde est dite « sans témoin »
(INFO), jamais verte. Le serveur d'essai de `tout.sh` écoute sur l'adresse déclarée, sur un port libre.

**4. Host, cookie, en-têtes du mandataire.**
- `[interface] nom = "berger.<domaine interne>"` : l'en-tête Host doit valoir ce nom (port 443 implicite) ; `localhost` et
  `127.0.0.1:<port>` ne restent acceptés que si `adresse` vaut `127.0.0.1` (mode tunnel). Le lien d'entrée devient
  `https://<nom>/#jeton=…` dès que `nom` est déclaré.
- Cookie : `Secure` en plus de `HttpOnly` et `SameSite=Strict` dès que `nom` est déclaré (la page est alors servie en HTTPS
  par SWAG) ; sans `nom`, pas de `Secure` (le tunnel est en HTTP local).
- **Aucune confiance dans `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host`, `X-Real-IP`** : le serveur ne s'en
  sert pour RIEN (ni contrôle, ni journal). Raison écrite : il n'a besoin ni de l'adresse du client (le contrôle porte sur
  le pair, SWAG, et sur le jeton) ni du schéma (connu par `nom`). Testé : un `X-Forwarded-For` forgé ne change rien.
- Lot 2 : l'`Origin` exigé devient `https://<nom>`.

**5. Le jeton d'entrée est gardé**, en plus du filtrage : `berger interface lien` reste le seul chemin d'entrée, sur PC
comme sur téléphone (le lien s'ouvre une fois, le cookie dure ; `--nouveau` ferme toutes les sessions).

**6. Retour arrière** (un geste, tracé) : retirer `adresse`, `nom` et `sources` de `[interface]` (retour aux défauts :
`127.0.0.1`, accès par tunnel ssh) et relancer le service ; restaurer `/etc/nftables.conf` (ci-dessus) ; côté exploitation,
retirer le site SWAG et le nom DNS. `berger interface lien` redonne alors le lien `http://localhost:<port>/`.

**7. Chiffrement SWAG → VM (inclus dans le 1c par le go du 14/10)** : le serveur parle TLS lui-même (module `ssl` de
Python standard : aucune dépendance Python ajoutée), avec un certificat INTERNE.
- *Réglage* : `[interface] tls = true`. Sans lui : HTTP, comme au lot 1a (mode tunnel).
- *Où* : `~/.config/berger/interface/` (dossier 700, masqué à tous les agents comme le coffre et le jeton) :
  `certificat.pem` (public) et `cle.pem` (600) ; jamais dans le dépôt, jamais affichée.
- *Création* : `berger interface certificat [--nouveau]` (propriétaire seul : refusé si `BERGER_AGENT`), qui lance
  `openssl` (présent sur la machine) : clé EC P-256 neuve, certificat auto-signé `CN = <nom>`, noms alternatifs
  `DNS:<nom>` et `IP:<adresse>`, durée **397 jours** (la plus longue que les navigateurs acceptent pour un serveur ; ici
  seul SWAG le lit). Sans `--nouveau`, un certificat existant n'est jamais écrasé ; la commande affiche son état (dates,
  empreinte SHA-256), jamais la clé. Écriture atomique, clé créée en 600 d'emblée.
- *Reconnaissance par SWAG* (fait par l'exploitation) : le CERTIFICAT (pas la clé) est déposé chez SWAG, et le site
  vérifie le serveur avec lui (`proxy_ssl_verify on`, `proxy_ssl_trusted_certificate <le certificat déposé>`,
  `proxy_ssl_name <nom>`) ; l'empreinte affichée par `berger interface certificat` permet de vérifier le dépôt.
- *Renouvellement* : avant l'échéance, `berger interface certificat --nouveau`, nouveau dépôt du certificat chez SWAG,
  relance du service. Le serveur et `berger interface certificat` disent clairement « certificat expiré le … » ou
  « expire dans N jours » (≤ 30) — au démarrage dans le journal du service, et à chaque `berger interface lien` ; la vue
  santé du lot 2 le reprendra.
- *Refus du HTTP en clair* : quand `tls = true`, le port ne parle que TLS ; une requête HTTP en clair n'obtient aucune
  réponse HTTP (testé). Version minimale TLS 1.2.
- *Retour arrière* : retirer `tls` de `[interface]` et relancer le service (retour en HTTP) ; côté SWAG, revenir à un
  relais `http://` (exploitation). Les fichiers du certificat peuvent rester : ils ne sont plus lus.
- *Tests* : HTTP en clair refusé quand TLS est réglé, HTTPS accepté avec le certificat ; clé en 600 ; certificat non
  écrasé sans `--nouveau` ; certificat expiré signalé par un message clair ; refus à un agent ; la sonde vérifie que la
  clé est illisible depuis le bac à sable.

**À configurer par l'exploitation** (hors de ce dépôt, avec le go du propriétaire) : la règle pare-feu réseau de SWAG vers la
VM (port déclaré seulement) ; le site SWAG `berger.<domaine interne>` (proxy vers `<adresse>:<port>`, restreint au réseau
interne et au VPN, certificat du domaine interne) ; le nom dans le DNS interne seulement (jamais dans le DNS public).

**Tests du lot 1c** (`tests/interface-serveur.py`, installation jetable) : écoute sur l'adresse déclarée ; refus d'une
adresse `0.0.0.0`/`::` ou d'un nom à la place d'une IP ; pair hors `sources` → 403 sans rien lancer ; Host = `nom` → accepté,
`localhost` → 403 quand `nom` est déclaré ; cookie `Secure` avec `nom`, sans `Secure` sinon ; `X-Forwarded-*` forgés
sans effet ; lien `https://<nom>/#jeton=…` ; sans réglage, comportement du lot 1a identique (non-régression).

**État de mise en service** (go du propriétaire du 14/10, mesures de l'exploitation ; référence : dépôt de l'infrastructure,
PR #49). Le lot 1c est **en service depuis le 14/10 vers 11 h**, TLS de SWAG à la VM compris :
- SWAG relaie en `https` vers le port de l'interface avec `proxy_ssl_verify on` ; le certificat interne de la VM y est en
  confiance (même empreinte SHA-256 des deux côtés ; échéance 15/11/2027) ; le Host transmis est le nom public.
- Le pare-feu du réseau n'ouvre que de SWAG vers la VM ; `nftables` de la VM n'accepte le port que depuis SWAG.
- Mesures de l'exploitation : via SWAG, 200 pour la page et 401 pour l'API sans jeton ; connexion directe depuis le poste
  de l'exploitation : refusée ; depuis la VM elle-même : 403 (filtre `sources`) ; aucune réponse en HTTP clair.
- **Reste à prouver** : `tests/sonde-interface.py` jouée par le `tests/tout.sh` de nuit (agents Claude et Codex).
- **Conséquence** : la condition « TLS de SWAG à la VM », posée AVANT d'installer le lot 2, est **remplie**.
(Règle du dépôt : ni adresse, ni nom de domaine, ni numéro de règle du pare-feu ici — « SWAG », « la VM », « le nom
public » et la référence de la PR suffisent.)

## 6 quater. L'interface en temps réel (proposition de l'exploitation du 14/10 ; go du propriétaire du 14/10 sur 98355a0)

*But* : une mise à jour en **moins d'1 s**, plus de rafraîchissement à vide toutes les 5 s.
*Comportement (réalisé)* — plus simple que la proposition d'origine, sans rien perdre : le serveur ne garde ni ne pousse
aucune donnée, il pousse un **signal** ; la page relit alors SA vue par la lecture habituelle (`berger vue … --json`). Pas
de cache côté serveur, pas de second chemin des données : la source unique reste `donnees()`.
- `berger veille` (UN processus pour tous les flux, lancé par le serveur au premier flux, relancé s'il meurt) relève toutes
  les 0,5 s la date et la taille (`os.stat`, rien du contenu) de ce qui fait changer les vues : `courtier/echanges.jsonl`,
  les écritures en attente, `equipes/*/demandes/`, les lectures, `a-lire/`, et pour chaque agent —
  **Claude ou Codex, mêmes fichiers** — `CHECKLIST.md`, `TODO.md`, `MISSION.md`, `.herdr.json`, le journal du jour,
  `a-lire/` ; les statuts Herdr toutes les 5 s ; `courtier/appels.log` toutes les **30 s** seulement (il change à chaque
  appel du courtier : mesuré le 15/10 sur l'installation, 12 à 18 appels par minute, surtout les lectures de la
  supervision — relevé à 0,5 s, ce serait un signal presque continu ; à 30 s, au plus 2 signaux par minute). Il écrit une
  ligne « changement » (regroupée sur 0,3 s) ; l'état de départ n'est pas un changement. **Plus aucun flux ouvert pendant
  60 s** : le serveur arrête la veille ; le flux suivant la relance.
- Le serveur relaie ce signal en **SSE** : `GET /api/flux` (`text/event-stream`, mêmes cookie, Host, sources et en-têtes que
  le reste de l'API), un événement `change` par changement, un événement `battement` toutes les 25 s (un événement, pas un commentaire :
  la page voit que le flux vit), `retry: 3000` en tête.
- La page ouvre un `EventSource` (même cookie, même filtre de sources, même Host, même CSP : `connect-src 'self'` suffit) ;
  sur `change`, elle relit sa vue (une vue fixe — un document ouvert, Documents — n'est pas rechargée) ; tant que le flux
  est ouvert, la boucle de 5 s se tait. **Repli automatique** sur la boucle de 5 s si le flux tombe (erreur, coupure, veille
  morte, SWAG qui ne le laisse pas passer) ; EventSource se reconnecte seul ; refusé pour de bon (503), nouvel essai 30 s
  plus tard. Un flux « ouvert » mais muet plus de 40 s (un relais qui retient le flux, faute de `proxy_buffering off`)
  ne compte plus : la boucle de 5 s reprend. La file « une demande à la fois » reste pour toutes les lectures.
*Chiffrage* :
- **Charge sur la VM** : un seul processus de veille ; `os.stat` toutes les 0,5 s sur quelques centaines de fichiers au plus
  (Python standard, aucune dépendance ; `inotify` exigerait `ctypes` ou un paquet : écarté) ; les statuts Herdr toutes les
  5 s (comme aujourd'hui la boucle de 5 s d'UNE page, mais une seule fois pour toutes les pages) ; une relecture de vue par
  page et par changement (0,2 s mesuré le 14/10 pour Synthèse, Courtier, Accueil), au lieu d'une toutes les 5 s.
- **Connexions ouvertes** : une par onglet ouvert ; **8 flux** au plus (au-delà : 503 « trop de flux ouverts (8 au plus) : la
  page reste sur le rafraîchissement de 5 s ») ; battement toutes les 25 s ; chaque flux tient un fil du serveur
  (`ThreadingHTTPServer`) et ne compte pas dans les 4 commandes simultanées.
- **Côté SWAG** (posé par l'exploitation, avec le go du propriétaire) : sur ce seul chemin, `proxy_buffering off` et un long
  délai de lecture (`proxy_read_timeout` au-delà du battement, ex. 1 h).
- **Tests exigés** (relecture du chef de projet, 14/10) :
  1. une **validation posée** (fichier ajouté dans `courtier/validations/`) **apparaît dans la page en moins de 2 s** (de
     l'écriture du fichier à l'événement reçu, puis `/api/validations` la donne) ; de même une checklist d'un agent Claude
     ET d'un agent Codex ;
  2. **flux coupé** (serveur qui ferme la connexion) → la page **repasse au rafraîchissement de 5 s**, puis **le flux
     reprend seul** quand le serveur l'accepte de nouveau (sans recharger la page) ;
  3. **un client en trop** (9e flux) est **refusé proprement** : 503 avec un message clair, aucune connexion déjà ouverte
     touchée, et ce client reste sur la boucle de 5 s.
  Et : aucun événement sans changement ; sans cookie → 401 ; Host étranger → 403 ; battement présent ; une seule veille pour
  tous les flux ; arrêtée 60 s après le dernier flux et relancée au suivant ; `appels.log` écrit en continu → au plus un
  signal par relevé. Fichiers : `tests/temps-reel.py` (serveur, vrais flux) et `tests/interface.py` (page, faux DOM : flux
  ouvert → boucle muette, `change` → relecture, muet plus de 40 s → boucle, coupure → repli puis reprise seule, 503 →
  nouvel essai à 30 s).

## 6 quinquies. Usage du propriétaire (avis de l'exploitation, relayé avec le go du propriétaire du 14/10 — SPEC SEULEMENT)

Sept points, par priorité. **Aucun code avant le go du propriétaire sur cette spec** ; les points 1 et 6 touchent le
**cœur** (courtier, supervision) : rien n'y est codé, **même dans une pile locale**, avant son go explicite.

**Multi-moteur (rappel du propriétaire, 14/10)** : le cœur sert des agents **Claude ET Codex** ; chaque comportement et
chaque test ci-dessous vaut pour les deux, et le dit. Ce sur quoi ils reposent est déjà commun aux deux moteurs : l'identité
d'un agent est `BERGER_AGENT`, posé par Berger au lancement pour Claude comme pour Codex (jamais déduit du moteur) ; un message
part par `berger parler` vers le panneau Herdr du moteur de l'agent ; une checklist est un fichier texte que les deux moteurs
écrivent dans leur dossier ; les règles (marquages) arrivent par le même `AGENTS.md` régénéré (Claude le lit par son
`CLAUDE.md`, Codex directement). Aucun comportement ne lit un fichier propre à un moteur (`.claude/`, `.codex/`) ni le texte
d'une conversation. Les tests de ces points se jouent **pour chaque moteur** : les suites sans modèle avec un agent
`moteur = claude` ET un agent `moteur = codex` dans le jeu de données ; `tests/tout.sh` (boucle `codex claude`, comme
aujourd'hui) pour ce qu'un agent réel fait dans son bac à sable.

**1. Auteur exact des échanges** (cœur).
- *Constat* : `courtier/echanges.jsonl` attribue au propriétaire des textes automatiques. Mesuré le 14/10 : environ 103
  « Rappel : ta demande… », 73 « Rappel : la demande… », 79 « Décision sur ta demande… », 52 « Demande de fusion… »,
  39 « Berger : ta mission… », plus les messages de l'agent de sécurité de l'exploitation passés par `berger parler`.
  Cause lue dans le code : `berger parler` écrit l'échange au nom du propriétaire quand `--de` n'est pas donné (`echange(de
  or PROPRIETAIRE, …)`), et les relances, décisions et missions l'appellent sans `--de` ou avec `--sans-echange` puis une
  trace à part.
- *Comportement* : chaque écriture d'échange porte son **émetteur exact** — `Berger · supervision` (relances, alertes),
  `Berger · courtier` (décisions de validation, demandes de fusion), l'agent qui parle (par son identifiant, quand
  `berger parler` est lancé par un agent ou un outil), le propriétaire **seulement** quand c'est lui (terminal, interface).
  `berger parler` sans `--de` venant d'un processus qui n'est pas le propriétaire : refus (plus de défaut silencieux). Le
  journal de l'agent et la vue Échanges montrent le même émetteur.
- *Existant* : reprise **seulement si elle est sûre** — un texte qui commence exactement par l'un des préfixes fixes
  ci-dessus est réattribué à son émetteur à la lecture (sans réécrire le fichier) ; tout le reste garde « propriétaire »
  et la vue le dit en clair (« auteur non vérifié avant le JJ/MM »).
- *Tests* : chaque chemin d'écriture (relance, décision, mission, demande de fusion, parler d'un agent, parler du
  propriétaire) donne le bon `de` ; parler sans `--de` hors propriétaire → refus ; reprise de l'existant : préfixes
  réattribués, le reste marqué « non vérifié ».
- *Multi-moteur* : l'émetteur d'un agent est son `BERGER_AGENT` (Claude et Codex), jamais le moteur ; le destinataire
  reçoit le message dans le panneau de SON moteur, avec le même en-tête. Tests : un message d'un agent Claude et d'un agent
  Codex → `de` = leur identifiant ; un message VERS un agent Claude et vers un agent Codex → même échange écrit, même
  émetteur (faux Herdr) ; sonde de `tests/tout.sh` pour chaque moteur : un agent réel ne peut pas écrire un échange au nom
  d'un autre (ni du propriétaire) depuis son bac à sable.

**2. Échanges allégés.**
- *Constat* : la vue Échanges envoie environ 600 Ko toutes les 5 s.
- *Comportement* : les **N derniers** (50) avec **pagination** (`avant=<quand>`), **filtres** par agent, chantier et genre,
  les **automatiques masqués par défaut et regroupés** (« 12 rappels identiques », un seul affiché, dépliable) ; en temps
  réel (§6 quater), seul le **nouveau** est poussé. Les filtres sont des arguments de la vue (motifs vérifiés), jamais un
  calcul de la page.
- *Tests* : taille d'une page bornée (moins de 50 Ko sur le jeu) ; pagination sans trou ni doublon ; filtres ; regroupement
  (12 rappels identiques → 1 ligne qui dit 12) ; un automatique masqué par défaut, visible avec le filtre.

**3. « À lire » qui se vide.**
- *Constat* : des notes restent alors que leur sujet est réglé (« lot 1c… il faut ton go », « <projet> dev en <version> »).
- *Comportement* : une note peut déclarer en tête ce qu'elle attend (`Décision attendue : …` existe déjà ; ajout :
  `Lié à : validation <n>` ou `Lié à : demande <projet>,<sujet>`, dans les 15 premières lignes) ; quand l'objet lié est réglé
  (écriture décidée : `<n>.fait.json` ; demande à l'état « fusionnée » — il n'existe pas d'état « abandonnée »), la note
  **sort d'elle-même** : elle compte comme lue (calculé par `lus()` à chaque lecture, rien d'écrit en plus, jamais
  supprimée), quitte le compte « non lus » et « À toi de décider », et dit pourquoi (champ `regle` de la vue `alire`,
  « réglé : … » dans Herdr et la page). Un agent Claude ou Codex écrit la même ligne. « Marquer lu » à la main : lot 2
  (`berger lu <id>`).
- *Tests* (`tests/alire-se-vide.py`) : note d'un agent Claude liée à une écriture décidée → lue ; note d'un agent Codex liée
  à une demande fusionnée → lue ; liées à une écriture en attente ou à une demande à relire → restent ; sans lien → reste ;
  compte « non lus » ; fichiers jamais supprimés ; quitte « À toi de décider » ; Herdr dit pourquoi ; une écriture décidée
  pendant la lecture → la note devient lue.

**4. Deux niveaux de menu.**
- *Comportement* : chaque vue déclare son niveau (`MENU = "toi"` ou `"technique"`, à côté de `ONGLET`/`ORDRE`, exposé par
  `berger vues --json`) ; la page affiche « Pour toi » (Accueil, Décisions, Chantiers, Échanges, Livrables, Documents) puis
  « Technique » (Sources, Catalogue, Tokens, Courtier, Checklists, Synthèse, Tableau…), repliable. Aucun nom de vue dans la
  page (règle §3 inchangée) ; Herdr garde ses onglets.
- *Tests* : chaque vue déclare `MENU` (contrat de `tests/vues.py`) ; la page range par `MENU` (faux DOM).

**5. Vue Chantiers** (aussi dans Herdr).
- *Comportement* : une entrée par sujet d'équipe : projet, chef, développeur(s), **état** (en cours / à relire / à finir /
  à valider / fusionné / installé), branche, portes (signées), validation à faire (n°), derniers échanges du sujet. Lue
  dans les mêmes sources que `equipe liste`, `demande` et Échanges (aucune nouvelle source).
- *Tests* : chaque état produit par le jeu de données ; schéma, champs produits et affichables (§3) ; texte = f(données).
- *Multi-moteur* : le moteur d'un développeur (Claude ou Codex) est montré, jamais utilisé pour calculer l'état (qui vient
  des demandes, des portes et des checklists, communs aux deux). Test : un développeur Claude et un développeur Codex dans
  le jeu de données, mêmes états produits.

**6. « En attente » n'est pas « bloqué »** (cœur : supervision).
- *Constat* : attendre le propriétaire ou une relecture s'écrit aujourd'hui `⚠ Bloqué` : rouge à l'Accueil et alerte au
  chef de projet, alors que rien n'est en panne.
- *Comportement* : nouveau marquage de checklist **`⏳ En attente : <qui> — <quoi>`**, distinct de `⚠ Bloqué` (une panne,
  une aide nécessaire) et de `⚠ Go attendu` (un go du propriétaire, montré dans « À toi de décider »). Effet : ni rouge à
  l'Accueil (gris « en attente »), ni alerte ni relance de la supervision tant que l'attente est réelle (validation en
  cours, demande de fusion inscrite) ; une attente sans objet en cours depuis plus de 24 h redevient une relance douce au
  chef de projet. La règle est ajoutée à `commun/REGLES.md` (avec le go).
- *Tests* : `⏳ En attente` → aucune alerte, aucun rouge ; `⚠ Bloqué` → alerte comme aujourd'hui ; attente sans objet
  > 24 h → une relance ; `⚠ Go attendu` inchangé.
- *Multi-moteur* : le marquage est une ligne de `CHECKLIST.md`, lue de la même façon pour les deux moteurs ; la règle
  arrive aux deux par `AGENTS.md` (régénéré) ; la relance douce part par `berger parler` vers le panneau du moteur de
  l'agent. Tests : un agent Claude et un agent Codex avec `⏳ En attente` → aucune alerte ni rouge pour l'un comme pour
  l'autre ; relance après 24 h reçue par chacun dans son panneau (faux Herdr) ; `AGENTS.md` régénéré d'un agent Claude et
  d'un agent Codex : la règle y figure ; `tests/tout.sh`, pour chaque moteur : un agent réel écrit le marquage dans sa
  checklist depuis son bac à sable, et la supervision le lit comme en attente.

**7. Répondre depuis un fil** (lot 2).
- *Comportement* : l'action « Répondre » du lot 2 (`berger parler`) part du fil d'un chantier ou d'un échange ; la réponse
  porte la référence du fil (`fil = <id>` dans l'échange écrit) et s'y affiche.
- *Tests* : réponse rattachée au bon fil ; un fil inconnu → refus sans rien lancer.

**Découpage en demandes courtes** (ordre recommandé : 1, puis 2 et 6, puis 5, avant le reste du lot 2) :

| Ordre | Demande | Touche le cœur | Préalable |
|---|---|---|---|
| 1 | (point 1) Auteur exact : `--de` partout, refus du défaut silencieux, reprise sûre de l'existant | oui (courtier, supervision, `parler`) | go explicite du propriétaire |
| 2 | (point 2) Échanges allégés : N derniers, pagination, filtres, automatiques regroupés | non (vue `echanges`) | 1 (les automatiques se reconnaissent à leur émetteur) |
| 3 | (point 6) `⏳ En attente` : marquage, Accueil, supervision, REGLES | oui (supervision, `commun/`) | go explicite du propriétaire |
| 4 | (point 5) Vue Chantiers (+ Herdr) | non | 2 (derniers échanges par sujet) |
| 5 | (point 3) À lire qui se vide (`Lié à :`) | non (vue `alire`, marquage de lecture) | — |
| 6 | (point 4) Deux niveaux de menu (`MENU`) | non (contrat des vues, page) | — |
| 7 | (point 7) Répondre depuis un fil | non (lot 2, après les 4 actions) | lot 2 (b) |

## 7. Hors périmètre, et risques

**Hors périmètre** : terminal interactif ou conversation dans la page (l'écran en direct du lot 2 se lit seulement) ; modification de fichiers, de `config.toml`, d'un
`agent.conf` ; missions, relances, fusions, installations depuis la page ; accès depuis Internet ; plusieurs comptes ;
application mobile ou de bureau ; notifications ; historiques et graphiques.

| Risque | Parade |
|---|---|
| **Lot 0 gros** : il touche les 16 vues, les 6 `fiche_*`, `cartes_tableau()`, `decisions()` | découpé en demandes de fusion successives (0a : le mécanisme + 3 vues simples — `alire`, `decisions`, `synthese` ; 0b, 0c : le reste), chacune avec la preuve octet pour octet ; Herdr ne change pas entre deux |
| Le texte de Herdr recalcule en douce une donnée hors de `donnees()` | test : `rendu_texte(json.loads(json.dumps(donnees())))` = `rendre()` octet pour octet — le rendu ne dépend QUE des données |
| **Charge** : 16 vues × 5 s | vue visible seule, onglet caché = rien, une demande en vol par page, 10 s maximum par commande, 4 en même temps (§4) |
| **Session perdue au redémarrage** du service | aucune : cookie dérivé du jeton, sans état serveur (§5) |
| Le code du serveur change à une installation | `installer` relance `berger-interface` ; s'il ne repart pas, la page ne répond plus mais Herdr marche : rien n'est perdu |
| Un nom permis à un projet qui pointe vers `127.0.0.1` | contrôle `Host` (403) + jeton (401), prouvés par la sonde (§5) |
| Codex non mesuré par ce développeur | la sonde de `tout.sh` le mesure pour chaque moteur avant le lot 1 |
| **Lot 1 trop gros** | découpé : **1a** serveur + jeton + page + vues existantes + « À toi de décider » + détail d'une demande ; **1b** livrables + versions (nouvelles sources : bibliothèque, git du dépôt, réglages `[equipes.<p>.versions]`) |
| Une maquette `.html` d'agent contient un script ou appelle un site | cadre isolé `sandbox` + CSP `default-src 'none'` servie avec le fichier ; test : un `.html` piégé (script, image distante, formulaire) ne s'exécute ni ne charge rien (en-têtes et attribut `sandbox` vérifiés) |
| Ouvrir un fichier hors des racines (`..`, lien, chemin absolu) | `id` opaque recherché dans la liste, liens ignorés, chemin résolu vérifié ; test avec des pièges |
| Versions fausses ou vieilles | chaque valeur porte sa source et son âge ; figé/échec comme les Sources ; « inconnu » plutôt que deviné |
| Les agents n'utilisent pas les nouveaux marquages (`⚠ Go attendu`, `❓ Question`, `Décision attendue`) | règle écrite dans `commun/REGLES.md` et les modèles ; la lecture de la fin de conversation reste en repli |
| L'écran en direct montre un texte sensible | panneaux de l'agent seulement, filtre de secrets ligne par ligne, lot 2 seulement |
| Un partage réseau figé bloque la vue `sante` | contrôle dans un sous-processus limité à 3 s, résultat « ne répond pas » |
| `http.server` est un serveur minimal | il n'écoute qu'en local, derrière jeton, ne sert que 3 fichiers et une table fixe ; aucune exposition directe |
| **Lot 1c** : le port écoute sur l'adresse de la VM | pare-feu de la VM (une seule source : SWAG) + filtre `sources` du serveur (403) + jeton (401) ; SWAG restreint au réseau interne et au VPN ; nom absent du DNS public |
| Adresse source de SWAG différente de son adresse de destination (traduction pare-feu réseau) | mesurée sur la première requête (journal du serveur, adresse du pair) avant d'être déclarée ; jamais supposée |
| Un processus de la VM hors bac à sable joint le port par `lo` (agent `mur = ouvert`, service) | filtre `sources` puis jeton ; agents en mur strict mesurés par la sonde (Claude et Codex, `127.0.0.1` et adresse de la VM) |
| SWAG → VM en HTTP en clair sur le réseau interne (cookie et jeton y passent) | TLS jusqu'à la VM, inclus dans le 1c (§6 ter, point 7) : certificat interne vérifié par SWAG |
| Certificat interne expiré : SWAG refuse de relayer, la page ne répond plus | durée 397 jours, alerte claire dès 30 jours avant (journal du service, `berger interface lien`), renouvellement en une commande ; retour arrière en HTTP |
| En-têtes `X-Forwarded-*` forgés | jamais lus ; testé |
| Lien d'entrée ouvert sur un téléphone | même jeton, même cookie ; `berger interface lien --nouveau` ferme toutes les sessions (téléphone perdu) |

## 8. Sources (seulement ce qui a été vérifié, 13/10/2026)

- Code du dépôt, lu : `bin/vues/*.py` (16 vues, `rendre`) ; `bin/berger` : `charger_vues`, `checklist`, `en_attente`,
  `validations`, `etat`, `suivi`, `cartes_tableau`, `alertes_synthese`, `depuis`, `decisions`, `documents_a_lire`,
  `lire_document` (marque lu), `installer`, motif `DOMAINE` / `equipe_domaine` ; `courtier/courtier` : `journal`
  (format de `appels.log`), `traiter_decisions` ; `tests/vues.py`, `tests/suites.sh`, `tests/pret.sh`,
  `tests/sonde-reseau.py`, `tests/tout.sh` (sondes par moteur) ; `systemd/berger-courtier.service`.
- Python 3.13.5 de la VM, vérifié par import et lecture des docstrings : `http.server.ThreadingHTTPServer`,
  `hmac.compare_digest` (« conçu pour empêcher l'analyse temporelle »), `secrets.token_urlsafe`.
- Mesures faites le 13/10 depuis le bac à sable de ce développeur (agent Claude, mur strict) : interfaces réseau,
  connexions directes et par le mandataire (§5) ; durée de démarrage de `bin/berger` (§4).
- Ajouts du 13/10 au soir, lus : `courtier/outils/_portes.py` (`inscrire_demande` : `resume[:1500]`, portes sans `par`
  ni `quand` ; `completer`, `precedence`) ; `courtier/outils/equipe_chef.py` (`relire`, `rejouer` qui ne garde pas
  son résultat, `renvoyer`) ; `courtier/courtier` `demander_validation` (champs d'une écriture en attente) ;
  `bin/berger` `BIBLIOTHEQUE`, `superviser` (`.supervision.json`), `question_en_attente` (Claude seul),
  `trace_installation` (format de `installations.log`), `tete_installation` ; `README.md` › Bibliothèque ;
  `config.exemple.toml` › `[equipes.*]`. `herdr pane read --help` (Herdr 0.9.3) : `--source visible`, `--format text`.
  Aucune mention de montage dans `bin/berger`, `README.md` ni `config.exemple.toml`.
- **Non cités, faute de vérification possible ici (pas d'accès Internet)** : les textes de la CNIL, de l'OWASP et la
  documentation des navigateurs (CSP, `SameSite`). Les choix du §5 sont les pratiques courantes ; une vérification de
  ces références par quelqu'un qui a l'accès est à faire avant de les citer.

## Découpage et refus

- **Lot 0** (sans rien de visible, en 2 ou 3 demandes de fusion) : `donnees()` + schémas + `berger vue/vues/etat/
  validations/document --json` + tests 1-3, 5-6, 9. Herdr inchangé, preuve octet pour octet (tests 6 et 9).
- **Lot 1a** : serveur + page en lecture seule + jeton + service + tests 4, 7, 8 et la sonde `sonde-interface.py` ;
  `decisions` enrichie et nouveaux marquages (§6.3) ; vues `validation` et `demande` et les champs ajoutés aux
  demandes (§6.4). Go du propriétaire requis (authentification).
- **Lot 1b** : vues `livrables` (§6.1) et `versions` (§6.2), cadre isolé, réglages `[equipes.<p>]`.
- **Lot 1c** (décidé le 14/10, AVANT le lot 2) : l'accès par `https://berger.<domaine interne>` derrière SWAG (§6 ter) —
  écoute et filtre `sources` déclarés, Host = `nom`, cookie `Secure`, `X-Forwarded-*` ignorés, sonde étendue à l'adresse
  de la VM ; TLS jusqu'à la VM (certificat interne) ; pare-feu de la VM par le propriétaire ; pare-feu réseau, site SWAG et
  DNS interne par l'exploitation.
- **Lot 2** (décidé le 13/10, fait APRÈS le 1c et AVANT le 1b) : les quatre actions du § « Lot 2 décidé », puis les vues `direct` et
  `sante` (§6 bis) + leurs tests. Toute action en plus : nouvelle spec courte.
- **Refusé par construction** : une règle métier dans `app.js` ou `interface.py` (ils ne connaissent ni fichier ni
  état) ; une écoute hors `127.0.0.1` ; une action hors de la table ; une vue sans schéma ; une dépendance à installer.
