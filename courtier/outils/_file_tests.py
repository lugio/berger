# -*- coding: utf-8 -*-
"""La FILE DES TESTS tenue par Berger (lot A de docs/plans/2026-11-04-acceleration-fusions-spec.md) — pas un type d'outil :
partagé par equipe_dev et equipe_chef. Avant de lancer des portes qui jouent la suite (`tests`), le courtier prend son TOUR :

1. un ticket numéroté (ordre d'arrivée) dans l'état du courtier : <installation>/courtier/file-tests/<n>.json ;
2. le plus petit ticket VIVANT passe ; un ticket ORPHELIN (porteur mort : courtier tué) est retiré à la lecture suivante. Un ticket
   est vivant tant que son porteur tient son VERROU (flock sur le fichier du ticket, pris avant qu'il paraisse dans la file) : ni un
   pid repris par un autre processus, ni un pid invisible d'un bac à sable ne trompent ce contrôle (le pid ne sert plus qu'aux
   tickets d'un courtier antérieur, sans verrou) ;
3. il prend alors le verrou des suites — le MÊME flock que tests/suites.sh (fichier `description` de la forge nue) — et le garde
   jusqu'à la fin de la dernière porte ; les suites lancées par la porte en héritent (BERGER_SUITES_VERROU_TENU=1) ;
4. le délai de la porte ne démarre qu'après : l'attente n'est pas comptée ; elle est bornée (2 h), au-delà : refus nommé
   « file des tests : attente dépassée », sans verdict.

Une passe lancée à la main (`bash tests/suites.sh`) prend un ticket dans la MÊME file (mode `manuel` ci-dessous, lancé par suites.sh) :
elle attend son tour comme une demande. Une passe qui ne peut pas ÉCRIRE la file de l'installation (bac à sable) ne prend pas de
ticket mais ne double pas non plus : elle LIT la file et attend qu'elle soit VIDE (aucun ticket : ni en cours, ni en attente) avant
de prendre le verrou — elle passe donc après tous ceux qui attendent ; au-delà de son attente maximale, refus nommé, aucun verdict.
Seule une machine sans installation de Berger (aucune file à doubler) garde le seul verrou des suites.
Pendant l'attente, le marqueur courrier/file/<demande> de l'agent dit à son client (berger-outil) que le délai ne court pas : le
courtier le RAFRAÎCHIT (date de modification) toutes les FRAICHEUR / 4 secondes ; le client ignore un marqueur plus vieux que
FRAICHEUR (courtier arrêté) et ne prolonge jamais l'attente au-delà de ATTENTE_MAX + 10 min."""
import contextlib, datetime, fcntl, json, os, select, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path

ATTENTE_MAX = 7200                                                         # 2 h (spec, lot A point 3)
FRAICHEUR = 120                                                            # s : un marqueur non rafraîchi depuis plus longtemps est ignoré du client
PAS = 1.0
ENV_TENU = {"BERGER_SUITES_VERROU_TENU": "1"}
_ALLOUER = threading.Lock()


class AttenteDepassee(ValueError):
    pass


def installation():
    return Path(os.environ.get("BERGER_DIR") or Path(__file__).resolve().parents[2])


def dossier_file(racine=None):
    return Path(racine or installation()) / "courtier/file-tests"


def vivant(pid):
    """Le processus existe et n'est pas un ZOMBIE : kill(pid, 0) réussit sur un zombie (mort, pas encore récolté par son parent),
    son état se lit dans /proc/<pid>/stat (Z ou X = mort)."""
    try: pid = int(pid); os.kill(pid, 0)
    except ProcessLookupError: return False
    except PermissionError: pass
    except (TypeError, ValueError, OverflowError): return False
    try: etat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError): return True                             # sans /proc : kill seul
    return etat not in ("Z", "X", "x")


def porteur(f):
    """Le porteur du ticket `f` tient-il son verrou ? True (vivant), False (orphelin), None (ticket sans verrou : courtier
    antérieur, ou illisible — seul le pid peut en juger)."""
    try:
        t = json.loads(Path(f).read_text())
        if not (isinstance(t, dict) and t.get("verrouille")): return None
        fd = os.open(f, os.O_RDONLY)
    except (OSError, ValueError): return None
    try:
        try: fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError: return True
        fcntl.flock(fd, fcntl.LOCK_UN); return False
    finally: os.close(fd)


def tickets(d=None):
    """Les tickets VIVANTS, par ordre d'arrivée (les orphelins sont retirés au passage, si la file est inscriptible d'ici ; sinon
    seulement ignorés : jamais une erreur qui bloquerait la file) → [dict]."""
    d = Path(d or dossier_file()); out = []
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        try: t = json.loads(f.read_text())
        except (OSError, ValueError): continue
        if not isinstance(t, dict): continue
        p = porteur(f)
        if p is False or (p is None and not vivant(t.get("pid"))):
            try: f.unlink(missing_ok=True)
            except OSError: pass
            continue
        out.append({**t, "fichier": f})
    return sorted(out, key=lambda t: int(t.get("n", 0)))


