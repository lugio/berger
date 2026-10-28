#!/usr/bin/env python3
"""Contrat du noyau (modulaire, lot 1) : un module de bin/vues/ n'emploie que l'API de bin/noyau/api.py et la bibliothèque standard ;
chaque nom de l'API existe ; la frontière tient À L'EXÉCUTION (un nom du cœur hors API n'existe pas pour une vue, la vue fautive est
écartée et NOMMÉE, les autres tournent) ; aucune vue n'est remise dans les globales du cœur. Une installation JETABLE.
Lot 2 : idem pour les moteurs (bin/moteurs/). Lot 3 : idem pour les familles de commandes (bin/commandes/) — un module n'emploie que l'API et la bibliothèque
standard ; seule la famille de transition reçoit VERBES_COEUR (le cœur ne prête rien aux autres) ; une famille cassée ou en doublon est écartée et nommée, les autres tournent.
Lot 3 bis : chaque nom ajouté à l'API pour les verbes déplacés existe dans son module du noyau, n'a plus de définition dans le cœur et ne passe par aucun
chemin du cœur réservé au lot 4 (coffre, mur, bac à sable, courtier, démarrage d'agent…) ; ce qu'un verbe déclare dans PASSE (IndexError…) et Refus (refus d'usage voulu, redevenu une ValueError ordinaire) sortent comme avant sans écarter la famille ; une ValueError ordinaire écarte la famille.
Usage : python3 tests/contrat-noyau.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast, builtins, json, os, re, shutil, subprocess, sys, tempfile
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
    """Noms lus par un module sans être définis par lui, ni builtin, ni dans l'API : (nom, ligne)."""
    t = ast.parse(Path(fichier).read_text(encoding="utf-8"))
    definis = set()
    for n in ast.walk(t):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)): definis.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)): definis.add(n.id)
        elif isinstance(n, ast.arg): definis.add(n.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names: definis.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name: definis.add(n.name)
    return sorted({(n.id, n.lineno) for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                   and n.id not in definis and n.id not in libres_ok})


# 1. contrat statique : chaque vue
for f in sorted((SRC / "bin/vues").glob("*.py")):
    if f.name.startswith("_"): continue
    mauvais = noms_libres(f)
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
    mauvais = noms_libres(f)
    dire(not mauvais, f"moteurs/{f.name} : n'emploie que l'API, BASE_NOYAU et ce que le cœur lui prête" + (f" — hors liste : {mauvais}" if mauvais else ""))
libres_ok -= prete

# 1c. contrat statique : chaque famille de commandes (lot 3) n'emploie QUE l'API du noyau et la bibliothèque standard — aucune exception : ni nom privé du
#     noyau, ni fonction ou constante du cœur prêtée (relecture du 28/10). Un verbe qui en aurait besoin reste dans bin/berger jusqu'au lot 4.
#     Seule la famille de transition reçoit une chose, VERBES_COEUR (le registre des verbes du cœur, qu'elle ne fait qu'inscrire).
fichiers_commandes = sorted(f for f in (SRC / "bin/commandes").glob("*.py") if not f.name.startswith("_"))
dire({"alire.py", "veille.py", "etat.py", "vues.py", "bureau.py", "journal.py", "transition.py"} <= {f.name for f in fichiers_commandes},
     "une famille par fichier : alire, veille, etat, vues, bureau, journal et la transition (bin/commandes/)")
_cinit = (SRC / "bin/commandes/__init__.py").read_text(encoding="utf-8")
dire(not re.search(r"COEUR_FONCTIONS|COEUR_CONSTANTES|COMMANDES_NOYAU|def brancher", _cinit), "bin/commandes/__init__.py ne prête rien : ni liste COEUR_*, ni COMMANDES_NOYAU, ni brancher")
for f in fichiers_commandes:
    if f.name == "__init__.py": continue                      # le paquet est du cœur (comme moteurs/__init__.py) : il n'est pas un module écartable
    if f.name == "transition.py": libres_ok.add("VERBES_COEUR")
    mauvais = noms_libres(f)
    libres_ok.discard("VERBES_COEUR")
    dire(not mauvais, f"commandes/{f.name} : n'emploie que l'API du noyau et la bibliothèque standard" + (f" — hors API : {mauvais}" if mauvais else ""))


# 1d. lot 3 bis : les noms ajoutés à l'API pour les verbes déplacés. Chacun : défini dans son module du noyau, listé dans l'API, employé par son verbe dans la
#     famille indiquée, ABSENT du cœur (déplacé, pas copié) ; et sa fermeture d'appels (dans le noyau) ne touche aucun chemin réservé au lot 4.
NOUVEAUX = {                       # nom : (module du noyau, famille qui l'emploie)
    "journal": ("agents", "journal"), "Refus": ("ecarts", "journal"), "liste_vues": ("registre", "vues"), "etat": ("ecrans", "etat"),
    "validations": ("ecrans", "etat"), "lire_document": ("ecrans", "alire"), "lire_interactif": ("ecrans", "alire"),
    "notifier": ("bandeaux", "bureau"), "mettre_a_jour_titres": ("bandeaux", "bureau"), "statusline": ("bandeaux", "bureau"),
}
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
        loc |= {(al.asname or al.name).split(".")[0] for x in ast.walk(n) if isinstance(x, (ast.Import, ast.ImportFrom)) for al in x.names}
        for x in ast.walk(n):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load) and x.id not in loc:
                if x.id in propres: pile.append(propres[x.id])
                elif x.id in plat:
                    vu_noms.add(x.id); pile.append(plat[x.id])
                elif x.id not in dir(builtins) and x.id not in _imports and x.id not in api.STDLIB and x.id != "__file__": libres.add(x.id)
            elif isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr in vues:
                pile += vues[x.func.attr]
    return vu_noms, libres
