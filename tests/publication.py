#!/usr/bin/env python3
"""Tests de la publication vers le dépôt en ligne (29/10/2026) — SANS réseau : une forge nue et un « en ligne » nu (file://),
dans un dossier jetable ; faux systemctl / systemd-run ; un faux git qui trace chaque commande puis appelle le vrai.
Spec : docs/plans/2026-10-29-publication-github-spec.md. Vécu : après les fusions n° 48, 54, 74/75, 80, 82 et 84, la forge locale
était à jour, rien n'était parti en ligne ; `publier` visait un remote `publication` qui n'existait pas.
1. option `publication` absente → aucune commande réseau, aucune ligne de publication ;
2. avance rapide → `publié : …`, en ligne = commit installé, étiquette ancêtre en ligne, forge/main contrôlé ;
3. étiquette différente en ligne → `publication échouée : étiquette vX différente en ligne`, jamais remplacée ;
4. `berger publier <forge>` (action manuelle) → la même fonction, la même trace ; remote en miroir refusé ;
5. courtier non resté actif → retour arrière, AUCUNE publication ;
6. divergence → refus sans force, en ligne inchangé, ligne d'échec, notification urgente ;
7. remote absent → `publication échouée : remote absent (origin)`, aucun push tenté ;
8. installer passe `--publier <forge>` au redémarrage seulement si l'option est active ; un nouvel essai le garde ;
9. config.exemple.toml : plus de remote `publication`, `publier` = la commande de Berger ;
10. renvoi n° 90 (relecture de Codex) : destinations d'envoi multiples ou différentes (pushurl) refusées avant tout envoi ;
    push.followTags sans effet (--no-follow-tags), étiquettes poussées par OID figé ; SHA installé vide → aucun push (jamais
    « :refs/heads/main ») ; un jeton factice n'apparaît dans aucun journal ni notification ; for-each-ref en échec = échec
    notifié ; contrôle par ls-remote (une référence périmée ne fait pas « publié ») ; l'option est celle de l'équipe de CETTE
    forge (deux équipes) ; OSError, journal illisible ou notify-send muet : tracé, notifié, borné, redémarrage à 0.
Jamais `--force`, `--mirror` ni refspec en « + » dans les commandes tracées ; seules les NOUVELLES notifications comptent.
Usage : python3 tests/publication.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import os, re, shutil, subprocess, sys, tempfile, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0
ENV_GIT = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
VRAI_GIT = shutil.which("git")


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def git(d, *a): return subprocess.run([VRAI_GIT, "-C", str(d), *a], capture_output=True, text=True, env={**os.environ, **ENV_GIT})


# ── 9. config.exemple.toml ──
exemple = (SRC / "config.exemple.toml").read_text()
dire("remote add publication" not in exemple and "push -q publication" not in exemple,
     "config.exemple.toml : plus de remote `publication` (la forge n'a qu'origin)")
lignes = [l.lstrip("# ").strip() for l in exemple.splitlines() if l.lstrip("# ").startswith("publier =")]
dire(lignes == ['publier = "bin/berger publier ~/projets/berger.git"'], f"config.exemple.toml : publier = la commande de Berger ({lignes})")
dire(any(l.lstrip("# ").startswith('publication = "origin"') for l in exemple.splitlines()),
     "config.exemple.toml : option `publication` montrée (commentée : absente par défaut)")

# Écart de place (docs/plans/2026-10-27-modulaire-decisions.md) : le code est dans bin/noyau/publication.py, module du cœur
module = (SRC / "bin/noyau/publication.py").read_text()
sys.path.insert(0, str(SRC / "bin")); from noyau import api as _api
dire("def publier_forge(" in module and "def publier_forge(" not in (SRC / "bin/berger").read_text(),
     "écart de place : publier_forge est dans bin/noyau/publication.py, plus dans bin/berger")
import ast
importes = {(n.module or "") if isinstance(n, ast.ImportFrom) else al.name for n in ast.walk(ast.parse(module))
            if isinstance(n, (ast.Import, ast.ImportFrom)) for al in n.names}
dire(importes and all(x.startswith("noyau.") or x in ("contextlib", "datetime", "io", "os", "re", "subprocess") for x in importes) and "run_path" not in module,
     f"noyau/publication.py n'importe que le noyau et la bibliothèque standard, jamais bin/berger ({sorted(importes)})")
publics = set(re.findall(r"^def (\w+)\(", module, re.M)) | {"INSTALLATIONS"}
dire(not publics & set(_api.API) and "publication" not in (SRC / "bin/noyau/api.py").read_text(),
     "noyau/publication.py hors de l'API du noyau : jamais exposé aux vues ni aux familles")

with tempfile.TemporaryDirectory() as t:
    m = Path(t); forge, enligne, i, graine = m / "projets/berger.git", m / "enligne.git", m / "berger", m / "graine"
    subprocess.run([VRAI_GIT, "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run([VRAI_GIT, "init", "-q", "--bare", "-b", "main", str(enligne)])
    subprocess.run([VRAI_GIT, "clone", "-q", str(forge), str(graine)], capture_output=True)
    _produit.copier(SRC, graine, ("bin", "courtier", "commun"))
    git(graine, "add", "-A"); git(graine, "commit", "-qm", "produit"); git(graine, "push", "-q", "origin", "main")
    git(forge, "remote", "add", "origin", f"file://{enligne}")                       # comme la vraie forge : un seul remote, origin
    git(forge, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/forge/*")
    git(forge, "push", "-q", "origin", "main")                                          # point de départ commun
    subprocess.run([VRAI_GIT, "clone", "-q", str(forge), str(i)], capture_output=True)
    (m / "coffre.json").write_text("{}")
    d = i / "agents/admin"; (d / "memory").mkdir(parents=True)
    (d / "agent.conf").write_text("nom = Admin\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\n")

    def configurer(publication=None, attente=None, avant=""):
        """[equipes.berger] EST l'installation : son dépôt (l'installation, origin = la forge) la lie à CETTE forge ; `avant` :
        des équipes écrites AVANT elle (renvoi n° 90 : l'option n'était prise que dans la première équipe à installer_outil)."""
        (i / "config.toml").write_text(f'proprietaire = "Zephyrin"\nmasques = []\ncoffre = "{m}/coffre.json"\n'
                                       + (f"[courtier]\nredemarrage_attente = {attente}\n" if attente is not None else "") + avant
                                       + f'[equipes.berger]\ninstaller_outil = "berger-admin installer"\nfusion_par = "proprietaire"\ndepot = "{i}"\n'
                                       + (f'publication = "{publication}"\n' if publication is not None else ""))

    b = m / ".local/bin"; b.mkdir(parents=True)
    (b / "systemd-run").write_text(f'#!/bin/sh\necho "$@" >> "{m}/systemd-run.log"\nexit 0\n')
    (b / "systemctl").write_text(f'#!/bin/sh\necho "$@" >> "{m}/systemctl.log"\n'
                                 f'if [ "$2" = is-active ]; then cat "{m}/etat-courtier" 2>/dev/null || echo active; fi\nexit 0\n')
    # faux git : trace chaque commande ; des marques le font échouer (renvoi n° 90) : HEAD illisible sans sortie, for-each-ref en
    # échec, push muet (rend 0 sans rien envoyer), push en échec qui écrit sur stderr le contenu de push-sortie (jeton factice)
    (b / "git").write_text(f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> "{m}/git.log"\ncase "$*" in\n'
                           f'  *" rev-parse HEAD") [ -f "{m}/tete-vide" ] && exit 128;;\n'
                           f'  *" for-each-ref "*) [ -f "{m}/foreach-ko" ] && exit 1;;\n'
                           f'  *" push "*) [ -f "{m}/push-muet" ] && exit 0; [ -f "{m}/push-sortie" ] && {{ cat "{m}/push-sortie" >&2; exit 128; }};;\n'
                           f'esac\nexec "{VRAI_GIT}" "$@"\n')
    for x in ("systemd-run", "systemctl", "git"): os.chmod(b / x, 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": str(m / "absent"), "BERGER_NOTIFY_SEND": str(m / "absent"),
           "BERGER_CONTROLE_PAUSE": "0", "BERGER_REDEMARRAGE_PAS": "0", **ENV_GIT}
    env.pop("BERGER_AGENT", None)
    configurer()
    sonde = subprocess.run([sys.executable, "-c", "import runpy,shutil;runpy.run_path(%r,run_name='x');print(shutil.which('systemctl'));print(shutil.which('git'))"
                            % str(i / "bin/berger")], env=env, capture_output=True, text=True)
    if sonde.stdout.split() != [str(b / "systemctl"), str(b / "git")]: sys.exit(f"ARRÊT : Berger prendrait le vrai systemctl ou git ({sonde.stdout.split() or sonde.stderr[-200:]})")
    berger = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=300)
    tete = lambda: git(i, "rev-parse", "HEAD").stdout.strip()
    enligne_main = lambda: git(enligne, "rev-parse", "refs/heads/main").stdout.strip()
    log = lambda: (i / "courtier/installations.log").read_text() if (i / "courtier/installations.log").exists() else ""
    notes = lambda: (i / "courtier/notifications.log").read_text() if (i / "courtier/notifications.log").exists() else ""
    gitlog = lambda: (m / "git.log").read_text() if (m / "git.log").exists() else ""
    reseau = lambda texte: [l for l in texte.splitlines() if any(f" {v} " in f" {l} " for v in ("push", "fetch", "ls-remote"))]
    sans_force = lambda texte: not [l for l in texte.splitlines() if "--force" in l or "--mirror" in l or " +" in l or " -f " in f" {l} "]
    n = [0]
    vu = [0]                                     # notifications déjà là : seules les NOUVELLES comptent (renvoi n° 90, P2-9)
    nouvelles = lambda: notes()[vu[0]:]
    pousse = lambda texte: [l for l in texte.splitlines() if " push " in f" {l} "]

    def nouveau():
        """Un commit de plus dans la forge, installé (avance rapide) : → (avant, apres)."""
        n[0] += 1; avant = tete()
        (graine / f"commun/n{n[0]}.md").write_text(f"nouveauté {n[0]}\n")
        git(graine, "add", "-A"); git(graine, "commit", "-qm", f"nouveauté {n[0]}"); git(graine, "push", "-q", "origin", "main")
        git(i, "pull", "-q", "--ff-only", str(forge), "main"); return avant, tete()

    def redemarrer(avant):
        (m / "git.log").unlink(missing_ok=True); avant_log = log(); vu[0] = len(notes())
        r = berger("courtier", "redemarrer", "--controle", avant, "--publier", str(forge))
        return r, log()[len(avant_log):], gitlog()

    # 1. option absente → rien en ligne
    avant, apres = nouveau(); depart = enligne_main()
    r, ajout, g = redemarrer(avant)
    dire(r.returncode == 0 and "courtier redémarré" in ajout and "publi" not in ajout, "option absente : redémarré, aucune ligne de publication"
         + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr)[-300:]}"))
    dire(not reseau(g) and enligne_main() == depart, "option absente : aucune commande réseau, en ligne inchangé")

    # 2. avance rapide → publié, étiquette ancêtre en ligne
    configurer("origin")
    git(graine, "tag", "-a", "v0.1.0", "-m", "Version 0.1.0", "HEAD"); git(graine, "push", "-q", "origin", "refs/tags/v0.1.0")
    avant, apres = nouveau()
    r, ajout, g = redemarrer(avant)
    dire(r.returncode == 0 and f"publié : {apres[:10]} → origin" in ajout, "avance rapide : « publié : <commit> → origin » dans installations.log"
         + ("" if f"publié : {apres[:10]}" in ajout else f" — {ajout[-300:]} {(r.stdout + r.stderr)[-300:]}"))
    dire(enligne_main() == apres, "avance rapide : en ligne/main = le commit INSTALLÉ")
    dire(git(enligne, "rev-parse", "-q", "--verify", "refs/tags/v0.1.0").returncode == 0, "avance rapide : l'étiquette ancêtre v0.1.0 est en ligne")
    dire(git(forge, "rev-parse", "refs/remotes/forge/main").stdout.strip() == apres, "avance rapide : forge/main relu après l'envoi (contrôlé)")
    dire(any(f"push --porcelain --no-follow-tags origin {apres}:refs/heads/main" in l for l in g.splitlines()) and sans_force(g),
         "avance rapide : push du SHA vers refs/heads/main, sans force ni « + »")
    dire("publication" not in nouvelles(), "avance rapide : aucune notification d'échec")

    # 3. étiquette différente en ligne → jamais remplacée
    autre = m / "autre"; subprocess.run([VRAI_GIT, "clone", "-q", str(enligne), str(autre)], capture_output=True)
    git(autre, "tag", "-a", "v0.1.1", "-m", "autre", "HEAD~1"); git(autre, "push", "-q", "origin", "refs/tags/v0.1.1")
    git(graine, "tag", "-a", "v0.1.1", "-m", "Version 0.1.1", "HEAD"); git(graine, "push", "-q", "origin", "refs/tags/v0.1.1")
    en_ligne_tag = git(enligne, "rev-parse", "refs/tags/v0.1.1").stdout.strip()
    avant, apres = nouveau(); r, ajout, g = redemarrer(avant)
    dire("publication échouée : étiquette v0.1.1 différente en ligne" in ajout and git(enligne, "rev-parse", "refs/tags/v0.1.1").stdout.strip() == en_ligne_tag
         and sans_force(g), "étiquette différente en ligne : échec nommé, étiquette en ligne NON remplacée" + ("" if "v0.1.1" in ajout else f" — {ajout[-300:]}"))
    git(forge, "tag", "-d", "v0.1.1")

    # 4. publier (action manuelle) : la même fonction ; miroir refusé
    (m / "git.log").unlink(missing_ok=True); avant_log = log()
    r = berger("publier", str(forge)); ajout = log()[len(avant_log):]
    dire(r.returncode == 0 and f"publié : {apres[:10]} → origin" in ajout and enligne_main() == apres,
         "publier (manuel) : main de la forge publié, même ligne de trace" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr)[-300:]}"))
    git(forge, "config", "remote.origin.mirror", "true"); (m / "git.log").unlink(missing_ok=True); avant_log = log()
    r = berger("publier", str(forge)); ajout = log()[len(avant_log):]
    dire(r.returncode != 0 and "publication échouée" in ajout and "miroir" in ajout and not [l for l in gitlog().splitlines() if " push " in f" {l} "],
         "remote en miroir : refusé avant tout push")
    git(forge, "config", "--unset", "remote.origin.mirror")

    # 5. courtier non resté actif → retour arrière, aucune publication
    avant, apres = nouveau(); depart = enligne_main(); (m / "etat-courtier").write_text("failed\n")
    r, ajout, g = redemarrer(avant)
    dire(r.returncode == 1 and tete() == avant and "publi" not in ajout and not reseau(g) and enligne_main() == depart,
         "courtier inactif : retour arrière, AUCUNE publication" + ("" if r.returncode == 1 else f" — {(r.stdout + r.stderr)[-300:]}"))
    (m / "etat-courtier").unlink()

    # 11. relecture Codex du 4d (07/11) : verifier-depot est REJOUÉ juste avant l'envoi, automatique ET manuel, sur le COMMIT QUI PART (lu dans la
    #     forge), jamais sur l'arbre installé. Sale (une donnée privée suivie : le nom du propriétaire) → refus net : nommé, code ≠ 0, aucun push, en
    #     ligne inchangé, tracé et notifié. Propre → le contrôle du commit a joué, puis UN push de main.
    controle_avant_push = lambda g: (lambda l: any("cat-file --batch" in x for x in l[:next((k for k, x in enumerate(l) if " push " in f" {x} "), len(l))]))(g.splitlines())
    pousse_main = lambda g: [l for l in pousse(g) if l.endswith(":refs/heads/main")]
    def commit_graine(fichier, texte, installer=True):
        """Un commit de la graine (ajout, ou retrait si texte est None) poussé dans la forge ; installé (avance rapide) si demandé. → (avant, apres)."""
        avant = tete()
        if texte is None: git(graine, "rm", "-q", fichier)
        else: (graine / fichier).write_text(texte); git(graine, "add", fichier)
        git(graine, "commit", "-qm", f"essai {fichier}"); git(graine, "push", "-q", "origin", "main")
        if installer: git(i, "pull", "-q", "--ff-only", str(forge), "main")
        return avant, git(graine, "rev-parse", "HEAD").stdout.strip()
    avant, apres = commit_graine("commun/prive.md", "note de Zephyrin\n"); depart = enligne_main()
    r, ajout, g = redemarrer(avant)
    dire(r.returncode != 0 and "publication échouée" in ajout and "verifier-depot" in ajout and not pousse(g) and enligne_main() == depart,
         f"11 automatique, commit installé sale : refus nommé (verifier-depot), code ≠ 0, aucun push, en ligne inchangé (code {r.returncode} ; {ajout.strip()[-160:]!r} ; {len(pousse(g))} push)")
    dire("commun/prive.md" in r.stdout and any("URGENT" in l and "verifier-depot" in l for l in nouvelles().splitlines()),
         "11 automatique, commit sale : le fichier fautif est nommé, notification urgente")
    (m / "git.log").unlink(missing_ok=True); avant_log = log(); vu[0] = len(notes())
    r = berger("publier", str(forge)); ajout = log()[len(avant_log):]
    dire(r.returncode != 0 and "verifier-depot" in ajout and "commun/prive.md" in r.stdout and not pousse(gitlog()) and enligne_main() == depart,
         f"11 manuel (berger publier), main de la forge sale : refus nommé, code ≠ 0, aucun push (code {r.returncode} ; {len(pousse(gitlog()))} push)")
    avant, apres = commit_graine("commun/prive.md", None)
    r, ajout, g = redemarrer(avant)
    dire(r.returncode == 0 and f"publié : {apres[:10]}" in ajout and len(pousse_main(g)) == 1 and controle_avant_push(g) and enligne_main() == apres,
         f"11 automatique, commit propre : verifier-depot joué sur le commit avant l'envoi, puis UN push de main ({len(pousse_main(g))} push de main ; contrôle avant : {controle_avant_push(g)})")
    # main de la forge EN AVANCE sur l'installation, avec une donnée privée ; l'arbre installé est propre : refus, code 1, zéro push
    propre = apres; depart = enligne_main(); _, prive = commit_graine("commun/prive.md", "note de Zephyrin\n", installer=False)
    dire(tete() == propre and git(forge, "rev-parse", "refs/heads/main").stdout.strip() == prive, "11 : la forge a main en avance (donnée privée), l'installation reste propre")
    (m / "git.log").unlink(missing_ok=True); avant_log = log()
    r = berger("publier", str(forge)); ajout = log()[len(avant_log):]
    dire(r.returncode == 1 and "verifier-depot" in ajout and "commun/prive.md" in r.stdout and not pousse(gitlog()) and enligne_main() == depart,
         f"11 manuel, main de la forge en avance et sale, installation propre : refus, code 1, aucun push (code {r.returncode} ; {len(pousse(gitlog()))} push ; {ajout.strip()[-120:]!r})")
    git(forge, "update-ref", "refs/heads/main", propre, prive); git(graine, "reset", "-q", "--hard", propre)   # la forge revient au commit propre
    avant, apres = nouveau(); (m / "git.log").unlink(missing_ok=True)
    r = berger("publier", str(forge))
    dire(r.returncode == 0 and len(pousse_main(gitlog())) == 1 and controle_avant_push(gitlog()) and enligne_main() == apres and "dépôt propre" not in r.stdout,
         f"11 manuel, commit propre : verifier-depot joué sur le commit avant l'envoi, UN push de main, sortie inchangée ({len(pousse_main(gitlog()))} ; {controle_avant_push(gitlog())} ; {r.stdout.strip()[-120:]!r})")

    # 10. renvoi n° 90 (relecture de Codex), chaque point d'abord rouge
    def echoue(g, ajout, quoi):
        """Échec nommé, AUCUN push tenté, une NOUVELLE notification urgente, en ligne inchangé."""
        return ("publication échouée" in ajout and quoi in ajout and not pousse(g) and enligne_main() == depart
                and any("URGENT" in l and "publication échouée" in l for l in nouvelles().splitlines()))

    # P1-1 : destinations d'envoi effectives (pushurl) — plusieurs, ou autre que l'URL du remote → refus avant tout envoi
    public = m / "public.git"; subprocess.run([VRAI_GIT, "init", "-q", "--bare", "-b", "main", str(public)])
    git(forge, "config", "--add", "remote.origin.pushurl", f"file://{enligne}"); git(forge, "config", "--add", "remote.origin.pushurl", f"file://{public}")
    depart = enligne_main(); avant, apres = nouveau(); r, ajout, g = redemarrer(avant)
    dire(r.returncode == 0 and echoue(g, ajout, "destinations") and git(public, "rev-parse", "-q", "--verify", "refs/heads/main").returncode,
         "pushurl multiples : « publication échouée : destinations… », aucun push, notifié" + ("" if "destinations" in ajout else f" — {ajout[-300:]}"))
    git(forge, "config", "--unset-all", "remote.origin.pushurl"); git(forge, "config", "remote.origin.pushurl", f"file://{public}")
    r, ajout, g = redemarrer(avant)
    dire(echoue(g, ajout, "destination") and git(public, "rev-parse", "-q", "--verify", "refs/heads/main").returncode,
         "pushurl différente de l'URL du remote (lue au contrôle) : refusée avant tout envoi" + ("" if "destination" in ajout else f" — {ajout[-300:]}"))
    git(forge, "config", "--unset-all", "remote.origin.pushurl")

    # P1-2 : HEAD de l'installation illisible, sans sortie → jamais « :refs/heads/main » (une suppression de branche)
    depart = enligne_main(); avant, apres = nouveau(); (m / "tete-vide").touch(); r, ajout, g = redemarrer(avant); (m / "tete-vide").unlink()
    dire(echoue(g, ajout, "commit") and not [l for l in g.splitlines() if " :refs/" in l] and r.returncode == 0,
         "SHA installé vide : refusé (SHA complet et commit existant exigés), aucun push, branche en ligne intacte"
         + ("" if "publication échouée" in ajout else f" — {ajout[-300:]} {(r.stdout + r.stderr)[-200:]}"))

    # P1-3 : la sortie de git n'est écrite que masquée — un jeton factice n'apparaît dans aucun journal ni notification
    jeton = "gh" + "p_" + "jetonfacticedutest" * 2                              # construit à l'exécution, sans chiffre
    for sortie, quoi in ((f"fatal: unable to access 'https://porteur:{jeton}@exemple.invalid/depot.git/': Permission denied (publickey)", "clé refusée"),
                         (f"remote: refus inattendu token={jeton} pour https://porteur:{jeton}@exemple.invalid/depot.git {jeton}", "publication échouée")):
        (m / "push-sortie").write_text(sortie + "\n"); r, ajout, g = redemarrer(avant); (m / "push-sortie").unlink()
        dire(quoi in ajout and "publication échouée" in ajout and jeton not in log() and jeton not in notes() and jeton not in r.stdout + r.stderr
             and "jetonfacticedutest" not in log() + notes() + r.stdout + r.stderr,
             f"jeton factice ({quoi}) : absent d'installations.log, des notifications et de la sortie" + ("" if quoi in ajout else f" — {ajout[-300:]}"))

    # P2-6 : for-each-ref en échec → échec notifié, jamais « publié » sans les étiquettes
    (m / "foreach-ko").touch(); r, ajout, g = redemarrer(avant); (m / "foreach-ko").unlink()
    dire(echoue(g, ajout, "étiquettes") and "publié" not in ajout, "for-each-ref en échec : « publication échouée : étiquettes… », aucun push, notifié"
         + ("" if "étiquettes" in ajout else f" — {ajout[-300:]}"))

    # P1-5 : push.followTags ne fait partir aucune étiquette non v* ; les v* partent par leur OID figé
    git(forge, "config", "push.followTags", "true")
    git(graine, "tag", "-a", "interne-confidentiel", "-m", "interne", "HEAD"); git(graine, "push", "-q", "origin", "refs/tags/interne-confidentiel")
    avant, apres = nouveau(); r, ajout, g = redemarrer(avant)
    oid = git(forge, "rev-parse", "refs/tags/v0.1.0").stdout.strip()
    dire(f"publié : {apres[:10]}" in ajout and git(enligne, "rev-parse", "-q", "--verify", "refs/tags/interne-confidentiel").returncode != 0,
         "push.followTags=true : l'étiquette annotée interne-confidentiel N'EST PAS en ligne" + ("" if "publié" in ajout else f" — {ajout[-300:]}"))
    dire(pousse(g) and all("--no-follow-tags" in l for l in pousse(g)) and any(f"{oid}:refs/tags/v0.1.0" in l for l in pousse(g)) and sans_force(g),
         "tous les push portent --no-follow-tags ; v0.1.0 part par son OID contrôlé (<oid>:refs/tags/v0.1.0)")
    git(forge, "config", "--unset", "push.followTags"); git(forge, "tag", "-d", "interne-confidentiel")

    # P2-7 : le contrôle relit le dépôt en ligne (ls-remote), pas une référence locale périmée
    git(forge, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    depart = enligne_main(); avant, apres = nouveau(); git(forge, "update-ref", "refs/remotes/forge/main", apres)
    (m / "push-muet").touch(); r, ajout, g = redemarrer(avant); (m / "push-muet").unlink()
    dire("publication échouée : contrôle" in ajout and "publié" not in ajout and enligne_main() == depart
         and any("URGENT" in l and "publication échouée" in l for l in nouvelles().splitlines()),
         "push muet + forge/main périmée = le commit : « publication échouée : contrôle… », pas « publié »" + ("" if "contrôle" in ajout else f" — {ajout[-300:]}"))
    git(forge, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/forge/*")

    # P1-4 : l'option est celle de l'équipe de CETTE forge (son dépôt a la forge pour origin) ; deux équipes sur elle = refus
    ailleurs = m / "ailleurs"; subprocess.run([VRAI_GIT, "init", "-q", str(ailleurs)]); git(ailleurs, "remote", "add", "origin", str(m / "ailleurs.git"))
    configurer("origin", avant=f'[equipes.autre]\ninstaller_outil = "autre-admin installer"\ndepot = "{ailleurs}"\npublication = "inexistant"\n')
    r, ajout, g = redemarrer(avant)
    dire(f"publié : {apres[:10]} → origin" in ajout and enligne_main() == apres,
         "deux équipes : l'option est prise dans l'équipe liée à la forge, pas dans la première" + ("" if "publié" in ajout else f" — {ajout[-300:]}"))
    configurer("origin", avant=f'[equipes.autre]\ninstaller_outil = "autre-admin installer"\ndepot = "{i}"\npublication = "origin"\n')
    depart = enligne_main(); avant, apres = nouveau(); r, ajout, g = redemarrer(avant)
    dire(r.returncode == 0 and echoue(g, ajout, "ambigu"), "deux équipes à installer_outil sur la même forge : ambiguïté refusée, notifiée, aucun push"
         + ("" if "ambigu" in ajout else f" — {ajout[-300:]}"))
    configurer("origin")

    # P2-8 : OSError, journal illisible, publier sans main, notify-send muet → tracé (si possible), notifié, borné, redémarrage à 0
    def module(code, **plus):
        return subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {str(i / 'bin')!r})\nfrom noyau.publication import *\n"
                               f"import noyau.publication as P, subprocess as S\n{code}"], env={**env, **plus}, capture_output=True, text=True, timeout=120)
    vu[0] = len(notes()); avant_log = log()
    r = module(f"vrai = S.run\ndef run(a, *k, **kw):\n    if 'push' in a: raise PermissionError('refusé')\n    return vrai(a, *k, **kw)\n"
               f"S.run = run\nprint('code', publier_installation({str(forge)!r}, {apres!r}, {avant!r}, lambda **k: 0))")
    dire("code 0" in r.stdout and "publication échouée" in log()[len(avant_log):] and "publication échouée" in nouvelles(),
         "OSError pendant le push : « publication échouée », notifiée, code 0" + ("" if "code 0" in r.stdout else f" — {r.stderr[-300:]}"))
    vu[0] = len(notes())
    r = module(f"from pathlib import Path\nP.INSTALLATIONS = Path({str(m)!r})\nS.run = lambda *a, **k: (_ for _ in ()).throw(OSError('disque'))\n"
               f"print('code', publier_installation({str(forge)!r}, {apres!r}, {avant!r}, lambda **k: 0))")
    dire("code 0" in r.stdout and "publication échouée" in nouvelles(), "installations.log illisible et git impossible : notifié quand même, code 0"
         + ("" if "code 0" in r.stdout else f" — {r.stderr[-300:]}"))
    vide = m / "vide.git"; subprocess.run([VRAI_GIT, "init", "-q", "--bare", "-b", "main", str(vide)])
    vu[0] = len(notes()); avant_log = log(); r = berger("publier", str(vide))
    dire(r.returncode == 1 and "publication échouée" in log()[len(avant_log):] and "publication échouée" in nouvelles(),
         "publier sans main : tracé ET notifié (plus seulement un message)")
    muet = m / "notify-muet"; muet.write_text("#!/bin/sh\nsleep 60\n"); os.chmod(muet, 0o755)
    vu[0] = len(notes()); import time; t0 = time.monotonic()
    r = module("from noyau.bandeaux import notifier\nnotifier('Berger · essai', 'notify-send muet', urgent=True)", BERGER_NOTIFY_SEND=str(muet))
    dire(r.returncode == 0 and time.monotonic() - t0 < 30 and "notify-send muet" in nouvelles(), f"notify-send muet : borné ({time.monotonic() - t0:.0f} s), journal écrit")

    # 6. divergence → refus sans force, ligne d'échec, notification urgente
    git(autre, "pull", "-q", "--ff-only", "origin", "main")
    (autre / "en-ligne.md").write_text("changé en ligne\n"); git(autre, "add", "-A"); git(autre, "commit", "-qm", "en ligne"); git(autre, "push", "-q", "origin", "main")
    diverge = enligne_main(); avant, apres = nouveau(); r, ajout, g = redemarrer(avant)
    dire(r.returncode == 0 and tete() == apres and "publication échouée : divergence" in ajout,
         "divergence : « publication échouée : divergence », installation gardée, code 0" + ("" if "divergence" in ajout else f" — {ajout[-300:]}"))
    dire(enligne_main() == diverge and sans_force(g), "divergence : en ligne inchangé, aucune force ni « + »")
    dire(any("URGENT" in l and "publication échouée" in l and "divergence" in l for l in nouvelles().splitlines()),
         "divergence : NOUVELLE notification URGENTE au propriétaire, qui nomme la divergence")

    # 7. remote absent → échec nommé, aucun push tenté
    git(forge, "remote", "remove", "origin")
    avant, apres = nouveau(); r, ajout, g = redemarrer(avant)
    dire("publication échouée : remote absent (origin)" in ajout and not [l for l in g.splitlines() if " push " in f" {l} "],
         "remote absent : « publication échouée : remote absent (origin) », aucun push tenté" + ("" if "remote absent" in ajout else f" — {ajout[-300:]}"))

    # 8. installer passe --publier seulement si l'option est active ; un nouvel essai le garde
    def installe():
        (m / "systemd-run.log").unlink(missing_ok=True); n[0] += 1
        (graine / f"commun/i{n[0]}.md").write_text("installé\n")
        git(graine, "add", "-A"); git(graine, "commit", "-qm", f"i{n[0]}"); git(graine, "push", "-q", "origin", "main")
        r = berger("installer", str(forge), "main")
        return r, (m / "systemd-run.log").read_text() if (m / "systemd-run.log").exists() else ""
    r, lance = installe()
    dire(r.returncode == 0 and f"--publier {forge}" in lance, "installer, option active : le redémarrage reçoit --publier <forge>"
         + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr)[-300:]}"))
    configurer(); r, lance = installe()
    dire(r.returncode == 0 and "courtier redemarrer --controle" in lance and "--publier" not in lance, "installer, option absente : pas de --publier")
    configurer("origin", attente=0); (i / "courtier/validations").mkdir(parents=True, exist_ok=True)
    (i / "courtier/validations/9.execution").write_text("{}"); (m / "systemd-run.log").unlink(missing_ok=True)
    r = berger("courtier", "redemarrer", "--controle", tete(), "--publier", str(forge))
    lance = (m / "systemd-run.log").read_text() if (m / "systemd-run.log").exists() else ""
    dire(r.returncode == 1 and f"--publier {forge}" in lance and "--essai 2" in lance, "redémarrage abandonné : le nouvel essai garde --publier <forge>")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
