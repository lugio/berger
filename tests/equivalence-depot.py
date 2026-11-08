#!/usr/bin/env python3
"""Équivalence des verbes du dépôt (modulaire, lot 4d, partie « dépôt », docs/plans/2026-10-27-modulaire-spec.md § Tests « Équivalence des sorties ») :
`verifier-depot`, `installer`, `publier`, `sauvegarder`, `restaurer` et `verifier-sauvegarde`, mesurés sur une installation JETABLE (un dépôt git, sa forge
locale et un dépôt « en ligne »), puis comparés à ce que mesurait `main` avant le déplacement (tests/attendus/equivalence-depot.json).
Pour chaque scénario : code de sortie, sortie standard, dernière ligne d'erreur, fichiers écrits hors du produit (dossiers d'agents, état du courtier :
installations.log, notifications, dernière sauvegarde ; présence de la phrase de chiffrement, jamais elle), le commit de l'installation, de la forge et du dépôt
en ligne, les archives du WebDAV factice, et les appels (faux systemd-run, gpg, curl, secret-tool : leur verbe et leurs fichiers, jamais la phrase ni les
identifiants). Refus mesurés : dépôt qui porte une marque privée, une donnée locale ou une valeur du coffre ; avance rapide refusée ; vérification en échec
après installation (retour arrière automatique) ; publication sans dépôt en ligne ; sauvegarde sans section, envoi en échec ; vérification sans section
(l'erreur d'avant) ; restauration sans argument. GARDE PROPRE À CE TEST : ni la phrase de chiffrement ni le mot de passe du WebDAV ne paraissent dans une
sortie, un appel ou un fichier relevé.
L'instantané garde CHAQUE fichier ; un journal n'est relevé par sa fin que si son début est resté identique (renvois n° 89 et 93).
Usage : python3 tests/equivalence-depot.py               mesure ce dépôt et compare (0 = identique)
        python3 tests/equivalence-depot.py --mesurer <source>   imprime la mesure d'un autre arbre (ex. un `git archive` de main)
        python3 tests/equivalence-depot.py --produire <source> <fichier>   écrit la mesure de <source> dans <fichier> (les attendus)
Les attendus (tests/attendus/equivalence-depot.json) ont été produits sur main 4f69605, avant le lot 4d :
        d=$(mktemp -d) && git archive b8d1831 | tar -x -C "$d" && python3 tests/equivalence-depot.py --produire "$d" tests/attendus/equivalence-depot.json"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import hashlib, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ATTENDU = SRC / "tests/attendus/equivalence-depot.json"
SECRET = "MotDePasse" + "FacticeDuDav"              # sans chiffre ni signe (leçon de l'équipe)

FAUX = {
    "systemd-run": "#!/usr/bin/env python3\nimport json, os, sys\nwith open(os.environ['FAUX_TRACE'], 'a') as f: f.write(json.dumps(['systemd-run'] + sys.argv[1:]) + '\\n')\n",
    "systemctl": "#!/usr/bin/env python3\nimport json, os, sys\nwith open(os.environ['FAUX_TRACE'], 'a') as f: f.write(json.dumps(['systemctl'] + sys.argv[1:]) + '\\n')\n",
    "notify-send": "#!/bin/sh\nexit 0\n",
    # le trousseau : un fichier du faux, jamais celui de la machine
    "secret-tool": r'''#!/usr/bin/env python3
import json, os, sys
f = os.path.join(os.environ["FAUX_DIR"], "trousseau")
with open(os.environ["FAUX_TRACE"], "a") as t: t.write(json.dumps(["secret-tool", sys.argv[1]]) + "\n")
if sys.argv[1] == "lookup":
    if os.path.exists(f): print(open(f).read()); sys.exit(0)
    sys.exit(1)
if sys.argv[1] == "store": open(f, "w").write(sys.stdin.read())
''',
    # gpg symétrique factice : « chiffre » et « déchiffre » par simple copie ; la phrase lue sur stdin n'est jamais relevée
    "gpg": r'''#!/usr/bin/env python3
import json, os, shutil, sys
a = sys.argv[1:]; sys.stdin.read()
with open(os.environ["FAUX_TRACE"], "a") as t: t.write(json.dumps(["gpg", "-d" if "-d" in a else "--symmetric", os.path.basename(a[a.index("-o") + 1]), os.path.basename(a[-1])]) + "\n")
shutil.copy(a[-1], a[a.index("-o") + 1])
''',
    # le WebDAV : un dossier ; les identifiants (lus sur stdin) ne sont jamais relevés
    "curl": r'''#!/usr/bin/env python3
import json, os, shutil, sys
a = sys.argv[1:]; sys.stdin.read()
dav = os.path.join(os.environ["FAUX_DIR"], "dav"); os.makedirs(dav, exist_ok=True)
url = a[-1]; nom = url.rstrip("/").rsplit("/", 1)[-1]
methode = a[a.index("-X") + 1] if "-X" in a else ("PUT" if "-T" in a else "GET")
with open(os.environ["FAUX_TRACE"], "a") as t: t.write(json.dumps(["curl", methode, nom]) + "\n")
code, corps = "200", ""
if methode == "MKCOL": code = "405"
elif methode == "PUT":
    if os.environ.get("FAUX_CURL") == "ko": code = "500"
    else: shutil.copy(a[a.index("-T") + 1], os.path.join(dav, nom)); code = "201"
elif methode == "PROPFIND": code, corps = "207", "".join(f"<d:href>/x/{n}</d:href>" for n in sorted(os.listdir(dav)))
elif methode == "DELETE": os.remove(os.path.join(dav, nom)); code = "204"
elif methode == "GET": shutil.copy(os.path.join(dav, nom), a[a.index("-o") + 1])
sys.stdout.write(corps + ("\n" + code if "-w" in a else ""))
''',
}

LANCEUR = r'''
import json, os, sys
src = sys.argv[1]; g = {"__name__": "essai", "__file__": src}
exec(compile(open(src).read(), src, "exec"), g)
g["main"](sys.argv[2:])
'''

GENERES = ("AGENTS.md", "BERGER.md", "CLAUDE.md", ".consigne-systeme.md", ".reglages-claude.json", ".mcp.json", "config.toml", "hooks.json", "settings.json")
HORS_RACINE = {"bin", "commun", "courtier", ".local", "faux", "tmp", "herdr-plugin", ".codex", "tmp-agents", "restauree"}   # restauree : ses NOMS (plus bas)
HORS = ("courrier", ".transport")
ETAT_COURTIER = re.compile(r"\.(log|json|jsonl|txt|decision)$")


def normaliser(texte, t):
    texte = str(texte).replace(str(t), "<T>").replace(re.sub(r"[^A-Za-z0-9-]", "-", str(t)), "<CLE-T>")   # le dossier des transcriptions de l'installation
    texte = re.sub(r"\d+ fichiers suivis", "<N> fichiers suivis", texte)
    texte = re.sub(r"berger-(verif|sauvegarde)-[A-Za-z0-9_]{8}", r"berger-\1-<X>", texte)   # le dossier temporaire de la vérification          # le nombre de fichiers du PRODUIT (il change avec chaque lot)
    texte = re.sub(r"\(\d+ Ko, chiffrée\)", "(<N> Ko, chiffrée)", texte)          # la taille d'une archive (dates des fichiers)
    texte = re.sub(r"\d+/\d+ fichiers identiques", "<N>/<N> fichiers identiques", texte)
    texte = re.sub(r"\b[0-9a-f]{40}\b", "<SHA>", texte)
    texte = re.sub(r"\b[0-9a-f]{10}\b", "<SHA10>", texte)
    texte = re.sub(r"tmp-agents/[0-9a-f]{12}", "tmp-agents/<H>", texte)
    texte = re.sub(r"claude-\d+(?![\d.])", "claude-<UID>", texte)
    texte = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<UUID>", texte)
    texte = re.sub(r"\d{8}-\d{6}", "<HORODATAGE>", texte)
    texte = re.sub(r"\d{8}-\d{4}\b", "<AVANT>", texte)
    texte = re.sub(r"\d{4}-\d{2}-\d{2}[T _]\d{2}:?\d{2}(:\d{2}(\.\d+)?)?", "<DATE-HEURE>", texte)
    texte = re.sub(r"\d{4}-\d{2}-\d{2}", "<DATE>", texte)
    texte = re.sub(r"\b\d{2}/\d{2}(/\d{4})?\b", "<JJ/MM>", texte)
    texte = re.sub(r"\b\d{2}:\d{2}(:\d{2})?\b", "<HEURE>", texte)
    texte = re.sub(r"\b\d{2} h \d{2}\b", "<HEURE>", texte)
    texte = re.sub(r"\"(jusqu|depuis)\": [0-9.]+", r'"\1": <TS>', texte)
    texte = re.sub(r"line \d+", "line <N>", texte)
    texte = re.sub(r"fait \d+ octets", "fait <N> octets", texte)                     # la longueur dépend du chemin de l'installation jetable
    return re.sub(r"/tmp/[^\s\"']*herdr-absent-\d+\.sock", "<SOCKET>", texte)


def contenu(f, t):
    """Le texte normalisé d'un fichier ; les consignes et réglages régénérés (longs, du cœur des deux côtés) : leur empreinte."""
    x = normaliser(f.read_text(errors="replace"), t)
    if f.name in GENERES or len(x) > 4000: return "sha256:" + hashlib.sha256(x.encode()).hexdigest()[:16]
    return x


