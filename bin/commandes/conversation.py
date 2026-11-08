"""Commandes « conversation » (interface web v2, lot 3 ; spec docs/plans/2026-11-05-interface-web-v2-lot3-spec.md, go n° 166) : berger conversation.

La page « Conversation » d'un agent, depuis l'interface web. Propriétaire seul : refusé à un agent (BERGER_AGENT). Le serveur (bin/interface.py)
a déjà gardé la requête (actions actives, 127.0.0.1, Host, Origin, session, jeton anti-rejeu, jeton à usage unique, débit, journal « admis ») ;
ici, tout ce qui touche l'agent et ses fichiers, recontrôlé au moment d'agir :

    berger conversation liste --json
        → JSON {agents, micro: {actif, raison}} : les pages ouvertes ([conversation] agents) et l'état du micro
    berger conversation envoyer <agent> --empreinte <e> --source <ip>     (JSON {texte, pieces: [{nom, donnees (base64)}]} sur stdin)
        → JSON {fait, message, pieces: [{chemin, genre, taille, sha256}]} : MÊME chemin que `berger parler <agent> --stdin` (parler_agent :
          agent.prompt de Herdr, puis la ligne des Échanges, « via l'interface web »)
    berger conversation transcrire --source <ip>                          (JSON {nom, donnees (base64)} sur stdin)
        → JSON {texte} : le binaire LOCAL déclaré ([interface] transcription), sans réseau, sans coffre, sans variable de Berger, 120 s au plus

Refus nommés (sys.exit « refusé : … ») : agent inconnu, page non ouverte, agent au repos ; texte trop long, caractère de contrôle, forme de
clé ; pièce d'un type refusé, aux premiers octets qui ne correspondent pas, trop grosse, trop longue, au-delà du quota, ou dont le chemin
sortirait du dossier de l'agent ; empreinte qui ne correspond pas ; micro sans transcription locale déclarée."""
import base64, contextlib, fcntl, hashlib, io, selectors, signal, stat, time

TEXTE_MAX = 20000
PIECES_MAX = 20                                       # par message (le débit horaire est tenu par le serveur)
QUOTA = 500 * 1024 * 1024                             # par agent, dans entrees/
MIO = 1024 * 1024
# Types permis : l'extension ET les premiers octets (jamais le type déclaré par le navigateur). (genre, taille maximale, signature)
TYPES = {"png": ("image", 10 * MIO), "jpg": ("image", 10 * MIO), "jpeg": ("image", 10 * MIO), "webp": ("image", 10 * MIO),
         "webm": ("audio", 25 * MIO), "ogg": ("audio", 25 * MIO), "wav": ("audio", 25 * MIO), "txt": ("texte", 2 * MIO)}
DUREE_MAX = 600                                       # s : 10 minutes d'audio au plus (lue par ffprobe)
TRANSCRIPTION_DELAI = 120                             # s au plus ; [interface] transcription_delai peut le raccourcir (1 à 120)
SORTIE_MAX = 64 * 1024                                # octets lus au plus sur stdout, et autant sur stderr, du transcripteur
CONTROLE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")   # caractères de contrôle C0 et C1 (dont U+009B, CSI), hors saut de ligne et tabulation


def signature_ok(ext, o):
    """Les premiers octets correspondent-ils à l'extension ?"""
    if ext == "png": return o[:8] == b"\x89PNG\r\n\x1a\n"
    if ext in ("jpg", "jpeg"): return o[:3] == b"\xff\xd8\xff"
    if ext == "webp": return o[:4] == b"RIFF" and o[8:12] == b"WEBP"
    if ext == "wav": return o[:4] == b"RIFF" and o[8:12] == b"WAVE"
    if ext == "ogg": return o[:4] == b"OggS"
    if ext == "webm": return o[:4] == b"\x1a\x45\xdf\xa3" and b"webm" in o[:64]
    if ext == "txt":
        try: t = o.decode("utf-8")
        except UnicodeDecodeError: return False
        return not CONTROLE.search(t.replace("\r\n", "\n"))
    return False


def empreinte(agent, texte, pieces):
    """L'empreinte de ce qui est MONTRÉ (agent, texte, chaque pièce : type, taille, sha256) — calculée de même par la page."""
    return hashlib.sha256("\0".join([agent, texte] + [f"{p['ext']}:{p['taille']}:{p['sha256']}" for p in pieces]).encode("utf-8")).hexdigest()


