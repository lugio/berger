"""Les moteurs de Berger (modulaire, lot 2) : un fichier par moteur dans bin/moteurs/ (NOM, ORDRE, executable, version, verdict, args,
lecteur_conso, et ses constantes propres), et ici ce qui est vrai de TOUS les moteurs : l'admission (contrat par moteur et version),
le choix du moteur d'un agent, les alertes de la Synthèse, les arguments de lancement (+ modèle de la mission).

Code déplacé de bin/berger : aucun comportement changé. Un moteur qui ne charge pas est ÉCARTÉ et NOMMÉ (MOTEURS_REFUSES, `berger etat`) ;
un agent qui le demande reçoit « moteur <x> écarté : <cause> », jamais un repli silencieux sur l'autre. Ce module n'est pas écartable.

Ce que le mur et les secrets gardent au cœur (lot 4) reste dans bin/berger : bin/berger le BRANCHE ici au démarrage (`brancher`, liste
nommée COEUR_*), jusqu'à son propre déplacement ; masques, cloisons et réglages du mur n'entrent jamais ici."""
import datetime, hashlib, importlib.util, json, os, re, shlex, shutil, subprocess, sys, time
from pathlib import Path
from noyau.config import *
from noyau.agents import *
from noyau.lectures import reglages_mission
from noyau.bandeaux import notifier
import noyau.lectures
import noyau.modeles
import noyau.ecarts
import noyau.api

# Ce que le cœur (bin/berger) prête aux moteurs tant que ses fonctions n'ont pas quitté le cœur (lot 4) : branché par bin/berger.
COEUR_FONCTIONS = ("consigne_systeme", "ecrire_mcp_claude", "ecrire_reseau_claude", "env_appelant",
                   "reglages_strict_externe")
COEUR_CONSTANTES = ("AU_REPOS", "ACCORD_BYPASS")
# Noms du noyau hors API qu'un moteur emploie (l'API reste celle des vues) : lecteurs de consommation, profil Codex ; transport (ecrire_configuration),
# sorti de l'API de lecture au lot 4d : une vue ou une famille ne lance aucun programme sans service.
BASE_NOYAU = ("ouvert", "externe", "travail", "CODEX_HOME", "CONSO", "lignes_neuves", "agent_du_dossier", "transport")
DOSSIER = Path(__file__).resolve().parent

MOTEURS, MODULES = [], {}                              # noms chargés (ordre déclaré), modules
MOTEURS_REFUSES = noyau.ecarts.MOTEURS_REFUSES       # {fichier: « Type: message »} : le dictionnaire partagé du noyau (noyau/ecarts.py ; berger etat le lit)
_coeur = {}


def _non_branche(nom):
    def f(*a, **k): raise RuntimeError(f"{nom} non branchée : bin/berger la pose dans moteurs au démarrage (brancher)")
    return f


for _n in COEUR_FONCTIONS: globals()[_n] = _non_branche(_n)


def brancher(**noms):
    """Prête au paquet, et à chaque moteur chargé, des noms du cœur listés dans COEUR_* (rien d'autre : un nom inconnu est refusé)."""
    for n in noms:
        if n not in COEUR_FONCTIONS + COEUR_CONSTANTES: raise NameError(f"moteurs : « {n} » n'est pas dans COEUR_FONCTIONS/COEUR_CONSTANTES")
    _coeur.update(noms); globals().update(noms)
    for mod in MODULES.values(): mod.__dict__.update(noms)


def espace_moteur(noyau_globals):
    """Ce que reçoit un moteur : l'API du noyau, la bibliothèque standard, BASE_NOYAU et ce que le cœur lui a branché."""
    manque = [n for n in BASE_NOYAU if n not in noyau_globals]
    if manque: raise NameError(f"moteurs : nom(s) du noyau absent(s) {', '.join(manque)}")
    return {**noyau.api.espace(noyau_globals), **{n: noyau_globals[n] for n in BASE_NOYAU}, **_coeur,
            "executable_moteur": executable_moteur, "version_moteur": version_moteur, "verdict_moteur": verdict_moteur}