def _ranger(out, cle, val):
    """Chaque clé normalisée porte la LISTE ordonnée de ses fichiers (renvoi n° 89) : deux fichiers horodatés au même nom normalisé restent deux."""
    out.setdefault(cle, []).append(val)


def fichiers(t):
    """Ce que les verbes du dépôt écrivent dans l'installation jetable hors du produit (dossiers d'agents et réglages par empreinte, état du courtier, phrase
    de chiffrement : sa PRÉSENCE seulement) ; le dépôt de l'installation (HEAD par son message, état), la forge et le dépôt en ligne (main par son message) ;
    les archives du serveur WebDAV factice (leurs noms)."""
    out = {}
    for f in sorted(t.rglob("*")):
        r = f.relative_to(t)
        if r.parts[0] in HORS_RACINE and not (r.parts[0] == "courtier" and "outils" not in r.parts and (f.is_dir() or ETAT_COURTIER.search(f.name))): continue
        if r.parts[0] in (".git", "forge.git", "enligne.git", "travail", ".config") or any(x in HORS for x in r.parts): continue
        if any(p.is_symlink() for p in list(f.parents)[:len(r.parts) - 1]): continue
        if f.is_symlink(): _ranger(out, normaliser(str(r), t), "-> " + normaliser(os.readlink(f), t))
        elif f.is_dir():
            if not any(f.iterdir()): _ranger(out, normaliser(str(r) + "/", t), "<dossier>")
        elif f.is_file(): _ranger(out, normaliser(str(r), t), contenu(f, t))
    out[".config/berger"] = sorted(p.name for p in (t / ".config/berger").glob("*")) if (t / ".config/berger").is_dir() else []
    out["installation"] = [git(t, "log", "-1", "--format=%s").stdout.strip(), git(t, "status", "--porcelain", "--untracked-files=no").stdout.strip()]
    for d in ("forge.git", "enligne.git"):
        out[d] = [git(t / d, "log", "-1", "--format=%s", "main").stdout.strip()] if (t / d).is_dir() else []
    out["restauree"] = sorted(p.name for p in (t / "restauree").iterdir()) if (t / "restauree").is_dir() else []   # les données restaurées : leurs noms
    dav = t / "faux/dav"
    out["webdav"] = [normaliser(p.name, t) for p in sorted(dav.glob("*"))] if dav.is_dir() else []
    return out


