#!/usr/bin/env python3
"""Tests du verbe prod (bin/serveur/berger-prod, spec docs/plans/2026-10-15-verbe-prod-spec.md) — sans réseau ni docker :
dépôt git jetable avec son « origin », commandes du serveur simulées par la configuration, santé lue par une URL file://,
faux gpg (le bac à sable des agents interdit l'agent gpg) puis une passe gpg RÉEL quand une clé jetable peut être créée.
Couvre : chaque refus (rien n'est fait), les prérequis (gpg, docker compose), le seuil de disque, les commandes « avant » et
« apres », la sauvegarde chiffrée et vérifiée, l'essai à blanc, la mise en production (branche principale sur l'étiquette),
les migrations SQL (jouées et inscrites, en erreur), le retour arrière (construction, santé, migration en erreur, retour
arrière en échec), la connexion ssh coupée en pleine construction, le verrou, la commande ssh forcée ;
puis par le courtier : le chef de projet obtient une demande validée par le propriétaire, un développeur est refusé.
Usage : python3 tests/verbe-prod.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import fcntl, json, os, re, shutil, signal, stat, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
PROD = SRC / "bin/serveur/berger-prod"
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


# Faux gpg : « chiffre » en base64 derrière un en-tête qui nomme le destinataire ; ne sait PAS déchiffrer (pas de clé
# privée sur le serveur) ; --list-packets et --list-keys comme gpg. $T/gpg-autre = chiffre pour un autre destinataire.
FAUX_GPG = r'''#!/usr/bin/env python3
import base64, os, sys
a = sys.argv[1:]; T = os.environ["T_PROD"]
ident = lambda n: "ID" + n.encode().hex().upper()
if "--encrypt" in a:
    dest = [a[i + 1] for i, x in enumerate(a) if x == "--recipient"]
    open(T + "/gpg-destinataires", "w").write(" ".join(dest))
    if os.path.exists(T + "/gpg-autre"): dest = ["autre-cle"]
    sys.stdout.buffer.write(("FAUX-GPG " + ",".join(dest) + "\n").encode() + base64.b64encode(sys.stdin.buffer.read()))
elif "--list-packets" in a:
    tete = open(a[-1], "rb").readline().decode()
    if tete.startswith("FAUX-GPG "):
        for n in tete[9:].strip().split(","): print(f":pubkey enc packet: version 3, algo 18, keyid {ident(n)}")
    sys.exit(2)
elif "--list-keys" in a:
    print(f"pub:u:255:22:{ident(a[-1])}0:0:::u:::scESC:"); print(f"sub:u:255:18:{ident(a[-1])}:0::::::e:")
elif "--decrypt" in a:
    sys.exit(2)
'''


# Faux psql : la table de suivi est $T/table.txt (une ligne par migration) ; « -c SELECT » la lit, « -c INSERT » inscrit ;
# « --single-transaction -f - » joue l'entrée en entier ou rien (ERREUR-FACTICE = échec), inscription comprise ; « -f - »
# seul (fichier qui gère sa transaction) joue sans inscrire. $T/mode.log : comment chaque entrée a été jouée.
FAUX_PSQL = r'''#!/usr/bin/env python3
import os, re, sys
a = sys.argv[1:]; T = os.environ["T_PROD"]; table = T + "/table.txt"
INSERT = r"INSERT INTO schema_migrations \(([a-z_, ]+)\) VALUES \(('[^']*'(?:, '[^']*')*)\);"
def inscrire(texte):
    for cols, vals in re.findall(INSERT, texte):
        open(table, "a").write(re.match(r"'([^']*)'", vals).group(1) + "\n")
        open(T + "/joue.log", "a").write(re.match(r"'([^']*)'", vals).group(1) + "\n")
        open(T + "/inscrit.log", "a").write(f"({cols}) ({vals})\n")
def mode(m): open(T + "/mode.log", "a").write(m + "\n")
if "-c" in a:
    sql = a[a.index("-c") + 1]
    if sql.startswith("INSERT"): mode("inscription"); inscrire(sql); sys.exit(0)
    if os.path.exists(T + "/table-absente"): sys.stderr.write('ERROR:  relation "schema_migrations" does not exist\n'); sys.exit(1)
    sys.stdout.write(open(table).read() if os.path.exists(table) else ""); sys.exit(0)
if a[-2:] == ["-f", "-"]:
    entree = sys.stdin.read()
    if "ERREUR-FACTICE" in entree: sys.stderr.write("ERROR:  erreur factice de migration\n"); sys.exit(3)
    if "--single-transaction" in a: mode("transaction-unique"); inscrire(entree)
    elif re.search(r"^\s*BEGIN\s*;", entree, re.I | re.M) and "INSERT INTO schema_migrations" not in entree: mode("sa-transaction")
    else: sys.exit(9)
    sys.exit(0)
sys.exit(9)
'''
FAUX_DOCKER = "#!/bin/sh\n[ \"$1 $2\" = \"compose version\" ] && echo 'Docker Compose version factice' && exit 0\nexit 1\n"


def git(d, *a): return subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True)


def depot_jetable(t):
    origin, graine, depot = t / "origin.git", t / "graine", t / "depot"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)])
    subprocess.run(["git", "clone", "-q", str(origin), str(graine)], capture_output=True)
    for x in ("user.name", "user.email"): git(graine, "config", x, "essai@exemple.invalid")

    def version(v, migration=None, sql="SELECT 1;", plus=None, retirer=None):
        (graine / "VERSION").write_text(v)
        if migration: (graine / "migrations" / migration).write_text(sql + "\n")
        for n, contenu in (plus or {}).items(): (graine / "migrations" / n).write_text(contenu)
        if retirer: (graine / "migrations" / retirer).unlink()
        git(graine, "add", "-A"); git(graine, "commit", "-qm", v); git(graine, "tag", v)
    (graine / "migrations").mkdir(); (graine / "migrations/LISEZMOI").write_text("pas une migration\n")
    version("v1.0.0", "0001_initial.sql"); git(graine, "push", "-q", "origin", "main", "--tags")
    subprocess.run(["git", "clone", "-q", str(origin), str(depot)], capture_output=True)
    version("v1.1.0"); version("v1.2.0", "0002_ajout_colonne.sql"); version("v1.3.0")
    version("v1.4.0", "0003_casse.sql", "ALTER TABLE x ADD COLUMN ERREUR-FACTICE;")
    version("v1.5.0", retirer="0003_casse.sql", plus={"0004_sa_transaction.sql": "begin;\nALTER TABLE x ADD COLUMN y int;\nCOMMIT;\n",
                                                       "0004b_simple.sql": "ALTER TABLE x ADD COLUMN z int;\n"})
    version("v1.6.0", "0005_l'apostrophe.sql")
    version("v1.7.0", retirer="0005_l'apostrophe.sql")
    git(graine, "push", "-q", "origin", "main", "--tags")
    git(graine, "checkout", "-q", "-b", "a-cote", "v1.0.0"); version("v9.0.0"); git(graine, "push", "-q", "origin", "v9.0.0")
    return depot


def config(t, depot, fichier="berger-prod.toml", **plus):
    T = str(t)
    c = {"depot": str(depot), "compose": "compose.yml", "service_base": "base", "sauvegardes": f"{T}/sauvegardes",
         "gpg_destinataire": "cle-de-sauvegarde-essai", "gpg": f"{T}/faux/gpg", "sante_url": f"file://{T}/sante.json",
         "sante_delai": 2, "sante_intervalle": 0.2, "docker": f"{T}/faux/docker", "psql": f"{T}/faux/psql",
         "migrations_dossier": "migrations",
         "sauvegarder": f"if [ -e {T}/sauvegarde-vide ]; then :; elif [ -e {T}/sauvegarde-illisible ]; then printf pas-un-dump; "
                        f"else printf 'PGDMP contenu-de-base-factice'; fi",
         "relire": "head -c 5 | grep -q PGDMP && echo 'liste des objets'",
         "construire": f"! {{ [ -e {T}/construction-cassee ] && grep -q v1.2.0 VERSION; }}",
         "demarrer": f"test ! -e {T}/demarrage-casse && {{ [ -e {T}/sante-figee ] || printf '{{\"version\": \"%s\"}}' \"$(cat VERSION)\" > {T}/sante.json; }}",
         "restaurer": "pg_restore --clean --if-exists", **plus}
    f = t / fichier; f.write_text("".join(f"{k} = {json.dumps(v)}\n" for k, v in c.items())); return f


def faux(t):
    """Les faux gpg, psql et docker du serveur, et la table de suivi qui connaît la migration de v1.0.0."""
    (t / "faux").mkdir()
    for n, txt in (("gpg", FAUX_GPG), ("psql", FAUX_PSQL), ("docker", FAUX_DOCKER)):
        (t / "faux" / n).write_text(txt); os.chmod(t / "faux" / n, 0o755)
    (t / "table.txt").write_text("0001_initial.sql\n")


def prod(cfg, *a, env=None):
    r = subprocess.run([sys.executable, str(PROD), "--config", str(cfg), *a], capture_output=True, text=True, timeout=120,
                       env={**os.environ, **(env or {})})
    try: cr = json.loads(r.stdout)
    except ValueError: cr = {}
    return r.returncode, cr, r


with tempfile.TemporaryDirectory() as td:
    t = Path(td); os.environ["T_PROD"] = td
    faux(t); depot = depot_jetable(t); cfg = config(t, depot)
    (t / "sante.json").write_text('{"version": "v1.0.0"}')
    sv = t / "sauvegardes"
    head = lambda: git(depot, "rev-parse", "HEAD").stdout.strip()
    branche = lambda: git(depot, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    tag = lambda v: git(depot, "rev-parse", f"{v}^{{commit}}").stdout.strip()
    sauvegardes = lambda: sorted(p.name for p in sv.glob("base-*")) if sv.exists() else []
    table = lambda: (t / "table.txt").read_text().split()
    jouees = lambda: (t / "joue.log").exists()
    avant = head()

    c, cr, r = prod(cfg, "aide")
    dire(c == 0 and "prod [--essai] vX.Y.Z" in r.stdout and "Prérequis : présents" in r.stdout, "aide : usage affiché, prérequis présents")

    # ── 0. prérequis et réglages : refus tôt, rien n'est fait ──
    for nom, plus, mot in (("gpg absent", {"gpg": f"{td}/absent/gpg"}, "gpg"),
                           ("docker compose absent", {"docker": f"{td}/absent/docker"}, "docker compose")):
        autre = config(t, depot, "autre.toml", **plus)
        c, cr, _ = prod(autre, "aide")
        dire(c == 1 and cr.get("statut") == "refus" and "prérequis absents" in cr.get("motif", "") and mot in cr.get("motif", ""),
             f"{nom} : « aide » refuse, motif clair")
        c, cr, _ = prod(autre, "prod", "--essai", "v1.1.0")
        dire(c == 1 and mot in cr.get("motif", "") and not sauvegardes() and head() == avant, f"{nom} : « --essai » refuse tôt, aucune sauvegarde")
    for nom, plus, mot in (("disque au-dessus du seuil", {"disque_seuil": 1}, "disque plein"),
                           ("seuil de disque invalide", {"disque_seuil": 101}, "disque_seuil"),
                           ("« docker system prune » dans apres", {"apres": ["docker image prune -f", "docker system prune -af"]}, "system prune"),
                           ("« system prune » dans avant", {"avant": "docker system  prune"}, "system prune"),
                           ("ancien réglage « migrer »", {"migrer": "manage.py migrate"}, "retiré"),
                           ("table de suivi au nom douteux", {"migrations_table": "t; DROP TABLE x"}, "nom SQL"),
                           ("colonne applied_by au nom douteux", {"migrations_colonne_par": "par'"}, "nom SQL")):
        c, cr, _ = prod(config(t, depot, "autre.toml", **plus), "prod", "v1.1.0")
        dire(c == 1 and mot in cr.get("motif", "") and not sauvegardes() and head() == avant, f"{nom} : refus, rien n'est fait")

    # ── 1. refus : rien n'est fait ──
    for v in ("1.1.0", "v1.1", "v01.1.0", "v1.1.0-rc1", "--essai"):
        c, cr, _ = prod(cfg, "prod", v)
        dire(c == 1 and cr.get("statut") == "refus" and "vX.Y.Z" in cr.get("motif", "") and not sauvegardes() and head() == avant,
             f"version mal formée « {v} » : refus, ni sauvegarde ni checkout")
    c, cr, _ = prod(cfg, "prod", "v7.7.7")
    dire(c == 1 and "absente" in cr.get("motif", "") and not sauvegardes(), "étiquette absente : refus, aucune sauvegarde")
    c, cr, _ = prod(cfg, "prod", "v9.0.0")
    dire(c == 1 and "hors de origin/main" in cr.get("motif", "") and not sauvegardes() and head() == avant,
         "étiquette hors de la branche principale : refus, aucune sauvegarde")
    (depot / "VERSION").write_text("modifié à la main")
    c, cr, _ = prod(cfg, "prod", "v1.1.0")
    dire(c == 1 and "modifiée" in cr.get("motif", "") and not sauvegardes(), "copie du serveur modifiée : refus, aucune sauvegarde")
    git(depot, "checkout", "-q", "--", "VERSION")
    c, cr, _ = prod(cfg, "inconnu", "v1.1.0")
    dire(c == 1 and cr.get("statut") == "refus", "verbe inconnu : refus")

    # ── commande ssh forcée ──
    for brut in ("prod v1.1.0; touch /tmp/x", "prod $(id)", "prod v1.1.0 | sh", "prod `id`"):
        c, cr, _ = prod(cfg, "--ssh", brut)
        dire(c == 1 and "ssh refusée" in cr.get("motif", "") and not sauvegardes(), f"ssh : « {brut} » refusée")
    c, cr, _ = prod(cfg, env={"SSH_ORIGINAL_COMMAND": "prod v1.1.0 && id"})
    dire(c == 1 and "ssh refusée" in cr.get("motif", ""), "ssh : SSH_ORIGINAL_COMMAND douteuse refusée")

    # ── 2. sauvegarde non vérifiée : refus, rien d'autre ──
    for temoin, mot in (("sauvegarde-vide", "vide"), ("sauvegarde-illisible", "pg_restore"), ("gpg-autre", "destinataire réglé")):
        (t / temoin).touch()
        c, cr, _ = prod(cfg, "prod", "v1.1.0")
        (t / temoin).unlink()
        dire(c == 1 and mot in cr.get("motif", "") and not sauvegardes() and not list(sv.glob("*.part")) and head() == avant
             and not jouees(), f"sauvegarde {mot} : refus, fichier retiré, rien d'autre n'est fait")

    # ── essai à blanc ──
    c, cr, _ = prod(cfg, "prod", "--essai", "v1.1.0")
    f = sv / sauvegardes()[0] if sauvegardes() else None
    dire(c == 0 and cr.get("statut") == "essai" and head() == avant and cr.get("version_avant") == "v1.0.0"
         and cr.get("commit_avant") == avant and cr.get("migrations_en_attente") == [] and not jouees(),
         "essai à blanc : vérifié et sauvegardé, rien n'a changé")
    dire(f is not None and cr.get("sauvegarde") == str(f) and stat.S_IMODE(f.stat().st_mode) == 0o600
         and stat.S_IMODE(sv.stat().st_mode) == 0o700 and b"contenu-de-base-factice" not in f.read_bytes(),
         "sauvegarde chiffrée : 600 dans un dossier 700, le clair absent du fichier")
    dire((t / "gpg-destinataires").read_text() == "cle-de-sauvegarde-essai", "chiffrée vers le destinataire de la configuration")

    # ── mise en production réussie ──
    c, cr, _ = prod(cfg, "prod", "v1.1.0")
    dire(c == 0 and cr.get("statut") == "ok" and head() == tag("v1.1.0") and cr.get("version_avant") == "v1.0.0"
         and cr.get("version_apres") == "v1.1.0" and cr.get("commit_avant") == avant and cr.get("commit_apres") == tag("v1.1.0")
         and cr.get("migrations_jouees") == [] and cr.get("restauration") is None, "prod v1.1.0 : en place, version servie vérifiée, compte rendu complet")
    dire(branche() == "main", "après un succès : la copie est sur la branche principale (pas de HEAD détachée)")
    dire(len(sauvegardes()) == 2 and all(k in cr for k in ("debut", "fin", "journal", "sauvegarde")), "une sauvegarde par passage, journal des commandes")
    c2, _, r2 = prod(cfg, "compte-rendu")
    dire(c2 == 0 and json.loads(r2.stdout).get("version_apres") == "v1.1.0", "compte-rendu : relit le dernier compte rendu (connexion coupée)")

    # ── 3. table de suivi et commandes « avant » : refus après la sauvegarde, le code ne bouge pas ──
    (t / "table-absente").touch()
    c, cr, _ = prod(cfg, "prod", "--essai", "v1.2.0")
    (t / "table-absente").unlink()
    dire(c == 1 and "illisible" in cr.get("motif", "") and head() == tag("v1.1.0"), "table de suivi illisible : refus, le code ne bouge pas")
    (t / "table.txt").write_text("")
    c, cr, _ = prod(cfg, "prod", "v1.2.0")
    (t / "table.txt").write_text("0001_initial.sql\n")
    dire(c == 1 and "vide" in cr.get("motif", "") and head() == tag("v1.1.0") and not jouees(),
         "table de suivi vide alors que des fichiers existent : refus (rien n'est rejoué)")
    c, cr, _ = prod(cfg, "prod", "--essai", "v1.2.0")
    dire(c == 0 and cr.get("migrations_en_attente") == ["0002_ajout_colonne.sql"] and not jouees() and head() == tag("v1.1.0"),
         "essai : les migrations en attente sont listées (fichier non .sql ignoré), aucune n'est jouée")
    c, cr, _ = prod(config(t, depot, "autre.toml", avant=[f"touch {td}/avant-joue", "false"]), "prod", "v1.2.0")
    dire(c == 1 and "« avant » en échec" in cr.get("motif", "") and (t / "avant-joue").exists() and head() == tag("v1.1.0") and not jouees(),
         "commande « avant » en échec : refus, le code ne bouge pas")

    # ── 6. retour arrière ──
    (t / "construction-cassee").touch()
    c, cr, _ = prod(cfg, "prod", "v1.2.0")
    (t / "construction-cassee").unlink()
    dire(c == 2 and cr.get("statut") == "retour-arriere" and head() == tag("v1.1.0") and cr.get("version_apres") == "v1.1.0"
         and cr.get("restauration") is None and not jouees(), "construction en échec : retour au commit d'avant, base non touchée, pas de restauration à faire")
    dire(branche() == "main" and f"git checkout -B main {tag('v1.1.0')}" in (cr.get("retour_arriere") or ""),
         "retour arrière : la branche principale au commit d'avant (pas de HEAD détachée), commande donnée de même")
    (t / "sante-figee").touch()
    c, cr, _ = prod(cfg, "prod", "v1.2.0")
    (t / "sante-figee").unlink()
    dire(c == 2 and head() == tag("v1.1.0") and cr.get("migrations_jouees") == ["0002_ajout_colonne.sql"] and jouees(),
         "santé qui ne sert pas la version : retour arrière après migrations")
    dire("--decrypt" in (cr.get("restauration") or "") and cr.get("sauvegarde", "?") in (cr.get("restauration") or "")
         and "pg_restore --clean" in (cr.get("restauration") or ""), "migrations jouées : la commande exacte de restauration est donnée, jamais lancée")
    (t / "table.txt").write_text("0001_initial.sql\n")  # la base restaurée à la main : 0002 de nouveau en attente
    (t / "demarrage-casse").touch()
    c, cr, _ = prod(cfg, "prod", "v1.2.0")
    (t / "demarrage-casse").unlink()
    dire(c == 3 and cr.get("statut") == "retour-arriere-echoue" and "RETOUR ARRIÈRE EN ÉCHEC" in cr.get("motif", "")
         and cr.get("restauration"), "retour arrière en échec : dit clairement (code 3), restauration donnée")

    # ── 4. migrations : jouées une par une et inscrites ; commandes « apres » ──
    git(depot, "checkout", "-q", "-B", "main", tag("v1.1.0")); (t / "sante.json").write_text('{"version": "v1.1.0"}')
    (t / "table.txt").write_text("0001_initial.sql\n"); (t / "joue.log").unlink(); (t / "inscrit.log").unlink(missing_ok=True)
    c, cr, _ = prod(config(t, depot, "autre.toml", apres=[f"touch {td}/apres-joue", "false"]), "prod", "v1.2.0")
    dire(c == 0 and cr.get("statut") == "ok" and head() == tag("v1.2.0") and branche() == "main"
         and cr.get("migrations_jouees") == ["0002_ajout_colonne.sql"] and table() == ["0001_initial.sql", "0002_ajout_colonne.sql"]
         and (t / "joue.log").read_text().split() == ["0002_ajout_colonne.sql"] and cr.get("restauration") is None,
         "migration factice jouée (psql --single-transaction) et inscrite dans la table de suivi, version en place")
    dire((t / "inscrit.log").read_text().splitlines() == ["(name) ('0002_ajout_colonne.sql')"],
         "applied_by non réglé (colonne absente de la table) : seul le nom est inscrit")
    dire((t / "apres-joue").exists() and cr.get("apres_en_echec") == ["false"] and "« apres » en échec" in cr.get("motif", ""),
         "commandes « apres » jouées après le succès ; un échec est signalé, la version reste en place")

    # ── 5. connexion ssh coupée en pleine construction : le script va au bout ──
    lent = config(t, depot, "autre.toml", construire=f"touch {td}/construction-commencee; sleep 2")
    p = subprocess.Popen([sys.executable, str(PROD), "--config", str(lent), "--ssh", "prod v1.3.0"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    for _ in range(400):
        if (t / "construction-commencee").exists(): break
        time.sleep(0.05)
    p.stdout.close(); p.stderr.close(); os.killpg(p.pid, signal.SIGHUP)  # ce que fait sshd quand la connexion tombe
    p.wait(timeout=60)
    c2, _, r2 = prod(cfg, "compte-rendu")
    try: cl = json.loads(r2.stdout)
    except ValueError: cl = {}
    dire((t / "construction-commencee").exists() and cl.get("statut") == "ok" and cl.get("version_apres") == "v1.3.0"
         and head() == tag("v1.3.0") and branche() == "main", "ssh coupée en pleine construction : la mise en production va au bout, compte-rendu la relit")

    # ── migration en erreur : retour arrière du code, restauration donnée ──
    c, cr, _ = prod(cfg, "prod", "v1.4.0")
    dire(c == 2 and cr.get("statut") == "retour-arriere" and head() == tag("v1.3.0") and branche() == "main"
         and cr.get("version_apres") == "v1.3.0" and cr.get("migrations_jouees") == [] and "0003_casse.sql" not in table()
         and "erreur factice" in cr.get("motif", ""), "migration en erreur : non inscrite, retour arrière du code au commit d'avant")
    dire("--decrypt" in (cr.get("restauration") or "") and cr.get("sauvegarde", "?") in (cr.get("restauration") or ""),
         "migration en erreur : la commande de restauration de la base est donnée")

    # ── migration qui gère sa transaction (BEGIN; … COMMIT;) ; applied_by ; nom à apostrophe ──
    (t / "mode.log").unlink(missing_ok=True); (t / "inscrit.log").unlink(missing_ok=True)
    c, cr, _ = prod(config(t, depot, "autre.toml", migrations_colonne_par="applied_by"), "prod", "v1.5.0")
    modes = (t / "mode.log").read_text().split() if (t / "mode.log").exists() else []
    inscrits = (t / "inscrit.log").read_text().splitlines() if (t / "inscrit.log").exists() else []
    dire(c == 0 and cr.get("migrations_jouees") == ["0004_sa_transaction.sql", "0004b_simple.sql"]
         and modes == ["sa-transaction", "inscription", "transaction-unique"]
         and table()[-2:] == ["0004_sa_transaction.sql", "0004b_simple.sql"],
         "migration avec son propre BEGIN/COMMIT : jouée SANS --single-transaction, puis inscrite ; la suivante dans une transaction unique")
    dire(inscrits == ["(name, applied_by) ('0004_sa_transaction.sql', 'berger-prod v1.5.0')",
                      "(name, applied_by) ('0004b_simple.sql', 'berger-prod v1.5.0')"],
         "applied_by réglé : rempli « berger-prod <version> » dans les deux cas")
    c, cr, _ = prod(cfg, "prod", "--essai", "v1.6.0")
    dire(c == 1 and "apostrophe" in cr.get("motif", "") and "0005_l'apostrophe.sql" in cr.get("motif", "") and head() == tag("v1.5.0"),
         "nom de migration avec une apostrophe : refus (jamais dans l'INSERT, jamais ignoré en silence)")

    # ── controles_sante (ex. un service annexe qui réutilise l'image d'un autre) : comptent pour le retour arrière ──
    c, cr, _ = prod(config(t, depot, "autre.toml", controles_sante=["true", f"test -e {td}/annexe-saine"]), "prod", "v1.7.0")
    dire(c == 2 and cr.get("statut") == "retour-arriere" and head() == tag("v1.5.0") and branche() == "main"
         and "contrôle de santé" in cr.get("motif", "") and "annexe-saine" in cr.get("motif", ""),
         "controles_sante : un contrôle qui ne passe pas dans le délai → retour arrière au commit d'avant")
    essai3 = f"n=$(cat {td}/essais 2>/dev/null || echo 0); echo $((n+1)) > {td}/essais; [ \"$n\" -ge 2 ]"
    c, cr, _ = prod(config(t, depot, "autre.toml", controles_sante=essai3), "prod", "v1.7.0")
    dire(c == 0 and cr.get("statut") == "ok" and head() == tag("v1.7.0") and (t / "essais").read_text().strip() == "3",
         "controles_sante : rejoué jusqu'à réussir dans le délai (ici au 3e essai), version en place")
    c, cr, _ = prod(config(t, depot, "autre.toml", controles_sante="docker system prune -f"), "prod", "v1.7.0")
    dire(c == 1 and "system prune" in cr.get("motif", ""), "controles_sante : « system prune » refusé comme dans avant / apres")

    # ── verrou ──
    with open(sv / ".berger-prod.verrou", "w") as v:
        fcntl.flock(v, fcntl.LOCK_EX)
        c, cr, _ = prod(cfg, "prod", "v1.1.0")
    dire(c == 1 and "déjà en cours" in cr.get("motif", ""), "une seconde mise en production en même temps : refusée")
    dire(len(list((sv / "comptes-rendus").glob("*.json"))) >= 1, "comptes rendus gardés dans le dossier des sauvegardes")
    jl = (sv / "berger-prod.log").read_text().splitlines() if (sv / "berger-prod.log").exists() else []
    dire(len(jl) >= 10 and " ok v1.1.0 " in "\n".join(jl) and " retour-arriere v1.2.0 " in "\n".join(jl), "journal du serveur : une ligne par passage, refus compris (dès que les réglages sont lus)")

    # ── générique : ni adresse ni nom propre à une installation ──
    # Les noms de projet ne s'écrivent pas ici (le dépôt resterait marqué) : ceux de l'installation viennent de ses
    # marques_privees (config.toml de l'installation qui joue ce test, jamais versionné) ; une copie sans config.toml ne
    # contrôle que les adresses et domaines, et verifier-depot contrôle les marques de tout le dépôt.
    try:
        import tomllib
        marques = [m for m in tomllib.loads((Path(os.environ.get("BERGER_DIR", SRC)) / "config.toml").read_text()).get("marques_privees", [])
                   if isinstance(m, str) and len(m) >= 3]
    except (OSError, ValueError): marques = []
    motif = r"\b\d{1,3}(\.\d{1,3}){3}\b|\.fr\b|\.com\b|\w@\w" + "".join("|" + re.escape(m) for m in marques)
    for f in (PROD, PROD.with_name("berger-prod.exemple.toml")):
        texte = f.read_text()
        dire(not re.search(motif, texte, re.I), f"{f.name} générique : aucune adresse, domaine ni nom de projet ({len(marques)} marque(s) privée(s) cherchée(s))")

# ── gpg RÉEL (clé jetable) : le serveur n'a que la clé PUBLIQUE ; le propriétaire déchiffre avec la sienne ──
with tempfile.TemporaryDirectory() as td:
    t = Path(td); os.environ["T_PROD"] = td
    g, srv = t / "g", t / "srv"; g.mkdir(mode=0o700); srv.mkdir(mode=0o700)
    cle = subprocess.run(["gpg", "--homedir", str(g), "--batch", "--passphrase", "", "--quick-gen-key", "essai-sauvegarde@exemple.invalid",
                          "default", "default", "never"], capture_output=True, text=True) if shutil.which("gpg") else None
    if not cle or cle.returncode != 0:
        print("NON JOUÉ gpg réel : clé jetable impossible ici (agent gpg interdit par le bac à sable ?) — joué par la porte du chef de projet")
    else:
        pub = subprocess.run(["gpg", "--homedir", str(g), "--batch", "--armor", "--export", "essai-sauvegarde@exemple.invalid"], capture_output=True).stdout
        subprocess.run(["gpg", "--homedir", str(srv), "--batch", "--import"], input=pub, capture_output=True)
        secretes = subprocess.run(["gpg", "--homedir", str(srv), "--batch", "--list-secret-keys"], capture_output=True, text=True).stdout
        faux(t); depot = depot_jetable(t); (t / "sante.json").write_text('{"version": "v1.0.0"}')
        cfg = config(t, depot, gpg="gpg", gpg_home=str(srv), gpg_destinataire="essai-sauvegarde@exemple.invalid")
        c, cr, _ = prod(cfg, "prod", "--essai", "v1.1.0")
        f = Path(cr.get("sauvegarde") or "/inexistant")
        clair = subprocess.run(["gpg", "--homedir", str(g), "--batch", "--decrypt", str(f)], capture_output=True).stdout if f.exists() else b""
        dire(c == 0 and not secretes.strip() and f.exists() and b"contenu-de-base-factice" not in f.read_bytes(),
             "gpg réel : serveur SANS clé privée, sauvegarde chiffrée et contrôlée")
        dire(clair == b"PGDMP contenu-de-base-factice", "gpg réel : le propriétaire la déchiffre à l'identique avec SA clé")
        (t / "sv2").mkdir(); cfg = config(t, depot, gpg="gpg", gpg_home=str(srv), gpg_destinataire="inconnu-du-trousseau", sauvegardes=str(t / "sv2"))
        c, cr, _ = prod(cfg, "prod", "--essai", "v1.1.0")
        dire(c == 1 and not list((t / "sv2").glob("base-*")), "gpg réel : destinataire absent du trousseau → refus, aucun fichier")
        for h in (g, srv): subprocess.run(["gpgconf", "--homedir", str(h), "--kill", "all"], capture_output=True)

# ── par le courtier : le chef de projet seul, chaque lancement validé par le propriétaire ──
APPEL = r'''
import json, runpy, sys, time
g = runpy.run_path(sys.argv[1], run_name="essai")
agent, req = sys.argv[2], json.loads(sys.argv[3])
d = g["AGENTS"] / agent / "courrier"; (d / "encours").mkdir(parents=True, exist_ok=True)
f = d / "encours" / "1.json"; f.write_text(json.dumps(req))
g["traiter"](agent, f, {})
for _ in range(600):
    r = d / "reponses" / "1.json"
    if r.exists(): print(r.read_text()); r.unlink(); break
    time.sleep(0.1)
'''
with tempfile.TemporaryDirectory() as td:
    m = Path(td); i = m / "berger"; _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}")
    # Faux ssh : rejoue ce que fait la clé à commande forcée du serveur (berger-prod --ssh "<commande reçue>").
    (m / "faux").mkdir(); (m / "faux/ssh").write_text(f'#!/bin/sh\nfor x; do d="$x"; done\nexec "{sys.executable}" "{PROD}" --config "{m}/prod.toml" --ssh "$d"\n')
    os.chmod(m / "faux/ssh", 0o755)
    (m / "sauvegardes/comptes-rendus").mkdir(parents=True); (m / "sauvegardes/comptes-rendus/1.json").write_text('{"statut": "ok", "version_apres": "v1.1.0"}')
    (m / "prod.toml").write_text(f'depot = "{m}"\ncompose = "c"\nservice_base = "b"\nsauvegardes = "{m}/sauvegardes"\n'
                                 f'gpg_destinataire = "x"\nsante_url = "file://{m}/s"\n')
    (i / "config.toml").write_text(
        f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n\n[equipes.p]\ndepot = "{m}/depot-p"\nchef_projet = "chef"\n\n'
        f'[outils.appli-prod]\ntype = "ssh"\nhote = "serveur.exemple"\nutilisateur = "berger-prod"\ncle_fichier = "{m}/cle"\n'
        '[outils.appli-prod.lecture]\ncompte-rendu = "compte-rendu"\n'
        '[outils.appli-prod.actions]\nprod = "prod {arg}"\nessai = "prod --essai {arg}"\n')
    for a, extra in (("chef", "outils = appli-prod\n"), ("p-sujet", f"projet = p\nsujet = sujet\ncopie = {m}/c\nbranche = equipe/sujet\nport = 0\noutils = p-dev\n")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\npanneaux = claude\nheures = aucune\n{extra}")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "PATH": f"{m}/faux:{os.environ['PATH']}"}

    def appel(agent, verbe, *args):
        r = subprocess.run([sys.executable, "-c", APPEL, str(i / "courtier/courtier"), agent, json.dumps({"outil": "appli-prod", "verbe": verbe, "args": list(args)})],
                           env=env, capture_output=True, text=True, timeout=120)
        try: return json.loads(r.stdout)
        except ValueError: return {"ok": None, "erreur": (r.stderr or r.stdout)[-300:]}

    r = appel("chef", "prod", "v1.1.0")
    dire(r.get("ok") and r.get("en_attente"), "courtier : prod par le chef de projet → demande en attente de la validation du propriétaire")
    V = list((i / "courtier/validations").glob("*.json")) if (i / "courtier/validations").exists() else []
    dire(len(V) == 1 and "prod v1.1.0" in V[0].read_text(), "courtier : l'aperçu de la validation donne la commande exacte")
    r = appel("chef", "essai", "v1.1.0")
    dire(r.get("ok") and r.get("en_attente"), "courtier : l'essai à blanc aussi attend la validation (il écrit une sauvegarde)")
    r = appel("p-sujet", "prod", "v1.1.0")
    dire(r.get("ok") is False and "droit" in r.get("erreur", ""), "courtier : un développeur est refusé")
    r = appel("chef", "prod", "v1.1.0;id")
    dire(r.get("ok") is False, "courtier : argument douteux refusé")
    r = appel("chef", "compte-rendu")
    dire(r.get("ok") and '"version_apres": "v1.1.0"' in json.dumps(r.get("donnees", r)).replace('\\"', '"'),
         "courtier : compte-rendu lu par ssh (commande forcée) sans validation")

print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
