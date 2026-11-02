#!/usr/bin/env python3
"""Contrat du noyau (modulaire, lot 1) : un module de bin/vues/ n'emploie que l'API de bin/noyau/api.py et la bibliothèque standard ;
chaque nom de l'API existe ; la frontière tient À L'EXÉCUTION (un nom du cœur hors API n'existe pas pour une vue, la vue fautive est
écartée et NOMMÉE, les autres tournent) ; aucune vue n'est remise dans les globales du cœur. Une installation JETABLE.
Lot 2 : idem pour les moteurs (bin/moteurs/). Lot 3 : idem pour les familles de commandes (bin/commandes/) — un module n'emploie que l'API et la bibliothèque
standard ; seule la famille de transition reçoit VERBES_COEUR (le cœur ne prête rien aux autres) ; une famille cassée ou en doublon est écartée et nommée, les autres tournent.
Lot 3 bis : chaque nom ajouté à l'API pour les verbes déplacés existe dans son module du noyau, n'a plus de définition dans le cœur et ne passe par aucun
chemin du cœur réservé au lot 4 (coffre, mur, bac à sable, courtier, démarrage d'agent…) ; ce qu'un verbe déclare dans PASSE (IndexError…) et Refus (refus d'usage voulu, redevenu une ValueError ordinaire) sortent comme avant sans écarter la famille ; une ValueError ordinaire écarte la famille.
Lot 4c : la famille equipes (lectures dans l'API, actions par les services), lire_document, lire_interactif, mettre_a_jour_titres et statusline (qui écrivent)
dans l'API d'action ; les services gardent leurs contrôles ; une panne du cœur sort telle qu'avant ; la famille cassée est écartée et nommée (sections 1h et 8).
Correctif contrat (29/10) : un module n'importe que la bibliothèque standard et noyau.api (ni autre module du noyau, ni module frère, ni import dynamique, ni attribut
spécial) ; les portées sont celles de Python (un nom local d'une fonction n'est pas défini pour une autre).
Usage : python3 tests/contrat-noyau.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast, builtins, json, os, re, shutil, subprocess, symtable, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    print(("ok     " if ok else "ÉCHEC  ") + texte); ko += 0 if ok else 1


sys.path.insert(0, str(SRC / "bin"))
from noyau import api

libres_ok = set(dir(builtins)) | set(api.API) | set(api.STDLIB) | {"__file__", "__name__", "__doc__"}


def noms_libres(fichier):
    """Noms lus par un module sans être définis À SA PORTÉE MODULE, ni builtin, ni dans l'API : (nom, ligne). Les portées sont celles de Python
    (symtable) : un nom local d'une fonction, ou défini dans un corps de classe, n'existe pas pour une autre fonction ni pour les méthodes."""
    src = Path(fichier).read_text(encoding="utf-8"); t = ast.parse(src); haut = symtable.symtable(src, str(fichier), "exec")
    tables = [haut]; i = 0
    while i < len(tables): tables += tables[i].get_children(); i += 1
    definis = {s.get_name() for s in haut.get_symbols() if s.is_assigned() or s.is_imported()}
    definis |= {s.get_name() for tb in tables for s in tb.get_symbols() if s.is_declared_global() and s.is_assigned()}
    mauvais = {(tb.get_lineno(), s.get_name()) for tb in tables for s in tb.get_symbols()
               if s.is_referenced() and s.is_global() and not s.get_name().startswith(".") and s.get_name() not in definis and s.get_name() not in libres_ok}
    # la ligne : le premier emploi du nom dans la portée qui le lit (la portée la plus proche qui l'englobe)
    portee, pile = {}, [(t, 0)]
    while pile:
        n, p = pile.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)): p = n.lineno
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load): portee.setdefault((p, n.id), n.lineno); portee[(p, n.id)] = min(portee[(p, n.id)], n.lineno)
        pile += [(c, p) for c in ast.iter_child_nodes(n)]
    return sorted({(nom, portee.get((l, nom), l)) for l, nom in mauvais})


SURS = set(sys.stdlib_module_names) - {"importlib", "runpy", "builtins", "gc", "inspect", "ctypes", "pkgutil", "zipimport", "code", "codeop"}


def imports_interdits(fichier):
    """Ce qu'un module (vue, famille de commandes, moteur) importe hors de la bibliothèque standard et de noyau.api : (description, ligne).
    Refusés : tout module du noyau autre que noyau.api (noyau.config, noyau.transport…, et `import noyau.api` nu, qui lie le paquet noyau entier),
    un module frère ou du cœur (commandes.x, moteurs.claude, vues.y, interface…), un import relatif, un import dynamique (importlib, __import__,
    sys.modules SOUS TOUT NOM : `from sys import modules as m`, `import sys as s` puis `s.modules`, `os.sys.modules`, `getattr(sys, "modules")`), ce qui
    est trop dynamique pour être jugé (getattr au nom calculé, vars, globals, eval, exec…) et la lecture d'un attribut spécial (`f.__globals__`…, par où l'espace d'un module du noyau redeviendrait lisible)."""
    t = ast.parse(Path(fichier).read_text(encoding="utf-8")); r = []
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            for a in n.names:
                haut = a.name.split(".")[0]
                if haut == "noyau" and not (a.name == "noyau.api" and a.asname): r.append((f"import {a.name}" + (f" as {a.asname}" if a.asname else ""), n.lineno))
                elif haut != "noyau" and haut not in SURS: r.append((f"import {a.name}", n.lineno))
        elif isinstance(n, ast.ImportFrom):
            m = n.module or ""; haut = m.split(".")[0]; noms = [a.name for a in n.names]
            if n.level or not m: r.append((f"from {'.' * n.level}{m} import {', '.join(noms)}", n.lineno))
            elif haut == "noyau" and not (m == "noyau.api" or m == "noyau" and noms == ["api"]): r.append((f"from {m} import {', '.join(noms)}", n.lineno))
            elif m == "noyau.api" and set(noms) & {"actions", "*"}: r.append((f"from {m} import {', '.join(noms)}", n.lineno))   # renvoi n° 83 : aucun accès à l'action
            elif haut != "noyau" and haut not in SURS: r.append((f"from {m} import {', '.join(noms)}", n.lineno))
            elif m == "sys" and set(noms) & ATTRIBUTS_FERMES: r.append((f"from sys import {', '.join(noms)}", n.lineno))   # sys.modules sous un autre nom
        elif isinstance(n, ast.Name) and n.id in NOMS_FERMES: r.append((n.id, n.lineno))
        elif isinstance(n, ast.Attribute) and _ferme(n.attr): r.append((f".{n.attr}", n.lineno))   # quel que soit l'objet : sys, un alias, os.sys…
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("getattr", "setattr", "delattr", "hasattr"):
            nom = n.args[1] if len(n.args) > 1 else None
            if not (isinstance(nom, ast.Constant) and isinstance(nom.value, str)): r.append((f"{n.func.id} au nom calculé", n.lineno))
            elif _ferme(nom.value): r.append((f"{n.func.id}(…, {nom.value!r})", n.lineno))
    return r


ATTRIBUTS_FERMES = {"modules", "_getframe", "actions"}     # sys.modules rend tout module chargé (noyau.config…) ; _getframe, les espaces des appelants ;
                                                              # actions : l'accès aux services d'action, sous tout nom d'objet (renvoi n° 83)
NOMS_FERMES = {"__import__", "__builtins__", "eval", "exec", "compile", "vars", "globals", "locals", "breakpoint"}   # trop dynamiques pour être jugés
def _ferme(attr): return attr in ATTRIBUTS_FERMES or attr.startswith("__") and attr.endswith("__")


def ecarts_contrat(fichier):
    """Tout ce qui sort du contrat pour un module : imports interdits, puis noms lus hors de l'API et de sa propre portée module."""
    return imports_interdits(fichier) + noms_libres(fichier)


# 1. contrat statique : chaque vue
for f in sorted((SRC / "bin/vues").glob("*.py")):
    if f.name.startswith("_"): continue
    mauvais = ecarts_contrat(f)
    dire(not mauvais, f"{f.name} : n'emploie que l'API du noyau et la bibliothèque standard" + (f" — hors API : {mauvais}" if mauvais else ""))

# 1b. contrat statique : chaque moteur (lot 2) n'emploie que l'API, la bibliothèque standard, BASE_NOYAU (noms du noyau hors API) et ce que le cœur
#     lui prête (COEUR_*, branché par bin/berger jusqu'au lot 4) ; ces listes sont lues dans bin/moteurs/__init__.py
_init = ast.parse((SRC / "bin/moteurs/__init__.py").read_text(encoding="utf-8"))
LISTES = {n.targets[0].id: ast.literal_eval(n.value) for n in _init.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
          and n.targets[0].id in ("COEUR_FONCTIONS", "COEUR_CONSTANTES", "BASE_NOYAU")}
prete = set(LISTES["COEUR_FONCTIONS"]) | set(LISTES["COEUR_CONSTANTES"]) | set(LISTES["BASE_NOYAU"]) | {"executable_moteur", "version_moteur", "verdict_moteur"}
fichiers_moteurs = sorted(f for f in (SRC / "bin/moteurs").glob("*.py") if not f.name.startswith("_"))
dire({"claude.py", "codex.py"} <= {f.name for f in fichiers_moteurs}, "un fichier par moteur : bin/moteurs/claude.py et codex.py")
libres_ok |= prete
for f in fichiers_moteurs:
    mauvais = ecarts_contrat(f)
    dire(not mauvais, f"moteurs/{f.name} : n'emploie que l'API, BASE_NOYAU et ce que le cœur lui prête" + (f" — hors liste : {mauvais}" if mauvais else ""))
libres_ok -= prete

# 1c. contrat statique : chaque famille de commandes (lot 3) n'emploie QUE l'API du noyau et la bibliothèque standard — aucune exception : ni nom privé du
#     noyau, ni fonction ou constante du cœur prêtée (relecture du 28/10). Un verbe qui en aurait besoin reste dans bin/berger jusqu'au lot 4.
#     Seule la famille de transition reçoit une chose, VERBES_COEUR (le registre des verbes du cœur, qu'elle ne fait qu'inscrire).
fichiers_commandes = sorted(f for f in (SRC / "bin/commandes").glob("*.py") if not f.name.startswith("_"))
dire({"alire.py", "veille.py", "etat.py", "vues.py", "bureau.py", "journal.py", "missions.py", "messages.py", "besoins.py", "equipes.py", "transition.py"} <= {f.name for f in fichiers_commandes},
     "une famille par fichier : alire, veille, etat, vues, bureau, journal, missions, messages, besoins, equipes et la transition (bin/commandes/)")
_cinit = (SRC / "bin/commandes/__init__.py").read_text(encoding="utf-8")
dire(not re.search(r"COEUR_FONCTIONS|COEUR_CONSTANTES|COMMANDES_NOYAU|def brancher", _cinit), "bin/commandes/__init__.py ne prête rien : ni liste COEUR_*, ni COMMANDES_NOYAU, ni brancher")
ACTIONS = tuple(getattr(api, "ACTIONS", ()))                 # lot 4a : l'API d'ACTION (services du noyau), donnée aux seules familles de commandes
libres_ok |= set(ACTIONS)
for f in fichiers_commandes:
    if f.name == "__init__.py": continue                      # le paquet est du cœur (comme moteurs/__init__.py) : il n'est pas un module écartable
    if f.name == "transition.py": libres_ok.add("VERBES_COEUR")
    mauvais = ecarts_contrat(f)
    libres_ok.discard("VERBES_COEUR")
    dire(not mauvais, f"commandes/{f.name} : n'emploie que l'API du noyau (lecture et action) et la bibliothèque standard" + (f" — hors API : {mauvais}" if mauvais else ""))
libres_ok -= set(ACTIONS)

# 1c bis. Le contrat statique doit REFUSER ce qui le contournait (relecture Codex du 28/10) : un import du noyau hors noyau.api (tout nom importé devenait
#     un nom permis), un import d'un module frère, un import dynamique, et un nom défini dans UNE portée lu dans une autre. Fichiers jetables, posés ici.
_REFUSES = {
    "import du noyau hors API (from noyau.config import COFFRE)": "from noyau.config import COFFRE\ndef rendre(w, h, a=None): return [COFFRE]\n",
    "import du noyau hors API (import noyau.config as c)": "import noyau.config as c\ndef rendre(w, h, a=None): return [c.COFFRE]\n",
    "import du noyau hors API (from noyau import transport)": "from noyau import transport\ndef rendre(w, h, a=None): return [transport]\n",
    "import du noyau hors API (import noyau.api, qui lie noyau)": "import noyau.api\ndef rendre(w, h, a=None): return [noyau.config.COFFRE]\n",
    "import du noyau hors API (import noyau)": "import noyau\ndef rendre(w, h, a=None): return [noyau]\n",
    "import d'un module frère (import commandes.alire)": "import commandes.alire\nVERBES = {}\n",
    "import d'un module frère (from commandes import alire)": "from commandes import alire\nVERBES = {}\n",
    "import d'un module frère (from moteurs import claude)": "from moteurs import claude\nNOM = 'x'\n",
    "import d'un module frère (import moteurs.claude as c)": "import moteurs.claude as c\nNOM = 'x'\n",
    "import d'un module frère (import vues.fiche)": "import vues.fiche\n",
    "import relatif (from . import alire)": "from . import alire\n",
    "import du cœur (import interface)": "import interface\n",
    "import dynamique (importlib)": "import importlib\nm = importlib.import_module('noyau.config')\n",
    "import dynamique (__import__)": "m = __import__('noyau.config')\n",
    "import dynamique (sys.modules)": "m = sys.modules['noyau.config']\n",
    # renvoi n° 77 (Codex) : sys.modules par un ALIAS, et les équivalents simples (refusés s'ils visent le noyau, ou tout court s'ils sont trop dynamiques)
    "sys.modules par alias (from sys import modules)": "from sys import modules\nx = modules['noyau.config'].COFFRE\n",
    "sys.modules par alias (from sys import modules as m)": "from sys import modules as m\nx = m['noyau.config'].COFFRE\n",
    "sys.modules par alias (import sys as s)": "import sys as s\nx = s.modules['noyau.config'].COFFRE\n",
    "sys.modules par un autre chemin (os.sys.modules)": "x = os.sys.modules['noyau.config'].COFFRE\n",
    "sys.modules par getattr (littéral)": "x = getattr(sys, 'modules')['noyau.config'].COFFRE\n",
    "sys.modules par getattr (alias)": "import sys as s\nx = getattr(s, 'modules')['noyau.config'].COFFRE\n",
    "getattr au nom calculé (trop dynamique)": "n = 'mod' + 'ules'\nx = getattr(sys, n)\n",
    "vars(sys) (trop dynamique)": "x = vars(sys)['modules']\n",
    "importlib.import_module('noyau.config')": "import importlib\nx = importlib.import_module('noyau.config').COFFRE\n",
    "from importlib import import_module": "from importlib import import_module as im\nx = im('noyau.config').COFFRE\n",
    "__import__('noyau.config') (littéral)": "x = __import__('noyau.config').config.COFFRE\n",
    "eval d'un import (trop dynamique)": "x = eval(\"__imp\" + \"ort__('noyau.config')\")\n",
    "attribut spécial (__globals__)":"def rendre(w, h, a=None): return [conf.__globals__['COFFRE']]\n",
    "portées mélangées (nom local d'une fonction lu dans une autre)": "def f():\n    COFFRE = 1\n    return COFFRE\ndef g():\n    return COFFRE\n",
    "portées mélangées (nom de classe lu dans une méthode)": "class C:\n    masques = 1\n    def m(self): return masques\n",
}
_ACCEPTES = {
    "from noyau.api import API": "from noyau.api import API\nX = API\n", "from noyau import api": "from noyau import api\nX = api.API\n",
    "import noyau.api as api": "import noyau.api as api\nX = api.API\n", "bibliothèque standard": "import json, os.path\nfrom pathlib import Path\nX = (json, os, Path)\n",
    "fermeture": "def f():\n    x = 1\n    def g(): return x\n    return g\n", "global déclaré": "def f():\n    global Z\n    Z = 1\ndef g(): return Z\n",
    "compréhension": "def f(t): return [y for y in t if y]\n", "getattr au nom littéral ordinaire": "def f(o): return getattr(o, 'titre', None)\n",
    "re.compile (un attribut, pas le builtin)": "MOTIF = re.compile('x')\n", "from sys import argv": "from sys import argv\nX = argv\n", "nom de l'API": "def rendre(w, h, a=None): return [conf(a)]\n",
}
with tempfile.TemporaryDirectory() as _tmp:
    for _jeu, _attendu in ((_REFUSES, True), (_ACCEPTES, False)):
        for _cas, _src in _jeu.items():
            _f = Path(_tmp) / "zz_jetable.py"; _f.write_text(_src, encoding="utf-8"); _vu = ecarts_contrat(_f)
            dire(bool(_vu) == _attendu, f"preuve : {_cas} — " + ("refusé" if _attendu else "accepté") + f" par le contrat statique ({_vu or 'aucun écart'})")


