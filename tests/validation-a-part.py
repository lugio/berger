#!/usr/bin/env python3
"""Tests de l'exécution À PART des validations (14/10/2026) — sans modèle, installation JETABLE (dépôt git), VRAI courtier
lancé en processus (sa boucle principale et son exécuteur). Spec : docs/plans/2026-10-14-validation-a-part-spec.md.
Vécu le 14/10 : la fusion n° 94 rejouait les portes (16 min) dans la boucle du courtier — plus aucun appel servi.
1. une validation dont l'action dure 8 s : pendant ce temps, une lecture d'un autre agent est servie en moins de 2 s et un
   panneau est collecté ;
2. validations décidées à la suite : exécutées l'une APRÈS l'autre, dans l'ordre des décisions (9 avant 10, 12 décidée
   avant 11 passe d'abord) ;
3. courtier arrêté net pendant une exécution : au redémarrage « état inconnu », action jamais rejouée, la décision qui
   attendait son tour s'exécute une fois ;
4. installation (HEAD changé + `berger courtier redemarrer`) : le redémarrage n'attend aucune exécution, le résultat est
   inscrit avant lui, la décision suivante attend le redémarrage ; HEAD revenu (retour arrière) : la file repart ;
5. garde-fou : sans redémarrage, la file repart après le délai — journal du courtier et UNE notification urgente ;
6. exécuteur mort : le courtier s'arrête (code ≠ 0), jamais une file muette.
Usage : python3 tests/validation-a-part.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, signal, subprocess, sys, tempfile, time
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


# Outil d'essai (dans l'installation jetable seulement) : une lecture immédiate, une écriture qui dure ce qu'on lui dit,
# trace son début et sa fin, et peut jouer une installation (HEAD changé, puis redémarrage contrôlé lancé à part).
OUTIL_LENT = '''import subprocess, sys, time
from pathlib import Path


class Outil:
    def __init__(self, reglages, secret, verifier_hote):
        self.trace, self.berger = Path(reglages["trace"]), Path(reglages["berger"])
        self.verbes = {"lire": self.lire}
        self.ecritures = {"agir": (self.apercu, self.agir)}

    def hotes(self): return {}

    def lire(self, args):
        """lecture immédiate"""
        return ["lu"]

    def apercu(self, args):
        """agir <nom> <secondes> [tete|installer]"""
        return "agir " + " ".join(args)

    def noter(self, x):
        with open(self.trace, "a") as f: f.write(f"{x} {time.time():.3f}\\n")

    def agir(self, args):
        self.noter(f"debut {args[0]}"); time.sleep(float(args[1]))
        if {"tete", "installer"} & set(args[2:]):
            subprocess.run(["git", "-c", "user.name=essai", "-c", "user.email=essai@essai", "-C", str(self.berger), "commit", "-q",
                            "--allow-empty", "-m", f"installation {args[0]}"], capture_output=True)
        if "installer" in args[2:]:
            subprocess.Popen([sys.executable, str(self.berger / "bin/berger"), "courtier", "redemarrer"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.noter(f"fin {args[0]}"); return "fait"
'''

with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"; trace = m / "trace.txt"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (i / "courtier/outils/lent.py").write_text(OUTIL_LENT)
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(
        f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n\n'
        f'[outils.lent]\ntype = "lent"\ntrace = "{trace}"\nberger = "{i}"\n\n'
        '[panneaux.vue]\noutil = "lent"\nverbe = "lire"\ncadence = 60\n\n'
        '[panneaux.vue2]\noutil = "lent"\nverbe = "lire"\ncadence = 60\n')
    for a, outils in (("admin", ""), ("lecteur", "lent")):
        (i / "agents" / a / "memory").mkdir(parents=True)
        (i / "agents" / a / "agent.conf").write_text(f"nom = {a}\npanneaux = claude\nheures = aucune\noutils = {outils}\n")
    G = ["git", "-c", "user.name=essai", "-c", "user.email=essai@essai", "-C", str(i)]
    subprocess.run([*G, "init", "-q"]); subprocess.run([*G, "add", "-A"]); subprocess.run([*G, "commit", "-qm", "installation"])
    tete = lambda: subprocess.run([*G, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    # faux systemctl (bin/berger met HOME/.local/bin en tête de son PATH) : note ce qu'il voit au moment du redémarrage
    V = i / "courtier/validations"; V.mkdir(parents=True); fb = m / ".local/bin"; fb.mkdir(parents=True)
    (fb / "systemctl").write_text(f'#!/bin/sh\nf=absent; [ -f "{V}/30.fait.json" ] && f=present\n'
                                  f'echo "fait=$f execution=$(ls "{V}" | grep -c execution)" > "{m}/systemctl.txt"\n')
    os.chmod(fb / "systemctl", 0o755)
    ENV = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "PATH": f"{fb}:{os.environ['PATH']}",
           "BERGER_HERDR": "herdr-absent-du-test", "BERGER_NOTIFY_SEND": "notify-send-absent-du-test"}

    def lancer(**plus):
        return subprocess.Popen([sys.executable, str(i / "courtier/courtier")], env={**ENV, **plus},
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    def arreter(p, sig=signal.SIGTERM):
        p.send_signal(sig); p.wait(10)

    def demande(n, *args):
        (V / f"{n}.json").write_text(json.dumps({"n": n, "agent": "admin", "outil": "lent", "verbe": "agir", "args": list(args),
                                                 "apercu": "agir " + " ".join(args), "valideur": None}))

    def decider(n, quand=None):
        tmp = V / f".{n}.tmp"; tmp.write_text("valider\npar=Proprio\n")
        if quand: os.utime(tmp, (quand, quand))
        tmp.rename(V / f"{n}.decision")

    fait = lambda n: (V / f"{n}.fait.json").exists()
    etat = lambda n: json.loads((V / f"{n}.fait.json").read_text()) if fait(n) else {}

    def traces():
        out = []
        for l in (trace.read_text().splitlines() if trace.exists() else []):
            quoi, nom, quand = l.split(); out.append((quoi, nom, float(quand)))
        return out

    def intervalle(nom):
        d = [x[2] for x in traces() if x[:2] == ("debut", nom)]; f = [x[2] for x in traces() if x[:2] == ("fin", nom)]
        return (d[0] if d else None, f[0] if f else None)

    # ── 1 et 2 : lecture servie pendant une exécution de 8 s ; exécutions l'une après l'autre, dans l'ordre ──
    t0 = time.time(); p = lancer()
    demande(93, "93", "8"); decider(93)
    dire(attendre(lambda: intervalle("93")[0]), "la validation n° 93 (8 s) a commencé")
    boite = i / "agents/lecteur/courrier"; boite.joinpath("demandes").mkdir(parents=True, exist_ok=True)
    debut = time.time(); tmp = boite / "demandes/.lire.tmp"
    tmp.write_text(json.dumps({"outil": "lent", "verbe": "lire", "args": []})); tmp.rename(boite / "demandes/lire.json")
    servie = attendre(lambda: (boite / "reponses/lire.json").exists(), 10); duree_lecture = time.time() - debut
    rep = json.loads((boite / "reponses/lire.json").read_text()) if servie else {}
    dire(servie and rep.get("ok") and duree_lecture < 2 and not intervalle("93")[1],
         f"pendant la n° 93, la lecture d'un autre agent est servie en {duree_lecture:.2f} s (< 2 s), avant la fin de l'action")
    maintenant = time.time()
    for n in (94, 9, 10, 12, 11): demande(n, str(n), "0.4")
    decider(94, maintenant); decider(9, maintenant + 1); decider(10, maintenant + 1)   # 9 et 10 décidées au même instant
    decider(12, maintenant + 2); decider(11, maintenant + 3)                            # 12 décidée AVANT 11
    dire(attendre(lambda: all(fait(n) for n in (93, 94, 9, 10, 12, 11)), 40), "les six validations sont exécutées")
    vue2 = json.loads((i / "courtier/panneaux/vue2.json").read_text()) if (i / "courtier/panneaux/vue2.json").exists() else {}
    import datetime as _d
    q = _d.datetime.fromisoformat(vue2["quand"]).timestamp() if vue2.get("quand") else 0
    d93, f93 = intervalle("93")
    dire(vue2.get("ok") and d93 - 1 <= q <= f93, "un panneau est collecté PENDANT l'exécution de la n° 93")
    ordre = [x[1] for x in traces() if x[0] == "debut"]
    dire(ordre == ["93", "94", "9", "10", "12", "11"], f"exécutées dans l'ordre des décisions, 9 avant 10, 12 avant 11 : {' '.join(ordre)}")
    iv = [intervalle(n) for n in ordre]
    dire(all(iv[k][1] <= iv[k + 1][0] for k in range(len(iv) - 1)), "jamais deux exécutions en même temps (chacune finit avant la suivante)")
    dire(all(etat(n).get("etat") == "validé et exécuté" for n in (93, 94)) and attendre(lambda: not list(V.glob("*.execution")), 10),   # le résultat d'abord, la marque ensuite
         "résultats inscrits comme avant (« validé et exécuté »), plus aucune marque « en cours »")
    arreter(p); print(f"  (tests 1 et 2 : {time.time() - t0:.1f} s)")

    # ── 3 : arrêt net pendant une exécution → « état inconnu », jamais rejouée ; la suivante une fois ──
    t0 = time.time(); p = lancer()
    demande(20, "20", "6"); demande(21, "21", "0.2"); decider(20); decider(21, time.time() + 1)
    dire(attendre(lambda: intervalle("20")[0]), "la n° 20 a commencé")
    arreter(p, signal.SIGKILL)
    dire((V / "20.execution").exists() and not fait(20), "courtier arrêté net : la marque « en cours » de la n° 20 reste, pas de résultat")
    p = lancer()
    dire(attendre(lambda: fait(21), 20), "au redémarrage, la n° 21 qui attendait son tour est exécutée")
    time.sleep(1.5)
    debuts = [x[1] for x in traces() if x[0] == "debut"]
    dire(etat(20).get("etat") == "validé mais ÉCHEC" and "inconnu" in str(etat(20).get("resultat")) and debuts.count("20") == 1
         and intervalle("20")[1] is None, "la n° 20 est dite « état inconnu » et n'a jamais été rejouée")
    dire(debuts.count("21") == 1 and etat(21).get("etat") == "validé et exécuté", "la n° 21 est exécutée une seule fois")
    arreter(p); print(f"  (test 3 : {time.time() - t0:.1f} s)")

    # ── 4 : installation automatique toujours contrôlée ; HEAD revenu → la file repart ──
    t0 = time.time(); p = lancer()
    demande(30, "30", "0.5", "installer"); demande(31, "31", "0.2"); decider(30)
    dire(attendre(lambda: intervalle("30")[0]), "la n° 30 (installation) a commencé"); decider(31)
    dire(attendre(lambda: (m / "systemctl.txt").exists(), 20), "le redémarrage contrôlé est lancé")
    vu = (m / "systemctl.txt").read_text().strip() if (m / "systemctl.txt").exists() else ""
    dire(vu == "fait=present execution=0", f"au redémarrage : résultat de la n° 30 inscrit, aucune exécution en cours ({vu})")
    time.sleep(2.5)
    dire(not fait(31) and not intervalle("31")[0], "HEAD changé : la n° 31 attend le redémarrage (rien exécuté avec l'ancien code)")
    dire("file des validations tenue" in (i / "courtier/appels.log").read_text(), "la file tenue est écrite au journal du courtier")
    arreter(p); p = lancer()                                             # le redémarrage (systemd) : nouveau code chargé
    dire(attendre(lambda: fait(31), 20), "après le redémarrage, la n° 31 est exécutée")
    avant = tete(); demande(32, "32", "0.2", "tete"); demande(33, "33", "0.2"); decider(32)
    dire(attendre(lambda: fait(32), 20) and tete() != avant, "la n° 32 change le HEAD de l'installation"); decider(33)
    time.sleep(2)
    dire(not fait(33), "la n° 33 attend tant que le HEAD a changé")
    subprocess.run([*G, "reset", "-q", "--soft", avant])
    dire(attendre(lambda: fait(33), 20), "HEAD revenu (retour arrière) : la file repart d'elle-même, la n° 33 est exécutée")
    arreter(p); print(f"  (test 4 : {time.time() - t0:.1f} s)")

    # ── 5 : garde-fou (délai réduit à 3 s) : journal + UNE notification urgente, la file repart ──
    t0 = time.time(); p = lancer(BERGER_FILE_TENUE="3")
    demande(40, "40", "0.2", "tete"); demande(41, "41", "0.2"); decider(40)
    dire(attendre(lambda: fait(40), 20), "la n° 40 change le HEAD"); decider(41)
    time.sleep(1.5); dire(not fait(41), "la n° 41 attend d'abord")
    dire(attendre(lambda: fait(41), 20), "sans redémarrage, la file repart après le délai : la n° 41 est exécutée")
    time.sleep(2)
    notes = (i / "courtier/notifications.log").read_text().splitlines() if (i / "courtier/notifications.log").exists() else []
    urgentes = [l for l in notes if "URGENT" in l and "non redémarré" in l]
    dire("aucun redémarrage du courtier" in (i / "courtier/appels.log").read_text(), "le garde-fou est écrit au journal du courtier")
    dire(len(urgentes) == 1, f"une seule notification urgente au propriétaire ({len(urgentes)})")
    arreter(p); print(f"  (test 5 : {time.time() - t0:.1f} s)")

    # ── 6 : exécuteur mort → le courtier s'arrête, code ≠ 0 ──
    t0 = time.time(); p = lancer()
    (V / "50.json").write_text("pas du json"); decider(50)
    try: code = p.wait(15)
    except subprocess.TimeoutExpired: code = None; arreter(p, signal.SIGKILL)
    erreur = p.stderr.read() if p.stderr else ""
    dire(code not in (None, 0) and "exécuteur" in erreur, f"exécuteur mort : le courtier s'arrête (code {code}), systemd le relancera")
    print(f"  (test 6 : {time.time() - t0:.1f} s)")

    # ── 7 : verrou du dépôt du chef — attente bornée, puis refus clair ; libre : la commande passe ──
    t0 = time.time(); os.environ["BERGER_ATTENTE_DEPOT"] = "1"
    import importlib.util
    spec = importlib.util.spec_from_file_location("equipe_chef_essai", i / "courtier/outils/equipe_chef.py")
    E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
    chef = E.Outil({"depot": str(i), "demandes": str(m / "demandes")}, None, None)
    verrou = E.verrou_depot(i); verrou.acquire()                         # une autre commande git tient le dépôt
    debut = time.time()
    try: chef.git("rev-parse", "HEAD"); refus = ""
    except RuntimeError as e: refus = str(e)
    attente = time.time() - debut; verrou.release()
    dire("dépôt du chef occupé" in refus and 0.9 <= attente < 3, f"dépôt tenu : refus clair après {attente:.1f} s d'attente bornée (« {refus[:60]} »)")
    dire(chef.git("rev-parse", "HEAD").stdout.strip() == tete() and not verrou.locked(), "dépôt libre : la commande passe et rend le verrou")
    print(f"  (test 7 : {time.time() - t0:.1f} s)")
print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
