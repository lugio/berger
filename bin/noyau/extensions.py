"""Les extensions (spec docs/plans/2026-11-07-extensions-spec.md, go n° 181) : installer, retirer, revenir à la version d'avant une skill, un
serveur MCP, une vue ou un outil du courtier, depuis un dossier local ou un dépôt git local, SANS toucher au produit ni à config.toml.

Fichiers : <installation>/extensions/<genre>/<nom>/<version>/ (copie figée, en lecture seule), `actuelle` = lien vers la version active ;
réglages : <installation>/extensions.toml, GÉNÉRÉ ici (jamais config.toml). Avant toute écriture, une sauvegarde vérifiée (`.avant-<nom>-<AAAAMMJJHHMM>`)
de extensions.toml et des agent.conf touchés ; après, regenerer ; un échec ramène l'état sauvegardé (rien de demi-installé). Chaque geste : une ligne dans
courtier/extensions.log. Lot 1 : le socle et le genre `skill` ; les autres genres sont refusés, nommés, jusqu'à leur lot.

Fonctions du CŒUR, hors API : `commande` reçoit du cœur `valeurs_coffre` (le coffre n'est lu qu'au cœur) et `regenerer`. Les VALEURS du coffre ne
sortent jamais de ce module : ni retour de fonction, ni message de refus, ni journal — un refus nomme le fichier, la ligne et le NOM de la clé.
Dépendances nommées, aucun `import *`."""
import datetime, fcntl, hashlib, io, json, os, re, shutil, stat, subprocess, sys, tarfile, tempfile, tomllib
from pathlib import Path
from noyau.config import AGENTS, BERGER, BIBLIOTHEQUE, CONFIG, COFFRE, HOME
from noyau.agents import agents, conf, ecritures_en_plus, memoire_dossier, travail
from noyau.lectures import MASQUE, SKILLS_PRODUIT, derniers_usages, developpeur, dossier_skills, masquer_secret

GENRES = ("skill", "mcp", "vue", "outil")
LOT_DU_GENRE = {"skill": 1, "mcp": 3, "vue": 4, "outil": 5}
PRIS_EN_CHARGE = ("skill", "mcp")                # lot 1 : skill ; lot 3 : mcp ; chaque lot suivant ajoute son genre
CLES_MCP = {"commande", "web", "max_reponse", "max_par_minute"}   # [mcp] d'un manifeste (lot 3) ; le reste est un refus
NOM_VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
# Lanceurs qui TÉLÉCHARGENT au démarrage (nom → sous-commande qui télécharge, ou None : toujours) : refusés pour un [mcp] de config.toml
# (serveur_mcp, bin/berger) comme pour un serveur MCP d'extension (lot 3). Déplacé ici de bin/berger, inchangé.
TELECHARGE = {"npx": None, "uvx": None, "bunx": None, "pnpx": None, "pipx": "run", "npm": "exec", "pnpm": "dlx", "yarn": "dlx", "bun": "x", "uv": "tool"}
SOUS_COMMANDES_TELECHARGE = {"exec", "dlx", "x", "run", "tool"}   # cherchées dans TOUS les arguments (renvoi n° 187 : « npm --yes exec … » passait)
# Interpréteurs et relais de programme : refusés en commande[0] d'un serveur MCP d'extension (renvoi n° 187, décisions du lot 3) — leur script
# serait un 2e programme à garder ; un serveur en langage de script se déclare par son exécutable installé (ligne #! contrôlée comme un argument).
_INTERPRETES = ("python|pypy|node|nodejs|bun|deno|ruby|perl|php|lua|luajit|tclsh|wish|java|rscript|sh|bash|dash|zsh|ksh|mksh|fish|csh|tcsh"
                "|env|busybox|awk|gawk|mawk|nawk|sed|xargs|nohup|setsid|timeout|nice|sudo|doas|su|script|expect")
INTERPRETE = re.compile(rf"({_INTERPRETES})([0-9][0-9.]*)?(-[0-9.]+)?", re.I)
URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://")
RACINE = BERGER / "extensions"
REGLAGES = BERGER / "extensions.toml"
JOURNAL = BERGER / "courtier/extensions.log"
RETIREES = RACINE / ".retirees"
TAILLE_MAX = 1 << 20                              # 1 Mio pour tout le paquet (skill, vue, outil)
FICHIERS_MAX = 500
NOM = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
COMMIT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
RESERVES = {"actuelle", "berger", "extension", "extensions", "retirees"}
CLES_MANIFESTE = {"nom", "genre", "version", "description", "droits", "mcp"}
TYPES_DROITS = {"reseau": bool, "ecriture": list, "env": list, "hotes": list, "secrets": list, "ecritures": list}
DROITS_DU_GENRE = {"skill": set(), "mcp": {"reseau", "ecriture", "env"}, "vue": set(), "outil": {"hotes", "secrets", "ecritures"}}
CLE_AGENT = {"skill": "skills", "mcp": "mcp", "outil": "outils"}   # la ligne d'agent.conf qui donne le droit ; une vue ne se donne pas
ENTETE = ("# Généré par `berger extension` : ne pas modifier à la main (une sauvegarde .avant-<nom>-<date> précède chaque geste).\n"
          "# Lu EN PLUS de config.toml, qui n'est jamais réécrit. Un même nom dans les deux est refusé.\n")


class RefusExtension(Exception):
    """Un refus nommé : rien n'est écrit (ou tout est revenu à l'état sauvegardé)."""


# ───────────────────────────── lecture de l'état ─────────────────────────────

def etat_extensions():
    """{genre: {nom: entrée}} lu dans extensions.toml ; {} s'il est absent. Un fichier illisible est un refus nommé (jamais « vide » en silence)."""
    if not REGLAGES.is_file(): return {}
    try: d = tomllib.loads(REGLAGES.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e: raise RefusExtension(f"extensions.toml illisible ({type(e).__name__}) : corrige-le ou reviens à sa sauvegarde .avant-…")
    return {g: d.get(g, {}) for g in GENRES if isinstance(d.get(g), dict)}


def dossier_actuel(genre, nom):
    """Le dossier de la version active d'une extension installée, sinon None."""
    e = etat_sans_refus().get(genre, {}).get(nom)
    if not e: return None
    d = RACINE / genre / nom / e.get("version", "")
    return d if d.is_dir() and not d.is_symlink() else None


def etat_sans_refus():
    try: return etat_extensions()
    except RefusExtension: return {}


def skill_installee(nom):
    """Pour lier_skills : le dossier de la skill d'extension `nom` (version active), sinon None."""
    if not NOM.fullmatch(nom or ""): return None
    d = dossier_actuel("skill", nom)
    return d if d and (d / "SKILL.md").is_file() else None


# ───────────────────────────── écriture de extensions.toml ─────────────────────────────

def _toml_valeur(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, str): return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list): return "[" + ", ".join(_toml_valeur(x) for x in v) + "]"
    raise TypeError(f"valeur non prévue dans extensions.toml : {type(v).__name__}")


def texte_etat(e):
    """Le texte de extensions.toml pour l'état `e` : entête, puis une table par extension (genre, nom triés). Tables imbriquées : droits, versions, lignes."""
    out = [ENTETE]
    for g in GENRES:
        for nom in sorted(e.get(g, {})):
            x = e[g][nom]; out.append(f"\n[{g}.{nom}]\n")
            for k in sorted(k for k, v in x.items() if not isinstance(v, dict)): out.append(f"{k} = {_toml_valeur(x[k])}\n")
            for k in sorted(k for k, v in x.items() if isinstance(v, dict)):
                out.append(f"\n[{g}.{nom}.{k}]\n")
                for kk in sorted(x[k]): out.append(f"{json.dumps(kk, ensure_ascii=False)} = {_toml_valeur(x[k][kk])}\n")
    return "".join(out)