for nom, (module, famille) in NOUVEAUX.items():
    texte_famille = (SRC / f"bin/commandes/{famille}.py").read_text(encoding="utf-8")
    dire(nom in _tout[module] and nom in api.API and re.search(r"\b%s\(" % nom, texte_famille) and nom not in _coeur,
         f"API : {nom} est défini dans noyau/{module}.py, listé dans l'API, employé par commandes/{famille}.py et absent du cœur")
    atteints, libres = _fermeture(nom)
    mauvais = (atteints | libres) & INTERDITS
    dire(not mauvais and not libres, f"API : {nom} ne passe par aucun chemin réservé au lot 4 ni par aucun nom que le noyau ne définit pas" + (f" — {sorted(mauvais | libres)}" if mauvais or libres else ""))
for module in ("registre", "ecrans", "bandeaux"):
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

# 1e. lot 3 bis : le paquet bin/commandes/ se charge SEUL, sans config.toml ni environnement (les tests de forme d'accès le chargent ainsi) : il n'importe que noyau.api et noyau.ecarts
r = subprocess.run([sys.executable, "-I", "-c", "import sys, importlib.util\nsys.path.insert(0, %r)\nsp = importlib.util.spec_from_file_location('commandes_seul', %r)\n"
                    "m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); print('ok')" % (str(SRC / "bin"), str(SRC / "bin/commandes/__init__.py"))],
                   env={}, capture_output=True, text=True)
dire(r.stdout.strip() == "ok", f"bin/commandes/ se charge sans config.toml ni environnement ({r.stderr.strip()[-120:] or 'ok'})")

# 2. chaque nom de l'API existe dans le noyau (pas de nom fantôme) et la liste n'a pas de doublon
os.environ.setdefault("BERGER_DIR", tempfile.mkdtemp())
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp); _produit.copier(SRC, t); (t / "config.toml").write_text('proprietaire = "Camille"\n')
    env = {**os.environ, "BERGER_DIR": str(t)}
    r = subprocess.run([sys.executable, "-c",
        "import sys; sys.path.insert(0, %r)\nfrom noyau.config import *\nfrom noyau.transport import *\nfrom noyau.affichage import *\n"
        "from noyau.agents import *\nfrom noyau.herdr import *\nfrom noyau.lectures import *\nfrom noyau.registre import *\nfrom noyau.ecrans import *\nfrom noyau.bandeaux import *\nfrom noyau import api\n"
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
                                                  "def args(a, interactif=True): return []\ndef lecteur_conso(): return lambda index: []\n")
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

sys.exit(1 if ko else 0)