# 1d. lot 3 bis : les noms ajoutés à l'API pour les verbes déplacés. Chacun : défini dans son module du noyau, listé dans l'API, employé par son verbe dans la
#     famille indiquée, ABSENT du cœur (déplacé, pas copié) ; et sa fermeture d'appels (dans le noyau) ne touche aucun chemin réservé au lot 4.
NOUVEAUX = {                       # nom : (module du noyau, famille qui l'emploie)
    "Refus": ("ecarts", "journal"), "liste_vues": ("registre", "vues"), "etat": ("ecrans", "etat"),
    "validations": ("ecrans", "etat"),
    "suivi": ("missions", "missions"), "rapport_mission": ("missions", "missions"),            # lot 4a : les LECTURES des missions
    "besoins": ("lectures", "besoins"),                                                         # lot 4b : la LECTURE des besoins
    "equipe_liste": ("equipes", "equipes"), "projet_liste": ("equipes", "equipes"),             # lot 4c : les LECTURES des équipes
    "domaines_projet": ("equipes", "equipes"),
}   # journal et notifier (lot 3 bis) ÉCRIVENT : au lot 4b ils passent dans l'API d'ACTION, mêmes vérifications en 1g (NOUVELLES_ACTIONS) ;
    # lire_document, lire_interactif (marquent lu), mettre_a_jour_titres (renomme les panneaux Herdr), statusline (relève le quota) : au lot 4c (1h, NOYAU_4C)
INTERDITS = {"demarrer_agent", "COFFRE", "valeurs_coffre", "coffre_sauvegarder", "masques", "cloisons", "reglages_claude", "config_codex", "hooks_codex",
             "ecrire_regles", "ecrire_mcp_claude", "ecrire_reseau_claude", "env_appelant", "reglages_strict_externe", "consigne_systeme", "ouvrir_en_mission",
             "message_remettre", "echange", "decider", "sauvegarder", "secrets_audit_silencieux", "installer", "lier_skills", "equipes", "enveloppe_mcp", "_transport"}
def _defs_source(texte):
    """{nom: nœud} des définitions de premier niveau d'un source ; et les noms que ce source importe."""
    t = ast.parse(texte); r = {}; imp = set()
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)): r[n.name] = n
        elif isinstance(n, ast.Assign):
            for tg in n.targets:
                for x in ast.walk(tg):
                    if isinstance(x, ast.Name): r[x.id] = n
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for al in n.names: imp.add((al.asname or al.name).split(".")[0])
    return r, imp
def _defs_noyau(module): return _defs_source((SRC / f"bin/noyau/{module}.py").read_text(encoding="utf-8"))[0]
_tout = {m.stem: _defs_noyau(m.stem) for m in (SRC / "bin/noyau").glob("*.py") if m.stem not in ("api", "__init__")}
_plat = {k: v for d in _tout.values() for k, v in d.items()}
_imports = set().union(*(_defs_source((m).read_text(encoding="utf-8"))[1] for m in (SRC / "bin/noyau").glob("*.py") if m.stem not in ("api", "__init__")))
_vues_fn = {}                                   # nom de fonction de vue -> nœuds (bin/vues/*.py) : cibles des appels dynamiques (m.donnees(a), m.rendre(…), VUES[x].vue_x(…))
_vue_de = {}                                    # id(nœud) -> définitions de son fichier de vue (ses noms propres : donnees, rendu_texte, constantes…)
for f in sorted((SRC / "bin/vues").glob("*.py")):
    _d = _defs_source(f.read_text(encoding="utf-8"))[0]
    for k, v in _d.items():
        _vue_de[id(v)] = _d
        if isinstance(v, ast.FunctionDef): _vues_fn.setdefault(k, []).append(v)
_coeur = {n.name for n in ast.parse((SRC / "bin/berger").read_text(encoding="utf-8")).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
def _globales(n):
    """Noms lus comme GLOBAUX (ou libres du module) dans la fonction `n` et tout ce qu'elle contient, d'après le module standard `symtable` (qui gère
    global, nonlocal, les classes et les fonctions imbriquées : on ne réécrit pas les portées à la main). None si `n` n'est pas une fonction."""
    if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): return None
    import symtable
    try: racine = symtable.symtable(ast.unparse(n), "<fonction>", "exec")
    except SyntaxError: return None
    out = set(); pile = [racine]
    while pile:
        t = pile.pop(); pile.extend(t.get_children())
        # le module factice (racine) ne contient que la fonction : son nom n'est pas lu, mais les VALEURS PAR DÉFAUT des paramètres (aussi des paramètres
        # nommés seuls), les décorateurs et les annotations s'évaluent DANS la racine : leurs noms sont lus comme globaux
        out |= {x.get_name() for x in t.get_symbols() if x.is_referenced() and x.is_global()}
    return out


def _fermeture(depart, plat=None, vues=None):
    """(noms du noyau atteints, noms LIBRES atteints) à partir d'un nœud ou d'un nom du noyau. Suit les noms du noyau ET les appels dynamiques vers les vues
    (tout `x.f(…)` dont `f` est une fonction de vue : on y va, comme au chargement) ; un nom introuvable (ni noyau, ni bibliothèque standard, ni builtin, ni
    local) est LIBRE : ce que le cœur injecte au démarrage (masques, cloisons…) ou un nom du cœur."""
    plat = _plat if plat is None else plat; vues = _vues_fn if vues is None else vues
    vu_noms, libres, vus, pile = set(), set(), set(), [plat[depart] if isinstance(depart, str) else depart]
    if isinstance(depart, str): vu_noms.add(depart)
    while pile:
        n = pile.pop(); propres = _vue_de.get(id(n), {})
        if id(n) in vus: continue
        vus.add(id(n))
        loc = {x.id for x in ast.walk(n) if isinstance(x, ast.Name) and isinstance(x.ctx, (ast.Store, ast.Del))} | {x.arg for x in ast.walk(n) if isinstance(x, ast.arg)}
        loc |= {x.name for x in ast.walk(n) if isinstance(x, ast.ExceptHandler) and x.name}
        globales = _globales(n)   # portée par symtable : une fonction définie DANS une fonction n'est locale que là où elle est visible (documents() : ajouter, parcourir)
        loc |= {(al.asname or al.name).split(".")[0] for x in ast.walk(n) if isinstance(x, (ast.Import, ast.ImportFrom)) for al in x.names}
        for x in ast.walk(n):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load) and (x.id in globales if globales is not None else x.id not in loc):
                if x.id in propres: pile.append(propres[x.id])
                elif x.id in plat:
                    vu_noms.add(x.id); pile.append(plat[x.id])
                elif x.id not in dir(builtins) and x.id not in _imports and x.id not in api.STDLIB and x.id != "__file__": libres.add(x.id)
            elif isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr in vues:
                pile += vues[x.func.attr]
    return vu_noms, libres
# La fermeture traite une fonction définie DANS une autre comme locale (documents() : ajouter, parcourir) sans ouvrir aucun accès :
# un appel à un nom interdit ou inconnu, même fait depuis la fonction imbriquée, reste atteint ou libre.
_imb = ast.parse("def f():\n    def ajouter(): return 1\n    def g(): return ajouter() + confier_mission() + nom_inconnu()\n    return g()\n").body[0]
_att, _lib = _fermeture(_imb, plat={}, vues={})
dire("ajouter" not in _lib and "g" not in _lib, f"fermeture : une fonction définie dans une autre est locale (libres : {sorted(_lib)})")
_att2, _lib2 = _fermeture(ast.parse("def f():\n    def g():\n        def masques(): return 1\n        return masques()\n    def h(): return masques()\n    return g() + h()\n").body[0], plat={}, vues={})
_cas_portee = {
    "global déclaré dans la fonction imbriquée": "def f():\n    def g():\n        global masques\n        return masques()\n    def masques(): return 1\n    return g()\n",
    "nom défini dans une classe, appelé depuis une méthode": "def f():\n    class C:\n        def masques(self): return 1\n        def m(self): return masques()\n    return C().m()\n",
    "nom défini dans la méthode d'une voisine": "def f():\n    class C:\n        def a(self):\n            def masques(): return 1\n            return masques()\n        def b(self): return masques()\n    return C()\n",
}
for _nom, _src in _cas_portee.items():
    _a3, _l3 = _fermeture(ast.parse(_src).body[0], plat={}, vues={})
    dire("masques" in _l3, f"fermeture (symtable) : {_nom} — l'appel global masques() reste signalé (libres : {sorted(_l3)})")
for _nom, _src, _attendu in (("valeur par défaut d'un paramètre", "def sonde(a, lecture=identite_donnees):\n    return lecture(a)\n", "identite_donnees"),
                             ("valeur par défaut d'un paramètre nommé seul", "def sonde(a, *, lecture=identite_donnees):\n    return lecture(a)\n", "identite_donnees"),
                             ("valeur par défaut d'un paramètre d'une fonction imbriquée", "def f():\n    def g(lecture=identite_donnees): return lecture(1)\n    return g()\n", "identite_donnees"),
                             ("valeur par défaut qui est un paramètre local de la fonction englobante", "def f(identite_donnees):\n    def g(lecture=identite_donnees): return lecture(1)\n    return g()\n", None)):
    _a4, _l4 = _fermeture(ast.parse(_src).body[0], plat={}, vues={})
    dire((_attendu in _l4) if _attendu else ("identite_donnees" not in _l4), f"fermeture (symtable) : {_nom} — {'lu comme nom global' if _attendu else 'local, pas global'} (libres : {sorted(_l4)})")
_a3, _l3 = _fermeture(ast.parse("def f():\n    x = 1\n    def g(y):\n        z = y + x\n        return ajouter(z)\n    def ajouter(v): return v\n    return g(2)\n").body[0], plat={}, vues={})
dire(not _l3, f"fermeture (symtable) : arguments, variables locales, nom englobant et fonction imbriquée visible ne sont pas libres (libres : {sorted(_l3)})")
dire("masques" in _lib2, f"fermeture : une fonction « masques » imbriquée AILLEURS ne cache pas un vrai appel global masques() (portée par fonction ; libres : {sorted(_lib2)})")
dire({"confier_mission", "nom_inconnu"} <= _lib, f"fermeture : un nom interdit ou inconnu appelé depuis la fonction imbriquée reste signalé (libres : {sorted(_lib)})")
for nom, (module, famille) in NOUVEAUX.items():
    _ff = SRC / f"bin/commandes/{famille}.py"; texte_famille = _ff.read_text(encoding="utf-8") if _ff.is_file() else ""
    if nom not in _plat: dire(False, f"API : {nom} absent du noyau (noyau/{module}.py)"); continue
    dire(nom in _tout.get(module, {}) and nom in api.API and re.search(r"\b%s\(" % nom, texte_famille) and nom not in _coeur,
         f"API : {nom} est défini dans noyau/{module}.py, listé dans l'API, employé par commandes/{famille}.py et absent du cœur")
    atteints, libres = _fermeture(nom)
    mauvais = (atteints | libres) & INTERDITS
    dire(not mauvais and not libres, f"API : {nom} ne passe par aucun chemin réservé au lot 4 ni par aucun nom que le noyau ne définit pas" + (f" — {sorted(mauvais | libres)}" if mauvais or libres else ""))
for module in ("registre", "ecrans", "bandeaux", "missions", "actions", "equipes"):
    if not (SRC / f"bin/noyau/{module}.py").is_file(): dire(False, f"noyau/{module}.py existe"); continue
    mauvais = noms_libres(SRC / f"bin/noyau/{module}.py")
    mauvais = [m for m in mauvais if m[0] not in _plat]
    dire(not mauvais, f"noyau/{module}.py ne cite que des noms du noyau, de la bibliothèque standard ou de ses voisins (aucun nom du cœur)" + (f" — {mauvais}" if mauvais else ""))

# 1d bis. L'analyse doit ÉCHOUER sur ce qu'elle doit refuser (relecture du 28/10) : (1) l'ancien `commande_vue` — un appel dynamique m.donnees(a) — atteint `masques`
#     par vues/fiche.py → identite_donnees ; (2) une fonction qui appelle directement `demarrer_agent` ; (3) un nom absent du noyau n'est pas ignoré.
_cv, _ = _defs_source("def commande_vue(args):\n    m = VUES['fiche']\n    return m.donnees(args[0])\n")
atteints, libres = _fermeture(_cv["commande_vue"])
dire("masques" in (atteints | libres) and "masques" in INTERDITS, "preuve : la fermeture d'un appel dynamique de vue (m.donnees → vues/fiche.py → identite_donnees) atteint masques, qui est interdit")
_fx, _ = _defs_source("def faux(a):\n    return demarrer_agent(a)\n")
atteints, libres = _fermeture(_fx["faux"])
dire("demarrer_agent" in libres and "demarrer_agent" in INTERDITS, "preuve : un appel direct à demarrer_agent est signalé (nom libre et interdit)")
_fy, _ = _defs_source("def faux2(a):\n    return inconnu_du_noyau(a)\n")
dire(_fermeture(_fy["faux2"])[1] == {"inconnu_du_noyau"}, "preuve : un nom absent du noyau est suivi, pas ignoré")

# 1e. lot 3 bis : le paquet bin/commandes/ se charge SEUL, sans config.toml ni environnement (les tests de forme d'accès le chargent ainsi) : il n'importe que noyau.api, noyau.ecarts et noyau.actions (aucun import lourd)
r = subprocess.run([sys.executable, "-I", "-c", "import sys, importlib.util\nsys.path.insert(0, %r)\nsp = importlib.util.spec_from_file_location('commandes_seul', %r)\n"
                    "m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); print('ok')" % (str(SRC / "bin"), str(SRC / "bin/commandes/__init__.py"))],
                   env={}, capture_output=True, text=True)
dire(r.stdout.strip() == "ok", f"bin/commandes/ se charge sans config.toml ni environnement ({r.stderr.strip()[-120:] or 'ok'})")

# 1f. lot 4a : la famille « missions » et l'API d'ACTION. Les LECTURES (suivi, rapport_mission) sont des noms de l'API ; les ACTIONS (confier_mission,
#     terminer_mission) sont des services du noyau (noyau/actions.py) que seules les familles de commandes reçoivent, jamais une vue ni un moteur. Les
#     contrôles (agent inscrit, une mission à la fois, plafond [missions] max, moteur et modèle, checklist finie, refus de fusion) restent DANS le service :
#     la famille n'en fait aucun. Ce qui passe par demarrer_agent ou le mur (ouvrir_en_mission, espace, fermer_mission…) reste au cœur, jamais dans une famille.
dire(ACTIONS[:2] == ("confier_mission", "terminer_mission"), f"API d'action (noyau/api.py ACTIONS) : confier_mission, terminer_mission ({ACTIONS or 'absente'})")
dire(not set(ACTIONS) & set(api.API), "l'API d'action est À PART de l'API de lecture (aucun nom dans les deux : une vue ne la reçoit pas)")
_act = _tout.get("actions", {})
_DU_NOYAU = ("journal", "notifier", "lire_document", "lire_interactif", "mettre_a_jour_titres", "statusline")
dire(all(n in _act and isinstance(_act[n], ast.FunctionDef) for n in ACTIONS if n not in _DU_NOYAU) and ACTIONS and not set(ACTIONS) & _coeur,
     "chaque service d'action est une fonction de noyau/actions.py (journal, notifier, lire_document… : celles du noyau, lots 4b et 4c, vérifiées en 1g et 1h), absente du cœur")
_fm = SRC / "bin/commandes/missions.py"
_src_m = _fm.read_text(encoding="utf-8") if _fm.is_file() else ""
_verbes_m = next((sorted(ast.literal_eval(k) for k in n.value.keys) for n in ast.parse(_src_m).body
                  if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "VERBES" and isinstance(n.value, ast.Dict)), [])
dire(_verbes_m == ["fin-mission", "mission", "rapport-mission", "suivi"], f"commandes/missions.py : la famille des missions, verbes mission, suivi, rapport-mission, fin-mission ({_verbes_m or 'absente'})")
_noms_m = {x.id for x in ast.walk(ast.parse(_src_m)) if isinstance(x, ast.Name)}
CONTROLES = {"MISSIONS", "missions_comptees", "chefs", "decider_mission", "moteurs", "mission_finie", "refus_fusion_proprietaire", "agent_vivant", "espace_ouvert",
             "demarrer_agent", "ouvrir_en_mission", "fermer_mission", "espace", "parler", "echange", "journal", "mission", "fin_mission", "brancher"}
dire(_src_m and not _noms_m & CONTROLES and "MISSION.md" not in _src_m and "max" not in _src_m,
     "la famille ne fait AUCUN contrôle elle-même (ni plafond, ni moteur, ni checklist) et n'appelle rien du cœur : ses verbes aiguillent vers des services"
     + (f" — {sorted(_noms_m & CONTROLES)}" if _noms_m & CONTROLES else ""))
