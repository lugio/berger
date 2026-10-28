#!/usr/bin/env python3
"""Tests de l'espace de pilotage « Berger » dans Herdr — sans modèle, avec un FAUX Herdr (jamais le vrai) : nom créé par
berger espace ensemble selon icone_berger, et berger refaire-espace berger qui retrouve l'espace sous son nom actuel comme
sous l'ancien (« Berger », créé avant icone_berger) ; onglet Catalogue créé, et ajouté par refaire-espace à un espace
qui ne l'a pas ; onglets créés avec leur icône, ceux d'un espace d'avant renommés. Usage : python3 tests/espaces.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["FAUX_HERDR"]; etat = json.load(open(T + "/etat.json")); a = sys.argv[1:]
with open(T + "/appels.log", "a") as f: f.write(json.dumps(a) + "\n")
r = {}
if a[:2] == ["workspace", "create"]:
    r = {"workspace": {"workspace_id": "w9"}, "tab": {"tab_id": "w9:t1"}, "root_pane": {"pane_id": "w9:p1"}}
elif a[:2] == ["tab", "create"]: r = {"tab": {"tab_id": "w9:t2"}, "root_pane": {"pane_id": "w9:p2"}}
elif a[:2] == ["workspace", "list"]: r = {"workspaces": [{"workspace_id": "w1", "label": etat["libelle"]}]}
elif a[:2] == ["tab", "list"]: r = {"tabs": [{"tab_id": f"w1:t{n + 1}", "label": l} for n, l in enumerate(etat.get("onglets", ["Accueil"]))]}
elif a[:2] == ["pane", "list"]: r = {"panes": [{"pane_id": f"w1:p{n + 1}", "tab_id": f"w1:t{n + 1}"} for n, _ in enumerate(etat.get("onglets", ["Accueil"]))]}
print(json.dumps({"result": r}))
'''


def installation(t, config):
    _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    (t / "coffre.json").write_text("{}")
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n' + config)
    (t / "faux").mkdir(exist_ok=True); (t / "faux/herdr").write_text(FAUX_HERDR); os.chmod(t / "faux/herdr", 0o755)
    (t / "faux/etat.json").write_text(json.dumps({"libelle": "aucun"}))
    return {**os.environ, "BERGER_DIR": str(t), "FAUX_HERDR": str(t / "faux"), "BERGER_HERDR": str(t / "faux/herdr"),
            "PATH": f"{t}/faux:" + os.environ["PATH"]}


def berger(t, env, *args):
    return subprocess.run([sys.executable, str(t / "bin/berger"), *args], env=env, capture_output=True, text=True, timeout=60)


def appels(t):
    f = t / "faux/appels.log"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


for config, attendu, cas in (("", "Berger", "sans icone_berger"), ('icone_berger = "🐑"\n', "🐑 Berger", "avec icone_berger")):
    with tempfile.TemporaryDirectory() as t:
        t = Path(t); env = installation(t, config)
        # SÉCURITÉ DU TEST : il ne doit parler QU'AU faux Herdr — sinon on s'arrête tout de suite
        sonde = subprocess.run([sys.executable, "-c", f"import runpy,sys;sys.argv=['b'];m=runpy.run_path({str(t / 'bin/berger')!r},run_name='x');print(m['HERDR'])"],
                               env=env, capture_output=True, text=True)
        if sonde.stdout.strip() != str(t / "faux/herdr"): sys.exit(f"ARRÊT : Berger n'utiliserait pas le faux Herdr ({sonde.stdout.strip() or sonde.stderr[-200:]})")
        r = berger(t, env, "espace", "ensemble")
        cree = [a for a in appels(t) if a[:2] == ["workspace", "create"]]
        libelle = cree[0][cree[0].index("--label") + 1] if cree else None
        dire(r.returncode == 0 and libelle == attendu, f"espace ensemble ({cas}) : espace créé sous le nom « {attendu} »"
             + ("" if libelle == attendu else f" — obtenu {libelle!r}, code {r.returncode} {r.stderr.strip()[-120:]}"))
        for existant in sorted({attendu, "Berger"}):
            (t / "faux/etat.json").write_text(json.dumps({"libelle": existant})); (t / "faux/appels.log").unlink(missing_ok=True)
            r = berger(t, env, "refaire-espace", "berger")
            dire(r.returncode == 0 and "pas d'espace Berger" not in r.stderr,
                 f"refaire-espace berger ({cas}) : retrouve l'espace nommé « {existant} »"
                 + ("" if r.returncode == 0 else f" — code {r.returncode} : {r.stderr.strip()[-120:]}"))

with tempfile.TemporaryDirectory() as t:
    t = Path(t); env = installation(t, "")
    berger(t, env, "espace", "ensemble")
    labels = [a[a.index("--label") + 1] for a in appels(t) if a[:2] == ["tab", "create"]]
    TOUS = ["📐 Livrables", "🗂 Documents", "📋 Tableau", "🚦 Synthèse", "🔎 Sources", "🔔 Décisions", "✅ Checklists", "📖 À lire", "🔐 Courtier", "💬 Échanges", "📚 Catalogue", "🪙 Tokens"]
    dire(labels == TOUS, f"espace ensemble : onglets {' · '.join(TOUS)} (obtenu {labels})")
    renommes = [a[3] for a in appels(t) if a[:2] == ["tab", "rename"]]
    dire(renommes == ["🏠 Accueil"], f"espace ensemble : 1er onglet renommé « 🏠 Accueil » (obtenu {renommes})")
    dire(any(a[:2] == ["pane", "run"] and a[-1].endswith("panneau catalogue") for a in appels(t)), "l'onglet Catalogue lance berger panneau catalogue")
    for onglets, attendu, renommes_att, cas in (
            (["Accueil", "Courtier", "Échanges"], ["📐 Livrables", "🗂 Documents", "📋 Tableau", "🚦 Synthèse", "🔎 Sources", "🔔 Décisions", "✅ Checklists", "📖 À lire", "📚 Catalogue", "🪙 Tokens"], ["🏠 Accueil", "🔐 Courtier", "💬 Échanges"], "espace d'avant le Catalogue et les icônes"),
            (["🏠 Accueil"] + TOUS, [], ["🏠 Accueil"], "espace complet, déjà avec icônes"),
            (["🏠 Accueil", "📋 Tableau", "📖 À lire", "🔐 Courtier", "💬 Échanges", "📚 Catalogue", "🪙 Tokens"], ["📐 Livrables", "🗂 Documents", "🚦 Synthèse", "🔎 Sources", "🔔 Décisions", "✅ Checklists"], ["🏠 Accueil"], "espace d'avant la Synthèse"),
            (["🏠 Accueil", "📖 À lire", "🔐 Courtier", "💬 Échanges", "📚 Catalogue", "🪙 Tokens", "🚦 Synthèse", "🔎 Sources"], ["📐 Livrables", "🗂 Documents", "📋 Tableau", "🔔 Décisions", "✅ Checklists"], ["🏠 Accueil"], "espace d'avant le Tableau")):
        (t / "faux/etat.json").write_text(json.dumps({"libelle": "Berger", "onglets": onglets})); (t / "faux/appels.log").unlink(missing_ok=True)
        r = berger(t, env, "refaire-espace", "berger")
        crees = [a[a.index("--label") + 1] for a in appels(t) if a[:2] == ["tab", "create"]]
        dire(r.returncode == 0 and crees == attendu, f"refaire-espace berger ({cas}) : onglets ajoutés {attendu or 'aucun'} (obtenu {crees})")
        renommes = list(dict.fromkeys(a[3] for a in appels(t) if a[:2] == ["tab", "rename"]))
        dire(renommes == renommes_att, f"refaire-espace berger ({cas}) : onglets renommés {renommes_att} (obtenu {renommes})")

with tempfile.TemporaryDirectory() as t:   # panneaux déjà ouverts : relancés (code à jour) ; onglet inconnu : intact
    t = Path(t); env = installation(t, "")
    (t / "faux/etat.json").write_text(json.dumps({"libelle": "Berger", "onglets": ["🏠 Accueil", "Mon onglet", "🔐 Courtier", "💬 Échanges", "📖 À lire"]}))
    r = berger(t, env, "refaire-espace", "berger")
    runs = {a[2]: a[3] for a in appels(t) if a[:2] == ["pane", "run"]}
    ctrl = {a[2] for a in appels(t) if a[:2] == ["pane", "send-keys"]}
    attendu = {"w1:p1": "panneau accueil", "w1:p3": "panneau courtier", "w1:p4": "panneau echanges", "w1:p5": "bin/berger lire"}
    dire(r.returncode == 0 and all(runs.get(k, "").endswith(v) for k, v in attendu.items()) and ctrl == set(attendu),
         f"refaire-espace berger : panneaux ouverts arrêtés puis relancés (Accueil, Courtier, Échanges, À lire) (obtenu {runs}, ctrl+c {sorted(ctrl)})")
    dire("w1:p2" not in runs and "w1:p2" not in ctrl, "refaire-espace berger : un onglet inconnu n'est jamais touché")
    dire(not any(k.startswith("w9:") and "panneau" in v and k in ctrl for k, v in runs.items()),
         "refaire-espace berger : les onglets ajoutés ne sont pas arrêtés (déjà neufs)")

with tempfile.TemporaryDirectory() as t:
    t = Path(t); env = installation(t, "")
    code = (f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(t / 'bin/berger')!r},run_name='x');"
            "print(json.dumps([g['nom_onglet'](x) for x in ('🏠 Accueil', 'Accueil', 'Mon onglet', '', None)] + [g['onglet']('Inconnu'), g['onglet']('Fiche')]"
            " + [all(len(i) == 1 for i in g['ICONES_ONGLETS'].values())]))")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    v = json.loads(r.stdout or "[]")
    dire(v[:5] == ["Accueil", "Accueil", "Mon onglet", "", ""], f"nom_onglet : reconnaît un onglet avec ou sans icône, laisse un autre nom intact (obtenu {v[:5]})")
    dire(v[5:7] == ["Inconnu", "📇 Fiche"], f"onglet : icône pour un onglet connu, rien pour un autre (obtenu {v[5:7]})")
    dire(v[7:] == [True], "chaque icône tient en UN caractère (pas de décalage dans le terminal)")

sys.exit(1 if ko else 0)
