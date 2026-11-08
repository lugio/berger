#!/usr/bin/env python3
"""Extensions, lot 1 (spec docs/plans/2026-11-07-extensions-spec.md, go n° 181) : le socle et le genre skill — sans modèle, sans Herdr, installation JETABLE.

Un test par refus (rien n'est écrit : arborescence extensions/, extensions.toml et agent.conf identiques), puis ajout → liste → mise à jour → revenir →
retirer (état d'avant retrouvé à l'octet près), retour automatique quand regenerer échoue, source git, verifier-depot qui refuse extensions/,
une méthode propre (skills-agent/) contrôlée comme le catalogue, et les valeurs du coffre confinées à bin/noyau/extensions.py (jamais dans un message,
le journal ni extensions.toml). Valeurs du coffre fictives, tirées à l'exécution.
Le cœur est appelé comme le fera le service du noyau : noyau.extensions.commande_extension(args, valeurs_coffre, regenerer, agent), avec les fonctions réelles du cœur.
Usage : python3 tests/extensions.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast, hashlib, json, os, random, re, string, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def lettres(n): return "".join(random.choice(string.ascii_letters) for _ in range(n))


SECRET = "Fac" + lettres(14) + "Tice"                     # valeur fictive du coffre, tirée à l'exécution (jamais écrite dans ce fichier)
MARQUE = "Marque" + lettres(6)

PILOTE = """import json, os, runpy, sys
sys.argv = ["berger"]; g = runpy.run_path(os.environ["ESSAI_BIN"], run_name="essai")
import noyau.extensions as X
mode = os.environ.get("ESSAI_REGENERER", ""); reg = g["regenerer"]
if mode == "echec":
    def reg(): raise RuntimeError("regenerer cassé pour l'essai")
elif mode == "rien": reg = lambda: None
if os.environ.get("ESSAI_COPIE") == "alteree":                         # renvoi n° 183, point 2 : la copie posée diffère de celle vérifiée
    _vrai = X.shutil.copytree
    def _altere(src, dst, *a, **k):
        r = _vrai(src, dst, *a, **k); f = sorted(p for p in __import__("pathlib").Path(dst).rglob("*") if p.is_file())[0]; f.write_bytes(f.read_bytes() + b"x"); return r
    X.shutil.copytree = _altere
