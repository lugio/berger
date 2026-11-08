#!/usr/bin/env python3
"""Interface web : le logo officiel et les retours de QA du propriétaire du 05/11 (affichage et lecture seulement). Sans modèle, faux Herdr,
installation JETABLE (tests/_jeu_vues.py), vraies requêtes HTTP sur 127.0.0.1. Vérifie :
 1. le logo docs/assets/berger.png est servi tel quel à /logo.png (200, image/png, même CSP stricte que la page, octet pour octet :
    l'empreinte est CELLE de tests/vitrine-readme.py, lue dans ce fichier) ; il est dans la marque de la barre latérale (à la place
    du « B »), dans l'en-tête (téléphone) et en favicon ; rien d'autre n'est servi à côté (un chemin voisin reste 404) ;
 2. Coulisses › Derniers appels : un appel dont les arguments tiennent sur plusieurs lignes (le courtier les écrit tels quels) reste UN
    appel — ses morceaux ne deviennent pas des lignes « — — — — — non — » ; les refus et le compte du jour le comptent une fois ;
 3. la barre latérale nomme un développeur par son sujet, le nom entier au survol et pour les lecteurs d'écran (code de la page) ;
 4. l'aperçu statique embarque le logo (aucune ressource extérieure).
Les largeurs à 1920 px (Accueil et À lire centrés, vide à droite borné) sont mesurées au navigateur par tests/_page_mesures.js
(tests/interface-finition.py). Usage : python3 tests/interface-logo.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import hashlib, http.client, json, re, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


EMPREINTE = re.search(r"hashlib\.sha256\(logo\)\.hexdigest\(\) ==\s*'([0-9a-f]{64})'", (SRC / "tests/vitrine-readme.py").read_text())
dire(EMPREINTE is not None, "l'empreinte du logo choisi par le propriétaire est lue dans tests/vitrine-readme.py (une seule source)")
EMPREINTE = EMPREINTE.group(1) if EMPREINTE else "?"
LOGO = (SRC / "docs/assets/berger.png").read_bytes()
dire(hashlib.sha256(LOGO).hexdigest() == EMPREINTE, "docs/assets/berger.png est ce logo, tel quel")

with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t, marquages=True)
    env = {k: v for k, v in env.items() if k != "BERGER_AGENT"}
    (i / "docs/assets").mkdir(parents=True); shutil.copy2(SRC / "docs/assets/berger.png", i / "docs/assets/berger.png")   # comme l'installation (le dépôt)
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=120)

    # ── 2. un appel à plusieurs lignes reste UN appel ──
    jour = time.strftime("%Y-%m-%d")
    with open(i / "courtier/appels.log", "a") as f:
        f.write(f"{jour} 09:00:00\tvigie\tberger-dev\tdemander-fusion\tCode à faire relire\n\nsuite du résumé\tREFUSÉ\terreur : porte rouge\n"
                f"{jour} 09:01:00\tscribe\tecrire\tvigie\tpremière ligne\n5. seconde ligne\taccepté\tremis à vigie\n")
    r = b("vue", "courtier", "--json")
    try: d = json.loads(r.stdout)["donnees"]
    except (ValueError, KeyError): d = {"appels": [], "aujourdhui": {}}
    appels = d["appels"]
    casses = [x for x in appels if not re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d", x["quand"]) or not x["agent"] or not x["outil"]]
    dire(r.returncode == 0 and not casses, f"Derniers appels : aucune ligne cassée (morceaux d'arguments lus comme des appels : {casses[:2]})")
    multi = [x for x in appels if x["quand"].startswith(jour + " 09:0")]
    dire(len(multi) == 2 and multi[0]["verbe"] == "demander-fusion" and multi[0]["ok"] is False and multi[0]["detail"] == "erreur : porte rouge"
         and multi[1]["ok"] is True and multi[1]["detail"] == "remis à vigie" and "\n" not in multi[0]["args"] and "suite du résumé" in multi[0]["args"],
         f"un appel aux arguments sur plusieurs lignes : UN appel, colonnes à leur place, arguments sur une ligne ({multi})")
    dire(d["aujourdhui"].get("appels") == 2 and d["aujourdhui"].get("refus") == 1, f"le compte du jour les compte une fois chacun ({d['aujourdhui']})")
    texte = b("vue", "courtier").stdout
    dire("— — — —" not in texte and "suite du résumé\tREFUSÉ" not in texte, "le rendu texte (Herdr) non plus ne montre de ligne cassée")

    # ── 1. le logo servi, dans la marque et en favicon ──
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    with open(i / "config.toml", "a") as f: f.write(f"[interface]\nport = {port}\n")
    srv = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
            except OSError: time.sleep(0.1)
        def req(chemin):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=30); c.putrequest("GET", chemin, skip_host=True)
            c.putheader("Host", f"localhost:{port}"); c.endheaders(); r = c.getresponse(); return r.status, dict(r.getheaders()), r.read()
        st, h, corps = req("/logo.png")
        dire(st == 200 and h.get("Content-Type") == "image/png" and hashlib.sha256(corps).hexdigest() == EMPREINTE,
             f"/logo.png : 200, image/png, l'empreinte du logo choisi ({st}, {h.get('Content-Type')}, {hashlib.sha256(corps).hexdigest()[:12]})")
        dire("default-src 'self'" in h.get("Content-Security-Policy", "") and h.get("X-Content-Type-Options") == "nosniff" and h.get("Cache-Control") == "no-store",
             "/logo.png : la même politique de contenu stricte que la page")
        dire(req("/berger.png")[0] == 404 and req("/logo.png/..")[0] == 404 and req("/docs/assets/berger.png")[0] == 404,
             "rien d'autre n'est servi à côté (un chemin voisin reste 404)")
        st, _, page = req("/"); page = page.decode()
        marque = re.search(r'<div class="marque">(.*?)</div>', page)
        dire(st == 200 and marque and '<img class="logo" src="/logo.png"' in marque.group(1) and ">B<" not in marque.group(1),
             "la marque de la barre latérale affiche le logo, plus le « B »")
        dire('<link rel="icon" type="image/png" href="/logo.png">' in page, "favicon de la page : ce même logo")
        dire(re.search(r'<img class="logo logo-entete" src="/logo.png" alt="Berger"', page) is not None, "l'en-tête porte aussi le logo (téléphone : la barre latérale y est cachée)")
    finally:
        srv.terminate(); srv.wait(timeout=10)

# ── 3. noms de la barre latérale ──
app = (SRC / "bin/page/app.js").read_text(); css = (SRC / "bin/page/app.css").read_text()
dire(re.search(r'const nomCourt = a => a\.role === "developpeur"', app) and 'title: a.nom, "aria-label": a.nom' in app,
     "barre latérale : un développeur nommé par son sujet, le nom entier au survol (title) et pour les lecteurs d'écran")
dire(re.search(r"@media \(max-width: 820px\) \{.*?\.logo-entete \{ display: block; \}", css, re.S) is not None and ".logo-entete { display: none;" in css,
     "le logo de l'en-tête ne paraît qu'au téléphone (la marque latérale y est cachée)")

# ── 4. l'aperçu statique embarque le logo ──
apercu = (SRC / "docs/apercu/interface.html").read_text()
dire('src="/logo.png"' not in apercu and 'href="/logo.png"' not in apercu and apercu.count('src="data:image/png;base64,') >= 2,
     "aperçu statique : le logo embarqué (marque et en-tête), rien chargé d'ailleurs")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
