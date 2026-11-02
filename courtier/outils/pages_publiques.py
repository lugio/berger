# -*- coding: utf-8 -*-
"""Outil de type « pages_publiques » pour le courtier de Berger — récupère, en LECTURE SEULE, des documents PUBLICS (PDF,
HTML) sur une liste blanche d'hôtes, sans identifiant, et les remet à l'agent qui demande (il n'a pas de réseau : c'est le
courtier qui télécharge pour lui). Premier usage : la veille d'un logiciel métier (notes de patch, nouveautés, doc).

Réglages (config.toml, section [outils.<nom>]) :
  hotes       liste blanche EXACTE des hôtes (« hôte » = port 443 seulement, « hôte:port » pour un autre port)
  delai       durée maximale d'un téléchargement, redirections comprises, en secondes (30 par défaut)
  taille_max  taille maximale d'un document, en Mo (50 par défaut)
  archive     facultatif : dossier de l'archive locale (défaut : courtier/pages/, non versionné) ; l'outil y range <nom>/
  [outils.<nom>.verbes.<verbe>]  url = modèle d'URL FIXÉ ici, avec au plus un {arg} (jamais dans l'hôte) ;
              motif = expression que {arg} doit suivre entière (obligatoire s'il y a un {arg}) ; aide = une ligne.
L'agent ne fournit JAMAIS une URL ni un hôte : seulement l'argument d'un verbe. {arg} est encodé dans l'URL (espaces),
mais refusé s'il contient « .. », « / », « \\ », « ? », « # », « % », un caractère de contrôle ou commence par un tiret.

Règles : HTTPS seulement, GET seulement ; aucun cookie, aucune session, aucun secret, aucun en-tête d'authentification ;
redirections suivies seulement vers un hôte de la liste blanche, en HTTPS (sinon refus) ; taille et délai bornés ;
vérification TLS TOUJOURS active (jamais l'équivalent de curl -k) : une chaîne de certificats incomplète se corrige côté
système, pas ici. Le proxy HTTPS de l'environnement est suivi (tunnel : le TLS reste vérifié de bout en bout).

Archive locale (empreinte SHA-256, dates, toutes les versions) : la réponse dit NOUVEAU / INCHANGÉ / MODIFIÉ (depuis le
<date>) / ABSENT (code HTTP). Le document est remis dans le dossier de L'AGENT QUI DEMANDE seulement
(<dossier de l'agent>/pages/<nom de l'outil>/<nom de fichier assaini>), sans jamais suivre un lien symbolique.
Verbe « liste » : les verbes configurés et ce que l'archive contient."""
import datetime, hashlib, http.client, importlib.util, json, os, re, socket, ssl, time, urllib.parse, urllib.request
from pathlib import Path

_spec = importlib.util.spec_from_file_location("outil__contexte", Path(__file__).with_name("_contexte.py"))
_contexte = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_contexte)   # contexte propre à chaque appel

INTERDITS = ("..", "/", "\\", "?", "#", "%")
REDIRECTIONS = (301, 302, 303, 307, 308)
MAX_REDIRECTIONS = 5
MO = 1024 * 1024
RAPPEL_404 = "un 404 (ou un refus) ne prouve pas qu'un document est privé ni qu'il n'existe pas : il a pu être déplacé ou renommé"


def lisible(n):
    return f"{n / MO:.1f} Mo".replace(".", ",") if n >= MO / 10 else f"{n / 1024:.1f} ko".replace(".", ",")


def maintenant():
    return datetime.datetime.now().isoformat(sep=" ", timespec="minutes")