sys.exit(X.commande_extension(json.loads(os.environ["ESSAI_ARGS"]), g["valeurs_coffre"], reg, os.environ.get("BERGER_AGENT") or None))
"""


def paquet(racine, nom, version="1.0.0", genre="skill", fichiers=None, manifeste=None, droits=""):
    d = Path(racine) / f"{nom}-{version}-{lettres(4)}"; d.mkdir(parents=True)
    (d / "extension.toml").write_text(manifeste if manifeste is not None else
                                      f'nom = "{nom}"\ngenre = "{genre}"\nversion = "{version}"\ndescription = "Méthode d\'essai {nom}."\n{droits}')
    (d / "SKILL.md").write_text(f"---\nname: {nom}\ndescription: essai\n---\nMéthode d'essai {nom} {version}.\n")
    for k, v in (fichiers or {}).items():
        (d / k).parent.mkdir(parents=True, exist_ok=True)
        (d / k).write_bytes(v) if isinstance(v, bytes) else (d / k).write_text(v)
    return d


def empreinte_attendue(d):
    """Recalcul INDÉPENDANT de l'empreinte de la spec : chemin, NUL, taille, NUL, contenu ; fichiers triés par chemin."""
    h = hashlib.sha256()
    for p in sorted((p for p in Path(d).rglob("*") if p.is_file()), key=lambda p: p.relative_to(d).as_posix()):
        b = p.read_bytes(); h.update(p.relative_to(d).as_posix().encode() + b"\0" + str(len(b)).encode() + b"\0" + b)
    return h.hexdigest()


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    coffre = m / "coffre-essai.json"; coffre.write_text(json.dumps({"service": {"jeton_api": SECRET}}))
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{coffre}"\nmarques_privees = ["{MARQUE}"]\n\n'
                                   '[skills]\ninterdits = ["MOT_INTERDIT_[0-9]+"]\n')
    (i / "skills/wiki").mkdir(parents=True); (i / "skills/wiki/SKILL.md").write_text("---\nname: wiki\n---\ncatalogue\n")
    for a, skills in (("alpha", "wiki"), ("beta", ""), ("gamma", "wiki   # commentaire")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\n" + (f"skills = {skills}\n" if skills else ""))
    src = m / "sources"; src.mkdir()
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "ESSAI_BIN": str(i / "bin/berger")}
    env.pop("BERGER_AGENT", None)

    def ext(*args, agent=None, regen="", copie=""):
        e = {**env, "ESSAI_ARGS": json.dumps(list(args)), "ESSAI_REGENERER": regen, "ESSAI_COPIE": copie}
        if agent: e["BERGER_AGENT"] = agent
        r = subprocess.run([sys.executable, "-c", PILOTE], env=e, capture_output=True, text=True, timeout=300)
        return r.returncode, r.stdout + r.stderr

    def photo():
        """L'état que gère une extension : arborescence extensions/ (chemins, liens, contenus), extensions.toml, agent.conf, liens de skills."""
        out = {}
        for p in sorted((i / "extensions").rglob("*")) if (i / "extensions").exists() else []:
            if p.name == ".verrou": continue
            out[str(p.relative_to(i))] = ("lien", os.readlink(p)) if p.is_symlink() else (p.read_bytes() if p.is_file() else "dossier")
        for f in [i / "extensions.toml", *sorted((i / "agents").glob("*/agent.conf"))]:
            out[str(f.relative_to(i))] = f.read_bytes() if f.exists() else None
        for a in ("alpha", "beta", "gamma"):
            s = i / "agents" / a / ".claude/skills"
            out[f"liens-{a}"] = sorted((p.name, os.readlink(p)) for p in s.iterdir() if p.is_symlink()) if s.is_dir() else []
        return out

    def refus(texte, args, attendu, agent=None, sans=None):
        avant = photo(); c, o = ext(*args, agent=agent); apres = photo()
        ok = c != 0 and re.search(attendu, o) is not None and avant == apres and (sans is None or sans not in o)
        dire(ok, f"refus : {texte}" + ("" if ok else f" — code {c}, état {'inchangé' if avant == apres else 'MODIFIÉ'} : {' '.join(o.split())[-260:]}"))

    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=300)
    dire(r.returncode == 0, "installation jetable : regenerer réussit" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr)[-200:]}"))
    conf_alpha0 = (i / "agents/alpha/agent.conf").read_bytes(); conf_gamma0 = (i / "agents/gamma/agent.conf").read_bytes()

    # ── le premier ajout d'un genre crée extensions/<genre>/ : un retour arrière l'emporte aussi (rien de demi-installé) ──
    dp = paquet(src, "premier"); c, o = ext("ajouter", "skill", str(dp), "--agents", "alpha", regen="echec")
    dire(c != 0 and not (i / "extensions/skill").exists(), "premier ajout d'un genre en échec : extensions/skill/ ne reste pas après le retour arrière"
         + ("" if c != 0 else f" — {o[-200:]}"))

    # ── renvoi n° 183, point 4 : l'état d'avant retrouvé À L'OCTET PRÈS — agent.conf avec et sans saut de ligne final, extensions.toml absent au départ ──
    dire(not (i / "extensions.toml").exists(), "départ : extensions.toml n'existe pas")
    fb = i / "agents/beta/agent.conf"; fb.write_bytes(fb.read_bytes().rstrip(b"\n"))          # beta : SANS saut de ligne final, sans ligne skills
    octets = {a: (i / "agents" / a / "agent.conf").read_bytes() for a in ("alpha", "beta", "gamma")}
    do = paquet(src, "octet"); c, o = ext("ajouter", "skill", str(do), "--agents", "alpha,beta,gamma")
    dire(c == 0, "ajout pour alpha (ligne skills, saut final), beta (sans ligne skills ni saut final), gamma (commentaire)" + ("" if c == 0 else f" — {o[-200:]}"))
    c, o = ext("retirer", "skill", "octet")
    apres = {a: (i / "agents" / a / "agent.conf").read_bytes() for a in ("alpha", "beta", "gamma")}
    dire(c == 0 and apres == octets, "retirer : chaque agent.conf retrouvé à l'octet près, avec ou sans saut de ligne final"
         + ("" if apres == octets else f" — écarts : {[a for a in octets if apres[a] != octets[a]]}"))
    dire(not (i / "extensions.toml").exists(), "retirer la dernière extension : extensions.toml n'existe plus, comme avant le premier ajout")
    fb.write_bytes(octets["beta"] + b"\n")                                                        # la suite du test repart de beta avec son saut final

    # ── refus (un par cas de la spec, lot 1) ──
    bon = paquet(src, "demo")
    refus("ajouter, appel venu d'un agent", ("ajouter", "skill", str(bon), "--agents", "alpha"), r"réservé au propriétaire", agent="alpha")
    d = paquet(src, "sansman"); (d / "extension.toml").unlink()
    refus("manifeste absent", ("ajouter", "skill", str(d)), r"manifeste absent")
    refus("manifeste invalide (TOML cassé)", ("ajouter", "skill", str(paquet(src, "casse", manifeste="nom = \n"))), r"manifeste invalide")
    refus("manifeste invalide (genre du paquet ≠ genre demandé)", ("ajouter", "skill", str(paquet(src, "autre", genre="vue"))), r"genre vue dans le paquet")
    refus("manifeste invalide (version non SemVer)", ("ajouter", "skill", str(paquet(src, "ver", version="1.0"))), r"SemVer")
    refus("manifeste invalide (nom hors minuscules et tirets)", ("ajouter", "skill", str(paquet(src, "Mauvais_Nom"))), r"minuscules")
    refus("manifeste invalide (clé inconnue)", ("ajouter", "skill", str(paquet(src, "cle", droits='auteur = "x"\n'))), r"1 clé inconnue", sans="auteur")   # renvoi n° 183 : le nom d'une clé inconnue n'est jamais recopié
    refus("manifeste invalide (droit réseau demandé par une skill)", ("ajouter", "skill", str(paquet(src, "res", droits="[droits]\nreseau = true\n"))), r"sans objet pour le genre skill")
    refus("nom pris par une méthode du produit", ("ajouter", "skill", str(paquet(src, "berger"))), r"nom (réservé|pris)")
    refus("nom pris par le catalogue de l'installation", ("ajouter", "skill", str(paquet(src, "wiki"))), r"nom pris : wiki est une méthode du catalogue")
    refus("nom réservé", ("ajouter", "skill", str(paquet(src, "actuelle"))), r"nom réservé")
    d = paquet(src, "lien"); (d / "dehors.md").symlink_to("/etc/hostname")
    refus("lien symbolique dans le paquet", ("ajouter", "skill", str(d)), r"lien symbolique dans le paquet : dehors\.md")
    (m / "lien-source").symlink_to(bon)
    refus("source qui est un lien symbolique", ("ajouter", "skill", str(m / "lien-source")), r"lien symbolique")
    refus("source relative", ("ajouter", "skill", "sources/demo"), r"chemin absolu")
    refus("paquet trop gros (plus de 1 Mio)", ("ajouter", "skill", str(paquet(src, "gros", fichiers={"gros.bin": b"a" * (1 << 20)}))), r"trop gros")
    d = paquet(src, "fuite", fichiers={"notes/extra.txt": f"un\ndeux\nla clé est {SECRET} ici\n"})
    refus("valeur du coffre dans un fichier autre que SKILL.md (fichier, ligne et NOM de la clé ; jamais la valeur)", ("ajouter", "skill", str(d)),
          r"notes/extra\.txt, ligne 3 : valeur du coffre \(clé « service\.jeton_api »\)", sans=SECRET)
    refus("verifier : même refus, la valeur n'est pas montrée", ("verifier", "skill", str(d)), r"valeur du coffre", sans=SECRET)
    refus("nom du fichier du coffre", ("ajouter", "skill", str(paquet(src, "fcoffre", fichiers={"a.md": "voir coffre-essai.json"}))), r"a\.md, ligne 1 : fichier du coffre")
    refus("motif [skills] interdits (même dans un binaire)", ("ajouter", "skill", str(paquet(src, "motif", fichiers={"b.bin": b"\xff\x00MOT_INTERDIT_7"}))), r"b\.bin, ligne 1 : motif interdit")
    refus("marque privée", ("ajouter", "skill", str(paquet(src, "marque", fichiers={"c.md": f"x\n{MARQUE}\n"}))), r"c\.md, ligne 2 : marque privée", sans=MARQUE)
    refus("agent inconnu", ("ajouter", "skill", str(bon), "--agents", "alpha,inconnu"), r"agent inconnu : inconnu")
    refus("--reseau pour une skill", ("ajouter", "skill", str(bon), "--reseau"), r"--reseau ne vaut que pour un serveur MCP")
    refus("genre pas encore pris en charge (vue : lot 4)", ("ajouter", "vue", str(paquet(src, "unevue", genre="vue"))), r"genre vue : pas encore pris en charge \(lot 4")   # mcp : pris en charge au lot 3 (tests/extensions-mcp.py)
    refus("genre inconnu", ("ajouter", "plugin", str(bon)), r"genre inconnu")
    refus("SKILL.md absent", ("ajouter", "skill", str((lambda d: ((d / "SKILL.md").unlink(), d)[1])(paquet(src, "sansskill")))), r"SKILL\.md absent")
    depot = m / "depot"; depot.mkdir()
    g = lambda *a: subprocess.run(["git", *a], cwd=depot, capture_output=True, text=True, env={**env, "GIT_AUTHOR_NAME": "essai", "GIT_AUTHOR_EMAIL": "essai@exemple.invalid",
                                                                                         "GIT_COMMITTER_NAME": "essai", "GIT_COMMITTER_EMAIL": "essai@exemple.invalid"})
    g("init", "-q", "-b", "main"); gp = paquet(depot, "gitdemo")
    for f in gp.iterdir(): f.rename(depot / f.name)
    gp.rmdir(); g("add", "-A"); g("commit", "-q", "-m", "essai"); sha = g("rev-parse", "HEAD").stdout.strip()
    refus("source git : commit abrégé", ("ajouter", "skill", f"git:{depot}@{sha[:12]}"), r"n'est pas un commit complet")
    refus("source git : nom de branche", ("ajouter", "skill", f"git:{depot}@main"), r"n'est pas un commit complet")
    refus("source git : commit absent", ("ajouter", "skill", f"git:{depot}@{'0' * 40}"), r"commit 000000000000 absent")
    refus("retirer, appel venu d'un agent", ("retirer", "skill", "demo"), r"réservé au propriétaire", agent="alpha")
    refus("revenir, appel venu d'un agent", ("revenir", "skill", "demo"), r"réservé au propriétaire", agent="alpha")
    refus("retirer une extension absente", ("retirer", "skill", "demo"), r"aucune extension skill « demo » installée")

    # ── verifier : tous les contrôles, rien d'écrit ──
    avant = photo(); c, o = ext("verifier", "skill", str(bon), "--agents", "alpha")
    dire(c == 0 and "rien n'est écrit" in o and empreinte_attendue(bon) in o and "nouvelle extension" in o and photo() == avant,
         "verifier : passe, montre l'empreinte et ce qui serait installé, n'écrit rien" + ("" if c == 0 else f" — {o[-200:]}"))

    # ── ajouter : un socle d'abord (l'état d'avant de demo), puis demo ──
    socle = paquet(src, "socle"); c, o = ext("ajouter", "skill", str(socle))
    dire(c == 0, "ajouter une première extension (donnée à personne)" + ("" if c == 0 else f" — {o[-300:]}"))
    toml_avant = (i / "extensions.toml").read_bytes()
    c, o = ext("ajouter", "skill", str(bon), "--agents", "alpha,gamma")
    dire(c == 0 and "installée" in o, "ajouter skill demo 1.0.0 --agents alpha,gamma" + ("" if c == 0 else f" — {o[-400:]}"))
    v1 = i / "extensions/skill/demo/1.0.0"
    dire((v1 / "SKILL.md").is_file() and os.readlink(i / "extensions/skill/demo/actuelle") == "1.0.0", "fichiers copiés dans extensions/skill/demo/1.0.0/, « actuelle » désigne 1.0.0")
    dire(not (v1 / "SKILL.md").is_symlink() and (v1 / "SKILL.md").read_bytes() == (bon / "SKILL.md").read_bytes(), "copie figée (pas un lien vers la source)")
    dire(not os.access(v1 / "SKILL.md", os.W_OK) or os.geteuid() == 0, "copie en lecture seule")
    import tomllib
    x = tomllib.loads((i / "extensions.toml").read_text())["skill"]["demo"]
    dire(x["version"] == "1.0.0" and x["empreinte"] == empreinte_attendue(bon) and x["agents"] == ["alpha", "gamma"],
         f"extensions.toml : version, empreinte recalculée à part, agents ({x.get('empreinte', '')[:12]})")
    ca = (i / "agents/alpha/agent.conf").read_text(); cg = (i / "agents/gamma/agent.conf").read_text(); cb = (i / "agents/beta/agent.conf").read_text()
    dire("skills = wiki, demo\n" in ca and "skills = wiki, demo   # commentaire" in cg and "demo" not in cb,
         "agent.conf : demo ajoutée à `skills =` (commentaire gardé), seulement chez les agents nommés")
    l = i / "agents/alpha/.claude/skills/demo"
    dire(l.is_symlink() and l.resolve() == v1.resolve() and (i / "agents/alpha/.agents/skills/demo").resolve() == v1.resolve(),
         "regenerer : la skill d'extension est liée chez alpha (deux moteurs), vers la version active")
    dire(not (i / "agents/beta/.claude/skills/demo").exists(), "beta (non nommé) ne la reçoit pas")
    sauv = sorted((i / "agents/alpha").glob("agent.conf.avant-demo-*"))
    dire(len(sauv) == 1 and sauv[0].read_bytes() == conf_alpha0, "sauvegarde vérifiée de agent.conf avant l'écriture (.avant-demo-<date>)")
    dire(len(list(i.glob("extensions.toml.avant-demo-*"))) == 1, "sauvegarde de extensions.toml avant l'écriture")
    j = (i / "courtier/extensions.log").read_text() if (i / "courtier/extensions.log").is_file() else ""
    dire(re.search(r"\tajoutee\tskill\tdemo\t1\.0\.0\t[0-9a-f]{12}\tagents=alpha,gamma\tdroits=aucun", j) is not None, "journal : une ligne (geste, genre, nom, version, empreinte, agents, droits)")

    c, o = ext("liste")
    dire(c == 0 and re.search(r"skill\s+demo\s+1\.0\.0\s+[0-9a-f]{12}\s+active", o) and "alpha, gamma" in o, "liste : genre, nom, version, empreinte courte, état, agents")
    c, o = ext("liste", "--json"); lj = json.loads(o) if c == 0 else []
    dire(any(e["nom"] == "demo" and e["empreinte"] == empreinte_attendue(bon) for e in lj), "liste --json : l'empreinte complète")

    refus("version égale à l'actuelle", ("ajouter", "skill", str(paquet(src, "demo", "1.0.0"))), r"pas plus récente")
    refus("version plus ancienne", ("ajouter", "skill", str(paquet(src, "demo", "0.9.0"))), r"pas plus récente")
    refus("revenir sans version précédente", ("revenir", "skill", "demo"), r"aucune version précédente")

    # ── mise à jour, puis revenir ──
    b2 = paquet(src, "demo", "1.1.0"); c, o = ext("ajouter", "skill", str(b2))
    dire(c == 0 and os.readlink(i / "extensions/skill/demo/actuelle") == "1.1.0" and l.resolve() == (i / "extensions/skill/demo/1.1.0").resolve(),
         "mise à jour 1.1.0 : actuelle et lien suivent, les agents gardent le droit" + ("" if c == 0 else f" — {o[-300:]}"))
    dire(v1.is_dir(), "la version précédente est gardée")
    c, o = ext("revenir", "skill", "demo")
    dire(c == 0 and os.readlink(i / "extensions/skill/demo/actuelle") == "1.0.0" and l.resolve() == v1.resolve(), "revenir : 1.0.0 redevient active" + ("" if c == 0 else f" — {o[-300:]}"))
    os.chmod(v1, 0o755); os.chmod(v1 / "SKILL.md", 0o644); (v1 / "SKILL.md").write_text("modifiée après coup\n"); os.chmod(v1 / "SKILL.md", 0o444); os.chmod(v1, 0o555)
    c, o = ext("ajouter", "skill", str(b2))
    dire(c == 0, "après revenir : la 1.1.0 gardée se réinstalle (même empreinte)" + ("" if c == 0 else f" — {o[-300:]}"))
    refus("revenir vers une version dont l'empreinte a changé", ("revenir", "skill", "demo"), r"empreinte changée")

    # ── retour automatique quand regenerer échoue ──
    for mode, cause in (("echec", "regenerer en échec"), ("rien", "n'est pas liée chez beta")):
        avant = photo(); c, o = ext("ajouter", "skill", str(paquet(src, "rate")), "--agents", "beta", regen=mode)
        dire(c != 0 and cause in o and "retour automatique" in o and photo() == avant and not (i / "extensions/skill/rate/1.0.0").exists(),
             f"regenerer {mode} : refus nommé, retour automatique, rien de demi-installé" + ("" if c != 0 and photo() == avant else f" — {o[-300:]}"))

    # ── retirer : état d'avant à l'octet près ──
    c, o = ext("retirer", "skill", "demo")
    dire(c == 0, "retirer skill demo" + ("" if c == 0 else f" — {o[-300:]}"))
    dire((i / "agents/alpha/agent.conf").read_bytes() == conf_alpha0 and (i / "agents/gamma/agent.conf").read_bytes() == conf_gamma0,
         "agent.conf d'alpha et de gamma : à l'octet près comme avant l'ajout")
    dire((i / "extensions.toml").read_bytes() == toml_avant, "extensions.toml : à l'octet près comme avant l'ajout")
    dire(not (i / "extensions/skill/demo").exists() and any((p / "1.0.0/SKILL.md").is_file() for p in (i / "extensions/.retirees").glob("skill-demo-*")),
         "fichiers déplacés dans extensions/.retirees/ (jamais effacés)")
    dire(not (i / "agents/alpha/.claude/skills/demo").exists(), "regenerer : plus de lien chez alpha")

    # ── source git ──
    c, o = ext("ajouter", "skill", f"git:{depot}@{sha}", "--agents", "beta")
    dire(c == 0 and (i / "agents/beta/.claude/skills/gitdemo").resolve() == (i / "extensions/skill/gitdemo/1.0.0").resolve(),
         "source git:<dépôt>@<commit complet> : installée et liée" + ("" if c == 0 else f" — {o[-300:]}"))
    dire((i / "extensions.toml").read_text().count(f"\"{empreinte_attendue(i / 'extensions/skill/gitdemo/1.0.0')}\"") >= 1, "source git : l'empreinte est celle du commit installé")
    c, o = ext("retirer", "skill", "gitdemo")
    dire(c == 0 and "skills" not in (i / "agents/beta/agent.conf").read_text(), "retirer : la ligne `skills =` créée par Berger disparaît")

    # ── renvoi n° 183, point 3 : aucune valeur du coffre ni marque cachée dans un échappement TOML, un nom de fichier ou une clé inconnue ──
    esc = lambda x: "".join(f"\\u{ord(ch):04x}" for ch in x)
    for quoi, cache in (("valeur du coffre", SECRET), ("marque privée", MARQUE)):
        dm = paquet(src, "echappe", manifeste=f'nom = "echappe"\ngenre = "skill"\nversion = "1.0.0"\ndescription = "Note {esc(cache)}."\n')
        refus(f"{quoi} cachée par des échappements \\uXXXX dans la description (contrôlée DÉCODÉE)", ("ajouter", "skill", str(dm)), r"extension\.toml", sans=cache)
        dg = paquet(src, "echappe-genre", manifeste=f'nom = "echappe-genre"\ngenre = "{esc(cache)}"\nversion = "1.0.0"\ndescription = "x"\n')
        refus(f"{quoi} dans un genre inconnu : le refus ne la recopie pas", ("verifier", "skill", str(dg)), r"genre", sans=cache)
        df = paquet(src, "nom-fichier", fichiers={f"notes-{cache}.md": "rien\n"})
        refus(f"{quoi} dans un NOM de fichier : refusée, jamais recopiée", ("verifier", "skill", str(df)), r"nom de fichier", sans=cache)
        dk = paquet(src, "cle-inconnue", manifeste=f'nom = "cle-inconnue"\ngenre = "skill"\nversion = "1.0.0"\ndescription = "x"\n{cache} = "x"\n')
        refus(f"{quoi} comme clé inconnue du manifeste : le refus en donne le nombre, jamais le nom", ("verifier", "skill", str(dk)), r"1 clé inconnue", sans=cache)
        dd = paquet(src, "droit-inconnu", manifeste=f'nom = "droit-inconnu"\ngenre = "skill"\nversion = "1.0.0"\ndescription = "x"\n[droits]\n{cache} = true\n')
        refus(f"{quoi} comme droit inconnu : jamais recopié", ("verifier", "skill", str(dd)), r"droit inconnu", sans=cache)
        dl = paquet(src, "lien-nomme"); (dl / f"lien-{cache}").symlink_to(dl / "SKILL.md")
        refus(f"{quoi} dans le nom d'un lien symbolique : refusé, le nom masqué", ("verifier", "skill", str(dl)), r"lien symbolique", sans=cache)

    # ── renvoi n° 183, point 2 : la copie INSTALLÉE est celle vérifiée — empreinte recalculée sur la copie finale ; parcours de la source par dir_fd ──
    dp = paquet(src, "posee"); avant2 = photo(); c, o = ext("ajouter", "skill", str(dp), "--agents", "beta", copie="alteree")
    dire(c != 0 and "empreinte" in o and photo() == avant2, "copie finale différente de la copie vérifiée : refusée, rien d'installé, état d'avant" + ("" if c != 0 else f" — {o[-200:]}"))
    src_cop = ast.get_source_segment((SRC / "bin/noyau/extensions.py").read_text(encoding="utf-8"), next(
        f for f in ast.walk(ast.parse((SRC / "bin/noyau/extensions.py").read_text(encoding="utf-8"))) if isinstance(f, ast.FunctionDef) and f.name == "_copier_sans_lien")) or ""
    dire("dir_fd" in src_cop and "O_DIRECTORY" in src_cop and "os.walk" not in src_cop, "la source est parcourue par descripteurs de dossier (dir_fd, O_DIRECTORY | O_NOFOLLOW) : un parent remplacé n'est pas suivi")

    # ── renvoi n° 183, point 1 : ecrire_aussi ne mène JAMAIS à extensions/ ni à extensions.toml (et ses sauvegardes), ni par un parent, un lien ou « .. » ──
    (i / "extensions").mkdir(exist_ok=True); lien = i / "raccourci-ext"
    if not lien.is_symlink(): lien.symlink_to(i / "extensions")
    lien_toml = i / "raccourci-toml"
    if not lien_toml.is_symlink(): lien_toml.symlink_to(i / "extensions.toml")
    prop = ("import json, os, runpy, sys\nsys.argv = ['berger']; g = runpy.run_path(os.environ['ESSAI_BIN'], run_name='essai')\n"
            "print(json.dumps(g['controler_proposition']('alpha', 'nouvelle', {'agent.conf': 'nom = Nouvelle\\nmoteur = claude\\nheures = aucune\\necrire_aussi = ' + os.environ['ESSAI_CHEMIN'] + '\\n', 'SOUL.md': 'x\\n'})))\n")
    def motifs_ecrire(chemin):
        r = subprocess.run([sys.executable, "-c", prop], env={**env, "ESSAI_CHEMIN": chemin}, capture_output=True, text=True, timeout=300)
        try: return [x for x in json.loads(r.stdout.strip().splitlines()[-1]) if "ecrire_aussi" in x]
        except (ValueError, IndexError): return ["illisible : " + r.stderr[-200:]]
    dire(motifs_ecrire(str(i / "agents/nouvelle/notes")) == [], "ecrire_aussi : un chemin permis de l'installation reste accepté (témoin)")
    for nom_cas, chemin in (("extensions/", i / "extensions"), ("une copie figée", i / "extensions/skill/demo/1.0.0"),
                            ("extensions.toml", i / "extensions.toml"), ("une sauvegarde extensions.toml.avant-*", i / "extensions.toml.avant-demo-202611070000"),
                            ("« .. »", f"{i}/agents/../extensions/skill"), ("un lien vers extensions/", lien / "skill"), ("un lien vers extensions.toml", lien_toml)):
        mo = motifs_ecrire(str(chemin))
        dire(any("extensions" in x for x in mo), f"ecrire_aussi vers {nom_cas} : proposition refusée, motif nommé ({mo})")
    lien.unlink(); lien_toml.unlink()

    # ── de bout en bout par la commande : berger extension → famille extensions → service gerer_extension → noyau/extensions.py ──
    def berger(*args, agent=None):
        e = {**env, "BERGER_AGENT": agent} if agent else env
        r = subprocess.run([sys.executable, str(i / "bin/berger"), "extension", *args], env=e, capture_output=True, text=True, timeout=300)
        return r.returncode, r.stdout + r.stderr
    dc = paquet(src, "cli")
    avant = photo(); c, o = berger("ajouter", "skill", str(dc), "--agents", "beta", agent="beta")
    dire(c == 1 and "réservé au propriétaire" in o and photo() == avant, "berger extension ajouter, lancé par un agent (BERGER_AGENT) : refusé, état inchangé"
         + ("" if c == 1 else f" — {o[-200:]}"))
    c, o = berger("ajouter", "skill", str(dc), "--agents", "beta")
    dire(c == 0 and (i / "agents/beta/.claude/skills/cli").resolve() == (i / "extensions/skill/cli/1.0.0").resolve(),
         "berger extension ajouter (propriétaire, au terminal) : installée et liée" + ("" if c == 0 else f" — {o[-300:]}"))
    c, o = berger("liste", "--json")
    dire(c == 0 and any(x.get("nom") == "cli" for x in json.loads(o or "[]")), "berger extension liste --json : la nouvelle extension y figure")
    c, o = berger("retirer", "skill", "cli", agent="beta")
    dire(c == 1 and "réservé au propriétaire" in o and (i / "extensions/skill/cli/actuelle").exists(), "berger extension retirer, lancé par un agent : refusé")
    c, o = berger("retirer", "skill", "cli")
    dire(c == 0 and not (i / "agents/beta/.claude/skills/cli").exists(), "berger extension retirer (propriétaire) : lien retiré" + ("" if c == 0 else f" — {o[-200:]}"))
    c, o = berger("inconnu")
    dire(c == 1 and "refusé" in o and "berger extension" in o, "berger extension <verbe inconnu> : refus nommé, l'usage rappelé")

    # ── aucune valeur du coffre hors du module ──
    traces = "".join(p.read_text(errors="ignore") for p in [i / "extensions.toml", i / "courtier/extensions.log", *i.glob("extensions.toml.avant-*")] if p.is_file())
    dire(SECRET not in traces and MARQUE not in traces, "aucune valeur du coffre ni marque dans extensions.toml, ses sauvegardes ou le journal")
    arbre = ast.parse((SRC / "bin/noyau/extensions.py").read_text(encoding="utf-8"))
    appels = [f.name for f in ast.walk(arbre) if isinstance(f, ast.FunctionDef)
              for n in ast.walk(f) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "valeurs_coffre"]
    cc = next(f for f in ast.walk(arbre) if isinstance(f, ast.FunctionDef) and f.name == "controler_contenu")
    noms_fstr = {n.id for s in ast.walk(cc) if isinstance(s, ast.JoinedStr) for n in ast.walk(s) if isinstance(n, ast.Name)}
    rend = [n for n in ast.walk(cc) if isinstance(n, ast.Return) and n.value is not None]
    fr = next((f for f in ast.walk(arbre) if isinstance(f, ast.FunctionDef) and f.name == "_filtrer_refus"), None)
    rend_fr = [ast.unparse(n.value) for n in ast.walk(fr) if isinstance(n, ast.Return)] if fr else ["absente"]
    fstr_fr = {n.id for s in ast.walk(fr) if isinstance(s, ast.JoinedStr) for n in ast.walk(s) if isinstance(n, ast.Name)} if fr else set()
    dire(sorted(appels) == ["_filtrer_refus", "controler_contenu"] and not noms_fstr & {"v", "valeurs", "t", "data"} and not rend
         and rend_fr == ["texte"] and not fstr_fr,
         "noyau/extensions.py : les valeurs du coffre ne sont lues que dans controler_contenu (ne les rend pas, ne les met dans aucun message) et "
         "_filtrer_refus (rend seulement le texte où elles sont masquées)" + ("" if sorted(appels) == ["_filtrer_refus", "controler_contenu"] else f" — lues dans {appels}"))
    dire("valeurs_coffre" not in (SRC / "bin/noyau/api.py").read_text(), "les valeurs du coffre ne passent pas par l'API du noyau")

dire("extensions/" in (SRC / "bin/berger").read_text().split("interdits_chemins = re.compile(", 1)[1].split("\n", 1)[0]
     and "extensions\\.toml" in (SRC / "bin/berger").read_text().split("interdits_chemins = re.compile(", 1)[1].split("\n", 1)[0],
     "verifier-depot : un fichier de extensions/ ou extensions.toml forcé dans le dépôt serait refusé")
g = subprocess.run(["git", "-C", str(SRC), "check-ignore", "-q", "extensions/skill/x/1.0.0/SKILL.md"], capture_output=True)
g2 = subprocess.run(["git", "-C", str(SRC), "check-ignore", "-q", "extensions.toml"], capture_output=True)
dire(g.returncode == 0 and g2.returncode == 0, "dépôt : extensions/ et extensions.toml sont ignorés par git (liste blanche du .gitignore)")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