dire({"confier_mission", "terminer_mission", "suivi", "rapport_mission"} <= _noms_m, "ses verbes passent par les lectures (suivi, rapport_mission) et les services d'action (confier_mission, terminer_mission)")
_REFUSES_4A = {
    "service importé hors API (from noyau.actions import confier_mission)": "from noyau.actions import confier_mission\nVERBES = {'x': confier_mission}\n",
    "module des services importé (import noyau.actions as a)": "import noyau.actions as a\nX = a.brancher\n",
    "branchement des services (brancher)": "def verbe(args, prive=False): return brancher(confier_mission=print)\n",
    "registre des services (_SERVICES)": "def verbe(args, prive=False): return _SERVICES['confier_mission']\n",
    "service du cœur appelé directement (mission)": "def verbe(args, prive=False): return mission(args[0], 'x', 'Proprio')\n",
    "service du cœur appelé directement (fin_mission)": "def verbe(args, prive=False): return fin_mission(args[0], 'Proprio')\n",
    "lancement d'un agent (demarrer_agent)": "def verbe(args, prive=False): return demarrer_agent(args[0], 'claude', 'p1')\n",
    "ouverture en mission (ouvrir_en_mission)": "def verbe(args, prive=False): return ouvrir_en_mission(args[0], 'hote', 'claude')\n",
    "contrôle du cœur refait dans la famille (missions_comptees)": "def verbe(args, prive=False): return len(missions_comptees())\n",
    "fermeture du panneau (fermer_mission)": "def verbe(args, prive=False): return fermer_mission(args[0])\n",
}
libres_ok |= set(ACTIONS)
for _cas, _texte in _REFUSES_4A.items():
    with tempfile.TemporaryDirectory() as _tmp:
        _f = Path(_tmp) / "zz_famille.py"; _f.write_text(_texte, encoding="utf-8"); _vu = ecarts_contrat(_f)
        dire(bool(_vu), f"preuve 4a (famille) : {_cas} — refusé par le contrat statique ({_vu or 'aucun écart'})")
with tempfile.TemporaryDirectory() as _tmp:
    _f = Path(_tmp) / "zz_famille.py"; _f.write_text("def verbe(args, prive=False): return confier_mission(args[0], 'x', PROPRIETAIRE)\n", encoding="utf-8")
    dire(not ecarts_contrat(_f) and bool(ACTIONS), "preuve 4a (famille) : un service d'action (confier_mission) est accepté dans une famille de commandes")
libres_ok -= set(ACTIONS)
with tempfile.TemporaryDirectory() as _tmp:
    for _n in ("confier_mission", "terminer_mission"):
        _f = Path(_tmp) / "zz_vue.py"; _f.write_text(f"def rendre(w, h, a=None): return [{_n}(a, 'x', 'y')]\n", encoding="utf-8"); _vu = ecarts_contrat(_f)
        dire(bool(_vu), f"preuve 4a (vue) : une vue qui appelle {_n} est refusée (l'API d'action n'est pas celle des vues) ({_vu or 'aucun écart'})")

# 1f bis. renvoi n° 83 (Codex, bloquant) : l'API d'action ne doit être atteignable par AUCUN import, ni directement ni indirectement, depuis une vue, un moteur
#     ou une famille (une famille reçoit les services de son chargeur, elle n'a rien à importer). Avant : `from noyau.api import actions` passait le contrat,
#     puis actions()["terminer_mission"](…) agissait depuis une vue.
_ACCES_ACTION = {
    "from noyau.api import actions": "from noyau.api import actions\ndef rendre(w, h, a=None): return [actions()['terminer_mission'](a, PROPRIETAIRE)]\n",
    "from noyau.api import actions as x": "from noyau.api import actions as x\nX = x\n",
    "from noyau.api import *": "from noyau.api import *\nX = 1\n",
    "import noyau.api as x ; x.actions()": "import noyau.api as x\ndef rendre(w, h, a=None): return [x.actions()['terminer_mission'](a, PROPRIETAIRE)]\n",
    "from noyau import api ; api.actions": "from noyau import api\nF = api.actions\n",
    "from noyau import api as x ; getattr(x, 'actions')": "from noyau import api as x\nF = getattr(x, 'actions')\n",
    "import noyau.api as x ; y = x ; y.actions": "import noyau.api as x\ny = x\nF = y.actions\n",
    "import noyau.actions as x": "import noyau.actions as x\nF = x.terminer_mission\n",
    "from noyau.actions import terminer_mission": "from noyau.actions import terminer_mission\nF = terminer_mission\n",
}
with tempfile.TemporaryDirectory() as _tmp:
    for _rang, _ajout in (("vue", set()), ("moteur", set()), ("famille", set(ACTIONS))):
        libres_ok |= _ajout
        for _cas, _texte in _ACCES_ACTION.items():
            _f = Path(_tmp) / "zz_acces.py"; _f.write_text(_texte, encoding="utf-8"); _vu = imports_interdits(_f)
            dire(bool(_vu), f"preuve 4a ({_rang}) : accès à l'API d'action par import refusé — {_cas} ({_vu or 'aucun écart'})")
        libres_ok -= _ajout

# 1g. lot 4b : les familles « messages » et « besoins ». La LECTURE (besoins) est un nom de l'API ; les ACTIONS (déposer, remettre, suivre une délégation,
#     poser une question, parler, tracer un échange, ranger, clore, annoncer un outil) sont des services de noyau/actions.py, réservés aux familles. Les gestes
#     restent au cœur (message_deposer, parler, demander…), et les contrôles avec eux : droits entre agents (ecrire:, deleguer:) et débit d'ecrire au courtier ;
#     gardien, clôture, agent sans panneau, bascule de moteur derrière le service. journal et notifier ÉCRIVENT : ils quittent l'API de lecture pour l'API
#     d'action (aucune vue ni aucun moteur ne les emploie ; bin/moteurs/__init__.py, le noyau des moteurs, les importe du noyau par leur nom).
ACTIONS_4B = ("deposer_message", "remettre_messages", "suivre_delegation", "poser_question", "parler_agent", "tracer_echange", "ranger_besoin",
              "clore_besoin", "annoncer_outil")
NOUVELLES_ACTIONS = {"journal": ("agents", "journal"), "notifier": ("bandeaux", "bureau")}      # nom : (module du noyau, famille qui l'emploie)
dire(ACTIONS[:13] == ("confier_mission", "terminer_mission") + ACTIONS_4B + tuple(NOUVELLES_ACTIONS),
     f"API d'action : les services des missions, puis des messages et des besoins, puis journal et notifier ({ACTIONS})")
dire(not set(NOUVELLES_ACTIONS) & set(api.API), "journal et notifier ne sont plus dans l'API de lecture : une vue ou un moteur ne les reçoit pas")
for nom, (module, famille) in NOUVELLES_ACTIONS.items():
    texte_famille = (SRC / f"bin/commandes/{famille}.py").read_text(encoding="utf-8")
    dire(nom in _tout.get(module, {}) and nom in ACTIONS and re.search(r"\b%s\(" % nom, texte_famille) and nom not in _coeur and nom not in _act,
         f"API d'action : {nom} est défini dans noyau/{module}.py (une seule définition), listé dans ACTIONS, employé par commandes/{famille}.py et absent du cœur")
    atteints, libres = _fermeture(nom)
    mauvais = (atteints | libres) & INTERDITS
    dire(not mauvais and not libres, f"API d'action : {nom} ne passe par aucun chemin réservé au lot 4 ni par aucun nom que le noyau ne définit pas" + (f" — {sorted(mauvais | libres)}" if mauvais or libres else ""))
_verbes_4b = {}
for _fam in ("messages", "besoins"):
    _f4 = SRC / f"bin/commandes/{_fam}.py"; _src4 = _f4.read_text(encoding="utf-8") if _f4.is_file() else ""
    _verbes_4b[_fam] = (_src4, next((sorted(ast.literal_eval(k) for k in n.value.keys) for n in ast.parse(_src4).body
                                    if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "VERBES" and isinstance(n.value, ast.Dict)), []))
dire(_verbes_4b["messages"][1] == ["delegation-suivi", "demander", "echange", "message-deposer", "message-remettre", "parler", "parler-interactif"],
     f"commandes/messages.py : message-deposer, message-remettre, delegation-suivi, demander, parler, parler-interactif, echange ({_verbes_4b['messages'][1] or 'absente'})")
dire(_verbes_4b["besoins"][1] == ["annonce-outil", "besoin", "besoin-ranger"], f"commandes/besoins.py : besoin, besoin-ranger, annonce-outil ({_verbes_4b['besoins'][1] or 'absente'})")
CONTROLES_4B = {"message_deposer", "message_remettre", "delegation_suivi", "demander", "parler", "echange", "besoin_ranger", "besoin_clore", "annonce_outil",
                "gardien", "BESOINS", "CONSIGNES", "debit_ecrire", "droits", "solliciter", "herdr_api", "herdr", "fcntl", "a_l_outil", "ecrire_regles",
                "bac_a_sable_ok", "moteurs", "ouvert", "brancher", "_SERVICES", "_geste", "ECHANGES", "travail"}
for _fam, (_src4, _) in _verbes_4b.items():
    _noms4 = {x.id for x in ast.walk(ast.parse(_src4)) if isinstance(x, ast.Name)}
    dire(_src4 and not _noms4 & CONTROLES_4B and "fcntl" not in _src4 and "\"attente\"" not in _src4,
         f"commandes/{_fam}.py ne fait AUCUN contrôle ni geste lui-même (ni file, ni verrou, ni gardien, ni Herdr, ni moteur) : ses verbes aiguillent"
         + (f" — {sorted(_noms4 & CONTROLES_4B)}" if _noms4 & CONTROLES_4B else ""))
_n_m = {x.id for x in ast.walk(ast.parse(_verbes_4b["messages"][0])) if isinstance(x, ast.Name)}
_n_b = {x.id for x in ast.walk(ast.parse(_verbes_4b["besoins"][0])) if isinstance(x, ast.Name)}
dire(set(ACTIONS_4B[:6]) <= _n_m and {"ranger_besoin", "clore_besoin", "annoncer_outil", "besoins"} <= _n_b,
     "leurs verbes passent par la lecture (besoins) et les services d'action (deposer_message … annoncer_outil)")
_REFUSES_4B = {
    "service importé hors API (from noyau.actions import deposer_message)": "from noyau.actions import deposer_message\nVERBES = {'x': deposer_message}\n",
    "module des services importé (import noyau.actions)": "import noyau.actions\nX = 1\n",
    "journal pris dans le noyau (from noyau.agents import journal)": "from noyau.agents import journal\nX = journal\n",
    "notifier pris dans le noyau (from noyau.bandeaux import notifier)": "from noyau.bandeaux import notifier\nX = notifier\n",
    "module du noyau importé par le paquet (from noyau import agents)": "from noyau import agents\nX = agents.journal\n",
    "geste du cœur appelé directement (message_deposer)": "def verbe(args, prive=False): return message_deposer(args[0], args[1], 'x')\n",
    "geste du cœur appelé directement (message_remettre)": "def verbe(args, prive=False): return message_remettre(args[0])\n",
    "geste du cœur appelé directement (delegation_suivi)": "def verbe(args, prive=False): return delegation_suivi(args[0], args[1], {})\n",
    "geste du cœur appelé directement (demander)": "def verbe(args, prive=False): return demander(args[0], 'q')\n",
    "geste du cœur appelé directement (parler)": "def verbe(args, prive=False): return parler(args[0], 'x')\n",
    "geste du cœur appelé directement (echange)": "def verbe(args, prive=False): return echange('a', 'b', 'message', 'x')\n",
    "geste du cœur appelé directement (besoin_ranger)": "def verbe(args, prive=False): return besoin_ranger(args[0], 'outil', 'x')\n",
    "geste du cœur appelé directement (besoin_clore)": "def verbe(args, prive=False): return besoin_clore('1', 'fait', 'x')\n",
    "geste du cœur appelé directement (annonce_outil)": "def verbe(args, prive=False): return annonce_outil(args[0])\n",
    "contrôle du courtier refait dans la famille (debit_ecrire)": "def verbe(args, prive=False): return debit_ecrire(args[0], args[1])\n",
    "gardien lu hors API (gardien)": "def verbe(args, prive=False): return gardien()\n",
    "branchement des services (brancher)": "def verbe(args, prive=False): return brancher({'deposer_message': print})\n",
}
libres_ok |= set(ACTIONS)
for _cas, _texte in _REFUSES_4B.items():
    with tempfile.TemporaryDirectory() as _tmp:
        _f = Path(_tmp) / "zz_famille.py"; _f.write_text(_texte, encoding="utf-8"); _vu = ecarts_contrat(_f)
        dire(bool(_vu), f"preuve 4b (famille) : {_cas} — refusé par le contrat statique ({_vu or 'aucun écart'})")
with tempfile.TemporaryDirectory() as _tmp:
    _f = Path(_tmp) / "zz_famille.py"
    _f.write_text("def verbe(args, prive=False):\n    journal(args[0], 'x'); notifier('t', 'x')\n    return deposer_message(args[0], args[1], 'x'), ranger_besoin(args[0], 'outil', 'x'), besoins()\n", encoding="utf-8")
    dire(not ecarts_contrat(_f), f"preuve 4b (famille) : services d'action (deposer_message, ranger_besoin, journal, notifier) et lecture (besoins) acceptés dans une famille ({ecarts_contrat(_f) or 'aucun écart'})")
libres_ok -= set(ACTIONS)
with tempfile.TemporaryDirectory() as _tmp:
    _cas4 = [("vue", n, f"def rendre(w, h, a=None): return [{n}(a, 'x')]\n") for n in ACTIONS_4B + ("journal", "notifier")]
    _cas4 += [("moteur", n, f"def verdict(a): return {n}(a, 'x')\n") for n in ("journal", "notifier", "parler_agent", "deposer_message")]
    for _rang, _n, _texte in _cas4:
        _f = Path(_tmp) / f"zz_{_rang}.py"; _f.write_text(_texte, encoding="utf-8"); _vu = ecarts_contrat(_f)
        dire(bool(_vu), f"preuve 4b ({_rang}) : un(e) {_rang} qui appelle {_n} est refusé(e) (l'API d'action n'est pas la sienne) ({_vu or 'aucun écart'})")
# l'accès INDIRECT aux actions de 4b, pour les trois rangs : par un module du noyau qui porte le geste, par le paquet, par le module des services
_ACCES_4B = {
    "from noyau.agents import journal": "from noyau.agents import journal\nF = journal\n",
    "from noyau.bandeaux import notifier": "from noyau.bandeaux import notifier\nF = notifier\n",
    "from noyau import agents ; agents.journal": "from noyau import agents\nF = agents.journal\n",
    "import noyau.bandeaux as x ; x.notifier": "import noyau.bandeaux as x\nF = x.notifier\n",
    "import noyau.actions as x ; x.deposer_message": "import noyau.actions as x\nF = x.deposer_message\n",
    "from noyau.actions import services_commandes": "from noyau.actions import services_commandes\nF = services_commandes()['ranger_besoin']\n",
    "from noyau.api import ACTIONS ; getattr(api, ACTIONS[0])": "from noyau import api\nfrom noyau.api import ACTIONS\nF = getattr(api, ACTIONS[2])\n",
    "un service par l'espace d'une lecture (etat.__globals__)": "def rendre(w, h, a=None): return [etat.__globals__['journal'](a, 'x')]\n",
}
with tempfile.TemporaryDirectory() as _tmp:
    for _rang, _ajout in (("vue", set()), ("moteur", set()), ("famille", set(ACTIONS))):
        libres_ok |= _ajout
        for _cas, _texte in _ACCES_4B.items():
            _f = Path(_tmp) / "zz_acces.py"; _f.write_text(_texte, encoding="utf-8"); _vu = imports_interdits(_f)
            dire(bool(_vu), f"preuve 4b ({_rang}) : accès indirect à une action refusé — {_cas} ({_vu or 'aucun écart'})")
        libres_ok -= _ajout

# 1h. lot 4c : la famille « equipes ». Les LECTURES (equipe_liste, projet_liste, domaines_projet : noyau/equipes.py) sont des noms de l'API ; les ACTIONS
#     (ouvrir et fermer un développeur, changer un site permis, inscrire un go, ouvrir et fermer un projet, jouer le crochet) sont des services de
#     noyau/actions.py, réservés aux familles. Les gestes restent au cœur (equipe_ouvrir, equipe_fermer, equipe_domaine, equipe_go, projet_ouvrir,
#     projet_fermer, lancer_crochet_equipe), et les contrôles avec eux : rôle (chef seul, chef ou coordinateur), go inscrit, plafond [missions] max,
#     copie (clone, branche, travail non commité), modèle permis, membres. lire_document, lire_interactif (marquent un document lu), mettre_a_jour_titres
#     (renomme les panneaux Herdr) et statusline (relève le quota) ÉCRIVENT : ils quittent l'API de lecture pour l'API d'action, comme journal et notifier.
ACTIONS_4C = ("ouvrir_developpeur", "fermer_developpeur", "changer_domaine", "inscrire_go", "ouvrir_projet", "fermer_projet", "jouer_crochet")
NOYAU_4C = {"lire_document": ("ecrans", "alire"), "lire_interactif": ("ecrans", "alire"), "mettre_a_jour_titres": ("bandeaux", "bureau"),
            "statusline": ("bandeaux", "bureau")}                       # nom : (module du noyau, famille qui l'emploie)
