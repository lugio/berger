#!/usr/bin/env python3
"""Tests du redémarrage du courtier (16/10/2026) — sans modèle, installation JETABLE (dépôt git), VRAI courtier lancé en processus,
VRAI client berger-outil, faux systemctl / systemd-run. Spec : docs/plans/2026-10-16-courtier-textes-spec.md (3).
Vécu le 16/10 : les portes des développeurs se relayaient, `berger courtier redemarrer` a abandonné au bout de 15 min (exit 1, sans
trace ni notification) et la file des décisions est restée tenue.
1. trois demandes longues qui se chevauchent, redémarrage demandé pendant elles, nouvelles demandes arrivées ensuite (dont un
   « controle » d'un outil ssh factice) : le redémarrage se fait dès la fin de la plus longue en cours (moins que sa durée), TOUTE
   nouvelle demande est rangée puis servie APRÈS (son client attend toujours), une lecture instantanée du courtier passe pendant ; agents Claude et Codex ;
2. abandon : trace « redémarrage NON fait », notification urgente, nouvel essai lancé à part (5 min) ; la demande rangée repart ;
   au dernier essai, plus de nouvel essai et c'est dit ;
3. file tenue : une décision prise pendant la file tenue reçoit le message exact (heure de l'installation), sans attendre ; le délai
   de la file part de l'installation, pas de la première décision vue.
Usage : python3 tests/redemarrage-courtier.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, json, os, signal, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def attendre(cond, delai=30.0):
    fin = time.time() + delai
    while time.time() < fin:
        if cond(): return True
        time.sleep(0.05)
    return bool(cond())


# Outil d'essai : « tests » est une porte (demande LONGUE) qui dure ce qu'on lui dit ; « lire » est immédiate ; « agir » une écriture.
OUTIL = '''import time
from pathlib import Path


class Outil:
    def __init__(self, reglages, secret, verifier_hote):
        self.trace = Path(reglages["trace"])
        self.verbes = {"tests": self.tests, "lire": self.lire}
        self.ecritures = {"agir": (lambda a: "agir " + " ".join(a), self.agir)}

    def hotes(self): return {}

    def noter(self, x):
        with open(self.trace, "a") as f: f.write(f"{x} {time.time():.3f}\\n")

    def tests(self, args):
        """porte d'essai : <nom> <secondes>"""
        self.noter(f"debut {args[0]}"); time.sleep(float(args[1])); self.noter(f"fin {args[0]}"); return ["vert"]

    def lire(self, args):
        """lecture immédiate"""
        return ["lu"]

    def agir(self, args):
        self.noter(f"agir {args[0]}"); return "fait"
'''

# Un outil ssh factice : « controle » dure (un contrôle lancé sur une autre machine) — aucun nom de verbe « long » connu du courtier.
SSH = '''import time
from pathlib import Path


class Outil:
    def __init__(self, reglages, secret, verifier_hote):
        self.trace = Path(reglages["trace"]); self.verbes = {"controle": self.controle}; self.ecritures = {}

    def hotes(self): return {}

    def controle(self, args):
        """contrôle distant factice : <nom> <secondes>"""
        with open(self.trace, "a") as f: f.write(f"debut {args[0]} {time.time():.3f}\\n")
        time.sleep(float(args[1])); return ["contrôlé"]