def git(d, *a, **kw):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True, **kw)


def ajouts(ancien, neuf):
    """Ce qu'un scénario ajoute à un journal : la fin du fichier, SI son ancien contenu est resté identique au début ; sinon le fichier entier, marqué
    (renvoi n° 93 : une ancienne ligne altérée fait un écart et ne devient jamais, muette, la référence du scénario suivant)."""
    ancien, neuf = ancien or "", neuf or ""
    return neuf[len(ancien):] if neuf.startswith(ancien) else {"début du journal modifié": neuf}


JOURNAUX = ("courtier/installations.log", "courtier/notifications.log", "courtier/echanges.jsonl")


def controler_journal():
    """Renvoi n° 93 : une ANCIENNE ligne d'un journal altérée, puis la même ligne neuve ajoutée, doit faire un écart. → la liste des défauts."""
    ancien = "ligne ancienne\n"; ligne = "ligne neuve\n"
    return [] if ajouts(ancien, ancien + ligne) != ajouts(ancien, ancien.replace("ancienne", "ALTEREE") + ligne) else ["une ancienne ligne altérée d'un journal ne fait pas d'écart"]


def controler_instantane():
    """Leçon du renvoi n° 89 : l'instantané garde CHAQUE fichier, même quand la normalisation rend leurs noms identiques ; un fichier antérieur modifié ou
    supprimé fait un écart. → la liste des défauts (vide = l'instantané voit tout)."""
    defauts = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td); d = t / "agents/chef/memory"; d.mkdir(parents=True)
        a, b = d / "2026-10-28.md", d / "2026-10-29.md"
        a.write_text("premier"); b.write_text("second")
        depart = fichiers(t)
        a.write_text("premier, modifié")
        if fichiers(t) == depart: defauts.append("un fichier antérieur modifié ne fait pas d'écart")
        a.unlink()
        if fichiers(t) == depart: defauts.append("un fichier antérieur supprimé ne fait pas d'écart")
    return defauts