LECTURES_4C = ("equipe_liste", "projet_liste", "domaines_projet")
dire(ACTIONS[13:] == ACTIONS_4C + tuple(NOYAU_4C), f"API d'action : puis les services des équipes et lire_document, lire_interactif, mettre_a_jour_titres, statusline ({ACTIONS[13:]})")
dire(not set(NOYAU_4C) & set(api.API), "lire_document, lire_interactif, mettre_a_jour_titres et statusline ne sont plus dans l'API de lecture : une vue ou un moteur ne les reçoit pas")
dire(set(LECTURES_4C) <= set(api.API) and not set(LECTURES_4C) & set(ACTIONS), "equipe_liste, projet_liste, domaines_projet sont des LECTURES (API), pas des actions")
dire(all(n in _act and isinstance(_act[n], ast.FunctionDef) for n in ACTIONS_4C) and not set(ACTIONS_4C) & _coeur,
     "chaque service des équipes est une fonction de noyau/actions.py, absente du cœur")
for nom, (module, famille) in NOYAU_4C.items():
    texte_famille = (SRC / f"bin/commandes/{famille}.py").read_text(encoding="utf-8")
    dire(nom in _tout.get(module, {}) and nom in ACTIONS and re.search(r"\b%s\(" % nom, texte_famille) and nom not in _coeur and nom not in _act,
         f"API d'action : {nom} est défini dans noyau/{module}.py (une seule définition), listé dans ACTIONS, employé par commandes/{famille}.py et absent du cœur")
    atteints, libres = _fermeture(nom)
    mauvais = (atteints | libres) & INTERDITS
    dire(not mauvais and not libres, f"API d'action : {nom} ne passe par aucun chemin réservé au lot 4 ni par aucun nom que le noyau ne définit pas" + (f" — {sorted(mauvais | libres)}" if mauvais or libres else ""))
_fe = SRC / "bin/commandes/equipes.py"; _src_e = _fe.read_text(encoding="utf-8") if _fe.is_file() else ""
_verbes_e = next((sorted(ast.literal_eval(k) for k in n.value.keys) for n in ast.parse(_src_e).body
                  if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "VERBES" and isinstance(n.value, ast.Dict)), [])
dire(_verbes_e == ["crochet-equipe", "equipe", "projet"], f"commandes/equipes.py : la famille des équipes, verbes equipe, projet, crochet-equipe ({_verbes_e or 'absente'})")
_noms_e = {x.id for x in ast.walk(ast.parse(_src_e)) if isinstance(x, ast.Name)}
CONTROLES_4C = {"equipe_ouvrir", "equipe_fermer", "equipe_domaine", "equipe_go", "projet_ouvrir", "projet_fermer", "lancer_crochet_equipe", "exiger_chef",
                "_equipe", "go_ouverture", "tracer_hors_go", "_portes_mod", "missions_comptees", "MISSIONS", "moteurs", "decider_mission", "_git", "_pile",
                "regenerer", "nouveau", "membres_possibles", "registre_projets", "dossier_projet", "valeurs_coffre", "mission", "fin_mission", "fermer_mission",
                "espace", "echange", "DOMAINE", "DOMAINES_MAX", "transport", "_transport", "subprocess", "shutil", "fcntl", "brancher", "_SERVICES", "_geste",
                "BERGER", "AGENTS", "conf", "dossier", "agents"}
dire(_src_e and not _noms_e & CONTROLES_4C and "fcntl" not in _src_e and "projets.json" not in _src_e and "git" not in _src_e,
     "commandes/equipes.py ne fait AUCUN contrôle ni geste lui-même (ni rôle, ni go, ni plafond, ni git, ni registre, ni shell) : ses verbes aiguillent"
     + (f" — {sorted(_noms_e & CONTROLES_4C)}" if _noms_e & CONTROLES_4C else ""))
dire(set(ACTIONS_4C) | set(LECTURES_4C) <= _noms_e, "ses verbes passent par les lectures (equipe_liste, projet_liste, domaines_projet) et les sept services d'action")
_REFUSES_4C = {
    "service importé hors API (from noyau.actions import ouvrir_developpeur)": "from noyau.actions import ouvrir_developpeur\nVERBES = {'x': ouvrir_developpeur}\n",
    "lecture prise dans son module (from noyau.equipes import equipe_liste)": "from noyau.equipes import equipe_liste\nX = equipe_liste\n",
    "module des équipes importé (import noyau.equipes as e)": "import noyau.equipes as e\nX = e.registre_projets\n",
    "lire_document pris dans le noyau (from noyau.ecrans import lire_document)": "from noyau.ecrans import lire_document\nX = lire_document\n",
    "statusline pris dans le noyau (from noyau.bandeaux import statusline)": "from noyau.bandeaux import statusline\nX = statusline\n",
    "geste du cœur appelé directement (equipe_ouvrir)": "def verbe(args, prive=False): return equipe_ouvrir('p', 's', 'x', 'chef')\n",
    "geste du cœur appelé directement (equipe_fermer)": "def verbe(args, prive=False): return equipe_fermer('p', 's', 'chef')\n",
    "geste du cœur appelé directement (equipe_domaine)": "def verbe(args, prive=False): return equipe_domaine('p', 'ajouter', 'a.org', 'coord')\n",
    "geste du cœur appelé directement (equipe_go)": "def verbe(args, prive=False): return equipe_go('p', 's', '1', 'spec.md', 'chef')\n",
    "geste du cœur appelé directement (projet_ouvrir)": "def verbe(args, prive=False): return projet_ouvrir('p', 'x', 'chef', 'chef')\n",
    "geste du cœur appelé directement (projet_fermer)": "def verbe(args, prive=False): return projet_fermer('p', 'x', 'chef')\n",
    "geste du cœur appelé directement (lancer_crochet_equipe)": "def verbe(args, prive=False): return lancer_crochet_equipe(args[0])\n",
    "contrôle du cœur refait dans la famille (exiger_chef)": "def verbe(args, prive=False): return exiger_chef('p', args[0], 'ouvrir')\n",
    "contrôle du cœur refait dans la famille (go_ouverture)": "def verbe(args, prive=False): return go_ouverture('p', {}, 's', 'x', 'chef')\n",
    "contrôle du cœur refait dans la famille (missions_comptees)": "def verbe(args, prive=False): return len(missions_comptees())\n",
    "registre des projets lu hors API (registre_projets)": "def verbe(args, prive=False): return registre_projets('p')\n",
    "dépôt lu hors API (_equipe)": "def verbe(args, prive=False): return _equipe('p')\n",
    "branchement des services (brancher)": "def verbe(args, prive=False): return brancher({'ouvrir_developpeur': print})\n",
}
libres_ok |= set(ACTIONS)
for _cas, _texte in _REFUSES_4C.items():
    with tempfile.TemporaryDirectory() as _tmp:
        _f = Path(_tmp) / "zz_famille.py"; _f.write_text(_texte, encoding="utf-8"); _vu = ecarts_contrat(_f)
        dire(bool(_vu), f"preuve 4c (famille) : {_cas} — refusé par le contrat statique ({_vu or 'aucun écart'})")
with tempfile.TemporaryDirectory() as _tmp:
    _f = Path(_tmp) / "zz_famille.py"
    _f.write_text("def verbe(args, prive=False):\n    statusline(args[0]); mettre_a_jour_titres(args[0]); lire_document(1); lire_interactif()\n"
                  "    return ouvrir_developpeur('p', 's', 'x', 'chef'), jouer_crochet(args[0]), equipe_liste('p'), projet_liste(), domaines_projet('p', signaler=False)\n", encoding="utf-8")
    dire(not ecarts_contrat(_f), f"preuve 4c (famille) : services des équipes, lire_document, statusline… et lectures des équipes acceptés dans une famille ({ecarts_contrat(_f) or 'aucun écart'})")
libres_ok -= set(ACTIONS)
with tempfile.TemporaryDirectory() as _tmp:
    _cas4 = [("vue", n, f"def rendre(w, h, a=None): return [{n}(a)]\n") for n in ACTIONS_4C + tuple(NOYAU_4C)]
    _cas4 += [("moteur", n, f"def verdict(a): return {n}(a)\n") for n in ACTIONS_4C + tuple(NOYAU_4C)]
    for _rang, _n, _texte in _cas4:
        _f = Path(_tmp) / f"zz_{_rang}.py"; _f.write_text(_texte, encoding="utf-8"); _vu = ecarts_contrat(_f)
        dire(bool(_vu), f"preuve 4c ({_rang}) : un(e) {_rang} qui appelle {_n} est refusé(e) (l'API d'action n'est pas la sienne) ({_vu or 'aucun écart'})")
    for _rang, _texte in (("vue", "def rendre(w, h, a=None): return [str(equipe_liste('p')), str(projet_liste()), str(domaines_projet('p', signaler=False))]\n"),
                          ("moteur", "def verdict(a): return domaines_projet('p', signaler=False)\n")):
        _f = Path(_tmp) / f"zz_{_rang}.py"; _f.write_text(_texte, encoding="utf-8")
        dire(not ecarts_contrat(_f), f"preuve 4c ({_rang}) : les LECTURES des équipes sont permises (API de lecture) ({ecarts_contrat(_f) or 'aucun écart'})")
# l'accès INDIRECT aux actions de 4c, pour les trois rangs : par le module du noyau qui porte la fonction, par le paquet, par le module des services
_ACCES_4C = {
    "from noyau.ecrans import lire_document": "from noyau.ecrans import lire_document\nF = lire_document\n",
    "from noyau.ecrans import lire_interactif as x": "from noyau.ecrans import lire_interactif as x\nF = x\n",
    "from noyau.bandeaux import mettre_a_jour_titres": "from noyau.bandeaux import mettre_a_jour_titres\nF = mettre_a_jour_titres\n",
    "from noyau import bandeaux ; bandeaux.statusline": "from noyau import bandeaux\nF = bandeaux.statusline\n",
    "import noyau.ecrans as x ; x.lire_document": "import noyau.ecrans as x\nF = x.lire_document\n",
    "import noyau.actions as x ; x.ouvrir_developpeur": "import noyau.actions as x\nF = x.ouvrir_developpeur\n",
    "from noyau.actions import fermer_developpeur": "from noyau.actions import fermer_developpeur\nF = fermer_developpeur\n",
    "from noyau.actions import services_commandes": "from noyau.actions import services_commandes\nF = services_commandes()['jouer_crochet']\n",
    "from noyau.api import ACTIONS ; getattr(api, ACTIONS[13])": "from noyau import api\nfrom noyau.api import ACTIONS\nF = getattr(api, ACTIONS[13])\n",
    "une action par l'espace d'une lecture (equipe_liste.__globals__)": "def rendre(w, h, a=None): return [equipe_liste.__globals__['statusline'](a)]\n",
    "le module des équipes par l'espace d'une lecture (projet_liste.__module__)": "def rendre(w, h, a=None): return [projet_liste.__module__]\n",
}
with tempfile.TemporaryDirectory() as _tmp:
    for _rang, _ajout in (("vue", set()), ("moteur", set()), ("famille", set(ACTIONS))):
        libres_ok |= _ajout
        for _cas, _texte in _ACCES_4C.items():
            _f = Path(_tmp) / "zz_acces.py"; _f.write_text(_texte, encoding="utf-8"); _vu = imports_interdits(_f)
            dire(bool(_vu), f"preuve 4c ({_rang}) : accès indirect à une action refusé — {_cas} ({_vu or 'aucun écart'})")
        libres_ok -= _ajout

# 2. chaque nom de l'API existe dans le noyau (pas de nom fantôme) et la liste n'a pas de doublon
os.environ.setdefault("BERGER_DIR", tempfile.mkdtemp())
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp); _produit.copier(SRC, t); (t / "config.toml").write_text('proprietaire = "Camille"\n')
    env = {**os.environ, "BERGER_DIR": str(t)}
    r = subprocess.run([sys.executable, "-c",
        "import sys; sys.path.insert(0, %r)\nfrom noyau.config import *\nfrom noyau.transport import *\nfrom noyau.affichage import *\n"
        "from noyau.agents import *\nfrom noyau.herdr import *\nfrom noyau.lectures import *\nfrom noyau.registre import *\nfrom noyau.ecrans import *\nfrom noyau.bandeaux import *\nfrom noyau.missions import *\nfrom noyau.equipes import *\nfrom noyau import api\n"
        "print(','.join(n for n in api.API + %r if n not in globals()))" % (str(t / "bin"), tuple(LISTES["BASE_NOYAU"]))], env=env, capture_output=True, text=True)
    dire(r.returncode == 0 and r.stdout.strip() == "", f"chaque nom de l'API (et de BASE_NOYAU pour les moteurs) existe dans le noyau (absents : {r.stdout.strip() or r.stderr.strip()[-200:] or 'aucun'})")
    dire(len(api.API) == len(set(api.API)), "aucun nom en double dans l'API")

    # 3. frontière à l'exécution : une vue qui cite un nom du cœur hors API est écartée et NOMMÉE ; les autres tournent
    (t / "bin/vues/zz_intrus.py").write_text(
        'TITRE, ICONE, ONGLET, ORDRE = "Intrus", "", "berger", 999\n'
        'def rendre(w, h, a=None):\n    return [str(verifier_depot)]\n'
        'def vue_zz_intrus(w, h): return rendre(w, h)\n')
    (t / "bin/vues/zz_cassee.py").write_text("raise RuntimeError('vue volontairement cassée')\n")
    r = subprocess.run([str(t / "bin/berger"), "vues", "--json"], env=env, capture_output=True, text=True)
    d = json.loads(r.stdout) if r.returncode == 0 else {"vues": [], "ecartees": []}
    types = {v["type"] for v in d["vues"]}
    dire({"alire", "tableau", "fiche", "zz_intrus"} <= types, "les vues saines et la vue qui cite un nom hors API se chargent (le nom n'est lu qu'à l'appel)")
    dire(any(e["vue"] == "zz_cassee" and "RuntimeError" in e["cause"] for e in d["ecartees"]), "une vue cassée est écartée et nommée, les autres tournent")
    r = subprocess.run([str(t / "bin/berger"), "vue", "zz_intrus"], env=env, capture_output=True, text=True)
    dire(r.returncode != 0 and "verifier_depot" in r.stderr + r.stdout, "un nom du cœur hors API n'existe pas pour une vue (NameError nommant le nom)")
    r = subprocess.run([sys.executable, "-c",
        "import importlib.machinery, importlib.util, sys\nl = importlib.machinery.SourceFileLoader('berger', %r); s = importlib.util.spec_from_loader('berger', l)\n"
        "m = importlib.util.module_from_spec(s); l.exec_module(m)\nprint(any(k.startswith('vue_') for k in vars(m)))" % str(t / "bin/berger")],
        env=env, capture_output=True, text=True)
    dire(r.stdout.strip() == "False", "aucune fonction vue_* n'est remise dans les globales du cœur (pas de lecture arrière)")

# 4. isolation des moteurs (lot 2) : un moteur cassé est écarté et NOMMÉ (berger etat), jamais remplacé en silence par l'autre ;
#    les moteurs sains tournent ; deux fichiers qui déclarent le même NOM sont écartés tous les deux
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp); _produit.copier(SRC, t); (t / "config.toml").write_text('proprietaire = "Camille"\n')
    a = t / "agents/essai"; (a / "memory").mkdir(parents=True)
    (a / "agent.conf").write_text("nom = essai\nmoteur = codex\nmur = ouvert\nheures = aucune\noutils =\n")
    env = {**os.environ, "BERGER_DIR": str(t), "HOME": str(t)}
    (t / "bin/moteurs/codex.py").write_text("raise RuntimeError('moteur volontairement cassé')\n")
    (t / "bin/moteurs/zz_sans_args.py").write_text("NOM = 'zz_sans_args'\nORDRE = 9\n")
    (t / "bin/moteurs/zz_double_a.py").write_text("NOM = 'double'\nORDRE = 9\ndef executable(): pass\ndef version(): pass\ndef verdict(): pass\n"
                                                  "def args(a, interactif=True): return []\ndef args_modele(modele, effort=None): return []\nefforts_permis = ()\ndef lecteur_conso(): return lambda index: []\n")
    (t / "bin/moteurs/zz_double_b.py").write_text((t / "bin/moteurs/zz_double_a.py").read_text())
    r = subprocess.run([str(t / "bin/berger"), "etat", "--json"], env=env, capture_output=True, text=True)
    d = json.loads(r.stdout)["donnees"] if r.returncode == 0 else {"moteurs_ecartes": []}
    ec = {e["moteur"]: e["cause"] for e in d["moteurs_ecartes"]}
    dire("RuntimeError" in ec.get("codex", "") and "fonction args() absente" not in ec.get("codex", ""), f"un moteur cassé est nommé dans berger etat --json avec sa cause ({ec.get('codex')})")
    dire("zz_sans_args" in ec and "absente" in ec["zz_sans_args"], "un moteur sans le contrat (fonctions absentes) est écarté et nommé")
    dire("zz_double_a" in ec and "zz_double_b" in ec and "plusieurs fichiers" in ec["zz_double_a"], "deux fichiers de même NOM : les DEUX sont écartés et nommés (jamais « le dernier gagne »)")
    r = subprocess.run([str(t / "bin/berger"), "etat"], env=env, capture_output=True, text=True)
    dire("⚠ moteur écarté : bin/moteurs/codex.py — RuntimeError" in r.stdout, "berger etat (texte) nomme le moteur écarté")
    prog = ("import json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); m = g['moteurs']\n"
            "try: m.args_moteur('essai', 'codex'); erreur = ''\nexcept ValueError as e: erreur = str(e)\n"
            "print(json.dumps({'charges': m.MOTEURS, 'choix': m.choisir_moteur('essai', 'codex'), 'erreur': erreur,\n"
            "                  'conso': sorted(g['LECTEURS_CONSO'])}))\n") % str(t / "bin/berger")
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {}
    dire(x.get("charges") == ["claude"], f"les moteurs sains tournent, le cassé n'est pas chargé (MOTEURS = {x.get('charges')} {r.stderr.strip()[-120:]})")
    dire(x.get("choix") and x["choix"][0] is None and "moteur codex écarté" in x["choix"][1], "un agent qui demande le moteur écarté reçoit « moteur codex écarté : … », pas un repli sur l'autre")
    dire("moteur codex écarté" in x.get("erreur", ""), "les arguments d'un moteur écarté : refusés, même message")
    dire(x.get("conso") == ["claude"], "LECTEURS_CONSO ne porte que les moteurs chargés (la vue Tokens n'affiche pas un moteur écarté)")

