#!/usr/bin/env python3
"""Interface web v2 — finition de l'interface (spec docs/plans/2026-11-05-interface-finition-ui-spec.md). Sans modèle, faux Herdr,
installation JETABLE (tests/_jeu_vues.py), un FAUX COURTIER (comme tests/interface-actions.py) pour le parcours d'une décision.
Vérifie :
 1. SANS navigateur — bin/page/app.css : aucune couleur en dur (#…, rgb(), hsl(), nom de couleur) hors des blocs de jetons « :root » ;
    ces blocs ne portent que des jetons (--nom: valeur) ; le thème sombre redéfinit chaque jeton de couleur du thème clair, de la même
    façon pour la préférence du système et pour le choix mémorisé ; aucune bordure à gauche (ni border-inline-start) ; transitions
    par le jeton de durée (150 ms au plus) et coupées sous prefers-reduced-motion ; aucune taille de texte sous 12 px ;
 2. SANS navigateur — bin/page/app.js : aucune couleur en dur ; la décision passe par les mêmes appels qu'au lot 2 (/api/action/apercu
    puis /api/action) et aucun autre ; aucun innerHTML ;
 3. AVEC Playwright (s'il est présent : PAS une dépendance du projet ; sinon « NON JOUÉ », jamais « ok ») : tests/_page_mesures.js
    mesure aux 4 largeurs (1920, 1440, 820, 390) et dans les 2 thèmes — contraste (pire cas cité), tailles, cibles, débordement, titre
    jamais coupé au milieu d'un mot, clavier, parcours en 2 clics, refus sans motif impossible, rafraîchissement fenêtre ouverte,
    CLS, À lire en deux volets, convention En bref / Pour toi / Détail replié, thème mémorisé, mouvement réduit.
Usage : python3 tests/interface-finition.py (0 = tout passe). Playwright : BERGER_PLAYWRIGHT=<dossier du module playwright ou
playwright-core>, BERGER_CHROMIUM=<navigateur> (sinon ceux que Playwright connaît)."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

SRC = Path(__file__).resolve().parent.parent
PAGE = SRC / "bin/page"
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


# ── 1. la feuille de style : des jetons, et eux seuls ──
COULEURS = ("white|black|red|green|blue|yellow|orange|purple|pink|gray|grey|silver|maroon|navy|teal|olive|lime|aqua|fuchsia|"
            "salmon|tomato|gold|crimson|coral|beige|ivory|khaki|lavender|tan|brown|cyan|magenta|indigo|violet|turquoise")
EN_DUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(|(?<![-\w])(?:" + COULEURS + r")(?![-\w])")


def jetons_et_reste(css):
    """→ ({bloc: {jeton: valeur}}, css sans les blocs de jetons). Un bloc de jetons : une règle dont le sélecteur commence par :root
    et dont le corps ne porte QUE des propriétés « --nom: valeur »."""
    blocs, reste = {}, css
    for m in re.finditer(r"(:root[^{]*)\{([^{}]*)\}", css):
        corps = m.group(2)
        decl = [d.strip() for d in corps.split(";") if d.strip()]
        if decl and all(d.startswith("--") for d in decl):
            blocs[m.group(1).strip()] = dict(d.split(":", 1) for d in decl)
            reste = reste.replace(m.group(0), "", 1)
    return blocs, reste


css = re.sub(r"/\*.*?\*/", "", (PAGE / "app.css").read_text(), flags=re.S)
blocs, reste = jetons_et_reste(css)
clair = blocs.get(":root", {})
sombres = {k: v for k, v in blocs.items() if "sombre" in k or "clair" in k}
dire(clair and len(sombres) == 2, f"app.css : un bloc de jetons clair (:root) et deux sombres (préférence du système, choix mémorisé) ({sorted(blocs)})")
en_dur = [(m.group(0), reste[max(0, m.start() - 40):m.start()].split("\n")[-1].strip()) for m in EN_DUR.finditer(reste)]
dire(not en_dur, f"app.css : aucune couleur en dur hors du bloc des jetons (trouvées : {en_dur[:5]})")
couleur = lambda v: bool(re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", v))
jetons_c = {k for k, v in clair.items() if couleur(v)}
manque = {nom: sorted(jetons_c - {k for k, v in b.items() if couleur(v)}) for nom, b in sombres.items()}
dire(jetons_c and not any(manque.values()) and len({json.dumps(b, sort_keys=True) for b in sombres.values()}) == 1,
     f"app.css : le thème sombre redéfinit les {len(jetons_c)} jetons de couleur, à l'identique pour le système et le choix mémorisé (manquent : {manque})")
dire(not [k for k in clair if not k.startswith("--")] and {"--e1", "--e2", "--e3", "--e4", "--t-corps", "--t-doc", "--r", "--ombre", "--duree"} <= set(clair),
     "app.css : jetons d'espacement (échelle de 4 px), de taille de texte, de rayon, d'ombre et de durée")
ech = sorted(int(v.strip()[:-2]) for k, v in clair.items() if re.fullmatch(r"--e\d+", k))
dire(ech and all(x % 4 == 0 for x in ech), f"app.css : l'échelle des espacements est en multiples de 4 px ({ech})")
gauche = [g for g in re.findall(r"border-left(?:-color|-width|-style)?\s*:[^;}]*|border-inline-start[^:]*:[^;}]*", reste)
          if not re.fullmatch(r"border-left(?:-width)?\s*:\s*0(?:px)?\s*", g.strip())]
dire(not gauche, f"app.css : aucune bordure à gauche, l'état se montre par un fond ou un badge (trouvées : {gauche})")
duree = clair.get("--duree", "").strip()
trans = re.findall(r"transition\s*:([^;}]*)", reste)
dire(duree in ("150ms", ".15s", "0.15s") and all("var(--duree)" in t or t.strip() == "none !important" for t in trans),
     f"app.css : chaque transition prend le jeton de durée ({duree}) ({trans})")
dire(re.search(r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{[^}]*transition:\s*none", reste) is not None, "app.css : aucune transition sous prefers-reduced-motion")
tailles = [int(x) for x in re.findall(r"font-size:\s*(\d+)px", reste)] + [int(v.strip()[:-2]) for k, v in clair.items() if k.startswith("--t-") and v.strip().endswith("px")]
dire(tailles and min(tailles) >= 12 and clair.get("--t-corps", "").strip() == "15px" and clair.get("--t-doc", "").strip() == "16px",
     f"app.css : aucune taille de texte sous 12 px, corps 15 px, document 16 px (plus petite : {min(tailles) if tailles else None})")

# ── 2. la page : aucune couleur en dur, mêmes appels qu'au lot 2 ──
app_js = (PAGE / "app.js").read_text()
code = re.sub(r"//[^\n]*", "", app_js)
dire(not re.findall(r"#[0-9a-fA-F]{6}\b|\brgba?\(", code) and ".style.color" not in code and ".style.background" not in code,
     "app.js : aucune couleur en dur (elles viennent toutes des jetons de app.css)")
appels = sorted(set(re.findall(r'"(/api/action[^"?]*)', code)))
dire({"/api/action", "/api/action/apercu"} <= set(appels) <= {"/api/action", "/api/action/apercu", "/api/actions"},
     f"app.js : la décision passe par les mêmes appels qu'au lot 2 (aperçu, action ; /api/actions dit seulement s'ils sont actifs), et eux seuls ({appels})")
dire("innerHTML" not in app_js and "insertAdjacentHTML" not in app_js, "app.js : aucun HTML inséré (le Markdown est rendu en éléments)")

# ── 3. un vrai navigateur, s'il est là ──
module = os.environ.get("BERGER_PLAYWRIGHT") or next((p for p in ("playwright", "playwright-core") if shutil.which("node") and subprocess.run(
    ["node", "-e", f"require.resolve('{p}')"], capture_output=True).returncode == 0), None)
if not module or not shutil.which("node"):
    print("NON JOUÉ navigateur réel (contraste, tailles, cibles, débordement, clavier, parcours en 2 clics, CLS, À lire) : Playwright absent de cette machine")
else:
    with tempfile.TemporaryDirectory() as t:
        i, env = J.construire(t, marquages=True); env = {k: v for k, v in env.items() if k != "BERGER_AGENT"}
        (i / "docs/assets").mkdir(parents=True); shutil.copy2(SRC / "docs/assets/berger.png", i / "docs/assets/berger.png")   # le logo, servi à /logo.png (comme l'installation)
        b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=120)
        # un document à la forme de fond (En bref, Pour toi, Détail), le plus récent : il s'ouvre le premier
        (i / "agents/scribe/a-lire/2026-10-14_forme.md").write_text(
            "# Forme de fond\n\n**En bref** : la page À lire se lit en deux volets.\n**Pour toi** : rien à décider, lis le résumé.\n\n"
            "Lié à : demande demo,forme\n\n## Détail\n\nIci le détail complet, replié par défaut.\n\n- un point\n- un autre point\n  - un sous-point\n\n"
            "| Colonne | Valeur |\n|---|---|\n| une | `code-en-ligne` |\n")
        # deux décisions d'essai POUR LE PROPRIÉTAIRE, et un faux courtier qui les « exécute » (même forme que tests/interface-actions.py)
        V = i / "courtier/validations"
        for n in (41, 42):
            (V / f"{n}.json").write_text(json.dumps({"n": n, "agent": "vigie", "outil": "berger-admin", "verbe": "espace", "args": ["vigie"],
                                                     "apercu": f"une écriture d'essai {n}", "valideur": None, "demande": "2026-10-13T10:00"}))
        arret = threading.Event()
        def courtier():
            while not arret.is_set():
                for f in V.glob("*.decision"):
                    try: contenu = f.read_text()
                    except OSError: continue
                    n = f.stem; d = json.loads((V / f"{n}.json").read_text()) if (V / f"{n}.json").exists() else {"n": int(n)}
                    d.update(etat="validé et exécuté" if contenu.startswith("valider") else "refusé")
                    (V / f"{n}.fait.json").write_text(json.dumps(d)); f.unlink(); (V / f"{n}.json").unlink(missing_ok=True)
                time.sleep(0.05)
        threading.Thread(target=courtier, daemon=True).start()
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        with open(i / "config.toml", "a") as f: f.write(f"[interface]\nport = {port}\nactions = true\n")
        lien = b("interface", "lien").stdout.strip()
        srv = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(100):
                try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
                except OSError: time.sleep(0.1)
            r = subprocess.run(["node", str(SRC / "tests/_page_mesures.js"), lien, "41", "42"], env={**os.environ, "BERGER_PLAYWRIGHT": module},
                               capture_output=True, text=True, timeout=900)
            try: res = json.loads(r.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError): res = {"#lancement": "ERREUR " + (r.stderr or r.stdout)[-400:]}
            if str(res.get("#lancement", "")).startswith("NON JOUÉ"): print(res["#lancement"])
            else:
                dire(len(res) >= 60 and "#exécution" not in res, f"navigateur : {len(res)} mesures jouées ({res.get('#exécution', 'sans erreur')})")
                for k, v in res.items():
                    if k != "#exécution": dire(v == "ok", f"navigateur : {k} ({v})")
        finally:
            arret.set(); srv.terminate(); srv.wait(timeout=10)

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
