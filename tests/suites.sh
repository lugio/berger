#!/usr/bin/env bash
# Les suites SANS MODÈLE de Berger (installation jetable, ni Herdr ni moteur) : une seule liste, deux usages —
#  - lue par tests/tout.sh (auto-test complet de l'installation) ;
#  - lancée seule : porte d'une COPIE de Berger (verify de l'équipe qui corrige Berger, 09/10/2026), sans config.toml.
# Usage : bash tests/suites.sh   (code de retour = nombre d'échecs)
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  B=$(cd "$(dirname "$0")/.." && pwd); ko=0; SEULES=1
  dire() { [ "$1" = ok ] || ko=$((ko+1)); printf '%-6s %s\n' "$1" "$4"; }
fi

# Dossiers temporaires des agents d'essai (tmp-par-agent, 14/10) : une racine jetable et COURTE (Claude refuse > 44 octets),
# jamais le vrai /tmp/bt ; dans un bac à sable (/tmp en lecture seule), aucune : `regenerer` le dit et continue.
# Donnée aux SEULES suites (tests/tout.sh inclut ce fichier : ses vrais agents gardent le vrai /tmp/bt), retirée à la fin.
_bt=$(mktemp -d /tmp/btXXXXXX 2>/dev/null) || _bt=""

# Raccourcis mise de la vraie maison (18/10/2026) : les suites posent un HOME JETABLE ; un raccourci mise lancé ainsi depuis un
# dossier sous la vraie maison échoue (« mise ERROR … config.toml are not trusted ») — y compris python3, donc le
# « #!/usr/bin/env python3 » de bin/berger : la porte tests du courtier était rouge pour toute branche, main compris.
# Chaque suite tourne donc sans les dossiers « …/mise/shims » dans son PATH, précédés d'un python3 qui EST l'interpréteur
# réel (résolu ici, avec le vrai HOME). Les vrais agents de tests/tout.sh gardent leur PATH (seul `suite` est concerné).
_py=$(python3 -c 'import os, sys; print(os.path.realpath(sys.executable))' 2>/dev/null)
_pyd=$(mktemp -d 2>/dev/null) && [ -n "$_py" ] && ln -s "$_py" "$_pyd/python3" || _pyd=""
_path_suites="${_pyd:+$_pyd:}$(tr ':' '\n' <<<"$PATH" | grep -v '/mise/shims/*$' | paste -sd:)"

# Herdr réel hors d'atteinte (fuite du 28/10/2026) : les développeurs et le rejeu tournent dans des panneaux Herdr et héritent de
# HERDR_SOCKET_PATH, XDG_CONFIG_HOME… ; une suite qui part de os.environ parlait au VRAI serveur (~80 espaces « P · un/deux/mdp/
# secr/pf » créés à chaque passage). Isolation POSITIVE, imposée à chaque suite : un faux Herdr (BERGER_HERDR → « false », donc
# socket_herdr() ne lit plus que BERGER_HERDR_SOCKET), un socket jetable absent, et HERDR_*, XDG_CONFIG_HOME, tout BERGER_HERDR_SOCKET
# hérité retirés. Une suite qui veut son propre faux Herdr le pose elle-même. Chaque suite l'impose aussi à son propre processus
# (tests/_herdr_isole.py : lancée seule, elle est isolée). Les RECETTES réelles (tests/tout.sh, tests/sonde-herdr*.py) restent
# connectées au vrai Herdr EXPRÈS : elles n'utilisent ni ce lanceur ni ce module. Contrôlé par tests/herdr-fuite.py.
_sans_herdr=(-u XDG_CONFIG_HOME -u BERGER_HERDR_SOCKET); while IFS= read -r _v; do _sans_herdr+=(-u "$_v"); done < <(compgen -e | grep '^HERDR_')
_faux_herdr=$(command -v false || echo /bin/false); _herdr_absent="/tmp/herdr-absent-$$.sock"