def charger(noyau_globals):
    """Un fichier par moteur dans bin/moteurs/ (les `_…` et __init__ ignorés). Contrat : NOM, ORDRE, efforts_permis, executable(), version(), verdict(),
    args(a, interactif=True), args_modele(modele, effort), lecteur_conso() ; modele_impose(a) facultatif. Un moteur qui ne charge pas est écarté et nommé ; les autres tournent. Remplit
    LECTEURS_CONSO (noyau) d'après les moteurs chargés. Deux fichiers qui déclarent le même NOM : les DEUX sont écartés. NOM (texte non vide), ORDRE (entier)
    et le lecteur rendu par lecteur_conso() (appelé une seule fois) sont vérifiés DANS l'interception : un moteur aux métadonnées invalides est écarté, nommé."""
    MOTEURS.clear(); MODULES.clear(); MOTEURS_REFUSES.clear(); noyau.lectures.LECTEURS_CONSO.clear()
    espace = espace_moteur(noyau_globals); trouves = {}
    for f in sorted(DOSSIER.glob("*.py")):
        if f.name.startswith("_"): continue
        try:
            spec = importlib.util.spec_from_file_location(f"moteur_{f.stem}", f); mod = importlib.util.module_from_spec(spec)
            mod.__dict__.update(espace)
            spec.loader.exec_module(mod)
            for c in ("NOM", "ORDRE"):
                if not hasattr(mod, c): raise AttributeError(f"constante {c} absente")
            if not isinstance(mod.NOM, str) or not mod.NOM: raise TypeError(f"constante NOM : un texte non vide (lu : {mod.NOM!r:.40})")
            if type(mod.ORDRE) is not int: raise TypeError(f"constante ORDRE : un entier (lu : {mod.ORDRE!r:.40})")
            for fn in ("executable", "version", "verdict", "args", "args_modele", "lecteur_conso"):
                if not callable(getattr(mod, fn, None)): raise AttributeError(f"fonction {fn}() absente")
            lecteur = mod.lecteur_conso()                       # appelé UNE fois, ici : le lecteur gardé est celui qu'on a vérifié
            if not callable(lecteur): raise TypeError("lecteur_conso() ne rend pas un lecteur")
            if not isinstance(getattr(mod, "efforts_permis", None), tuple): raise AttributeError("constante efforts_permis (tuple, vide si le moteur n'a pas d'effort) absente")
        except Exception as e:
            MOTEURS_REFUSES[f.stem] = f"{type(e).__name__}: {e}"; continue
        trouves.setdefault(mod.NOM, []).append((f.stem, mod, lecteur))
    for nom, liste in trouves.items():
        if len(liste) > 1:
            for stem, _, _ in liste: MOTEURS_REFUSES[stem] = f"nom de moteur « {nom} » déclaré par plusieurs fichiers : {', '.join(s for s, _, _ in liste)}"
    for nom, liste in sorted(trouves.items(), key=lambda x: (x[1][0][1].ORDRE, x[0])):   # NOM texte et ORDRE entier : vérifiés ci-dessus, le tri ne peut pas lever
        if len(liste) == 1:
            MODULES[nom] = liste[0][1]; MOTEURS.append(nom); noyau.lectures.LECTEURS_CONSO[nom] = liste[0][2]
    noyau.lectures.SOURCES_ALERTES["moteurs"] = alertes_moteurs


def module(m):
    """Le module du moteur `m`, ou ValueError : « moteur <m> écarté : <cause> » (jamais un repli sur l'autre), « moteur inconnu »."""
    if m in MODULES: return MODULES[m]
    if m in MOTEURS_REFUSES: raise ValueError(f"moteur {m} écarté : {MOTEURS_REFUSES[m]}")
    raise ValueError(f"moteur inconnu : {m} ({' ou '.join(MOTEURS) or 'aucun moteur chargé'})")


def ecartes():
    """Moteurs écartés pour `berger etat` : [{moteur, cause}]."""
    return [{"moteur": n, "cause": e} for n, e in sorted(MOTEURS_REFUSES.items())]


# ─── Admission d'un moteur (mcp-trous, 17/10/2026) ───
# Un moteur n'est admis pour un agent strict que si SA version a passé le contrat (tests/contrat-moteur.sh) : outils vus =
# les siens seulement, aucun serveur MCP lancé, fichiers MCP non inscriptibles et ignorés, socket(AF_UNIX) refusé. Verdict
# gardé par moteur ET version (tests/contrats/<moteur>-<version>.txt, hors dépôt), 1re ligne « ADMIS » ou « NON ADMIS » ;
# version jamais vue = contrat joué avant le premier lancement. Non admis : l'agent BASCULE sur l'autre moteur s'il est
# admis (décision du propriétaire du 17/10 : pas de blocage sec), rouge dans la Synthèse et notification ; aucun : refus.
CONTRATS = BERGER / "tests/contrats"
DELAI_CONTRAT, GRACE_CONTRAT = 1200, 30          # secondes : contrat joué avant un lancement, puis le temps de se nettoyer
_VERSIONS = {}