def _ecrire_atomique(f, texte):
    tmp = f.with_name(f".{f.name}.tmp"); tmp.write_text(texte, encoding="utf-8"); os.replace(tmp, f)


# ───────────────────────────── sauvegarde vérifiée ─────────────────────────────

def _horodatage(): return datetime.datetime.now().strftime("%Y%m%d%H%M")


def sauvegarder_fichier(f, nom, stamp):
    """Copie vérifiée `<f>.avant-<nom>-<stamp>` (existe, même contenu relu) ; le chemin, ou None si `f` n'existe pas (le retour arrière l'effacera)."""
    if not f.exists(): return None
    b = f.with_name(f"{f.name}.avant-{nom}-{stamp}"); i = 2
    while b.exists(): b = f.with_name(f"{f.name}.avant-{nom}-{stamp}-{i}"); i += 1
    shutil.copy2(f, b)
    if not b.is_file() or b.read_bytes() != f.read_bytes(): raise RefusExtension(f"sauvegarde de {f.name} non vérifiée : rien n'est modifié")
    return b


class Sauvegarde:
    """Les fichiers sauvegardés AVANT un geste et ce qu'il a créé : `revenir_extension()` remet tout comme avant (fichiers à l'octet près)."""
    def __init__(self, nom):
        self.nom, self.stamp, self.copies, self.crees, self.liens, self.deplaces = nom, _horodatage(), [], [], [], []

    def garder(self, f):
        if any(x == f for x, _ in self.copies): return
        self.copies.append((f, sauvegarder_fichier(f, self.nom, self.stamp)))

    def lien(self, l):
        self.liens.append((l, os.readlink(l) if l.is_symlink() else None))

    def revenir(self):
        for de, vers in reversed(self.deplaces):
            if vers.exists() and not de.exists(): de.parent.mkdir(parents=True, exist_ok=True); os.replace(vers, de)
        for l, cible in reversed(self.liens):
            if l.is_symlink() or l.exists(): l.unlink()
            if cible is not None: os.symlink(cible, l)
        for d in reversed(self.crees): _effacer_copie(d)
        for f, b in self.copies:
            if b is None: f.unlink(missing_ok=True)
            else: shutil.copy2(b, f)

    def fichiers(self): return [str(b.relative_to(BERGER)) for _, b in self.copies if b is not None]


def _effacer_copie(d):
    """Efface une copie que CE geste a créée (jamais une version déjà installée) : les droits d'écriture lui sont rendus d'abord."""
    if not d.exists(): return
    for r, ds, _ in os.walk(d): os.chmod(r, 0o755)
    shutil.rmtree(d)


# ───────────────────────────── source et paquet ─────────────────────────────

