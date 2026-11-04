#!/usr/bin/env python3
"""Serveur de l'interface web de Berger (spec docs/plans/2026-10-13-interface-spec.md, lot 1a) — Python standard seulement.

Il ne connaît ni fichier d'état ni règle : chaque donnée vient d'une commande `berger … --json` (la même que la ligne de
commande et les panneaux de Herdr) ; il sert trois fichiers fixes (bin/page/index.html, app.js, app.css) et les schémas.
Lecture seule (lot 1) : aucune action, aucune écriture. Lancé par `berger interface servir`. Les livrables .html (maquettes,
aperçus : spec §6.1) sont servis tels quels, à origine opaque et sans réseau (CSP_LIVRABLE).

Sécurité (§5 et §6 ter de la spec) : écoute sur l'adresse DÉCLARÉE ([interface] adresse ; défaut 127.0.0.1) ; seules les
adresses déclarées ([interface] sources : SWAG, ou 127.0.0.1 pour le tunnel) sont servies, les autres → 403 avant toute
lecture ; en-tête Host exigé (le nom déclaré derrière SWAG ; localhost ou 127.0.0.1 + port en mode tunnel : contre le DNS
rebinding) ; les en-têtes X-Forwarded-* ne sont JAMAIS lus (ni contrôle ni journal : le contrôle porte sur le pair et sur le
jeton) ; jeton lu à chaque requête dans un fichier masqué aux agents, échangé une fois (POST /connexion) contre un cookie
DÉRIVÉ du jeton (HttpOnly, SameSite=Strict, Secure derrière SWAG), comparé à temps constant ; TLS optionnel (module ssl,
certificat interne : le HTTP en clair n'obtient alors aucune réponse) ; politique de contenu stricte, pas de cache ;
journal sans paramètres ni contenu (l'adresse du pair n'y figure que pour une source refusée). Charge : 10 s au plus par commande, 4 commandes à la fois (503 sinon).
Temps réel (§6 quater) : GET /api/flux relaie en SSE le signal de `berger veille` (un seul processus) — aucune donnée,
la page relit ses vues ; 8 flux au plus."""
import argparse, hashlib, hmac, http.server, json, re, socket, ssl, subprocess, sys, threading, urllib.parse
from pathlib import Path

ICI = Path(__file__).resolve().parent
BERGER = ICI / "berger"
PAGE = ICI / "page"
SCHEMAS = (ICI / "vues", ICI / "schemas")
ADRESSE = "127.0.0.1"                                                      # défaut : l'écoute se déclare ([interface] adresse)
DELAI = 10                                                                # s par commande lancée
SIMULTANEES = 4
FLUX_MAX = 8                                                              # flux temps réel ouverts à la fois (§6 quater)
VEILLE_REPOS = 60                                                         # s sans aucun flux ouvert : la veille s'arrête (relancée au flux suivant)
BATTEMENT = 25                                                            # s : événement « battement » : SWAG et le navigateur gardent le flux, la page le sait vivant
FICHIERS = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/app.css": ("app.css", "text/css; charset=utf-8")}
NOM = re.compile(r"[a-z0-9][a-z0-9-]{0,40}")                             # type de vue, nom de schéma
ARG = re.compile(r"[A-Za-z0-9][A-Za-z0-9,._-]{0,199}")                    # agent ou filtre d'une vue : jamais un tiret initial
COMMANDES = {"/api/vues": ["vues", "--json"], "/api/etat": ["etat", "--json"], "/api/validations": ["validations", "--json"]}
ENTETES = {"Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
                                      "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
           "X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"}
COOKIE = "berger"
# Un livrable servi tel quel (spec §6.1, maquettes et aperçus) : document à ORIGINE OPAQUE (sandbox sans allow-same-origin :
# ni cookie, ni stockage, ni accès à la page qui l'encadre), ses scripts en ligne permis (un aperçu se construit par son
# JavaScript) mais AUCUN réseau (connect-src, img-src, form-action…) ; encadrable par la page seule. Un autre genre se télécharge.
CSP_LIVRABLE = ("sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
                "font-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors 'self'")
# Type de chaque genre : table FERMÉE (le genre vient de l'extension, vérifiée par sa signature par `berger livrable --brut`),
# jamais déduit du contenu ; nosniff sur toutes les réponses. Affichés (inline) : pdf et images ; tout le reste téléchargé.
GENRES = {"html": "text/html; charset=utf-8", "md": "text/markdown; charset=utf-8", "pdf": "application/pdf", "png": "image/png",
          "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp", "autre": "application/octet-stream"}