def forme_de_cle(t):
    return masquer_secret(t) != t                            # MOTIFS_CLES (courtier/_secrets.py), par le noyau : la même définition partout


def verifier_texte(t):
    if not isinstance(t, str): raise Refus("texte illisible")
    if len(t) > TEXTE_MAX: raise Refus(f"texte trop long ({len(t)} caractères ; {TEXTE_MAX} au plus — un long collage devient une pièce jointe)")
    if CONTROLE.search(t) or "\r" in t: raise Refus("caractère de contrôle dans le texte (seuls le saut de ligne et la tabulation sont permis)")
    if forme_de_cle(t): raise Refus("forme de clé dans le texte : rien n'est envoyé — une clé se range dans le coffre (berger coffre), jamais dans un message")
    return t


def duree_audio(chemin):
    """Durée en secondes lue par ffprobe (déjà présent), ou None si elle est illisible."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(chemin)],
                           capture_output=True, text=True, timeout=30, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
        return float(r.stdout.strip()) if r.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired): return None


def lire_pieces(brutes):
    """Les pièces reçues : [{ext, genre, octets, taille, sha256}], chaque type contrôlé (extension, premiers octets, taille). Refus nommé sinon."""
    if not isinstance(brutes, list): raise Refus("pièces illisibles")
    if len(brutes) > PIECES_MAX: raise Refus(f"trop de pièces ({len(brutes)} ; {PIECES_MAX} au plus par message)")
    out = []
    for p in brutes:
        if not isinstance(p, dict) or not isinstance(p.get("nom"), str) or not isinstance(p.get("donnees"), str): raise Refus("pièce illisible")
        ext = p["nom"].rsplit(".", 1)[-1].lower() if "." in p["nom"] else ""
        if ext not in TYPES: raise Refus(f"type de pièce refusé (.{ext[:10]}) : images PNG, JPEG, WebP ; audio WebM, Ogg, WAV ; texte")
        try: o = base64.b64decode(p["donnees"], validate=True)
        except ValueError: raise Refus("pièce illisible (base64)") from None
        genre, maxi = TYPES[ext]
        if len(o) > maxi: raise Refus(f"pièce trop grosse ({len(o) / MIO:.1f} Mio ; {maxi // MIO} Mio au plus pour un fichier {genre})")
        if not signature_ok(ext, o): raise Refus(f"pièce .{ext} refusée : ses premiers octets ne sont pas ceux d'un fichier .{ext}")
        if genre == "texte" and forme_de_cle(o.decode("utf-8")): raise Refus("forme de clé dans le texte collé : rien n'est envoyé — une clé se range dans le coffre")
        out.append({"ext": ext, "genre": genre, "octets": o, "taille": len(o), "sha256": hashlib.sha256(o).hexdigest()})
    return out


def dossier_prive(parent_fd, nom):
    """Un sous-dossier 0700 de `parent_fd`, créé s'il manque, JAMAIS un lien : → son descripteur (O_DIRECTORY|O_NOFOLLOW)."""
    try: os.mkdir(nom, 0o700, dir_fd=parent_fd)
    except FileExistsError: pass
    fd = os.open(nom, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    if stat.S_IMODE(os.fstat(fd).st_mode) != 0o700: os.fchmod(fd, 0o700)
    return fd


def occupe(racine):
    """Octets déjà rangés sous entrees/ (sans suivre aucun lien)."""
    total = 0
    for d, _, fs in os.walk(racine, followlinks=False):
        for f in fs:
            try: st = os.lstat(os.path.join(d, f))
            except OSError: continue
            if stat.S_ISREG(st.st_mode): total += st.st_size
    return total


def ranger(a, pieces):
    """Range chaque pièce dans le dossier de l'agent DESTINATAIRE seulement : entrees/AAAA-MM-JJ/HHMMSS-<n>.<ext>, dossiers 0700, fichiers 0600
    écrits en O_EXCL|O_NOFOLLOW (un lien posé à l'avance n'est jamais suivi), nom fait par Berger. Le chemin est construit ici puis contrôlé
    une fois résolu. Quota de 500 Mio : au-delà, refus (rien n'est supprimé). → [{chemin, genre, taille, sha256}]."""
    if not pieces: return []
    base = dossier(a).resolve()
    racine = base / "entrees"
    if racine.is_symlink(): raise Refus("entrees/ est un lien : refusé (le chemin sortirait du dossier de l'agent)")
    try: return _ranger(base, racine, pieces)
    except OSError as e: raise Refus(f"pièce non rangée ({e.strerror or 'erreur système'}) : un dossier de entrees/ est un lien ou illisible — le chemin sortirait du dossier de l'agent") from None


def _ranger(base, racine, pieces):
    maintenant = datetime.datetime.now(); out = []
    fd_base = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd_e = dossier_prive(fd_base, "entrees")
        try:
            # le quota se compte ET les pièces s'écrivent sous UN verrou par agent (entrees/.verrou) : deux dépôts simultanés ne passent
            # jamais tous les deux au-delà des 500 Mio (renvoi n° 172)
            fd_v = os.open(".verrou", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=fd_e)
            fcntl.flock(fd_v, fcntl.LOCK_EX)
            deja = occupe(racine)
            if deja + sum(p["taille"] for p in pieces) > QUOTA:
                os.close(fd_v)
                raise Refus(f"quota dépassé : {deja / MIO:.0f} Mio déjà rangés dans entrees/ ({QUOTA // MIO} Mio au plus par agent) — rien n'est supprimé seul")
            fd_j = dossier_prive(fd_e, maintenant.strftime("%Y-%m-%d"))
            try:
                for p in pieces:
                    for n in range(1, 1000):
                        nom = f"{maintenant:%H%M%S}-{n}.{'jpg' if p['ext'] == 'jpeg' else p['ext']}"
                        try: fd = os.open(nom, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd_j); break
                        except FileExistsError: continue
                    else: raise Refus("trop de pièces dans la même seconde")
                    with os.fdopen(fd, "wb") as f: f.write(p["octets"])
                    chemin = racine / maintenant.strftime("%Y-%m-%d") / nom
                    if not str(chemin.resolve()).startswith(str(base / "entrees") + "/"): raise Refus("chemin de pièce hors du dossier de l'agent : refusé")
                    out.append({"chemin": chemin, "genre": p["genre"], "taille": p["taille"], "sha256": p["sha256"]})
            finally: os.close(fd_j); os.close(fd_v)                        # le verrou tombe avec son descripteur
        finally: os.close(fd_e)
    finally: os.close(fd_base)
    return out


def taille_lisible(n):
    return f"{n / MIO:.1f} Mio".replace(".", ",") if n >= MIO else f"{max(1, round(n / 1024))} Kio"


def pistes_video(chemin):
    """Le nombre de pistes vidéo lues par ffprobe (None si illisible) : un WebM ou un Ogg peut porter de la vidéo, hors périmètre."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=index", "-of", "csv=p=0", str(chemin)],
                           capture_output=True, text=True, timeout=30, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
        return len([l for l in r.stdout.splitlines() if l.strip()]) if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired): return None


def verifier_duree(pieces):
    """L'audio : sans aucune piste vidéo, 10 minutes au plus, lu par ffprobe sur une copie privée (dossier 0700 jetable)."""
    for p in pieces:
        if p["genre"] != "audio": continue
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / f"audio.{p['ext']}"; f.write_bytes(p["octets"]); os.chmod(f, 0o600)
            d = duree_audio(f); v = pistes_video(f)
        if v is None: raise Refus(f"audio .{p['ext']} illisible (pistes inconnues) : refusé")
        if v: raise Refus(f"fichier .{p['ext']} avec une piste vidéo : refusé (la vidéo est hors périmètre)")
        if d is None: raise Refus(f"audio .{p['ext']} illisible (durée inconnue) : refusé")
        if d > DUREE_MAX: raise Refus(f"audio trop long ({d / 60:.1f} min ; 10 minutes au plus)")


def agent_destinataire(a):
    """L'agent, déclaré et VIVANT, et le moteur de son panneau : Refus nommé sinon (au repos : « relance-le depuis Herdr »)."""
    if a not in agents(): raise Refus(f"agent inconnu : {str(a)[:40]}")
    if a not in conversations_ouvertes(): raise Refus(f"page « Conversation » non ouverte pour {a} ([conversation] agents dans config.toml)")
    m, vivant = vivant_herdr(a)
    if not vivant: raise Refus("au repos : relance-le depuis Herdr")
    return m


def envoyer(a, emp, source, entree):
    m = agent_destinataire(a)
    texte = verifier_texte(entree.get("texte", ""))
    pieces = lire_pieces(entree.get("pieces", []))
    if not texte.strip() and not pieces: raise Refus("message vide")
    if not emp or emp != empreinte(a, texte, pieces): raise Refus("empreinte périmée : ce qui est reçu n'est pas ce qui était montré — rien n'est envoyé")
    verifier_duree(pieces)
    ranges = ranger(a, pieces)
    relatif = not conf(a).get("dossier")                 # l'agent travaille dans son dossier : le chemin court se lit depuis là
    lignes = [f"Pièce jointe : {x['chemin'].relative_to(dossier(a).resolve()) if relatif else x['chemin']} ({x['genre']}, {taille_lisible(x['taille'])})" for x in ranges]
    message = "\n".join(([texte] if texte.strip() else []) + lignes)
    with contextlib.redirect_stdout(io.StringIO()): parler_agent(a, message, m, False)   # berger parler : agent.prompt de Herdr (jamais taper dans le panneau)
    tracer_echange(PROPRIETAIRE, a, "message", "via l'interface web : " + message)         # la ligne des Échanges de berger parler, « via l'interface web »
    journal(a, f"via l'interface web ({source}) : message de {PROPRIETAIRE} ({len(texte)} caractères, {len(ranges)} pièce(s) jointe(s))")
    return {"fait": True, "message": f"envoyé à {conf(a)['nom']}",
            "pieces": [{"chemin": str(x["chemin"]), "genre": x["genre"], "taille": x["taille"], "sha256": x["sha256"]} for x in ranges]}


def masques_transcription():
    """Ce que le binaire de transcription ne voit jamais : le coffre, les dossiers masqués aux agents, les réglages et le courtier de Berger,
    le dossier du socket de Herdr, et les masques de config.toml — `masques` ET `masques_si_presents` (.aws, .kube, .config/gh, navigateurs…),
    comme le courtier. /run, /var/run et /tmp sont recouverts à part (argv_transcription)."""
    c = Path(os.path.expanduser(str(CONFIG.get("coffre", "~/.config/berger/coffre.json")))).parent
    l = [c, HOME / ".config/berger", BERGER / "courtier", HOME / ".ssh", HOME / ".gnupg", HOME / ".claude", HOME / ".codex", HOME / ".config/herdr"]
    if socket_herdr(): l.append(Path(socket_herdr()).parent)
    l += [HOME / x for x in list(CONFIG.get("masques", [])) + list(CONFIG.get("masques_si_presents", [])) if isinstance(x, str)]
    return [p for p in dict.fromkeys(l) if p.is_dir() or p.is_file()]


def argv_transcription(binaire, t, f):
    """bwrap pour le binaire de transcription : sans réseau (--unshare-net), sans variable d'environnement de Berger ni bus de session
    (--clearenv), et SANS AUCUN socket par chemin : /run (dont /run/user/<uid> : bus D-Bus, systemd de l'utilisateur), /var/run et /tmp
    recouverts d'un tmpfs AVANT le seul dossier de la dictée ; coffre, dossiers masqués et socket de Herdr recouverts aussi (renvoi n° 172)."""
    argv = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--unshare-net", "--unshare-pid", "--unshare-ipc", "--die-with-parent", "--new-session",
            "--clearenv", "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin", "--setenv", "LANG", "C.UTF-8", "--setenv", "HOME", str(t),
            "--tmpfs", "/run", "--tmpfs", "/tmp"]
    if Path("/var/run").is_dir() and not Path("/var/run").is_symlink(): argv += ["--tmpfs", "/var/run"]   # un lien vers /run est déjà couvert
    for p in masques_transcription(): argv += ["--tmpfs", str(p)] if p.is_dir() else ["--ro-bind", "/dev/null", str(p)]   # un fichier masqué : vide
    # le binaire déclaré reste visible (lui seul, en lecture), même s'il est sous un dossier recouvert ; puis le seul dossier de la dictée
    return argv + ["--ro-bind", binaire, binaire, "--bind", str(t), str(t), "--chdir", str(t), binaire, str(f)]