# 4 bis. un moteur aux MÉTADONNÉES invalides (NOM non texte, ORDRE non entier, lecteur_conso() qui ne tient pas au second appel) est écarté et nommé ;
#     il ne bloque pas le chargement des autres (relecture Codex du 28/10 : TypeError hors interception dans moteurs.charger)
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp); _produit.copier(SRC, t); (t / "config.toml").write_text('proprietaire = "Camille"\n')
    env = {**os.environ, "BERGER_DIR": str(t), "HOME": str(t)}
    _corps = ("def executable(): pass\ndef version(): pass\ndef verdict(): pass\ndef args(a, interactif=True): return []\n"
              "def args_modele(modele, effort=None): return []\nefforts_permis = ()\n")
    (t / "bin/moteurs/zz_nom_liste.py").write_text("NOM = []\nORDRE = 9\n" + _corps + "def lecteur_conso(): return lambda index: []\n")
    (t / "bin/moteurs/zz_nom_vide.py").write_text("NOM = ''\nORDRE = 9\n" + _corps + "def lecteur_conso(): return lambda index: []\n")
    (t / "bin/moteurs/zz_ordre_texte.py").write_text("NOM = 'zz_ordre_texte'\nORDRE = 'premier'\n" + _corps + "def lecteur_conso(): return lambda index: []\n")
    (t / "bin/moteurs/zz_conso_instable.py").write_text("NOM = 'zz_conso_instable'\nORDRE = 9\n" + _corps +
        "_n = []\ndef lecteur_conso():\n    _n.append(1)\n    if len(_n) > 1: raise RuntimeError('second appel')\n    return lambda index: []\n")
    r = subprocess.run([str(t / "bin/berger"), "etat", "--json"], env=env, capture_output=True, text=True)
    try: ec = {e["moteur"]: e["cause"] for e in json.loads(r.stdout)["donnees"]["moteurs_ecartes"]}
    except (ValueError, KeyError): ec = {}; print(r.stderr.strip()[-300:])
    dire(r.returncode == 0 and "NOM" in ec.get("zz_nom_liste", "") and "NOM" in ec.get("zz_nom_vide", ""), f"un moteur dont NOM n'est pas un texte non vide est écarté et nommé ({ec.get('zz_nom_liste')})")
    dire("ORDRE" in ec.get("zz_ordre_texte", ""), f"un moteur dont ORDRE n'est pas un entier est écarté et nommé ({ec.get('zz_ordre_texte')})")
    prog = ("import json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); m = g['moteurs']\n"
            "print(json.dumps({'charges': m.MOTEURS, 'conso': sorted(g['LECTEURS_CONSO']), 'ecartes': sorted(m.MOTEURS_REFUSES)}))\n") % str(t / "bin/berger")
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {}; print(r.stderr.strip()[-300:])
    dire(x.get("charges") == ["claude", "codex", "zz_conso_instable"] and x.get("conso") == ["claude", "codex", "zz_conso_instable"],
         f"les moteurs sains se chargent malgré eux, et lecteur_conso() n'est appelé qu'une fois, sous protection (MOTEURS = {x.get('charges')})")

# 5. isolation des commandes (lot 3) : une famille cassée, sans contrat ou en doublon est écartée et NOMMÉE (berger etat) ; les autres tournent ; un verbe
#    déclaré par deux familles écarte les DEUX (jamais « la dernière gagne ») ; un nom du cœur non prêté n'existe pas pour une famille
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp); _produit.copier(SRC, t); (t / "config.toml").write_text('proprietaire = "Camille"\n')
    shutil.copytree(SRC / "bin/commandes", t / "bin/commandes", dirs_exist_ok=True)
    env = {**os.environ, "BERGER_DIR": str(t), "HOME": str(t)}
    (t / "bin/commandes/zz_cassee.py").write_text("raise RuntimeError('famille volontairement cassée')\n")
    (t / "bin/commandes/zz_sans_aide.py").write_text('FAMILLE = "zz_sans_aide"\nVERBES = {"zz-sans-aide": lambda args, prive=False: None}\nAIDE = {}\nDROITS = {}\n')
    (t / "bin/commandes/zz_intrus.py").write_text(
        'FAMILLE = "zz_intrus"\ndef verbe(args, prive=False):\n    return masques("x")\n'
        'VERBES = {"zz-intrus": verbe}\nAIDE = {"zz-intrus": "berger zz-intrus"}\nDROITS = {"zz-intrus": {"prive": False, "cas_go": None}}\n')
    (t / "bin/commandes/zz_double_a.py").write_text(
        'FAMILLE = "zz_double_a"\nVERBES = {"zz-double": lambda args, prive=False: print("a"), "zz-seul-a": lambda args, prive=False: print("seul a")}\n'
        'AIDE = {"zz-double": "berger zz-double", "zz-seul-a": "berger zz-seul-a"}\n'
        'DROITS = {"zz-double": {"prive": False, "cas_go": None}, "zz-seul-a": {"prive": False, "cas_go": None}}\n')
    (t / "bin/commandes/zz_double_b.py").write_text(
        'FAMILLE = "zz_double_b"\nVERBES = {"zz-double": lambda args, prive=False: print("b")}\nAIDE = {"zz-double": "berger zz-double"}\n'
        'DROITS = {"zz-double": {"prive": False, "cas_go": None}}\n')
    for _n, _ex in (("refus", 'Refus("refus d\'usage voulu")'), ("interne", 'ValueError("erreur interne")'), ("indexe", "IndexError('sans argument')")):
        (t / f"bin/commandes/zz_{_n}.py").write_text(
            f'FAMILLE = "zz_{_n}"\ndef verbe(args, prive=False):\n    raise {_ex}\n'
            f'VERBES = {{"zz-{_n}": verbe}}\nAIDE = {{"zz-{_n}": "berger zz-{_n}"}}\nDROITS = {{"zz-{_n}": {{"prive": False, "cas_go": None}}}}\n'
            + ('PASSE = {"zz-refus": (Refus,)}\n' if _n == "refus" else 'PASSE = {"zz-indexe": (IndexError,)}\n' if _n == "indexe" else ""))
    (t / "bin/commandes/zz_saine.py").write_text(
        'FAMILLE = "zz_saine"\nVERBES = {"zz-saine": lambda args, prive=False: print("saine tourne")}\nAIDE = {"zz-saine": "berger zz-saine"}\n'
        'DROITS = {"zz-saine": {"prive": False, "cas_go": None}}\n')
    r = subprocess.run([str(t / "bin/berger"), "etat", "--json"], env=env, capture_output=True, text=True)
    d = json.loads(r.stdout)["donnees"] if r.returncode == 0 else {"commandes_ecartees": []}
    ec = {e["commandes"]: e["cause"] for e in d["commandes_ecartees"]}
    dire("RuntimeError" in ec.get("zz_cassee", ""), f"une famille cassée est nommée dans berger etat --json avec sa cause ({ec.get('zz_cassee')})")
    dire("zz_sans_aide" in ec and "AIDE absente" in ec["zz_sans_aide"], "une famille sans AIDE ni DROITS pour un verbe est écartée et nommée")
    dire("zz_double_a" in ec and "zz_double_b" in ec and "zz-double" in ec["zz_double_a"] and "zz_double_b" in ec["zz_double_a"],
         "deux familles qui déclarent le même verbe : les DEUX sont écartées et nommées (jamais « la dernière gagne »)")
    dire("zz_intrus" not in ec and "zz_saine" not in ec and "affichage" not in ec and "transition" not in ec, "les familles saines (celles du produit, une neuve) ne sont pas écartées")
    r = subprocess.run([str(t / "bin/berger"), "etat"], env=env, capture_output=True, text=True)
    dire("⚠ commandes écartées : bin/commandes/zz_cassee.py — RuntimeError" in r.stdout, "berger etat (texte) nomme la famille écartée")
    r = subprocess.run([str(t / "bin/berger"), "zz-saine"], env=env, capture_output=True, text=True)
    dire(r.returncode == 0 and r.stdout.strip() == "saine tourne", "une famille saine tourne malgré les familles écartées")
    r = subprocess.run([str(t / "bin/berger"), "vues"], env=env, capture_output=True, text=True)
    dire(r.returncode == 0 and "accueil" in r.stdout, "les familles du produit tournent aussi (berger vues)")
    # l'aide (relecture Codex du 28/10 : AIDES était rempli mais jamais affiché) : la docstring du cœur, inchangée, PUIS l'AIDE des familles qu'elle ne documente pas
    _doc = ast.get_docstring(ast.parse((SRC / "bin/berger").read_text(encoding="utf-8")), clean=False)
    r = subprocess.run([str(t / "bin/berger"), "aide"], env=env, capture_output=True, text=True)
    dire(r.returncode == 0 and r.stdout.startswith(_doc + "\n"), "berger aide : la docstring du cœur d'abord, inchangée (sortie des verbes du cœur identique)")
    dire("berger zz-saine" in r.stdout[len(_doc):] and "berger zz-seul-a" not in r.stdout and "berger zz-cassee" not in r.stdout,
         "…puis l'AIDE des familles chargées (une famille neuve y paraît, une écartée non)")
    dire(all(re.search(r"^\s*berger %s\b" % v, r.stdout, re.M) for v in ("lire", "notifier", "statusline", "titres", "etat", "vues", "veille", "noter")),
         "…chaque verbe déplacé d'une famille du produit a sa ligne dans l'aide")
    _extra = r.stdout[len(_doc):]
    dire(not re.search(r"^\s*berger (etat|vues|veille|noter|livrable|validations)\b", _extra, re.M), "…sans répéter un verbe que la docstring documente déjà")
    r = subprocess.run([str(t / "bin/berger"), "zz-inconnu"], env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and r.stderr.startswith("commande inconnue : zz-inconnu\n\n" + _doc) and "berger zz-saine" in r.stderr, "« commande inconnue » montre la même aide")
    # la déclaration explicite (PASSE) : DANS LE MÊME PROCESSUS que l'appel refusé (le registre est reconstruit à chaque processus)
    prog = ("import json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); c = g['commandes']; sortie = {}\n"
            "for v in ('zz-refus', 'zz-indexe', 'zz-interne'):\n"
            "    try: c.lancer(v, [])\n"
            "    except SystemExit as e: sortie[v] = 'exit: ' + str(e.code)[:60]\n"
            "    except BaseException as e: sortie[v] = type(e).__name__\n"
            "print(json.dumps({'sortie': sortie, 'ecartees': sorted(e['commandes'] for e in c.ecartees()), 'verbes': sorted(v for v in c.VERBES if v.startswith('zz-'))}))\n") % str(t / "bin/berger")
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {"sortie": {}, "ecartees": [], "verbes": []}; print(r.stderr[-300:])
    dire(x["sortie"].get("zz-refus") == "ValueError" and "zz_refus" not in x["ecartees"] and "zz-refus" in x["verbes"], f"un refus d'usage déclaré (Refus, PASSE) sort comme la ValueError d'avant et sa famille reste servie ({x['sortie'].get('zz-refus')})")
    dire(x["sortie"].get("zz-indexe") == "IndexError" and "zz_indexe" not in x["ecartees"], "un verbe qui déclare IndexError le laisse non interceptée, comme avant son déplacement")
    dire(x["sortie"].get("zz-interne", "").startswith("exit: commande zz-interne : famille zz_interne écartée (ValueError") and "zz_interne" in x["ecartees"] and "zz-interne" not in x["verbes"],
         f"une ValueError INTERNE (non déclarée) écarte la famille, nommée ({x['sortie'].get('zz-interne')})")
    # le vrai verbe : statusline sans agent garde son comportement d'avant (IndexError non interceptée, jamais « famille bureau écartée »), dans le même processus
    prog = ("import json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); c = g['commandes']\n"
            "try: c.lancer('statusline', []); r = 'rien'\nexcept SystemExit as e: r = 'exit'\nexcept BaseException as e: r = type(e).__name__\n"
            "print(json.dumps({'r': r, 'ecartees': [e['commandes'] for e in c.ecartees()], 'verbes': 'statusline' in c.VERBES}))\n") % str(t / "bin/berger")
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {"r": "", "ecartees": ["?"], "verbes": False}
    dire(x["r"] == "IndexError" and "bureau" not in x["ecartees"] and x["verbes"], f"berger statusline sans agent : IndexError non interceptée, la famille bureau n'est pas écartée ({x['r']})")
    r = subprocess.run([str(t / "bin/berger"), "statusline"], env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and "IndexError" in r.stderr and "écartée" not in r.stderr, "…et en ligne de commande : la trace d'une IndexError, pas « famille écartée »")
    # entrée privée invalide pour noter --stdin (trop grande, pas en UTF-8) : le refus d'avant (ValueError « entrée privée … »), famille journal NON écartée, dans le même processus
    prog = ("import io, json, runpy, sys\nsys.argv = ['berger']\nimport os; os.environ['BERGER_AGENT'] = 'essai'\n"
            "g = runpy.run_path(%r, run_name='essai'); c = g['commandes']; sortie = {}\n"
            "for nom, octets in (('utf8', b'\\xff\\xfe'), ('grande', b'a' * (1024 * 1024 + 1))):\n"
            "    sys.stdin = io.TextIOWrapper(io.BytesIO(octets))\n"
            "    try: c.lancer('noter', ['--stdin']); sortie[nom] = 'rien'\n"
            "    except SystemExit as e: sortie[nom] = 'exit: ' + str(e.code)[:50]\n"
            "    except BaseException as e: sortie[nom] = type(e).__name__ + ': ' + str(e)\n"
            "print(json.dumps({'sortie': sortie, 'ecartees': [e['commandes'] for e in c.ecartees()], 'verbe': 'noter' in c.VERBES}))\n") % str(t / "bin/berger")
    r = subprocess.run([sys.executable, "-c", prog], env={**env, "BERGER_AGENT": "essai"}, capture_output=True, text=True)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {"sortie": {}, "ecartees": ["?"], "verbe": False}; print(r.stderr[-300:])
    dire(x["sortie"].get("utf8") == "ValueError: entrée privée UTF-8 requise" and x["sortie"].get("grande") == "ValueError: entrée privée trop grande" and "journal" not in x["ecartees"] and x["verbe"],
         f"noter --stdin, entrée invalide (UTF-8, trop grande) : le refus d'avant, la famille journal n'est pas écartée ({x['sortie']})")
    r = subprocess.run([str(t / "bin/berger"), "noter", "--stdin"], input=b"\xff\xfe", env={**env, "BERGER_AGENT": "essai"}, capture_output=True)
    dire(r.returncode == 1 and r.stderr.rstrip().splitlines()[-1] == "ValueError: entrée privée UTF-8 requise".encode() and "écartée".encode() not in r.stderr and b"noyau.ecarts" not in r.stderr, "…et en ligne de commande : la dernière ligne d'avant (ValueError: entrée privée…), pas « famille écartée »")
    # les verbes du CŒUR qui lisent l'entrée privée (demander, parler) : la dernière ligne d'avant le lot 3 (« ValueError: … », pas « noyau.ecarts.Refus: … »)
    for _v in ("demander", "parler"):
        r = subprocess.run([str(t / "bin/berger"), _v, "essai", "--stdin"], input=b"\xff\xfe", env=env, capture_output=True)
        dire(r.returncode == 1 and r.stderr.rstrip().splitlines()[-1] == "ValueError: entrée privée UTF-8 requise".encode(),
             f"berger {_v} --stdin, entrée non UTF-8 (famille messages depuis le lot 4b) : la dernière ligne d'avant ({r.stderr.rstrip().splitlines()[-1][:60] if r.stderr.strip() else b''!r})")
    r = subprocess.run([str(t / "bin/berger"), "noter", "x"], env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and r.stderr.rstrip().splitlines()[-1] == "ValueError: berger noter --stdin ; texte positionnel refusé" and "écartée" not in r.stderr and "noyau.ecarts" not in r.stderr,
         "berger noter x : la même sortie d'erreur qu'avant (dernière ligne « ValueError: berger noter… »), famille journal non écartée")
    r = subprocess.run([str(t / "bin/berger"), "notifier", "x"], env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and r.stderr.rstrip().splitlines()[-1] == "ValueError: berger notifier --stdin [--urgent] ; tableau JSON titre et texte sur stdin" and "écartée" not in r.stderr and "noyau.ecarts" not in r.stderr,
         "berger notifier x : la même sortie d'erreur qu'avant (dernière ligne « ValueError: berger notifier… »), famille bureau non écartée")
    r = subprocess.run([str(t / "bin/berger"), "lire", "\u00b2"], env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and r.stderr.rstrip().splitlines()[-1] == "ValueError: invalid literal for int() with base 10: '\u00b2'" and "écartée" not in r.stderr and "noyau.ecarts" not in r.stderr,
         "berger lire ² : la ValueError d'avant (int refuse « ² »), famille alire non écartée")
    r = subprocess.run([str(t / "bin/berger"), "zz-double"], env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and r.stderr.startswith("commande inconnue : zz-double") and "⚠ commandes écartées : bin/commandes/zz_double_a.py" in r.stderr
         and "⚠ commandes écartées : bin/commandes/zz_double_b.py" in r.stderr, "le verbe en doublon n'est servi par aucune des deux ; le refus nomme les familles écartées")
    r = subprocess.run([str(t / "bin/berger"), "zz-seul-a"], env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and "commande inconnue : zz-seul-a" in r.stderr, "une famille écartée pour un doublon est écartée EN ENTIER (ses autres verbes aussi)")
    # un verbe qui plante À L'APPEL (ici un nom du cœur qui n'existe pas pour une famille) écarte sa famille, nommée ; la voisine saine continue
    prog = ("import json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); c = g['commandes']\n"
            "try: c.lancer('zz-intrus', [])\nexcept SystemExit as e: msg = str(e.code)\n"
            "print(json.dumps({'msg': msg, 'ecartees': c.ecartees(), 'verbes': sorted(c.VERBES), 'apres': c.lancer('zz-intrus', []) is NotImplemented,\n"
            "                  'saine': c.lancer('zz-saine', []), 'etat': g['donnees_etat']()['commandes_ecartees']}))\n") % str(t / "bin/berger")
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {"msg": "", "ecartees": [], "verbes": [], "apres": False, "etat": []}; print(r.stderr[-300:])
    dire("zz_intrus" in x["msg"] and "masques" in x["msg"] and "écartée" in x["msg"], f"un verbe qui plante à l'appel : la famille est écartée et NOMMÉE dans le message ({x['msg'][:90]!r})")
    noms = {e["commandes"]: e["cause"] for e in x["etat"]}
    dire("masques" in noms.get("zz_intrus", "") and "NameError" in noms.get("zz_intrus", ""), "…elle figure dans l'état (commandes_ecartees) avec sa cause, comme une famille cassée au chargement")
    dire("zz-intrus" not in x["verbes"] and x["apres"] and "zz-saine" in x["verbes"], "…ses verbes quittent le registre (commande inconnue ensuite) ; la famille saine voisine reste servie")
    dire("transition" not in noms and "alire" not in noms and "veille" not in noms, "…et aucune famille du produit n'est écartée à cause d'elle")
    # le message dit vrai (relecture Codex du 28/10) : rien ne garde l'écartement à l'appel ; un nouveau processus (berger etat) reconstruit le registre
    r = subprocess.run([str(t / "bin/berger"), "zz-interne"], env=env, capture_output=True, text=True)
    r2 = subprocess.run([str(t / "bin/berger"), "etat", "--json"], env=env, capture_output=True, text=True)
    try: noms = {e["commandes"] for e in json.loads(r2.stdout)["donnees"]["commandes_ecartees"]}
    except (ValueError, KeyError): noms = {"?"}
    dire(r.returncode == 1 and "famille zz_interne écartée (ValueError" in r.stderr and "zz_interne" not in noms,
         "en ligne de commande, l'écartement à l'appel ne vaut que pour cet appel : un nouveau berger etat ne la nomme pas")
    dire("la nomme." not in r.stderr and "pour cet appel seulement" in r.stderr and "ne la nomme pas" in r.stderr,
         f"…et le message le dit, sans promettre que berger etat la nommera ({r.stderr.strip().splitlines()[-1][:110]!r})")