def executable_moteur(m):
    """Le VRAI exécutable du moteur. Un raccourci mise (shims/<m> → /usr/bin/mise) est résolu par « mise which <m> » :
    le raccourci et mise ne changent pas quand mise met le moteur à jour, le chemin résolu si (installs/<m>/<version>/…).
    None : introuvable — y compris un raccourci que mise ne résout pas (« not currently active ») : rendre mise lui-même
    ferait lancer « mise <args> », qui tente d'installer des outils (vécu le 18/10 : serveur MCP d'essai jamais démarré)."""
    x = shutil.which(m)
    if not x: return None
    r = os.path.realpath(x)
    if os.path.basename(r) == "mise":
        try:
            p = subprocess.run([r, "which", m], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
            w = p.stdout.strip() if p.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired): w = ""
        r = os.path.realpath(w) if w else None
        if r and os.path.basename(r) == "mise": r = None
    return r


def version_moteur(m):
    """Version installée du moteur (« 2.1.300 », « 0.162.1 »), relue quand son VRAI exécutable change (executable_moteur :
    un processus qui dure, comme l'interface, voit une mise à jour faite par mise) ; None : introuvable."""
    x = executable_moteur(m)
    if not x: return None
    try: cle = (m, x, os.stat(x).st_mtime_ns)
    except OSError: return None
    if cle not in _VERSIONS:
        try: r = subprocess.run([x, "--version"], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired): return None
        v = re.search(r"\b(\d+\.\d+\.\d+)\b", r.stdout or ""); _VERSIONS[cle] = v and v.group(1)
    return _VERSIONS[cle]


def fichier_contrat(m, v): return CONTRATS / f"{m}-{v}.txt"


# Lignes ✓ qu'un verdict ADMIS doit porter (web-integre lot 1 bis, 30/10/2026) : le contrôle (12), outils web intégrés refusés,
# et son témoin positif. Un verdict ADMIS rendu avant (12) n'admet plus : il est « à rejouer » — le contrat est rejoué
# au prochain lancement strict, comme pour une version jamais vue (renvoi du 30/10 : jamais de blocage sans tentative).
# Renvoi n° 108 (31/10) : seul le (12) par LISTE FERMÉE prouve (« ✓ (12) liste fermée ») ; un verdict de l'ancien (12),
# qui cherchait des noms web (lot 1 et lot 1 bis), est « à rejouer » de la même façon.
CONTROLES_EXIGES = {}
CONTROLES_PAR_DEFAUT = ("✓ témoin (12) ", "✓ (12) liste fermée ")    # le témoin positif fait partie du contrôle, sous Claude comme sous Codex


# Admission par équivalence (go n° 136, docs/plans/2026-11-02-admission-auto-spec.md) : une version sans liste fermée, admise par
# le contrat parce que ses outils sont ceux de la liste de référence (la plus récente du dépôt). Aucune liste n'est écrite : le
# verdict porte « équivalence : <moteur> <version> sha256 <64> », et il ne vaut que si CETTE liste du dépôt existe encore avec
# CETTE empreinte (sinon « à rejouer »). La référence est toujours une liste relue du dépôt, jamais une autre équivalence.
LISTES = BERGER / "tests/outils-connus"
EQUIVALENCE = re.compile(r"équivalence : (claude|codex) (\d+(?:\.\d+)*) sha256 ([0-9a-f]{64})")
ADMIS_EQUIVALENCE = "✓ (12) liste fermée : admis par équivalence avec "


def equivalence_verdict(m, lignes):
    """(version de référence, None) si le verdict admet par équivalence avec une liste du dépôt intacte ; (référence ou None, raison)
    si la référence est absente, d'un autre moteur, modifiée ou retirée ; None si le verdict n'est pas une équivalence."""
    refs = [EQUIVALENCE.fullmatch(l.strip()) for l in lignes if l.startswith("équivalence")]
    if not refs and not any(l.startswith(ADMIS_EQUIVALENCE) for l in lignes): return None
    if len(refs) != 1 or not refs[0] or refs[0].group(1) != m:
        return None, f"verdict d'équivalence sans référence lisible de {m} — contrat à rejouer : bash tests/contrat-moteur.sh {m}"
    ref, h = refs[0].group(2), refs[0].group(3)
    try: ok = hashlib.sha256((LISTES / f"{m}-{ref}.json").read_bytes()).hexdigest() == h
    except OSError: ok = False
    if not ok or not any(l.startswith(f"{ADMIS_EQUIVALENCE}{m} {ref} (sha256 {h[:8]})") for l in lignes):
        return ref, (f"liste de référence {m} {ref} modifiée ou retirée depuis l'admission par équivalence — contrat à rejouer : "
                     f"bash tests/contrat-moteur.sh {m}")
    return ref, None


