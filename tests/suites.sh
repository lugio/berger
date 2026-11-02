#!/usr/bin/env bash
# Les suites SANS MODÈLE de Berger (installation jetable, ni Herdr ni moteur) : une seule liste, deux usages —
#  - lue par tests/tout.sh (auto-test complet de l'installation) ;
#  - lancée seule : porte d'une COPIE de Berger (verify de l'équipe qui corrige Berger, 09/10/2026), sans config.toml.
# Usage : bash tests/suites.sh   (code de retour = nombre d'échecs)
# PARALLÈLE (28/10/2026) : BERGER_SUITES_PARALLELE=<n> suites à la fois (1 par défaut = une par une ; seuls 1 à 4 sont acceptés, le reste est refusé et ramené à 1 : RAM de 15 Go). Chaque suite
# tourne dans son propre processus, sa propre installation jetable (elle la crée elle-même : mktemp / TemporaryDirectory, ports 0)
# et SON dossier BERGER_TMP_AGENTS ; la sortie de chacune est gardée à part puis rendue DANS L'ORDRE de la liste ci-dessous, avec
# les mêmes lignes de verdict qu'une passe séquentielle. BERGER_SUITES_DUREES=<fichier> y écrit la durée de chaque suite, BERGER_SUITES_MEM=<fichier> son pic de mémoire (tests/_mesure_mem.py).
# VERROU GLOBAL (flock) : un seul suites.sh à la fois sur la machine ; BERGER_SUITE_DELAI (1200 s) borne chaque suite.
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

# Suites qui ne se jouent PAS en parallèle des autres : jouées SEULES (rien d'autre ne tourne pendant ce temps), LANCÉES EN DERNIER
# (pour ne rien bloquer), leur verdict rendu à leur place dans la liste. Chaque suite a son installation, ses ports (0 = libre) et son
# temporaire jetables : la seule raison d'être « à part » est un chronométrage serré qu'une machine chargée fausse.
declare -A _a_part=()
_a_part[redemarrage-courtier.py]="délais mesurés à la seconde (réponse < 5 s, redémarrage < 8 s, attentes bornées à 8 s) : rouge au hasard dès que la machine est chargée (28/10/2026, deuxième passe parallèle)"
_a_part[temps-reel.py]="flux temps réel : reprise attendue en 2 s après une veille tuée, rouge au hasard sous charge (28/10/2026, load 24 des autres agents) ; assertion inchangée"
# Délai maximal propre à une suite (secondes), quand BERGER_SUITE_DELAI (1200) ne convient pas : _delai_suite[fichier]=secondes.
declare -A _delai_suite=()
# Suites LANCÉES EN PREMIER (la plus longue ne doit pas démarrer en queue de passe ; aucune aujourd'hui : herdr-fuite.py ne rejoue plus les autres) ; leurs
# verdicts restent rendus à leur place dans la liste.
_en_tete=()

# Une suite de tests : réussie seulement si son CODE DE RETOUR est 0 (07/10 : « grep -c ^ok » passait dès qu'UN contrôle
# était bon — tests/installation.py rouge n'a pas été vu par tout.sh), puis on compte ses contrôles.
# Un contrôle « NON JOUÉ » (ce que l'environnement ne permet pas de prouver, ex. sous verify) est dit sur la ligne, jamais compté ok.
# `suite` DÉCLARE (fichier, titre, détail) ; _jouer_les_suites (fin du fichier) les lance, N à la fois, et rend les verdicts dans l'ordre.
_sf=(); _st=(); _sd=(); _rouges=(); _rouges_diag=()
suite() { _sf+=("$1"); _st+=("$2"); _sd+=("$3"); }

