#!/usr/bin/env python3
"""Équivalence des verbes des secrets (modulaire, lot 4d, partie « secrets », docs/plans/2026-10-27-modulaire-spec.md § Tests « Équivalence des sorties ») :
`secrets audit` et `coffre sauvegarder|purger`, mesurés sur une installation JETABLE, puis comparés à ce que mesurait `main` avant le déplacement
(tests/attendus/equivalence-secrets.json).
Pour chaque scénario : code de sortie, sortie standard, dernière ligne d'erreur, fichiers écrits dans l'installation jetable hors du produit (résultat de l'audit,
copies chiffrées du coffre et leur purge) et les appels (faux `age` : son destinataire et ses fichiers, jamais le contenu du coffre). Refus mesurés : forme
inconnue, destinataire absent ou invalide, motif invalide, `age` absent, chiffrement en échec, copie non conforme (en-tête, taille). Audit : sans fuite, puis
une valeur du coffre dans le dossier d'un agent et dans une transcription de moteur (nommés par la CLÉ, jamais la valeur), une valeur faite de mots ordinaires
(pas un secret). GARDE PROPRE À CE TEST : aucune valeur du coffre ne paraît dans une sortie ni dans un relevé de fichier écrit par berger (contrôlé à chaque
scénario, avant et après le déplacement).
L'instantané garde CHAQUE fichier (copies horodatées du coffre comprises) ; un journal n'est relevé par sa fin que si son début est resté identique.
Usage : python3 tests/equivalence-secrets.py               mesure ce dépôt et compare (0 = identique)
        python3 tests/equivalence-secrets.py --mesurer <source>   imprime la mesure d'un autre arbre (ex. un `git archive` de main)
        python3 tests/equivalence-secrets.py --produire <source> <fichier>   écrit la mesure de <source> dans <fichier> (les attendus)
Les attendus (tests/attendus/equivalence-secrets.json) ont été produits sur main 4f69605, avant le lot 4d :
        d=$(mktemp -d) && git archive b8d1831 | tar -x -C "$d" && python3 tests/equivalence-secrets.py --produire "$d" tests/attendus/equivalence-secrets.json"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import hashlib, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ATTENDU = SRC / "tests/attendus/equivalence-secrets.json"
SECRET = "Jeton" + "FacticeDuCoffre"                 # sans chiffre ni signe (leçon de l'équipe) ; ni un simple mot, ni une URL : une valeur « secrète »
ORDINAIRE = "client credentials ordinaires"          # une valeur faite de mots ordinaires : jamais prise pour un secret

FAUX = {
    "age": r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(["age", a[a.index("-r") + 1], os.path.basename(a[a.index("-o") + 1]), os.path.basename(a[-1])]) + "\n")
mode = os.environ.get("FAUX_AGE", "ok")
if mode == "ko": sys.exit(1)
taille = os.path.getsize(a[-1])
with open(a[a.index("-o") + 1], "wb") as f: f.write(b"age-encryption.org/v1\n" + (b"x" * taille if mode == "ok" else b""))
''',
    "notify-send": "#!/bin/sh\nexit 0\n",
}

LANCEUR = r'''
import json, os, sys
src = sys.argv[1]; g = {"__name__": "essai", "__file__": src}
exec(compile(open(src).read(), src, "exec"), g)
g["main"](sys.argv[2:])
'''

GENERES = ("AGENTS.md", "BERGER.md", "CLAUDE.md", ".consigne-systeme.md", ".reglages-claude.json", ".mcp.json", "config.toml", "hooks.json", "settings.json")
HORS_RACINE = {"bin", "commun", "courtier", ".local", "faux", "tmp", "herdr-plugin"}
HORS = ("courrier", ".transport")
ETAT_COURTIER = re.compile(r"\.(log|json|jsonl|txt|decision)$")


def normaliser(texte, t):
    texte = str(texte).replace(str(t), "<T>").replace(re.sub(r"[^A-Za-z0-9-]", "-", str(t)), "<CLE-T>")   # le dossier des transcriptions de l'installation
    texte = re.sub(r"cherchées dans \d+ fichiers", "cherchées dans <N> fichiers", texte)   # le nombre de fichiers du PRODUIT copié (il change avec chaque lot)
    texte = re.sub(r"(\d+ valeurs, )\d+ fichiers", r"\1<N> fichiers", texte)                 # idem, dans courtier/dernier-audit.txt
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
    """Tout ce que les verbes du mur écrivent dans l'installation jetable, hors du produit : chaque fichier (contenu normalisé, ou empreinte des réglages
    générés), chaque lien symbolique (sa cible), chaque dossier vide ; l'état du courtier (validations, journaux), jamais ses sources."""
    out = {}
    for f in sorted(t.rglob("*")):
        r = f.relative_to(t)
        if r.parts[0] in HORS_RACINE and not (r.parts[0] == "courtier" and "outils" not in r.parts and (f.is_dir() or ETAT_COURTIER.search(f.name))): continue
        if any(x in HORS for x in r.parts) or any(p.is_symlink() for p in list(f.parents)[:len(r.parts) - 1]): continue
        if f.is_symlink(): _ranger(out, normaliser(str(r), t), "-> " + normaliser(os.readlink(f), t))
        elif f.is_dir():
            if not any(f.iterdir()): _ranger(out, normaliser(str(r) + "/", t), "<dossier>")
        elif f.is_file(): _ranger(out, normaliser(str(r), t), contenu(f, t))
    return out