def verdict_moteur(m):
    """(état, version, raison) — état : « admis », « non admis », « jamais vu » (aucun verdict pour cette version) ou
    « à rejouer » (ADMIS sans une ligne de CONTROLES_EXIGES : jamais admis, contrat à rejouer). ADMIS ne vaut que sans
    ligne ✗ et avec chaque ligne de CONTROLES_EXIGES ; admis par équivalence, seulement si sa liste de référence est intacte
    (equivalence_verdict). Ne joue rien : lecture seule (Synthèse)."""
    v = version_moteur(m)
    if not v: return "non admis", None, f"{m} introuvable ou version illisible"
    lignes = lire(fichier_contrat(m, v)).splitlines()
    if not lignes: return "jamais vu", v, f"contrat jamais joué pour {m} {v}"
    if lignes[0].strip() == "ADMIS" and not any(l.startswith("✗ ") for l in lignes):
        manque = [x.strip() for x in CONTROLES_EXIGES.get(m, CONTROLES_PAR_DEFAUT) if not any(l.startswith(x) for l in lignes)]
        eq = equivalence_verdict(m, lignes)
        if not manque and eq and eq[1]: return "à rejouer", v, eq[1]
        if not manque: return "admis", v, ""
        return "à rejouer", v, (f"verdict rendu sans le contrôle (12) par liste fermée (outils web intégrés ; manque : {', '.join(manque)}) — "
                                f"contrat à rejouer : bash tests/contrat-moteur.sh {m} (tests/contrats/{m}-{v}.txt)")
    raisons = [l[2:] for l in lignes[1:] if l.startswith("✗ ")]
    return "non admis", v, (" · ".join(raisons[:3]) or "contrat non passé") + f" (tests/contrats/{m}-{v}.txt)"


A_JOUER = ("jamais vu", "à rejouer")       # états où le contrat est joué avant le lancement


