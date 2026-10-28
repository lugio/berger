"""Les commandes de Berger (modulaire, lot 3) : une famille de verbes par fichier dans bin/commandes/, découverte comme les vues.

Contrat d'un module de commandes :
    FAMILLE = "alire"                                  nom court, affiché par `berger etat` en cas d'écartement
    VERBES  = {"lire": fonction, …}                    verbe -> fonction(args, prive=False) ; NotImplemented = « ce n'est pas ma forme »
    AIDE    = {"lire": "berger lire [n°] …"}           une ligne d'aide par verbe
    DROITS  = {"lire": {"prive": False, "cas_go": None}}   entrée privée obligatoire ? cas de la règle de go (1 à 5) ?

`main()` ne connaît plus aucun verbe : il cherche `cmd` ici (`lancer`). L'obligation d'entrée privée (mission, message-deposer, equipe, projet)
vient de DROITS[...]["prive"] (`prive`). Deux familles qui déclarent le même verbe : les DEUX sont écartées et nommées (jamais « la dernière
gagne »). Une famille qui ne charge pas est écartée et nommée (COMMANDES_REFUSEES, `berger etat`) ; les autres tournent. Ce paquet n'est pas écartable.

Un module n'emploie QUE l'API du noyau (noyau/api.py) et la bibliothèque standard : le cœur ne lui prête rien, le noyau ne lui montre aucun
nom hors API. Un verbe qui appelle une fonction du cœur, le courtier, le mur, le bac à sable, les réglages moteur ou les identifiants RESTE donc
dans bin/berger jusqu'au lot 4. Le module `transition` inscrit dans le même registre ces verbes du cœur (VERBES_COEUR, donné par bin/berger à
`charger` : lui seul le reçoit) ; il disparaît avec le lot 4. Un verbe d'une famille qui plante À L'APPEL écarte sa famille (nommée, `berger etat`), sauf ce que la famille déclare laisser passer pour ce verbe (`PASSE`, optionnel : `{verbe: (exceptions,)}` ; ex. `Refus`, de l'API, pour un refus d'usage voulu : il sort alors comme la `ValueError` d'avant, même message)."""
import importlib.util, sys
from pathlib import Path
import noyau.api
import noyau.ecarts
from noyau.ecarts import Refus

DOSSIER = Path(__file__).resolve().parent

FAMILLES, VERBES, AIDES, DROITS = {}, {}, {}, {}   # nom -> module ; verbe -> fonction / ligne d'aide / droits
COMMANDES_REFUSEES = noyau.ecarts.COMMANDES_REFUSEES   # {fichier: « Type: message »} : le dictionnaire partagé du noyau (noyau/ecarts.py ; berger etat le lit)
FAMILLE_DE = {}
COEUR = "transition"                  # la famille des verbes restés au cœur : jamais écartée à l'appel (ses refus sont ceux de bin/berger)


def espace_commandes(noyau_globals):
    """Ce que reçoit un module de commandes : l'API du noyau et la bibliothèque standard, rien d'autre."""
    return noyau.api.espace(noyau_globals)


def _controler(mod):
    if not isinstance(getattr(mod, "FAMILLE", None), str) or not mod.FAMILLE: raise AttributeError("constante FAMILLE absente")
    for c in ("VERBES", "AIDE", "DROITS"):
        if not isinstance(getattr(mod, c, None), dict): raise AttributeError(f"dictionnaire {c} absent")
    for v, fn in mod.VERBES.items():
        if not callable(fn): raise TypeError(f"verbe {v} : pas une fonction")
        if not isinstance(mod.AIDE.get(v), str) or not mod.AIDE[v].strip(): raise KeyError(f"verbe {v} : ligne d'AIDE absente")
        d = mod.DROITS.get(v)
        if not isinstance(d, dict) or not isinstance(d.get("prive"), bool) or d.get("cas_go") not in (None, 1, 2, 3, 4, 5):
            raise KeyError(f"verbe {v} : DROITS absent ou invalide ({{\"prive\": bool, \"cas_go\": None|1..5}})")
    passe = getattr(mod, "PASSE", {})
    if not isinstance(passe, dict): raise TypeError("PASSE : un dictionnaire {verbe: (exceptions, …)} ou rien")
    for v, ex in passe.items():
        if v not in mod.VERBES: raise KeyError(f"PASSE décrit un verbe absent de VERBES : {v}")
        if not isinstance(ex, tuple) or not all(isinstance(x, type) and issubclass(x, BaseException) for x in ex): raise TypeError(f"verbe {v} : PASSE doit être un tuple de classes d'exception")
    for c in ("AIDE", "DROITS"):
        en_trop = sorted(set(getattr(mod, c)) - set(mod.VERBES))
        if en_trop: raise KeyError(f"{c} décrit un verbe absent de VERBES : {', '.join(en_trop)}")