'''

# ignore_cleanup_errors : le courtier lance à part (_transport.lancer) le message « Décision sur ta demande » ; un tel fils peut
# écrire encore son journal pendant le nettoyage (vu le 26/10 : « Directory not empty » APRÈS 26 contrôles verts).
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
    m = Path(td); i = m / "berger"; trace = m / "trace.txt"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (i / "courtier/outils/lent.py").write_text(OUTIL); (i / "courtier/outils/sshfactice.py").write_text(SSH)
    (m / "coffre-essai.json").write_text("{}")

    def config(courtier):
        (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n\n'
                                       f'[courtier]\n{courtier}\n\n[outils.lent]\ntype = "lent"\ntrace = "{trace}"\n\n[outils.machine]\ntype = "sshfactice"\ntrace = "{trace}"\n')
    config("redemarrage_attente = 60")
    for a, moteur in (("dev-claude", "claude"), ("dev-codex", "codex"), ("admin", "claude")):
        (i / "agents" / a / "memory").mkdir(parents=True)
        (i / "agents" / a / "agent.conf").write_text(f"nom = {a}\nmoteur = {moteur}\npanneaux = {moteur}\nheures = aucune\noutils = lent, machine\n")
    G = ["git", "-c", "user.name=essai", "-c", "user.email=essai@essai", "-C", str(i)]
    subprocess.run([*G, "init", "-q"]); subprocess.run([*G, "add", "-A"]); subprocess.run([*G, "commit", "-qm", "installation"])
    # faux systemctl (bin/berger met HOME/.local/bin en tête de son PATH) : note l'heure du redémarrage et ce qui était en cours
    fb = m / ".local/bin"; fb.mkdir(parents=True)
    (fb / "systemctl").write_text(f'#!/bin/sh\ncase "$*" in *restart*) echo "$(date +%s.%N) encours=$(ls {i}/agents/*/courrier/encours/ 2>/dev/null | grep -c json)" '
                                  f'>> "{m}/redemarrages.txt";; *is-active*) echo active;; esac\nexit 0\n')
    (fb / "systemd-run").write_text(f'#!/bin/sh\necho "$*" >> "{m}/systemd-run.txt"\nexit 0\n')
    for x in ("systemctl", "systemd-run"): os.chmod(fb / x, 0o755)
    ENV = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "PATH": f"{fb}:{os.environ['PATH']}", "BERGER_REDEMARRAGE_PAS": "0.2",
           "BERGER_HERDR": "herdr-absent-du-test", "BERGER_NOTIFY_SEND": "notify-send-absent-du-test", "BERGER_OUTIL_PRISE": "3"}

    def lancer(**plus):
        return subprocess.Popen([sys.executable, str(i / "courtier/courtier")], env={**ENV, **plus}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def arreter(p): p.send_signal(signal.SIGTERM); p.wait(10)

    def client(agent, verbe, *args, outil="lent"):                       # le VRAI client, lancé depuis le dossier de l'agent
        prive = ["--stdin"] if args else []                               # transport privé : paramètres en JSON sur stdin
        c = subprocess.Popen([sys.executable, str(i / "courtier/berger-outil"), outil, verbe, *prive], cwd=i / "agents" / agent, env=ENV,
                             stdin=subprocess.PIPE if args else subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if args: c.stdin.write(json.dumps(list(args))); c.stdin.close(); c.stdin = None
        return c

    def reponse(c, delai=60):
        try: out, _ = c.communicate(timeout=delai)
        except subprocess.TimeoutExpired: c.kill(); return {}
        try: return json.loads(out)
        except ValueError: return {}

    def berger(*args, **kw): return subprocess.Popen([sys.executable, str(i / "bin/berger"), *args], env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw)

    def traces():
        return [(l.split()[0], l.split()[1], float(l.split()[2])) for l in (trace.read_text().splitlines() if trace.exists() else [])]

    def quand(quoi, nom): return next((x[2] for x in traces() if x[:2] == (quoi, nom)), None)

    def redemarrages(): return (m / "redemarrages.txt").read_text().splitlines() if (m / "redemarrages.txt").exists() else []

    def attente(agent): return list((i / "agents" / agent / "courrier/attente").glob("*.json"))

    # ── 1 : trois demandes longues qui se chevauchent ; redémarrage pendant elles ; les nouvelles servies après ──
    t0 = time.time(); p = lancer()
    longues = [client("dev-claude", "tests", "L1", "3"), client("dev-codex", "tests", "L2", "5")]
    time.sleep(0.5); longues.append(client("dev-claude", "tests", "L3", "8"))
    dire(attendre(lambda: all(quand("debut", n) for n in ("L1", "L2", "L3")), 10), "trois demandes longues en cours, qui se chevauchent (Claude et Codex)")
    time.sleep(1.5); debut_redemarrage = time.time(); r = berger("courtier", "redemarrer")
    dire(attendre(lambda: (i / "courtier/fermeture").exists(), 5), "redemarrer pose la marque de fermeture")
    nouvelles = [client("dev-codex", "tests", "N1", "1"), client("dev-claude", "tests", "N2", "1"),
                 client("dev-codex", "controle", "S1", "1", outil="machine"), client("dev-claude", "lire")]
    debut_courte = time.time(); courte = reponse(client("dev-codex", "liste", outil="validation"), 10); duree_courte = time.time() - debut_courte
    dire(courte.get("ok") is True and duree_courte < 2, f"pendant la fermeture, une lecture instantanée du courtier (validation liste) est servie ({duree_courte:.1f} s)")
    dire(attendre(lambda: len(attente("dev-codex")) == 2 and len(attente("dev-claude")) == 2, 5) and not any(quand("debut", n) for n in ("N1", "N2", "S1")),
         "TOUTE nouvelle demande est RANGÉE (courrier/attente/), pas entamée : portes, « controle » d'un outil ssh, simple lecture d'un outil")
    dire(attendre(lambda: redemarrages(), 20), "le redémarrage a lieu")
    fait = float(redemarrages()[0].split()[0]) if redemarrages() else 0
    plus_longue = quand("fin", "L3") or 0
    dire(fait - debut_redemarrage < 8 and plus_longue <= fait < plus_longue + 1.5,
         f"redémarré {fait - debut_redemarrage:.1f} s après la demande — moins que la plus longue (8 s), dès sa fin ({fait - plus_longue:.1f} s après)")
    dire(redemarrages()[:1] and redemarrages()[0].endswith("encours=0"), "au redémarrage, plus rien en cours (aucune demande coupée)")
    dire(r.wait(10) == 0 and not (i / "courtier/fermeture").exists(), "redemarrer finit (code 0) et retire la marque")
    dire(all(reponse(c).get("ok") is True for c in longues), "les trois demandes longues ont leur réponse")
    dire(not any(quand("debut", n) for n in ("N1", "N2", "S1")), "rien des nouvelles n'a tourné avant le redémarrage")
    arreter(p); p = lancer()                                             # systemd relance le courtier : nouveau code chargé
    rep = [reponse(c) for c in nouvelles]
    dire(all(x.get("ok") is True for x in rep) and all((quand("debut", n) or 0) > fait for n in ("N1", "N2", "S1")),
         "après le redémarrage, les nouvelles (dont le « controle » ssh) sont servies, et leur client (délai de prise de 3 s) a attendu sa réponse")
    arreter(p); print(f"  (test 1 : {time.time() - t0:.1f} s)")

    # ── 2 : abandon → trace, notification urgente, nouvel essai ; la demande rangée repart ──
    t0 = time.time(); config("redemarrage_attente = 2\nredemarrage_reessai = 300\nredemarrage_essais = 3"); p = lancer()
    longue = client("dev-claude", "tests", "A1", "5")
    dire(attendre(lambda: quand("debut", "A1"), 10), "une demande longue de 5 s est en cours")
    r = berger("courtier", "redemarrer")
    dire(attendre(lambda: (i / "courtier/fermeture").exists(), 5), "fermeture posée")
    rangee = client("dev-codex", "tests", "A2", "0.2")
    dire(attendre(lambda: attente("dev-codex"), 5), "une nouvelle demande longue est rangée")
    code = r.wait(20); sortie = r.stdout.read()
    log = (i / "courtier/installations.log").read_text() if (i / "courtier/installations.log").exists() else ""
    notes = (i / "courtier/notifications.log").read_text() if (i / "courtier/notifications.log").exists() else ""
    essai = (m / "systemd-run.txt").read_text() if (m / "systemd-run.txt").exists() else ""
    dire(code == 1 and "redémarrage NON fait" in sortie and not redemarrages()[1:], f"abandon : code 1, dit, aucun redémarrage ({sortie.strip()[:90]})")
    dire("redémarrage NON fait" in log and "essai 1/3" in log and "dev-claude" in log, "abandon TRACÉ dans courtier/installations.log (essai, qui était en cours)")
    dire(any("URGENT" in l and "redémarrage du courtier NON fait" in l for l in notes.splitlines()), "abandon NOTIFIÉ en urgence au propriétaire")
    dire("--on-active=300" in essai and "courtier redemarrer --essai 2" in essai, f"nouvel essai lancé à part dans 5 min ({essai.strip()[-70:]})")
    dire(not (i / "courtier/fermeture").exists() and reponse(rangee, 20).get("ok") is True, "la marque tombe : la demande rangée repart et est servie")
    reponse(longue, 20)
    longue = client("dev-codex", "tests", "A3", "4"); attendre(lambda: quand("debut", "A3"), 10)
    r = berger("courtier", "redemarrer", "--essai", "3"); code = r.wait(20); sortie = r.stdout.read()
    essai2 = (m / "systemd-run.txt").read_text() if (m / "systemd-run.txt").exists() else ""
    dire(code == 1 and "dernier essai" in sortie and essai2 == essai and "essai 3/3" in (i / "courtier/installations.log").read_text(),
         "dernier essai : tracé, plus de nouvel essai, et c'est dit (relance à la main)")
    reponse(longue, 20); arreter(p); print(f"  (test 2 : {time.time() - t0:.1f} s)")

    # ── 3 : file tenue — message exact à la décision, délai compté depuis l'installation ──
    t0 = time.time(); config("redemarrage_attente = 60"); p = lancer()
    V = i / "courtier/validations"; V.mkdir(parents=True, exist_ok=True)
    def demande(n): (V / f"{n}.json").write_text(json.dumps({"n": n, "agent": "admin", "outil": "lent", "verbe": "agir", "args": [str(n)],
                                                             "apercu": f"agir {n}", "valideur": None}))
    time.sleep(1)
    subprocess.run([*G, "commit", "-q", "--allow-empty", "-m", "installation 1"])
    heure = int(subprocess.run([*G, "reflog", "-1", "--date=unix", "--format=%gd", "HEAD"], capture_output=True, text=True).stdout.strip().split("{")[1].rstrip("}"))
    dire(attendre(lambda: (i / "courtier/file-tenue.json").exists(), 8), "installation vue SANS décision : la file est tenue (courtier/file-tenue.json)")
    demande(60); debut = time.time(); b = berger("valider", "60"); b.wait(40); sortie = b.stdout.read().strip(); duree = time.time() - debut
    attendu = (f"décision enregistrée ; file tenue : installation en attente de redémarrage depuis {datetime.datetime.fromtimestamp(heure):%H h %M} — "
               "ta décision sera traitée après le redémarrage du courtier (courtier/installations.log)")
    dire(sortie == attendu, f"décision pendant la file tenue : message exact (« {sortie[:110]} »)")
    dire(duree < 5 and not quand("agir", "60"), f"réponse sans attendre ({duree:.1f} s), rien exécuté avec l'ancien code")
    arreter(p); p = lancer(BERGER_FILE_TENUE="4")                        # redémarré : la n° 60 passe, la file repart
    dire(attendre(lambda: quand("agir", "60"), 15) and not (i / "courtier/file-tenue.json").exists(), "après le redémarrage, la n° 60 est exécutée")
    time.sleep(1); subprocess.run([*G, "commit", "-q", "--allow-empty", "-m", "installation 2"]); installe = time.time()
    attendre(lambda: (i / "courtier/file-tenue.json").exists(), 8)
    time.sleep(max(0, installe + 5.5 - time.time()))                    # le délai (4 s) est passé depuis l'installation
    demande(61); decide = time.time(); berger("valider", "61").wait(40)
    dire(attendre(lambda: (V / "61.fait.json").exists(), 10) and quand("agir", "61") and quand("agir", "61") - decide < 2.5,
         "délai compté depuis l'INSTALLATION : une décision prise après lui passe tout de suite (pas 4 s de plus)")
    notes = (i / "courtier/notifications.log").read_text() if (i / "courtier/notifications.log").exists() else ""
    dire(sum("non redémarré" in l for l in notes.splitlines()) == 1, "le garde-fou de la file prévient une fois")
    arreter(p); print(f"  (test 3 : {time.time() - t0:.1f} s)")
print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