def jouer_contrat(m, a):
    """Joue tests/contrat-moteur.sh <m> <a> (il écrit le verdict). Un à la fois : un verrou par moteur."""
    s = BERGER / "tests/contrat-moteur.sh"
    if not s.is_file(): return
    CONTRATS.mkdir(parents=True, exist_ok=True)
    import fcntl
    with open(CONTRATS / f".{m}.verrou", "w") as vr:
        fcntl.flock(vr, fcntl.LOCK_EX)
        if verdict_moteur(m)[0] not in A_JOUER: return                  # joué entre-temps par un autre lancement
        # au délai : SIGTERM d'abord (le contrat retire alors les fichiers posés chez l'agent), SIGKILL seulement après
        p = subprocess.Popen(["bash", str(s), m, a], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try: p.wait(timeout=DELAI_CONTRAT)
        except subprocess.TimeoutExpired:
            p.terminate()
            try: p.wait(timeout=GRACE_CONTRAT)
            except subprocess.TimeoutExpired: p.kill(); p.wait()


def moteur_admis(m, a):
    """None si `m` est admis (contrat joué au besoin, sur l'agent `a`), sinon la raison."""
    if m in MOTEURS_REFUSES: return f"moteur {m} écarté : {MOTEURS_REFUSES[m]}"
    etat, v, raison = verdict_moteur(m)
    if etat in A_JOUER:
        jouer_contrat(m, a); etat, v, raison = verdict_moteur(m)
        if etat == "jamais vu": return f"{m} {v} non admis : contrat impossible à jouer (tests/contrat-moteur.sh)"
        if etat == "à rejouer": etat, raison = "non admis", f"contrat impossible à rejouer ou rejoué sans (12) — {raison}"
    if etat == "admis": return None
    signaler_non_admis(m, v, raison)
    return f"{m}{' ' + v if v else ''} non admis : {raison}"


def signaler_non_admis(m, v, raison):
    """Une notification par version non admise (pas une par lancement)."""
    f = CONTRATS / f"{m}-{v}.notifie"
    if not v or f.exists(): return
    try: CONTRATS.mkdir(parents=True, exist_ok=True); f.write_text(raison + "\n")
    except OSError: pass
    notifier(f"Berger · {m} non admis", f"{m} {v} n'a pas passé le contrat d'admission : les agents strict basculent sur "
             f"l'autre moteur. {raison}", urgent=True)


def choisir_moteur(a, m):
    """(moteur à lancer, raison de la bascule) pour l'agent `a` qui demande `m`. Mur ouvert : hors sujet, `m` tel quel.
    Aucun moteur admis : (None, raison)."""
    if m in MOTEURS_REFUSES: return None, f"moteur {m} écarté : {MOTEURS_REFUSES[m]}"
    if ouvert(a): return m, None
    pb = moteur_admis(m, a)
    if not pb: return m, None
    autre = "codex" if m == "claude" else "claude"
    pb2 = moteur_admis(autre, a)
    if pb2: return None, f"aucun moteur admis pour un agent strict — {pb} ; {pb2}"
    journal(a, f"{pb} : bascule sur {autre}")
    return autre, pb


def alertes_moteurs():
    """Synthèse : un moteur utilisé par un agent strict et non admis → ROUGE ; version installée sans verdict (contrat à jouer) →
    JAUNE ; admis par équivalence sans liste exacte au dépôt → JAUNE (go n° 136). Un moteur
    absent de la machine n'y est pas (rien ne se lance sous lui : ce n'est pas un trou du mur)."""
    al = []
    utilises = {x for a in agents() if not ouvert(a) for x in [conf(a)["moteur"], *re.split(r"[ ,]+", conf(a).get("panneaux", ""))] if x in MOTEURS}
    for m in sorted(utilises):
        etat, v, raison = verdict_moteur(m)
        if not v: continue
        if etat == "non admis": al.append(("rouge", "moteurs", f"{m}{' ' + v if v else ''} non admis — {raison} : les agents strict basculent sur l'autre moteur"))
        elif etat == "jamais vu": al.append(("jaune", "moteurs", f"{m} {v} : version installée sans verdict : contrat à jouer (bash tests/contrat-moteur.sh {m})"))
        elif etat == "admis" and not (LISTES / f"{m}-{v}.json").exists():
            eq = equivalence_verdict(m, lire(fichier_contrat(m, v)).splitlines())
            if eq: al.append(("jaune", "moteurs", f"{m} {v} admis par équivalence avec {m} {eq[0]} : liste à ajouter au dépôt "
                                                  f"(tests/outils-connus/{m}-{v}.json, copie relue de {m}-{eq[0]}.json)"))
        elif etat == "à rejouer": al.append(("jaune", "moteurs", f"{m} {v} : {raison} — rejoué au prochain lancement d'un agent strict"))
    return al


def args_moteur(a, m, interactif=True):
    """Arguments du moteur + modèle/effort de sa mission. Un modèle imposé par le moteur refuse une mission contradictoire."""
    mm, modele = reglages_mission(a); base = module(m).args(a, interactif)
    effort = noyau.modeles.trace_mission(a)[2] if mm == m else None
    if mm != m: modele = None
    try:
        impose = getattr(module(m), "modele_impose", lambda a: None)(a)
        if impose is not None:
            if modele is not None and modele != impose:
                raise ValueError(f"modèle de mission {modele!r} incompatible avec le modèle imposé {impose!r} pour {m}")
            modele = impose
        if modele is None and effort is None: return base                              # champs vraiment absents
        noyau.modeles.controler_lancement(m, modele, effort, module(m).efforts_permis)   # MISSION.md peut avoir été éditée : on revalide
    except ValueError as e: sys.exit(f"lancement refusé pour {a} : {e}")
    return base + (module(m).args_modele(modele, effort) if modele is not None else [])


def decider_mission(moteur, modele, texte, par, niveau_agent=None):
    """(moteur, modèle, ligne 2 de MISSION.md) d'une mission, ou sys.exit nommé (AVANT de rien créer). Table `[modeles]` absente :
    rien ne change, le modèle est vérifié contre l'ancienne liste `[missions] modeles_<moteur>` (repli nommé) et il n'y a pas de ligne 2."""
    try: module(moteur)
    except ValueError as e: sys.exit(str(e))
    try: table = noyau.modeles.table()
    except ValueError as e: sys.exit(f"{e} — rien n'a été créé")
    if not table:
        permis = noyau.lectures.MISSIONS.get(f"modeles_{moteur}", [])
        if modele and (modele not in permis or not noyau.modeles.nom_sur(modele)):
            sys.exit(f"modèle non permis pour {moteur} : {modele} (permis : {', '.join(permis) or 'aucun'}) — rien n'a été créé")
        return moteur, modele, ""
    try: modele, niveau, raison, effort = noyau.modeles.decider(moteur, modele, texte, par, niveau_agent, module(moteur).efforts_permis)
    except ValueError as e: sys.exit(f"{e} — rien n'a été créé")
    return moteur, modele, noyau.modeles.ligne_trace(niveau, raison, effort)
