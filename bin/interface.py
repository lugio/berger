#!/usr/bin/env python3
"""Serveur de l'interface web de Berger (spec docs/plans/2026-10-13-interface-spec.md, lot 1a) — Python standard seulement.

Il ne connaît ni fichier d'état ni règle : chaque donnée vient d'une commande `berger … --json` (la même que la ligne de
commande et les panneaux de Herdr) ; il sert cinq fichiers fixes (bin/page/index.html, app.js, app.css, icones.json : la source commune des icônes avec Herdr ; le logo
docs/assets/berger.png, tel quel) et les schémas.
Lecture seule sans `[interface] actions = true` (absent par défaut) ; avec, les QUATRE gestes du propriétaire (interface web v2,
lot 2, go n° 140 : valider, refuser, répondre, marquer lu) par `berger action` — le chemin de la ligne de commande —, gardés : source
locale ou VPN, session, en-tête Origin, jeton anti-rejeu dérivé de la session, jeton d'aperçu à usage unique lié à l'empreinte de la
demande, 30 tentatives par heure, chaque tentative (refus compris) au journal des actions. Lancé par `berger interface servir`. Les livrables .html (maquettes,
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
la page relit ses vues ; 8 flux au plus.
Réglages (spec 2026-11-05-interface-reglages, go n° 169) : GET /api/vue/reglages est servi EN DIRECT par le lecteur du noyau (noyau/reglages.py),
config.toml relu à chaque ouverture, valeurs sensibles masquées AVANT la sérialisation, coffre jamais lu ; toute autre méthode : 405.
Extensions (spec 2026-11-07-extensions, § 6, go n° 181, lot 2) : GET /api/vue/extensions est la vue `extensions` (données filtrées par le noyau),
repassée au même dernier filtre que les réglages (forme de clé, bloc PEM) et sans le dossier personnel, sinon 500 sans détail ; toute autre méthode : 405."""
import argparse, collections, datetime, hashlib, hmac, http.server, ipaddress, json, os, re, secrets, socket, ssl, subprocess, sys, threading, time, urllib.parse
from pathlib import Path

ICI = Path(__file__).resolve().parent
if str(ICI) not in sys.path: sys.path.insert(0, str(ICI))                  # noyau/reglages.py : autonome (bibliothèque standard seulement)
import noyau.reglages as REGLAGES
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
            "/app.css": ("app.css", "text/css; charset=utf-8"),
            "/icones.json": ("icones.json", "application/json; charset=utf-8"),   # la source commune des icônes et des libellés (avec Herdr)
            "/logo.png": (ICI.parent / "docs/assets/berger.png", "image/png")}   # le logo officiel (spec archive/2026-10-24-logo-spec.md), tel quel : marque et favicon
NOM = re.compile(r"[a-z0-9][a-z0-9-]{0,40}")                             # type de vue, nom de schéma
ARG = re.compile(r"[A-Za-z0-9][A-Za-z0-9,._-]{0,199}")                    # agent ou filtre d'une vue : jamais un tiret initial
COMMANDES = {"/api/vues": ["vues", "--json"], "/api/etat": ["etat", "--json"], "/api/validations": ["validations", "--json"],
             "/api/conversations": ["conversation", "liste", "--json"]}      # lot 3 : les pages « Conversation » ouvertes, l'état du micro
ENTETES = {"Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
                                      "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
           "X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"}
COOKIE = "berger"
# Actions du propriétaire (lot 2, garde-fous 2 à 6 de la spec 2026-11-03-interface-web-v2)
ACTIONS_WEB = ("valider", "refuser", "repondre", "lu")
CIBLE = re.compile(r"[a-z0-9][a-z0-9-]{0,40}")                           # n° d'écriture, agent ou document : jamais un tiret initial
DEBIT = 30                                                                # tentatives par heure glissante (une session valide qui POSTe)
NONCE_VIE = 600                                                           # s : un aperçu vaut 10 min, une seule fois
NONCES_MAX = 64
DELAI_ACTION = 75                                                         # s : `berger valider` attend le courtier jusqu'à 30 s
CORPS_MAX = 8192
# Lot 3 (page « Conversation », spec 2026-11-05-interface-web-v2-lot3, go n° 166) : un message à un agent, ses pièces jointes, une dictée.
# Garde-fous du lot 2 (actions actives, session, Origin, jeton anti-rejeu, jeton à usage unique, journal « admis » avant, ligne de résultat),
# plus : 127.0.0.1 SEULEMENT (ni VPN, ni SWAG) ; empreinte de ce qui est montré ; débit à part (60 messages, 20 pièces, 100 Mio par heure,
# relu au journal) ; requête de 40 Mio au plus, lue en flux et coupée avant d'aller au-delà.
MIO = 1024 * 1024
MESSAGES_HEURE, PIECES_HEURE, OCTETS_HEURE = 60, 20, 100 * MIO
MESSAGE_MAX = 40 * MIO
DELAI_MESSAGE = 75                                                        # s : remise Herdr et rangement des pièces
DELAI_TRANSCRIPTION = 150                                                 # s : le binaire local en a 120
VPN = ipaddress.ip_network("100.64.0.0/10")                               # espace partagé des VPN (WireGuard, Tailscale…)
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
ROUTE_REGLAGES = "/api/vue/reglages"                                      # lecture seule : GET, rien d'autre (405)
ROUTE_EXTENSIONS = "/api/vue/extensions"                                  # lecture seule : GET, rien d'autre (405)
LECTURE_SEULE = (ROUTE_REGLAGES, ROUTE_EXTENSIONS)


