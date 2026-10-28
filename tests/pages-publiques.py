#!/usr/bin/env python3
"""Tests de l'outil « pages_publiques » (documents publics en lecture seule) — un petit serveur HTTPS LOCAL avec un
certificat de test (autorité de test créée ici, jamais installée sur la machine) : aucun appel Internet, aucun coffre.
Usage : python3 tests/pages-publiques.py   (code de retour 0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util, os, ssl, subprocess, sys, tempfile, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODULE = Path(__file__).resolve().parent.parent / "courtier/outils/pages_publiques.py"
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def erreur(f, *a):
    """Le message d'erreur levé par f(*a), ou None si f n'a rien refusé."""
    try: f(*a); return None
    except Exception as e: return f"{type(e).__name__} : {e}"


def certificats(d):
    """Autorité de test + certificat « localhost » signé par elle ; un certificat « intrus » auto-signé, hors autorité."""
    def o(*a): subprocess.run(["openssl", *a], cwd=d, check=True, capture_output=True)
    ec = ["-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-days", "2"]
    o("req", "-x509", *ec, "-keyout", "ac.key", "-out", "ac.pem", "-subj", "/CN=Autorite de test berger",
      "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    o("req", *ec[:-2], "-keyout", "site.key", "-out", "site.csr", "-subj", "/CN=localhost")
    (Path(d) / "ext").write_text("subjectAltName=DNS:localhost\nbasicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature\n"
                                 "extendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n")
    o("x509", "-req", "-in", "site.csr", "-CA", "ac.pem", "-CAkey", "ac.key", "-CAcreateserial", "-out", "site.pem", "-days", "2", "-extfile", "ext")
    o("req", "-x509", *ec, "-keyout", "intrus.key", "-out", "intrus.pem", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost")


REQUETES = []                                                         # (méthode, chemin, en-têtes) de CHAQUE requête reçue
DOCS = {"/doc/Notes de version.pdf": b"%PDF-1.4 notes de version, premiere edition"}


class Site(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def envoyer(self, code, corps=b"", entetes=(), longueur=True):
        self.send_response(code)
        for k, v in entetes: self.send_header(k, v)
        self.send_header("Set-Cookie", "session=piege-a-cookie; Path=/")  # un client qui garderait des cookies le renverrait
        if longueur: self.send_header("Content-Length", str(len(corps)))
        self.end_headers(); self.wfile.write(corps)

    def do_GET(self):
        REQUETES.append(("GET", self.path, dict(self.headers)))
        chemin, port = urllib.parse.unquote(self.path), self.server.server_address[1]
        if chemin in DOCS: return self.envoyer(200, DOCS[chemin], [("Content-Type", "application/pdf"), ("Last-Modified", "Mon, 05 Oct 2026 08:00:00 GMT")])
        if chemin == "/redir-ok": return self.envoyer(302, entetes=[("Location", "/doc/Notes de version.pdf".replace(" ", "%20"))])
        if chemin == "/redir-dehors": return self.envoyer(302, entetes=[("Location", "https://hors-liste.exemple/doc.pdf")])
        if chemin == "/redir-http": return self.envoyer(302, entetes=[("Location", f"http://localhost:{port}/doc/Notes%20de%20version.pdf")])
        if chemin == "/gros": return self.envoyer(200, b"x" * 5000, [("Content-Type", "application/pdf")])
        if chemin == "/gros-flux":                                        # sans Content-Length annoncé : coupé à la lecture
            self.close_connection = True; return self.envoyer(200, b"x" * 5000, [("Content-Type", "application/pdf")], longueur=False)
        if chemin == "/page": return self.envoyer(200, b"<html><body>nouveautes</body></html>", [("Content-Type", "text/html; charset=utf-8")])
        self.envoyer(404, b"introuvable")

    def do_POST(self): REQUETES.append(("POST", self.path, dict(self.headers))); self.envoyer(405)


def serveur(d, cert, cle):
    s = ThreadingHTTPServer(("localhost", 0), Site)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(Path(d) / cert, Path(d) / cle)
    s.socket = ctx.wrap_socket(s.socket, server_side=True)
    threading.Thread(target=s.serve_forever, daemon=True).start(); return s


for v in ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"): os.environ.pop(v, None)
with tempfile.TemporaryDirectory() as d:
    racine = Path(d); certificats(d)
    os.environ["SSL_CERT_FILE"] = str(racine / "ac.pem")              # l'autorité de test, pour CE processus seulement
    bon, intrus = serveur(d, "site.pem", "site.key"), serveur(d, "intrus.pem", "intrus.key")
    p, pi = bon.server_address[1], intrus.server_address[1]
    spec = importlib.util.spec_from_file_location("outil_pages_publiques", MODULE)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    base = f"https://localhost:{p}"
    verbes = {
        "doc": {"url": base + "/doc/{arg}", "motif": r"[\w][\w .()+-]*\.pdf", "aide": "nom de fichier .pdf"},
        "patchs": {"url": base + "/doc/Patch {arg}.pdf", "motif": r"^\d{2}\.\d{2}\.\d{3}$"},
        "page": base + "/page", "redir-ok": base + "/redir-ok", "redir-dehors": base + "/redir-dehors",
        "redir-http": base + "/redir-http", "gros": base + "/gros", "gros-flux": base + "/gros-flux",
        "intrus": f"https://localhost:{pi}/doc/Notes%20de%20version.pdf",
        "par-adresse": f"https://127.0.0.1:{p}/doc/Notes%20de%20version.pdf",   # certificat au nom de localhost seulement
    }
    reglages = {"nom": "veille-test", "hotes": [f"localhost:{p}", f"localhost:{pi}", f"127.0.0.1:{p}"], "delai": 10,
                "taille_max": 0.001, "archive": str(racine / "archive"), "verbes": verbes}
    o = mod.Outil(reglages, None, None)
    agent = racine / "agents/metiers"; agent.mkdir(parents=True)
    o.contexte = {"agent": "metiers", "dossier": str(agent)}           # ce que pose le courtier avant chaque appel
    remis = agent / "pages/veille-test"

    # ── configuration : URL et hôtes fixés par le propriétaire, jamais par l'agent ──
    def conf(v): return mod.Outil({**reglages, "verbes": {"x": v}}, None, None)
    dire(erreur(conf, "https://hors-liste.exemple/a.pdf") and "liste blanche" in erreur(conf, "https://hors-liste.exemple/a.pdf"),
         "config : un verbe vers un hôte hors de la liste blanche est refusé au chargement")
    dire(erreur(conf, {"url": "https://{arg}/a.pdf", "motif": "x"}) is not None, "config : {arg} dans l'hôte refusé")
    dire(erreur(conf, f"http://localhost:{p}/a.pdf") is not None, "config : HTTP sans S refusé")
    dire(erreur(conf, {"url": base + "/{arg}/{arg}", "motif": "x"}) is not None, "config : deux {arg} refusés")
    dire(erreur(conf, base + "/{arg}") is not None, "config : un {arg} sans motif refusé")
    dire(erreur(conf, f"https://localhost.exemple:{p}/a.pdf") is not None and erreur(conf, f"https://x@localhost:{p}/a.pdf") is not None,
         "config : hôte comparé EXACTEMENT (ni suffixe, ni identifiant dans l'URL)")
    dire(erreur(conf, f"https://localhost:{p + 1 if p + 1 != pi else p + 2}/a.pdf") is not None, "config : un autre port du même hôte est refusé")
    dire(erreur(lambda: mod.Outil({**reglages, "verbes": {"liste": base + "/a.pdf"}}, None, None)) is not None, "config : le verbe « liste » est réservé")
    dire(set(o.verbes) == set(verbes) | {"liste"} and o.hotes() == {}, "l'outil n'a que les verbes configurés + liste, et aucun secret")

    # ── arguments : refusés AVANT tout appel réseau ──
    n0 = len(REQUETES)
    for mauvais in ("..pdf", "a..b.pdf", "a/b.pdf", "a\\b.pdf", "a?.pdf", "a#.pdf", "a%2e.pdf", "-a.pdf", "a\n.pdf",
                    "https:__hors-liste.exemple_a.pdf.exe", "a.exe"):
        dire(erreur(o.verbes["doc"], [mauvais]) is not None, f"argument refusé : {mauvais!r}")
    dire(erreur(o.verbes["doc"], []) is not None and erreur(o.verbes["doc"], ["a.pdf", "b.pdf"]) is not None, "il faut UN argument, pas zéro ni deux")
    dire(erreur(o.verbes["page"], ["x"]) is not None, "un verbe sans {arg} n'accepte aucun argument")
    dire(erreur(o.verbes["patchs"], ["24.10"]) is not None and erreur(o.verbes["patchs"], ["24.10.123 "]) is not None,
         "patchs : la version doit suivre son motif entier")
    dire(len(REQUETES) == n0, "aucun argument refusé n'a atteint le serveur")

    # ── NOUVEAU / INCHANGÉ / MODIFIÉ, remise chez le demandeur ──
    r = o.verbes["doc"](["Notes de version.pdf"])
    dire(r["etat"] == "NOUVEAU" and REQUETES[-1][1] == "/doc/Notes%20de%20version.pdf", "premier téléchargement : NOUVEAU, espaces encodés dans l'URL")
    dire((remis / "Notes de version.pdf").read_bytes() == DOCS["/doc/Notes de version.pdf"], "le document arrive dans <agent>/pages/<outil>/")
    dire(len(r["sha256"]) == 64 and r["last_modified"].startswith("Mon, 05 Oct 2026") and r["octets"] == len(DOCS["/doc/Notes de version.pdf"]),
         "réponse : empreinte SHA-256, Last-Modified du site, taille")
    r2 = o.verbes["doc"](["Notes de version.pdf"])
    dire(r2["etat"].startswith("INCHANGÉ") and r2["sha256"] == r["sha256"], "même fichier deux fois : INCHANGÉ")
    DOCS["/doc/Notes de version.pdf"] = b"%PDF-1.4 notes de version, seconde edition"
    r3 = o.verbes["doc"](["Notes de version.pdf"])
    dire(r3["etat"].startswith("MODIFIÉ (depuis le ") and r3["sha256"] != r["sha256"], "fichier changé : MODIFIÉ (depuis le <date>)")
    dire((remis / "Notes de version.pdf").read_bytes().endswith(b"seconde edition"), "la nouvelle version est remise")
    arch = sorted(x.name for x in (racine / "archive/veille-test").iterdir())
    dire("index.json" in arch and sum(x.endswith("_Notes de version.pdf") for x in arch) == 2, "archive : les deux versions et l'index")
    a = o.verbes["doc"](["Absent.pdf"])
    dire(a["etat"] == "ABSENT (HTTP 404)" and "ne prouve pas" in a["rappel"] and not (remis / "Absent.pdf").exists(),
         "404 : ABSENT, avec le rappel qu'un 404 ne prouve pas qu'un document est privé ; rien n'est remis")
    h = o.verbes["page"]([])
    dire(h["etat"] == "NOUVEAU" and (remis / "page.html").is_file(), "une page HTML est remise (nom assaini, .html ajouté)")
    lst = o.verbes["liste"]([])
    dire(set(lst["verbes"]) == set(verbes) and lst["verbes"]["patchs"]["motif"].startswith("^")
         and {x["demande"] for x in lst["archive"]} == {"doc Notes de version.pdf", "page"}
         and next(x for x in lst["archive"] if x["demande"] == "page")["versions"] == 1
         and next(x for x in lst["archive"] if x["demande"] != "page")["versions"] == 2, "liste : verbes configurés et état de l'archive")

    # ── redirections, taille, TLS ──
    rr = o.verbes["redir-ok"]([])
    dire(rr["etat"].startswith(("NOUVEAU", "INCHANGÉ", "MODIFIÉ")) and rr.get("url_finale", "").endswith("/doc/Notes%20de%20version.pdf"),
         "redirection vers un hôte de la liste : suivie (url finale dite)")
    e = erreur(o.verbes["redir-dehors"], [])
    dire(e is not None and "liste blanche" in e, "redirection vers un hôte hors liste : refusée")
    e = erreur(o.verbes["redir-http"], [])
    dire(e is not None and "HTTPS" in e, "redirection vers HTTP (même hôte) : refusée")
    for v in ("gros", "gros-flux"):
        e = erreur(o.verbes[v], [])
        dire(e is not None and "trop gros" in e and not (remis / v).exists(), f"taille max dépassée : refusée ({v}), rien n'est remis")
    e = erreur(o.verbes["intrus"], [])
    dire(e is not None and "NON VÉRIFIABLE" in e and "côté système" in e, "certificat non signé par une autorité reconnue : refus, message clair")
    e = erreur(o.verbes["par-adresse"], [])
    dire(e is not None and "NON VÉRIFIABLE" in e, "certificat valide mais pour un autre nom : refus (nom d'hôte vérifié)")

    # ── jamais ailleurs que chez le demandeur ; jamais un lien symbolique suivi ──
    ailleurs = racine / "ailleurs"; ailleurs.mkdir(); (ailleurs / "cible").write_text("intact")
    (remis / "Piege.pdf").symlink_to(ailleurs / "cible")
    DOCS["/doc/Piege.pdf"] = b"%PDF-1.4 piege"
    o.verbes["doc"](["Piege.pdf"])
    dire((ailleurs / "cible").read_text() == "intact" and not (remis / "Piege.pdf").is_symlink(), "un lien symbolique dans pages/ est remplacé, jamais suivi")
    autre = racine / "agents/autre"; autre.mkdir(parents=True); (autre / "pages").symlink_to(ailleurs)
    o.contexte = {"agent": "autre", "dossier": str(autre)}
    e = erreur(o.verbes["doc"], ["Piege.pdf"])
    dire(e is not None and "lien symbolique" in e and sorted(x.name for x in ailleurs.iterdir()) == ["cible"],
         "pages/ en lien symbolique vers un autre dossier : remise refusée, rien écrit ailleurs")
    o.contexte = None
    sans = o.verbes["doc"](["Piege.pdf"])
    dire(sans["remis"].startswith("non"), "sans agent demandeur : rien n'est remis (l'archive seule est tenue)")
    hors = [str(x.relative_to(racine)) for x in racine.rglob("*") if x.is_file() and not x.is_symlink()
            and not x.is_relative_to(racine / "archive") and not x.is_relative_to(remis) and x.parent != racine and x != ailleurs / "cible"]
    dire(hors == [], f"aucun fichier écrit hors de <agent>/pages/<outil>/ et de l'archive {hors[:3]}")

    # ── ce qui part vers le site ──
    dire(REQUETES and all(m == "GET" for m, _, _ in REQUETES), f"GET seulement ({len(REQUETES)} requêtes reçues)")
    dire(not any(k.lower() in ("cookie", "authorization", "proxy-authorization") for _, _, h_ in REQUETES for k in h_),
         "aucun en-tête Cookie ni Authorization envoyé (le cookie posé par le site n'est jamais renvoyé)")
    bon.shutdown(); intrus.shutdown()

    # ── l'exemple de config.exemple.toml : chargé tel quel, adresses encodées comme le site les attend (sans réseau) ──
    import re, tomllib
    texte = (MODULE.parent.parent.parent / "config.exemple.toml").read_text()
    bloc = texte[texte.index("# [outils.veille-editeur]"):].split("\n\n")[0].splitlines()
    exemple = tomllib.loads("\n".join(l[2:] for l in bloc if re.match(r"# (\[|\w[\w-]* = )", l)))["outils"]["veille-editeur"]
    v = mod.Outil({**exemple, "nom": "veille-editeur", "archive": str(racine / "archive")}, None, None)
    dire(set(v.verbes) == {"patchs", "doc-comptaex", "doc-gestex", "nouveautes-gestex", "nouveautes-comptaex", "liste"},
         "exemple veille-editeur : chargé, tous ses verbes sur des hôtes de sa liste blanche")
    dire(v.url("patchs", ["26.20.096"])[1].endswith("/Patchs/Patch_COMPTAEX%20GESTEX%20CONNECT%2026.20.096.pdf"), "exemple : patchs, espaces encodés")
    for verbe, logiciel in (("nouveautes-gestex", "GESTEX"), ("nouveautes-comptaex", "COMPTAEX")):
        doc = f"NOUV_2026-2_{logiciel} CONNECT_26.20.pdf"
        u = v.url(verbe, [doc])[1]
        dire(u.startswith("https://depot.editeur.example/") and u.endswith(f"/{logiciel}/Doc%20Nouveaut%C3%A9s/NOUV_2026-2_{logiciel}%20CONNECT_26.20.pdf"),
             f"exemple : {verbe} accepte « {doc} » (é et espaces encodés)")
        dire(erreur(v.url, verbe, [f"Nouv_2026-2_{logiciel} CONNECT_26.20.pdf"]) is None, f"exemple : {verbe} accepte aussi « Nouv_… »")
        for mauvais in ("a/b.pdf", "../x.pdf", f"NOUV_2026-2_{'COMPTAEX' if logiciel == 'GESTEX' else 'GESTEX'} CONNECT_26.20.pdf"):
            dire(erreur(v.url, verbe, [mauvais]) is not None, f"exemple : {verbe} refuse « {mauvais} »")

print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