def place(sujet, d=None, projet=None):
    """Ce que voient `equipe liste` et `demandes` pour un sujet (d'un projet, si `projet` est donné : deux projets peuvent avoir le
    même sujet) : « en cours (<sujet>, depuis HH:MM) », « en file (2e, derrière <sujet>) », ou None s'il n'est pas dans la file."""
    l = tickets(d)
    for i, t in enumerate(l):
        if t.get("sujet") != sujet or (projet is not None and t.get("projet") != projet): continue
        if t.get("etat") == "en cours": return f"en cours ({sujet}, depuis {str(t.get('debut', ''))[11:16]})"
        return f"en file ({i + 1}e, derrière {l[i - 1].get('sujet')})" if i else "en file (1er, attend le verrou des suites)"
    return None


def verrou_suites(depot):
    """Le fichier verrouillé par tests/suites.sh : `description` du dépôt NU de la forge, remonté d'origine en origine (puis par les
    alternates) depuis `depot`, six maillons au plus. Introuvable (aucune forge locale) : None — le courtier verrouille alors son
    propre fichier (la file reste unique entre ses portes)."""
    d = Path(depot)
    for _ in range(6):
        if not d.is_dir(): return None
        r = subprocess.run(["git", "-C", str(d), "rev-parse", "--is-bare-repository"], capture_output=True, text=True)
        if r.stdout.strip() == "true":
            f = d / "description"
            return f if f.is_file() and not f.is_symlink() else None
        o = subprocess.run(["git", "-C", str(d), "config", "--get", "remote.origin.url"], capture_output=True, text=True).stdout.strip()
        o = o.removeprefix("file://")
        if not o:
            g = subprocess.run(["git", "-C", str(d), "rev-parse", "--absolute-git-dir"], capture_output=True, text=True).stdout.strip()
            try: a = (Path(g) / "objects/info/alternates").read_text().splitlines()[0].strip()
            except (OSError, IndexError): return None
            d = (Path(g) / "objects" / a).parent if not a.startswith("/") else Path(a).parent; continue
        if "://" in o or (":" in o and not o.startswith(("/", "."))): return None
        d = Path(o) if o.startswith("/") else d / o
    return None