def ajouts(ancien, neuf):
    """Ce qu'un scénario ajoute à un journal : la fin du fichier, SI son ancien contenu est resté identique au début ; sinon le fichier entier, marqué
    (renvoi n° 93 : une ancienne ligne altérée fait un écart et ne devient jamais, muette, la référence du scénario suivant)."""
    ancien, neuf = ancien or "", neuf or ""
    return neuf[len(ancien):] if neuf.startswith(ancien) else {"début du journal modifié": neuf}


JOURNAUX = ("courtier/appels.log", "courtier/notifications.log", "courtier/echanges.jsonl")


def controler_journal():
    """Renvoi n° 93 : une ANCIENNE ligne d'un journal altérée, puis la même ligne neuve ajoutée, doit faire un écart. → la liste des défauts."""
    ancien = "ligne ancienne\n"; ligne = "ligne neuve\n"
    return [] if ajouts(ancien, ancien + ligne) != ajouts(ancien, ancien.replace("ancienne", "ALTEREE") + ligne) else ["une ancienne ligne altérée d'un journal ne fait pas d'écart"]


def controler_instantane():
    """Leçon du renvoi n° 89 : l'instantané garde CHAQUE fichier, même quand la normalisation rend leurs noms identiques (copies horodatées du coffre) ;
    une copie antérieure modifiée ou supprimée fait un écart. → la liste des défauts (vide = l'instantané voit tout)."""
    defauts = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td); d = t / "sauvegardes/coffre"; d.mkdir(parents=True)
        a, b = d / "coffre-20261029-100000-avant-x.json.age", d / "coffre-20261029-110000-avant-x.json.age"
        a.write_text("premier"); b.write_text("second")
        depart = fichiers(t)
        a.write_text("premier, modifié")
        if fichiers(t) == depart: defauts.append("une copie antérieure modifiée ne fait pas d'écart")
        a.unlink()
        if fichiers(t) == depart: defauts.append("une copie antérieure supprimée ne fait pas d'écart")
    return defauts