def executer_borne(argv, delai, maxi=SORTIE_MAX):
    """Lance argv et lit stdout et stderr PENDANT l'exécution, `maxi` octets au plus chacun : au dépassement, ou au délai, le groupe du
    processus est tué et la transcription refusée (jamais toute la sortie en mémoire). Rend (code, stdout, stderr)."""
    p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    lus = {p.stdout: bytearray(), p.stderr: bytearray()}; sel = selectors.DefaultSelector(); fin = time.monotonic() + delai
    for f in lus: sel.register(f, selectors.EVENT_READ)
    try:
        while sel.get_map():
            reste = fin - time.monotonic()
            if reste <= 0: raise Refus(f"transcription : délai de {delai} s dépassé")
            for k, _ in sel.select(reste):
                b = os.read(k.fd, 65536)
                if not b: sel.unregister(k.fileobj); continue
                lus[k.fileobj] += b
                if len(lus[k.fileobj]) > maxi:
                    raise Refus(f"transcription : sortie trop longue (plus de {maxi // 1024} Kio) — processus arrêté, rien n'est montré")
        try: code = p.wait(timeout=max(0.1, fin - time.monotonic()))
        except subprocess.TimeoutExpired: raise Refus(f"transcription : délai de {delai} s dépassé") from None
        return code, bytes(lus[p.stdout]), bytes(lus[p.stderr])
    finally:
        sel.close()
        if p.poll() is None:
            with contextlib.suppress(OSError): os.killpg(p.pid, signal.SIGKILL)
            p.wait()
        p.stdout.close(); p.stderr.close()