def mesurer(src):
    src = Path(src).resolve(); resultats = []
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as tmp_hors:
        t = Path(td); hors = Path(tmp_hors)
        _produit.copier(src, t, ("bin", "courtier", "commun"))
        (t / "coffre.json").write_text(json.dumps({"webdav": {"utilisateur": "quelqu-un", "mot_de_passe": SECRET}}))
        sauvegarde = ('[sauvegarde]\nwebdav = "https://dav.exemple.org/remote.php/dav/files/{utilisateur}"\ndossier = "berger/sauvegardes"\n'
                      'utilisateur_cle = "webdav.utilisateur"\nmot_de_passe_cle = "webdav.mot_de_passe"\ngarder = 2\n')
        def config(plus=""):
            (t / "config.toml").write_text(f'proprietaire = "Camille"\nmasques = []\ncoffre = "{t}/coffre.json"\nmarques_privees = ["marquedelamaison"]\n\n' + plus)
        config()
        for a in ("chef", "ouv"):
            d = t / "agents" / a; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nheures = aucune\nmoteur = claude\nmur = ouvert\n")
        faux = t / ".local/bin"; faux.mkdir(parents=True); (t / "faux").mkdir()
        for nom, texte in FAUX.items(): (faux / nom).write_text(texte); (faux / nom).chmod(0o755)
        trace = t / "faux/trace.jsonl"
        env = dict(os.environ, BERGER_DIR=str(t), HOME=str(t), PATH=f"{faux}:{os.environ['PATH']}", BERGER_NOTIFY_SEND=str(faux / "notify-send"),
                   FAUX_TRACE=str(trace), FAUX_DIR=str(t / "faux"), TMPDIR=str(hors),
                   LC_ALL="C", LANG="C", LANGUAGE="",     # git est traduit selon la locale (poste en français, runner en anglais) et sa sortie entre dans les mesures
                   GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t.invalid")
        for k in ("BERGER_AGENT", "AGENT_PANNE", "FAUX_CURL"): env.pop(k, None)
        for k in [k for k in env if k.startswith(("CLAUDE_CODE_", "CODEX_", "ENABLE_CLAUDEAI"))]: env.pop(k)
        # l'installation est un dépôt git (le produit seul) ; sa forge locale, et un dépôt « en ligne » (origin de la forge)
        git(t, "init", "-q", "-b", "main"); git(t, "add", "bin", "courtier", "commun"); git(t, "commit", "-qm", "installation")
        subprocess.run(["git", "clone", "-q", "--bare", str(t), str(t / "forge.git")], check=True, env=env)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(t / "enligne.git")], check=True, env=env)
        git(t / "forge.git", "remote", "set-url", "origin", f"file://{t}/enligne.git"); git(t / "forge.git", "push", "-q", "origin", "main")
        subprocess.run(["git", "clone", "-q", str(t / "forge.git"), str(t / "travail")], check=True, env=env)
        avant = {"fichiers": fichiers(t)}
        fuites = []

        def noter(nom, r):
            appels = [normaliser(l.replace(str(hors), "<TMP>"), t) for l in trace.read_text().splitlines()] if trace.exists() else []
            trace.unlink(missing_ok=True)
            apres = fichiers(t)
            ecrits = {k: x for k, x in apres.items() if avant["fichiers"].get(k, "∅") != x}
            for j in JOURNAUX:
                if j in ecrits and j in avant["fichiers"]: ecrits[j] = ajouts(avant["fichiers"][j][0], apres[j][0])
            ecrits.update({k: "(supprimé)" for k in avant["fichiers"] if k not in apres})
            avant["fichiers"] = apres
            err = [l for l in r.stderr.splitlines() if l.strip()]
            fin = err[0] if err and err[0].startswith("commande inconnue : ") else (err[-1] if err else "")
            phrase = (t / "faux/trousseau").read_text().strip() if (t / "faux/trousseau").exists() else None
            vu = r.stdout + r.stderr + json.dumps({k: x for k, x in ecrits.items() if k != "docs/cle.md"}) + json.dumps(appels)   # docs/cle.md : la fuite posée par le test
            if SECRET in vu or (phrase and phrase in vu): fuites.append(nom)
            ecrits = json.loads(json.dumps(ecrits).replace(SECRET, "<VALEUR DU COFFRE>"))
            resultats.append({"scenario": nom, "code": r.returncode, "stdout": normaliser(r.stdout.replace(str(hors), "<TMP>"), t),
                              "stderr_fin": normaliser(fin.replace(str(hors), "<TMP>"), t), "fichiers_ecrits": ecrits, "appels": appels})

        def cli(nom, *argv, plus=None):
            r = subprocess.run([sys.executable, "-c", LANCEUR, str(t / "bin/berger"), *argv], env={**env, **(plus or {})}, capture_output=True, timeout=900)
            r.stdout, r.stderr = r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace"); noter(nom, r)

        def pousser(message, fichier, texte):
            (t / "travail" / fichier).parent.mkdir(parents=True, exist_ok=True); (t / "travail" / fichier).write_text(texte)
            git(t / "travail", "add", "-A"); git(t / "travail", "commit", "-qm", message); git(t / "travail", "push", "-q", "origin", "main")

        # 1. verifier-depot : la neutralité du dépôt (marques, données locales, valeurs du coffre)
        cli("verifier-depot (dépôt propre)", "verifier-depot")
        cli("verifier-depot, argument ignoré", "verifier-depot", "en-trop")
        for cas, fichier, texte in (("marque privée", "docs/note.md", "voir marquedelamaison.exemple\n"), ("nom du propriétaire dans un mot", "docs/go.md", "GO_CAMILLE\n"),
                                    ("valeur du coffre", "docs/cle.md", f"x = {SECRET}\n"), ("donnée d'un agent", "agents/chef/memory/x.md", "note\n")):
            (t / fichier).parent.mkdir(parents=True, exist_ok=True); (t / fichier).write_text(texte); git(t, "add", "-f", fichier)
            cli(f"verifier-depot, {cas}", "verifier-depot")
            git(t, "rm", "-q", "--cached", fichier); (t / fichier).unlink(); avant["fichiers"] = fichiers(t)   # remis en l'état, hors relevé
        # 2. installer : avance rapide depuis la forge, vérifications, regenerer, redémarrage détaché ; retour arrière automatique
        cli("installer sans forge", "installer")
        cli("installer, trop d'arguments", "installer", str(t / "forge.git"), "main", "en-trop")
        cli("installer, forge introuvable (rien n'a changé)", "installer", str(t / "absente.git"))
        cli("installer, rien de neuf", "installer", str(t / "forge.git"))
        pousser("une note", "docs/note.md", "Une note neutre.\n")
        cli("installer (avance rapide, verifier-depot, regenerer, redémarrage lancé)", "installer", str(t / "forge.git"), "main")
        pousser("une marque", "docs/marque.md", "Chez Camille.\n")
        cli("installer, verifier-depot en échec (retour arrière automatique)", "installer", str(t / "forge.git"))
        # 3. publier : main de la forge en ligne (avance rapide seule). Relecture Codex du 4d : la publication contrôle désormais le COMMIT QUI PART ; main de
        #    la forge portait encore la marque du cas précédent (retirée de l'installation par le retour arrière, pas de la forge) et partait en ligne
        #    (avant : publié ; désormais : refusé, tests/publication.py section 11). La marque est retirée de la forge avant de mesurer la publication propre.
        pousser("marque retirée", "docs/marque.md", "Une note neutre.\n")
        cli("publier sans forge", "publier")
        cli("publier (main de la forge vers son origin)", "publier", str(t / "forge.git"))
        cli("publier, forge introuvable (échec tracé)", "publier", str(t / "absente.git"))
        # 4. sauvegarder, verifier-sauvegarde, restaurer : archive chiffrée vers le WebDAV, relue
        cli("sauvegarder sans section [sauvegarde]", "sauvegarder")
        cli("verifier-sauvegarde sans section (l'erreur d'avant)", "verifier-sauvegarde")
        config(sauvegarde)
        cli("verifier-sauvegarde, aucune archive", "verifier-sauvegarde")
        cli("sauvegarder (phrase créée dans le trousseau, envoi)", "sauvegarder")
        dav = t / "faux/dav"
        envoyees = sorted(dav.glob("*")) if dav.is_dir() else []       # la première archive devient deux archives anciennes (noms fixes : la rotation se voit)
        for p, vieux in zip(envoyees[:1], ("berger-donnees-2020-01-01_0000.tar.gz.gpg",)):
            p.rename(dav / vieux); (dav / "berger-donnees-2020-01-02_0000.tar.gz.gpg").write_bytes((dav / vieux).read_bytes())
        cli("sauvegarder (phrase existante, rotation : garder 2)", "sauvegarder")
        cli("sauvegarder, envoi en échec", "sauvegarder", plus={"FAUX_CURL": "ko"})
        cli("verifier-sauvegarde (téléchargée, déchiffrée, comparée)", "verifier-sauvegarde")
        cli("restaurer sans argument", "restaurer")
        archive = (sorted(dav.glob("*")) if dav.is_dir() else [])[-1:] or [t / "absente.tar.gz.gpg"]; archive = archive[0]
        cli("restaurer (archive locale déchiffrée)", "restaurer", str(archive), str(t / "restauree"))
        resultats.append({"scenario": "GARDE : ni la phrase ni le mot de passe du WebDAV dans une sortie, un appel ou un fichier relevé", "code": 1 if fuites else 0,
                          "stdout": "fuites : " + (", ".join(fuites) or "aucune"), "stderr_fin": "", "fichiers_ecrits": {}, "appels": []})
    return resultats