# Une suite de tests : réussie seulement si son CODE DE RETOUR est 0 (07/10 : « grep -c ^ok » passait dès qu'UN contrôle
# était bon — tests/installation.py rouge n'a pas été vu par tout.sh), puis on compte ses contrôles.
# Un contrôle « NON JOUÉ » (ce que l'environnement ne permet pas de prouver, ex. sous verify) est dit sur la ligne, jamais compté ok.
suite() {
  local out rc nj; out=$(env "${_sans_herdr[@]}" BERGER_HERDR="$_faux_herdr" BERGER_HERDR_SOCKET="$_herdr_absent" PATH="$_path_suites" BERGER_TMP_AGENTS=${_bt:-$BERGER_TMP_AGENTS} python3 "$B/tests/$1" 2>&1); rc=$?
  nj=$(grep -c '^NON JOUÉ' <<<"$out"); [ "$nj" = 0 ] && nj="" || nj=", $nj NON JOUÉ(S) : python3 tests/$1"
  # Suites unittest (« Ran N tests », pas de ligne « ok ») : leurs tests joués comptent (moins les sautés) ; une suite qui
  # ne joue rien est dite NON MESURÉE sur sa ligne (26/10 : « 0 contrôles » affiché pour des suites de 3 à 42 tests).
  local n ran saut; n=$(grep -c '^ok' <<<"$out"); ran=$(grep -oE '^Ran [0-9]+ tests?' <<<"$out" | grep -oE '[0-9]+' | tail -n 1)
  saut=$(grep -oE 'skipped=[0-9]+' <<<"$out" | grep -oE '[0-9]+' | tail -n 1)
  [ -n "$ran" ] && n=$((n + ran - ${saut:-0}))
  [ "$n" = 0 ] && nj="$nj, NON MESURÉE : aucun contrôle joué (python3 tests/$1)"
  if [ $rc = 0 ]; then dire ok - - "$2 : $n contrôles${ran:+ (dont ${ran} tests unittest${saut:+, $saut sautés})} $3$nj"
  else
    dire ÉCHEC - - "$2 : $(grep -c '^ÉCHEC' <<<"$out") échec(s), code $rc (python3 tests/$1)"
    # Garder la cause dans la porte externe, qui seule peut mesurer les sockets.
    local diagnostics
    diagnostics=$(grep -E '^ÉCHEC|^FAIL:|^ERROR:|^Traceback|^  File |^[[:alnum:]_.]*(Error|Exception):' <<<"$out")
    if [ -n "$diagnostics" ]; then printf '%s\n' "$diagnostics" | tail -n 40 | cut -c 1-1000
    else printf '%s\n' "$out" | tail -n 15 | cut -c 1-1000; fi
  fi
}


# SUITE_SEULE=<fichier> : cette suite seule (tests/shims-mise.py s'en sert pour jouer une sonde par `suite`, comme la porte)
if [ -n "$SUITE_SEULE" ] && [ -n "$SEULES" ]; then
  suite "$SUITE_SEULE" "suite seule" ""; [ -n "$_bt" ] && rm -rf "$_bt"; [ -n "$_pyd" ] && rm -rf "$_pyd"; exit $ko
