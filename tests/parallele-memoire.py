#!/usr/bin/env python3
"""Protection de la RAM par le lanceur de suites (renvoi de la n° 71, 29/10/2026 ; exigence du propriétaire : ne jamais saturer la machine).
  1. par défaut UNE suite à la fois ; BERGER_SUITES_PARALLELE n'accepte qu'un entier de 1 à 4, tout le reste (0, négatif, texte, 999999,
     9223372036854775808, 5 000 chiffres…) est un refus nommé ramené à 1, côté shell ET côté Python, sans exception ni boucle sans fin ;
  2. verrou GLOBAL (flock) : un seul tests/suites.sh à la fois sur la machine ; le suivant attend (message) ou s'arrête sans verdict vert ;
     le lanceur qui le détient ne se bloque pas lui-même (rejeu de herdr-fuite.py, suite seule jouée par une suite) ;
  3. l'ordonnanceur (extrait de suites.sh, suites factices) : jamais plus de n suites à la fois, une suite « à part » seule (même placée en
     tête ET à part), attente de PID explicites, délai maximal par suite, suite morte sans « fin » comptée en échec, descendants tués
     (TERM puis KILL), aussi pour le rejeu de herdr-fuite.py (tests/_parallele.py) ;
  4. la mesure de mémoire d'une suite (tests/_mesure_mem.py) ;
  5. la preuve Herdr sur TOUTES les suites, faite par suites.sh à leur passage normal (environnement hostile, un socket témoin par suite et par
     chemin) : une suite témoin qui s'y connecte fait échouer la passe, au nom de cette suite ; sans sockets (bac à sable) : NON JOUÉ.
Le test respecte le plafond qu'on lui donne : il ne joue jamais plus de suites factices à la fois que BERGER_SUITES_PARALLELE (1 par défaut).
Usage : python3 tests/parallele-memoire.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import fcntl, re, shutil, signal, socket, subprocess, sys, tempfile, time
from pathlib import Path

import _parallele
from _parallele import parallele

T = Path(__file__).resolve().parent
SRC = T.parent
SUITES_SH = (T / "suites.sh").read_text()
ko = 0
ENV = {"PATH": _os.environ["PATH"]}


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def bloc(debut, fin):
    m = re.search(debut + r".*?(?=" + fin + ")", SUITES_SH, re.S | re.M)
    return m.group(0) if m else ""


def bash(script, env=None, timeout=60):
    return subprocess.run(["bash", "-c", script], env={**ENV, **(env or {})}, capture_output=True, text=True, timeout=timeout)


PLAFOND = parallele()          # le plafond donné à CE test (BERGER_SUITES_PARALLELE du lanceur, 1 par défaut)
with tempfile.TemporaryDirectory(prefix="pm") as t:
    t = Path(t)
    ordonnanceur = bloc(r"^_sf=\(\)", r"^# SUITE_SEULE=")
    dire("_jouer_les_suites()" in ordonnanceur and "_verrou_global()" in ordonnanceur and "_parallele_choisi()" in ordonnanceur,
         "l'ordonnanceur, le verrou et la règle du nombre sont extraits de suites.sh")

    # 1. le nombre de suites à la fois : 1 par défaut, 1 à 4 sinon refus nommé, côté shell ET côté Python
    sans = bash(ordonnanceur + "\n_parallele_choisi")
    dire(sans.stdout.strip() == "1" and not sans.stderr.strip() and parallele(env={}) == 1, f"par défaut : 1 suite à la fois (shell={sans.stdout.strip()}, Python={parallele(env={})})")
    for v in "1234":
        sh = bash(ordonnanceur + "\n_parallele_choisi", {"BERGER_SUITES_PARALLELE": v})
        dire(sh.stdout.strip() == v and parallele(env={"BERGER_SUITES_PARALLELE": v}) == int(v) and not sh.stderr.strip(), f"BERGER_SUITES_PARALLELE={v} accepté (shell={sh.stdout.strip()})")
    invalides = ["0", "-1", "abc", "5", "999999", "9223372036854775808", "1" * 5000, "2.5", " 2", "2 ", "02", "+2", "1;2", "$(id)"]
    for v in invalides:
        nom = v if len(v) < 30 else f"{v[:6]}… ({len(v)} caractères)"
        try:
            sh = bash(ordonnanceur + "\n_parallele_choisi", {"BERGER_SUITES_PARALLELE": v}, timeout=20)
            py_n, py_msg = parallele(env={"BERGER_SUITES_PARALLELE": v}), _parallele.refus(env={"BERGER_SUITES_PARALLELE": v})
            bon = sh.stdout.strip() == "1" and "BERGER_SUITES_PARALLELE" in sh.stderr and "refusé" in sh.stderr and py_n == 1 and py_msg and "refusé" in py_msg
            dire(bon, f"valeur invalide « {nom} » : refus nommé, ramené à 1 (shell={sh.stdout.strip()!r}, Python={py_n})")
        except Exception as e:   # une exception ou un blocage est exactement ce qui est interdit
            dire(False, f"valeur invalide « {nom} » : exception ou blocage ({type(e).__name__})")

    # 2. le verrou global : un fichier EXISTANT, ouvert en LECTURE SEULE (flock verrouille l'inode : valable d'un bac à sable à l'autre)
    verrou = t / "berger-suites.lock"; verrou.write_text(""); verrou.chmod(0o444)
    appel = ordonnanceur + "\n_verrou_global; echo \"rc=$? tenu=$BERGER_SUITES_VERROU_TENU\""
    venv = {"BERGER_SUITES_VERROU": str(verrou), "BERGER_SUITES_ATTENTE": "2"}
    r = bash(appel, venv)
    dire("rc=0 tenu=1" in r.stdout, f"verrou libre (fichier en lecture seule) : pris, le lanceur le signale à ses descendants ({r.stdout.strip()})")
    tenu = open(verrou, "rb"); fcntl.flock(tenu, fcntl.LOCK_EX)           # une autre passe de tests tient le verrou (descripteur en lecture seule)
    t0 = time.time(); r = bash(appel, venv); dt = time.time() - t0
    dire("rc=1" in r.stdout and "j'attends mon tour" in r.stderr and "NON JOUÉE" in r.stderr and 1.5 < dt < 15,
         f"verrou pris par une autre passe : message d'attente, puis arrêt sans verdict ({dt:.1f} s) : {r.stderr.strip()[-120:]}")
    r = bash(appel, {**venv, "BERGER_SUITES_VERROU_TENU": "1"})
    dire("rc=0" in r.stdout, "rejeu : un descendant du lanceur qui tient le verrou ne se bloque pas lui-même (suite seule jouée par une suite)")
    fcntl.flock(tenu, fcntl.LOCK_UN); tenu.close()
    r = bash(appel, {**venv, "BERGER_SUITES_ATTENTE": "20"})
    dire("rc=0" in r.stdout, "verrou relâché : la passe suivante le prend")
    autre = subprocess.Popen([sys.executable, "-c", f"import fcntl,time; f=open({str(verrou)!r},'rb'); fcntl.flock(f,2); print('tenu',flush=True); time.sleep(2)"], stdout=subprocess.PIPE, text=True)
    autre.stdout.readline(); t0 = time.time(); r = bash(appel, {**venv, "BERGER_SUITES_ATTENTE": "20"}); dt = time.time() - t0; autre.wait()
    dire("rc=0" in r.stdout and "j'attends mon tour" in r.stderr and dt < 15, f"la passe qui attend reprend dès que l'autre finit ({dt:.1f} s)")
    # le descripteur du verrou est DYNAMIQUE : tests/tout.sh tient .tout.verrou sur le descripteur 9 et inclut suites.sh — exec 9<… le lui aurait volé
    tout_verrou = t / ".tout.verrou"
    script9 = (f"exec 9>{tout_verrou}; flock -n 9 || exit 3\n" + ordonnanceur +
               "\n_verrou_global; echo \"rc=$? fd=${_verrou_fd:-aucun}\"; echo pret; sleep 4\n")
    h9 = subprocess.Popen(["bash", "-c", script9], env={**ENV, **venv}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lignes9 = []
    while True:
        l = h9.stdout.readline()
        if not l or l.strip() == "pret": break
        lignes9.append(l.strip())
    f9 = open(tout_verrou, "rb")
    try: fcntl.flock(f9, fcntl.LOCK_EX | fcntl.LOCK_NB); tenu9 = False
    except OSError: tenu9 = True
    finally: f9.close()
    h9.wait(timeout=30)
    dire(tenu9 and "rc=0" in " ".join(lignes9) and "fd=9" not in " ".join(lignes9),
         f"le verrou de tout.sh (descripteur 9, .tout.verrou) reste tenu pendant suites.sh, qui prend un autre descripteur ({' '.join(lignes9)} ; tenu {tenu9})")

    # herdr-fuite.py lancée SEULE : sa sonde copie le lanceur dans un temporaire sans .git ; sans verrou jetable, « forge locale introuvable » et la sonde ne tourne pas
    seul = subprocess.run([sys.executable, str(T / "herdr-fuite.py")], env={**ENV, "TMPDIR": str(t)}, capture_output=True, text=True, timeout=300)
    dire(seul.returncode == 0 and re.search(r"^ok +lanceur : faux Herdr imposé", seul.stdout, re.M) and "ÉCHEC" not in seul.stdout,
         f"herdr-fuite.py lancée SEULE : la sonde du lanceur tourne et réussit (code {seul.returncode}) {seul.stdout[-250:]!r}")

    # le chemin PAR DÉFAUT : le fichier « description » du dépôt d'origine (forge locale), le MÊME inode pour toutes les copies, jamais réécrit
    def git(*a, cwd=None):
        return subprocess.run(["git", "-c", "user.name=essai", "-c", "user.email=essai@exemple.invalid", *a], cwd=cwd, capture_output=True, text=True)

    def inode(chemin): return _os.stat(chemin).st_ino
    forge = t / "forge.git"; git("init", "-q", "--bare", str(forge)); copies = []
    for nom in ("copie1", "copie2"):
        git("clone", "-q", str(forge), str(t / nom)); copies.append(t / nom)
    chemins = [bash(ordonnanceur + f"\nB={c}; _verrou_chemin") for c in copies]
    dire(all(c.returncode == 0 for c in chemins) and chemins[0].stdout == chemins[1].stdout and chemins[0].stdout.strip() == str(forge / "description"),
         f"deux copies du même projet verrouillent le MÊME fichier : la description du dépôt d'origine ({chemins[0].stdout.strip()[-30:]})")
    avant = inode(forge / "description"); avant_head = inode(forge / "HEAD"); avant_config = inode(forge / "config")
    git("commit", "-q", "--allow-empty", "-m", "x", cwd=copies[0]); git("push", "-q", "origin", "HEAD:main", cwd=copies[0]); git("fetch", "-q", cwd=copies[1])
    git("gc", "-q", cwd=forge); git("config", "core.essai", "oui", cwd=forge); git("symbolic-ref", "HEAD", "refs/heads/main", cwd=forge); git("repack", "-adq", cwd=forge)
    dire(inode(forge / "description") == avant, "push, fetch, gc, repack, config et symbolic-ref ne réécrivent JAMAIS la description (même inode : le verrou tient)")
    dire(inode(forge / "HEAD") != avant_head and inode(forge / "config") != avant_config,
         "témoin : HEAD et config, eux, changent d'inode (réécrits par renommage) — c'est pourquoi ils ne portent pas le verrou")
    # le même inode vu par deux copies : la prise d'un descripteur par l'une est vue par l'autre
    tenu = open(forge / "description", "rb"); fcntl.flock(tenu, fcntl.LOCK_EX)
    r = bash(ordonnanceur + f"\nB={copies[1]}; _verrou_global; echo \"rc=$?\"", {"BERGER_SUITES_ATTENTE": "2"})
    dire("rc=1" in r.stdout and "NON JOUÉE" in r.stderr, "le verrou tenu pour la copie 1 est vu par la copie 2 (même inode)")
    fcntl.flock(tenu, fcntl.LOCK_UN); tenu.close()
    # introuvable ou non verrouillable : NON JOUÉE, jamais un repli qui ne sérialiserait rien
    (forge / "description").rename(forge / "description.ailleurs")
    r = bash(ordonnanceur + f"\nB={copies[0]}; _verrou_global; echo \"rc=$?\"")
    dire("rc=1" in r.stdout and "introuvable" in r.stderr and "NON JOUÉE" in r.stderr and "berger-suites-" not in r.stderr,
         "forge locale sans fichier de verrou : passe NON JOUÉE, aucun repli sur /tmp")
    (forge / "description.ailleurs").rename(forge / "description")
    inutilisable = t / "inutilisable.lock"; inutilisable.write_text(""); inutilisable.chmod(0)
    r = bash(appel, {"BERGER_SUITES_VERROU": str(inutilisable)})
    dire("rc=1" in r.stdout and "NON JOUÉE" in r.stderr and "illisible" in r.stderr, "fichier de verrou illisible : passe NON JOUÉE")
    absent = bash(appel, {"BERGER_SUITES_VERROU": str(t / "n-existe-pas.lock")})
    dire("rc=1" in absent.stdout and "introuvable" in absent.stderr, "chemin imposé inexistant : passe NON JOUÉE (rien n'est créé en silence)")
    # dépôt sans forge locale (clone public, sans remote) : seul cas d'un verrou /tmp, dit
    nu = t / "public"; nu.mkdir(); git("init", "-q", str(nu)); git("remote", "add", "origin", "https://exemple.invalid/berger.git", cwd=nu)
    publique = bash(ordonnanceur + f"\nB={nu}; _verrou_chemin")
    dire(publique.returncode == 2 and publique.stdout.strip().startswith("/tmp/berger-suites-") and "sans forge locale" in publique.stderr,
         "dépôt sans forge locale (origine https) : verrou /tmp, propre à la machine, dit à l'écran")
    sans_remote = t / "sans-remote"; sans_remote.mkdir(); git("init", "-q", str(sans_remote))
    sr = bash(ordonnanceur + f"\nB={sans_remote}; _verrou_chemin")
    dire(sr.returncode == 2 and "sans forge locale" in sr.stderr, "dépôt sans aucune origine : verrou /tmp, dit")

    # le chef rejoue dans un clone de SON dépôt de travail (git clone --shared, origine = ce dépôt, lui-même cloné de la forge) : même fichier
    def chemin(b_):
        return bash(ordonnanceur + f"\nB={b_}; _verrou_chemin")
    travail = t / "travail-du-chef"; git("clone", "-q", str(forge), str(travail))
    rejeu = t / "rejeu-du-chef"; git("clone", "-q", "--shared", "--no-checkout", str(travail), str(rejeu))
    cr = chemin(rejeu)
    dire(cr.returncode == 0 and cr.stdout.strip() == str(forge / "description") and inode(cr.stdout.strip()) == inode(forge / "description"),
         f"rejeu du chef (clone --shared du dépôt de travail) : remonte jusqu'à la forge nue, MÊME fichier que le développeur ({cr.stdout.strip()[-25:]}, code {cr.returncode})")
    (rejeu / ".git/config").write_text((rejeu / ".git/config").read_text().replace("url = ", "url = file://"))     # origine en file:///
    cf = chemin(rejeu)
    dire(cf.returncode == 0 and cf.stdout.strip() == str(forge / "description"), "origine file:///… : reconnue comme locale et résolue (pas un clone public)")
    sans_origine = t / "alternates-seules"; git("clone", "-q", "--shared", "--no-checkout", str(travail), str(sans_origine)); git("remote", "remove", "origin", cwd=sans_origine)
    ca = chemin(sans_origine)
    dire(ca.returncode == 0 and ca.stdout.strip() == str(forge / "description"), "sans origine mais avec alternates : remonte par les alternates jusqu'à la forge")
    # origine locale qui ne mène à aucune description verrouillable : NON JOUÉE (jamais un repli sur /tmp)
    cassee = t / "cassee"; git("clone", "-q", str(forge), str(cassee)); git("remote", "set-url", "origin", "file://" + str(t / "disparue.git"), cwd=cassee)
    r = bash(ordonnanceur + f"\nB={cassee}; _verrou_global; echo \"rc=$?\"")
    dire("rc=1" in r.stdout and "NON JOUÉE" in r.stderr and "sans forge locale" not in r.stderr and "berger-suites-" not in r.stderr,
         "origine file:// vers un dépôt disparu : passe NON JOUÉE, jamais traitée en clone public")
    c2 = bash(ordonnanceur + f"\nB={cassee}; _verrou_chemin")
    dire(c2.returncode == 1, "origine locale inaccessible : _verrou_chemin répond « introuvable » (code 1), pas « verrou /tmp » (code 2)")
    # profondeur bornée et boucle : NON JOUÉE, sans boucle sans fin
    chaine = forge
    for i in range(8):
        suivant = t / f"maillon{i}"; git("clone", "-q", str(chaine), str(suivant)); chaine = suivant
    cp = bash(ordonnanceur + f"\nB={chaine}; _verrou_chemin", timeout=30)
    dire(cp.returncode == 1, f"chaîne de 8 origines (au-delà de la profondeur permise) : introuvable, sans boucle sans fin (code {cp.returncode})")
    a_ = t / "boucle-a"; b_ = t / "boucle-b"; git("init", "-q", str(a_)); git("init", "-q", str(b_))
    git("remote", "add", "origin", str(b_), cwd=a_); git("remote", "add", "origin", str(a_), cwd=b_)
    cb = bash(ordonnanceur + f"\nB={a_}; _verrou_chemin", timeout=30)
    dire(cb.returncode == 1, f"origines en boucle : introuvable, sans boucle sans fin (code {cb.returncode})")

    # d'un bac à sable à l'autre : placer exprès le verrou sous /tmp, comme un clone frais de CI.
    # Son inode seul est remonté après le tmpfs privé ; on exige la CONTENTION (« j'attends mon tour » puis « toujours pris »), pas « introuvable » qui passerait pour une preuve
    partage = t / f".verrou-essai-{_os.getpid()}"; partage.write_text(""); partage.chmod(0o444)
    try:
        cenv = {"BERGER_SUITES_VERROU": str(partage), "BERGER_SUITES_ATTENTE": "2"}
        tenu = open(partage, "rb"); fcntl.flock(tenu, fcntl.LOCK_EX)
        def contention(prefixe):
            r = subprocess.run([*prefixe, "bash", "-c", appel], env={**ENV, **cenv}, capture_output=True, text=True, timeout=60)
            return "rc=1" in r.stdout and "j'attends mon tour" in r.stderr and "toujours pris" in r.stderr and "introuvable" not in r.stderr, r
        ok_, r = contention([])
        dire(ok_, f"contention vérifiée (sans bac) : message d'attente puis « toujours pris », jamais « introuvable » : {r.stderr.strip()[-110:]}")
        bw = subprocess.run(["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--unshare-pid", "true"], capture_output=True)
        if bw.returncode == 0:
            # Le fichier seul reste visible, même quand le clone de la CI est sous /tmp.
            ok_, r = contention(["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--ro-bind", str(partage), str(partage), "--unshare-pid"])
            dire(ok_, f"deux bacs à sable (bwrap, /tmp privés) : la CONTENTION du verrou tenu hors du bac est vue de l'intérieur : {r.stderr.strip()[-110:]}")
        else:
            print("NON JOUÉ bwrap imbriqué impossible ici : exclusion d'un bac à sable à l'autre prouvée à la main le 29/10 (docs/plans/archive/2026-10-29-portes-serialisees-spec.md)")
        fcntl.flock(tenu, fcntl.LOCK_UN); tenu.close()
    finally:
        partage.unlink(missing_ok=True)
    # le vrai script : une suite seule jouée par une suite (SUITE_SEULE), copie jetable de suites.sh et suite triviale (pas une suite du dépôt)
    (t / "seul/tests").mkdir(parents=True); (t / "seul/tests/suites.sh").write_text(SUITES_SH); (t / "seul/tests/triv.py").write_text("print('ok    un contrôle')\n")
    reel = {**venv, "SUITE_SEULE": "triv.py", "TMPDIR": str(t)}
    tenu = open(verrou, "rb"); fcntl.flock(tenu, fcntl.LOCK_EX)
    r = subprocess.run(["bash", str(t / "seul/tests/suites.sh")], env={**ENV, **reel, "BERGER_SUITES_VERROU_TENU": "1"}, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0 and re.search(r"^ok ", r.stdout, re.M), f"suites.sh réel, verrou tenu par le lanceur : la suite seule se joue (code {r.returncode})")
    r = subprocess.run(["bash", str(t / "seul/tests/suites.sh")], env={**ENV, **reel}, capture_output=True, text=True, timeout=120)
    dire(r.returncode != 0 and "NON JOUÉE" in r.stderr and not re.search(r"^ok ", r.stdout, re.M), f"suites.sh réel, verrou pris par une autre passe : arrêt sans aucune ligne verte (code {r.returncode})")
    fcntl.flock(tenu, fcntl.LOCK_UN); tenu.close()

    # 3. l'ordonnanceur réel (extrait de suites.sh), suites factices, jamais plus que le plafond donné à ce test
    (t / "tests").mkdir(); journal = t / "journal"
    corps = ("import os, sys, time\nj = %r\nnom = os.path.basename(sys.argv[0])\n"
             "open(j, 'a').write(f'debut {nom} {time.time()}\\n'); time.sleep(%s); open(j, 'a').write(f'fin {nom} {time.time()}\\n')\n")
    for i in range(10): (t / f"tests/s{i}.py").write_text(corps % (str(journal), "0.6"))
    for nom in ("solo", "tete"): (t / f"tests/{nom}.py").write_text(corps % (str(journal), "0.6"))   # « tete » : en tête ET à part, comme herdr-fuite.py

    (t / "v.lock").write_text("")     # le fichier de verrou imposé aux passes factices : il doit exister (jamais créé en silence)
    (t / "py").mkdir(); (t / "py/python3").symlink_to(_os.path.realpath(sys.executable))   # un python3 réel en tête du PATH : sous un HOME jetable, un raccourci mise échoue

    def passe(n, declarations, delai="60", extra=None, timeout=120):
        journal.write_text("")
        script = ("dire() { [ \"$1\" = ok ] || ko=$((ko+1)); echo \"$1 $4\"; }; ko=0; _bt=''; _pyd=''; _sans_herdr=(); _faux_herdr=/bin/false; _herdr_absent=%s/absent.sock; _path_suites=\"$PATH\"\n"
                  "declare -A _a_part=(); declare -A _delai_suite=(); _a_part[solo.py]=x; _a_part[tete.py]=x; _en_tete=(tete.py); B=%s\n" % (t, t) + ordonnanceur +
                  "\n" + declarations + "\n_jouer_les_suites; echo \"ko=$ko\"; for i in \"${!_sf[@]}\"; do echo \"verdict ${_sf[$i]}\"; done\n")
        env = {"PATH": f"{t}/py:{ENV['PATH']}", "TMPDIR": str(t), "BERGER_SUITES_PARALLELE": str(n), "BERGER_SUITES_VERROU": str(t / "v.lock"), "BERGER_SUITE_DELAI": delai, **(extra or {})}
        return bash(script, env, timeout)

    liste = "suite tete.py tete ''; for i in 0 1 2 3 4 5 6 7 8 9; do suite s$i.py s$i ''; done; suite solo.py solo ''"
    for n in range(1, min(3, PLAFOND) + 1):
        r = passe(n, liste)
        evts = sorted((float(l.split()[2]), 1 if l.startswith("debut") else -1, l.split()[1]) for l in journal.read_text().splitlines())
        en_cours, maxi, seule_ok, actifs = 0, 0, True, set()
        for _, sens, nom in evts:
            en_cours += sens; maxi = max(maxi, en_cours)
            if sens == 1:
                actifs.add(nom)
                if nom in ("solo.py", "tete.py") and len(actifs) > 1: seule_ok = False
                if ({"solo.py", "tete.py"} & actifs) and nom not in ("solo.py", "tete.py"): seule_ok = False
            else: actifs.discard(nom)
        dire(len(evts) == 24 and r.returncode == 0 and "ko=0" in r.stdout and maxi <= n, f"n={n} : {len(evts) // 2} suites jouées, jamais plus de {n} à la fois (maximum vu : {maxi}) {r.stderr[-200:]}")
        dire(seule_ok, f"n={n} : les suites « à part » (dont celle placée aussi en tête, jouée UNE fois) tournent seules")

    # délai maximal, suite morte sans « fin », descendants tués — y compris ceux qui CHANGENT DE SESSION — à n=1 (suites factices, aucune mémoire).
    # Chaque suite factice lance un témoin « exec -a <nom> sleep 300 » (un sleep avec un mot en trop échouait aussitôt : tests faussement verts)
    # et écrit son PID seulement s'il est VIVANT : contrôle positif, puis on exige qu'il soit mort à la fin.
    def lire_pid(nom):
        f = t / f"pid-{nom}"
        return int(f.read_text()) if f.exists() and f.read_text().strip().isdigit() else None

    def vivant(pid):
        try: _os.kill(pid, 0); return True
        except OSError: return False

    def temoin(nom, session, quitte=False):
        return ("import os, signal, subprocess, time\np = subprocess.Popen(['bash', '-c', 'exec -a %s-temoin-pm sleep 300'], start_new_session=%s)\ntime.sleep(0.5)\n"
                "open(%r, 'w').write(str(p.pid) if p.poll() is None else 'MORT')\n%stime.sleep(300)\n") % (nom, session, str(t / f"pid-{nom}"),
                                                                                                    "os.kill(os.getppid(), signal.SIGKILL)\n" if quitte else "")
    (t / "tests/bloque.py").write_text(temoin("bloque", False))
    (t / "tests/evade.py").write_text(temoin("evade", True))                  # change de session : hors du groupe de processus de la suite
    (t / "tests/meurt.py").write_text(temoin("meurt", True, quitte=True))     # tue son _jouer : jamais de « fin », son témoin d'une autre session survit
    (t / "tests/vert.py").write_text("print('ok    un contrôle')\n")
    shutil.copy2(T / "_tuer_marque.py", t / "tests/_tuer_marque.py")
    t0 = time.time(); r = passe(1, "suite bloque.py bloque ''; suite evade.py evade ''; suite meurt.py meurt ''; suite vert.py vert ''", delai="4", timeout=90); dt = time.time() - t0
    dire("ko=3" in r.stdout and dt < 60, f"délai maximal par suite + suite morte sans « fin » : 3 échecs comptés, la passe finit ({dt:.0f} s) {(r.stdout + r.stderr)[-200:]!r}")
    for nom in ("bloque", "evade", "meurt"):
        pid = lire_pid(nom); reste = subprocess.run(["pgrep", "-f", f"{nom}-temoin-pm"], capture_output=True, text=True).stdout.split()
        dire(pid is not None and not vivant(pid) and not reste, f"témoin « {nom} » : vivant au départ (contrôle positif), tué à la fin, y compris d'une autre session ou après la mort de son _jouer (pid {pid}, restants {reste})")
        for q in reste: subprocess.run(["kill", "-9", q])

    # une suite ne doit pas hériter de SIGINT ignoré (processus lancé en arrière-plan sans contrôle des tâches) : tests/argv-client.py interrompt un client
    (t / "tests/sigint.py").write_text("import sys\nignore = int([l for l in open('/proc/self/status') if l.startswith('SigIgn:')][0].split()[1], 16)\n"
                                       "print('ok    SIGINT par défaut' if not ignore & 2 else 'ÉCHEC SIGINT ignoré (héritage d un arrière-plan sans contrôle des tâches)'); sys.exit(1 if ignore & 2 else 0)\n")
    r = passe(1, "suite sigint.py sigint ''")
    dire("ko=0" in r.stdout and "SIGINT" not in r.stdout.replace("sigint.py", ""), f"une suite hérite de SIGINT par défaut, pas ignoré {r.stdout[-200:]!r}")

    # le lanceur tué par SIGKILL : son verrou est libéré aussitôt (le descripteur n'est transmis à personne) et plus aucune suite orpheline ne survit
    (t / "tests/longue.py").write_text(temoin("longue", True))
    verrou2 = t / "verrou2.lock"; verrou2.write_text("")
    script = ("dire() { :; }; ko=0; _bt=''; _pyd=''; _sans_herdr=(); _faux_herdr=/bin/false; _herdr_absent=%s/absent.sock; _path_suites=\"$PATH\"\n"
              "declare -A _a_part=(); declare -A _delai_suite=(); _en_tete=(); B=%s\n" % (t, t) + ordonnanceur + "\nsuite longue.py longue ''\n_jouer_les_suites\n")
    (t / "pid-longue").unlink(missing_ok=True)
    lanceur = subprocess.Popen(["bash", "-c", script], env={**ENV, "PATH": f"{t}/py:{ENV['PATH']}", "TMPDIR": str(t), "BERGER_SUITES_PARALLELE": "1", "BERGER_SUITES_VERROU": str(verrou2),
                                                             "BERGER_TEMOINS_RACINE": "/proc/inexistant/temoins"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(100):
        if lire_pid("longue"): break
        time.sleep(0.1)
    pid = lire_pid("longue")
    lanceur.kill(); lanceur.wait()                          # SIGKILL : aucun nettoyage possible côté lanceur
    t0 = time.time(); libre = False
    while time.time() - t0 < 10 and not libre:
        f = open(verrou2, "rb")
        try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); libre = True
        except OSError: time.sleep(0.2)
        finally: f.close()
    dire(pid is not None and libre, f"lanceur tué par SIGKILL : son verrou est libéré aussitôt (aucune suite ne garde le descripteur) — libre {libre} en {time.time() - t0:.1f} s")
    for _ in range(100):
        if pid is None or not vivant(pid): break
        time.sleep(0.1)
    dire(pid is not None and not vivant(pid), "lanceur tué par SIGKILL : la suite orpheline et ses descendants d'une autre session sont tués par la veille de la suite")
    if pid is not None and vivant(pid): _os.kill(pid, signal.SIGKILL)

    # le groupe de processus du rejeu de herdr-fuite.py : délai et interruption tuent les descendants (contrôle positif : le témoin vit au départ)
    def script_temoin(nom, fichier):
        return f"(exec -a {nom}-temoin-pm sleep 300) & p=$!; sleep 0.4; kill -0 $p && echo $p > {fichier}; sleep 300"
    (t / "pid-rejeu").unlink(missing_ok=True)
    t0 = time.time(); rc, sortie = _parallele.groupe_run(["bash", "-c", script_temoin("rejeu", t / "pid-rejeu")], dict(_os.environ), str(t), 2); dt = time.time() - t0
    pid = lire_pid("rejeu"); reste = subprocess.run(["pgrep", "-f", "rejeu-temoin-pm"], capture_output=True, text=True).stdout.split()
    dire(rc == 124 and dt < 20 and pid is not None and not vivant(pid) and not reste, f"rejeu : délai dépassé → code 124, témoin vivant au départ puis tué ({dt:.1f} s, pid {pid}, restants {reste})")
    for q in reste: subprocess.run(["kill", "-9", q])
    (t / "pid-interrompu").unlink(missing_ok=True)
    fils = subprocess.Popen([sys.executable, "-c", "import sys; sys.path.insert(0, %r)\nimport _parallele\n_parallele.installer_signaux()\n"
                             "print('prêt', flush=True)\n_parallele.groupe_run(['bash', '-c', %r], None, '.', 300)\n" % (str(T), script_temoin("interrompu", t / "pid-interrompu"))],
                            stdout=subprocess.PIPE, text=True)
    fils.stdout.readline()
    for _ in range(50):
        if lire_pid("interrompu"): break
        time.sleep(0.1)
    pid = lire_pid("interrompu"); fils.send_signal(signal.SIGTERM)
    try: fils.wait(15); fini = True
    except subprocess.TimeoutExpired: fils.kill(); fini = False
    reste = subprocess.run(["pgrep", "-f", "interrompu-temoin-pm"], capture_output=True, text=True).stdout.split()
    dire(fini and pid is not None and not vivant(pid) and not reste, f"rejeu interrompu (TERM) : le rejeu s'arrête et son témoin, vivant au départ, avec lui (arrêté {fini}, pid {pid}, restants {reste})")
    for q in reste: subprocess.run(["kill", "-9", q])

    # 4. la mesure de mémoire d'une suite
    fich = t / "mem.tsv"
    r = subprocess.run([sys.executable, str(T / "_mesure_mem.py"), str(fich), "grosse.py", "--", sys.executable, "-c",
                        "b = bytearray(80 * 1024 * 1024); import time; time.sleep(1.2); print('fait')"], capture_output=True, text=True, timeout=60)
    lignes = fich.read_text().split("\t") if fich.exists() else []
    dire(r.returncode == 0 and "fait" in r.stdout and len(lignes) == 3 and int(lignes[0]) >= 60000 and int(lignes[1]) >= 60000 and lignes[2].strip() == "grosse.py",
         f"mesure de mémoire : une suite qui prend 80 Mo est vue (pic de l'arbre, plus gros processus, nom) : {lignes}")

    # 5. la preuve Herdr sur toutes les suites, jouée par suites.sh : plomberie (helper factice, sans socket) puis vrais sockets si le bac à sable les permet
    racine_t = Path(tempfile.mkdtemp(prefix="h", dir=_os.environ.get("TMPDIR") or "/tmp"))
    (t / "tests/_temoins.py").write_text(
        "import os, signal, sys\nracine, n, connexions, pret = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]\n"
        "for i in range(n):\n    os.makedirs(f'{racine}/m-{i}/.config/herdr'); os.makedirs(f'{racine}/x-{i}/herdr')\n"
        "def fin(*_):\n    with open(connexions, 'a') as f:\n        for nom in sorted(os.listdir(racine)):\n"
        "            if nom.startswith('touche-'): f.write(nom.split('-', 1)[1].replace('-', ' ', 1) + '\\n')\n    sys.exit(0)\n"
        "signal.signal(signal.SIGTERM, fin); open(pret, 'w').close()\nsignal.pause()\n")
    # une suite correcte vérifie son environnement hostile ; la suite « fuite » se « connecte » au socket hérité (marque que le faux témoin relit)
    verif = ("import os, sys\nh = os.environ.get('HERDR_SOCKET_PATH', ''); r = os.path.dirname(h); i = os.path.basename(h)[2:-5]\n"
             "bon = (h.endswith('.sock') and os.environ.get('HERDR_PANE_ID') == 'pane-temoin' and os.environ.get('HERDR_ENV') == '1'\n"
             "       and os.environ.get('XDG_CONFIG_HOME') == f'{r}/x-{i}' and os.environ.get('BERGER_HERDR_SOCKET') == f'{r}/b-{i}.sock'\n"
             "       and os.environ.get('HOME') == f'{r}/m-{i}' and os.path.basename(os.environ.get('BERGER_HERDR', '')) == 'true')\n")
    (t / "tests/propre.py").write_text(verif + "print('ok    environnement hostile vu' if bon else 'ÉCHEC environnement'); sys.exit(0 if bon else 1)\n")
    (t / "tests/propre2.py").write_text((t / "tests/propre.py").read_text())
    (t / "tests/fuite.py").write_text(verif + "open(f'{r}/touche-{i}-HERDR_SOCKET_PATH', 'w').close()\nprint('ok    fuite simulée'); sys.exit(0 if bon else 1)\n")
    extra = {"BERGER_TEMOINS_RACINE": str(racine_t)}
    r = passe(1, "suite propre.py propre ''; suite propre2.py propre2 ''", extra=extra)
    dire(r.returncode == 0 and "ko=0" in r.stdout and "preuve sur TOUTES les suites : 2 suites jouées en environnement hostile" in r.stdout and "0 connexion" in r.stdout and "NON JOUÉ" not in r.stdout,
         f"suites correctes : chacune voit son environnement hostile (4 chemins vers ses témoins, HOME jetable), preuve « 0 connexion » rendue {r.stdout[-300:]!r}")
    r = passe(1, "suite propre.py propre ''; suite fuite.py fuite ''; suite propre2.py propre2 ''", extra=extra)
    dire("ko=1" in r.stdout and "ÉCHEC isolation Herdr cassée : fuite.py a joint le socket témoin HERDR_SOCKET_PATH" in r.stdout and "preuve sur TOUTES" not in r.stdout,
         f"une suite qui se connecte au socket hérité fait échouer la passe, au nom de cette suite {r.stdout[-300:]!r}")
    r = passe(1, "suite vert.py vert ''", extra={"BERGER_TEMOINS_RACINE": "/proc/inexistant/temoins"})
    dire("ko=0" in r.stdout and "NON JOUÉ Herdr réel hors d'atteinte" in r.stdout, "témoins impossibles à écouter : NON JOUÉ dit (jamais « ok »), les suites sont jouées avec le faux Herdr du lanceur")
    try: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM).close(); unix = True
    except OSError: unix = False
    if unix:   # vrais sockets : le helper de suites.sh voit une connexion et la nomme
        (t / "tests/_temoins.py").write_text((T / "_temoins.py").read_text()); fr = Path(tempfile.mkdtemp(prefix="h", dir=_os.environ.get("TMPDIR") or "/tmp"))
        helper = subprocess.Popen([sys.executable, str(T / "_temoins.py"), str(fr), "3", str(fr / "connexions"), str(fr / "pret")])
        for _ in range(50):
            if (fr / "pret").exists(): break
            time.sleep(0.1)
        for chemin in (fr / "h-1.sock", fr / "m-2/.config/herdr/herdr.sock"):
            c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); c.connect(str(chemin)); c.close()
        time.sleep(0.5); helper.terminate(); helper.wait(10)
        vus = sorted((fr / "connexions").read_text().split("\n")[:-1]) if (fr / "connexions").exists() else []
        dire(vus == ["1 HERDR_SOCKET_PATH", "2 HOME/.config"], f"vrais sockets témoins : deux connexions vues et nommées par suite et par chemin ({vus})")
    else:
        print("NON JOUÉ sockets AF_UNIX impossibles dans cet environnement (bac à sable) : sockets témoins réels non prouvés ici (la plomberie l'est, ci-dessus)")

    # 6. contrôles de structure
    hf = (T / "herdr-fuite.py").read_text()
    dire(re.search(r"^_a_part\[herdr-fuite", SUITES_SH, re.M) is None and "max_workers" not in hf and "def joue" not in hf and "_temoins_demarrer" in SUITES_SH,
         "herdr-fuite.py ne rejoue plus toutes les suites (chaque suite tourne UNE fois) : la preuve est faite par suites.sh, dans l'environnement hostile")
    dire("export BERGER_SUITES_PARALLELE=$n" in SUITES_SH, "suites.sh transmet le plafond retenu à ses descendants (même nombre, calculé une fois)")
    nus = [l for l in SUITES_SH.splitlines() if re.match(r"\s*wait\s*(;|$|#)", l) or re.search(r"[;&|]\s*wait\s*(;|$)", l)]
    dire(not nus, f"aucun « wait » sans argument dans suites.sh (un serveur d'essai de tout.sh l'attendrait sans fin) : {nus}")
    dire("1,5 Go" not in SUITES_SH and "MemAvailable" not in SUITES_SH and "meminfo" not in (T / "_parallele.py").read_text(), "la règle « 1,5 Go par suite » est retirée (non étayée)")
sys.exit(1 if ko else 0)