def source_locale(ip):
    """Garde-fou 2 : une action ne vient que du poste (boucle locale) ou du réseau privé / VPN, jamais d'ailleurs, même authentifiée."""
    try: a = ipaddress.ip_address(str(ip).split("%")[0])
    except ValueError: return False
    if a.version == 6 and a.ipv4_mapped: a = a.ipv4_mapped
    return a.is_loopback or (a.is_private and not a.is_unspecified) or (a.version == 4 and a in VPN)


def empreinte_message(agent, texte, pieces):
    """L'empreinte de ce qui est MONTRÉ (agent, texte, chaque pièce : type, taille, sha256), comme la page et `berger conversation envoyer`
    (bin/commandes/conversation.py, empreinte) la calculent."""
    return hashlib.sha256("\0".join([agent, texte] + [f"{p['ext']}:{p['taille']}:{p['sha256']}" for p in pieces]).encode("utf-8")).hexdigest()


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

    def __init__(self, port, fichier_jeton, adresse=ADRESSE, nom=None, sources=(ADRESSE,), tls=None, actions=False):
        self.fichier_jeton = Path(fichier_jeton); self.port = port; self.nom = nom; self.sources = set(sources)
        self.hotes = ({nom} if nom else set()) | ({f"localhost:{port}", f"{ADRESSE}:{port}"} if adresse == ADRESSE else set())
        self.origines = ({f"https://{nom}"} if nom else set()) | {f"{'https' if tls else 'http'}://{h}" for h in self.hotes if h != nom}
        self.actions = actions is True; self.nonces = {}; self.verrou = threading.Lock(); self.tls = bool(tls)
        self.journal_actions = self.fichier_jeton.with_name("interface-actions.jsonl")   # à côté du jeton : dossier masqué aux agents
        self.tentatives = collections.deque(self.relire_tentatives())
        self.envois = collections.deque(self.relire_envois())             # lot 3 : (heure, pièces, octets) des messages admis de la dernière heure
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

    def relire_tentatives(self):
        """Les tentatives comptées de la DERNIÈRE HEURE, relues au journal (toute l'heure, quel que soit le nombre de lignes de refus
        entre-temps) : un redémarrage ne remet pas le débit à zéro. Le journal est écrit dans l'ordre : on le lit depuis la fin."""
        limite = time.time() - 3600; out = []
        try: lignes = self.journal_actions.read_text().splitlines()
        except OSError: return out
        for l in reversed(lignes):
            try: x = json.loads(l); t = datetime.datetime.fromisoformat(x["quand"]).timestamp()
            except (ValueError, KeyError, TypeError): continue
            if t <= limite: break
            if x.get("compte"): out.append(t)
        return sorted(out)

    def relire_envois(self):
        """Les messages ADMIS de la dernière heure, relus au journal : le débit du lot 3 compte encore après un redémarrage."""
        limite = time.time() - 3600; out = []
        try: lignes = self.journal_actions.read_text().splitlines()
        except OSError: return out
        for l in reversed(lignes):
            try: x = json.loads(l); t = datetime.datetime.fromisoformat(x["quand"]).timestamp()
            except (ValueError, KeyError, TypeError): continue
            if t <= limite: break
            if x.get("genre") in ("message", "transcription") and x.get("resultat") == "admis":
                ps = x.get("pieces") or []
                out.append((t, 1 if x["genre"] == "message" else 0, len(ps), sum(int(p.get("taille") or 0) for p in ps)))
        return sorted(out)

    def noter_message(self, genre, source, agent, resultat, motif, taille=None, pieces=None):
        """Garde-fou 5 du lot 3 : une ligne par tentative (refus compris) — l'agent, la taille du texte, chaque pièce (type, taille, sha256) ;
        JAMAIS le texte ni le contenu. → True si la ligne est écrite."""
        ligne = json.dumps({"quand": datetime.datetime.now().isoformat(timespec="seconds"), "via": "interface web", "genre": genre, "source": source,
                            "agent": agent if isinstance(agent, str) and CIBLE.fullmatch(agent) else None, "resultat": resultat, "motif": motif,
                            "taille_texte": taille, "pieces": [{"type": p["ext"], "taille": p["taille"], "sha256": p["sha256"]} for p in pieces or []]}, ensure_ascii=False)
        with self.verrou:
            try:
                fd = os.open(self.journal_actions, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, "a") as f: f.write(ligne + "\n")
                ecrit = True
            except OSError as e: sys.stderr.write(f"journal des actions impossible à écrire ({type(e).__name__})\n"); ecrit = False
        sys.stderr.write(f"{genre} {resultat}" + (f" ({motif})" if motif else "") + "\n")
        return ecrit

    def debit_envoi(self, message, pieces, octets, prendre):
        """Le débit du lot 3, à part des 30 actions du lot 2 : None s'il reste de la place (et la prend si `prendre`), sinon le refus nommé."""
        with self.verrou:
            limite = time.time() - 3600
            while self.envois and self.envois[0][0] <= limite: self.envois.popleft()
            m = sum(x[1] for x in self.envois); p = sum(x[2] for x in self.envois); o = sum(x[3] for x in self.envois)
            if m + message > MESSAGES_HEURE: return f"débit : {MESSAGES_HEURE} messages par heure au plus — réessaie plus tard"
            if p + pieces > PIECES_HEURE: return f"débit : {PIECES_HEURE} pièces jointes par heure au plus — réessaie plus tard"
            if o + octets > OCTETS_HEURE: return f"débit : {OCTETS_HEURE // MIO} Mio de pièces jointes par heure au plus — réessaie plus tard"
            if prendre: self.envois.append((time.time(), message, pieces, octets))
            return None

    def rendre_envoi(self):
        with self.verrou:
            if self.envois: self.envois.pop()

    def noter_action(self, source, action, cible, resultat, motif, compte):
        """Garde-fou 5 : une ligne par tentative, refus compris — l'heure, la source, l'action, la cible, l'issue et le NOM du refus ;
        jamais le texte d'un motif ni d'une réponse, jamais un jeton. Fichier 600 dans le dossier masqué aux agents. → True si la ligne
        est écrite (une action n'est jamais faite sans sa ligne)."""
        ligne = json.dumps({"quand": datetime.datetime.now().isoformat(timespec="seconds"), "via": "interface web", "source": source,
                            "action": action if action in ACTIONS_WEB else None, "cible": cible if isinstance(cible, str) and CIBLE.fullmatch(cible) else None,
                            "resultat": resultat, "motif": motif, "compte": compte}, ensure_ascii=False)
        with self.verrou:
            try:
                fd = os.open(self.journal_actions, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, "a") as f: f.write(ligne + "\n")
                ecrit = True
            except OSError as e: sys.stderr.write(f"journal des actions impossible à écrire ({type(e).__name__})\n"); ecrit = False
        sys.stderr.write(f"action {resultat} : {action if action in ACTIONS_WEB else '?'}" + (f" ({motif})" if motif else "") + "\n")
        return ecrit

    def prendre_place(self):
        """Garde-fou 6 : au plus DEBIT tentatives par heure glissante. True si celle-ci est admise (et comptée)."""
        with self.verrou:
            limite = time.time() - 3600
            while self.tentatives and self.tentatives[0] <= limite: self.tentatives.popleft()
            if len(self.tentatives) >= DEBIT: return False
            self.tentatives.append(time.time()); return True

    def rendre_place(self):
        """Une tentative qui n'a pas pu s'écrire au journal n'est pas faite : elle ne compte pas non plus (le débit relu = le journal)."""
        with self.verrou:
            if self.tentatives: self.tentatives.pop()

    def nonce(self, action, cible, empreinte):
        n = secrets.token_urlsafe(24)
        with self.verrou:
            maintenant = time.time()
            for k in [k for k, v in self.nonces.items() if v[3] < maintenant]: del self.nonces[k]
            while len(self.nonces) >= NONCES_MAX: del self.nonces[next(iter(self.nonces))]
            self.nonces[n] = (action, cible, empreinte, maintenant + NONCE_VIE)
        return n

    def servir_nonce(self, n):
        """Le jeton d'aperçu, retiré à la première présentation (anti-rejeu) ; None s'il est inconnu, déjà servi ou périmé."""
        with self.verrou:
            v = self.nonces.pop(n, None) if isinstance(n, str) else None
        return v if v and v[3] >= time.time() else None

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
        """Le pair (l'adresse qui se connecte, jamais un en-tête X-Forwarded-*) est une source déclarée, puis Host est admis. Un refus
        sur un chemin d'action va aussi au journal des actions (garde-fou 5 : chaque tentative, refus compris)."""
        if urllib.parse.urlsplit(self.path).path in ("/api/message", "/api/message/jeton", "/api/transcrire"):
            g = "transcription" if self.path.startswith("/api/transcrire") else "message"
            if self.client_address[0] not in self.server.sources: self.server.noter_message(g, self.client_address[0], None, "refusé", "source refusée")
            elif self.headers.get("Host", "") not in self.server.hotes: self.server.noter_message(g, self.client_address[0], None, "refusé", "hôte refusé")
        if urllib.parse.urlsplit(self.path).path.startswith("/api/action"):
            if self.client_address[0] not in self.server.sources: self.server.noter_action(self.client_address[0], None, None, "refusé", "source refusée", False)
            elif self.headers.get("Host", "") not in self.server.hotes: self.server.noter_action(self.client_address[0], None, None, "refusé", "hôte refusé", False)
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
        if chemin == "/api/actions":
            return self.envoyer(200, json.dumps({"actives": self.server.actions and source_locale(self.client_address[0]),
                                                 "messages": self.server.actions and self.poste_local()}).encode())   # lot 3 : écrire à un agent (127.0.0.1 seulement)
        if chemin == "/api/action/apercu": return self.apercu()
        if chemin == "/api/message/jeton": return self.jeton_message()
        if chemin == ROUTE_REGLAGES: return self.reglages()
        if chemin == ROUTE_EXTENSIONS: return self.extensions()
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

    def do_HEAD(self):
        if urllib.parse.urlsplit(self.path).path in LECTURE_SEULE: return self.refuser()   # réglages, extensions : GET seulement
        self.do_GET()

    def do_POST(self):
        if not self.hote_ok(): return
        chemin = urllib.parse.urlsplit(self.path).path
        if chemin == "/api/action": return self.action()
        if chemin == "/api/message": return self.message()
        if chemin == "/api/transcrire": return self.transcription()
        if chemin != "/connexion": return self.refuser()
        try: n = int(self.headers.get("Content-Length", "0"))
        except ValueError: n = 0
        if not 0 < n <= 1024: return self.erreur(400, "demande refusée")
        try: donne = str(json.loads(self.rfile.read(n)).get("jeton", ""))
        except (ValueError, AttributeError): return self.erreur(400, "demande refusée")
        j = self.server.jeton()
        if not j or not hmac.compare_digest(donne.encode(), j.encode()): return self.erreur(401, "jeton refusé")
        self.envoyer(204, plus=[("Set-Cookie", f"{COOKIE}={deriver(j, 'session')}; HttpOnly; SameSite=Strict; Path=/" + ("; Secure" if self.server.nom or self.server.tls else ""))])

    def refuser(self):
        plus = [("Allow", "GET")] if urllib.parse.urlsplit(self.path).path in LECTURE_SEULE else []
        self.envoyer(405, json.dumps({"erreur": "lecture seule"}, ensure_ascii=False).encode(), plus=plus)
    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = refuser

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

    def lancer(self, args, delai=None, entree=None, brut=False):
        """Lance `berger <args>` (le code installé fait foi), 10 s au plus, 4 à la fois → sa sortie (octets), ou None après
        avoir répondu l'erreur. `brut` : le résultat complet (code compris), sans répondre d'erreur pour un code ≠ 0."""
        place = self.server.place                                          # le MÊME sémaphore pour prendre et rendre la place
        if not place.acquire(blocking=False): return self.erreur(503, "occupé : réessaie au prochain tour")
        delai = DELAI if delai is None else delai                         # lu à l'appel (pas figé au chargement du module)
        try:
            r = subprocess.run([sys.executable, str(BERGER), *args], capture_output=True, timeout=delai, input=entree)
        except subprocess.TimeoutExpired:
            return self.erreur(504, f"vue en échec : délai de {delai} s dépassé")
        finally:
            place.release()
        if brut: return r
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

    # ── actions du propriétaire (lot 2) ──
    def garde_actions(self, action=None, cible=None):
        """Garde-fous 2 et 3 communs à l'aperçu et à l'action → message de refus (déjà répondu et journalisé), ou None."""
        src = self.client_address[0]
        def non(code, texte, motif):
            self.server.noter_action(src, action, cible, "refusé", motif, False); self.erreur(code, texte); return motif
        if not self.server.actions: return non(403, "actions désactivées : [interface] actions = true absent de config.toml (lecture seule)", "actions désactivées")
        if not source_locale(src): return non(403, "source hors local/VPN : les actions ne viennent que du poste ou du VPN", "source hors local/VPN")
        if not self.connecte(): return non(401, "connexion requise : ouvre le lien donné par « berger interface lien »", "sans session")
        return None

    def jeton_action(self):
        j = self.server.jeton(); return deriver(j, "action") if j else None

    def apercu(self):
        """GET /api/action/apercu?action=&cible= : ce qui sera fait (numéro, aperçu exact, empreinte) — `berger action apercu` —, plus le
        jeton anti-rejeu de la session et un jeton d'aperçu à usage unique, lié à CETTE empreinte (garde-fou 4)."""
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        action, cible = q.get("action", [""])[0], q.get("cible", [""])[0]
        if self.garde_actions(action, cible): return
        if action not in ACTIONS_WEB or not CIBLE.fullmatch(cible): return self.erreur(400, "action ou cible refusée")
        r = self.lancer(["action", "apercu", action, cible], brut=True)
        if r is None: return
        if r.returncode: return self.erreur(409, ((r.stderr or r.stdout).decode("utf-8", "replace").strip().splitlines() or ["refusé"])[-1][:300])
        try: d = json.loads(r.stdout)
        except ValueError: return self.erreur(502, "aperçu illisible")
        d.update(nonce=self.server.nonce(action, cible, d["empreinte"]), jeton=self.jeton_action())
        self.envoyer(200, json.dumps(d, ensure_ascii=False).encode())

    def action(self):
        """POST /api/action (JSON {action, cible, empreinte, nonce, motif | texte}) : chaque garde-fou dans l'ordre, chaque refus NOMMÉ
        et journalisé ; puis `berger action faire` — le chemin de la ligne de commande — qui recompare l'empreinte au moment d'agir."""
        src = self.client_address[0]
        if self.garde_actions(): return
        if not self.server.prendre_place():
            self.server.noter_action(src, None, None, "refusé", "débit", False)
            return self.erreur(429, f"débit : {DEBIT} actions par heure au plus — réessaie plus tard")
        x = {}
        def non(code, texte, motif):
            self.server.noter_action(src, x.get("action"), x.get("cible"), "refusé", motif, True); return self.erreur(code, texte)
        if self.headers.get("Origin") not in self.server.origines: return non(403, "origine refusée : une action ne part que de cette page", "origine refusée")
        if self.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"): return non(403, "origine refusée : requête d'un autre site", "origine refusée")
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json": return non(415, "demande refusée : JSON attendu", "pas du JSON")
        try: n = int(self.headers.get("Content-Length", "0"))
        except ValueError: n = 0
        if not 0 < n <= CORPS_MAX: return non(400, "demande refusée : taille", "taille")
        try: x = json.loads(self.rfile.read(n))
        except ValueError: x = {}
        if not isinstance(x, dict): x = {}
        j = self.jeton_action()
        if not j or not hmac.compare_digest(str(self.headers.get("X-Berger-Jeton", "")).encode(), j.encode()):
            return non(403, "jeton anti-rejeu absent ou faux : rouvre l'aperçu", "jeton anti-rejeu absent ou faux")
        action, cible = x.get("action"), x.get("cible")
        if action not in ACTIONS_WEB or not isinstance(cible, str) or not CIBLE.fullmatch(cible): return non(400, "action ou cible refusée", "action ou cible refusée")
        champ = {"refuser": ("motif", "motif du refus obligatoire"), "repondre": ("texte", "réponse obligatoire")}.get(action)
        if champ and not str(x.get(champ[0]) or "").strip(): return non(400, champ[1], champ[1])
        v = self.server.servir_nonce(x.get("nonce"))
        if v is None or v[:2] != (action, cible): return non(403, "jeton d'aperçu déjà servi, périmé ou d'une autre demande : rouvre l'aperçu", "rejeu")
        if not isinstance(x.get("empreinte"), str) or not hmac.compare_digest(x["empreinte"].encode(), v[2].encode()):
            return non(409, "demande modifiée : ce n'est pas l'empreinte de l'aperçu — rien n'est fait", "demande modifiée")
        if not self.server.noter_action(src, action, cible, "admis", None, True):             # pas de ligne au journal = pas d'action ; comptée ICI
            self.server.rendre_place(); return self.erreur(503, "journal des actions impossible à écrire : rien n'est fait")
        entree = json.dumps({champ[0]: str(x[champ[0]])} if champ else {}, ensure_ascii=False).encode()
        r = self.lancer(["action", "faire", action, cible, "--empreinte", v[2], "--source", src], delai=DELAI_ACTION, entree=entree, brut=True)
        if r is None: return self.server.noter_action(src, action, cible, "refusé", "occupé ou délai", False)   # déjà comptée par « admis »
        if r.returncode:
            texte = ((r.stderr or r.stdout).decode("utf-8", "replace").strip().splitlines() or ["refusé"])[-1][:300]
            self.server.noter_action(src, action, cible, "refusé", "demande modifiée" if "demande modifiée" in texte else "refusé par la commande", False)
            return self.erreur(409, texte)
        if not self.server.noter_action(src, action, cible, "fait", None, False):                # l'issue doit être au journal : sinon, une erreur
            return self.erreur(500, "action faite, mais sa ligne « fait » n'a pas pu être écrite au journal des actions : vérifie-le avant de recommencer")
        self.envoyer(200, r.stdout)

    # ── la page « Conversation » (lot 3) ──
    def garde_message(self, genre, agent=None):
        """Garde-fous communs du lot 3 → le motif du refus (déjà répondu et journalisé), ou None. 127.0.0.1 SEULEMENT pour ce lot : ni le VPN,
        ni un relais (SWAG) — le pair ET l'en-tête Host doivent être ceux du poste."""
        src = self.client_address[0]
        def non(code, texte, motif):
            self.server.noter_message(genre, src, agent, "refusé", motif); self.erreur(code, texte); return motif
        if not self.server.actions: return non(403, "actions désactivées : [interface] actions = true absent de config.toml (lecture seule)", "actions désactivées")
        if not self.poste_local():
            return non(403, "hors 127.0.0.1 : un message ne part que du poste lui-même (ni le VPN ni un relais, pour ce lot)", "hors 127.0.0.1")
        if not self.connecte(): return non(401, "connexion requise : ouvre le lien donné par « berger interface lien »", "sans session")
        return None

    def poste_local(self):
        """Le pair est 127.0.0.1 (ou ::1) — pas une autre adresse de boucle, ni le VPN — et Host est celui du poste (localhost:port, 127.0.0.1:port)."""
        try: a = ipaddress.ip_address(self.client_address[0].split("%")[0]); a = a.ipv4_mapped or a if a.version == 6 else a
        except ValueError: return False
        boucle = str(a) in (ADRESSE, "::1")
        return boucle and self.headers.get("Host", "") in (f"localhost:{self.server.port}", f"{ADRESSE}:{self.server.port}")

    def jeton_message(self):
        """GET /api/message/jeton?agent= : le jeton anti-rejeu de la session et un jeton à usage unique lié à CET agent (un envoi, une fois)."""
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        agent, usage = q.get("agent", [""])[0], q.get("usage", ["message"])[0]
        if self.garde_message("transcription" if usage == "transcription" else "message", agent): return
        if not CIBLE.fullmatch(agent) or usage not in ("message", "transcription"): return self.erreur(400, "agent ou usage refusé")
        j = self.server.jeton()                                         # le jeton à usage unique est lié à l'agent ET à l'usage (envoi, dictée)
        self.envoyer(200, json.dumps({"jeton": deriver(j, "message") if j else None, "nonce": self.server.nonce(usage, agent, None)}).encode())

    def corps_json(self, maxi, non):
        """Le corps JSON, lu EN FLUX par morceaux et coupé avant d'aller au-delà de `maxi` → dict, ou None (refus déjà répondu par `non`)."""
        if self.headers.get("Origin") not in self.server.origines: return non(403, "origine refusée : un message ne part que de cette page", "origine refusée")
        if self.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"): return non(403, "origine refusée : requête d'un autre site", "origine refusée")
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json": return non(415, "demande refusée : JSON attendu", "pas du JSON")
        try: n = int(self.headers.get("Content-Length", "0"))
        except ValueError: n = 0
        if n > maxi: self.close_connection = True; return non(413, f"demande trop grosse ({n // MIO} Mio ; {maxi // MIO} Mio au plus) : rien n'est lu", "taille")
        if n <= 0: return non(400, "demande refusée : taille", "taille")
        morceaux, lu = [], 0
        while lu < n:
            b = self.rfile.read(min(65536, n - lu))
            if not b: break
            lu += len(b)
            if lu > maxi: self.close_connection = True; return non(413, "demande trop grosse : coupée", "taille")
            morceaux.append(b)
        try: x = json.loads(b"".join(morceaux))
        except ValueError: x = None
        if not isinstance(x, dict): return non(400, "demande illisible (objet JSON attendu)", "illisible")
        j = self.server.jeton()
        if not j or not hmac.compare_digest(str(self.headers.get("X-Berger-Jeton", "")).encode(), deriver(j, "message").encode()):
            return non(403, "jeton anti-rejeu absent ou faux : recharge la page", "jeton anti-rejeu absent ou faux")
        return x

    @staticmethod
    def meta_pieces(brutes):
        """(ext, taille, sha256) de chaque pièce REÇUE, calculés ici (jamais crus du client) ; None si illisible."""
        import base64
        out = []
        if not isinstance(brutes, list): return None
        for p in brutes:
            if not isinstance(p, dict) or not isinstance(p.get("nom"), str) or not isinstance(p.get("donnees"), str): return None
            try: o = base64.b64decode(p["donnees"], validate=True)
            except ValueError: return None
            out.append({"ext": p["nom"].rsplit(".", 1)[-1].lower()[:10] if "." in p["nom"] else "", "taille": len(o), "sha256": hashlib.sha256(o).hexdigest()})
        return out

    def message(self):
        """POST /api/message (JSON {agent, texte, pieces: [{nom, donnees}], empreinte, nonce}) : chaque garde-fou dans l'ordre, chaque refus NOMMÉ
        et journalisé ; une ligne « admis » AVANT (sinon 503, rien n'est fait) ; puis `berger conversation envoyer` — le chemin de berger parler —,
        qui recontrôle tout au moment d'agir ; la ligne de résultat (son échec : une erreur, jamais un 200)."""
        src = self.client_address[0]
        if self.garde_message("message"): return
        x = {}
        def non(code, texte, motif, meta=None):
            self.server.noter_message("message", src, x.get("agent"), "refusé", motif, len(x["texte"]) if isinstance(x.get("texte"), str) else None, meta)
            self.erreur(code, texte); return None
        refus = self.server.debit_envoi(1, 0, 0, False)
        if refus: return non(429, refus, "débit")
        x = self.corps_json(MESSAGE_MAX, non) or {}
        if not x: return
        agent, texte = x.get("agent"), x.get("texte", "")
        if not isinstance(agent, str) or not CIBLE.fullmatch(agent) or not isinstance(texte, str): return non(400, "agent ou texte refusé", "agent ou texte refusé")
        v = self.server.servir_nonce(x.get("nonce"))
        if v is None or v[:2] != ("message", agent): return non(403, "jeton d'envoi déjà servi, périmé ou d'un autre agent : rien n'est envoyé, réessaie", "rejeu")
        meta = self.meta_pieces(x.get("pieces", []))
        if meta is None: return non(400, "pièce jointe illisible", "pièce illisible")
        emp = empreinte_message(agent, texte, meta)
        if not isinstance(x.get("empreinte"), str) or not hmac.compare_digest(x["empreinte"].encode(), emp.encode()):
            return non(409, "empreinte périmée : ce qui est reçu n'est pas ce qui était montré — rien n'est envoyé", "empreinte périmée", meta)
        refus = self.server.debit_envoi(1, len(meta), sum(p["taille"] for p in meta), True)
        if refus: return non(429, refus, "débit", meta)
        if not self.server.noter_message("message", src, agent, "admis", None, len(texte), meta):
            self.server.rendre_envoi(); return self.erreur(503, "journal des actions impossible à écrire : rien n'est envoyé")
        entree = json.dumps({"texte": texte, "pieces": x.get("pieces", [])}, ensure_ascii=False).encode()
        r = self.lancer(["conversation", "envoyer", agent, "--empreinte", emp, "--source", src], delai=DELAI_MESSAGE, entree=entree, brut=True)
        if r is None: return self.server.noter_message("message", src, agent, "refusé", "occupé ou délai", len(texte), meta)
        if r.returncode:
            t = ((r.stderr or r.stdout).decode("utf-8", "replace").strip().splitlines() or ["refusé"])[-1][:300]
            self.server.noter_message("message", src, agent, "refusé", "refusé par la commande", len(texte), meta)
            return self.erreur(409, t)
        if not self.server.noter_message("message", src, agent, "fait", None, len(texte), meta):
            return self.erreur(500, "message envoyé, mais sa ligne « fait » n'a pas pu être écrite au journal des actions : vérifie-le avant de recommencer")
        self.envoyer(200, r.stdout)

    def transcription(self):
        """POST /api/transcrire (JSON {agent, nom, donnees, empreinte, nonce}) : le binaire LOCAL déclaré, par `berger conversation transcrire`
        (qui refuse sans [interface] transcription : côté serveur aussi, pas seulement le bouton grisé). Comme un envoi (renvoi n° 172) : un
        jeton à usage unique (/api/message/jeton?usage=transcription) et l'empreinte de l'audio (sha256) — une requête rejouée est refusée ;
        elle compte dans le débit. Le texte revient dans la zone de saisie, corrigeable."""
        src = self.client_address[0]
        if self.garde_message("transcription"): return
        meta = None
        def non(code, texte, motif):
            self.server.noter_message("transcription", src, None, "refusé", motif, None, meta); self.erreur(code, texte); return None
        x = self.corps_json(MESSAGE_MAX, non) or {}
        if not x: return
        agent = x.get("agent")
        if not isinstance(agent, str) or not CIBLE.fullmatch(agent): return non(400, "agent refusé", "agent refusé")
        v = self.server.servir_nonce(x.get("nonce"))
        if v is None or v[:2] != ("transcription", agent): return non(403, "jeton de dictée déjà servi, périmé ou d'un autre agent : rien n'est lancé, réessaie", "rejeu")
        meta = self.meta_pieces([{"nom": x.get("nom"), "donnees": x.get("donnees")}])
        if meta is None: return non(400, "audio illisible", "pièce illisible")
        if not isinstance(x.get("empreinte"), str) or not hmac.compare_digest(x["empreinte"].encode(), meta[0]["sha256"].encode()):
            return non(409, "empreinte périmée : l'audio reçu n'est pas celui qui a été enregistré — rien n'est lancé", "empreinte périmée")
        refus = self.server.debit_envoi(0, 1, meta[0]["taille"], True)
        if refus: return non(429, refus, "débit")
        if not self.server.noter_message("transcription", src, None, "admis", None, None, meta):
            self.server.rendre_envoi(); return self.erreur(503, "journal des actions impossible à écrire : rien n'est lancé")
        r = self.lancer(["conversation", "transcrire", "--source", src], delai=DELAI_TRANSCRIPTION, entree=json.dumps({"nom": x.get("nom"), "donnees": x.get("donnees")}).encode(), brut=True)
        if r is None: return self.server.noter_message("transcription", src, None, "refusé", "occupé ou délai", None, meta)
        if r.returncode:
            t = ((r.stderr or r.stdout).decode("utf-8", "replace").strip().splitlines() or ["refusé"])[-1][:300]
            self.server.noter_message("transcription", src, None, "refusé", "refusé par la commande", None, meta)
            return self.erreur(409, t)
        if not self.server.noter_message("transcription", src, None, "fait", None, None, meta):
            return self.erreur(500, "transcription faite, mais sa ligne « fait » n'a pas pu être écrite au journal des actions")
        self.envoyer(200, r.stdout)

    def reglages(self):
        """GET /api/vue/reglages : la page « Réglages » (lecture seule), lue ICI par le lecteur du noyau — config.toml relu, masqué avant
        d'être sérialisé ; un fichier invalide est dit sans montrer son contenu (et même quand `berger` ne démarre plus). Même enveloppe que
        `berger vue reglages --json`. Une panne du lecteur : 500 sans détail (son message pourrait citer une valeur)."""
        try:
            d = REGLAGES.donnees(Path(os.environ.get("BERGER_DIR") or ICI.parent))
            try: version = json.loads((ICI / "vues/reglages.schema.json").read_text()).get("x-version", 1)
            except (OSError, ValueError): version = None
            corps = json.dumps({"vue": "reglages", "version": version, "genere": datetime.datetime.now().isoformat(timespec="seconds"), "donnees": d},
                               ensure_ascii=False).encode()
            if REGLAGES.motif_restant(corps.decode("utf-8")): raise REGLAGES.Fuite("motif de clé dans le corps")   # dernier passage, sur ce qui part
        except Exception as e:                                             # Fuite comprise : 500 sans détail, rien n'est envoyé
            sys.stderr.write(f"réglages illisibles ({type(e).__name__})\n"); return self.erreur(500, "réglages illisibles")
        self.envoyer(200, corps)

    def extensions(self):
        """GET /api/vue/extensions : la page « Extensions » (lecture seule) — `berger vue extensions --json`, déjà filtrée par le noyau ; dernier
        passage sur ce qui part (forme de clé, bloc PEM, dossier personnel) : 500 sans détail plutôt qu'une fuite."""
        sortie = self.lancer(["vue", "extensions", "--json"])
        if sortie is None: return
        texte = sortie.decode("utf-8", "replace")
        try: json.loads(texte)
        except ValueError: return self.erreur(502, "vue en échec : réponse illisible")
        if REGLAGES.motif_restant(texte) or str(Path.home()) in texte:
            sys.stderr.write("extensions : refusé au dernier passage\n"); return self.erreur(500, "extensions illisibles")
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