# Lance la suite n° $1 (processus à part) : sortie, code de retour et durée sous $_res/$1, « fin » écrit en dernier.
# BERGER_SUITES_MEM=<fichier> : mesure de sa mémoire (tests/_mesure_mem.py). Le descripteur du verrou global n'est transmis à PERSONNE : ce _jouer le
# ferme d'abord, donc ni lui, ni la suite, ni un orphelin ne gardent le verrou si le lanceur meurt. Chaque suite porte BERGER_SUITE_MARQUE=<lanceur>-<n°> dans son
# environnement (hérité par tous ses descendants, même d'une autre session) : à sa fin, ou si le lanceur meurt (veille : SIGKILL ne se rattrape pas
# autrement), tout ce qui porte la marque est tué (tests/_tuer_marque.py).
# Le processus $1 existe et n'est ni zombie ni mort : un lanceur tué mais pas encore « attendu » par son parent reste visible à `kill -0`, et la veille
# qui l'attendait gardait les tuyaux du parent ouverts (le parent, en attente de leur fin, ne l'« attendait » jamais : blocage vu le 29/10).
_vivant() { kill -0 "$1" 2>/dev/null && ! grep -qE '^State:[[:space:]]*[ZX]' "/proc/$1/status" 2>/dev/null; }
_fermer_verrou() { [ -n "$_verrou_fd" ] && eval "exec $_verrou_fd>&-"; return 0; }
_tuer_marque() { [ -e "$B/tests/_tuer_marque.py" ] && ( _fermer_verrou; exec "${_py:-python3}" "$B/tests/_tuer_marque.py" "$1" >/dev/null 2>&1 ); return 0; }
_jouer() {
  local i=$1 f=${_sf[$1]} d="$_res/$1" t0=$EPOCHREALTIME rc bt=$BERGER_TMP_AGENTS cmd marque="$$-$1" cp gw
  _fermer_verrou
  set -m        # contrôle des tâches DANS ce sous-processus : la suite, lancée en arrière-plan, garde SIGINT par défaut et son stdin (tests/argv-client.py l'interrompt)
  cmd=(python3 "$B/tests/$f"); [ -n "$BERGER_SUITES_MEM" ] && cmd=(python3 "$B/tests/_mesure_mem.py" "$BERGER_SUITES_MEM" "$f" -- "${cmd[@]}")
  mkdir -p "$d"; [ -n "$_bt" ] && { bt="$_bt/$i"; mkdir -m 700 "$bt"; }      # un dossier temporaire d'agents PAR suite (700, comme celui de mktemp : l'agent refuse un autre mode)
  local herdr=(BERGER_HERDR="$_faux_herdr" BERGER_HERDR_SOCKET="${_herdr_absent%.sock}-$i.sock")      # sans témoins : faux Herdr imposé par le lanceur
  [ -n "$_temoins_racine" ] && herdr=(HERDR_SOCKET_PATH="$_temoins_racine/h-$i.sock" HERDR_PANE_ID=pane-temoin HERDR_WORKSPACE_ID=espace-temoin HERDR_ENV=1
    XDG_CONFIG_HOME="$_temoins_racine/x-$i" BERGER_HERDR_SOCKET="$_temoins_racine/b-$i.sock" BERGER_HERDR="$(command -v true)" HOME="$_temoins_racine/m-$i")   # HOSTILE : tout mène à un témoin
  ( while _vivant $$; do sleep 1; done; _tuer_marque "$marque" ) & gw=$!       # veille : le lanceur ($$) est mort → pas d'orphelin
  env "${_sans_herdr[@]}" "${herdr[@]}" PATH="$_path_suites" BERGER_TMP_AGENTS="$bt" BERGER_SUITE_MARQUE="$marque" "${cmd[@]}" >"$d/sortie" 2>&1 & cp=$!
  wait "$cp"; rc=$?
  kill "$gw" 2>/dev/null; wait "$gw" 2>/dev/null
  _tuer_marque "$marque"                                                   # descendants restés derrière la suite
  echo $rc >"$d/rc"; echo "$(( 10#${EPOCHREALTIME//[.,]/} - 10#${t0//[.,]/} ))" >"$d/us"; : >"$d/fin"
}

# Clôture la suite n° $1 de force (délai dépassé, processus mort sans « fin ») : code $2, raison $3 dans sa sortie, comptée en échec.
_forcer_fin() {
  local d="$_res/$1"; _tuer_marque "$$-$1"; mkdir -p "$d"; echo "ÉCHEC $3" >>"$d/sortie"; echo "$2" >"$d/rc"; echo "$(( (SECONDS - ${_debut[$1]:-$SECONDS}) * 1000000 ))" >"$d/us"; : >"$d/fin"
}

# TERM au groupe de processus du PID $1 (la suite et ses descendants), courte attente, puis KILL.
_tuer_groupe() { kill -TERM -- "-$1" 2>/dev/null; sleep 2; kill -KILL -- "-$1" 2>/dev/null; }

# Verdict de la suite n° $1, à partir de sa sortie gardée (même texte qu'avant le parallélisme).
_rapporter() {
  local i=$1 f=${_sf[$1]} out rc nj; out=$(<"$_res/$1/sortie"); rc=$(<"$_res/$1/rc")
  [ -n "$BERGER_SUITES_DUREES" ] && printf '%s\t%s\n' "$(( $(<"$_res/$1/us") / 1000 ))" "$f" >>"$BERGER_SUITES_DUREES"
  nj=$(grep -c '^NON JOUÉ' <<<"$out"); [ "$nj" = 0 ] && nj="" || nj=", $nj NON JOUÉ(S) : python3 tests/$f"
  # Suites unittest (« Ran N tests », pas de ligne « ok ») : leurs tests joués comptent (moins les sautés) ; une suite qui
  # ne joue rien est dite NON MESURÉE sur sa ligne (26/10 : « 0 contrôles » affiché pour des suites de 3 à 42 tests).
  local n ran saut; n=$(grep -c '^ok' <<<"$out"); ran=$(grep -oE '^Ran [0-9]+ tests?' <<<"$out" | grep -oE '[0-9]+' | tail -n 1)
  saut=$(grep -oE 'skipped=[0-9]+' <<<"$out" | grep -oE '[0-9]+' | tail -n 1)
  [ -n "$ran" ] && n=$((n + ran - ${saut:-0}))
  [ "$n" = 0 ] && nj="$nj, NON MESURÉE : aucun contrôle joué (python3 tests/$f)"
  if [ $rc = 0 ]; then dire ok - - "${_st[$i]} : $n contrôles${ran:+ (dont ${ran} tests unittest${saut:+, $saut sautés})} ${_sd[$i]}$nj"
  else
    dire ÉCHEC - - "${_st[$i]} : $(grep -c '^ÉCHEC' <<<"$out") échec(s), code $rc (python3 tests/$f)"; _rouges+=("$f")
    # Garder la cause dans la porte externe, qui seule peut mesurer les sockets.
    local diagnostics
    diagnostics=$(grep -E '^ÉCHEC|^FAIL:|^ERROR:|^Traceback|^  File |^[[:alnum:]_.]*(Error|Exception):' <<<"$out")
    if [ -n "$diagnostics" ]; then diagnostics=$(printf '%s\n' "$diagnostics" | tail -n 40 | cut -c 1-1000)
    else diagnostics=$(printf '%s\n' "$out" | tail -n 15 | cut -c 1-1000); fi
    printf '%s\n' "$diagnostics"; _rouges_diag+=("$f :"$'\n'"$(tail -n 8 <<<"$diagnostics")")     # rappelé en fin de passe : la porte ne garde que les dernières lignes
  fi
}