def transcrire(entree):
    binaire, raison = transcription_locale()
    if binaire is None: raise Refus(raison)               # côté serveur aussi, pas seulement le bouton grisé
    pieces = lire_pieces([entree] if isinstance(entree, dict) else [])
    if pieces[0]["genre"] != "audio": raise Refus("transcription : un fichier audio (WebM, Ogg, WAV)")
    verifier_duree(pieces)
    with tempfile.TemporaryDirectory(prefix="berger-dictee-") as t:
        os.chmod(t, 0o700); f = Path(t) / f"dictee.{pieces[0]['ext']}"
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as h: h.write(pieces[0]["octets"])
        argv = argv_transcription(binaire, t, f)
        d = (CONFIG.get("interface") or {}).get("transcription_delai", TRANSCRIPTION_DELAI)
        delai = d if isinstance(d, int) and 1 <= d <= TRANSCRIPTION_DELAI else TRANSCRIPTION_DELAI
        try: code, sortie, erreurs = executer_borne(argv, delai)
        except FileNotFoundError: raise Refus("transcription : isolement impossible (bubblewrap absent) — rien n'est lancé") from None
    if code:
        err = erreurs.decode("utf-8", "replace")
        if "bwrap" in err and ("namespace" in err or "Operation not permitted" in err or "Permission" in err):
            raise Refus("transcription : isolement réseau impossible sur cette machine — rien n'est lancé")
        raise Refus(f"transcription en échec (code {code})")
    try: texte = sortie.decode("utf-8").strip()
    except UnicodeDecodeError: raise Refus("transcription illisible (pas de l'UTF-8)") from None
    texte = CONTROLE.sub("", texte.replace("\r\n", "\n").replace("\r", "\n"))[:TEXTE_MAX]
    if forme_de_cle(texte): raise Refus("forme de clé dans la transcription : rien n'est montré — une clé se range dans le coffre")
    return {"texte": texte}


