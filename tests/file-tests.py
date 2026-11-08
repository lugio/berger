#!/usr/bin/env python3
"""File des tests tenue par Berger (lot A, docs/plans/2026-11-04-acceleration-fusions-spec.md) : ticket numéroté, ordre d'arrivée,
verrou des suites pris par le courtier AVANT les portes (le délai de la porte ne court qu'après), ticket mort retiré, attente bornée
(refus sans verdict), file visible (demandes, equipe liste, Accueil en jaune au-delà de 30 min), consignes sans « demande le tour ».
Sans modèle ni bac à sable (les portes de l'essai sont des commandes jouées hors bac à sable). Usage : python3 tests/file-tests.py"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import datetime, importlib.util, json, os, subprocess, sys, tempfile, threading, time
from pathlib import Path
os.environ.pop("BERGER_SUITES_VERROU_TENU", None)   # la porte qui joue CETTE suite tient déjà le verrou : ses portes factices doivent partir sans

RACINE = Path(__file__).resolve().parent.parent; OUTILS = RACINE / "courtier/outils"
ko = 0


def charger(t, nom=None):
    spec = importlib.util.spec_from_file_location(nom or f"outil_{t}", OUTILS / f"{t}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def git(d, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True)


F = charger("_file_tests"); F.PAS = 0.05

with tempfile.TemporaryDirectory() as t:
    t = Path(t); os.environ["BERGER_DIR"] = str(t); (t / "config.toml").write_text('proprietaire = "Test"\n')
    forge, depot = t / "forge.git", t / "depot"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    (depot / "porte.sh").write_text('sleep "${DUREE:-0}"; echo "ok $1 : tenu=${BERGER_SUITES_VERROU_TENU:-non} lu=$(cat a.txt 2>/dev/null) ici=$(pwd)"\n')
    git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
    file = t / "courtier/file-tests"

    # ── le verrou est celui de tests/suites.sh : `description` de la forge nue, remontée depuis la copie ──
    dire(F.verrou_suites(depot) == forge / "description", f"verrou des suites : la description de la forge nue ({F.verrou_suites(depot)})")
    clone2 = t / "clone2"; subprocess.run(["git", "clone", "-q", "--shared", str(depot), str(clone2)], capture_output=True)
    dire(F.verrou_suites(clone2) == forge / "description", "verrou des suites : même fichier depuis un clone du dépôt du chef (deux maillons)")

    # ── 1. trois demandes simultanées : ordre d'arrivée, aucune paire ne se chevauche ──
    traces, debut = [], threading.Event()
    def demande(sujet, retard):
        time.sleep(retard)
        with F.tour(sujet, depot):
            traces.append((sujet, "début", time.monotonic())); time.sleep(0.4); traces.append((sujet, "fin", time.monotonic()))
    fils = [threading.Thread(target=demande, args=(s, r)) for s, r in (("un", 0), ("deux", 0.1), ("trois", 0.2))]
    for f in fils: f.start()
    time.sleep(0.25)
    places = {s: F.place(s) for s in ("un", "deux", "trois")}
    for f in fils: f.join()
    ordre = [s for s, quoi, _ in traces if quoi == "début"]
    dire(ordre == ["un", "deux", "trois"], f"3 demandes simultanées : passées dans l'ordre d'arrivée ({ordre})")
    fen = {s: [x for y, _, x in traces if y == s] for s in ordre}
    dire(all(fen[a][1] <= fen[b][0] or fen[b][1] <= fen[a][0] for a in ordre for b in ordre if a < b), "aucune paire ne se chevauche (un seul tour à la fois)")
    dire(places["un"].startswith("en cours (un, depuis") and places["deux"] == "en file (2e, derrière un)" and places["trois"] == "en file (3e, derrière deux)",
         f"visible : « en cours (un, depuis HH:MM) », « en file (2e, derrière un) » ({places})")
    dire(not list(file.glob("*.json")), "tickets retirés à la sortie")

    # ── 2. une passe lancée à la main (bash tests/suites.sh) tient le même verrou : la file l'attend ──
    p = subprocess.Popen(["flock", str(forge / "description"), "sleep", "1.2"]); time.sleep(0.3); t0 = time.monotonic()
    with F.tour("apres-la-main", depot): attendu = time.monotonic() - t0
    p.wait()
    dire(attendu >= 0.7, f"une passe à la main tient le verrou (même fichier) : la file attend sa fin ({attendu:.1f} s)")

    # ── 2 bis. numéros de ticket : deux chargements SÉPARÉS du module (equipe_dev, equipe_chef), en même temps → jamais deux fois le même ──
    G1, G2 = charger("_file_tests", "file_a"), charger("_file_tests", "file_b"); depart = threading.Barrier(40); pris, erreurs = [], []
    def prendre(m):
        depart.wait()
        try: pris.append(m.allouer(file, {"sujet": "x", "pid": os.getpid()})[0])
        except Exception as e: erreurs.append(repr(e))
    fils = [threading.Thread(target=prendre, args=(G1 if i % 2 else G2,)) for i in range(40)]
    for f in fils: f.start()
    for f in fils: f.join()
    dire(not erreurs and len(set(pris)) == 40 and len(list(file.glob("*.json"))) == 40,
         f"40 tickets pris en même temps par deux modules chargés séparément : 40 numéros distincts, aucune erreur ({len(set(pris))}, {erreurs[:1]})")
    for f in file.glob("*.json"): f.unlink()

    # ── 2 ter. une passe À LA MAIN (suites.sh) prend un ticket dans la même file : elle attend son tour, et la suivante l'attend ──
    B = t / "B"; subprocess.run(["git", "clone", "-q", str(forge), str(B)], capture_output=True)
    (B / "courtier/outils").mkdir(parents=True); (B / "courtier/outils/_file_tests.py").symlink_to(OUTILS / "_file_tests.py")
    lignes = (RACINE / "tests/suites.sh").read_text().splitlines()
    debut = next(i for i, l in enumerate(lignes) if l.startswith("_verrou_depot_nu()"))
    fin = next(i for i in range(next(i for i, l in enumerate(lignes) if l.startswith("_verrou_global()")), len(lignes)) if lignes[i] == "}")
    fermer = next(l for l in lignes if l.startswith("_fermer_verrou()"))
    (t / "manuel.sh").write_text("\n".join([f'B="{B}"', fermer, *lignes[debut:fin + 1],
                                            '_verrou_global || { echo "NON JOUÉE"; exit 1; }', 'echo "tour tenu=$BERGER_SUITES_VERROU_TENU"', "sleep 1"]) + "\n")
    env_m = {k: v for k, v in os.environ.items() if k not in ("BERGER_SUITES_VERROU", "BERGER_SUITES_VERROU_TENU")}
    marques = {}
    def devant():
        with F.tour("devant", depot): time.sleep(1.2)
        marques["devant"] = time.monotonic()
    h = threading.Thread(target=devant); h.start(); time.sleep(0.3)
    m = subprocess.Popen(["bash", str(t / "manuel.sh")], env=env_m, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); time.sleep(0.5)
    vu = F.place("passe manuelle")
    def apres():
        time.sleep(0.2)
        with F.tour("apres", depot): marques["apres"] = time.monotonic()
    a = threading.Thread(target=apres); a.start()
    sortie = m.communicate(timeout=60)[0]; marques["manuel"] = time.monotonic(); h.join(); a.join()
    dire(vu == "en file (2e, derrière devant)", f"passe à la main : un ticket dans la file, visible derrière la demande en cours ({vu})")
    dire(m.returncode == 0 and "tour tenu=1" in sortie and "tour obtenu" in sortie, f"passe à la main : tour obtenu dans l'ordre, verrou tenu pour ses suites ({sortie.strip()[-160:]})")
    dire(marques["devant"] <= marques["apres"] and marques["apres"] >= marques["manuel"] - 0.3,
         "la demande arrivée APRÈS la passe à la main attend sa fin (l'ordre d'arrivée est commun)")
    dire(not list(file.glob("*.json")), "passe à la main finie : son ticket est retiré")
    # file NON inscriptible d'ici (bac à sable, ou porte d'un courtier antérieur) : sans ticket, mais jamais devant la file
    occupe = file / "00000001.json"
    occupe.write_text(json.dumps({"n": 1, "sujet": "devant", "pid": os.getpid(), "etat": "en cours"}))
    file.chmod(0o500)
    try:
        def liberer(): file.chmod(0o700); occupe.unlink(); file.chmod(0o500)
        g = threading.Timer(1.2, liberer); g.start(); t0 = time.monotonic()
        r = subprocess.run(["bash", str(t / "manuel.sh")], env=env_m, capture_output=True, text=True, timeout=60); g.join(); o = r.stderr + r.stdout
        dire(r.returncode == 0 and "sans ticket" in o and "tour tenu=1" in o and time.monotonic() - t0 >= 2.0,
             f"file non inscriptible : sans ticket, la passe attend que la file soit VIDE (ticket « devant » parti) puis la suit ({time.monotonic() - t0:.1f} s, {o.strip()[-90:]})")
        file.chmod(0o700); occupe.write_text("{}"); file.chmod(0o500)
        r = subprocess.run(["bash", str(t / "manuel.sh")], env={**env_m, "BERGER_SUITES_ATTENTE": "1"}, capture_output=True, text=True, timeout=60); o = r.stderr + r.stdout
        dire(r.returncode != 0 and "NON JOUÉE" in o and "porte « tests »" in o and "tour tenu" not in o,
             f"file non inscriptible et jamais vide : refus nommé au-delà de l'attente, aucun verdict ({o.strip()[-120:]})")
    finally:
        file.chmod(0o700); occupe.unlink(missing_ok=True)

    # ── 3. ticket orphelin (processus mort) retiré ; attente bornée : refus nommé ──
    mort = subprocess.Popen(["true"]); mort.wait()
    file.mkdir(parents=True, exist_ok=True)
    (file / "00000001.json").write_text(json.dumps({"n": 1, "sujet": "orphelin", "pid": mort.pid, "etat": "en cours"}))
    t0 = time.monotonic()
    with F.tour("vivant", depot): pass
    dire(time.monotonic() - t0 < 2 and not (file / "00000001.json").exists(), "un ticket dont le processus est mort est retiré : il ne bloque pas la file")
    zombie = subprocess.Popen(["true"]); time.sleep(0.3)                  # fini mais NON récolté : un vrai zombie
    etat = Path(f"/proc/{zombie.pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    try: os.kill(zombie.pid, 0); repond = True
    except ProcessLookupError: repond = False
    dire(etat == "Z" and repond and not F.vivant(zombie.pid), f"un zombie répond à kill(pid, 0) (état {etat}) mais n'est pas compté vivant")
    (file / "00000001.json").write_text(json.dumps({"n": 1, "sujet": "zombie", "pid": zombie.pid, "etat": "en cours"}))
    t0 = time.monotonic()
    try:
        with F.tour("derriere-zombie", depot, attente_max=3): r = "passé"
    except F.AttenteDepassee as e: r = str(e)
    dire(r == "passé" and time.monotonic() - t0 < 2 and not (file / "00000001.json").exists(), f"le ticket d'un zombie ne bloque pas la tête de la file ({r[:60]})")
    (file / "00000001.json").write_text(json.dumps({"n": 1, "sujet": "devant", "pid": os.getpid(), "etat": "en cours"}))   # vivant, ne part jamais
    try:
        with F.tour("patient", depot, attente_max=0.5): r = "passé"
    except F.AttenteDepassee as e: r = str(e)
    dire("file des tests : attente dépassée" in r and "aucun verdict" in r, f"au-delà de l'attente maximale : refus nommé ({r[:70]})")
    dire([x.name for x in file.glob("*.json")] == ["00000001.json"], "refus : son ticket est retiré")
    (file / "00000001.json").unlink()

    # ── 3 bis. ticket ORPHELIN (relecture 7/10) : son porteur est mort mais son pid est repris par un autre processus, ou invisible
    # d'un bac à sable — c'est le VERROU du ticket (tenu par son porteur), pas son pid, qui dit s'il est vivant ──
    (file / "00000001.json").unlink(missing_ok=True)
    orphelin = file / "00000001.json"
    orphelin.write_text(json.dumps({"n": 1, "sujet": "orphelin", "pid": os.getpid(), "etat": "en cours", "verrouille": 1}))
    t0 = time.monotonic()
    try:
        with F.tour("apres-orphelin", depot, attente_max=2): r = "passé"
    except F.AttenteDepassee as e: r = str(e)
    dire(r == "passé" and time.monotonic() - t0 < 1.5 and not orphelin.exists(), f"ticket orphelin au pid repris par un autre processus : retiré, la file passe ({r[:60]})")
    tenu = F.allouer(file, {"sujet": "tenu", "pid": "invisible"})
    dire([x["sujet"] for x in F.tickets(file)] == ["tenu"], "ticket au verrou tenu : vivant même si son pid ne se voit pas (bac à sable)")
    os.close(tenu[3])                                                    # porteur parti sans retirer son ticket
    dire(F.tickets(file) == [] and not tenu[1].exists(), "porteur parti sans retirer son ticket : orphelin nettoyé à la lecture suivante")
    orphelin.write_text(json.dumps({"n": 1, "sujet": "orphelin", "pid": os.getpid(), "etat": "en cours", "verrouille": 1}))
    def derriere(attente):
        lu, ec = os.pipe(); os.close(ec); dits = []
        try: rc = F.derriere_la_file(file, str(forge / "description"), attente, "essai", dits.append, lu)
        finally: os.close(lu)
        return rc, dits
    rc, dits = derriere(2)
    dire(rc == 0 and any(x.startswith("TOUR") for x in dits), f"passe sans ticket (bac à sable) : un ticket orphelin ne la bloque pas ({dits})")
    orphelin.unlink(missing_ok=True)
    # passe sans ticket : lecture de la file et prise du verrou ATOMIQUES — un ticket arrivé entre les deux passe devant elle
    import fcntl as _fcntl
    class Course:
        arrive = None
        def __getattr__(self, a): return getattr(_fcntl, a)
        def flock(self, fd, op):
            if op & _fcntl.LOCK_EX and self.arrive is None:
                self.arrive = True; self.arrive = F.allouer(file, {"sujet": "arrive-entre-deux", "pid": os.getpid()})
            return _fcntl.flock(fd, op)
    course = Course(); F.fcntl = course
    try: rc, dits = derriere(1)
    finally: F.fcntl = _fcntl
    dire(rc != 0 and not any(x.startswith("TOUR") for x in dits), f"passe sans ticket : un ticket arrivé entre la lecture de la file et le verrou passe devant ({dits[-1][:70] if dits else ''})")
    if isinstance(course.arrive, tuple): os.close(course.arrive[3]); course.arrive[1].unlink(missing_ok=True)

    # ── 4. développeur : la porte tests prend le tour, son délai ne court qu'après ; refus sans verdict ──
    copie, agent, dem = t / "copie", t / "agent", t / "demandes"
    subprocess.run(["git", "clone", "-q", str(forge), str(copie)], capture_output=True); git(copie, "switch", "-q", "-c", "equipe/demo")
    git(copie, "config", "user.name", "t"); git(copie, "config", "user.email", "t@t.invalid")
    (agent / "courrier").mkdir(parents=True); (agent / "agent.conf").write_text(f"projet = p\nsujet = demo\ncopie = {copie}\nbranche = equipe/demo\nport = 0\n")
    E = charger("equipe_dev", "outil_equipe_dev_file"); E._file.PAS = 0.05
    toutes = {"verify": "sh porte.sh verify", "tests": "DUREE=1 sh porte.sh tests", "pret": "sh porte.sh pret"}
    dev = E.Outil({"principale": "main", "demandes": str(dem), "delai": 2, "regle_go": False, **toutes}, None, None)
    dev.contexte = {"agent": "p-demo", "dossier": str(agent), "demande": "q1.json"}
    dev.hors_bac |= {"verify", "tests", "pret"}                            # l'essai n'a pas de bac à sable : portes jouées directement
    (copie / "a.txt").write_text("a"); git(copie, "add", "-A"); git(copie, "commit", "-qm", "feat: a"); dev.verbes["pousser"]([])
    vus = []
    def tenir():
        with F.tour("autre", depot):
            vus.append((agent / "courrier/file").is_dir() and list((agent / "courrier/file").glob("*")))
            time.sleep(2.5); vus.append(bool(list((agent / "courrier/file").glob("q1.json"))))
    h = threading.Thread(target=tenir); h.start(); time.sleep(0.3)
    r = dev.verbes["tests"]([]); h.join()
    dire(r["code"] == 0 and "ok tests" in r["sortie"], f"porte tests seule : attente de 2,5 s + 1 s de porte, délai 2 s → verte (le délai ne compte pas l'attente)")
    dire("tenu=1" in r["sortie"], "la porte hérite du verrou tenu (BERGER_SUITES_VERROU_TENU=1) : suites.sh ne le reprend pas")
    dire(vus[-1] is True and not list((agent / "courrier/file").glob("*")), "pendant l'attente, le marqueur courrier/file/<demande> dit au client que le délai ne court pas ; retiré ensuite")
    r = dev.verbes["verify"]([])
    dire("tenu=non" in r["sortie"], "verify seule ne passe pas par la file (pas de suite)")
    r = dev.verbes["demander-fusion"](["livré : a.txt, portes jouées"]); d = json.loads((dem / "demo.json").read_text())
    dire(all(d["portes"][p]["etat"] == "vert" for p in ("verify", "tests", "pret")) and "tenu=1" in d["portes"]["tests"]["bilan"]
         and "tenu=1" in d["portes"]["verify"]["bilan"], "demander-fusion : le tour est pris AVANT les portes et gardé jusqu'à la dernière")
    (dem / "demo.json").unlink()
    (file / "00000001.json").write_text(json.dumps({"n": 1, "sujet": "devant", "pid": os.getpid(), "etat": "en cours"}))
    E._file.ATTENTE_MAX = 0.5
    try: dev.verbes["demander-fusion"](["livré : a.txt, portes jouées"]); r = "accepté"
    except ValueError as e: r = str(e)
    dire("attente dépassée" in r and not (dem / "demo.json").exists(), "demander-fusion : attente dépassée → refus, AUCUNE demande ni verdict inscrit")
    (file / "00000001.json").unlink(); E._file.ATTENTE_MAX = 60
    # portes INSCRITES jouées dans une copie FIGÉE du SHA (hors de portée de l'agent, effacée ensuite) : modifier sa copie pendant
    # l'attente ou les portes — même en restaurant ensuite — ne change pas le contenu testé
    ld = json.loads((dem / "demo.json").read_text()) if (dem / "demo.json").exists() else None
    figees = t / "courtier/portes-figees"
    def tenir2():
        with F.tour("autre", depot): time.sleep(1.2)
    h = threading.Thread(target=tenir2); h.start(); time.sleep(0.3)
    g = threading.Timer(0.5, lambda: (copie / "a.txt").write_text("FAUX"))   # modifié pendant l'attente, laissé tel quel pendant les portes
    g.start(); dev.verbes["demander-fusion"](["livré : a.txt, portes jouées"]); h.join(); g.join()
    d = json.loads((dem / "demo.json").read_text()); b = " ".join(d["portes"][p]["bilan"] for p in ("verify", "tests", "pret"))
    dire(b.count("lu=a ") == 3 and "FAUX" not in b, f"copie de l'agent modifiée pendant l'attente : les 3 portes lisent le contenu du SHA ({b[:160]})")
    dire(str(copie) not in b and b.count(str(figees)) == 3, "les portes inscrites jouent dans la copie figée du courtier (courtier/portes-figees), jamais dans la copie de l'agent")
    dire(figees.is_dir() and not [x for x in figees.iterdir() if x.is_dir()], "copie figée effacée après les portes")
    git(copie, "checkout", "-q", "--", "a.txt"); (dem / "demo.json").unlink()
    # copie figée laissée par un ARRÊT BRUTAL du courtier (relecture 7/10) : effacée au démarrage ; une copie en usage, jamais
    sha = git(copie, "rev-parse", "HEAD").stdout.strip()
    (t / "brutal.py").write_text(
        "import importlib.util, os, sys\n"
        f"s = importlib.util.spec_from_file_location('e', {str(OUTILS / 'equipe_dev.py')!r}); E = importlib.util.module_from_spec(s); s.loader.exec_module(E)\n"
        f"o = E.Outil({{'principale': 'main', 'demandes': {str(dem)!r}, 'delai': 2, 'regle_go': False}}, None, None)\n"
        f"with o.copie_figee({{'copie': {str(copie)!r}, 'sujet': 'brutal'}}, {sha!r}): os.kill(os.getpid(), 9)\n")
    subprocess.run([sys.executable, str(t / "brutal.py")], capture_output=True, timeout=120)
    restes = [x for x in figees.iterdir() if x.is_dir()]
    dire(len(restes) == 1 and restes[0].name.startswith("brutal-"), f"courtier tué pendant les portes : sa copie figée reste ({[x.name for x in restes]})")
    with dev.copie_figee(dev.valeurs(), sha) as en_usage:
        efface = F.nettoyer_figees(figees); garde = en_usage.is_dir()
    dire(garde and len(efface) == 1 and efface[0].startswith("brutal-") and not [x for x in figees.iterdir() if x.is_dir()],
         f"nettoyage : la copie orpheline est effacée, jamais une copie en usage (verrou tenu) ({efface})")
    src = (RACINE / "courtier/courtier").read_text(); debut_main = src[src.index("def main():"):].split("threading.Thread(target=executeur")[0]
    dire("nettoyer_figees(" in debut_main and "tickets(" in debut_main, "le courtier nettoie copies figées et tickets orphelins à son démarrage, avant toute porte")

    # ── 5. visible : demandes du chef, equipe liste, Accueil (jaune au-delà de 30 min) ──
    C = charger("equipe_chef", "outil_equipe_chef_file")
    chef = C.Outil({"depot": str(depot), "principale": "main", "demandes": str(dem), "pret": "true", "travail": str(t / "integration"), "projet": "p"}, None, None)
    def attendre_seul():
        with F.tour("devant", depot): time.sleep(1.5)
    h = threading.Thread(target=attendre_seul); h.start(); time.sleep(0.3); l = {}
    g = threading.Timer(0.5, lambda: l.update({x["sujet"]: x for x in chef.verbes["demandes"]([])})); g.start()
    dev.verbes["demander-fusion"](["livré : a.txt, portes jouées"])      # le contexte de l'agent est propre au fil : la demande dans ce fil-ci
    h.join(); g.join()
    dire("demo" in l and l["demo"].get("tests") == "en file (2e, derrière devant)" and "pas encore inscrite" in l["demo"].get("etat", ""),
         f"berger-chef demandes : une demande-fusion qui attend dans la file (pas encore de JSON) est listée ({l.get('demo')})")
    (dem / "demo.json").unlink(missing_ok=True)
    (file / "00000001.json").write_text(json.dumps({"n": 1, "sujet": "devant", "projet": "p", "pid": os.getpid(), "etat": "en cours"}))
    (file / "00000000.json").write_text(json.dumps({"n": 0, "sujet": "zombie", "projet": "p", "pid": zombie.pid, "etat": "en cours"}))   # compté, il ferait de demo le 3e
    (file / "00000003.json").write_text(json.dumps({"n": 3, "sujet": "demo", "projet": "autre-projet", "pid": os.getpid(), "etat": "en file"}))
    (file / "00000004.json").write_text(json.dumps({"n": 4, "sujet": "seul-ailleurs", "projet": "autre-projet", "pid": os.getpid(), "etat": "en file"}))
    dem.mkdir(exist_ok=True); (dem / "demo.json").write_text(json.dumps({"sujet": "demo", "branche": "equipe/demo", "etat": "à relire"}))
    (file / "00000002.json").write_text(json.dumps({"n": 2, "sujet": "demo", "projet": "p", "pid": os.getpid(), "etat": "en file",
                                                    "depuis": (datetime.datetime.now() - datetime.timedelta(minutes=40)).isoformat(timespec="seconds")}))
    l = chef.verbes["demandes"]([])
    dire(l and l[0].get("tests") == "en file (2e, derrière devant)", f"berger-chef demandes : « tests : en file (2e, derrière devant) », zombie ignoré ({l[0].get('tests') if l else None})")
    dire(sorted(x["sujet"] for x in l) == ["demo", "devant"], f"demandes du projet p : ses tickets seulement, ni ceux d'un autre projet (seul-ailleurs) ni son « demo » ({[x['sujet'] for x in l]})")
    (file / "00000005.json").write_text(json.dumps({"n": 5, "sujet": "orphelin-lu", "projet": "p", "pid": os.getpid(), "etat": "en file", "verrouille": 1}))
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); from noyau import lectures as L; "
            "print(json.dumps({'place': L.place_tests('demo', projet='p'), 'alertes': L.alertes_file_tests(), 'sujets': [x['sujet'] for x in L.file_tests()]}, ensure_ascii=False))")
    r = subprocess.run([sys.executable, "-c", code, str(RACINE / "bin")], capture_output=True, text=True, env={**os.environ, "BERGER_DIR": str(t), "HOME": str(t)})
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {"erreur": (r.stderr or r.stdout)[-300:]}
    dire(x.get("place") == "en file (2e, derrière devant)", f"lecture de Berger (equipe liste) : même place ({x.get('place') or x})")
    dire("orphelin-lu" not in x.get("sujets", ["orphelin-lu"]) and "devant" in x.get("sujets", []), f"lecture de Berger : un ticket orphelin (verrou libre, pid repris) est ignoré ({x.get('sujets')})")
    dire(any(a[0] == "jaune" and "demo attend depuis 40 min" in a[2] for a in x.get("alertes", [])), f"Accueil : JAUNE au-delà de 30 min d'attente ({x.get('alertes')})")
    for f in file.glob("*.json"): f.unlink()

# ── 7. client berger-outil : un marqueur de file VIEUX (courtier mort) est ignoré ; un marqueur frais prolonge, jamais au-delà du plafond ──
CLIENT = RACINE / "courtier/berger-outil"
def client(t, rafraichir, plafond=None, duree=6.0):
    """Lance le client sans courtier ; dès que sa demande paraît, pose son marqueur de file (rafraîchi ou non). → (fini, secondes)."""
    ag = Path(tempfile.mkdtemp(dir=t)); (ag / "agent.conf").write_text("nom = essai\n")
    env = {**os.environ, "BERGER_OUTIL_PRISE": "1", **({"BERGER_OUTIL_PLAFOND_FILE": str(plafond)} if plafond is not None else {})}
    c = subprocess.Popen([sys.executable, "-I", str(CLIENT), "outil", "verbe"], cwd=ag, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    t0 = time.monotonic(); marque = None
    while time.monotonic() - t0 < duree and c.poll() is None:
        if marque is None:
            vus = list((ag / "courrier/demandes").glob("*.json")) if (ag / "courrier/demandes").is_dir() else []
            if vus:
                marque = ag / "courrier/file" / vus[0].name; marque.write_text("{}")
                if not rafraichir: os.utime(marque, (time.time() - 1000, time.time() - 1000))
        elif rafraichir: os.utime(marque)
        time.sleep(0.2)
    fini = c.poll() is not None; ecoule = time.monotonic() - t0
    if not fini: c.kill()
    c.wait(); return fini, ecoule

with tempfile.TemporaryDirectory() as t:
    fini, ecoule = client(t, rafraichir=False)
    dire(fini and ecoule < 4, f"client : marqueur de file VIEUX (courtier arrêté) ignoré → délai normal, il s'arrête ({ecoule:.1f} s)")
    fini, ecoule = client(t, rafraichir=True, duree=3.5)
    dire(not fini, "client : marqueur de file FRAIS (le courtier attend son tour) → le délai ne court pas")
    fini, ecoule = client(t, rafraichir=True, plafond=1.5, duree=8)
    dire(fini and ecoule < 6, f"client : plafond absolu — même un marqueur frais ne prolonge pas l'attente au-delà ({ecoule:.1f} s)")

# ── 6. consignes générées : plus de « demande le tour » ──
modeles = "".join((RACINE / "commun/modeles" / f).read_text() for f in ("equipe-developpeur.md", "equipe-chef-de-projet.md", "equipe-coordinateur.md", "equipe-processus.md"))
dire("demande le tour" not in modeles.lower() and "demande-moi le tour" not in modeles.lower(), "consignes générées (développeur, chef, coordinateur, circuit) : aucune règle « demande le tour »")
dire("Berger tient la file des tests" in modeles, "consignes : la file est tenue par Berger (l'agent lance sa porte, Berger le fait attendre)")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