def allouer(d, champs):
    """Un numéro de ticket, jamais deux fois le même : sous un verrou FICHIER (d/.allouer, flock) que partagent tous les chargements
    du module (equipe_dev et equipe_chef chargés séparément, une passe manuelle). Le ticket est écrit et VERROUILLÉ (flock exclusif)
    sous un nom provisoire, puis lié à son nom définitif (link : échoue s'il existe, nouvel essai) : il ne paraît dans la file que
    complet et tenu. Le porteur garde le descripteur ouvert tant qu'il est dans la file ; le fermer (ou mourir) en fait un orphelin.
    → (n, chemin, ticket, descripteur verrouillé)."""
    with _ALLOUER, open(os.open(d / ".allouer", os.O_WRONLY | os.O_CREAT, 0o600), "w") as v:
        fcntl.flock(v, fcntl.LOCK_EX)
        tmp = d / f".ticket-{os.getpid()}-{threading.get_ident()}.tmp"; tmp.unlink(missing_ok=True)
        fd = os.open(tmp, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            for _ in range(100):
                n = max([int(f.stem) for f in d.glob("*.json") if f.stem.isdigit()] + [0]) + 1
                f = d / f"{n:08d}.json"; t = {"n": n, **champs, "verrouille": 1}
                os.ftruncate(fd, 0); os.pwrite(fd, json.dumps(t, ensure_ascii=False).encode(), 0)
                try: os.link(tmp, f)
                except FileExistsError: continue
                return n, f, t, fd
        except BaseException:
            os.close(fd); raise
        finally:
            tmp.unlink(missing_ok=True)
        os.close(fd)
    raise RuntimeError(f"file des tests : aucun numéro de ticket libre dans {d}")


@contextlib.contextmanager
def tour(sujet, depot, agent=None, projet=None, marqueur=None, attente_max=None, racine=None, verrou=None, manuelle=False):
    """Le tour des tests : ticket, attente (bornée) d'être le premier vivant ET d'avoir le verrou, puis le verrou tenu pendant le
    bloc ; ticket retiré et verrou relâché en sortant, quoi qu'il arrive. marqueur : Path du marqueur d'attente de l'agent (créé
    pendant l'attente, retiré dès le verrou obtenu). → (cède) le dict du ticket. AttenteDepassee au-delà de attente_max."""
    d = dossier_file(racine); d.mkdir(parents=True, exist_ok=True)
    attente_max = ATTENTE_MAX if attente_max is None else attente_max
    chemin = Path(verrou) if verrou else (verrou_suites(depot) or d / "verrou")
    n, f, t, tenu = allouer(d, {"sujet": sujet, "agent": agent, "projet": projet, "pid": os.getpid(), "etat": "en file",
                          "depuis": datetime.datetime.now().isoformat(timespec="seconds"), "verrou": str(chemin), **({"manuelle": True} if manuelle else {})})
    v = None; t0 = time.monotonic()
    try:
        if marqueur:
            try: Path(marqueur).parent.mkdir(exist_ok=True); Path(marqueur).write_text(json.dumps({"file": n}))
            except OSError: marqueur = None
        v = os.open(chemin, os.O_RDONLY) if chemin.exists() else os.open(chemin, os.O_RDONLY | os.O_CREAT, 0o600)
        frais = time.monotonic()
        while True:
            if marqueur and time.monotonic() - frais >= FRAICHEUR / 4:     # le client sait ainsi que le courtier attend toujours
                try: os.utime(marqueur)
                except OSError: pass
                frais = time.monotonic()
            premier = next(iter(tickets(d)), None)
            if premier and premier["n"] == n:
                try: fcntl.flock(v, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                except BlockingIOError: pass                                # une passe à la main, ou une autre installation
            if time.monotonic() - t0 > attente_max:
                raise AttenteDepassee(f"file des tests : attente dépassée ({f'{int(attente_max // 60)} min' if attente_max >= 120 else f'{attente_max:g} s'} sans tour) — aucun verdict inscrit, "
                                      f"relance quand la file est libre (equipe liste)")
            time.sleep(PAS)
        t.update(etat="en cours", debut=datetime.datetime.now().isoformat(timespec="seconds"))
        f.write_text(json.dumps(t, ensure_ascii=False))
        if marqueur: Path(marqueur).unlink(missing_ok=True); marqueur = None
        yield t
    finally:
        if marqueur: Path(marqueur).unlink(missing_ok=True)
        f.unlink(missing_ok=True); os.close(tenu)                         # ticket retiré, puis son verrou relâché
        if v is not None:
            try: fcntl.flock(v, fcntl.LOCK_UN)
            finally: os.close(v)


def _creation(racine):
    """Verrou de CRÉATION des copies figées (racine/.creation) : une copie naît et se verrouille sous lui, le nettoyage le prend aussi —
    il ne voit donc jamais une copie créée mais pas encore tenue."""
    racine.mkdir(parents=True, exist_ok=True)
    v = open(os.open(racine / ".creation", os.O_WRONLY | os.O_CREAT, 0o600), "w"); fcntl.flock(v, fcntl.LOCK_EX); return v


def creer_copie(prefixe, racine=None):
    """Un dossier neuf pour une copie figée, déjà TENU par son verrou d'usage (flock sur le dossier) jusqu'à la fermeture du
    descripteur rendu. → (dossier, descripteur)."""
    racine = Path(racine or installation() / "courtier/portes-figees")
    with _creation(racine):
        d = Path(tempfile.mkdtemp(prefix=prefixe, dir=racine)); fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
        try: fcntl.flock(fd, fcntl.LOCK_EX); return d, fd
        except BaseException: os.close(fd); shutil.rmtree(d, ignore_errors=True); raise


def nettoyer_figees(racine=None):
    """Au démarrage du courtier : efface les copies figées ORPHELINES de <installation>/courtier/portes-figees (courtier tué pendant
    des portes : son `finally` n'a pas couru). Jamais une copie en usage : son verrou est tenu. → [noms effacés]."""
    racine = Path(racine or installation() / "courtier/portes-figees"); fait = []
    if not racine.is_dir(): return fait
    with _creation(racine):
        for c in sorted(racine.iterdir()):
            try:
                if c.is_symlink() or not c.is_dir(): continue
                fd = os.open(c, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            except OSError: continue
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                shutil.rmtree(c, ignore_errors=True); fait.append(c.name)
            except BlockingIOError: pass
            finally: os.close(fd)
    return fait


def avec_tests(portes):
    """Les portes à jouer passent-elles par la file ? Oui dès que `tests` (complète ou courte) est une COMMANDE locale."""
    return isinstance(portes, dict) and isinstance(portes.get("tests"), tuple) and portes["tests"][0] == "commande"


def installation_partagee():
    """L'installation de Berger dont la file est commune : BERGER_DIR, sinon celle de la commande `berger` du PATH, sinon ~/berger. → Path ou None."""
    if os.environ.get("BERGER_DIR"): return Path(os.environ["BERGER_DIR"])
    b = shutil.which("berger")
    if b: return Path(b).resolve().parents[1]
    m = Path.home() / "berger"
    return m if (m / "bin/berger").is_file() else None


def manuel(verrou, attente, entree=0, sortie=None):
    """Mode `manuel` (lancé par tests/suites.sh pour une passe à la main) : un ticket « passe manuelle » dans la file de l'installation,
    le tour attendu dans l'ordre, puis « TOUR » écrit sur la sortie et le verrou des suites TENU jusqu'à la fin de suites.sh (fin de
    son entrée, ou suites.sh disparu). « SANS-FILE <raison> » : aucune installation de Berger sur la machine (aucune file à doubler) —
    suites.sh garde alors son seul verrou. « REFUS <motif> » : attente dépassée — passe NON JOUÉE. File non inscriptible
    d'ici (bac à sable) : derriere_la_file. → code de retour."""
    sortie = sortie or sys.stdout
    dire = lambda x: (sortie.write(x + "\n"), sortie.flush())
    inst = installation_partagee()
    if inst is None:
        dire("SANS-FILE aucune installation de Berger sur cette machine (BERGER_DIR, commande berger, ~/berger) : aucune file à doubler"); return 0
    d = dossier_file(inst)
    try:
        d.mkdir(parents=True, exist_ok=True)
        if not os.access(d, os.W_OK | os.X_OK): raise OSError("non inscriptible")
    except OSError as e:
        return derriere_la_file(d, verrou, attente, f"{d} : {e.strerror or e}", dire, entree)
    parent = os.getppid()
    try:
        with tour("passe manuelle", None, agent=os.environ.get("USER") or "inconnu", racine=inst, verrou=verrou, attente_max=attente, manuelle=True):
            dire("TOUR")
            while os.getppid() == parent:
                if select.select([entree], [], [], 1.0)[0] and not os.read(entree, 4096): break
    except AttenteDepassee as e:
        dire(f"REFUS {e}"); return 1
    except OSError as e:
        dire(f"REFUS file des tests inutilisable ({e}) : passe NON JOUÉE"); return 1
    return 0


def derriere_la_file(d, verrou, attente, raison, dire, entree=0):
    """Passe manuelle qui ne peut pas écrire la file (bac à sable) : sans ticket, elle passe quand la file est VIDE, et le constat
    est ATOMIQUE avec la prise du verrou : verrou des suites pris D'ABORD, file lue ENSUITE en le tenant ; un ticket présent → verrou
    relâché, nouvel essai. Un ticket arrivé après ce constat attend donc la fin de la passe, et aucun ne peut se glisser entre la
    lecture et le verrou. Un ticket compte tant que son porteur tient son verrou (un orphelin ne bloque pas) ; un ticket sans
    verrou (courtier antérieur) compte tant que son fichier existe : son processus n'est pas forcément visible d'ici. Le verrou
    est tenu jusqu'à la fin de suites.sh. Au-delà de `attente` : REFUS nommé. → code de retour."""
    t0 = time.monotonic(); parent = os.getppid(); v = None
    try:
        v = os.open(verrou, os.O_RDONLY)
        while True:
            try: fcntl.flock(v, fcntl.LOCK_EX | fcntl.LOCK_NB); tenu = True
            except BlockingIOError: tenu = False
            if tenu:
                if not (d.is_dir() and any(porteur(f) is not False for f in d.glob("*.json"))): break
                fcntl.flock(v, fcntl.LOCK_UN)
            if time.monotonic() - t0 > attente:
                dire(f"REFUS passe manuelle sans ticket ({raison} — bac à sable ?) : la file des tests n'a pas été vide pendant {int(attente)} s "
                     "— lance la porte « tests » de ton outil (berger-outil <projet>-dev tests), le courtier y prend ton ticket"); return 1
            time.sleep(PAS)
        dire("TOUR sans ticket (file non inscriptible d'ici : passée après toute la file)")
        while os.getppid() == parent:
            if select.select([entree], [], [], 1.0)[0] and not os.read(entree, 4096): break
        return 0
    except OSError as e:
        dire(f"REFUS verrou des suites inutilisable ({e}) : passe NON JOUÉE"); return 1
    finally:
        if v is not None: os.close(v)


if __name__ == "__main__":                                                 # python3 -I _file_tests.py manuel <verrou> <attente en s>
    if len(sys.argv) != 4 or sys.argv[1] != "manuel" or not sys.argv[3].isdigit():
        print("usage : _file_tests.py manuel <verrou> <attente en secondes>", file=sys.stderr); sys.exit(2)
    sys.exit(manuel(sys.argv[2], int(sys.argv[3])))