def lire_entree(maxi):
    brut = sys.stdin.buffer.read(maxi + 1)
    if len(brut) > maxi: raise Refus("entrée trop grosse")
    try: x = json.loads(brut or b"{}")
    except ValueError: raise Refus("entrée illisible (JSON attendu)") from None
    if not isinstance(x, dict): raise Refus("entrée illisible (objet JSON attendu)")
    return x


def verbe_conversation(args, prive=False):
    if os.environ.get("BERGER_AGENT"): sys.exit("berger conversation : réservé au propriétaire (interface web), jamais à un agent")
    opt = lambda nom: args[args.index(nom) + 1] if nom in args and args.index(nom) + 1 < len(args) else None
    try:
        if args[:1] == ["liste"]:
            binaire, raison = transcription_locale()
            r = {"agents": conversations_ouvertes(), "micro": {"actif": binaire is not None, "raison": raison}}
        elif args[:1] == ["envoyer"] and len(args) >= 2:
            r = envoyer(args[1], opt("--empreinte"), opt("--source") or "?", lire_entree(48 * MIO))
        elif args[:1] == ["transcrire"]:
            r = transcrire(lire_entree(36 * MIO))
        else: return NotImplemented
    except Refus as e: sys.exit(f"refusé : {e}")
    print(json.dumps(r, ensure_ascii=False)); return 0


FAMILLE = "conversation"
VERBES = {"conversation": verbe_conversation}
AIDE = {"conversation": "berger conversation liste|envoyer <agent>|transcrire …   page « Conversation » de l'interface web (propriétaire seul ; même chemin que berger parler)"}
DROITS = {"conversation": {"prive": False, "cas_go": None}}