# 6. lot 4a, à l'exécution : (a) la famille missions reçoit l'API de lecture ET d'action, rien du cœur ; une vue et un moteur ne reçoivent pas l'action ;
#    (b) les services d'action gardent LEURS contrôles, appelés directement (sans la famille) ; (c) brancher refuse un nom hors liste ou ce qui n'est pas une
#    fonction ; (d) la famille missions cassée est écartée et NOMMÉE, ses verbes sont inconnus (jamais servis par le cœur en silence), le reste tourne.
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp); _produit.copier(SRC, t)
    (t / "config.toml").write_text('proprietaire = "Camille"\n\n[missions]\nmax = 1\n')
    for _a in ("aa", "bb"):
        (t / "agents" / _a / "memory").mkdir(parents=True); (t / "agents" / _a / "agent.conf").write_text(f"nom = {_a}\nmoteur = claude\nheures = aucune\n")
    (t / "agents/aa/MISSION.md").write_text("# Mission confiée par Camille — essai\nmoteur : claude\n\nx\n")
    env = {**os.environ, "BERGER_DIR": str(t), "HOME": str(t)}
    # (0) renvoi n° 83, à l'exécution : noyau.api ne porte plus aucun accès à l'action ; une vue qui l'y cherche (import indirect) échoue sans rien terminer
    r = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r)\nfrom noyau import api\nimport noyau.actions as s\n"
                        "print(sorted(n for n in vars(api) if 'action' in n.lower()), callable(getattr(s, 'services_commandes', None)))" % str(t / "bin")],
                       env={}, capture_output=True, text=True)
    dire(r.stdout.strip() == "['ACTIONS'] True", f"4a : noyau.api n'expose plus d'accès aux services (seule la liste ACTIONS des noms) ; le chargeur de commandes les prend dans noyau.actions ({r.stdout.strip() or r.stderr.strip()[-120:]})")
    (t / "bin/vues/zz_action.py").write_text('import noyau.api as x\nTITRE, ICONE, ONGLET, ORDRE = "Action", None, "berger", 998\n'
                                             'def rendre(w, h, a=None): return [str(x.actions()["terminer_mission"]("aa", PROPRIETAIRE))]\n')
    r = subprocess.run([str(t / "bin/berger"), "vue", "zz_action"], env=env, capture_output=True, text=True)
    dire(r.returncode != 0 and "AttributeError" in r.stderr and (t / "agents/aa/MISSION.md").is_file(),
         f"4a : une vue qui cherche l'action par noyau.api échoue (AttributeError) et ne termine rien ({(r.stderr.strip().splitlines() or [''])[-1][:90]})")
    (t / "bin/vues/zz_action.py").unlink()
    prog = ("import json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); c = g['commandes']; act = g['noyau'].actions; out = {}\n"
            "fam = vars(c.FAMILLES.get('missions', object())); vue = vars(g['VUES']['missions']); mot = vars(g['moteurs'].MODULES['claude'])\n"
            "out['famille'] = {n: n in fam for n in ('confier_mission', 'terminer_mission', 'suivi', 'rapport_mission', 'mission', 'fin_mission', 'demarrer_agent',\n"
            "                  'ouvrir_en_mission', 'brancher', '_SERVICES', 'missions_comptees', 'chefs', 'agent_vivant')}\n"
            "out['meme'] = fam.get('confier_mission') is act.confier_mission and fam.get('terminer_mission') is act.terminer_mission\n"
            "out['vue'] = [n for n in ('confier_mission', 'terminer_mission') if n in vue]; out['dans_moteur'] = [n for n in ('confier_mission', 'terminer_mission') if n in mot]\n"
            "def essai(nom, f, *a):\n"
            "    try: f(*a); out[nom] = 'accepté'\n"
            "    except SystemExit as e: out[nom] = str(e.code)\n"
            "    except BaseException as e: out[nom] = type(e).__name__ + ': ' + str(e)\n"
            "essai('inconnu', act.confier_mission, 'fantome', 'x', 'Camille')\n"
            "essai('deja', act.confier_mission, 'aa', 'x', 'Camille')\n"
            "essai('plafond', act.confier_mission, 'bb', 'x', 'Camille')\n"
            "g['MISSIONS']['max'] = 5; g['confier_mission'] = None\n"
            "essai('moteur', act.confier_mission, 'bb', 'x', 'Camille', 'inexistant')\n"
            "essai('modele', act.confier_mission, 'bb', 'x', 'Camille', 'claude', 'pas-permis')\n"
            "essai('terminer', act.terminer_mission, 'aa', 'bb')\n"
            "essai('terminer_sans', act.terminer_mission, 'bb', 'aa')\n"
            "essai('hors_liste', act.brancher, {'lancer_agent': print})\n"
            "essai('pas_fonction', act.brancher, {'confier_mission': 1})\n"
            "out['bb_mission'] = (g['dossier']('bb') / 'MISSION.md').exists()\n"
            "print(json.dumps(out))\n") % str(t / "bin/berger")
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {"famille": {}, "meme": False, "vue": ["?"], "dans_moteur": ["?"]}; print(r.stderr[-400:])
    fam = x["famille"]
    dire(fam and all(fam[n] for n in ("confier_mission", "terminer_mission", "suivi", "rapport_mission")) and x["meme"],
         "4a, exécution : la famille missions reçoit la lecture (suivi, rapport_mission) et l'action (confier_mission, terminer_mission : les services de noyau/actions.py)")
    dire(fam and not any(fam[n] for n in ("mission", "fin_mission", "demarrer_agent", "ouvrir_en_mission", "brancher", "_SERVICES", "missions_comptees", "chefs", "agent_vivant")),
         f"4a, exécution : rien du cœur ni du branchement n'existe pour elle (mission, fin_mission, demarrer_agent, brancher…) ({[n for n, v in fam.items() if v]})")
    dire(x["vue"] == [] and x["dans_moteur"] == [], f"4a, exécution : une vue et un moteur ne reçoivent pas l'API d'action ({x['vue'] + x['dans_moteur']})")
    dire(x.get("inconnu", "").startswith("agent inconnu : fantome"), f"service confier_mission, appelé SANS la famille : agent inconnu refusé ({x.get('inconnu')})")
    dire(x.get("deja", "").startswith("aa a déjà une mission en cours"), f"…une mission à la fois ({x.get('deja')})")
    dire(x.get("plafond", "").startswith("déjà 1 missions en cours (aa) : maximum 1"), f"…plafond [missions] max ({x.get('plafond')})")
    dire(x.get("moteur", "").startswith("moteur inconnu : inexistant"), f"…moteur vérifié par le cœur ({x.get('moteur')})")
    dire(x.get("modele", "").startswith("modèle non permis pour claude : pas-permis"), f"…modèle vérifié (noyau.modeles) ({x.get('modele')})")
    dire(not x.get("bb_mission", True), "…aucun de ces refus n'a créé de MISSION.md")
    dire(x.get("terminer", "").startswith("mission de aa NON terminée"), f"service terminer_mission, appelé SANS la famille : checklist non finie refusée hors propriétaire ({x.get('terminer', '')[:60]})")
    dire(x.get("terminer_sans", "") == "bb n'a pas de mission en cours", f"…sans mission en cours, refusé ({x.get('terminer_sans')})")
    dire(x.get("hors_liste", "").startswith("NameError") and x.get("pas_fonction", "").startswith("TypeError"),
         f"brancher refuse un service hors de la liste ACTIONS et ce qui n'est pas une fonction ({x.get('hors_liste')} ; {x.get('pas_fonction')})")
    # (c bis) renvoi de master (29/10, n° 55 du propriétaire : pas de dispense générale) : une panne du CŒUR sortie d'un service (ErreurService) passe et ressort
    #     telle qu'avant ; une erreur DANS la famille, hors service, l'écarte et la nomme ; l'IndexError d'un argument manquant passe, comme avant.
    tete = "import json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); c = g['commandes']; act = g['noyau'].actions\n" % str(t / "bin/berger")
    bilan = "print(json.dumps({'r': r, 'ecartees': {e['commandes']: e['cause'] for e in c.ecartees()}, 'verbes': sorted(v for v in c.VERBES if 'mission' in v or v == 'suivi')}))\n"
    def _jouer(corps):
        r = subprocess.run([sys.executable, "-c", tete + corps + bilan], env=env, capture_output=True, text=True)
        try: return json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError): print(r.stderr[-300:]); return {"r": "", "ecartees": {"?": "?"}, "verbes": []}
    _quatre = ["fin-mission", "mission", "rapport-mission", "suivi"]
    x = _jouer("def panne(*a): return {}['pane']\nact.brancher({'confier_mission': panne})\n"
               "try: c.lancer('mission', ['bb', 'x']); r = 'rien'\nexcept SystemExit as e: r = 'exit: ' + str(e.code)[:80]\nexcept BaseException as e: r = type(e).__name__ + ': ' + str(e)\n")
    dire(x["r"] == "KeyError: 'pane'" and not x["ecartees"] and x["verbes"] == _quatre,
         f"4a : une panne du cœur passée par le service ressort telle qu'avant (KeyError d'origine), la famille missions n'est pas écartée ({x['r']}, écartées {x['ecartees']})")
    r = subprocess.run([sys.executable, "-c", tete + "def panne(*a): return {}['pane']\nact.brancher({'terminer_mission': panne})\nc.lancer('fin-mission', ['aa'])\n"],
                       env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and r.stderr.rstrip().splitlines()[-1] == "KeyError: 'pane'" and "écartée" not in r.stderr and "ErreurService" not in r.stderr,
         "…et la sortie d'erreur est celle d'avant (dernière ligne « KeyError: 'pane' », ni « écartée » ni ErreurService)")
    x = _jouer("vars(c.FAMILLES['missions'])['json'] = None\n"
               "try: c.lancer('suivi', ['aa']); r = 'rien'\nexcept SystemExit as e: r = 'exit: ' + str(e.code)[:80]\nexcept BaseException as e: r = type(e).__name__\n")
    dire(x["r"].startswith("exit: commande suivi : famille missions écartée (AttributeError") and "AttributeError" in x["ecartees"].get("missions", "") and x["verbes"] == [],
         f"4a : une erreur DANS la famille, hors service, l'écarte et la NOMME, ses verbes quittent le registre ({x['r'][:70]})")
    x = _jouer("try: c.lancer('suivi', []); r = 'rien'\nexcept SystemExit as e: r = 'exit'\nexcept BaseException as e: r = type(e).__name__\n")
    dire(x["r"] == "IndexError" and not x["ecartees"], f"4a : l'IndexError d'un argument manquant passe, comme avant, sans écarter la famille ({x['r']})")

    # (d) la famille des missions cassée : écartée et nommée ; ses verbes ne sont servis par personne ; le reste (familles et transition) tourne
    (t / "bin/commandes/missions.py").write_text("raise RuntimeError('famille des missions volontairement cassée')\n")
    r = subprocess.run([str(t / "bin/berger"), "etat", "--json"], env=env, capture_output=True, text=True)
    try: ec = {e["commandes"]: e["cause"] for e in json.loads(r.stdout)["donnees"]["commandes_ecartees"]}
    except (ValueError, KeyError): ec = {}
    dire("RuntimeError" in ec.get("missions", "") and set(ec) == {"missions"}, f"4a : la famille missions cassée est écartée et NOMMÉE, elle seule ({ec})")
    for _argv in (["suivi", "aa"], ["fin-mission", "aa"], ["rapport-mission", "aa"]):
        r = subprocess.run([str(t / "bin/berger"), *_argv], env=env, capture_output=True, text=True)
        dire(r.returncode == 1 and r.stderr.startswith(f"commande inconnue : {_argv[0]}") and "⚠ commandes écartées : bin/commandes/missions.py — RuntimeError" in r.stderr,
             f"4a : berger {_argv[0]} avec la famille cassée : « commande inconnue », la famille nommée (jamais servi en silence par le cœur)")
    r = subprocess.run([str(t / "bin/berger"), "--stdin"], input=json.dumps(["mission", "bb", "x"]), env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and r.stderr.startswith("commande inconnue : mission") and not (t / "agents/bb/MISSION.md").exists(), "4a : mission (--stdin) avec la famille cassée : inconnue, rien créé")
    r = subprocess.run([str(t / "bin/berger"), "vues"], env=env, capture_output=True, text=True)
    r2 = subprocess.run([str(t / "bin/berger"), "besoin", "liste", "--json"], env=env, capture_output=True, text=True)
    dire(r.returncode == 0 and "accueil" in r.stdout and r2.returncode == 0, "4a : les autres familles et les verbes du cœur tournent (berger vues, berger besoin liste --json)")