def charger(noyau_globals, verbes_coeur):
    """Un fichier par famille dans bin/commandes/ (les `_…` et __init__ ignorés). Une famille qui ne charge pas est écartée et nommée ; deux familles
    qui déclarent le même verbe sont écartées TOUTES LES DEUX, nommées. Remplit le registre (VERBES, AIDES, DROITS, FAMILLE_DE).
    `verbes_coeur` ({verbe: fonction}) n'est donné qu'au module de transition."""
    for d in (FAMILLES, VERBES, AIDES, DROITS, COMMANDES_REFUSEES, FAMILLE_DE): d.clear()
    espace = espace_commandes(noyau_globals); sains = {}
    for f in sorted(DOSSIER.glob("*.py")):
        if f.name.startswith("_"): continue
        try:
            spec = importlib.util.spec_from_file_location(f"commandes_{f.stem}", f); mod = importlib.util.module_from_spec(spec)
            mod.__dict__.update(espace)
            if f.stem == COEUR: mod.VERBES_COEUR = verbes_coeur
            spec.loader.exec_module(mod)
            _controler(mod)
        except Exception as e:
            COMMANDES_REFUSEES[f.stem] = f"{type(e).__name__}: {e}"; continue
        sains[f.stem] = mod
    par_verbe = {}
    for stem, mod in sains.items():
        for v in mod.VERBES: par_verbe.setdefault(v, []).append(stem)
    doubles = {v: s for v, s in par_verbe.items() if len(s) > 1}
    for stem in sorted({x for s in doubles.values() for x in s}):
        COMMANDES_REFUSEES[stem] = "verbe(s) déclaré(s) par plusieurs familles : " + ", ".join(
            f"{v} ({' et '.join(s)})" for v, s in sorted(doubles.items()) if stem in s)
        del sains[stem]
    for stem, mod in sains.items():
        FAMILLES[stem] = mod
        for v, fn in mod.VERBES.items():
            VERBES[v], AIDES[v], DROITS[v], FAMILLE_DE[v] = fn, mod.AIDE[v], mod.DROITS[v], stem


def prive(cmd):
    """Ce verbe exige-t-il l'entrée privée (`berger --stdin`) ? Déclaré par DROITS, plus écrit en dur dans main()."""
    return bool(DROITS.get(cmd, {}).get("prive"))


def ecarter(famille, cause):
    """Écarte une famille (nommée dans COMMANDES_REFUSEES) : ses verbes quittent le registre."""
    COMMANDES_REFUSEES[famille] = cause
    FAMILLES.pop(famille, None)
    for v in [v for v, f in FAMILLE_DE.items() if f == famille]:
        for d in (VERBES, AIDES, DROITS, FAMILLE_DE): d.pop(v, None)


def lancer(cmd, args, prive=False):
    """Exécute le verbe `cmd` (ce que rend sa fonction), ou NotImplemented : verbe inconnu, ou forme qui n'est pas la sienne.
    Une famille (hors transition) dont le verbe plante est écartée et nommée ; le message dit laquelle. sys.exit, Ctrl-C et ce que le verbe déclare dans PASSE passent tels quels."""
    fn = VERBES.get(cmd)
    if fn is None: return NotImplemented
    famille = FAMILLE_DE[cmd]
    if famille == COEUR: return fn(args, prive)
    passe = tuple(getattr(FAMILLES.get(famille), "PASSE", {}).get(cmd, ()))
    try: return fn(args, prive)
    except passe as e:                                        # ce que le verbe DÉCLARE laisser passer (PASSE) : comme avant son déplacement, la famille n'est pas en cause
        if type(e) is Refus: raise ValueError(*e.args) from None   # un Refus sort tel qu'il était avant : une ValueError ordinaire (dernière ligne « ValueError: … »)
        raise
    except Exception as e:
        cause = f"{type(e).__name__} à l'appel de {cmd} : {e}"
        ecarter(famille, cause)
        sys.exit(f"commande {cmd} : famille {famille} écartée ({cause})\nbin/commandes/{famille}.py est écartée jusqu'à sa correction ; `berger etat` la nomme.")


def ecartees():
    """Familles écartées pour `berger etat` : [{commandes, cause}]."""
    return [{"commandes": n, "cause": e} for n, e in sorted(COMMANDES_REFUSEES.items())]


def inconnue(cmd, aide):
    """Le refus d'un verbe inconnu : le même texte qu'avant ; si des familles sont écartées, elles sont nommées (le verbe était peut-être chez elles)."""
    t = f"commande inconnue : {cmd}\n\n{aide}"
    for e in ecartees(): t += f"\n⚠ commandes écartées : bin/commandes/{e['commandes']}.py — {e['cause']}"
    return t


def tableau():
    """verbe -> famille (le tableau du manuel)."""
    return dict(sorted(FAMILLE_DE.items()))
