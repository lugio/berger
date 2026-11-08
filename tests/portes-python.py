#!/usr/bin/env python3
"""Les portes et les commandes du courtier lancées avec le Python du SYSTÈME, sans les raccourcis de mise (06/11/2026).
Vécu : depuis la mise à jour omarchy du 05/11 (omarchy-settings 4.5.0, outils « lazy » de mise), chaque appel du raccourci
~/.local/share/mise/shims/python3 veut écrire dans ~/.local/share/mise ; dans un bac à sable il sort « mise ERROR Read-only
file system (os error 30) ». Le courtier mettait ces raccourcis en tête du PATH de ce qu'il lance : la porte verify
(bash tests/syntaxe.sh) mourait avant de démarrer, pour toute branche.
  1. scripts de portes (tests/syntaxe.sh, tests/portes-doc.sh, tests/suites.sh) : un FAUX raccourci python3 qui échoue toujours, dans un dossier
     …/mise/shims en tête du PATH, ne les arrête plus (témoin : le faux échoue bien seul) ;
  2. courtier (_commandes.env_lancement, commun à copie, commandes, equipe_dev et equipe_chef) : un faux python3 qui échoue,
     en tête du PATH du courtier, n'est jamais pris — la commande lancée passe par /usr/bin/python3 ; SEUL python3 change :
     herdr (et gh, codex, claude) reste celui des raccourcis mise, le reste du PATH est gardé (renvoi n° 173) ;
  3. /usr/bin/python3 absent : refus net, nommé, la commande n'est pas lancée (pas de repli sur le PATH) ;
  4. dans un vrai bac à sable (bubblewrap), le même python3 (NON JOUÉ si bubblewrap ne peut pas s'ouvrir ici) ;
  5. les scripts de portes ne remplacent pas leur PATH : seul leur python3 est choisi hors des raccourcis mise.
Usage : python3 tests/portes-python.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util, os, re, subprocess, sys, tempfile
from pathlib import Path

T = Path(__file__).resolve().parent; SRC = T.parent; ko = 0
SYSTEME = "/usr/bin/python3"
SONDE = "python3 -c 'import sys; print(\"interprete=\" + sys.executable)'"


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def charger(nom):
    spec = importlib.util.spec_from_file_location(f"essai_{nom}", SRC / "courtier/outils" / f"{nom}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


if not os.access(SYSTEME, os.X_OK):
    print(f"NON JOUÉ {SYSTEME} absent de cette machine : rien à prouver ici (le refus est prouvé plus bas par un chemin factice)")

with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    shims = t / "maison/.local/share/mise/shims"; shims.mkdir(parents=True)
    faux = t / "faux"; faux.mkdir()
    for d in (shims, faux):
        (d / "python3").write_text('#!/bin/sh\necho "mise ERROR Read-only file system (os error 30) — faux python3 du test" >&2\nexit 1\n')
        (d / "python3").chmod(0o755)
    (shims / "herdr").write_text("#!/bin/sh\necho herdr-des-raccourcis\n"); (shims / "herdr").chmod(0o755)   # un AUTRE outil des raccourcis

    # ── 1. Scripts de portes ─────────────────────────────────────────────────────────────────────────────────────────
    env = {**os.environ, "PATH": f"{shims}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}"}
    r = subprocess.run(["python3", "-c", "print(1)"], env=env, capture_output=True, text=True)
    dire(r.returncode != 0 and "faux python3" in r.stderr, "témoin : le faux raccourci mise python3 en tête du PATH échoue bien")
    r = subprocess.run(["bash", str(T / "syntaxe.sh")], env=env, capture_output=True, text=True, timeout=300)
    dire(r.returncode == 0 and r.stdout.startswith("ok syntaxe"), "porte verify (tests/syntaxe.sh) verte malgré le faux raccourci mise python3"
         + ("" if r.returncode == 0 else f" — {' '.join((r.stdout + r.stderr).split())[-200:]}"))
    r = subprocess.run(["bash", str(T / "portes-doc.sh")], env=env, capture_output=True, text=True, timeout=600)
    dire("faux python3" not in r.stdout + r.stderr, "porte doc (tests/portes-doc.sh) : le faux raccourci mise python3 n'est jamais appelé"
         + ("" if "faux python3" not in r.stdout + r.stderr else f" — {' '.join((r.stdout + r.stderr).split())[-200:]}"))
    r = subprocess.run(["bash", str(T / "suites.sh")], env={**env, "SUITE_SEULE": "sonde-shebang.py"}, capture_output=True, text=True, timeout=300)
    dire(r.returncode == 0 and r.stdout.startswith("ok"), "porte tests (tests/suites.sh) verte malgré le faux raccourci mise python3"
         + ("" if r.returncode == 0 else f" — {' '.join((r.stdout + r.stderr).split())[-200:]}"))

    # ── 2. Courtier : ce qu'il lance passe par /usr/bin/python3 ──────────────────────────────────────────────────────────
    base = charger("_commandes")
    lanceur = getattr(base, "env_lancement", None)
    dire(callable(lanceur), "courtier : _commandes.env_lancement existe (environnement commun de ce que le courtier lance)")
    if callable(lanceur):
        maison = os.environ["HOME"]; os.environ["HOME"] = str(t / "maison")   # ~/.local/share/mise/shims = les faux raccourcis
        try: e = lanceur({"PATH": f"{faux}:/usr/bin:/bin", "HOME": str(t / "maison")})
        finally: os.environ["HOME"] = maison
        morceaux = e["PATH"].split(":")
        dire(morceaux[0] == str(SRC / "courtier/python-systeme"), "courtier : le dossier du python3 du système est en tête du PATH")
        # Renvoi n° 173 : seul python3 change — le reste du PATH est gardé tel quel, raccourcis mise compris (herdr, gh, codex, claude).
        trouve = lambda x: subprocess.run(["bash", "-c", f"command -v {x}"], env={**os.environ, **e}, capture_output=True, text=True).stdout.strip()
        dire(trouve("python3") == str(SRC / "courtier/python-systeme/python3"), "courtier : python3 du PATH de lancement = python-systeme (faux shims python3 écarté)")
        dire(trouve("herdr") == str(shims / "herdr"), "courtier : herdr du PATH de lancement = celui des raccourcis mise (les autres outils ne changent pas)")
        dire(str(shims) in morceaux and str(faux) in morceaux, "courtier : le reste du PATH reçu est gardé (raccourcis mise compris)")
    os.environ["PATH"] = f"{faux}{os.pathsep}{shims}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}"   # celui du courtier
    commandes = charger("commandes")
    travail = t / "travail"; travail.mkdir()
    o = commandes.Outil({"dossier": str(travail), "lecture": {"sonde": SONDE}, "bac_a_sable": ["sonde-bac"],
                         "actions": {}, "masques": []}, None, None)
    try:
        r = o.verbes["sonde"]([])
        dire(r["code"] == 0 and f"interprete={SYSTEME}" in r["sortie"], f"courtier (commandes) : faux python3 en tête du PATH → la commande passe par {SYSTEME}"
             + ("" if r["code"] == 0 else f" — {' '.join(r['sortie'].split())[-200:]}"))
    except Exception as x: dire(False, f"courtier (commandes) : la sonde n'a pas tourné — {x}")

    # ── 3. /usr/bin/python3 absent : refus net, rien n'est lancé ─────────────────────────────────────────────────────────
    temoin = travail / "lance"
    o = commandes.Outil({"dossier": str(travail), "lecture": {"marque": f"touch {temoin}"}, "actions": {}, "masques": []}, None, None)
    vrai = getattr(commandes._base, "PYTHON_SYSTEME", None)
    commandes._base.PYTHON_SYSTEME = str(t / "absent/python3")
    try:
        o.verbes["marque"]([]); dire(False, "refus : /usr/bin/python3 absent → la commande a été acceptée")
    except RuntimeError as x:
        dire("introuvable" in str(x) and "absent/python3" in str(x), f"refus : python du système absent → refus nommé ({str(x)[:90]}…)")
    except Exception as x: dire(False, f"refus : erreur inattendue {type(x).__name__} : {x}")
    finally: commandes._base.PYTHON_SYSTEME = vrai
    dire(not temoin.exists(), "refus : la commande n'a pas été lancée (pas de repli sur le PATH)")

    # ── 3b. Le bac à sable ne cache pas le python3 du système quand l'installation est sous /tmp (correctif CI, 08/11/2026) ─────────────────
    #    Le bac à sable monte un tmpfs sur /tmp. La copie jouée par la CI (tests/clone-frais.sh : /tmp/bcfXXXXXX/…) y héberge courtier/python-systeme :
    #    il disparaissait, le PATH retombait sur /usr/local/bin/python3 et la sonde rendait « interprete=/usr/local/bin/python3 », pas /usr/bin/python3.
    #    Prouvé sur l'argv (sans bubblewrap) : le dossier du python3 du système est remonté EN LECTURE SEULE après le tmpfs ; hors /tmp, rien de plus.
    vrai_dossier = base.DOSSIER_PYTHON
    try:
        for dossier_py, attendu in ((Path("/tmp/bcfessai/depot/courtier/python-systeme"), True), (Path("/home/essai/berger/courtier/python-systeme"), False)):
            base.DOSSIER_PYTHON = dossier_py
            for tmp_propre in (None, "/tmp/agent-essai"):
                a = base.bac_a_sable(["true"], str(travail), [], tmp=tmp_propre)
                liaison = ["--ro-bind", str(dossier_py), str(dossier_py)]
                pos = next((i for i in range(len(a) - 2) if a[i:i + 3] == liaison), -1)
                mont_tmp = next((i for i in range(len(a) - 1) if a[i + 1] == "/tmp" and a[i] in ("--tmpfs", tmp_propre)), len(a))   # « --bind <tmp> /tmp » ou « --tmpfs /tmp »
                dire((pos > mont_tmp) if attendu else (pos == -1),
                     f"bac à sable ({'tmp propre' if tmp_propre else 'tmpfs'}) : python3 du système "
                     + ("sous /tmp remonté en lecture seule APRÈS le /tmp du bac" if attendu else "hors /tmp : aucune liaison de plus"))
    finally: base.DOSSIER_PYTHON = vrai_dossier

    # ── 4. Dans un vrai bac à sable ──────────────────────────────────────────────────────────────────────────────────────
    sonde_bac = subprocess.run(["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--unshare-net", "true"], capture_output=True)
    if sonde_bac.returncode:
        print("NON JOUÉ bubblewrap ne s'ouvre pas ici (bac à sable imbriqué) : python3 du bac à sable non prouvé")
    else:
        o = commandes.Outil({"dossier": str(travail), "lecture": {"sonde-bac": SONDE}, "bac_a_sable": ["sonde-bac"],
                             "actions": {}, "masques": []}, None, None)
        r = o.verbes["sonde-bac"]([])
        dire(r["code"] == 0 and f"interprete={SYSTEME}" in r["sortie"], f"bac à sable : faux python3 en tête du PATH → {SYSTEME}"
             + ("" if r["code"] == 0 else f" — {' '.join(r['sortie'].split())[-200:]}"))

# ── 5. Chaque lanceur du courtier passe par env_lancement ; les scripts de portes ne retirent les raccourcis que pour python3 ──
for f in ("copie.py", "commandes.py", "equipe_chef.py"):
    texte = (SRC / "courtier/outils" / f).read_text(encoding="utf-8")
    dire("env_lancement(" in texte and "mise/shims:" not in texte, f"courtier/outils/{f} construit son PATH par env_lancement")
for f in ("syntaxe.sh", "portes-doc.sh", "suites.sh"):
    lignes = [l for l in (T / f).read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#")]
    global_ = re.compile(r"(^|;|then)\s*PATH=(\$_sans_mise\s*(;|$)|\$\(tr )")      # PATH du script remplacé (pas un préfixe d'UNE commande)
    dire(not any(global_.search(l) for l in lignes),
         f"tests/{f} ne retire pas les raccourcis mise de son propre PATH (seul python3 est choisi hors d'eux)")

# ── 6. Sockets témoins sans aucune connexion : le fichier des connexions n'existe pas, et suites.sh ne le dit pas (correctif CI, 08/11/2026) ──
#    Le témoin n'écrit « i vecteur » qu'à une connexion (tests/_temoins.py, mode « a »). Sans connexion — le cas NORMAL — le fichier est absent et
#    `done <fichier 2>/dev/null` laissait bash écrire « suites.sh: ligne 242: …/connexions: No such file or directory » (le « 2>/dev/null »
#    ne couvre pas l'échec de la redirection d'entrée, évaluée avant lui). On joue la fonction _temoins_verifier telle qu'écrite dans suites.sh.
texte = (T / "suites.sh").read_text(encoding="utf-8")
m = re.search(r"^_temoins_verifier\(\) \{\n.*?^\}\n", texte, flags=re.S | re.M)
dire(m is not None, "suites.sh : la fonction _temoins_verifier est trouvée")
if m:
    with tempfile.TemporaryDirectory() as t:
        racine = Path(t) / "temoins"; racine.mkdir()                                  # aucun fichier « connexions »
        script = ("dire() { echo \"$1 $4\"; }; _sf=(a.py); _rouges=(); _temoins_arreter() { :; }; sleep() { :; }\n" + m.group(0)
                  + f"_temoins_racine={racine}\n_temoins_verifier\necho \"rouges=${{#_rouges[@]}}\"\n")
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
        dire(r.returncode == 0 and r.stderr == "", "suites.sh : aucune connexion aux témoins → rien sur la sortie d'erreur" + ("" if r.stderr == "" else f" — {r.stderr.strip()[:200]}"))
        dire(r.stdout.startswith("ok ") and "rouges=0" in r.stdout, "suites.sh : aucune connexion aux témoins → verdict ok, aucune suite en échec")

sys.exit(1 if ko else 0)