# 7. lot 4b, à l'exécution : (a) les familles messages et besoins reçoivent la lecture (besoins) et les services d'action, rien du cœur ; journal et notifier
#    (API d'action) ne sont plus dans l'espace d'une vue ni d'un moteur, mais restent celui du noyau pour les familles journal et bureau ; (b) les services
#    gardent leurs contrôles, appelés SANS la famille ; (c) une panne du cœur passée par un service ressort telle qu'avant ; une erreur dans la famille
#    l'écarte et la nomme ; (d) une famille cassée (messages, puis besoins) est écartée et NOMMÉE, ses verbes sont inconnus, le reste tourne.
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp); _produit.copier(SRC, t)
    (t / "config.toml").write_text('proprietaire = "Camille"\n')
    for _a in ("aa", "bb"):
        (t / "agents" / _a / "memory").mkdir(parents=True); (t / "agents" / _a / "agent.conf").write_text(f"nom = {_a}\nmoteur = claude\nheures = aucune\nmur = ouvert\n")
    env = {**os.environ, "BERGER_DIR": str(t), "HOME": str(t)}
    COEUR_4B = ("message_deposer", "message_remettre", "delegation_suivi", "demander", "parler", "echange", "besoin_ranger", "besoin_clore", "annonce_outil",
                "gardien", "BESOINS", "solliciter", "debit_ecrire", "brancher", "_SERVICES", "mission", "fin_mission")
    prog = ("import json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); c = g['commandes']; act = g['noyau'].actions; out = {}\n"
            "fm = vars(c.FAMILLES.get('messages', object())); fb = vars(c.FAMILLES.get('besoins', object())); fj = vars(c.FAMILLES.get('journal', object()))\n"
            "fu = vars(c.FAMILLES.get('bureau', object())); vue = vars(g['VUES']['alire']); mot = vars(g['moteurs'].MODULES['claude'])\n"
            "A4B = %r; COEUR = %r\n"
            "out['services'] = [n for n in A4B if not (fm.get(n) is getattr(act, n, 0) and fb.get(n) is getattr(act, n, 0))]\n"
            "out['lecture'] = 'besoins' in fb and fb['besoins'] is g['besoins']\n"
            "out['coeur'] = sorted(n for n in COEUR if n in fm or n in fb)\n"
            "out['journal_notifier'] = fj.get('journal') is g['journal'] and fu.get('notifier') is g['notifier']\n"
            "out['vue'] = sorted(n for n in A4B + ('journal', 'notifier') if n in vue); out['moteur'] = sorted(n for n in A4B + ('journal', 'notifier') if n in mot)\n"
            "def essai(nom, f, *a):\n"
            "    try: f(*a); out[nom] = 'accepté'\n"
            "    except SystemExit as e: out[nom] = str(e.code)\n"
            "    except BaseException as e: out[nom] = type(e).__name__ + ': ' + str(e) + ' | ' + type(e.__cause__).__name__\n"
            "essai('deposer', act.deposer_message, 'aa', 'fantome', 'x')\n"
            "essai('ranger', act.ranger_besoin, 'aa', 'outil', 'x')\n"
            "essai('clore_etat', act.clore_besoin, '1', 'peut-etre', 'x', None)\n"
            "essai('clore_par', act.clore_besoin, '1', 'fait', 'x', 'bb')\n"
            "essai('clore_absent', act.clore_besoin, '1', 'fait', 'x', None)\n"
            "essai('parler', act.parler_agent, 'aa', 'x')\n"
            "essai('annoncer', act.annoncer_outil, 'essai', False)\n"
            "essai('question', act.poser_question, 'fantome', 'q', None, None)\n"
            "essai('pas_fonction', act.brancher, {'deposer_message': 1})\n"
            "out['rien'] = not (g['BERGER'] / 'courtier/besoins').exists() and not (g['AGENTS'] / 'fantome').exists()\n"
            "print(json.dumps(out))\n") % (str(t / "bin/berger"), ACTIONS_4B, COEUR_4B)
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {"services": ["?"], "lecture": False, "coeur": ["?"], "journal_notifier": False, "vue": ["?"], "moteur": ["?"]}; print(r.stderr[-400:])
    dire(x["services"] == [] and x["lecture"], f"4b, exécution : les familles messages et besoins reçoivent les services d'action (ceux de noyau/actions.py) et la lecture besoins (manquants : {x['services']})")
    dire(x["coeur"] == [], f"4b, exécution : rien du cœur ni du branchement n'existe pour elles (message_deposer, parler, demander, gardien, brancher…) ({x['coeur']})")
    dire(x["journal_notifier"], "4b, exécution : journal et notifier, dans l'API d'action, restent ceux du noyau pour les familles journal (noter) et bureau (notifier)")
    dire(x["vue"] == [] and x["moteur"] == [], f"4b, exécution : une vue et un moteur ne reçoivent ni les services de 4b, ni journal, ni notifier ({x['vue'] + x['moteur']})")
    dire(x.get("deposer", "").startswith("agent inconnu : fantome"), f"service deposer_message, appelé SANS la famille : agent inconnu refusé ({x.get('deposer')})")
    dire(x.get("ranger") == "aucun gardien déclaré", f"service ranger_besoin : sans gardien, refusé ({x.get('ranger')})")
    dire(x.get("clore_etat", "").startswith("berger besoin clore <n°> fait|refuse|transmis"), f"service clore_besoin : état inconnu refusé ({x.get('clore_etat')})")
    dire(x.get("clore_par", "").startswith("seul le gardien"), f"…clôture par un autre que le gardien refusée ({x.get('clore_par')})")
    dire(x.get("clore_absent") == "besoin n° 1 introuvable ou déjà clos", f"…besoin introuvable refusé ({x.get('clore_absent')})")
    dire(x.get("parler") == "aa n'a pas de panneau agent ouvert", f"service parler_agent : agent sans panneau refusé ({x.get('parler')})")
    dire(x.get("annoncer") == "aucune consigne rangée pour l'outil essai", f"service annoncer_outil : outil sans consigne refusé ({x.get('annoncer')})")
    dire(x.get("question", "").startswith("ErreurService: poser_question : FileNotFoundError") and x.get("question", "").endswith("| FileNotFoundError"),
         f"service poser_question : une panne du cœur sort en ErreurService, l'origine gardée en cause ({x.get('question', '')[:80]})")
    dire(x.get("pas_fonction", "").startswith("TypeError"), f"brancher refuse ce qui n'est pas une fonction pour un service de 4b ({x.get('pas_fonction')})")
    dire(x.get("rien"), "…aucun de ces refus n'a rien écrit (ni besoin, ni dossier d'agent)")
    # (c) panne du cœur par un service, erreur dans la famille, ce qui passe (IndexError, Refus, JSON de delegation-suivi)
    tete = "import io, json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); c = g['commandes']; act = g['noyau'].actions\n" % str(t / "bin/berger")
    bilan = "print(json.dumps({'r': r, 'ecartees': {e['commandes']: e['cause'] for e in c.ecartees()}}))\n"
    essai_l = lambda v, a, p="False": f"try: c.lancer({v!r}, {a!r}, {p}); r = 'rien'\nexcept SystemExit as e: r = 'exit: ' + str(e.code)[:90]\nexcept BaseException as e: r = type(e).__name__ + ': ' + str(e)\n"
    def _jouer(corps):
        r = subprocess.run([sys.executable, "-c", tete + corps + bilan], env=env, capture_output=True, text=True)
        try: return json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError): print(r.stderr[-300:]); return {"r": "", "ecartees": {"?": "?"}}
    x = _jouer("def panne(*a): return {}['pane']\nact.brancher({'deposer_message': panne})\n" + essai_l("message-deposer", ["aa", "bb", "x"], "True"))
    dire(x["r"] == "KeyError: 'pane'" and not x["ecartees"], f"4b : une panne du cœur passée par deposer_message ressort telle qu'avant, la famille messages n'est pas écartée ({x['r']}, {x['ecartees']})")
    r = subprocess.run([sys.executable, "-c", tete + "def panne(*a): return {}['pane']\nact.brancher({'ranger_besoin': panne})\nc.lancer('besoin-ranger', ['aa', 'outil', 'x'])\n"],
                       env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and r.stderr.rstrip().splitlines()[-1] == "KeyError: 'pane'" and "écartée" not in r.stderr and "ErreurService" not in r.stderr,
         "…et la sortie d'erreur est celle d'avant (besoin-ranger : dernière ligne « KeyError: 'pane' », ni « écartée » ni ErreurService)")
    x = _jouer("vars(c.FAMILLES['besoins'])['json'] = None\n" + essai_l("besoin", ["liste", "--json"]))
    dire(x["r"].startswith("exit: commande besoin : famille besoins écartée (AttributeError") and "AttributeError" in x["ecartees"].get("besoins", "") and set(x["ecartees"]) == {"besoins"},
         f"4b : une erreur DANS la famille besoins, hors service, l'écarte et la NOMME, elle seule ({x['r'][:80]})")
    x = _jouer(essai_l("message-remettre", []))
    dire(x["r"].startswith("IndexError") and not x["ecartees"], f"4b : l'IndexError d'un argument manquant passe, comme avant, sans écarter la famille ({x['r']})")
    x = _jouer(essai_l("parler", ["aa", "x"]))
    dire(x["r"].startswith("ValueError: berger parler <agent> --stdin") and not x["ecartees"], f"4b : le refus d'usage de parler sort en ValueError, comme avant ({x['r'][:60]})")
    x = _jouer("sys.stdin = io.StringIO('pas du json')\n" + essai_l("delegation-suivi", ["aa", "bb"]))
    dire(x["r"].startswith("JSONDecodeError") and not x["ecartees"], f"4b : delegation-suivi, JSON invalide : la JSONDecodeError d'avant, la famille n'est pas écartée ({x['r'][:60]})")
    # renvoi n° 89 : json.loads ne lève pas que JSONDecodeError ; ses autres erreurs de décodage (et celles de la lecture de stdin) sortent telles qu'avant,
    # à cet endroit seulement : PASSE ne s'élargit pas, une ValueError ailleurs dans le verbe écarte toujours la famille
    x = _jouer("sys.stdin = io.StringIO('{\"en_trop\": ' + '7' * 5000 + '}')\n" + essai_l("delegation-suivi", ["aa", "bb"]))
    dire(x["r"].startswith("ValueError: Exceeds the limit") and not x["ecartees"], f"4b : delegation-suivi, entier de 5 000 chiffres : la ValueError d'avant, la famille n'est pas écartée ({x['r'][:60]})")
    x = _jouer("sys.stdin = io.StringIO('[' * 100000 + ']' * 100000)\n" + essai_l("delegation-suivi", ["aa", "bb"]))
    dire(x["r"].startswith("RecursionError") and not x["ecartees"], f"4b : delegation-suivi, imbrication trop profonde : la RecursionError d'avant, la famille n'est pas écartée ({x['r'][:60]})")
    for _v, _a in (("delegation-suivi", ["aa", "bb"]), ("echange", ["aa", "bb", "question", "--stdin"])):
        x = _jouer("sys.stdin = io.TextIOWrapper(io.BytesIO(b'\\xff'), encoding='utf-8')\n" + essai_l(_v, _a))
        dire(x["r"].startswith("UnicodeDecodeError") and not x["ecartees"], f"4b : {_v}, entrée non UTF-8 : l'UnicodeDecodeError d'avant, la famille n'est pas écartée ({x['r'][:60]})")
    x = _jouer("sys.stdin = io.StringIO('{}')\nvars(c.FAMILLES['messages'])['suivre_delegation'] = lambda *a: int('x')\n" + essai_l("delegation-suivi", ["aa", "bb"]))
    dire(x["r"].startswith("exit: commande delegation-suivi : famille messages écartée (ValueError") and "ValueError" in x["ecartees"].get("messages", ""),
         f"4b : une ValueError dans delegation-suivi, hors décodage de l'entrée, écarte toujours la famille, nommée ({x['r'][:70]})")
    x = _jouer("r = sorted({c.FAMILLE_DE[v] + ':' + v + ':' + ','.join(sorted(e.__name__ for e in ex)) for f in ('messages', 'besoins') for v, ex in c.FAMILLES[f].PASSE.items()})\n")
    dire(x["r"] and all(l.split(":")[2] == "ErreurService,IndexError,Refus" for l in x["r"]), f"4b : PASSE reste limité, le même pour chaque verbe des messages et des besoins ({x['r'][:3]})")
    x = _jouer(essai_l("demander", ["aa", "--vite", "x"]))
    dire(x["r"].startswith("ValueError: berger demander <agent> --stdin") and not x["ecartees"], f"4b : le refus d'usage de demander sort en ValueError, comme avant ({x['r'][:60]})")
    # (d) une famille cassée : écartée et nommée, ses verbes inconnus, le reste tourne
    _lu = lambda f: f.read_text() if f.is_file() else "raise RuntimeError('famille absente')\n"
    _messages, _besoins = _lu(t / "bin/commandes/messages.py"), _lu(t / "bin/commandes/besoins.py")
    for _fam, _verbes, _autre in (("messages", (["parler", "aa", "--stdin"], ["message-remettre", "aa"], ["echange", "aa", "bb", "message", "x"]), ["besoin", "liste", "--json"]),
                                  ("besoins", (["besoin", "liste"], ["besoin-ranger", "aa", "outil", "x"], ["annonce-outil", "essai"]), ["message-remettre", "aa"])):
        (t / "bin/commandes/messages.py").write_text(_messages); (t / "bin/commandes/besoins.py").write_text(_besoins)
        (t / f"bin/commandes/{_fam}.py").write_text(f"raise RuntimeError('famille {_fam} volontairement cassée')\n")
        r = subprocess.run([str(t / "bin/berger"), "etat", "--json"], env=env, capture_output=True, text=True)
        try: ec = {e["commandes"]: e["cause"] for e in json.loads(r.stdout)["donnees"]["commandes_ecartees"]}
        except (ValueError, KeyError): ec = {}
        dire("RuntimeError" in ec.get(_fam, "") and set(ec) == {_fam}, f"4b : la famille {_fam} cassée est écartée et NOMMÉE, elle seule ({ec})")
        for _argv in _verbes:
            r = subprocess.run([str(t / "bin/berger"), *_argv], input="x", env=env, capture_output=True, text=True)
            dire(r.returncode == 1 and r.stderr.startswith(f"commande inconnue : {_argv[0]}") and f"⚠ commandes écartées : bin/commandes/{_fam}.py — RuntimeError" in r.stderr,
                 f"4b : berger {_argv[0]} avec la famille {_fam} cassée : « commande inconnue », la famille nommée (jamais servi en silence par le cœur)")
        r = subprocess.run([str(t / "bin/berger"), *_autre], env=env, capture_output=True, text=True)
        r2 = subprocess.run([str(t / "bin/berger"), "vues"], env=env, capture_output=True, text=True)
        dire(r.returncode == 0 and r2.returncode == 0 and "accueil" in r2.stdout, f"4b : avec {_fam} cassée, l'autre famille ({' '.join(_autre)}) et les vues tournent")
    (t / "bin/commandes/messages.py").write_text("raise RuntimeError('cassée')\n")
    r = subprocess.run([str(t / "bin/berger"), "--stdin"], input=json.dumps(["message-deposer", "aa", "bb", "x"]), env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and r.stderr.startswith("commande inconnue : message-deposer") and not (t / "agents/bb/messages").exists(),
         "4b : message-deposer (--stdin) avec la famille messages cassée : inconnue, rien déposé")

