#!/usr/bin/env python3
"""Interface web v2, lot 1 — lecture (spec docs/plans/2026-11-03-interface-web-v2-spec.md ; la maquette
docs/plans/interface-web-v2/maquette-accueil.html fait foi). Sans modèle, faux Herdr, installation JETABLE (tests/_jeu_vues.py).
Vérifie :
 1. une SEULE source d'icônes et de libellés (bin/page/icones.json), lue par les deux : Herdr (ICONES_ONGLETS, onglet()) en
    symbole texte, la page web (servie à /icones.json) en SVG ; aucun tracé SVG ni symbole d'onglet écrit ailleurs (app.js, index.html,
    bin/vues/) ; chaque icône : un caractère qui n'est pas un émoji, des formes SVG d'une liste fermée ;
 2. aucun émoji dans la page (app.js, app.css, index.html, icones.json) ni dans les libellés d'onglets de Herdr ;
 3. aucune bordure colorée à gauche (ni liseré coloré en haut) dans la feuille de style ;
 4. l'onglet Décisions est absent du web (berger vues --json) ET de Herdr (ONGLETS_BERGER, PANNEAUX_BERGER), `berger vue decisions`
    reste ; `berger refaire-espace berger` ferme l'ancien onglet par son titre EXACT (« 🔔 Décisions » ou « Décisions ») ;
 5. menu latéral repliable : un bouton, un état mémorisé dans le navigateur seulement (localStorage, clé berger-menu) — prouvé dans
    le faux DOM par tests/interface.py, et ici dans un vrai navigateur si Playwright est présent ;
 6. avec Playwright (s'il est présent : PAS une dépendance du projet ; sinon « NON JOUÉ ») : aux largeurs 1440, 820 et 390, pas de
    débordement horizontal, « null » absent, aucun émoji, aucune bordure gauche colorée, Décisions absent ; le menu replié survit au
    rechargement ; une fenêtre de détail s'ouvre et se ferme (Échap) ; une seule requête par vue au premier chargement.
Usage : python3 tests/interface-v2.py (0 = tout passe). Playwright : BERGER_PLAYWRIGHT=<dossier du module playwright ou
playwright-core>, BERGER_CHROMIUM=<navigateur> (sinon ceux que Playwright connaît)."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

SRC = Path(__file__).resolve().parent.parent
PAGE = SRC / "bin/page"
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


# Émojis : les plages des pictogrammes Unicode (Extended_Pictographic, à quelques signes près), les drapeaux, le sélecteur
# de présentation émoji et le liant — la page applique la même règle avec \p{Extended_Pictographic}.
PLAGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF), (0x231A, 0x231B), (0x23E9, 0x23FA), (0x25AA, 0x25AB), (0x25FB, 0x25FE),
          (0xFE0F, 0xFE0F), (0x200D, 0x200D), (0x2194, 0x2199), (0x21A9, 0x21AA), (0x3030, 0x3030), (0x303D, 0x303D), (0x3297, 0x3299))


def emojis(t): return sorted({c for c in t if any(a <= ord(c) <= b for a, b in PLAGES)})


src = json.loads((PAGE / "icones.json").read_text())
app_js, app_css, index = ((PAGE / f).read_text() for f in ("app.js", "app.css", "index.html"))

# ── 1. une seule source
FORMES = {"path", "rect", "circle"}
mal = {n: i for n, i in src["icones"].items() if not (isinstance(i.get("texte"), str) and len(i["texte"]) == 1 and not emojis(i["texte"])
                                                      and i.get("svg") and all(f in FORMES and isinstance(a, dict) for f, a in i["svg"]))}
dire(not mal, f"icones.json : chaque icône a un symbole texte d'UN caractère sans émoji et un SVG de formes permises ({sorted(FORMES)}) (fautives : {sorted(mal)})")
inconnues = {n: o["icone"] for n, o in src["onglets"].items() if o.get("icone") not in src["icones"]} | \
            {r: i for r, i in src["roles"].items() if i not in src["icones"]}
dire(not inconnues and all(o.get("libelle") for o in src["onglets"].values()), f"icones.json : chaque onglet a un libellé et une icône connue, chaque rôle aussi (inconnues : {inconnues})")
traces = re.findall(r'\bd\s*[:=]\s*["\']M|<path|<svg[^>]*>\s*<|\bM\d+(?:\.\d+)? \d', app_js + index)
dire(not traces and "/icones.json" in app_js and "const ICONES = {" not in app_js,
     f"page : aucun tracé SVG écrit dans app.js ni index.html, les icônes viennent de /icones.json (trouvés : {traces[:3]})")
symboles = {i["texte"] for i in src["icones"].values() if len(i["texte"]) == 1 and not i["texte"].isascii()}
dans_vues = [f.name for f in (SRC / "bin/vues").glob("*.py") if re.search(r"^ICONE(_GROUPE)? = ", f.read_text(), re.M)]
dire(not dans_vues, f"bin/vues/ : plus aucune constante ICONE (la source commune les porte) (encore : {dans_vues})")
dire('"/icones.json": ("icones.json"' in (SRC / "bin/interface.py").read_text(), "le serveur de l'interface sert la source commune à /icones.json")

# ── 2. aucun émoji dans la page
for nom, t in (("app.js", app_js), ("app.css", app_css), ("index.html", index), ("icones.json", (PAGE / "icones.json").read_text())):
    dire(not emojis(t), f"bin/page/{nom} : aucun émoji ({emojis(t)})")

# ── 3. aucune bordure colorée à gauche, aucun liseré coloré
css = re.sub(r"/\*.*?\*/", "", app_css, flags=re.S)
gauche = re.findall(r"border-left(?:-color|-width|-style)?\s*:[^;}]*", css) + re.findall(r"border-inline-start[^:]*:[^;}]*", css)
gauche = [g for g in gauche if not re.fullmatch(r"border-left(?:-width)?\s*:\s*0(?:px)?\s*", g.strip())]
liseres = re.findall(r"border-(?:top|bottom)\s*:\s*[2-9]px\s+solid\s+var\(--(?:rouge|jaune|vert|bleu)[^)]*\)", css)
dire(not gauche and not liseres, f"app.css : aucune bordure à gauche ni liseré coloré (trouvés : {gauche + liseres})")

# ── 4. Décisions : retiré du web et de Herdr, la vue reste en ligne de commande
with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t, marquages=True); env = {k: v for k, v in env.items() if k != "BERGER_AGENT"}
    b = lambda *a, **k: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env={**env, **k.get("env", {})}, capture_output=True, text=True, timeout=120)
    vues = json.loads(b("vues", "--json").stdout)["vues"]
    nav = [v for v in vues if v["onglet"] == "berger"]
    dire(not [v for v in nav if v["titre"] == "Décisions" or v["groupe"] == "Décisions"] and any(v["type"] == "decisions" and v["onglet"] is None for v in vues),
         "web : Décisions n'est plus un onglet (berger vues --json : onglet None), la vue reste lisible")
    dire(all(v["icone"] in src["icones"] for v in nav), f"berger vues --json : l'icône de chaque onglet est un NOM de la source commune ({[v['icone'] for v in nav]})")
    r = b("vue", "decisions", "--json"); dire(r.returncode == 0 and "decisions" in json.loads(r.stdout)["donnees"], "berger vue decisions --json : toujours là (ligne de commande)")
    code = ("import runpy,sys,json;sys.argv=['b'];g=runpy.run_path(sys.argv[0] if False else %r,run_name='x');"
            "print(json.dumps({'onglets':[l for l,_ in g['ONGLETS_BERGER']],'panneaux':g['PANNEAUX_BERGER'],'icones':g['ICONES_ONGLETS'],"
            "'libelles':[g['onglet'](n) for n in ['Accueil']+[l for l,_ in g['ONGLETS_BERGER']]+['Travail','Fiche','Missions','Équipe']],"
            "'anciens':g['ANCIENS_ONGLETS'].get('Décisions'),'noms':[g['nom_onglet'](x) for x in ('🔔 Décisions','🏠 Accueil','⌂ Accueil','Notes Décisions')]}))") % str(i / "bin/berger")
    x = json.loads(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120).stdout.strip().splitlines()[-1])
    dire("Décisions" not in x["onglets"] and "Décisions" not in x["panneaux"] and not any("decisions" in v for v in x["panneaux"].values()),
         f"Herdr : Décisions absent des onglets et des panneaux de l'espace Berger ({x['onglets']})")
    attendus = [f"{src['icones'][src['onglets'][n]['icone']]['texte']} {src['onglets'][n]['libelle']}" for n in ['Accueil'] + x["onglets"] + ['Travail', 'Fiche', 'Missions', 'Équipe']]
    dire(x["libelles"] == attendus and not emojis("".join(x["libelles"])), f"Herdr : libellés d'onglets = symbole + libellé de la source commune, sans émoji ({x['libelles']})")
    dire(x["anciens"] == ["Décisions", "🔔 Décisions"] and x["noms"] == ["Décisions", "Accueil", "Accueil", "Notes Décisions"],
         f"Herdr : l'ancien onglet est reconnu par son titre EXACT (« Décisions », « 🔔 Décisions ») ; un onglet de l'utilisateur reste intact ({x['anciens']}, {x['noms']})")

    # ── 6. un vrai navigateur, s'il est là
    module = os.environ.get("BERGER_PLAYWRIGHT") or next((p for p in ("playwright", "playwright-core") if shutil.which("node") and subprocess.run(
        ["node", "-e", f"require.resolve('{p}')"], capture_output=True).returncode == 0), None)
    if not module or not shutil.which("node"):
        print("NON JOUÉ navigateur réel (largeurs, débordement, menu mémorisé, fenêtres) : Playwright absent de cette machine")
    else:
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        with open(i / "config.toml", "a") as f: f.write(f"[interface]\nport = {port}\n")
        lien = b("interface", "lien").stdout.strip()
        srv = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(100):
                try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
                except OSError: time.sleep(0.1)
            r = subprocess.run(["node", str(SRC / "tests/_page_navigateur.js"), lien], env={**os.environ, "BERGER_PLAYWRIGHT": module},
                               capture_output=True, text=True, timeout=300)
            try: res = json.loads(r.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError): res = {"#lancement": "ERREUR " + (r.stderr or r.stdout)[-400:]}
            if str(res.get("#lancement", "")).startswith("NON JOUÉ"): print(res["#lancement"])
            else:
                for k, v in res.items(): dire(v == "ok", f"navigateur : {k} ({v})")
        finally:
            srv.terminate(); srv.wait(timeout=10)

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