def _copier_sans_lien(src, dst, total):
    """Copie `src` (dossier) dans `dst` en refusant lien symbolique, fichier spécial et taille. Parcours par DESCRIPTEURS de dossier (dir_fd,
    O_DIRECTORY | O_NOFOLLOW à chaque niveau) : un dossier parent remplacé par un lien pendant la copie n'est jamais suivi ; ce qui est lu est
    ce qui est copié (fstat sur le descripteur ouvert)."""
    def copier(fd, rel):
        with os.scandir(fd) as it: noms = sorted(x.name for x in it)
        for n in noms:
            q = rel / n; st = os.stat(n, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISLNK(st.st_mode): raise RefusExtension(f"lien symbolique dans le paquet : {q}")
            if stat.S_ISDIR(st.st_mode):
                (dst / q).mkdir(); sous = os.open(n, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try: copier(sous, q)
                finally: os.close(sous)
                continue
            if not stat.S_ISREG(st.st_mode): raise RefusExtension(f"fichier spécial dans le paquet : {q}")
            f = os.open(n, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(f, "rb") as fi:
                if not stat.S_ISREG(os.fstat(fi.fileno()).st_mode): raise RefusExtension(f"fichier spécial dans le paquet : {q}")
                data = fi.read(TAILLE_MAX + 1)
            total[0] += len(data); total[1] += 1
            if total[0] > TAILLE_MAX: raise RefusExtension(f"paquet trop gros : plus de {TAILLE_MAX // 1024} Kio (1 Mio au plus)")
            if total[1] > FICHIERS_MAX: raise RefusExtension(f"paquet : plus de {FICHIERS_MAX} fichiers")
            (dst / q).write_bytes(data)
    try: racine = os.open(src, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError: raise RefusExtension("source : dossier introuvable ou lien symbolique")
    try: copier(racine, Path("."))
    finally: os.close(racine)


def _depuis_git(spec, dst):
    """`git:<dépôt local>@<commit complet>` : le contenu de CE commit (git archive), sans lien symbolique ni chemin hors du paquet."""
    depot, sep, commit = spec[4:].rpartition("@")
    if not sep or not depot: raise RefusExtension("source git : forme git:<dépôt local>@<commit complet>")
    if not COMMIT.fullmatch(commit): raise RefusExtension(f"source git : « {commit[:20]} » n'est pas un commit complet (jamais une branche ni un commit abrégé : ce qui est vérifié est ce qui est installé)")
    d = Path(depot)
    if not d.is_absolute() or not d.is_dir(): raise RefusExtension("source git : le dépôt doit être un chemin absolu vers un dossier existant")
    t = subprocess.run(["git", "cat-file", "-t", commit], cwd=d, capture_output=True, text=True)
    if t.returncode or t.stdout.strip() != "commit": raise RefusExtension(f"source git : commit {commit[:12]} absent du dépôt")
    a = subprocess.run(["git", "archive", "--format=tar", commit], cwd=d, capture_output=True)
    if a.returncode: raise RefusExtension(f"source git : git archive en échec (code {a.returncode})")
    total = 0
    with tarfile.open(fileobj=io.BytesIO(a.stdout)) as tar:
        for m in tar.getmembers():
            p = Path(m.name)
            if p.is_absolute() or ".." in p.parts: raise RefusExtension(f"chemin hors du paquet : {m.name}")
            if m.issym() or m.islnk(): raise RefusExtension(f"lien symbolique dans le paquet : {m.name}")
            if m.isdir(): (dst / p).mkdir(parents=True, exist_ok=True); continue
            if not m.isfile(): raise RefusExtension(f"fichier spécial dans le paquet : {m.name}")
            total += m.size
            if total > TAILLE_MAX: raise RefusExtension(f"paquet trop gros : plus de {TAILLE_MAX // 1024} Kio (1 Mio au plus)")
            (dst / p).parent.mkdir(parents=True, exist_ok=True); (dst / p).write_bytes(tar.extractfile(m).read())


def preparer_source(source, tmp):
    """La source (dossier absolu ou git:<dépôt>@<commit>) copiée dans `tmp`/paquet : tous les contrôles portent sur CETTE copie, qui est celle installée."""
    dst = Path(tmp) / "paquet"; dst.mkdir()
    if source.startswith("git:"): _depuis_git(source, dst); return dst
    s = Path(source)
    if not s.is_absolute(): raise RefusExtension("source : un chemin absolu (dossier local) ou git:<dépôt local>@<commit complet>")
    if s.is_symlink(): raise RefusExtension("source : le dossier est un lien symbolique")
    if not s.is_dir(): raise RefusExtension("source : dossier introuvable")
    _copier_sans_lien(s, dst, [0, 0])
    return dst


def fichiers_paquet(d):
    """[(chemin relatif posix, octets)] de tous les fichiers du paquet, triés par chemin."""
    return sorted((p.relative_to(d).as_posix(), p.read_bytes()) for p in d.rglob("*") if p.is_file() and not p.is_symlink())


def empreinte_paquet(d):
    """sha256 de la liste triée des fichiers : pour chacun, chemin (UTF-8), octet nul, taille en décimal, octet nul, contenu. Manifeste compris."""
    h = hashlib.sha256()
    for chemin, data in fichiers_paquet(d): h.update(chemin.encode("utf-8") + b"\0" + str(len(data)).encode() + b"\0" + data)
    return h.hexdigest()


def version_t(v): return tuple(int(x) for x in v.split("."))


# ───────────────────────────── contrôles ─────────────────────────────

def lire_manifeste(d, genre):
    """Le manifeste extension.toml validé (dict normalisé), ou un refus nommé."""
    f = d / "extension.toml"
    if not f.is_file(): raise RefusExtension("manifeste absent : extension.toml à la racine du paquet")
    try: m = tomllib.loads(f.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as e: raise RefusExtension(f"manifeste invalide : {str(e)[:120]}")
    hors = sorted(set(m) - CLES_MANIFESTE)
    if hors: raise RefusExtension(f"manifeste invalide : {len(hors)} clé{'s' if len(hors) > 1 else ''} inconnue{'s' if len(hors) > 1 else ''} "
                                  f"(permises : {', '.join(sorted(CLES_MANIFESTE))} ; le nom n'est pas recopié)")
    for k in ("nom", "genre", "version", "description"):
        if not isinstance(m.get(k), str) or not m[k].strip(): raise RefusExtension(f"manifeste invalide : « {k} » manquant (texte)")
    if not NOM.fullmatch(m["nom"]) or len(m["nom"]) > 40: raise RefusExtension("manifeste invalide : nom en minuscules, chiffres et tirets (40 au plus)")
    if m["genre"] not in GENRES: raise RefusExtension(f"manifeste invalide : genre inconnu ({', '.join(GENRES)} ; la valeur n'est pas recopiée)")
    if m["genre"] != genre: raise RefusExtension(f"manifeste invalide : genre {m['genre']} dans le paquet, {genre} demandé")
    if not VERSION.fullmatch(m["version"]): raise RefusExtension("manifeste invalide : version SemVer x.y.z attendue")
    if "\n" in m["description"] or len(m["description"]) > 200: raise RefusExtension("manifeste invalide : description d'une ligne (200 caractères au plus)")
    droits = m.get("droits", {})
    if not isinstance(droits, dict): raise RefusExtension("manifeste invalide : [droits] doit être une table")
    norm = {}
    for k, v in droits.items():
        if k not in TYPES_DROITS: raise RefusExtension(f"manifeste invalide : droit inconnu (permis : {', '.join(TYPES_DROITS)} ; le nom n'est pas recopié)")
        if not isinstance(v, TYPES_DROITS[k]) or (isinstance(v, list) and not all(isinstance(x, str) and x for x in v)):
            raise RefusExtension(f"manifeste invalide : droit « {k} » mal formé")
        if v and k not in DROITS_DU_GENRE[genre]: raise RefusExtension(f"manifeste invalide : droit « {k} » sans objet pour le genre {genre}")
        if v: norm[k] = v
    if "mcp" in m and genre != "mcp": raise RefusExtension(f"manifeste invalide : [mcp] sans objet pour le genre {genre}")
    if genre == "mcp":
        x = m.get("mcp")
        if not isinstance(x, dict): raise RefusExtension("manifeste invalide : [mcp] absent (commande = [\"/chemin/absolu\", …])")
        hors_mcp = set(x) - CLES_MCP
        if hors_mcp: raise RefusExtension(f"manifeste invalide : [mcp] : {len(hors_mcp)} clé{'s' if len(hors_mcp) > 1 else ''} inconnue{'s' if len(hors_mcp) > 1 else ''} "
                                          f"(permises : {', '.join(sorted(CLES_MCP))} ; le nom n'est pas recopié)")
        c = x.get("commande")
        if not isinstance(c, list) or not c or not all(isinstance(y, str) and y for y in c): raise RefusExtension("manifeste invalide : [mcp] commande : une liste non vide de textes")
        if "web" in x and not isinstance(x["web"], bool): raise RefusExtension("manifeste invalide : [mcp] web : true ou false")
        for e in norm.get("env", []):
            if not NOM_VARIABLE.fullmatch(e): raise RefusExtension("manifeste invalide : [droits] env : des NOMS de variables (lettres, chiffres, _), jamais une valeur")
        for e in norm.get("ecriture", []):
            q = Path(e)
            if q.is_absolute() or ".." in q.parts or not q.parts: raise RefusExtension("manifeste invalide : [droits] ecriture : un sous-dossier RELATIF au dossier de l'agent, sans « .. »")
    return {"nom": m["nom"], "genre": genre, "version": m["version"], "description": m["description"].strip(), "droits": norm, "mcp": m.get("mcp")}


def _motifs_interdits():
    """(regex, ce qu'on nomme) : le NOM du fichier du coffre, les motifs [skills] interdits, les marques privées de config.toml."""
    v = CONFIG.get("skills"); motifs = [(re.compile(re.escape(COFFRE.name), re.I), f"fichier du coffre « {COFFRE.name} »")]
    for x in (v.get("interdits", []) if isinstance(v, dict) else []):
        try: motifs.append((re.compile(x, re.I), f"motif interdit « {x} »"))
        except re.error: pass
    for x in CONFIG.get("marques_privees", []) or []:
        if isinstance(x, str) and len(x) >= 3: motifs.append((re.compile(re.escape(x), re.I), "marque privée"))
    return motifs


def _textes_manifeste(d):
    """Toutes les clés et tous les textes du manifeste, DÉCODÉS par TOML (un échappement \\uXXXX ne cache rien) : ce qui sera affiché et écrit."""
    try: m = tomllib.loads((d / "extension.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError): return []
    out = []
    def voir(x):
        if isinstance(x, dict):
            for k, v in x.items(): out.append(str(k)); voir(v)
        elif isinstance(x, list):
            for v in x: voir(v)
        elif isinstance(x, str): out.append(x)
    voir(m); return out


def controler_contenu(d, valeurs_coffre):
    """Aucune valeur du coffre, ni nom de son fichier, ni motif interdit, ni marque privée : dans les NOMS des fichiers du paquet (refus par le rang
    du fichier, jamais son nom), dans les textes DÉCODÉS du manifeste, puis dans le contenu de chaque fichier (binaires compris).
    Refus : « <fichier>, ligne <n> : <ce qui est trouvé> » — pour le coffre, le NOM de la clé, jamais la valeur."""
    valeurs = valeurs_coffre() or {}; motifs = _motifs_interdits(); fs = fichiers_paquet(d)
    for rang, (chemin, _) in enumerate(fs, 1):
        for v, cle in valeurs.items():
            if v and v in chemin: raise RefusExtension(f"nom de fichier n° {rang} du paquet (ordre trié ; le nom n'est pas recopié) : valeur du coffre (clé « {cle} »)")
        for rx, quoi in motifs:
            if rx.search(chemin): raise RefusExtension(f"nom de fichier n° {rang} du paquet (ordre trié ; le nom n'est pas recopié) : {quoi}")
    for texte in _textes_manifeste(d):
        for v, cle in valeurs.items():
            if v and v in texte: raise RefusExtension(f"extension.toml (texte décodé) : valeur du coffre (clé « {cle} »)")
        for rx, quoi in motifs:
            if rx.search(texte): raise RefusExtension(f"extension.toml (texte décodé) : {quoi}")
    for chemin, data in fs:
        t = data.decode("utf-8", errors="ignore")
        for v, cle in valeurs.items():
            if v and v in t:
                ligne = t.count("\n", 0, t.index(v)) + 1
                raise RefusExtension(f"{chemin}, ligne {ligne} : valeur du coffre (clé « {cle} »)")
        for rx, quoi in motifs:
            m = rx.search(t)
            if m:
                ligne = t.count("\n", 0, m.start()) + 1
                raise RefusExtension(f"{chemin}, ligne {ligne} : {quoi}")


def nom_libre(genre, nom, e):
    """Ni réservé, ni du produit, ni d'un autre genre déjà installé ; pour une skill, ni le catalogue de l'installation."""
    if nom in RESERVES: raise RefusExtension(f"nom réservé : {nom}")
    for g in GENRES:
        if g != genre and nom in e.get(g, {}): raise RefusExtension(f"nom pris : {nom} est déjà une extension de genre {g}")
    if genre == "mcp" and nom in (CONFIG.get("mcp") or {}): raise RefusExtension(f"nom pris : {nom} est un serveur [mcp.{nom}] de config.toml")
    if genre == "skill":
        if (SKILLS_PRODUIT / nom).exists(): raise RefusExtension(f"nom pris : {nom} est une méthode du produit (commun/skills/)")
        if (dossier_skills() / nom / "SKILL.md").is_file(): raise RefusExtension(f"nom pris : {nom} est une méthode du catalogue de l'installation")


def controler_agents(liste, genre):
    for a in liste:
        if not re.fullmatch(r"[\w.-]+", a) or not (AGENTS / a / "agent.conf").is_file(): raise RefusExtension(f"agent inconnu : {a[:40]}")
    if liste and genre not in CLE_AGENT: raise RefusExtension(f"--agents : une extension de genre {genre} ne se donne pas à un agent")
    for a in liste if genre == "mcp" else []:
        if developpeur(a): raise RefusExtension(f"{a} est un développeur d'équipe : il ne reçoit jamais un serveur MCP")


def controler_genre(genre, d, m, reseau=False):
    """Les contrôles propres au genre. Lot 1 : skill (SKILL.md présent, motif_refus_skill rejoué sur tout le dossier). Lot 3 : mcp (commande :
    chemin absolu d'un exécutable déjà installé, hors des dossiers d'agents et d'extensions/, jamais un lanceur qui télécharge ; réseau
    seulement demandé ET accordé par --reseau ; web et réseau incompatibles). serveur_mcp, rejoué après l'écriture, reste la source des refus."""
    if genre == "mcp":
        c = m["mcp"]["commande"]; p = Path(c[0]); demande = m["droits"].get("reseau") is True
        if not p.is_absolute(): raise RefusExtension("mcp : commande[0] doit être le chemin absolu d'un exécutable déjà installé (jamais un nom cherché dans le PATH)")
        if telecharge(c): raise RefusExtension(f"mcp : commande « {p.name} » : télécharge au démarrage — installe le serveur, puis déclare son binaire")
        if any(INTERPRETE.fullmatch(n) for n in {p.name, p.resolve().name}):
            raise RefusExtension(f"mcp : commande « {p.name} » : interpréteur refusé (son script serait un autre programme à garder) — déclare l'exécutable installé du serveur")
        controler_chemins_mcp(c)
        if not p.is_file() or not os.access(p, os.X_OK): raise RefusExtension("mcp : commande introuvable ou non exécutable")
        if demande and not reseau: raise RefusExtension("mcp : réseau demandé par le manifeste — il ne s'installe qu'avec --reseau (décision du propriétaire)")
        if reseau and not demande: raise RefusExtension("mcp : --reseau sans réseau demandé par le manifeste ([droits] reseau = true)")
        if m["mcp"].get("web") is True and demande: raise RefusExtension("mcp : web = true et reseau = true : incompatibles (le web passe par le proxy du courtier, réseau coupé)")
    if genre == "skill":
        if not (d / "SKILL.md").is_file(): raise RefusExtension("skill : SKILL.md absent à la racine du paquet")
        from noyau.skills import motif_refus_skill   # le même contrôle que le catalogue (fichier du coffre, [skills] interdits), sur tout le dossier
        motif = motif_refus_skill(d)
        if motif: raise RefusExtension(f"skill refusée : {motif}")


def telecharge(cmd):
    """Vrai si la commande lance un téléchargeur : un lanceur de TELECHARGE (son nom, ou celui de sa cible) toujours téléchargeur, ou dont une
    sous-commande qui télécharge figure PARMI TOUS ses arguments. Partagé par serveur_mcp (config.toml) et les serveurs MCP d'extension."""
    p = Path(os.path.expanduser(cmd[0])); noms = {p.name}
    try: noms.add(p.resolve().name)
    except OSError: pass
    return any(n in TELECHARGE and (TELECHARGE[n] is None or bool(SOUS_COMMANDES_TELECHARGE & set(cmd[1:]))) for n in noms)


def dossiers_inscriptibles():
    """[(dossier, motif)] dont le contenu ne doit être ni lancé ni lu par un serveur MCP d'extension : les dossiers d'agent, extensions/, puis
    ce qu'un agent peut écrire (son dossier de travail, sa mémoire, ses `ecrire_aussi` — dont la copie d'un développeur —, la bibliothèque, les
    temporaires des agents). Un agent en mur ouvert, hors bac à sable, n'est borné par aucun dossier : limite écrite dans les décisions."""
    out = [(AGENTS, "dossier d'agent"), (RACINE, "extensions/")]
    for a in agents():
        try: out += [(Path(x), "dossier inscriptible par un agent") for x in (travail(a), memoire_dossier(a), *ecritures_en_plus(a)) if x]
        except SystemExit: continue
    tmp = Path(os.environ.get("BERGER_TMP_AGENTS") or "/tmp/bt")
    return out + [(BIBLIOTHEQUE, "dossier inscriptible par un agent (bibliothèque)"), (tmp, "dossier inscriptible par un agent (temporaires)"),
                  (Path("/tmp") / f"claude-{os.getuid()}", "dossier inscriptible par un agent (temporaires)")]


def _formes(q):
    """Le chemin tel quel (normalisé) et résolu (liens compris)."""
    f = {Path(os.path.normpath(q))}
    try: f.add(q.resolve())
    except OSError: pass
    return f


def _sous(q, dossiers):
    """Le motif du premier dossier qui contient `q` (chemin et dossier, chacun tel quel ET résolu), sinon None."""
    cands = _formes(q)
    for d, motif in dossiers:
        if any(c.is_relative_to(x) for c in cands for x in _formes(d)): return motif
    return None


def controler_chemins_mcp(c):
    """Renvoi n° 187 : commande[0], chaque argument (et la valeur d'un `--option=valeur`) et les mots de la ligne #! de commande[0] — tout ce qui
    désigne un chemin — hors des dossiers d'agent, d'extensions/ et des dossiers inscriptibles par un agent. Un chemin relatif (« ./x », « a/b »)
    ou sous « ~ » est refusé : le serveur le lirait depuis son dossier courant, le dossier d'écriture de l'agent. Une URL n'est pas un chemin."""
    mots = list(c)
    try:
        with open(c[0], "rb") as f: tete = f.read(256)
        if tete.startswith(b"#!"): mots += tete[2:].split(b"\n", 1)[0].decode("utf-8", "replace").split()
    except OSError: pass
    dossiers = dossiers_inscriptibles()
    for mot in mots:
        for v in ([mot.split("=", 1)[1]] + ([mot] if os.path.isabs(mot) else []) if "=" in mot else [mot]):   # « --option=valeur » : la valeur
            if not v or URL.match(v): continue
            if v.startswith("~"): raise RefusExtension(f"mcp : argument « {v[:60]} » : chemin relatif (~) — un chemin absolu, hors des dossiers des agents")
            if os.path.isabs(v):
                motif = _sous(Path(v), dossiers)
                if motif == "extensions/": raise RefusExtension(f"mcp : « {v[:80]} » est dans extensions/ (le serveur se déclare par son binaire installé)")
                if motif: raise RefusExtension(f"mcp : « {v[:80]} » est dans un {motif} (un agent pourrait réécrire ce que le serveur lance ou lit)")
            elif "/" in v or v in (".", ".."):
                raise RefusExtension(f"mcp : argument « {v[:60]} » : chemin relatif (lu depuis le dossier courant du serveur, celui de l'agent) — un chemin absolu")


def controler_paquet(genre, d, valeurs_coffre, liste_agents, reseau, e):
    """Tous les contrôles d'un paquet copié en `d` : rend {manifeste, empreinte, taille, fichiers, avant} ou lève un refus nommé. Rien n'est écrit."""
    if genre not in GENRES: raise RefusExtension(f"genre inconnu : {genre[:20]} ({', '.join(GENRES)})")
    if genre not in PRIS_EN_CHARGE: raise RefusExtension(f"genre {genre} : pas encore pris en charge (lot {LOT_DU_GENRE[genre]} de la spec)")
    if reseau and genre != "mcp": raise RefusExtension("--reseau ne vaut que pour un serveur MCP")
    m = lire_manifeste(d, genre)
    nom_libre(genre, m["nom"], e)
    controler_agents(liste_agents, genre)
    avant = e.get(genre, {}).get(m["nom"])
    if avant and version_t(m["version"]) <= version_t(avant["version"]):
        raise RefusExtension(f"version {m['version']} : pas plus récente que l'actuelle ({avant['version']}) — `berger extension revenir` pour reculer")
    controler_contenu(d, valeurs_coffre)
    controler_genre(genre, d, m, reseau)
    fs = fichiers_paquet(d)
    return {"manifeste": m, "empreinte": empreinte_paquet(d), "taille": sum(len(x) for _, x in fs), "fichiers": len(fs), "avant": avant}


# ───────────────────────────── droits dans agent.conf ─────────────────────────────

def _derniere_ligne(lignes, cle):
    """Indice de la DERNIÈRE ligne `cle = …` (celle que lit conf_texte), sinon None."""
    r = None
    for i, l in enumerate(lignes):
        if "=" in l and not l.lstrip().startswith("#") and l.split("=", 1)[0].strip() == cle: r = i
    return r


def _elements(valeur): return [x.strip() for x in valeur.split("#")[0].split(",") if x.strip()]


def donner_droit(a, cle, nom):
    """Ajoute `nom` à la ligne `cle =` de agent.conf (créée au besoin). → (ligne d'avant ou None, ligne écrite, bloc ajouté en fin de fichier ou
    None), ou None si déjà là. Le bloc ajouté (saut de ligne mis devant une dernière ligne qui n'en avait pas compris) permet le retour à l'octet près."""
    f = AGENTS / a / "agent.conf"; t = f.read_text(encoding="utf-8"); lignes = t.split("\n"); i = _derniere_ligne(lignes, cle)
    if i is None:
        nouvelle = f"{cle} = {nom}"; bloc = ("" if t.endswith("\n") or not t else "\n") + nouvelle + "\n"
        f.write_text(t + bloc, encoding="utf-8"); return (None, nouvelle, bloc)
    l = lignes[i]; tete, valeur = l.split("=", 1); val, diese, commentaire = valeur.partition("#")
    if nom in _elements(val): return None
    sv = val.rstrip(); fin = val[len(sv):]
    nv = (sv + ", " + nom) if sv.strip() else (" " + nom)
    lignes[i] = tete + "=" + nv + (fin if diese else "") + diese + commentaire
    f.write_text("\n".join(lignes), encoding="utf-8"); return (l, lignes[i], None)


def reprendre_droit(a, cle, nom, trace):
    """Retire `nom` de agent.conf : si la ligne est encore celle que Berger a écrite, la ligne d'avant revient À L'OCTET PRÈS (ou disparaît si
    Berger l'avait créée) ; sinon `nom` seul est retiré de la liste."""
    f = AGENTS / a / "agent.conf"
    if not f.is_file(): return
    t = f.read_text(encoding="utf-8"); lignes = t.split("\n"); i = _derniere_ligne(lignes, cle)
    if i is None: return
    avant, ecrite, bloc = (trace or {}).get("avant"), (trace or {}).get("ecrite"), (trace or {}).get("bloc")
    if avant is None and bloc and t.endswith(bloc) and lignes[i] == ecrite:   # la ligne créée par Berger, toujours en fin : le bloc ajouté s'en va, à l'octet près
        f.write_text(t[:-len(bloc)], encoding="utf-8"); return
    if ecrite is not None and lignes[i] == ecrite:
        if avant is None: del lignes[i]
        else: lignes[i] = avant
    else:
        tete, valeur = lignes[i].split("=", 1); val, diese, commentaire = valeur.partition("#")
        reste = [x for x in _elements(val) if x != nom]
        if len(reste) == len(_elements(val)): return
        lignes[i] = tete + "= " + ", ".join(reste) + ((" " + diese + commentaire) if diese else "")
    f.write_text("\n".join(lignes), encoding="utf-8")


# ───────────────────────────── gestes ─────────────────────────────

def _verrou():
    RACINE.mkdir(parents=True, exist_ok=True); v = open(RACINE / ".verrou", "a"); fcntl.flock(v, fcntl.LOCK_EX); return v


def _proprietaire_seul(verbe, agent):
    if agent: raise RefusExtension(f"berger extension {verbe} : réservé au propriétaire, au terminal — jamais à un agent ({agent[:40]}) ; un agent peut PROPOSER une extension (lot 6)")


def _figer(d):
    """La copie installée en lecture seule : fichiers 0444, dossiers 0555."""
    for r, ds, fs in os.walk(d, topdown=False):
        for f in fs: os.chmod(Path(r) / f, 0o444)
        os.chmod(r, 0o555)


def _poser_actuelle(base, version, sv):
    l = base / "actuelle"; sv.lien(l)
    tmp = base / ".actuelle.tmp"
    if tmp.is_symlink() or tmp.exists(): tmp.unlink()
    os.symlink(version, tmp); os.replace(tmp, l)


def _apres(genre, nom, regenerer, liste_agents, version_dir, serveur_mcp=None):
    """Ce qui suit l'écriture : regenerer, puis la preuve — skill : chaque agent nommé a le lien vers la version active ; mcp : serveur_mcp
    (bin/berger, la SEULE source des refus d'un serveur MCP) accepte le serveur pour chaque agent nommé. → None ou la cause."""
    try: regenerer()
    except (Exception, SystemExit) as ex: return f"regenerer en échec ({type(ex).__name__}: {str(ex)[:160]})"
    if genre == "mcp" and version_dir is not None:
        if serveur_mcp is None: return "serveur_mcp non fourni par le cœur : rien n'est installé"
        for a in liste_agents:
            try: _, pb = serveur_mcp(a, nom)
            except (Exception, SystemExit) as ex: pb = f"{type(ex).__name__}: {str(ex)[:160]}"
            if pb: return f"serveur_mcp refuse pour {a} : {pb}"
    if genre == "skill" and version_dir is not None:
        for a in liste_agents:
            l = AGENTS / a / ".claude/skills" / nom
            if not l.is_symlink() or l.resolve() != version_dir.resolve(): return f"regenerer : la skill {nom} n'est pas liée chez {a}"
    return None


def tracer_extension(geste, genre, nom, x, extra=""):
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    droits = ",".join(f"{k}={'oui' if v is True else '+'.join(v) if isinstance(v, list) else v}" for k, v in sorted((x.get("droits") or {}).items())) or "aucun"
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M}\t{geste}\t{genre}\t{nom}\t{x.get('version', '?')}\t{x.get('empreinte', '?')[:12]}\t"
                f"agents={','.join(x.get('agents', [])) or 'aucun'}\tdroits={droits}{chr(9) + extra if extra else ''}\n")


def _echec(sv, regenerer, cause):
    sv.revenir()
    try: regenerer()
    except (Exception, SystemExit): pass
    raise RefusExtension(f"{cause} — retour automatique à l'état d'avant (sauvegardes : {', '.join(sv.fichiers()) or 'aucune, rien n’existait'})")


def ajouter_extension(genre, source, liste_agents, reseau, valeurs_coffre, regenerer, agent, dire=print, serveur_mcp=None):
    _proprietaire_seul("ajouter", agent)
    with tempfile.TemporaryDirectory(prefix="berger-extension-") as tmp, _verrou():
        d = preparer_source(source, tmp); e = etat_extensions()
        r = controler_paquet(genre, d, valeurs_coffre, liste_agents, reseau, e); m = r["manifeste"]; nom, version = m["nom"], m["version"]
        base = RACINE / genre / nom; dest = base / version
        if dest.exists() and empreinte_paquet(dest) != r["empreinte"]: raise RefusExtension(f"version {version} déjà présente avec une autre empreinte : change de version")
        sv = Sauvegarde(nom); sv.garder(REGLAGES)
        cle = CLE_AGENT.get(genre); lignes = dict((r["avant"] or {}).get("lignes", {}))
        for a in liste_agents: sv.garder(AGENTS / a / "agent.conf")
        try:
            for q in (base.parent, base):                                    # le dossier du genre aussi (premier ajout de ce genre)
                if not q.exists(): sv.crees.append(q); q.mkdir()
            if not dest.exists():
                sv.crees.append(dest); shutil.copytree(d, dest); _figer(dest)
                if empreinte_paquet(dest) != r["empreinte"]:   # la copie INSTALLÉE est celle vérifiée, sinon rien n'est installé
                    raise RefusExtension(f"la copie installée n'a pas l'empreinte vérifiée ({r['empreinte'][:12]}) : rien n'est installé")
            _poser_actuelle(base, version, sv)
            for a in liste_agents:
                t = donner_droit(a, cle, nom)
                if t: lignes[a] = json.dumps({"avant": t[0], "ecrite": t[1], **({"bloc": t[2]} if t[2] else {})}, ensure_ascii=False)
            anciens = list((r["avant"] or {}).get("agents", []))
            x = {"version": version, "empreinte": r["empreinte"], "description": m["description"], "installee": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "agents": sorted(set(anciens) | set(liste_agents)), "droits": dict(m["droits"]), "lignes": lignes,
                 "versions": {**(r["avant"] or {}).get("versions", {}), version: r["empreinte"]}}
            accords = sorted(set((r["avant"] or {}).get("reseau_versions") or []) | ({version} if reseau else set()), key=version_t)
            if accords: x["reseau_versions"] = accords                      # l'accord réseau version par version : revenir le reprend (renvoi n° 187)
            if reseau: x["droits"]["reseau_accorde"] = True
            e.setdefault(genre, {})[nom] = x; _ecrire_atomique(REGLAGES, texte_etat(e))
        except RefusExtension: sv.revenir(); raise
        except Exception as ex: _echec(sv, regenerer, f"écriture en échec ({type(ex).__name__})")
        cause = _apres(genre, nom, regenerer, x["agents"], dest, serveur_mcp)
        if cause: _echec(sv, regenerer, cause)
        tracer_extension("ajoutee" if not r["avant"] else "mise a jour", genre, nom, x)
    dire(f"extension {genre} {nom} {version} installée (empreinte {r['empreinte'][:12]}) ; donnée à : {', '.join(x['agents']) or 'personne'}"
         + (f" ; avant : {r['avant']['version']}" if r["avant"] else "") + f" ; sauvegardes : {', '.join(sv.fichiers()) or 'aucune (rien n’existait)'}")
    return 0


def retirer_extension(genre, nom, regenerer, agent, dire=print):
    _proprietaire_seul("retirer", agent)
    with _verrou():
        e = etat_extensions(); x = e.get(genre, {}).get(nom)
        if not x: raise RefusExtension(f"aucune extension {genre} « {nom[:40]} » installée")
        sv = Sauvegarde(nom); sv.garder(REGLAGES); cle = CLE_AGENT.get(genre)
        ags = [a for a in x.get("agents", []) if (AGENTS / a / "agent.conf").is_file()]
        for a in ags: sv.garder(AGENTS / a / "agent.conf")
        base = RACINE / genre / nom; vers = RETIREES / f"{genre}-{nom}-{sv.stamp}"; i = 2
        while vers.exists(): vers = RETIREES / f"{genre}-{nom}-{sv.stamp}-{i}"; i += 1
        try:
            for a in ags:
                tr = x.get("lignes", {}).get(a); reprendre_droit(a, cle, nom, json.loads(tr) if tr else None)
            del e[genre][nom]
            if any(e.get(g) for g in GENRES): _ecrire_atomique(REGLAGES, texte_etat(e))
            else: REGLAGES.unlink(missing_ok=True)   # plus aucune extension : l'état d'avant le premier ajout (pas de fichier) ; sauvegardé .avant- d'abord
            if base.exists(): RETIREES.mkdir(parents=True, exist_ok=True); os.replace(base, vers); sv.deplaces.append((base, vers))
        except Exception as ex: _echec(sv, regenerer, f"écriture en échec ({type(ex).__name__})")
        cause = _apres(genre, nom, regenerer, [], None)
        if cause: _echec(sv, regenerer, cause)
        tracer_extension("retiree", genre, nom, x, f"fichiers={vers.relative_to(BERGER)}")
    dire(f"extension {genre} {nom} retirée (droits repris à : {', '.join(ags) or 'personne'}) ; fichiers gardés dans {vers.relative_to(BERGER)} ; sauvegardes : {', '.join(sv.fichiers())}")
    return 0


def revenir_extension(genre, nom, valeurs_coffre, regenerer, agent, dire=print, serveur_mcp=None):
    _proprietaire_seul("revenir", agent)
    with _verrou():
        e = etat_extensions(); x = e.get(genre, {}).get(nom)
        if not x: raise RefusExtension(f"aucune extension {genre} « {nom[:40]} » installée")
        base = RACINE / genre / nom; actuelle = version_t(x["version"])
        avant = sorted((v for v in x.get("versions", {}) if version_t(v) < actuelle and (base / v).is_dir()), key=version_t)
        if not avant: raise RefusExtension(f"{genre} {nom} : aucune version précédente gardée")
        v = avant[-1]; d = base / v
        if empreinte_paquet(d) != x["versions"][v]: raise RefusExtension(f"{genre} {nom} {v} : empreinte changée depuis son installation — rien n'est modifié")
        m = lire_manifeste(d, genre)
        if m["nom"] != nom or m["version"] != v: raise RefusExtension(f"{genre} {nom} {v} : manifeste incohérent avec son dossier")
        accord = v in (x.get("reseau_versions") or []) and m["droits"].get("reseau") is True   # l'accord donné à CETTE version, jamais un nouveau
        controler_contenu(d, valeurs_coffre); controler_genre(genre, d, m, accord)
        sv = Sauvegarde(nom); sv.garder(REGLAGES)
        try:
            _poser_actuelle(base, v, sv)
            y = dict(x, version=v, empreinte=x["versions"][v], description=m["description"], droits=dict(m["droits"]),
                     installee=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
            if accord: y["droits"]["reseau_accorde"] = True
            e[genre][nom] = y; _ecrire_atomique(REGLAGES, texte_etat(e))
        except Exception as ex: _echec(sv, regenerer, f"écriture en échec ({type(ex).__name__})")
        cause = _apres(genre, nom, regenerer, y["agents"], d, serveur_mcp)
        if cause: _echec(sv, regenerer, cause)
        tracer_extension("revenue", genre, nom, y, f"depuis={x['version']}")
    dire(f"extension {genre} {nom} revenue à {v} (depuis {x['version']}, empreinte {y['empreinte'][:12]}) ; sauvegardes : {', '.join(sv.fichiers())}")
    return 0


def verifier_extension(genre, source, liste_agents, reseau, valeurs_coffre, dire=print):
    with tempfile.TemporaryDirectory(prefix="berger-extension-") as tmp:
        d = preparer_source(source, tmp); r = controler_paquet(genre, d, valeurs_coffre, liste_agents, reseau, etat_extensions()); m = r["manifeste"]
    droits = m["droits"]
    dire(f"extension {genre} {m['nom']} {m['version']} : contrôles passés, rien n'est écrit\n"
         f"  {m['description']}\n  empreinte : {r['empreinte']}\n  paquet : {r['fichiers']} fichier(s), {r['taille']} octets\n"
         f"  droits demandés : {', '.join(f'{k} = {v}' for k, v in sorted(droits.items())) or 'aucun'}\n"
         f"  serait : {'mise à jour de ' + r['avant']['version'] + ' vers ' + m['version'] if r['avant'] else 'nouvelle extension'} ; donnée à : {', '.join(liste_agents) or 'personne'}")
    return 0


def donnees_liste():
    """[{genre, nom, version, empreinte, description, agents, droits, installee, etat}] : ce que montrent `liste` et (lot 2) la page Extensions."""
    out = []
    for g, ext in etat_extensions().items():
        for nom, x in sorted(ext.items()):
            d = RACINE / g / nom / x.get("version", "")
            out.append({"genre": g, "nom": nom, "version": x.get("version"), "empreinte": x.get("empreinte"), "description": x.get("description", ""),
                        "agents": x.get("agents", []), "droits": x.get("droits", {}), "installee": x.get("installee"),
                        "etat": "active" if d.is_dir() else "écartée : fichiers absents"})
    return out


# ───────────────────────────── serveurs MCP d'extension (lot 3) ─────────────────────────────

def serveurs_mcp_extensions():
    """{nom: déclaration} des serveurs MCP d'extension ACTIFS, au format d'un [mcp.<nom>] de config.toml (lu par serveur_mcp, inchangé) :
    commande du manifeste, écriture « {agent}/<sous-dossier> », variables nommées à valeur VIDE (décision du lot 3), réseau seulement s'il a
    été accordé (--reseau). Une copie dont l'empreinte a changé, ou illisible, n'est pas déclarée (le serveur est alors refusé, nommé)."""
    out = {}
    for nom, x in sorted((etat_sans_refus().get("mcp") or {}).items()):
        if not NOM.fullmatch(nom) or not isinstance(x, dict) or not isinstance(x.get("version"), str) or not VERSION.fullmatch(x["version"]): continue
        d = RACINE / "mcp" / nom / x["version"]
        try:
            if d.is_symlink() or not d.is_dir() or empreinte_paquet(d) != x.get("empreinte"): continue
            mf = tomllib.loads((d / "extension.toml").read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError): continue
        mc, dr = mf.get("mcp") or {}, mf.get("droits") or {}
        if not isinstance(mc, dict) or not isinstance(dr, dict) or not isinstance(mc.get("commande"), list): continue
        decl = {"commande": list(mc["commande"]), "ecriture": ["{agent}/" + str(e) for e in dr.get("ecriture") or []],
                "env": {str(n): "" for n in dr.get("env") or []}, "reseau": dr.get("reseau") is True and (x.get("droits") or {}).get("reseau_accorde") is True}
        for k in ("web", "max_reponse", "max_par_minute"):
            if k in mc: decl[k] = mc[k]
        out[nom] = decl
    return out


def recharger_mcp(serveurs):
    """Remplit (EN PLACE) le dict SERVEURS_MCP du cœur : les serveurs d'extension, puis les [mcp.<nom>] de config.toml, qui priment. Rejoué
    avant chaque regenerer d'un geste d'extension : le serveur ajouté ou retiré est vu dans le même processus."""
    serveurs.clear(); serveurs.update({**serveurs_mcp_extensions(), **(CONFIG.get("mcp") or {})})
    return serveurs


def mcp_reseau():
    """Décision du lot 3 : les serveurs MCP à RÉSEAU qu'au moins un agent a dans son `mcp =` → [{serveur, origine, agents}] (pour
    `berger etat --json` et la ligne « ⚠ réseau ouvert » de regenerer ; aucune notification)."""
    cfg = CONFIG.get("mcp") or {}; tous = {**serveurs_mcp_extensions(), **cfg}; out = []
    for s, d in sorted(tous.items()):
        if not isinstance(d, dict) or d.get("reseau") is not True: continue
        ags = sorted(a for a in agents() if s in [y.strip() for y in conf(a).get("mcp", "").split(",")])
        if ags: out.append({"serveur": s, "origine": "config.toml" if s in cfg else "extension", "agents": ags})
    return out


def lignes_reseau_mcp():
    return [f"⚠ réseau ouvert : serveur MCP {x['serveur']} ({x['origine']}) pour {', '.join(x['agents'])}" for x in mcp_reseau()]


# ───────────────────────────── la page « Extensions » (lot 2), en lecture seule ─────────────────────────────

FICHIER_MONTRE = "~/berger/extensions.toml"
CHAMPS_DROITS = set(TYPES_DROITS) | {"reseau_accorde"}


def _montrable(v):
    """Un texte montré par la page : une forme de clé → masqué ; une marque privée → masqué ; le dossier personnel → « ~ » (aucun chemin privé)."""
    s = masquer_secret(str(v if v is not None else ""))
    for mq in CONFIG.get("marques_privees") or []:
        if isinstance(mq, str) and mq and mq.lower() in s.lower(): return MASQUE
    return s.replace(str(HOME), "~")


def _dernier_usage(genre, nom):
    """MCP : le dernier appel ACCEPTÉ au journal du courtier (« mcp:<nom> », tous agents) ; sinon, et pour une skill : « non mesuré »."""
    if genre != "mcp": return "non mesuré"
    vus = [q for (a, o), q in derniers_usages().items() if o == f"mcp:{nom}"]
    return max(vus).strftime("%Y-%m-%d %H:%M") if vus else "non mesuré"


def extensions_donnees():
    """Les données de la page « Extensions » (spec § 6), en LECTURE SEULE : {fichier, lisible, signalements, extensions}. LISTE BLANCHE des champs ;
    chaque valeur validée (nom, version, empreinte, agent, date) ou montrée par _montrable ; une clé inconnue n'est jamais montrée. Le coffre n'est
    pas lu (aucune valeur du coffre ne peut sortir d'ici) ; rien n'est écrit. Dernier usage : « non mesuré » (une skill n'a pas de trace d'usage ;
    MCP et outil du courtier : à leur lot)."""
    base = {"fichier": FICHIER_MONTRE, "lisible": True, "signalements": [], "extensions": []}
    try: etat = etat_extensions()
    except RefusExtension:
        base.update(lisible=False, signalements=[{"quoi": "extensions.toml illisible", "consequence": "aucune extension n'est donnée aux agents tant qu'il n'est pas corrigé ou revenu à sa sauvegarde .avant-…", "ton": "rouge"}])
        return base
    for g in GENRES:
        for nom, x in sorted((etat.get(g) or {}).items()):
            if not NOM.fullmatch(nom) or not isinstance(x, dict):
                base["signalements"].append({"quoi": f"une entrée [{g}] invalide", "consequence": "ignorée (nom ou forme invalide)", "ton": "jaune"}); continue
            version = x.get("version") if isinstance(x.get("version"), str) and VERSION.fullmatch(x["version"]) else None
            emp = x.get("empreinte") if isinstance(x.get("empreinte"), str) and re.fullmatch(r"[0-9a-f]{64}", x["empreinte"]) else None
            droits = x.get("droits") if isinstance(x.get("droits"), dict) else {}
            montres = [{"cle": k, "valeur": "oui" if v is True else "non" if v is False else ", ".join(_montrable(e) for e in v) if isinstance(v, list) else _montrable(v)}
                       for k, v in sorted(droits.items()) if k in CHAMPS_DROITS and k != "reseau_accorde"]
            d = RACINE / g / nom / (version or "")
            if version is None: etat_x = "écartée : version invalide dans extensions.toml"
            elif not d.is_dir() or d.is_symlink(): etat_x = "écartée : fichiers absents"
            elif g == "skill" and not (d / "SKILL.md").is_file(): etat_x = "écartée : SKILL.md absent"
            else: etat_x = "active"
            inst = x.get("installee") if isinstance(x.get("installee"), str) and re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", x["installee"]) else None
            agents = x.get("agents") if isinstance(x.get("agents"), list) else []
            base["extensions"].append({"genre": g, "nom": nom, "version": version or "invalide", "empreinte": emp[:12] if emp else "invalide",
                                       "description": _montrable(x.get("description", ""))[:200],
                                       "agents": [a for a in agents if isinstance(a, str) and re.fullmatch(r"[\w.-]+", a) and not a.startswith(".")],
                                       "droits": montres, "reseau": droits.get("reseau_accorde") is True,
                                       "installee": inst or "inconnue", "dernier_usage": _dernier_usage(g, nom), "etat": etat_x})
    return base


def liste_extensions(en_json, dire=print):
    l = donnees_liste()
    if en_json: dire(json.dumps(l, ensure_ascii=False, indent=2)); return 0
    if not l: dire("aucune extension installée"); return 0
    for x in l:
        dr = x["droits"]; reseau = " · RÉSEAU" if dr.get("reseau_accorde") else ""
        dire(f"{x['genre']:<6} {x['nom']:<24} {x['version']:<10} {x['empreinte'][:12]}  {x['etat']}{reseau}\n"
             f"       agents : {', '.join(x['agents']) or 'personne'} ; droits : {', '.join(f'{k} = {v}' for k, v in sorted(dr.items())) or 'aucun'} ; installée le {x['installee']}")
    return 0


AIDE_EXTENSION = ("berger extension verifier <genre> <source> [--agents a,b] [--reseau]   tous les contrôles, rien n'est écrit\n"
        "berger extension ajouter  <genre> <source> [--agents a,b] [--reseau]   (propriétaire) installe ; <source> = dossier absolu ou git:<dépôt>@<commit>\n"
        "berger extension retirer  <genre> <nom>                                 (propriétaire) retire ; fichiers gardés dans extensions/.retirees/\n"
        "berger extension revenir  <genre> <nom>                                 (propriétaire) la version d'avant\n"
        "berger extension liste    [--json]")


def _options(args):
    """(positionnels, agents, reseau, json) ; une option inconnue est un refus."""
    pos, ags, reseau, js, i = [], [], False, False, 0
    while i < len(args):
        a = args[i]
        if a == "--agents":
            if i + 1 >= len(args): raise RefusExtension("--agents : une liste a,b attendue")
            ags = [x.strip() for x in args[i + 1].split(",") if x.strip()]; i += 2; continue
        if a == "--reseau": reseau = True
        elif a == "--json": js = True
        elif a.startswith("--"): raise RefusExtension(f"option inconnue : {a[:20]}")
        else: pos.append(a)
        i += 1
    return pos, ags, reseau, js


def commande_extension(args, valeurs_coffre, regenerer, agent=None, dire=print, serveur_mcp=None):
    """`berger extension …` : → code de sortie (0, ou 1 pour un refus nommé, écrit sur la sortie d'erreur). `agent` : BERGER_AGENT de l'appelant ;
    `serveur_mcp` : la source des refus d'un serveur MCP (bin/berger), rejouée après l'écriture (lot 3)."""
    try:
        if not args: raise RefusExtension(AIDE_EXTENSION)
        verbe, (pos, ags, reseau, js) = args[0], _options(args[1:])
        if verbe == "liste" and not pos: return liste_extensions(js, dire)
        if verbe in ("verifier", "ajouter") and len(pos) == 2:
            genre, source = pos
            if genre not in GENRES: raise RefusExtension(f"genre inconnu : {genre[:20]} ({', '.join(GENRES)})")
            if verbe == "verifier": return verifier_extension(genre, source, ags, reseau, valeurs_coffre, dire)
            return ajouter_extension(genre, source, ags, reseau, valeurs_coffre, regenerer, agent, dire, serveur_mcp)
        if verbe in ("retirer", "revenir") and len(pos) == 2 and not ags and not reseau:
            genre, nom = pos
            if genre not in GENRES: raise RefusExtension(f"genre inconnu : {genre[:20]} ({', '.join(GENRES)})")
            if verbe == "retirer": return retirer_extension(genre, nom, regenerer, agent, dire)
            return revenir_extension(genre, nom, valeurs_coffre, regenerer, agent, dire, serveur_mcp)
        raise RefusExtension(AIDE_EXTENSION)
    except RefusExtension as ex:
        print(f"refusé : {_filtrer_refus(str(ex), valeurs_coffre)}", file=sys.stderr); return 1


def _filtrer_refus(texte, valeurs_coffre):
    """Dernier passage sur un message de refus (un nom de lien, de fichier, une valeur citée par un refus en amont du contrôle de contenu) :
    une valeur du coffre ou une marque privée y devient « [masqué] ». Rend le texte FILTRÉ, jamais une valeur."""
    try: valeurs = valeurs_coffre() or {}
    except Exception: valeurs = {}
    for v in sorted((v for v in valeurs if v), key=len, reverse=True): texte = texte.replace(v, "[masqué]")
    for x in CONFIG.get("marques_privees", []) or []:
        if isinstance(x, str) and len(x) >= 3: texte = re.sub(re.escape(x), "[masqué]", texte, flags=re.I)
    return texte


__all__ = ("RefusExtension", "commande_extension", "extensions_donnees", "TELECHARGE", "telecharge", "recharger_mcp", "mcp_reseau", "lignes_reseau_mcp", "serveurs_mcp_extensions", "skill_installee", "donnees_liste", "etat_extensions", "empreinte_paquet")
