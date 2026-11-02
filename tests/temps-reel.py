#!/usr/bin/env python3
"""L'interface en temps réel (spec docs/plans/2026-10-13-interface-spec.md §6 quater) — sans modèle, faux Herdr, installation
JETABLE (tests/_jeu_vues.py : un agent Claude, vigie, et un agent Codex, scribe), vraies requêtes HTTP sur un port libre.
Vérifie, côté serveur (le côté page est dans tests/interface.py, faux DOM) :
 1. une écriture posée en attente apparaît en moins de 2 s : événement « change » sur le flux, puis /api/validations la donne ;
    une checklist modifiée d'un agent Claude ET d'un agent Codex aussi ; aucun événement sans changement ;
 2. flux coupé (la veille meurt) : le flux se ferme ; un nouveau flux s'ouvre et reçoit de nouveau les changements (veille
    relancée seule) ;
 3. un client en trop (9e flux) : 503 avec un message clair, les flux ouverts continuent de recevoir ;
 et : sans cookie → 401 ; Host étranger → 403 ; événement « battement » quand rien ne change (délai raccourci, dans le processus).
Usage : python3 tests/temps-reel.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import http.client, json, os, signal, socket, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def port_libre():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class Flux:
    """Un client du flux : GET /api/flux, puis lecture ligne à ligne avec un délai."""
    def __init__(self, port, cookie, host=None):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.s.sendall(f"GET /api/flux HTTP/1.1\r\nHost: {host or f'localhost:{port}'}\r\nCookie: {cookie}\r\nAccept: text/event-stream\r\n\r\n".encode())
        d = b""
        while b"\r\n\r\n" not in d:
            bout = self.s.recv(4096)
            if not bout: break
            d += bout
        tete, _, self.tampon = d.partition(b"\r\n\r\n"); lignes = tete.decode().split("\r\n")
        self.statut = int(lignes[0].split()[1]); self.entetes = {}
        for l in lignes[1:]:
            k, _, v = l.partition(":"); self.entetes[k.lower()] = v.strip()
        if self.statut != 200:                                             # réponse d'erreur : le corps entier (Content-Length)
            n = int(self.entetes.get("content-length", "0"))
            while len(self.tampon) < n:
                bout = self.s.recv(4096)
                if not bout: break
                self.tampon += bout
        self.corps = b"" if self.statut == 200 else self.tampon

    def attendre(self, quoi, delai):
        """Lit jusqu'à une ligne qui commence par `quoi` → secondes écoulées, None au délai, "fin" si le flux se ferme.
        Lecture par recv et tampon propre (un fichier de socket devient inutilisable après un délai dépassé)."""
        t0 = time.time()
        while True:
            while b"\n" in self.tampon:
                l, _, self.tampon = self.tampon.partition(b"\n")
                if l.decode().startswith(quoi): return time.time() - t0
            reste = delai - (time.time() - t0)
            if reste <= 0: return None
            self.s.settimeout(reste)
            try: bout = self.s.recv(4096)
            except (socket.timeout, TimeoutError): return None
            except OSError: return "fin"
            if not bout: return "fin"
            self.tampon += bout

    def fermer(self):
        try: self.s.close()
        except OSError: pass


def pids_veille(i):
    out = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit(): continue
        try: c = (p / "cmdline").read_bytes().split(b"\0")
        except OSError: continue
        if str(i / "bin/berger").encode() in c and b"veille" in c: out.append(int(p.name))
    return out


with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t); m = i.parent; port = port_libre()
    env = {k: v for k, v in env.items() if k != "BERGER_AGENT"}         # l'installation jetable agit comme le propriétaire
    with open(i / "config.toml", "a") as f: f.write(f"[interface]\nport = {port}\n")
    jeton = subprocess.run([sys.executable, str(i / "bin/berger"), "interface", "lien"], env=env, capture_output=True, text=True).stdout.strip().partition("#jeton=")[2]
    srv = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for _ in range(50):
        try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
        except OSError: time.sleep(0.1)
    ouverts = []
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("POST", "/connexion", body=json.dumps({"jeton": jeton}), headers={"Host": f"localhost:{port}", "Content-Type": "application/json"})
        cookie = (c.getresponse().getheader("Set-Cookie") or "").split(";")[0]

        dire(Flux(port, "berger=" + "0" * 64).statut == 401, "flux sans cookie valide : 401")
        dire(Flux(port, cookie, host="evil.example").statut == 403, "flux avec un Host étranger : 403")
        a = Flux(port, cookie); ouverts.append(a)
        dire(a.statut == 200 and a.entetes.get("content-type", "").startswith("text/event-stream") and a.entetes.get("cache-control") == "no-store"
             and "default-src 'self'" in a.entetes.get("content-security-policy", ""), "flux : 200, text/event-stream, no-store, même CSP que la page")
        dire(a.attendre("retry:", 3) is not None, "flux : « retry » en tête (le navigateur se reconnecte seul après 3 s)")
        time.sleep(1.0)                                                     # la veille prend son empreinte de départ
        dire(a.attendre("event: change", 1.5) is None, "aucun événement sans changement")

        # 1. une écriture posée en attente → la page la voit en moins de 2 s
        v = i / "courtier/validations"; n = 1 + max(int(p.stem) for p in v.glob("*.json") if p.stem.isdigit())
        modele = json.loads((v / "1.json").read_text())
        (v / f"{n}.json").write_text(json.dumps({**modele, "n": n, "apercu": "écriture posée pendant le test"}))
        dt = a.attendre("event: change", 2)
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("GET", "/api/validations", headers={"Host": f"localhost:{port}", "Cookie": cookie})
        vues = json.loads(c.getresponse().read())
        dire(isinstance(dt, float) and dt < 2 and any(x.get("n") == n for x in vues["donnees"]["validations"]),
             f"une écriture posée en attente : événement en {dt if not isinstance(dt, float) else round(dt, 2)} s (< 2 s), puis lue par /api/validations")
        for agent, moteur in (("vigie", "Claude"), ("scribe", "Codex")):
            time.sleep(0.5)
            with open(i / "agents" / agent / "CHECKLIST.md", "a") as f: f.write("- [ ] étape ajoutée pendant le test\n")
            dt = a.attendre("event: change", 2)
            dire(isinstance(dt, float) and dt < 2, f"checklist d'un agent {moteur} ({agent}) modifiée : événement en moins de 2 s ({dt})")

        # 3. un client en trop : 503 propre, les flux ouverts continuent
        for _ in range(7): ouverts.append(Flux(port, cookie))
        neuvieme = Flux(port, cookie)
        dire(all(x.statut == 200 for x in ouverts) and len(ouverts) == 8, "8 flux ouverts à la fois")
        msg = json.loads(neuvieme.corps or b"{}").get("erreur", "") if neuvieme.statut == 503 else ""
        dire(neuvieme.statut == 503 and "8 au plus" in msg and "5 s" in msg, f"9e flux : 503, message clair ({msg})")
        time.sleep(0.5)
        with open(i / "agents/scribe/CHECKLIST.md", "a") as f: f.write("- [ ] encore une étape\n")
        recus = [x.attendre("event: change", 2) for x in ouverts]
        dire(all(isinstance(r, float) for r in recus), "après le refus du 9e, les 8 flux ouverts reçoivent toujours les changements")
        for x in ouverts[1:]: x.fermer()
        ouverts = ouverts[:1]; time.sleep(0.3)

        # 2. flux coupé : la veille meurt → le flux se ferme ; un nouveau flux reprend (veille relancée)
        pv = pids_veille(i)
        for p in pv: os.kill(p, signal.SIGTERM)
        dire(len(pv) == 1 and a.attendre("event: change", 3) == "fin", f"une seule veille pour tous les flux ({len(pv)}) ; morte, le flux se ferme (la page repasse à 5 s)")
        b2 = Flux(port, cookie); ouverts.append(b2); time.sleep(1.0)
        with open(i / "agents/vigie/CHECKLIST.md", "a") as f: f.write("- [ ] après la reprise\n")
        dt = b2.attendre("event: change", 2)
        dire(b2.statut == 200 and isinstance(dt, float) and len(pids_veille(i)) == 1, f"reprise : un nouveau flux reçoit de nouveau les changements, veille relancée seule ({dt})")
    finally:
        for x in ouverts: x.fermer()
        srv.terminate(); srv.wait(timeout=10)
        for p in pids_veille(i):
            try: os.kill(p, signal.SIGTERM)
            except OSError: pass

    # appels.log, qui change à chaque appel du courtier : relevé toutes les VEILLE_APPELS secondes seulement (raccourci à 2 s) —
    # 6 s d'appels en continu (tous les 0,2 s) donnent au plus 4 signaux, au lieu d'un toutes les 0,5 s
    prog = (f"import runpy, threading, time, json, io, contextlib\ng = runpy.run_path({str(i / 'bin/berger')!r}, run_name='essai')\n"
            "g['commandes'].FAMILLES['veille'].veille.__globals__['VEILLE_APPELS'] = 2\n"
            f"f = {str(i / 'courtier/appels.log')!r}\n"
            "def ecrire():\n    t0 = time.time()\n    while time.time() - t0 < 6:\n        open(f, 'a').write('appel\\n'); time.sleep(0.2)\n"
            "sortie = io.StringIO()\nthreading.Thread(target=ecrire, daemon=True).start()\n"
            "with contextlib.redirect_stdout(sortie): g['commandes'].FAMILLES['veille'].veille(fois=14)\n"
            "print(json.dumps({'signaux': sortie.getvalue().count('changement')}))")
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True, timeout=60)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {}; print(r.stderr[-600:])
    dire(isinstance(x.get("signaux"), int) and 1 <= x["signaux"] <= 4,
         f"appels.log écrit en continu (toutes les 0,2 s pendant 6 s) : {x.get('signaux')} signal(s), au plus un par relevé (VEILLE_APPELS), jamais un flot")

    # battement (délai raccourci, serveur dans le processus) : « : battement » quand rien ne change
    jf = m / ".config/berger/interface.jeton"
    prog = (f"import runpy, threading, socket, time, json\ng = runpy.run_path({str(i / 'bin/interface.py')!r}, run_name='essai')\n"
            "g['Requete'].flux.__globals__['BATTEMENT'] = 0.4\n"
            f"s = g['Serveur'](0, {str(jf)!r}); p = s.server_address[1]; s.hotes = {{'localhost:%d' % p}}\n"
            "threading.Thread(target=s.serve_forever, daemon=True).start()\n"
            f"ck = 'berger=' + g['deriver'](open({str(jf)!r}).read().strip(), 'session')\n"
            "so = socket.create_connection(('127.0.0.1', p), timeout=5)\n"
            "so.sendall(('GET /api/flux HTTP/1.1\\r\\nHost: localhost:%d\\r\\nCookie: %s\\r\\n\\r\\n' % (p, ck)).encode())\n"
            "t0 = time.time(); d = b''\n"
            "while time.time() - t0 < 2 and b'event: battement' not in d: d += so.recv(4096)\n"
            # plus aucun flux pendant VEILLE_REPOS (raccourci à 1 s) : la veille s'arrête ; un nouveau flux la relance
            "g['Requete'].flux.__globals__['VEILLE_REPOS'] = 1.0\n"
            "vivante_avant = s.veille.vivante(); so.close(); time.sleep(0.3); encore = s.veille.vivante()\n"
            "t1 = time.time()\n"
            "while time.time() - t1 < 5 and s.veille.vivante(): time.sleep(0.1)\n"
            "arretee = not s.veille.vivante(); delai = round(time.time() - t1, 1)\n"
            "so = socket.create_connection(('127.0.0.1', p), timeout=5)\n"
            "so.sendall(('GET /api/flux HTTP/1.1\\r\\nHost: localhost:%d\\r\\nCookie: %s\\r\\n\\r\\n' % (p, ck)).encode()); so.recv(4096); time.sleep(0.3)\n"
            "relancee = s.veille.vivante(); so.close(); s.veille.proc and s.veille.proc.terminate()\n"
            "print(json.dumps({'battement': b'event: battement' in d, 'vivante_avant': vivante_avant, 'encore': encore, 'arretee': arretee, 'delai': delai, 'relancee': relancee}))")
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True, timeout=60)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {}; print(r.stderr[-600:])
    dire(x.get("vivante_avant") and x.get("encore") and x.get("arretee") and x.get("relancee"),
         f"plus aucun flux : la veille s'arrête après le délai de repos (raccourci à 1 s : arrêtée en {x.get('delai')} s), pas avant ; un nouveau flux la relance")
    dire(x.get("battement") is True, "événement « battement » quand rien ne change (SWAG et le navigateur gardent le flux ; la page le sait vivant)")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