EN_LIGNE = {"pdf", "png", "jpeg", "gif", "webp"}
CSP_PDF = "default-src 'none'; object-src 'none'; frame-ancestors 'none'"     # sans sandbox : le lecteur PDF refuse un document sandboxé
CSP_FERME = "sandbox; default-src 'none'; frame-ancestors 'none'"


def deriver(jeton, usage):
    """Une valeur dérivée du jeton (cookie de session, plus tard jeton anti-rejeu) : changer le jeton les invalide toutes."""
    return hmac.new(jeton.encode(), usage.encode(), hashlib.sha256).hexdigest()


class Veille:
    """Le temps réel (§6 quater) : UN processus `berger veille` pour tous les flux (lancé au premier, relancé s'il meurt) ;
    chaque ligne qu'il écrit est un changement — le numéro `generation` avance et les flux en attente sont réveillés. Il ne
    porte aucune donnée : la page relit ses vues (berger vue … --json, la source unique). Plus aucun flux pendant
    VEILLE_REPOS : elle est arrêtée (rien ne tourne pour personne)."""

    def __init__(self):
        self.cond = threading.Condition(); self.generation = 0; self.proc = None; self.clients = 0; self.minuterie = None

    def entrer(self):
        with self.cond:
            self.clients += 1
            if self.minuterie: self.minuterie.cancel(); self.minuterie = None

    def sortir(self):
        with self.cond:
            self.clients -= 1
            if self.clients == 0 and self.vivante():
                self.minuterie = threading.Timer(VEILLE_REPOS, self.arreter_si_seule); self.minuterie.daemon = True; self.minuterie.start()

    def arreter_si_seule(self):
        with self.cond:
            if self.clients == 0 and self.vivante(): self.proc.terminate()
            self.minuterie = None

    def vivante(self): return self.proc is not None and self.proc.poll() is None

    def demarrer(self):
        with self.cond:
            if self.vivante(): return True
            try: self.proc = subprocess.Popen([sys.executable, str(BERGER), "veille"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            except OSError: self.proc = None; return False
            threading.Thread(target=self.lire, args=(self.proc,), daemon=True).start()
            return True

    def lire(self, proc):
        for ligne in proc.stdout:
            if ligne.startswith("changement"):
                with self.cond: self.generation += 1; self.cond.notify_all()
        proc.wait()
        with self.cond: self.cond.notify_all()                             # veille morte : les flux se ferment, la page repasse à 5 s


class Serveur(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, fichier_jeton, adresse=ADRESSE, nom=None, sources=(ADRESSE,), tls=None):
        self.fichier_jeton = Path(fichier_jeton); self.port = port; self.nom = nom; self.sources = set(sources)
        self.hotes = ({nom} if nom else set()) | ({f"localhost:{port}", f"{ADRESSE}:{port}"} if adresse == ADRESSE else set())
        self.place = threading.BoundedSemaphore(SIMULTANEES)
        self.flux = threading.BoundedSemaphore(FLUX_MAX); self.veille = Veille()
        if ":" in adresse: self.address_family = socket.AF_INET6
        super().__init__((adresse, port), Requete)
        if tls:                                                            # (certificat, clé) : le port ne parle plus que TLS
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(*tls)
            self.socket = ctx.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)   # poignée de main dans le fil de la requête

    def handle_error(self, request, client_address):                       # HTTP en clair sur le port TLS, client parti : une ligne, pas une trace
        sys.stderr.write(f"connexion abandonnée ({type(sys.exc_info()[1]).__name__})\n")

    def jeton(self):
        try: j = self.fichier_jeton.read_text().strip()
        except OSError: return None
        return j if len(j) >= 32 else None


class Requete(http.server.BaseHTTPRequestHandler):
    server_version = "berger"; sys_version = ""

    def setup(self):
        if isinstance(self.request, ssl.SSLSocket): self.request.settimeout(10); self.request.do_handshake()
        super().setup()

    def log_request(self, code="-", size="-"):                          # méthode, chemin SANS paramètres, code : rien d'autre
        sys.stderr.write(f"{self.command} {urllib.parse.urlsplit(self.path).path} {code}\n")

    def log_message(self, *a): pass

    def envoyer(self, code, corps=b"", type_="application/json; charset=utf-8", plus=(), base=ENTETES):
        self.send_response(code)
        for k, v in base.items(): self.send_header(k, v)
        for k, v in plus: self.send_header(k, v)
        self.send_header("Content-Type", type_); self.send_header("Content-Length", str(len(corps))); self.end_headers()
        if self.command != "HEAD": self.wfile.write(corps)

    def erreur(self, code, texte):
        self.envoyer(code, json.dumps({"erreur": texte}, ensure_ascii=False).encode())

    def hote_ok(self):
        """Le pair (l'adresse qui se connecte, jamais un en-tête X-Forwarded-*) est une source déclarée, puis Host est admis."""
        if self.client_address[0] not in self.server.sources:
            # l'adresse du PAIR, seulement pour un refus : c'est ainsi qu'on MESURE la source de SWAG (spec §6 ter) ; méthode et
            # chemin sans paramètres, jamais un cookie ni un en-tête
            sys.stderr.write(f"source refusée : {self.client_address[0]} {self.command} {urllib.parse.urlsplit(self.path).path}\n")
            self.erreur(403, "source refusée"); return False
        if self.headers.get("Host", "") in self.server.hotes: return True
        self.erreur(403, "hôte refusé"); return False

    def connecte(self):
        j = self.server.jeton()
        if not j: return False
        for morceau in self.headers.get("Cookie", "").split(";"):
            k, _, v = morceau.strip().partition("=")
            if k == COOKIE and hmac.compare_digest(v, deriver(j, "session")): return True
        return False

    def do_GET(self):
        if not self.hote_ok(): return
        chemin = urllib.parse.urlsplit(self.path).path
        if chemin in FICHIERS:
            nom, type_ = FICHIERS[chemin]
            try: return self.envoyer(200, (PAGE / nom).read_bytes(), type_)
            except OSError: return self.erreur(404, "absent")
        if not chemin.startswith("/api/"): return self.erreur(404, "inconnu")
        if not self.connecte(): return self.erreur(401, "connexion requise : ouvre le lien donné par « berger interface lien »")
        if chemin in COMMANDES: return self.commande(COMMANDES[chemin])
        if chemin == "/api/flux": return self.flux()
        m = re.fullmatch(r"/api/vue/([^/]+)", chemin)
        if m and NOM.fullmatch(m.group(1)):
            a = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("a", [None])[0]
            if a is not None and not ARG.fullmatch(a): return self.erreur(400, "argument refusé")
            return self.commande(["vue", m.group(1)] + ([a] if a else []) + ["--json"])
        m = re.fullmatch(r"/api/livrable/([0-9a-f]{16})/(" + "|".join(GENRES) + ")", chemin)
        if m: return self.livrable(*m.groups())
        m = re.fullmatch(r"/api/schema/([^/]+)", chemin)
        if m and NOM.fullmatch(m.group(1)):
            for d in SCHEMAS:
                f = d / f"{m.group(1)}.schema.json"
                if f.is_file(): return self.envoyer(200, f.read_bytes())
        self.erreur(404, "inconnu")

    def do_HEAD(self): self.do_GET()

    def do_POST(self):
        if not self.hote_ok(): return
        if urllib.parse.urlsplit(self.path).path != "/connexion": return self.erreur(405, "lecture seule")
        try: n = int(self.headers.get("Content-Length", "0"))
        except ValueError: n = 0
        if not 0 < n <= 1024: return self.erreur(400, "demande refusée")
        try: donne = str(json.loads(self.rfile.read(n)).get("jeton", ""))
        except (ValueError, AttributeError): return self.erreur(400, "demande refusée")
        j = self.server.jeton()
        if not j or not hmac.compare_digest(donne.encode(), j.encode()): return self.erreur(401, "jeton refusé")
        self.envoyer(204, plus=[("Set-Cookie", f"{COOKIE}={deriver(j, 'session')}; HttpOnly; SameSite=Strict; Path=/" + ("; Secure" if self.server.nom else ""))])

    def refuser(self): self.erreur(405, "lecture seule")
    do_PUT = do_DELETE = do_PATCH = refuser

    def flux(self):
        """GET /api/flux (text/event-stream) : un événement « change » à chaque changement relevé par la veille, un battement
        toutes les 25 s ; 8 flux au plus (le 9e : 503, la page reste sur le rafraîchissement de 5 s) ; la veille morte ferme
        le flux (la page repasse à 5 s, et EventSource se reconnecte seul)."""
        if not self.server.flux.acquire(blocking=False):
            return self.erreur(503, f"trop de flux ouverts ({FLUX_MAX} au plus) : la page reste sur le rafraîchissement de 5 s")
        v = self.server.veille; v.entrer()
        try:
            if not v.demarrer(): return self.erreur(503, "temps réel indisponible : la page reste sur le rafraîchissement de 5 s")
            self.send_response(200)
            for k, x in ENTETES.items(): self.send_header(k, x)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8"); self.send_header("X-Accel-Buffering", "no"); self.end_headers()
            self.close_connection = True
            self.wfile.write(b"retry: 3000\n\n"); self.wfile.flush()
            gen = v.generation
            while True:
                with v.cond: v.cond.wait_for(lambda: v.generation != gen or not v.vivante(), timeout=BATTEMENT)
                if v.generation != gen:
                    gen = v.generation; self.wfile.write(f"event: change\ndata: {gen}\n\n".encode())
                elif not v.vivante(): break
                else: self.wfile.write(b"event: battement\ndata: \n\n")   # un événement (pas un commentaire) : la page voit que le flux vit
                self.wfile.flush()
        except OSError: pass                                                # client parti
        finally: v.sortir(); self.server.flux.release()

    def lancer(self, args):
        """Lance `berger <args>` (le code installé fait foi), 10 s au plus, 4 à la fois → sa sortie (octets), ou None après
        avoir répondu l'erreur."""
        place = self.server.place                                          # le MÊME sémaphore pour prendre et rendre la place
        if not place.acquire(blocking=False): return self.erreur(503, "occupé : réessaie au prochain tour")
        try:
            r = subprocess.run([sys.executable, str(BERGER), *args], capture_output=True, timeout=DELAI)
        except subprocess.TimeoutExpired:
            return self.erreur(504, f"vue en échec : délai de {DELAI} s dépassé")
        finally:
            place.release()
        if r.returncode:
            return self.erreur(502, "vue en échec : " + ((r.stderr or r.stdout).decode("utf-8", "replace").strip().splitlines() or ["?"])[-1][:300])
        return r.stdout

    def commande(self, args):
        """`berger <args>` ; rend son JSON tel quel."""
        sortie = self.lancer(args)
        if sortie is None: return
        try: json.loads(sortie)
        except ValueError: return self.erreur(502, "vue en échec : réponse illisible")
        self.envoyer(200, sortie)

    def livrable(self, ident, genre):
        """Un document tel quel (Livrables, Documents) : `berger livrable <id> --brut <genre>` vérifie que le document a CE genre
        (jamais cru de la page) ; un .html est servi isolé (CSP_LIVRABLE, encadré par la page) ; pdf et images affichés
        (inline, jamais encadrés) ; le reste téléchargé ; une CSP stricte sur chaque réponse."""
        sortie = self.lancer(["livrable", ident, "--brut", genre])
        if sortie is None: return
        if genre == "html":
            base = {k: v for k, v in ENTETES.items() if k != "X-Frame-Options"}   # frame-ancestors 'self' : la page seule l'encadre
            return self.envoyer(200, sortie, GENRES[genre], base={**base, "Content-Security-Policy": CSP_LIVRABLE})
        csp = CSP_PDF if genre == "pdf" else CSP_FERME
        disposition = "inline" if genre in EN_LIGNE else "attachment"
        ext = {"autre": "bin", "jpeg": "jpg"}.get(genre, genre)
        self.envoyer(200, sortie, GENRES[genre], base={**ENTETES, "Content-Security-Policy": csp},
                     plus=[("Content-Disposition", f'{disposition}; filename="document-{ident}.{ext}"')])


def servir(port, fichier_jeton, adresse=ADRESSE, nom=None, sources=(ADRESSE,), tls=None):
    s = Serveur(port, fichier_jeton, adresse, nom, sources, tls)
    lien = f"https://{nom}/" if nom else f"{'https' if tls else 'http'}://localhost:{port}/"
    print(f"interface de Berger : {lien} (écoute sur {adresse}:{port}{', TLS' if tls else ''} ; sources admises : {', '.join(sorted(s.sources))})", flush=True)
    s.serve_forever()


if __name__ == "__main__":
    p = argparse.ArgumentParser(prog="interface.py", description="lancé par « berger interface servir » (réglages : [interface] de config.toml)")
    p.add_argument("commande", choices=["servir"]); p.add_argument("port", type=int); p.add_argument("jeton")
    p.add_argument("--adresse", default=ADRESSE); p.add_argument("--nom"); p.add_argument("--sources", default=ADRESSE)
    p.add_argument("--tls", nargs=2, metavar=("CERTIFICAT", "CLE"))
    x = p.parse_args()
    servir(x.port, x.jeton, x.adresse, x.nom, [s for s in x.sources.split(",") if s], tuple(x.tls) if x.tls else None)