if __name__ == "__main__":
    if sys.argv[1:2] == ["--mesurer"]:
        print(json.dumps(mesurer(sys.argv[2]), ensure_ascii=False, indent=1)); sys.exit(0)
    if sys.argv[1:2] == ["--produire"] and len(sys.argv) == 4:
        Path(sys.argv[3]).write_text(json.dumps(mesurer(sys.argv[2]), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"attendus écrits : {sys.argv[3]} (mesurés sur {sys.argv[2]})"); sys.exit(0)
    defauts = controler_instantane() + controler_journal()
    for d in defauts: print(f"ÉCHEC  instantané : {d}")
    mesure, attendu = mesurer(SRC), json.loads(ATTENDU.read_text(encoding="utf-8"))
    ko = len(defauts)
    par_nom = {x["scenario"]: x for x in attendu}
    for m in mesure:
        a = par_nom.pop(m["scenario"], None)
        ok = a == m
        ko += not ok
        print(("ok     " if ok else "ÉCHEC  ") + f"{m['scenario']} : code {m['code']}, " + (m["stderr_fin"][:90] or m["stdout"].strip()[:90]))
        if not ok and a is not None:
            for k in sorted(set(a) | set(m)):
                if a.get(k) != m.get(k): print(f"         {k} : avant {json.dumps(a.get(k), ensure_ascii=False)[:400]}\n         {' ' * len(k)}   après {json.dumps(m.get(k), ensure_ascii=False)[:400]}")
    for nom in par_nom: ko += 1; print(f"ÉCHEC  {nom} : mesuré avant, absent après")
    print(f"---- {ko} écart(s) sur {len(mesure)} scénario(s)")
    sys.exit(1 if ko else 0)