def servir(port, fichier_jeton, adresse=ADRESSE, nom=None, sources=(ADRESSE,), tls=None, actions=False):
    s = Serveur(port, fichier_jeton, adresse, nom, sources, tls, actions)
    lien = f"https://{nom}/" if nom else f"{'https' if tls else 'http'}://localhost:{port}/"
    print(f"interface de Berger : {lien} (écoute sur {adresse}:{port}{', TLS' if tls else ''} ; sources admises : {', '.join(sorted(s.sources))} ; actions : {'oui' if s.actions else 'non, lecture seule'})", flush=True)
    s.serve_forever()


if __name__ == "__main__":
    p = argparse.ArgumentParser(prog="interface.py", description="lancé par « berger interface servir » (réglages : [interface] de config.toml)")
    p.add_argument("commande", choices=["servir"]); p.add_argument("port", type=int); p.add_argument("jeton")
    p.add_argument("--adresse", default=ADRESSE); p.add_argument("--nom"); p.add_argument("--sources", default=ADRESSE)
    p.add_argument("--tls", nargs=2, metavar=("CERTIFICAT", "CLE")); p.add_argument("--actions", action="store_true")
    x = p.parse_args()
    servir(x.port, x.jeton, x.adresse, x.nom, [s for s in x.sources.split(",") if s], tuple(x.tls) if x.tls else None, x.actions)