# Nombre de suites à la fois : BERGER_SUITES_PARALLELE s'il vaut 1, 2, 3 ou 4 ; absent ou vide, 1 ; toute autre valeur (0, négatif, texte, énorme…)
# est REFUSÉE par un message nommé et ramenée à 1. Même règle dans tests/_parallele.py (rejeu de la sonde de herdr-fuite.py), vérifiée par tests/parallele-memoire.py.
_parallele_choisi() {
  local v=${BERGER_SUITES_PARALLELE-}
  case $v in
    ""|1|2|3|4) echo "${v:-1}";;
    *) echo "BERGER_SUITES_PARALLELE=« ${v:0:40} » refusé : un entier de 1 à 4 est attendu, 1 utilisé" >&2; echo 1;;
  esac
}
# Verrou GLOBAL : un seul suites.sh à la fois sur la machine, toutes copies et toutes portes confondues. Chaque porte a son /tmp privé (tmpfs de
# bubblewrap) : un fichier de verrou DANS /tmp serait un autre fichier pour chaque porte. Un flock verrouille l'INODE, pas le chemin, et se prend sur un
# descripteur ouvert en LECTURE SEULE : on verrouille donc un fichier qui existe déjà et que toutes les portes voient (--ro-bind / /). Lequel : le fichier
# « description » du dépôt d'origine (remote.origin.url, forge locale) — créé une fois par `git init --bare` et JAMAIS réécrit ensuite (push, fetch, gc,
# config, symbolic-ref le laissent intact : prouvé par tests/parallele-memoire.py), alors que HEAD et config sont réécrits par renommage, donc un NOUVEL
# inode qui casserait le verrou sans bruit. Forge locale sans ce fichier, ou fichier non verrouillable : passe NON JOUÉE, jamais un repli qui ne
# sérialiserait rien. Seul un dépôt sans forge locale (clone public, sans remote) a un verrou /tmp, dit à l'écran : il n'est pas dans une porte de Berger.
# $BERGER_SUITES_VERROU (fichier existant) remplace le choix (tests). Le suivant attend son tour (message ; BERGER_SUITES_ATTENTE secondes, 600 par
# défaut) puis s'arrête SANS verdict. Le lanceur qui le tient l'indique à ses descendants (BERGER_SUITES_VERROU_TENU) : une suite seule jouée par une suite
# ne se bloque pas elle-même. Le descripteur du verrou est ALLOUÉ (exec {_verrou_fd}) : tests/tout.sh, qui inclut ce fichier, tient déjà le 9 (.tout.verrou). Il n'est transmis à aucun processus de suite (voir _jouer) : tué par SIGKILL, le lanceur libère le verrou.
# _verrou_chemin affiche le chemin ; code 0 = fichier partagé, 2 = verrou /tmp (aucune origine locale), 1 = introuvable (origine locale sans fichier).
# Développeur, chef et courtier doivent résoudre le MÊME fichier : le rejeu du chef est un clone `--shared` de SON dépôt de travail (origine = ce dépôt,
# lui-même cloné de la forge) ; on remonte donc d'origine en origine (puis les alternates, à défaut d'origine) jusqu'au dépôt NU (core.bare), de six
# maillons au plus (une boucle ou une chaîne plus longue = introuvable). Une origine locale (chemin ou file://) qui ne mène pas à une description
# verrouillable = introuvable, jamais le verrou /tmp, réservé à l'absence de toute origine locale (https, ssh, aucune).
_verrou_depot_nu() {          # $1 = dépôt de départ ; affiche le dépôt nu de la forge ; code 0 trouvé, 1 introuvable, 2 aucune origine locale
  local d=$1 n=0 o a g
  while [ $n -lt 6 ]; do
    n=$((n+1))
    [ -d "$d" ] || return 1
    [ "$(git -C "$d" rev-parse --is-bare-repository 2>/dev/null)" = true ] && { echo "$d"; return 0; }
    o=$(git -C "$d" config --get remote.origin.url 2>/dev/null); o=${o#file://}
    if [ -z "$o" ]; then                                                           # sans origine : les alternates (clone --shared) mènent au dépôt source
      g=$(git -C "$d" rev-parse --absolute-git-dir 2>/dev/null) || return 1
      a=$(head -n 1 "$g/objects/info/alternates" 2>/dev/null)
      [ -z "$a" ] && { [ $n = 1 ] && return 2; return 1; }
      case $a in /*) ;; *) a="$g/objects/$a";; esac
      d=$(cd "$a/.." 2>/dev/null && pwd) || return 1; continue
    fi
    case $o in
      /*) d=$o;;
      [A-Za-z]*://*|[!/.]*:*) [ $n = 1 ] && return 2; return 1;;                  # URL distante : pas une forge locale
      *) d="$d/$o";;
    esac
  done
  return 1
}
_verrou_chemin() {
  local nu k
  if [ -n "$BERGER_SUITES_VERROU" ]; then echo "$BERGER_SUITES_VERROU"; [ -f "$BERGER_SUITES_VERROU" ] && return 0; return 1; fi
  nu=$(_verrou_depot_nu "$B"); k=$?
  if [ $k = 0 ]; then
    echo "$nu/description"; [ -f "$nu/description" ] && [ ! -L "$nu/description" ] && return 0; return 1
  fi
  if [ $k = 2 ]; then
    echo "suites.sh : dépôt sans forge locale (clone public) : verrou /tmp, propre à cette machine seulement" >&2
    echo "/tmp/berger-suites-$(id -u).lock"; return 2
  fi
  echo "(forge locale introuvable depuis $B)"; return 1
}
_verrou_global() {
  [ -n "$BERGER_SUITES_VERROU_TENU" ] && return 0
  local v k rc w=${BERGER_SUITES_ATTENTE:-600}
  v=$(_verrou_chemin); k=$?
  [[ "$w" =~ ^[0-9]{1,5}$ ]] || w=600
  command -v flock >/dev/null || { echo "suites.sh : flock absent, verrou global impossible : passe NON JOUÉE" >&2; return 1; }
  [ $k = 1 ] && { echo "suites.sh : fichier de verrou introuvable ($v) : passe NON JOUÉE (aucun repli qui ne sérialiserait rien)" >&2; return 1; }
  if [ -e "$v" ]; then { exec {_verrou_fd}<"$v"; } 2>/dev/null || { echo "suites.sh : verrou $v illisible : passe NON JOUÉE" >&2; return 1; }
  else { exec {_verrou_fd}>>"$v"; } 2>/dev/null || { echo "suites.sh : verrou $v impossible à créer : passe NON JOUÉE" >&2; return 1; }; fi
  flock -n -E 75 "$_verrou_fd"; rc=$?
  if [ $rc = 75 ]; then
    echo "suites.sh : une autre passe de tests tient le verrou ($v) ; j'attends mon tour (au plus $w s)" >&2
    flock -w "$w" -E 76 "$_verrou_fd"; rc=$?
    [ $rc = 76 ] && { echo "suites.sh : verrou toujours pris après $w s : passe NON JOUÉE (aucun verdict)" >&2; _fermer_verrou; return 1; }
  fi
  [ $rc = 0 ] || { echo "suites.sh : verrou $v non verrouillable : passe NON JOUÉE" >&2; _fermer_verrou; return 1; }
  export BERGER_SUITES_VERROU_TENU=1
}
# Preuve « Herdr réel hors d'atteinte » sur TOUTES les suites (29/10/2026, en remplacement du rejeu complet de herdr-fuite.py : chaque suite ne tourne
# qu'UNE fois). Chaque suite est jouée à son passage normal dans un environnement HOSTILE : les quatre chemins par lesquels elle pourrait joindre Herdr
# (HERDR_SOCKET_PATH, XDG_CONFIG_HOME/herdr/herdr.sock, BERGER_HERDR_SOCKET hérité, repli HOME/.config/herdr/herdr.sock d'un HOME jetable) mènent à
# des sockets TÉMOINS qui écoutent (tests/_temoins.py), un par suite ; son isolation propre (tests/_herdr_isole.py) doit les éviter. Une connexion à
# l'un d'eux = ÉCHEC nommé. Si les témoins ne peuvent pas écouter (bac à sable), NON JOUÉ, et les suites gardent l'isolation du lanceur (faux Herdr).
_temoins_racine=""; _temoins_pid=""
_temoins_demarrer() {
  local r=${BERGER_TEMOINS_RACINE:-} k
  _temoins_racine=""; _temoins_pid=""
  if [ -n "$r" ]; then mkdir -p "$r" 2>/dev/null || return 1; else r=$(mktemp -d /tmp/htXXXXXX 2>/dev/null) || return 1; fi
  ( _fermer_verrou; exec python3 "$B/tests/_temoins.py" "$r" "$1" "$r/connexions" "$r/pret" >"$r/temoins.log" 2>&1 ) &
  _temoins_pid=$!
  for k in $(seq 1 100); do
    [ -e "$r/pret" ] && { _temoins_racine=$r; return 0; }
    kill -0 "$_temoins_pid" 2>/dev/null || break
    sleep 0.1
  done
  kill "$_temoins_pid" 2>/dev/null; wait "$_temoins_pid" 2>/dev/null; _temoins_pid=""; rm -rf "$r"; return 1
}
_temoins_arreter() { [ -n "$_temoins_pid" ] && { kill "$_temoins_pid" 2>/dev/null; wait "$_temoins_pid" 2>/dev/null; }; _temoins_pid=""; }
_temoins_verifier() {
  if [ -z "$_temoins_racine" ]; then
    echo "NON JOUÉ Herdr réel hors d'atteinte, preuve sur toutes les suites : les sockets témoins ne peuvent pas écouter ici (bac à sable) ; les suites ont gardé l'isolation du lanceur (faux Herdr)"; return
  fi
  sleep 0.3; _temoins_arreter
  local nb=0 i vecteur
  while read -r i vecteur; do
    [ -n "$i" ] || continue; nb=$((nb+1))
    dire ÉCHEC - - "isolation Herdr cassée : ${_sf[$i]} a joint le socket témoin $vecteur (python3 tests/${_sf[$i]})"; _rouges+=("${_sf[$i]}")
  done <"$_temoins_racine/connexions" 2>/dev/null
  [ $nb = 0 ] && dire ok - - "Herdr réel hors d'atteinte, preuve sur TOUTES les suites : ${#_sf[@]} suites jouées en environnement hostile (HERDR_SOCKET_PATH, XDG_CONFIG_HOME, BERGER_HERDR_SOCKET hérité, HOME jetable), 0 connexion aux sockets témoins"
  rm -rf "$_temoins_racine"; _temoins_racine=""
}
# Joue les suites déclarées : N à la fois (lancées dans l'ordre de la liste, une « à part » seule), verdicts rendus dans l'ordre.
_jouer_les_suites() {
  _verrou_global || { ko=$((ko+1)); return; }
  local n; n=$(_parallele_choisi)
  local total=${#_sf[@]} lance=0 rendu=0 fini i k t seule="" ordre=() delai=${BERGER_SUITE_DELAI:-1200}
  [[ "$delai" =~ ^[1-9][0-9]{0,5}$ ]] || { echo "BERGER_SUITE_DELAI=« ${delai:0:40} » refusé : un nombre de secondes est attendu, 1200 utilisé" >&2; delai=1200; }
  for t in "${_en_tete[@]}"; do for k in "${!_sf[@]}"; do [ "${_sf[$k]}" = "$t" ] && ordre+=("$k"); done; done      # ordre de LANCEMENT
  for k in "${!_sf[@]}"; do [[ " ${ordre[*]} " == *" $k "* || -n "${_a_part[${_sf[$k]}]}" ]] || ordre+=("$k"); done
  for k in "${!_sf[@]}"; do [ -n "${_a_part[${_sf[$k]}]}" ] && [[ " ${ordre[*]} " != *" $k "* ]] && ordre+=("$k"); done   # les suites « à part » en dernier (sauf déjà placée en tête : une suite deux fois dans l'ordre en laisse une autre jamais lancée, et le rendu attend son « fin » sans fin)
  export BERGER_SUITES_PARALLELE=$n      # transmis aux descendants (un plafond, calculé une fois)
  _res=$(mktemp -d) || { echo "impossible de créer le dossier des résultats" >&2; ko=$((ko+1)); return; }
  _temoins_demarrer "$total"
  # Contrôle des tâches (set -m) : un processus lancé en arrière-plan SANS lui ignore SIGINT et perd son stdin, et une suite qui
  # interrompt un client (tests/argv-client.py, test_nettoyage_interruption) ne le verrait plus s'arrêter. Chaque suite a aussi
  # son groupe de processus : l'arrêt du lanceur les emporte toutes (TERM, courte attente, KILL).
  local m=${-//[^m]/}; set -m
  _pid=(); _debut=()
  trap 'for p in "${_pid[@]}"; do kill -TERM -- -$p 2>/dev/null; done; sleep 3; for p in "${_pid[@]}"; do kill -KILL -- -$p 2>/dev/null; done; for p in "${!_pid[@]}"; do _tuer_marque "$$-$p"; done; _temoins_arreter; rm -rf "$_res" "$_bt" "$_pyd" "$_temoins_racine"; exit 130' INT TERM
  while [ $rendu -lt $total ]; do
    fini=$(ls "$_res"/*/fin 2>/dev/null | wc -l)                      # ... en cours = lancées - finies
    [ -n "$seule" ] && [ -e "$_res/$seule/fin" ] && seule=""          # la suite « à part » a fini : on reprend
    while [ -z "$seule" ] && [ $lance -lt $total ] && [ $((lance - fini)) -lt $n ]; do
      i=${ordre[$lance]}
      if [ -n "${_a_part[${_sf[$i]}]}" ]; then [ $lance -gt $fini ] && break; seule=$i; fi     # « à part » : attendre que plus rien ne tourne, puis rien d'autre pendant qu'elle tourne
      _jouer $i & _pid[$i]=$!; _debut[$i]=$SECONDS; lance=$((lance + 1))
    done
    # Surveillance des suites en cours, par PID : délai maximal (groupe tué), ou processus mort sans avoir écrit « fin » (échec compté)
    for i in "${!_pid[@]}"; do
      [ -e "$_res/$i/fin" ] && continue
      if ! kill -0 "${_pid[$i]}" 2>/dev/null; then
        sleep 0.3; [ -e "$_res/$i/fin" ] || _forcer_fin $i 125 "processus de la suite mort sans avoir rendu de verdict"
      elif [ $((SECONDS - _debut[i])) -ge "${_delai_suite[${_sf[$i]}]:-$delai}" ]; then
        _tuer_groupe "${_pid[$i]}"; _forcer_fin $i 124 "délai dépassé (${_delai_suite[${_sf[$i]}]:-$delai} s) : groupe de processus arrêté"
      fi
    done
    while [ $rendu -lt $total ] && [ -e "$_res/$rendu/fin" ]; do _rapporter $rendu; rendu=$((rendu + 1)); done
    [ $rendu -lt $total ] && sleep 0.1
  done
  [ ${#_pid[@]} -gt 0 ] && wait "${_pid[@]}" 2>/dev/null          # PID explicites : un « wait » nu attendrait aussi les serveurs d'essai de tout.sh
  trap - INT TERM; [ -n "$m" ] || set +m; rm -rf "$_res"
  _temoins_verifier
}


# SUITE_SEULE=<fichier> : cette suite seule (tests/shims-mise.py s'en sert pour jouer une sonde par `suite`, comme la porte)
if [ -n "$SUITE_SEULE" ] && [ -n "$SEULES" ]; then
  suite "$SUITE_SEULE" "suite seule" ""; BERGER_SUITES_PARALLELE=1 _jouer_les_suites; [ -n "$_bt" ] && rm -rf "$_bt"; [ -n "$_pyd" ] && rm -rf "$_pyd"; exit $ko
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
suite portes-allegees.py "portes allégées" "(porte courte décidée par le courtier d'après le diff, jamais par l'agent ; mettre-a-jour sans identité git ; courtier/consignes/ ignoré)"
suite equipe.py "équipe de dev" "(demande de fusion, fusion, hooks, droits)"
suite contexte-appel.py "contexte propre à chaque appel du courtier" "(deux développeurs concurrents : SA copie, SON agent ; chaque outil à contexte, panneaux)"
suite equipe-verif.py "équipe : verify distant et conflits" "(verify par un outil du courtier, conflits entre demandes et avec main)"
suite processus-dev.py "processus de dév générique" "(4 portes : absentes, vertes, rouges, gate « non mesuré », pret obligatoire ; correctif : test et cause racine ; relecture qui rejoue et recompte ; fusion : pret rejouée, main avancée sans ou avec fichier commun ; étiquette SemVer et journal)"
suite sha-fige.py "SHA figé" "(la fusion validée est celle du commit présenté à l'aperçu : demande ou branche qui a bougé → refus ; validation sans SHA refusée ; portes distantes sur le SHA, attestation « commit testé »)"
suite chef-copie.py "branche de finition écrite dans la copie de travail du chef" "(importée en avance rapide seule puis poussée, demandée, fusionnée ; copie réécrite refusée ; copie_chef ; refus : hors dossier, lien, .git renvoyé, dépôt, forge, installation ; config piégée de la copie jamais exécutée, témoins)"
suite chef-finition.py "branche de finition du chef de projet" "(pousser et demander la fusion comme un développeur, au nom du chef ; fusion au propriétaire seul ; refus : principale, hors préfixe, .., tiret, espace, force, développeur ; hook piégé ; en-tête de journal avec un titre)"
suite equipe-ouverture.py "équipe : ouverture sûre" "(modèle refusé avant toute création, ports distincts en simultané)"
suite herdr-fuite.py "Herdr réel hors d'atteinte des suites" "(contrôles positifs : sans isolation, un client Herdr atteint chacun des chemins réels et les sockets témoins, avec isolation non ; lanceur : faux Herdr imposé, HERDR_*, XDG_CONFIG_HOME et BERGER_HERDR_SOCKET hérités retirés ; chaque suite importe l'isolation ; sonde-shebang.py isolée, lancée directement. La preuve « 0 connexion » sur TOUTES les suites est faite par suites.sh lui-même, à leur passage normal, dans un environnement hostile)"
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
suite commandes-couverture.py "couverture des commandes" "(les 61 verbes figés = l'union des familles de bin/commandes/ (27 en famille, 34 inscrits par la transition), une aide et des droits par verbe, aucun doublon, tableau du manuel, entrée privée déclarée, verbe inconnu inchangé)"
suite equivalence-missions.py "équivalence des missions (lot 4a)" "(40 scénarios mesurés sur main : sorties, refus, fichiers écrits, transport --stdin, droits par le courtier, lancement strict, plafond)"
suite equivalence-messages.py "équivalence des messages et des besoins (lot 4b)" "(82 scénarios mesurés avant le lot : sorties, refus, fichiers écrits, transport --stdin, droits ecrire:/deleguer: par le courtier, débit, bascule de demander, besoins)"
suite equivalence-equipes.py "équivalence des équipes (lot 4c)" "(99 scénarios mesurés sur main : sorties, refus de rôle, de go, de plafond et de sujet, fichiers écrits, copies, transport --stdin, crochet, données d équipe illisibles, droits par le courtier)"
suite taille-fichiers.py "taille des fichiers" "(1 500 lignes, cliquet de bin/berger)"
suite missions.py "agents de mission en lecture seule" "(écriture, mission, délégation, décision refusées ; lecture permise)"
suite modeles-table.py "table des modèles et règle par type" "(lot 1 : [modeles], ligne « Type : », ligne 2 de MISSION.md, suivi, aucun fichier de courtier/ dans le diff du lot)"
suite affichage.py "affichage des panneaux" "(jamais de débordement, écran séparé, terminal rendu propre)"
suite synthese.py "onglets Synthèse et Sources" "(rouge et jaune seulement, collecte en échec dite, secrets bloqués)"
suite tableau.py "onglet Tableau" "(colonnes, cartes sans doublon)"
suite decisions.py "onglets Décisions et Checklists" "(question laissée, validations, cases restantes, onglets rangés)"
suite refonte-espace.py "refonte de l'espace Berger" "(ce qui attend le propriétaire, Rien à faire, états périmés, Accueil sans défilement, Documents fusionné, un seul Accueil)"
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
suite publication.py "publication vers le dépôt en ligne" "(sans réseau : forge et « en ligne » nus ; option absente → rien ; avance rapide → publié, étiquettes ancêtres, contrôlé ; étiquette différente, miroir, divergence, remote absent → échec nommé, tracé, notifié, jamais de force ; courtier inactif → aucune publication ; installer et nouvel essai passent --publier ; publier manuel = même fonction)"
suite domaines.py "sites permis par projet" "(liste stricte par --settings et protégée, deny-all sinon, motif exact, validée par le superviseur, Codex sans réseau)"
suite tmp-par-agent.py "dossier temporaire par agent" "(CLAUDE_CODE_TMPDIR dans les réglages ET dans l’environnement de chaque lancement — exec, claude -p, Herdr —, commun et autres refusés en lecture et écriture, Claude et Codex, 700, relais réseau non couvert, > 44 octets ou dossier douteux : lancement refusé, mur ouvert inchangé)"
suite anti-boucle.py "garde-fou anti-boucle" "(même appel refusé au-delà de boucle_max par heure sans sollicitation, gardien prévenu une fois, Synthèse, appels espacés ou différents acceptés, interrupteur ; relance d’un agent occupé seulement si boucle repérée et rien depuis inactif_min, un agent occupé sans boucle jamais relancé ; règle dans REGLES et le skill ; neutre au moteur)"
suite superviseur.py "agent superviseur" "(lit les autres agents, n'y écrit pas, coffre et sources illisibles, Claude et Codex)"
suite equipe-berger.py "équipe qui corrige Berger" "(jamais l'installation pour dépôt ; forge locale : publier et synchroniser en avance rapide seule, jamais de force)"
suite vitrine-readme.py "README bilingues et schémas générés" "(structure, liens, badges, logo choisi et génération déterministe)"
suite communaute-porte.py "porte communautaire légère" "(aucun rejeu, trente et un contrôles conservés, témoins de fichiers invalides)"
suite communaute.py "fichiers communautaires" "(contribution, modèles, CI et lanceur du clone frais)"
suite config-exemple-racine.py "config.exemple.toml : options racine" "(tête décommentée lue en TOML : chaque option racine connue est à la racine, avant [[gardes]])"
suite apercu.py "aperçu statique de l'interface" "(aucun flux ni requête réelle, EventSource et fetch neutralisés avant la page)"
suite clone-frais-checkout.py "clone frais d'un checkout GitHub non nu" "(sans réseau : origine https, verrou des suites résolu par le clone frais, preuve menée jusqu'au bout)"
suite ci-et-etats-locaux.py "CI (pret sur la PR) et états locaux ignorés" "(pret sur le diff de la PR, base explicite ; états du courtier, du relais web et des MCP ignorés ; aucun fichier suivi ignoré)"
suite pret-base.py "pret : base de comparaison explicite" "(BERGER_PRET_BASE = branche cible de la PR ; absente ou douteuse → échec nommé, jamais un repli sur origin/main)"
suite vitrine.py "vitrine documentaire" "(manuel conservé, matrice exhaustive, liens locaux, liste blanche et verifier-depot jetable)"
suite installer-master.py "doc : installer le Master" "(blocs de config.exemple.toml lisibles en TOML avec les clés citées, chaque commande berger citée existe)"
suite agent-appliquer.py "créer ou modifier un agent sur proposition" "(droits avant → après, empreinte, sauvegarde, refus même validés)"
suite verbe-prod.py "verbe prod (script serveur)" "(prérequis et disque contrôlés tôt, étiquette de main seule, sauvegarde relue en flux, chiffrée pour la clé publique seule et contrôlée sinon refus, essai à blanc, migrations SQL jouées et inscrites (transaction unique ou BEGIN propre, applied_by, apostrophe refusée), avant/apres, controles_sante (retour arrière), branche principale sans HEAD détachée, santé, retour arrière sans toucher la base, ssh coupée en pleine construction, verrou, journal, ssh forcé ; courtier : chef validé, développeur refusé)"
suite mcp-trous.py "trous MCP des agents strict" "(Claude : --strict-mcp-config et ENABLE_CLAUDEAI_MCP_SERVERS=false à chaque lancement ; Codex : apps, plugins, remote_plugin, skill_mcp_dependency_install, tool_suggest coupés ; .mcp.json, .claude/settings*.json, .codex/ en lecture seule ; moteur non admis : bascule, rouge, refus si aucun ; mur ouvert inchangé)"
suite web-integre.py "outils web intégrés des moteurs (lot 1)" "(strict Claude : WebFetch et WebSearch dans permissions.deny, --settings d'un externe compris ; strict Codex : -c web_search=\"disabled\", sous-agents et clock coupés à chaque lancement ; mur ouvert inchangé ; contrat (12) hors moteur : init, faux fournisseur local, témoin obligatoire, aucune requête = rouge)"
suite contrat-outils-codex.py "contrôle (12) Codex : rejeu des requêtes capturées" "(tools et additional_tools cumulés, identifiants structurés, enveloppe ou outil inconnu = non mesurable et nommé, témoin compris)"
suite contrat-sous-agents.py "contrôle (13) Codex : sous-agents (collaboration) pour les stricts" "(spawn_agent et sortie du sous-agent obligatoires, sinon non mesurable ; lecture, écriture MCP, socket témoin, réseau depuis l'outil du sous-agent : une évasion = rouge nommée ; collaboration accepté par (12) seulement si (13) verte ; web et clock refusés ; faux exécutable)"
suite codex-modele-strict.py "modèle Codex imposé aux stricts (codex_modele_strict)" "(-m au lancement interactif, exec et contrat ; option absente ou mur ouvert inchangés ; valeur invalide et mission contradictoire refusées)"
suite mcp.py "serveurs MCP par berger-mcp" "(configs : berger-mcp seul, Claude --mcp-config, Codex approuvé pour CE serveur, rien sans mcp = ; refus § 3 ; relais : protocole, journal sans valeur, filtre coffre/clé/notification, débit, taille ; enveloppe : coffre, autre agent, réseau, écriture, env vidé ; bwrap absent ou en échec : rien ; socket relais ↔ courtier)"
suite web-relais.py "remise de rapport web sans mission réelle" "(validation propriétaire, snapshot, secrets, liens, scope, dépôt exclusif, mission chef et reçu)"
suite web-relais-mission.py "attribution exclusive des missions" "(deux appels concurrents, aucun écrasement ni effet doublé)"
suite web-connecter.py "connexion propriétaire sans réseau" "(lease unique, révocation, profils privés, faux Playwright headful, POST propriétaire seul)"
suite web-profils-masques.py "masques des profils web" "(parent effectif créé avant enveloppe, coffre par défaut, chemins externes)"
suite web-session.py "coffre des sessions web" "(coffre temporaire, sauvegarde simulée, identité, cookies, rétention)"
suite web-security-review.py "régressions de la revue de sécurité web" "(méthodes détournées avant Cookie, échéances indépendantes, aperçu absent des argv et cookies courts)"
suite web-session-proxy.py "session prêtée au proxy" "(flux sans socket, Cookie TLS, lecture seule, Set-Cookie, cycle et nettoyage, filtre)"
suite web-effacement.py "chemins d'effacement en POST validé" "(delete refusé en GET, HEAD, POST non validé et session prêtée, permis en POST validé ; logout, export, settings, payment toujours refusés)"
suite web-https.py "HTTPS contrôlé" "(TLS réel, méthodes, Host, corps, chemins et certificat par accès)"
suite web.py "accès web d'un agent (proxy et cycle)" "(proxy : nom permis, autre nom, IP, adresse privée après résolution, redirection hors de l'accès, méthode, corps > 64 Ko refusés et journalisés, sans paramètres d'URL ; CONNECT tunnelé ; socket UNIX ; cycle : demande validée par le propriétaire seul, --duree 24 h au plus, un accès à la fois, prolongation, refus, expiration, échéance, berger web fermer, redémarrage)"
suite contrat-session.py "contrat de session sans réseau" "(doubles, témoins obligatoires, DOM, statut TLS, fuite/refus/échéance, nettoyage et publics restaurés)"
suite contrat-web.py "contrat web : témoins navigateur, Host et tunnels" "(régressions de la revue)"
suite contrat-socket.py "contrôle (6) du contrat, hors moteur" "(connect() vers un socket témoin qui écoute hors bac à sable, vu par l'agent ; création en information ; témoin connecté ; socket retiré, reprise sûre)"
suite parallele-memoire.py "protection de la RAM par le lanceur de suites" "(1 suite à la fois par défaut, BERGER_SUITES_PARALLELE de 1 à 4 sinon refus nommé, shell et Python ; verrou global flock sans auto-blocage du rejeu ; jamais plus de n à la fois, suite à part seule, délai par suite, suite morte comptée en échec, descendants tués au délai et à l'interruption ; mesure de mémoire)"
suite shims-mise.py "suites sous un HOME jetable" "(raccourcis mise de la vraie maison retirés du PATH des suites, python3 réel : bin/berger démarre par son shebang ; témoin rouge sans)"

_jouer_les_suites
[ -n "$_bt" ] && rm -rf "$_bt"; [ -n "$_pyd" ] && rm -rf "$_pyd"
if [ -n "$SEULES" ]; then [ ${#_rouges[@]} = 0 ] || { echo "suites en échec : ${_rouges[*]}"; printf '%s\n' "${_rouges_diag[@]}"; }; echo "==== $ko échec(s)"; exit $ko; fi