fi
suite marques-produit.py "marques fixes du produit" "(dépôt et maison jetables, refus sans configuration privée)"
suite codex-ouverture.py "ouverture restreinte Codex" "(dialogue, invite, réception, réessai borné, argv privés, Claude inchangé)"
suite argv-herdr.py "messages Herdr privés" "(CLI réelle, argv du noyau, attente et refus)"
suite argv-config.py "configurations générées privées" "(dossier existant, liens refusés et nettoyage en échec)"
suite argv-cli.py "CLI privée complète" "(vraies fonctions Berger et moteurs simulés, fichiers système privés)"
suite argv-imbrique.py "appels internes privés" "(messages, missions, équipes, délégation, notifications et renvois)"
suite argv-shell.py "scripts privés hors des arguments" "(commandes, copies, piles, crochets et entrée indépendante)"
suite argv-client.py "client privé du courtier" "(stdin, fichier, droits, validation, liens et nettoyage)"
suite argv-connecteurs.py "curl sans contenu privé en arguments" "(GitHub et Dolibarr, transmission exacte)"
suite argv-prive.py "consignes non interactives sur stdin" "(deux moteurs, délégation et refus des contenus positionnels)"
suite outils.py "outils à commandes fixées" "(injections refusées, actions séparées)"
suite pages-publiques.py "outil pages_publiques" "(documents publics : liste blanche, redirections, taille, TLS vérifié, remise au seul demandeur, sans cookie)"
suite sql-lecture.py "outil sql_lecture" "(requêtes fixées, SELECT seul, paramètres liés, lignes et délai bornés, lecture seule, aucun secret)"
suite equipe.py "équipe de dev" "(demande de fusion, fusion, hooks, droits)"
suite contexte-appel.py "contexte propre à chaque appel du courtier" "(deux développeurs concurrents : SA copie, SON agent ; chaque outil à contexte, panneaux)"
suite equipe-verif.py "équipe : verify distant et conflits" "(verify par un outil du courtier, conflits entre demandes et avec main)"
suite processus-dev.py "processus de dév générique" "(4 portes : absentes, vertes, rouges, gate « non mesuré », pret obligatoire ; correctif : test et cause racine ; relecture qui rejoue et recompte ; fusion : pret rejouée, main avancée sans ou avec fichier commun ; étiquette SemVer et journal)"
suite chef-copie.py "branche de finition écrite dans la copie de travail du chef" "(importée en avance rapide seule puis poussée, demandée, fusionnée ; copie réécrite refusée ; copie_chef ; refus : hors dossier, lien, .git renvoyé, dépôt, forge, installation ; config piégée de la copie jamais exécutée, témoins)"
suite chef-finition.py "branche de finition du chef de projet" "(pousser et demander la fusion comme un développeur, au nom du chef ; fusion au propriétaire seul ; refus : principale, hors préfixe, .., tiret, espace, force, développeur ; hook piégé ; en-tête de journal avec un titre)"
suite equipe-ouverture.py "équipe : ouverture sûre" "(modèle refusé avant toute création, ports distincts en simultané)"
suite herdr-fuite.py "Herdr réel hors d'atteinte des suites" "(aucune variable HERDR_* transmise aux suites ; socket témoin héritée : aucune connexion, equipe-ouverture et regle-go)"
suite hierarchie-equipe.py "hiérarchie d'équipe" "(droits calculés depuis [equipes.*] : chef ouvre, suit, ferme ; coordinateur suit le chef ; rien vers un autre projet ; equipe:<projet> ignoré et signalé ; alertes en chaîne ; transition ; mission au chef vivant)"
suite finition-chef.py "finition par le chef de projet" "(finition = chef : livraison sans pret « à finir », porte rouge refusée, jamais fusionnée ; le chef la remplace seulement si sa branche contient le commit livré, origine gardée ; défaut inchangé)"
suite finition-soldee.py "finition soldée et relance après application" "(la fusion de la finition solde la livraison « à finir » reprise ; la supervision ne relance jamais une livraison reprise ou soldée, et solde au premier passage celle dont la finition a été fusionnée avant le correctif, hors limite de débit d'ecrire ; proposition appliquée : agent au repos relancé, occupé : relance en attente faite au repos, une seule fois)"
suite renommer.py "renommer un agent" "(l'espace Herdr suit le nom affiché, identifiant et dossier inchangés)"
suite regle-go.py "règle de go : rappels d'une demande renvoyée ou en attente" "(claude et codex : plus de rappel après « Terminé » écrit après le renvoi, une alerte au chef ; attente/reprendre du chef : refus, ni rappel ni fusion en attente ; go inscrit : equipe go, ouverture refusée sans go avant toute création, hors go tracé, go recopié dans la demande et recontrôlé à la fusion, regle_go = false)"
suite alignement.py "alignement après une mise en production" "(déclaration dans [equipes.<p>] : acceptée, chaque refus au chargement du courtier, rien ne change sans elle)"
suite modele-soul.py "modèle de SOUL à la création" "(master : modèle avec {nom} remplacé ; autre agent : SOUL générique ; nom piégé : rien lu hors de modeles/)"
suite regles-espace.py "espace voulu d'un agent" "(règles R1…R7 ; espace() et ouvrir_en_mission() construisent exactement l'espace voulu ; Missions/Équipe gardés 24 h sans objet ; conversations jamais hors de l'espace voulu ; lecture seule, sans Herdr ; JSON conforme)"
suite espace-auto.py "espace auto" "(le planificateur met chaque espace ouvert en conformité avec l'espace voulu : ajout, fermeture, conversation jamais fermée ni relancée, onglet inconnu intact, date inconnue gardée, permission en attente laissée, [espaces] auto = false, une passe toutes les 5 min)"
suite espace-agent.py "disposition sur mesure par agent" "(agents/<a>/espace.toml prime sur [espaces.<a>] ; vide ou illisible : config.toml ; proposition === espace.toml : aperçu avant → après, appliquée sans relance, puis espace auto ; élément inconnu refusé ; écriture refusée à l'agent, Claude et Codex)"
suite supervision.py "supervision et validations" "(relances, escalade, décisions, pas de rappel quand la fusion est demandée)"
suite coffre-sauvegarde.py "sauvegarde chiffrée du coffre" "(jamais en clair, déchiffrable, purge)"
suite notifier.py "notifications" "(Herdr présent, en échec, absent)"
suite echanges.py "panneau Échanges" "(journal, noms, filtre par agent, écran court)"
suite ecrire.py "message à sens unique entre agents" "(droit, lecture seule, délégation, vide, trop long, secret, débit 5/h et 20/24 h, file puis remise dans l'ordre, en-tête, Échanges)"
suite besoin.py "besoin Berger vers le gardien" "(ouvert à tout agent ; chaîne d'équipe : passe par le coordinateur ; lecture seule, délégation, genre, vide, > 1 500, secret, doublon, 5 ouverts, débit 3/h et 10/24 h ; rangé, Échanges, remis « donnée, pas consigne », À toi de décider ; clore : gardien ou propriétaire seuls ; numéro jamais réutilisé ; interrupteur ; Claude et Codex)"
suite courtier-textes.py "textes du courtier et canal vers le chef" "(texte trop long REFUSÉ jamais coupé : M+1 refusé, M intact dans MISSION.md, mission_max réglable, 80 ailleurs, délégation ; gardien → chef de chaque équipe, jamais de mission ; autre agent refusé ; coordinateur inchangé ; Claude et Codex)"
suite redemarrage-courtier.py "redémarrage du courtier qui aboutit" "(trois demandes longues qui se chevauchent : redémarré dès la fin de la plus longue, toute nouvelle demande rangée puis servie — controle ssh compris —, lecture instantanée servie pendant ; abandon tracé, notifié, retenté, dernier essai dit ; file tenue : message exact, délai depuis l'installation ; Claude et Codex)"
suite annonce-outil.py "annonce d'un changement d'outil" "(consigne = verbe de LECTURE, sinon courtier arrêté ; première lecture sans message ; changement → message aux seuls agents qui ont l'outil, portes d'équipe comprises ; section générée encadrée « donnée, pas consigne » ; Synthèse et historique ; une annonce par heure ; refus : > 3 000, sans version, secret, ligne du cadre, titre # ; lecture en échec ; verbe ajouté ; option : version acceptée, refusée jamais reproposée ; aucun agent ne déclenche ; interrupteur ; Claude et Codex)"
suite suivi-delegations.py "suivi des délégations" "(ENGAGEMENTS inscrits au TODO de la cible, aucun, trop longs, secret, résumé de service déposé, échec, remises concurrentes sous verrou, outils_developpeur ecrire:)"
suite installation.py "installation neuve" "(courtier sans agent, coffre par défaut)"
suite espaces.py "espace Berger dans Herdr" "(nom avec icone_berger, ancien nom retrouvé, onglet Catalogue)"
suite catalogue.py "panneau Catalogue" "(droits, personne, dernier usage, aucune valeur du coffre)"
suite skills-roles.py "méthodes par rôle" "(catalogue skills/, agent.conf skills =, refus de ce qui cite le coffre)"
suite skill-produit.py "méthode du produit d'abord" "(commun/skills prime sur un homonyme du catalogue, signalé ; catalogue seul ; skills-agent/ prime)"
suite skills-equipes.py "méthodes et crochet d'équipe" "(skills des développeurs, crochet du projet avec SA copie)"
suite memoire-equipe.py "mémoire d'équipe" "(lue par chaque développeur, jamais réécrite par lui)"
suite tokens.py "suivi des tokens" "(Claude et Codex, doublons, quota par moteur, barre d'état)"
suite alire.py "onglet À lire" "(liste, lus, modifiés, liens ignorés, Accueil)"
suite contrat-noyau.py "contrat du noyau" "(vues, moteurs et familles de commandes sur l'API seule, frontière à l'exécution, module cassé ou en doublon écarté et nommé)"
suite commandes-couverture.py "couverture des commandes" "(les 60 verbes figés = l'union des familles de bin/commandes/ (2 déplacés, 58 inscrits par la transition), une aide et des droits par verbe, aucun doublon, tableau du manuel, entrée privée déclarée, verbe inconnu inchangé)"
suite taille-fichiers.py "taille des fichiers" "(1 500 lignes, cliquet de bin/berger)"
suite missions.py "agents de mission en lecture seule" "(écriture, mission, délégation, décision refusées ; lecture permise)"
suite affichage.py "affichage des panneaux" "(jamais de débordement, écran séparé, terminal rendu propre)"
suite synthese.py "onglets Synthèse et Sources" "(rouge et jaune seulement, collecte en échec dite, secrets bloqués)"
suite tableau.py "onglet Tableau" "(colonnes, cartes sans doublon)"
suite decisions.py "onglets Décisions et Checklists" "(question laissée, validations, cases restantes, onglets rangés)"
suite reprise.py "reprise après redémarrage" "(agents dans leur conversation, panneaux relancés)"
suite abonnement.py "abonnement Claude" "(type et palier écrits, rien d'autre touché)"
suite appelant.py "appelant nommé à la passerelle" "(en-tête au nom de l'agent, 4 murs, réglages gardés)"
suite auto-test-nuit.py "auto-test de nuit" "(verrou, résultat rouge si échec ou plus de 26 h)"
suite consignes-canari.py "ligne témoin des consignes personnelles de Claude" "(choix : exclusion par dossier agent, skills, commun, import, espaces, longueur, fichier absent ; comparaison : exacte, espaces, ABSENT, vide ; jamais affichée)"
suite coherences-vps.py "cohérences VPS" "(accès de délégation, refus des gardes, horaires, JSON et fermeture après refus propriétaire)"
suite roles.py "panneaux selon le rôle des agents" "(à côté de l'agent, onglets propres, reprise, sources et checklists filtrées)"
suite commandes.py "commandes sans test jusqu'ici" "(reveil, tache, planificateur, relancer, fin-mission, restaurer : faux moteurs, faux Herdr, faux trousseau)"
suite proteges.py "parties protégées d'un agent" "(proteges : Claude refus d'édition + denyWrite, Codex read, chemins refusés ou absents nommés)"
suite memoire.py "validation de la mémoire" "(porte de perte, sauvegarde avant, proposition retirée, mémoire externe)"
suite vues.py "vues en modules (bin/vues/)" "(contrat de chaque vue, onglets et icônes déduits, vue piégée écartée et nommée)"
suite vues-herdr.py "vues Herdr avant captures" "(largeurs, attentes communes, résolutions explicites et refus regroupés)"
suite demo-vues.py "démonstration fictive des vues" "(deux installations isolées, rendus reproductibles à 80 et 140 colonnes)"
suite interface-serveur.py "serveur de l'interface web" "(lien et jeton, 127.0.0.1 seulement, 401 sans jeton, cookie dérivé HttpOnly SameSite=Strict, Host vérifié, données = berger vue --json, pièges refusés, lecture seule, en-têtes stricts, journal sans paramètres, délai et charge bornés, page sans ressource extérieure)"
suite interface.py "données des vues (interface)" "(schéma par vue, données conformes, chaque champ produit et affichable, texte de Herdr identique octet pour octet, texte = f(données), vue piégée écartée)"
suite livrables.py "vues Livrables et Documents (interface)" "(un seul lister : commun, projets, travail, À lire, branches en cours ; ignorés ; Livrables = filtre ; --brut au genre vérifié par signature ; .html à origine opaque et sans réseau ; pdf et images inline avec leur type et nosniff ; le reste téléchargé ; preuve navigateur)"
suite temps-reel.py "temps réel de l'interface (SSE)" "(écriture en attente visible en moins de 2 s, checklist d'un agent Claude et d'un agent Codex ; aucun événement sans changement ; 9e flux refusé proprement ; veille morte → flux fermé puis reprise ; veille arrêtée sans flux ; appels.log sans flot de signaux ; battement)"
suite alire-se-vide.py "À lire qui se vide" "(note « Lié à : » d'un agent Claude et d'un agent Codex : lue quand l'écriture est décidée ou la demande fusionnée ; en cours ou sans lien : reste ; jamais supprimée ; quitte À toi de décider)"
suite ecrire-aussi.py "ecrire_aussi" "(un fichier inscriptible sans être pris pour un dossier)"
suite bibliotheque.py "bibliothèque (lot 2)" "(dossier de travail à soi, masqué aux autres, commun lu jamais écrit, Claude et Codex)"
suite cles-parlantes.py "clés parlantes du coffre" "(jeton, mot de passe, mdp, secret retenus par le filtre et l'audit)"
suite bibliotheque-projets.py "bibliothèque (lot 4)" "(projets d'équipe : ouverture validée, membres seuls, partage filtré, fermeture archivée, Claude et Codex)"
suite validation-fait.py "résultat d'une validation" "(action qui redémarre le courtier : résultat inscrit avant le redémarrage ; décision sur une validation déjà faite refusée ; action coupée jamais rejouée)"
suite validation-a-part.py "validations exécutées à part" "(lecture servie < 2 s pendant une exécution, panneau collecté ; une à la fois, dans l'ordre des décisions ; arrêt net : jamais rejouée ; installation : file tenue jusqu'au redémarrage, HEAD revenu, garde-fou notifié une fois ; exécuteur mort : courtier arrêté)"
suite moins-validations.py "moins de validations" "(relancer au repos seulement, sans validation ; --force du propriétaire tracé ; etiqueter sans validation sur une fusion validée ; fusion de Berger → installation seule ; installer : retour arrière automatique prouvé ; résumé de fusion avec les portes de la demande)"
suite domaines.py "sites permis par projet" "(liste stricte par --settings et protégée, deny-all sinon, motif exact, validée par le superviseur, Codex sans réseau)"
suite tmp-par-agent.py "dossier temporaire par agent" "(CLAUDE_CODE_TMPDIR dans les réglages ET dans l’environnement de chaque lancement — exec, claude -p, Herdr —, commun et autres refusés en lecture et écriture, Claude et Codex, 700, relais réseau non couvert, > 44 octets ou dossier douteux : lancement refusé, mur ouvert inchangé)"
suite anti-boucle.py "garde-fou anti-boucle" "(même appel refusé au-delà de boucle_max par heure sans sollicitation, gardien prévenu une fois, Synthèse, appels espacés ou différents acceptés, interrupteur ; relance d’un agent occupé seulement si boucle repérée et rien depuis inactif_min, un agent occupé sans boucle jamais relancé ; règle dans REGLES et le skill ; neutre au moteur)"
suite superviseur.py "agent superviseur" "(lit les autres agents, n'y écrit pas, coffre et sources illisibles, Claude et Codex)"
suite equipe-berger.py "équipe qui corrige Berger" "(jamais l'installation pour dépôt ; forge locale : publier et synchroniser en avance rapide seule, jamais de force)"
suite vitrine-readme.py "README bilingues et schémas générés" "(structure, liens, badges, logo choisi et génération déterministe)"
suite communaute-porte.py "porte communautaire légère" "(aucun rejeu, trente contrôles conservés, témoins de fichiers invalides)"
suite communaute.py "fichiers communautaires" "(contribution, modèles, CI et lanceur du clone frais)"
suite vitrine.py "vitrine documentaire" "(manuel conservé, matrice exhaustive, liens locaux, liste blanche et verifier-depot jetable)"
suite installer-master.py "doc : installer le Master" "(blocs de config.exemple.toml lisibles en TOML avec les clés citées, chaque commande berger citée existe)"
suite agent-appliquer.py "créer ou modifier un agent sur proposition" "(droits avant → après, empreinte, sauvegarde, refus même validés)"
suite verbe-prod.py "verbe prod (script serveur)" "(prérequis et disque contrôlés tôt, étiquette de main seule, sauvegarde relue en flux, chiffrée pour la clé publique seule et contrôlée sinon refus, essai à blanc, migrations SQL jouées et inscrites (transaction unique ou BEGIN propre, applied_by, apostrophe refusée), avant/apres, controles_sante (retour arrière), branche principale sans HEAD détachée, santé, retour arrière sans toucher la base, ssh coupée en pleine construction, verrou, journal, ssh forcé ; courtier : chef validé, développeur refusé)"
suite mcp-trous.py "trous MCP des agents strict" "(Claude : --strict-mcp-config et ENABLE_CLAUDEAI_MCP_SERVERS=false à chaque lancement ; Codex : apps, plugins, remote_plugin, skill_mcp_dependency_install, tool_suggest coupés ; .mcp.json, .claude/settings*.json, .codex/ en lecture seule ; moteur non admis : bascule, rouge, refus si aucun ; mur ouvert inchangé)"
suite mcp.py "serveurs MCP par berger-mcp" "(configs : berger-mcp seul, Claude --mcp-config, Codex approuvé pour CE serveur, rien sans mcp = ; refus § 3 ; relais : protocole, journal sans valeur, filtre coffre/clé/notification, débit, taille ; enveloppe : coffre, autre agent, réseau, écriture, env vidé ; bwrap absent ou en échec : rien ; socket relais ↔ courtier)"
suite web-relais.py "remise de rapport web sans mission réelle" "(validation propriétaire, snapshot, secrets, liens, scope, dépôt exclusif, mission chef et reçu)"
suite web-relais-mission.py "attribution exclusive des missions" "(deux appels concurrents, aucun écrasement ni effet doublé)"
suite web-connecter.py "connexion propriétaire sans réseau" "(lease unique, révocation, profils privés, faux Playwright headful, POST propriétaire seul)"
suite web-profils-masques.py "masques des profils web" "(parent effectif créé avant enveloppe, coffre par défaut, chemins externes)"
suite web-session.py "coffre des sessions web" "(coffre temporaire, sauvegarde simulée, identité, cookies, rétention)"
suite web-security-review.py "régressions de la revue de sécurité web" "(méthodes détournées avant Cookie, échéances indépendantes, aperçu absent des argv et cookies courts)"
suite web-session-proxy.py "session prêtée au proxy" "(flux sans socket, Cookie TLS, lecture seule, Set-Cookie, cycle et nettoyage, filtre)"
suite web-https.py "HTTPS contrôlé" "(TLS réel, méthodes, Host, corps, chemins et certificat par accès)"
suite web.py "accès web d'un agent (proxy et cycle)" "(proxy : nom permis, autre nom, IP, adresse privée après résolution, redirection hors de l'accès, méthode, corps > 64 Ko refusés et journalisés, sans paramètres d'URL ; CONNECT tunnelé ; socket UNIX ; cycle : demande validée par le propriétaire seul, --duree 24 h au plus, un accès à la fois, prolongation, refus, expiration, échéance, berger web fermer, redémarrage)"
suite contrat-session.py "contrat de session sans réseau" "(doubles, témoins obligatoires, DOM, statut TLS, fuite/refus/échéance, nettoyage et publics restaurés)"
suite contrat-web.py "contrat web : témoins navigateur, Host et tunnels" "(régressions de la revue)"
suite contrat-socket.py "contrôle (6) du contrat, hors moteur" "(connect() vers un socket témoin qui écoute hors bac à sable, vu par l'agent ; création en information ; témoin connecté ; socket retiré, reprise sûre)"
suite shims-mise.py "suites sous un HOME jetable" "(raccourcis mise de la vraie maison retirés du PATH des suites, python3 réel : bin/berger démarre par son shebang ; témoin rouge sans)"

[ -n "$_bt" ] && rm -rf "$_bt"; [ -n "$_pyd" ] && rm -rf "$_pyd"
if [ -n "$SEULES" ]; then echo "==== $ko échec(s)"; exit $ko; fi