class Outil:
    contexte = _contexte.ContexteDeLAppel(None)                        # posé par le courtier pour CET appel : {"agent", "dossier"}

    def __init__(self, reglages, secret, verifier_hote):              # secret, verifier_hote : inutiles ici (aucun secret)
        self.nom = str(reglages.get("nom", "pages"))
        if not re.fullmatch(r"[\w-]{1,40}", self.nom): raise ValueError(f"nom d'outil invalide : {self.nom}")
        self.hotes_permis = {str(h).strip().lower() for h in reglages.get("hotes", []) if str(h).strip()}
        if not self.hotes_permis: raise ValueError(f"{self.nom} : liste blanche « hotes » vide")
        self.delai = float(reglages.get("delai", 30)); self.taille_max = int(float(reglages.get("taille_max", 50)) * MO)
        racine = reglages.get("archive") or Path(__file__).resolve().parent.parent / "pages"
        self.archive = Path(os.path.expanduser(str(racine))) / self.nom
        self.modeles, self.verbes = {}, {}
        for verbe, r in reglages.get("verbes", {}).items():
            r = {"url": r} if isinstance(r, str) else dict(r)
            self.modeles[verbe] = self.controler_modele(verbe, r)
            self.verbes[verbe] = self.fabriquer(verbe)
        self.verbes["liste"] = self.liste

    def hotes(self): return {}                                        # aucun secret ne part d'ici

    # ───────── configuration : chaque verbe = une URL fixée, au plus un {arg} hors de l'hôte ─────────
    def controler_modele(self, verbe, r):
        url, motif = str(r.get("url", "")), r.get("motif")
        if not re.fullmatch(r"[\w-]{1,40}", verbe) or verbe in ("liste", "aide"): raise ValueError(f"{self.nom} : nom de verbe refusé « {verbe} »")
        s = urllib.parse.urlsplit(url)
        if s.scheme != "https": raise ValueError(f"{self.nom}.{verbe} : HTTPS seulement")
        if not self.permis(s): raise ValueError(f"{self.nom}.{verbe} : hôte hors de la liste blanche ({s.netloc})")
        if url.count("{arg}") > 1 or re.sub(r"\{arg\}", "", url).count("{") or "}" in re.sub(r"\{arg\}", "", url):
            raise ValueError(f"{self.nom}.{verbe} : au plus UN {{arg}}, aucune autre accolade")
        if "{arg}" in s.netloc or s.fragment: raise ValueError(f"{self.nom}.{verbe} : l'hôte est fixé, pas de « # »")
        if "{arg}" in url and not motif: raise ValueError(f"{self.nom}.{verbe} : un {{arg}} demande son « motif »")
        return {"url": url, "motif": re.compile(str(motif)) if motif else None, "aide": str(r.get("aide", "")).strip()}

    def permis(self, s):
        """Hôte de la liste blanche, comparé EXACTEMENT (sans identifiant dans l'URL ; port 443 sauf « hôte:port » listé)."""
        if "@" in s.netloc or not s.hostname: return False
        try: port = s.port
        except ValueError: return False
        h = s.hostname.lower()
        return (port in (None, 443) and h in self.hotes_permis) or f"{h}:{port}" in self.hotes_permis

    def fabriquer(self, verbe):
        m = self.modeles[verbe]
        def lire(args): return self.recuperer(verbe, args)
        lire.__doc__ = (f"{verbe}{' <' + (m['aide'] or m['motif'].pattern) + '>' if m['motif'] else ''} : "
                        f"récupère {m['url']} (document public, remis dans ton dossier pages/{self.nom}/)")
        return lire

    def url(self, verbe, args):
        m = self.modeles[verbe]
        if not m["motif"]:
            if args: raise ValueError(f"{verbe} n'accepte aucun argument")
            a = None
        else:
            if len(args) != 1: raise ValueError(f"{verbe} attend UN argument ({m['aide'] or m['motif'].pattern})")
            a = args[0]
            if not a.strip() or a.startswith("-") or any(x in a for x in INTERDITS) or any(ord(c) < 32 or ord(c) == 127 for c in a):
                raise ValueError("argument refusé : ni « .. », « / », « \\ », « ? », « # », « % », caractère de contrôle, ni tiret initial")
            if not m["motif"].fullmatch(a): raise ValueError(f"argument refusé : « {a} » ne suit pas le motif de {verbe} ({m['motif'].pattern})")
        s = urllib.parse.urlsplit(m["url"])
        sur = "!$&'()*+,;=:@-._~%{}"                                    # le modèle garde ses %XX ; les espaces sont encodés
        chemin, requete = urllib.parse.quote(s.path, safe="/" + sur), urllib.parse.quote(s.query, safe="/?" + sur)
        if a is not None:
            chemin = chemin.replace("{arg}", urllib.parse.quote(a, safe="")); requete = requete.replace("{arg}", urllib.parse.quote(a, safe=""))
        return a, urllib.parse.urlunsplit(("https", s.netloc, chemin or "/", requete, ""))

    # ───────── téléchargement ─────────
    def connexion(self, hote, port, ctx, delai):
        proxy = urllib.request.getproxies().get("https")
        if proxy and not urllib.request.proxy_bypass(hote):
            p = urllib.parse.urlsplit(proxy if "://" in proxy else f"http://{proxy}")
            if p.username: raise PermissionError("proxy avec identifiant : non pris en charge (cet outil n'a aucun secret)")
            c = http.client.HTTPSConnection(p.hostname, p.port or 80, timeout=delai, context=ctx)
            c.set_tunnel(hote, port); return c                            # TLS de bout en bout avec le site, vérifié
        return http.client.HTTPSConnection(hote, port, timeout=delai, context=ctx)

    def telecharger(self, url):
        """GET seul, sans cookie ni authentification. -> (code HTTP, contenu ou None, url finale, Last-Modified, type)."""
        fin = time.monotonic() + self.delai
        ctx = ssl.create_default_context()                                # vérification du certificat ET du nom : toujours
        assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
        for _ in range(MAX_REDIRECTIONS + 1):
            s = urllib.parse.urlsplit(url)
            if s.scheme != "https": raise PermissionError(f"refusé : redirection hors HTTPS ({url[:100]})")
            if not self.permis(s): raise PermissionError(f"refusé : hôte hors de la liste blanche ({s.netloc[:60]})")
            reste = fin - time.monotonic()
            if reste <= 0: raise TimeoutError
            c = self.connexion(s.hostname, s.port or 443, ctx, reste)
            try:
                c.request("GET", (s.path or "/") + (f"?{s.query}" if s.query else ""),
                          headers={"User-Agent": "berger-pages-publiques", "Accept": "*/*", "Accept-Encoding": "identity"})
                r = c.getresponse()
                if r.status in REDIRECTIONS:
                    loc = r.getheader("Location")
                    if not loc: raise RuntimeError(f"redirection HTTP {r.status} sans destination")
                    url = urllib.parse.urljoin(url, loc.strip()); continue
                if r.status != 200: return r.status, None, url, None, None
                annonce = r.getheader("Content-Length", "")
                if annonce.isdigit() and int(annonce) > self.taille_max:
                    raise ValueError(f"refusé : document trop gros ({lisible(int(annonce))} annoncés, {lisible(self.taille_max)} au plus)")
                morceaux, total = [], 0
                while b := r.read(65536):
                    total += len(b)
                    if total > self.taille_max: raise ValueError(f"refusé : document trop gros (plus de {lisible(self.taille_max)})")
                    if time.monotonic() > fin: raise TimeoutError
                    morceaux.append(b)
                return 200, b"".join(morceaux), url, r.getheader("Last-Modified"), r.getheader("Content-Type")
            except ssl.SSLCertVerificationError as e:
                raise ConnectionError(f"certificat de {s.hostname} NON VÉRIFIABLE ({e.verify_message}) : téléchargement refusé. "
                                      "La vérification TLS reste toujours active ; si la chaîne de certificats du site est incomplète, "
                                      "le remède est côté système (certificat intermédiaire ajouté au magasin de la machine), pas dans l'outil") from None
            except (socket.timeout, TimeoutError):
                raise TimeoutError(f"délai dépassé ({self.delai:g} s au plus)") from None
            finally:
                c.close()
        raise PermissionError(f"refusé : plus de {MAX_REDIRECTIONS} redirections")

    # ───────── archive (côté courtier) et remise (dossier du demandeur) ─────────
    def index(self):
        f = self.archive / "index.json"
        try: return json.loads(f.read_text())
        except (OSError, ValueError): return {}

    def ranger(self, idx):
        self.archive.mkdir(parents=True, exist_ok=True)
        tmp = self.archive / ".index.json.tmp"; tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=1)); tmp.replace(self.archive / "index.json")

    @staticmethod
    def nom_fichier(url, type_):
        dernier = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])
        n = re.sub(r"[^\w .()+-]", "_", dernier).strip().lstrip(".-_ ")[:120].rstrip(". ")
        if not n: n = "page"
        if "." not in n and "html" in (type_ or ""): n += ".html"
        return n

    def remettre(self, nom, contenu):
        """Écrit pages/<outil>/<nom> dans le dossier de l'agent qui demande — et nulle part ailleurs. Le courtier a plus de
        droits que l'agent : aucun lien symbolique n'est suivi (dossiers ouverts O_NOFOLLOW, fichier remplacé, jamais suivi)."""
        dossier = (self.contexte or {}).get("dossier")
        if not dossier: return None
        fds = [os.open(dossier, os.O_RDONLY | os.O_DIRECTORY)]
        try:
            for partie in ("pages", self.nom):
                try: os.mkdir(partie, 0o755, dir_fd=fds[-1])
                except FileExistsError: pass
                try: fds.append(os.open(partie, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fds[-1]))
                except OSError: raise PermissionError(f"remise refusée : {partie} n'est pas un vrai dossier (lien symbolique ?)") from None
            tmp = f".{nom}.{os.getpid()}.tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=fds[-1])
            with os.fdopen(fd, "wb") as f: f.write(contenu)
            try: os.replace(tmp, nom, src_dir_fd=fds[-1], dst_dir_fd=fds[-1])
            except OSError:
                os.unlink(tmp, dir_fd=fds[-1]); raise PermissionError(f"remise refusée : {nom} existe et n'est pas un fichier") from None
            return str(Path(dossier) / "pages" / self.nom / nom)
        finally:
            for fd in fds: os.close(fd)

    def recuperer(self, verbe, args):
        a, url = self.url(verbe, args)
        code, contenu, finale, last_modified, type_ = self.telecharger(url)
        cle = f"{verbe} {a}" if a is not None else verbe
        idx = self.index(); avant = idx.get(cle); quand = maintenant()
        rep = {"demande": cle, "url": url}
        if finale != url: rep["url_finale"] = finale
        if code != 200:
            rep.update(etat=f"ABSENT (HTTP {code})", rappel=RAPPEL_404)
            if avant: rep["archive"] = f"dernière version archivée : vue le {avant['verifie_le']}, empreinte {avant['sha256'][:16]}…"
            return rep
        empreinte = hashlib.sha256(contenu).hexdigest(); nom = self.nom_fichier(url, type_)
        if not avant: etat = "NOUVEAU"
        elif avant["sha256"] == empreinte: etat = f"INCHANGÉ (même empreinte depuis le {avant['vu_le']})"
        else: etat = f"MODIFIÉ (depuis le {avant['verifie_le']} : l'empreinte a changé)"
        self.archive.mkdir(parents=True, exist_ok=True)
        copie = self.archive / f"{empreinte[:16]}_{nom}"                    # toutes les versions sont gardées
        if not copie.exists(): copie.write_bytes(contenu)
        idx[cle] = {"url": url, "fichier": nom, "sha256": empreinte, "taille": len(contenu), "type": type_, "last_modified": last_modified,
                    "vu_le": avant["vu_le"] if avant and avant["sha256"] == empreinte else quand, "verifie_le": quand,
                    "versions": (avant or {}).get("versions", 0) + (not avant or avant["sha256"] != empreinte)}
        self.ranger(idx)
        rep.update(etat=etat, taille=lisible(len(contenu)), octets=len(contenu), sha256=empreinte, type=type_,
                   last_modified=last_modified or "non fourni par le site", remis=self.remettre(nom, contenu) or "non (aucun agent demandeur)")
        return rep

    def liste(self, args):
        """liste : les verbes configurés et ce que l'archive contient (empreinte, dates, taille)."""
        if args: raise ValueError("liste n'accepte aucun argument")
        verbes = {v: {"url": m["url"], "argument": (m["aide"] or m["motif"].pattern) if m["motif"] else "aucun",
                      **({"motif": m["motif"].pattern} if m["motif"] else {})} for v, m in self.modeles.items()}
        archive = [{"demande": k, "fichier": d["fichier"], "taille": lisible(d["taille"]), "sha256": d["sha256"][:16] + "…",
                    "vu_le": d["vu_le"], "verifie_le": d["verifie_le"], "last_modified": d.get("last_modified") or "non fourni",
                    "versions": d.get("versions", 1)} for k, d in sorted(self.index().items())]
        return {"outil": self.nom, "hotes": sorted(self.hotes_permis), "taille_max": lisible(self.taille_max), "delai": f"{self.delai:g} s",
                "verbes": verbes, "archive": archive or "vide"}