def mesurer(src):
    src = Path(src).resolve(); resultats = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        _produit.copier(src, t, ("bin", "courtier", "commun"))
        (t / "coffre.json").write_text(json.dumps({"service": {"jeton": SECRET, "client": ORDINAIRE, "utilisateur": "quelqu-un"}}))
        dest = "age1" + "q" * 58
        def config(coffre_s=None):
            (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n\n'
                                           + (f"[coffre_sauvegarde]\n{coffre_s}" if coffre_s is not None else ""))
        config()
        for a in ("chef", "ouv"):
            d = t / "agents" / a; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nheures = aucune\nmoteur = claude\n")
        (t / "faux").mkdir(); faux = t / ".local/bin"; faux.mkdir(parents=True)
        for nom, texte in FAUX.items(): (faux / nom).write_text(texte); (faux / nom).chmod(0o755)
        trace = t / "faux/trace.jsonl"
        (t / "tmp").mkdir()
        env = dict(os.environ, BERGER_DIR=str(t), HOME=str(t), PATH=f"{faux}:{os.environ['PATH']}", BERGER_NOTIFY_SEND=str(faux / "notify-send"),
                   FAUX_TRACE=str(trace), TMPDIR=str(t / "tmp"))
        for k in ("BERGER_AGENT", "AGENT_PANNE", "FAUX_AGE"): env.pop(k, None)
        for k in [k for k in env if k.startswith(("CLAUDE_CODE_", "CODEX_", "ENABLE_CLAUDEAI"))]: env.pop(k)
        avant = {"fichiers": fichiers(t)}
        fuites = []

        def noter(nom, r):
            appels = [normaliser(l, t) for l in trace.read_text().splitlines()] if trace.exists() else []
            trace.unlink(missing_ok=True)
            apres = fichiers(t)
            ecrits = {k: x for k, x in apres.items() if avant["fichiers"].get(k, "∅") != x}
            for j in JOURNAUX:
                if j in ecrits and j in avant["fichiers"]: ecrits[j] = ajouts(avant["fichiers"][j][0], apres[j][0])
            ecrits.update({k: "(supprimé)" for k in avant["fichiers"] if k not in apres})
            avant["fichiers"] = apres
            err = [l for l in r.stderr.splitlines() if l.strip()]
            fin = err[0] if err and err[0].startswith("commande inconnue : ") else (err[-1] if err else "")
            ecrits_berger = {k: x for k, x in ecrits.items() if not k.startswith(("agents/chef/memory/fuite", ".claude/projects/"))}
            if SECRET in r.stdout + r.stderr + json.dumps(ecrits_berger) + json.dumps(appels): fuites.append(nom)
            ecrits = json.loads(json.dumps(ecrits).replace(SECRET, "<VALEUR DU COFFRE>"))   # les fuites que le test pose lui-même : jamais la valeur dans la référence
            resultats.append({"scenario": nom, "code": r.returncode, "stdout": normaliser(r.stdout, t),
                              "stderr_fin": normaliser(fin, t), "fichiers_ecrits": ecrits, "appels": appels})

        def cli(nom, *argv, plus=None):
            r = subprocess.run([sys.executable, "-c", LANCEUR, str(t / "bin/berger"), *argv], env={**env, **(plus or {})}, capture_output=True, timeout=600)
            r.stdout, r.stderr = r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace"); noter(nom, r)

        # 1. secrets audit : les valeurs du coffre cherchées en clair hors du coffre ; seulement des NOMS de clés
        cli("secrets sans sous-commande", "secrets")
        cli("secrets, sous-commande inconnue", "secrets", "lister")
        cli("secrets audit (aucune fuite)", "secrets", "audit")
        (t / "agents/chef/memory/fuite.md").write_text(f"note : {SECRET} et {ORDINAIRE}\n")
        cle = re.sub(r"[^A-Za-z0-9-]", "-", str(t)); tr = t / ".claude/projects" / cle; tr.mkdir(parents=True)
        (tr / "session.jsonl").write_text(json.dumps({"texte": SECRET}) + "\n")
        cli("secrets audit (deux fichiers, nommés par la clé)", "secrets", "audit")
        (t / "agents/chef/memory/fuite.md").unlink(); (tr / "session.jsonl").unlink()
        cli("secrets audit (nettoyé)", "secrets", "audit", "en-trop")
        # 2. coffre sauvegarder | purger : copie CHIFFRÉE (age) vers la clé publique, vérifiée ; purge des anciennes
        cli("coffre sans sous-commande", "coffre")
        cli("coffre sauvegarder sans motif", "coffre", "sauvegarder")
        cli("coffre, sous-commande inconnue", "coffre", "ouvrir", "x")
        cli("coffre sauvegarder, destinataire absent", "coffre", "sauvegarder", "avant-essai")
        config(f'destinataire = "AGE-SECRET-KEY-pas-une-cle-publique"\ndossier = "{t}/sauvegardes/coffre"\ngarder_jours = 7\n')
        cli("coffre sauvegarder, destinataire qui n'est pas une clé publique", "coffre", "sauvegarder", "avant-essai")
        config(f'destinataire = "{dest}"\ndossier = "{t}/sauvegardes/coffre"\ngarder_jours = 7\n')
        cli("coffre sauvegarder, motif invalide", "coffre", "sauvegarder", "avant essai !")
        cli("coffre sauvegarder, age absent", "coffre", "sauvegarder", "avant-essai", plus={"PATH": f"{t}/faux:/usr/bin:/bin", "HOME": str(t / "tmp")})
        cli("coffre sauvegarder, chiffrement en échec", "coffre", "sauvegarder", "avant-essai", plus={"FAUX_AGE": "ko"})
        cli("coffre sauvegarder, copie non conforme (supprimée)", "coffre", "sauvegarder", "avant-essai", plus={"FAUX_AGE": "court"})
        cli("coffre sauvegarder (copie chiffrée vérifiée)", "coffre", "sauvegarder", "avant-essai")
        vieux = t / "sauvegardes/coffre/coffre-20200101-000000-ancien.json.age"; vieux.write_text("ancienne copie\n")
        os.utime(vieux, (time.time() - 30 * 86400, time.time() - 30 * 86400))
        cli("coffre purger (une copie de plus de 7 jours)", "coffre", "purger")
        cli("coffre purger (rien à effacer)", "coffre", "purger")
        vieux.write_text("ancienne copie\n"); os.utime(vieux, (time.time() - 30 * 86400, time.time() - 30 * 86400))
        cli("coffre sauvegarder (puis purge des anciennes)", "coffre", "sauvegarder", "avant-outil")
        resultats.append({"scenario": "GARDE : aucune valeur du coffre dans une sortie ni un fichier écrit par berger", "code": 1 if fuites else 0,
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