# 8. lot 4c, à l'exécution : (a) la famille equipes reçoit les lectures (equipe_liste, projet_liste, domaines_projet) et les services d'action, rien du cœur ;
#    lire_document, lire_interactif, mettre_a_jour_titres et statusline (API d'action) ne sont plus dans l'espace d'une vue ni d'un moteur, mais restent
#    ceux du noyau pour les familles alire et bureau ; (b) les services gardent leurs contrôles, appelés SANS la famille ; (c) une panne du cœur passée par
#    un service ressort telle qu'avant ; une erreur dans la famille l'écarte et la nomme ; (d) la famille cassée est écartée et NOMMÉE, ses verbes sont
#    inconnus, le reste tourne.
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp); _produit.copier(SRC, t)
    (t / "config.toml").write_text(f'proprietaire = "Camille"\n\n[equipes.p]\nchef_projet = "chef"\ncoordinateur = "coord"\ndepot = "{t}/depot"\n\n'
                                   f'[equipes.inst]\nchef_projet = "chef"\ndepot = "{t}"\n')
    for _a in ("chef", "coord", "intrus"):
        (t / "agents" / _a / "memory").mkdir(parents=True); (t / "agents" / _a / "agent.conf").write_text(f"nom = {_a}\nmoteur = claude\nheures = aucune\nmur = ouvert\n")
    env = {**os.environ, "BERGER_DIR": str(t), "HOME": str(t)}
    COEUR_4C = ("equipe_ouvrir", "equipe_fermer", "equipe_domaine", "equipe_go", "projet_ouvrir", "projet_fermer", "lancer_crochet_equipe", "exiger_chef",
                "_equipe", "go_ouverture", "registre_projets", "membres_possibles", "missions_comptees", "regenerer", "brancher", "_SERVICES", "mission", "fin_mission")
    prog = ("import json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); c = g['commandes']; act = g['noyau'].actions; out = {}\n"
            "fe = vars(c.FAMILLES.get('equipes', object())); fa = vars(c.FAMILLES.get('alire', object())); fu = vars(c.FAMILLES.get('bureau', object()))\n"
            "vue = vars(g['VUES']['alire']); mot = vars(g['moteurs'].MODULES['claude'])\n"
            "A4C = %r; NOY = %r; LEC = %r; COEUR = %r\n"
            "out['services'] = [n for n in A4C if fe.get(n) is not getattr(act, n, 0)]\n"
            "out['lectures'] = [n for n in LEC if not (n in fe and fe[n] is g[n])]\n"
            "out['coeur'] = sorted(n for n in COEUR if n in fe)\n"
            "out['noyau'] = fa.get('lire_document') is g['lire_document'] and fa.get('lire_interactif') is g['lire_interactif'] and fu.get('mettre_a_jour_titres') is g['mettre_a_jour_titres'] and fu.get('statusline') is g['statusline']\n"
            "out['vue'] = sorted(n for n in A4C + NOY if n in vue); out['moteur'] = sorted(n for n in A4C + NOY if n in mot)\n"
            "out['lecture_vue'] = all(n in vue for n in LEC)\n"
            "def essai(nom, f, *a):\n"
            "    try: f(*a); out[nom] = 'accepté'\n"
            "    except SystemExit as e: out[nom] = str(e.code)\n"
            "    except BaseException as e: out[nom] = type(e).__name__ + ': ' + str(e) + ' | ' + type(e.__cause__).__name__\n"
            "essai('ouvrir_role', act.ouvrir_developpeur, 'p', 'demo', 'x', 'coord', None, None)\n"
            "essai('ouvrir_inconnu', act.ouvrir_developpeur, 'z', 'demo', 'x', 'chef', None, None)\n"
            "essai('ouvrir_installation', act.ouvrir_developpeur, 'inst', 'demo', 'x', 'chef', None, None)\n"
            "essai('ouvrir_sujet', act.ouvrir_developpeur, 'p', 'X', 'x', 'chef', None, None)\n"
            "essai('fermer_role', act.fermer_developpeur, 'p', 'demo', 'intrus')\n"
            "essai('fermer_absent', act.fermer_developpeur, 'p', 'demo', 'chef')\n"
            "essai('domaine_nom', act.changer_domaine, 'p', 'ajouter', '*.joker.org', 'coord', False)\n"
            "essai('domaine_action', act.changer_domaine, 'p', 'changer', 'a.org', 'coord', False)\n"
            "essai('go_role', act.inscrire_go, 'p', 'demo', '1', 'spec.md', 'intrus', False)\n"
            "essai('go_cas', act.inscrire_go, 'p', 'demo', '9', 'spec.md', 'chef', False)\n"
            "essai('projet_role', act.ouvrir_projet, 'p', 'demo', 'chef', 'intrus')\n"
            "essai('projet_membres', act.ouvrir_projet, 'p', 'demo', 'intrus', 'chef')\n"
            "essai('projet_fermer', act.fermer_projet, 'p', 'demo', 'chef')\n"
            "essai('crochet', act.jouer_crochet, 'chef')\n"
            "essai('du_noyau', act.brancher, {'statusline': print})\n"
            "essai('pas_fonction', act.brancher, {'ouvrir_developpeur': 1})\n"
            "out['rien'] = not (g['AGENTS'] / 'p-demo').exists() and not (g['BERGER'] / 'equipes/p/domaines').exists() and not (g['BERGER'] / 'equipes/p/projets.json').exists()\n"
            "print(json.dumps(out))\n") % (str(t / "bin/berger"), ACTIONS_4C, tuple(NOYAU_4C), LECTURES_4C, COEUR_4C)
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {"services": ["?"], "lectures": ["?"], "coeur": ["?"], "noyau": False, "vue": ["?"], "moteur": ["?"], "lecture_vue": False}; print(r.stderr[-400:])
    dire(x["services"] == [] and x["lectures"] == [], f"4c, exécution : la famille equipes reçoit les sept services (ceux de noyau/actions.py) et les trois lectures (manquants : {x['services'] + x['lectures']})")
    dire(x["coeur"] == [], f"4c, exécution : rien du cœur ni du branchement n'existe pour elle (equipe_ouvrir, exiger_chef, _equipe, registre_projets, brancher…) ({x['coeur']})")
    dire(x["noyau"], "4c, exécution : lire_document, lire_interactif (alire), mettre_a_jour_titres et statusline (bureau), dans l'API d'action, restent ceux du noyau")
    dire(x["vue"] == [] and x["moteur"] == [], f"4c, exécution : une vue et un moteur ne reçoivent ni les services des équipes, ni lire_document, lire_interactif, mettre_a_jour_titres, statusline ({x['vue'] + x['moteur']})")
    dire(x["lecture_vue"], "4c, exécution : les lectures des équipes sont dans l'espace d'une vue (API de lecture)")
    dire(x.get("ouvrir_role", "").startswith("coord n'est pas le chef de projet de p (chef) : ouvrir refusé"), f"service ouvrir_developpeur, appelé SANS la famille : le chef seul ({x.get('ouvrir_role')})")
    dire(x.get("ouvrir_inconnu", "").startswith("projet d'équipe inconnu : z"), f"…projet inconnu refusé ({x.get('ouvrir_inconnu')})")
    dire(x.get("ouvrir_installation", "").startswith("[equipes.inst] : le dépôt ne peut pas être l'installation"), f"…dépôt = installation refusé ({x.get('ouvrir_installation', '')[:70]})")
    dire(x.get("ouvrir_sujet", "").startswith("sujet : 2 à 30 caractères"), f"…sujet invalide refusé ({x.get('ouvrir_sujet')})")
    dire(x.get("fermer_role", "").startswith("intrus n'est pas le chef de projet de p") and x.get("fermer_absent") == "pas de développeur p-demo",
         f"service fermer_developpeur : le chef seul, développeur absent refusé ({x.get('fermer_role', '')[:50]} ; {x.get('fermer_absent')})")
    dire(x.get("domaine_nom", "").startswith("« *.joker.org » n'est pas un nom de domaine exact") and x.get("domaine_action", "").startswith("berger equipe domaine <projet>"),
         f"service changer_domaine : nom inexact et action inconnue refusés ({x.get('domaine_nom', '')[:50]})")
    dire(x.get("go_role", "").startswith("seuls le chef de projet et le coordinateur de p demandent un go") and x.get("go_cas", "").startswith("cas : 1 à 5"),
         f"service inscrire_go : rôle et cas refusés ({x.get('go_role', '')[:50]} ; {x.get('go_cas', '')[:30]})")
    dire(x.get("projet_role", "").startswith("intrus n'est ni le chef de projet ni le coordinateur") and x.get("projet_membres", "").startswith("membres refusés : intrus")
         and x.get("projet_fermer") == "pas de projet ouvert p/demo", f"services ouvrir_projet, fermer_projet : rôle, membres, projet absent refusés ({x.get('projet_membres', '')[:40]})")
    dire(x.get("crochet") == "accepté", f"service jouer_crochet : un agent qui n'est pas développeur ne fait rien (réponse vide du crochet) ({x.get('crochet')})")
    dire(x.get("du_noyau", "").startswith("NameError") and x.get("pas_fonction", "").startswith("TypeError"),
         f"brancher refuse statusline (fonction du noyau, jamais branchée) et ce qui n'est pas une fonction ({x.get('du_noyau', '')[:60]} ; {x.get('pas_fonction', '')[:40]})")
    dire(x.get("rien"), "…aucun de ces refus n'a rien écrit (ni développeur, ni sites permis, ni registre de projets)")
    # (c) panne du cœur par un service, erreur dans la famille, ce qui passe (IndexError, entrée du crochet illisible)
    tete = "import io, json, runpy, sys\nsys.argv = ['berger']\ng = runpy.run_path(%r, run_name='essai'); c = g['commandes']; act = g['noyau'].actions\n" % str(t / "bin/berger")
    bilan = "print(json.dumps({'r': r, 'ecartees': {e['commandes']: e['cause'] for e in c.ecartees()}}))\n"
    essai_l = lambda v, a, p="False": f"try: c.lancer({v!r}, {a!r}, {p}); r = 'rien'\nexcept SystemExit as e: r = 'exit: ' + str(e.code)[:90]\nexcept BaseException as e: r = type(e).__name__ + ': ' + str(e)[:90]\n"
    def _jouer(corps):
        r = subprocess.run([sys.executable, "-c", tete + corps + bilan], env=env, capture_output=True, text=True)
        try: return json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError): print(r.stderr[-300:]); return {"r": "", "ecartees": {"?": "?"}}
    x = _jouer("def panne(*a): return {}['pane']\nact.brancher({'ouvrir_developpeur': panne})\n" + essai_l("equipe", ["ouvrir", "p", "demo", "x"], "True"))
    dire(x["r"] == "KeyError: 'pane'" and not x["ecartees"], f"4c : une panne du cœur passée par ouvrir_developpeur ressort telle qu'avant, la famille equipes n'est pas écartée ({x['r']}, {x['ecartees']})")
    r = subprocess.run([sys.executable, "-c", tete + "def panne(*a): return {}['pane']\nact.brancher({'ouvrir_projet': panne})\nc.lancer('projet', ['ouvrir', 'p', 'demo', 'chef'], True)\n"],
                       env=env, capture_output=True, text=True)
    dire(r.returncode == 1 and r.stderr.rstrip().splitlines()[-1] == "KeyError: 'pane'" and "écartée" not in r.stderr and "ErreurService" not in r.stderr,
         "…et la sortie d'erreur est celle d'avant (projet ouvrir : dernière ligne « KeyError: 'pane' », ni « écartée » ni ErreurService)")
    x = _jouer("vars(c.FAMILLES['equipes'])['json'] = None\n" + essai_l("equipe", ["liste", "p"], "True"))
    dire(x["r"].startswith("exit: commande equipe : famille equipes écartée (AttributeError") and "AttributeError" in x["ecartees"].get("equipes", "") and set(x["ecartees"]) == {"equipes"},
         f"4c : une erreur DANS la famille equipes, hors service, l'écarte et la NOMME, elle seule ({x['r'][:80]})")
    # renvoi n° 93 : une donnée d'équipe illisible (demande de fusion, projets.json, sites permis) n'est pas un défaut du module : l'erreur du lecteur sort
    # telle qu'avant, à l'endroit de la lecture seulement, sans écarter la famille ; PASSE ne s'élargit pas, une ValueError ailleurs dans le verbe écarte toujours
    _dv = t / "agents/p-vieux"; (_dv / "memory").mkdir(parents=True)
    _dv.joinpath("agent.conf").write_text("nom = P vieux\nmoteur = claude\nheures = aucune\nprojet = p\nsujet = vieux\nbranche = p/vieux\nport = 0\n")
    _dem = t / "equipes/p/demandes/vieux.json"; _dem.parent.mkdir(parents=True, exist_ok=True)
    for _cas, _octets, _attendu, _argv in (
            ("demande de fusion « { »", b"{", "JSONDecodeError", ["liste", "p"]),
            ("demande de fusion qui n'est pas un objet", b"[1]", "AttributeError", ["liste", "p"]),
            ("demande de fusion trop imbriquée", b"[" * 100000 + b"]" * 100000, "RecursionError", ["liste", "p"]),
            ("demande de fusion non UTF-8", b'{"etat": "\xff"}', "UnicodeDecodeError", ["liste", "p"]),
            ("demande de fusion, renvois illisibles", b'{"renvois": "trois"}', "ValueError", ["liste", "p"])):
        _dem.write_bytes(_octets)
        x = _jouer(essai_l("equipe", _argv, "True"))
        dire(x["r"].startswith(_attendu) and not x["ecartees"], f"4c : equipe liste, {_cas} : l'erreur d'avant ({_attendu}), la famille n'est pas écartée ({x['r'][:70]})")
    _dem.unlink()
    (t / "equipes/p/projets.json").write_bytes(b"[" * 100000 + b"]" * 100000)
    x = _jouer(essai_l("projet", ["liste"], "True"))
    dire(x["r"].startswith("RecursionError") and not x["ecartees"], f"4c : projet liste, projets.json trop imbriqué : l'erreur d'avant, la famille n'est pas écartée ({x['r'][:70]})")
    (t / "equipes/p/projets.json").unlink()
    (t / "equipes/p/domaines").write_bytes(b"exemple.org\n\xff\n")
    x = _jouer(essai_l("equipe", ["domaines", "p"], "True"))
    dire(x["r"].startswith("UnicodeDecodeError") and not x["ecartees"], f"4c : equipe domaines, liste non UTF-8 : l'erreur d'avant, la famille n'est pas écartée ({x['r'][:70]})")
    (t / "equipes/p/domaines").unlink()
    x = _jouer("vars(c.FAMILLES['equipes'])['_opt'] = lambda *a: int('x')\n" + essai_l("projet", ["ouvrir", "p", "demo", "chef", "--par", "chef"], "True"))
    dire(x["r"].startswith("exit: commande projet : famille equipes écartée (ValueError") and "ValueError" in x["ecartees"].get("equipes", ""),
         f"4c : une ValueError dans le verbe, hors lecture, écarte toujours la famille, nommée ({x['r'][:70]})")
    shutil.rmtree(_dv)
    x = _jouer(essai_l("crochet-equipe", []))
    dire(x["r"].startswith("IndexError") and not x["ecartees"], f"4c : l'IndexError d'un argument manquant passe, comme avant, sans écarter la famille ({x['r']})")
    x = _jouer("sys.stdin = io.StringIO('[' * 100000 + ']' * 100000)\n" + essai_l("crochet-equipe", ["chef"]))
    dire(x["r"].startswith("rien") and not x["ecartees"], f"4c : crochet-equipe d'un agent qui n'est pas développeur ne lit pas l'entrée, la famille n'est pas écartée ({x['r'][:60]})")
    x = _jouer("r = sorted({c.FAMILLE_DE[v] + ':' + v + ':' + ','.join(sorted(e.__name__ for e in ex)) for v, ex in c.FAMILLES['equipes'].PASSE.items()})\n")
    dire(x["r"] and len(x["r"]) == 3 and all(l.split(":")[2] == "ErreurService,IndexError,Refus" for l in x["r"]), f"4c : PASSE reste limité, le même pour chaque verbe des équipes ({x['r']})")
    x = _jouer("r = {v: c.DROITS[v]['prive'] for v in ('equipe', 'projet', 'crochet-equipe')}\nr['transition'] = sorted(v for v, f in c.FAMILLE_DE.items() if f == 'transition' and c.DROITS[v]['prive'])\n")
    dire(x["r"] == {"equipe": True, "projet": True, "crochet-equipe": False, "transition": []},
         f"4c : l'entrée privée obligatoire d'equipe et de projet vient des DROITS de la famille (plus aucun verbe privé dans la transition) ({x['r']})")
    # (d) la famille cassée : écartée et nommée, ses verbes inconnus, le reste tourne
    (t / "bin/commandes/equipes.py").write_text("raise RuntimeError('famille equipes volontairement cassée')\n")
    r = subprocess.run([str(t / "bin/berger"), "etat", "--json"], env=env, capture_output=True, text=True)
    try: ec = {e["commandes"]: e["cause"] for e in json.loads(r.stdout)["donnees"]["commandes_ecartees"]}
    except (ValueError, KeyError): ec = {}
    dire("RuntimeError" in ec.get("equipes", "") and set(ec) == {"equipes"}, f"4c : la famille equipes cassée est écartée et NOMMÉE, elle seule ({ec})")
    for _argv, _entree in ((["--stdin"], json.dumps(["equipe", "liste", "p"])), (["--stdin"], json.dumps(["projet", "ouvrir", "p", "demo", "chef"])), (["crochet-equipe", "chef"], "{}")):
        r = subprocess.run([str(t / "bin/berger"), *_argv], input=_entree, env=env, capture_output=True, text=True)
        _v = json.loads(_entree)[0] if _argv == ["--stdin"] else _argv[0]
        dire(r.returncode == 1 and r.stderr.startswith(f"commande inconnue : {_v}") and "⚠ commandes écartées : bin/commandes/equipes.py — RuntimeError" in r.stderr,
             f"4c : berger {_v} avec la famille cassée : « commande inconnue », la famille nommée (jamais servi en silence par le cœur)")
    dire(not (t / "equipes/p/projets.json").exists(), "4c : projet ouvrir (--stdin) avec la famille cassée : rien ouvert")
    r = subprocess.run([str(t / "bin/berger"), "vues"], env=env, capture_output=True, text=True)
    r2 = subprocess.run([str(t / "bin/berger"), "besoin", "liste", "--json"], env=env, capture_output=True, text=True)
    r3 = subprocess.run([str(t / "bin/berger"), "suivi", "chef"], env=env, capture_output=True, text=True)
    dire(r.returncode == 0 and "accueil" in r.stdout and r2.returncode == 0 and r3.returncode == 0, "4c : les autres familles et les vues tournent (vues, besoin liste --json, suivi)")

sys.exit(1 if ko else 0)
