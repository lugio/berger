# -*- coding: utf-8 -*-
"""Les PORTES d'une équipe (processus de dév générique, docs/plans/2026-10-12-processus-dev-generique-spec.md) — pas un
type d'outil : partagé par equipe_dev (le développeur les joue avant sa demande) et equipe_chef (le relecteur les rejoue).

Quatre portes, dans cet ordre, déclarées par projet dans [equipes.<projet>], chacune sous la même forme que verify :
  <porte> = "commande"            lancée dans la copie, en bac à sable
  <porte>_outil = "<outil> <verbe>"  verbe de LECTURE d'un outil du courtier, qui reçoit la branche POUSSÉE
verify (rapide), tests (suite complète), gate (facultative), pret (finition du projet — OBLIGATOIRE pour demander ou
fusionner). Résultat de chaque porte : « vert », « rouge » ou « non mesuré » (porte absente) — jamais vert par défaut."""
import datetime, importlib.util, json, os, posixpath, re, subprocess
from pathlib import Path

import importlib.util
_spec_transport = importlib.util.spec_from_file_location('berger_transport', Path(__file__).with_name('_transport.py'))
_transport = importlib.util.module_from_spec(_spec_transport); _spec_transport.loader.exec_module(_transport)

PORTES = ("verify", "tests", "gate", "pret")
VERT, ROUGE, NON_MESURE = "vert", "rouge", "non mesuré"
# Fichiers de test (correctif → le test qui reproduit le bug) : dossier tests/test/spec/__tests__, test_*.py, *.test.js, *_spec.rb…
MOTIF_TESTS = r"(^|/)(tests?|spec|__tests__)/|(^|/)test_[^/]*$|[._-](test|spec)\.[^/]+$"
CORRECTIF = re.compile(r"fix(\([^)]*\))?!?:")                       # Conventional Commits : fix: / fix(x): / fix!:
CAUSE = re.compile(r"(?i)\bcause racine\s*:")


# ── porte courte « documentation seule » (spec 2026-10-28-portes-allegees-spec.md) : le COURTIER lit le diff, l'agent ne déclare rien ──
EXT_DOC = (".md", ".png", ".jpg", ".svg", ".webp", ".txt")                 # sous docs/ seulement ; à la racine du dépôt : *.md (dont CHANGELOG.md)
# Exclusions INCOMPRESSIBLES (relecture n°67, indépendantes de motif_tests) : le code, les scripts et tout fichier lu par un agent ne sont jamais de la documentation
EXCLUS_DEBUT = ("bin/", "courtier/", "tests/", "crochets/", "hooks/", "herdr-plugin/", "commun/", "docs/scripts/")
EXCLUS_DOSSIERS = ("consignes", "skills", "skills-agent", "modeles", "pending", "memoire", "memory", "taches", "scripts", "hooks", "crochets", "tests")
RACINE_DOC = ("README.md", "README.fr.md", "CHANGELOG.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md")   # à la racine : cette liste FERMÉE, rien d'autre
MOTS_INTERDITS = ("agents", "claude", "soul", "gemini", "codex", "heartbeat", "mission", "memory", "skill", "consigne")   # sous docs/ : jamais dans un nom (casse ignorée)
MODES_DOC = ("100644", "000000")                                           # ni lien symbolique, ni exécutable, ni sous-module (000000 = ajout/suppression)
COURT = "documentation seule"


def declaree_doc(reglages):
    """("commande", cmd) | ("outil", "<outil> <verbe>") | None — la porte courte `doc` / `doc_outil`, même forme que verify."""
    if reglages.get("doc_outil"): return ("outil", reglages["doc_outil"])
    if reglages.get("doc"): return ("commande", reglages["doc"])
    return None


_conftexte = None


def conf_texte(texte):
    """Le LECTEUR RÉEL d'agent.conf (bin/noyau/conftexte.py, le même que celui de bin/berger : commentaires `#` retirés)."""
    global _conftexte
    if _conftexte is None:
        spec = importlib.util.spec_from_file_location("berger_conftexte", Path(__file__).resolve().parents[2] / "bin/noyau/conftexte.py")
        _conftexte = importlib.util.module_from_spec(spec); spec.loader.exec_module(_conftexte)
    return _conftexte.conf_texte(texte)


def chemins_consigne(installation=None, depots=()):
    """Les chemins que la configuration désigne comme consigne d'un agent (`consigne_fichier =` de <installation>/agents/*/agent.conf,
    injecté dans la consigne système par bin/berger : `dossier(a) / f`, donc depuis le dossier de l'agent) : jamais de la documentation,
    même sous docs/. Chaque valeur est résolue (realpath : « ../ » et liens) ; on garde le chemin ABSOLU (un chemin du diff est exclu s'il en
    est un suffixe : copie de projet sous l'installation), le chemin relatif à l'installation ou à un dépôt de `depots`, et TOUJOURS le repli
    prudent « */<nom du fichier> » (refus de tout fichier de ce nom). → ensemble de chaînes."""
    install = Path(installation or os.environ.get("BERGER_DIR") or Path(__file__).resolve().parents[2])
    racines = [os.path.realpath(r) for r in (install, *depots)]; out = set()
    for conf in sorted((install / "agents").glob("*/agent.conf")):
        try: v = conf_texte(conf.read_text()).get("consigne_fichier", "").strip("\"'")
        except OSError: continue
        if not v: continue
        absolu = os.path.realpath(conf.parent / os.path.expanduser(v))
        out.add(absolu); out.add("*/" + posixpath.basename(absolu))        # le chemin résolu (comparé par suffixe) ET le repli prudent par nom
        for r in racines:
            if absolu.startswith(r.rstrip("/") + "/"): out.add(posixpath.relpath(absolu, r))
    return out


def chemin_documentaire(chemin, consignes=()):
    """LISTE POSITIVE : à la racine, les seuls documents publics de RACINE_DOC ; sous docs/, du texte ou des images dont le nom ne contient
    aucun mot de MOTS_INTERDITS. Puis les exclusions incompressibles (dossiers de code, scripts, fichiers lus par les agents) et tout
    chemin désigné comme consigne par la configuration. Tout le reste : porte complète."""
    bas = chemin.lower(); parties = bas.split("/")
    if chemin.startswith("/") or ".." in parties or bas.startswith(EXCLUS_DEBUT): return False
    if any(x in EXCLUS_DOSSIERS for x in parties[:-1]): return False
    if any(c == chemin or (c.startswith("*/") and parties[-1] == c[2:].lower()) or (c.startswith("/") and c.lower().endswith("/" + bas)) for c in consignes): return False
    if len(parties) == 1: return chemin in RACINE_DOC
    return bas.startswith("docs/") and bas.endswith(EXT_DOC) and not any(m in parties[-1] for m in MOTS_INTERDITS)


def documentation_seule(git, base, tete, motif_tests=MOTIF_TESTS, consignes=None, depots=()):
    """La demande ne touche-t-elle QUE de la documentation ? Lu dans le diff `base...tete` du dépôt qui porte la branche
    (git(*args) comme controler_demande), jamais déclaré par l'agent. → (vrai, « N fichiers ») ou (faux, la raison : le premier
    fichier hors périmètre). Diff vide ou illisible : faux. --no-renames : un renommage liste la source ET la cible."""
    r = git("diff", "--raw", "--no-renames", "-z", f"{base}...{tete}")
    if r.returncode: return False, "diff illisible"
    mots = r.stdout.split("\0"); fichiers = []; consignes = chemins_consigne(depots=depots) if consignes is None else consignes
    for i in range(0, len(mots) - 1, 2):
        meta, chemin = mots[i].split(), mots[i + 1]
        if len(meta) < 2 or not mots[i].startswith(":"): return False, "diff illisible"
        if meta[0][1:] not in MODES_DOC or meta[1] not in MODES_DOC: return False, f"{chemin} n'est pas un fichier ordinaire (lien, exécutable ou sous-module)"
        if not chemin_documentaire(chemin, consignes) or re.search(motif_tests, chemin):
            return False, f"{chemin} n'est pas de la documentation"
        fichiers.append(chemin)
    if not fichiers: return False, "diff vide"
    return True, f"{len(fichiers)} fichier{'s' if len(fichiers) > 1 else ''}"


def choisir(portes, doc, git, base, tete, motif_tests=MOTIF_TESTS, depots=()):
    """Les portes à jouer. doc non déclarée : celles du projet, sans message. Sinon, documentation seule → la porte doc remplace
    `tests` (les 4 portes restent) ; sinon la complète, et le message nomme le fichier. → (portes, court, message | None)."""
    if not doc: return portes, False, None
    seule, raison = documentation_seule(git, base, tete, motif_tests, depots=depots)
    if not seule: return portes, False, f"porte complète : {raison}"
    return {**portes, "tests": doc}, True, f"porte courte ({COURT} : {raison}) — tests complets non joués"


def marquer_court(res, court):
    """La porte `tests` jouée à la place par `doc` le dit dans son résultat (inscrit, signé, rejoué comme les autres)."""
    if court and res.get("tests", {}).get("etat") != NON_MESURE: res["tests"]["court"] = COURT
    return res


def declarees(reglages):
    """{porte: ("commande", cmd) | ("outil", "<outil> <verbe>")} — l'outil l'emporte s'il est déclaré."""
    out = {}
    for p in PORTES:
        if reglages.get(f"{p}_outil"): out[p] = ("outil", reglages[f"{p}_outil"])
        elif reglages.get(p): out[p] = ("commande", reglages[p])
    return out


def bilan(sortie):
    """La dernière ligne non vide de la sortie (souvent le compte des contrôles) : ce que le relecteur recompte."""
    return next((l.strip() for l in reversed(str(sortie).splitlines()) if l.strip()), "")[:200]


def resultat(code, sortie):
    return {"etat": VERT if code == 0 else ROUGE, "code": code, "bilan": bilan(sortie)}


SHA_COMMIT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")                    # SHA-1 ou SHA-256 complet
ATTESTATION = "commit testé : "                                              # ligne qu'une porte distante écrit pour être verte


def sha_valide(sha):
    """Un SHA de commit complet, jamais un nom de branche (spec 2026-10-29-sha-fige) → sha (ValueError sinon)."""
    if not isinstance(sha, str) or not SHA_COMMIT.fullmatch(sha):
        raise ValueError(f"commit figé mal formé (« {str(sha)[:60]} ») : un SHA complet est attendu, jamais une branche")
    return sha


def attestation(sortie, sha):
    """Ce qui manque à la sortie d'une porte distante pour être verte → None, ou le défaut. Exactement UNE ligne « commit testé :
    <sha> », avec CE sha : deux lignes (même identiques) ou un autre SHA → rouge. C'est une DÉCLARATION de l'outil, pas une
    preuve : elle arrête un outil qui teste par erreur la branche, pas un outil malveillant (manuel, « SHA figé »)."""
    lignes = [l.strip()[len(ATTESTATION.strip()):].strip() for l in str(sortie).splitlines() if l.strip().startswith(ATTESTATION.strip())]
    if not lignes: return f"n'a pas prouvé avoir testé {sha} (ligne « {ATTESTATION}{sha} » absente)"
    if len(lignes) > 1: return f"n'a pas prouvé avoir testé {sha} : plusieurs lignes d'attestation ({', '.join(x[:40] or '(vide)' for x in lignes)}) : une seule « {ATTESTATION}{sha} » est attendue"
    if lignes[0] != sha: return f"n'a pas prouvé avoir testé {sha} : il atteste un autre commit ({lignes[0][:64] or '(vide)'})"
    return None


def distante(verbe, sha):
    """Une porte <porte>_outil jouée sur `sha` (jamais une branche : un push pendant le test ferait tester un autre commit).
    Verte seulement si sa sortie porte UNE ligne « commit testé : <sha> », avec CE sha → {code, sortie}."""
    r = verbe([sha_valide(sha)]); r = r if isinstance(r, dict) else {"code": 1, "sortie": str(r)}
    sortie = str(r.get("sortie", ""))
    defaut = attestation(sortie, sha) if r.get("code", 1) == 0 else None
    if defaut: return {**r, "code": 1, "sortie": f"{sortie}\nl'outil {defaut} : porte rouge"}
    return r


def jouer(portes, commande, outil):
    """Joue les 4 portes dans l'ordre, sans s'arrêter à la première rouge (le message les donne toutes).
    commande(porte, cmd) et outil(porte) rendent (code, sortie). → {porte: {etat, code, bilan}}, sorties {porte: texte}."""
    res, sorties = {}, {}
    for p in PORTES:
        if p not in portes: res[p] = {"etat": NON_MESURE}; continue
        genre, valeur = portes[p]
        try: code, sortie = commande(p, valeur) if genre == "commande" else outil(p)
        except Exception as e: code, sortie = 1, f"porte {p} injouable : {e}"
        res[p] = resultat(code, sortie); sorties[p] = str(sortie)
    return res, sorties


def rouges(res):
    return [p for p, r in res.items() if r["etat"] == ROUGE]


def resume(res):
    return " ; ".join(f"{p} : {r['etat']}" + (f", {r['quand']}" if r.get("quand") else "") + (f" ({r['bilan']})" if r.get("bilan") else "")
                      + (f" [porte courte : {r['court']}]" if r.get("court") else "")
                      for p, r in res.items())


def completer(res, demande):
    """Les portes NON rejouées (« non mesuré » ici) reprennent le résultat inscrit dans la demande, sur le même commit, avec
    sa date (« vert, à la demande du 13/10 19:34 ») ; « non mesuré » ne reste que pour une porte jamais jouée (13/10/2026 :
    le résumé d'une fusion en avance rapide disait « verify : non mesuré » pour une porte jouée et verte)."""
    quand = str(demande.get("demande", ""))
    try: quand = datetime.datetime.fromisoformat(quand).strftime("à la demande du %d/%m %H:%M")
    except ValueError: quand = "à la demande"
    out = dict(res)
    for p, r in res.items():
        a = (demande.get("portes") or {}).get(p) or {}
        if r.get("etat") == NON_MESURE and a.get("etat") in (VERT, ROUGE): out[p] = {**a, "quand": quand}
    return out


def correctifs(commits, fichiers, texte_demande, motif_tests=MOTIF_TESTS):
    """Règle du correctif (SSDF PW.8.2 ex. 3, RV.3) : une branche qui contient un commit fix… touche un fichier de test (le
    test qui reproduit le bug), et chaque fix… écrit sa cause racine (« Cause racine : … ») — dans son message ou, à défaut
    (l'historique poussé ne se réécrit pas), dans le texte de la demande. commits = [(sujet, message complet)]. → problèmes."""
    fix = [(s, m) for s, m in commits if CORRECTIF.match(s)]
    if not fix: return []
    out = []
    if not any(re.search(motif_tests, f) for f in fichiers):
        out.append(f"correctif ({fix[0][0][:80]}) sans test qui reproduit le bug : ajoute-le (fichier de test touché par la branche)")
    if not CAUSE.search(texte_demande):
        sans = [s[:80] for s, m in fix if not CAUSE.search(m)]
        if sans: out.append(f"correctif sans cause racine ({'; '.join(sans)}) : écris « Cause racine : … » dans le commit ou dans la demande")
    return out


# ── demande de fusion : les MÊMES contrôles et la même inscription, branche d'un développeur ou du chef de projet ──
def controler_demande(git, tete, branche, principale, resume, portes, motif_tests=MOTIF_TESTS, sale=False, maj="lance « mettre-a-jour »",
                      pret=True):
    """Ce qui refuse une demande avant les portes. git(*args) lance git (hooks désactivés) dans le dépôt qui porte la
    branche ; tete = sa référence locale (HEAD dans la copie d'un développeur, refs/heads/<branche> chez le chef) ;
    sale = des changements non commités sur cette branche ; pret = False : la finition est au chef (`finition = "chef"`),
    la porte pret n'est pas exigée ici. → le commit demandé (ValueError sinon)."""
    if len(resume) < 10: raise ValueError("donne un résumé lisible (ce qui est livré, tests joués, migrations)")
    if sale: raise ValueError("ta copie a des changements non commités : commite d'abord")
    git("fetch", "origin", principale, branche)
    commit = git("rev-parse", "--verify", "--quiet", tete).stdout.strip()
    if not commit or not git("log", "--oneline", f"origin/{principale}..{tete}").stdout.strip():
        raise ValueError(f"aucun commit à fusionner par rapport à {principale}")
    if git("rev-parse", f"origin/{branche}").stdout.strip() != commit:
        raise ValueError("ta branche n'est pas poussée telle quelle : lance « pousser » d'abord")
    if git("merge-base", "--is-ancestor", f"origin/{principale}", tete).returncode:
        raise ValueError(f"ta branche n'est pas à jour avec {principale} : {maj}, reteste, repousse")
    if pret and "pret" not in portes:
        raise ValueError("aucune porte « pret » déclarée pour ce projet (pret ou pret_outil dans [equipes.<projet>]) : "
                         "la finition du projet est obligatoire — préviens ton chef de projet, le propriétaire la déclare")
    base = f"origin/{principale}"
    commits = [tuple(c.strip("\n").split("\x00", 1)) for c in git("log", "--format=%s%x00%B%x1e", f"{base}..{tete}").stdout.split("\x1e")
               if "\x00" in c]                                         # [(sujet, message complet)]
    probleme = correctifs(commits, git("diff", "--name-only", f"{base}...{tete}").stdout.split(), resume, motif_tests)
    if probleme: raise ValueError("règle du correctif : " + " ; ".join(probleme))
    return commit


def refuser_rouges(res, sorties):
    if rouges(res):
        raise ValueError("porte rouge : pas de demande (la branche doit être saine) — " + resume(res) + "\n"
                         + "\n".join(f"--- {p}\n{sorties.get(p, '')[-800:]}" for p in rouges(res)))


RESUME_MAX = 8000                                                         # le résumé d'une demande, gardé en entier jusque-là


def signer(res, par, quand):
    """Chaque porte JOUÉE porte qui l'a jouée et quand (joue_par, joue_le) ; « non mesuré » reste tel quel (spec interface §6.4)."""
    return {p: ({**r, "joue_par": par, "joue_le": quand} if r.get("etat") != NON_MESURE else r) for p, r in res.items()}


def inscrire_demande(demandes, sujet, branche, commit, texte, agent, res, a="chef de projet", **plus):
    """La demande « à relire » (demandes/<sujet>.json, lue par l'outil du chef) et sa trace dans le panneau Échanges. → la demande."""
    quand = datetime.datetime.now().isoformat(timespec="minutes")
    d = {"sujet": sujet, "branche": branche, "commit": commit, "resume": texte[:RESUME_MAX], "tronque": len(texte) > RESUME_MAX, "agent": agent,
         "portes": signer(res, agent, quand), "etat": "à relire", "demande": quand, **plus}
    demandes.mkdir(parents=True, exist_ok=True)
    (demandes / f"{sujet}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    _transport.executer(str(Path(__file__).resolve().parents[2] / "bin/berger"), ['echange', agent or sujet, a, 'demande de fusion', f'{sujet} : {texte[:1200]}'], capture_output=True)
    return d



# ── Règle de go (docs/plans/2026-10-15-regle-go-spec.md, point b) : un sujet « règle de go » ne s'ouvre et ne se demande
# qu'avec le go INSCRIT du propriétaire sur une spec nommée (equipes/<projet>/go/<sujet>.json, écrit par `berger equipe go`
# après sa validation). Vécu le 15/10 : du code lancé sur un sujet de mots de passe après une simple réponse à des questions.
# Mots par défaut : seulement ceux des cinq cas de la règle (ni « courtier » ni « garde » : exception du cœur, pas règle de go).
# Cas 1 complété le 16/10 (remarque de l'agent d'infrastructure) : les autres noms courants d'un secret — « identifiants du portail fiscal » passait.
GO_MOTS = ("mot de passe", "mots de passe", "mdp", "secret", "secrets", "coffre", "identifiant", "identifiants", "jeton", "jetons",
           "token", "tokens", "clé d'api", "clé d’api", "clés d'api", "clés d’api", "credentials", "droits", "authentification",
           "logiciel métier", "production", "pare-feu")
GO_CAS = re.compile(r"(?im)^\s*règle de go\s*:\s*cas\s*([1-5](?:\s*,\s*[1-5])*)\s*$")     # déclaré par le chef dans la mission
HORS_GO = re.compile(r"(?im)^\s*hors go\s*:\s*(.+?)\s*$")                                  # faux positif des mots, raison tracée
HORS_GO_MIN = 20


def empreinte(texte):
    import hashlib
    return hashlib.sha256(texte.encode()).hexdigest()


def mots_go(texte, mots=None):
    """Les mots de la règle de go trouvés dans `texte` (mots entiers, sans casse : « secrétariat » n'est pas « secret »)."""
    return [m for m in (mots or GO_MOTS) if re.search(r"(?<!\w)" + re.escape(m) + r"(?!\w)", texte or "", re.I)]


def go_lu(go, sujet):
    """Le fichier de go du sujet ({etat: demandé|inscrit, spec, empreinte, validation…}) ou None."""
    try: return json.loads((Path(go) / f"{sujet}.json").read_text())
    except (OSError, ValueError): return None


def marquage(go, sujet, mission, mots=None):
    """Pourquoi le sujet est « règle de go » : [] s'il ne l'est pas. Fichier de go (même seulement demandé), cas déclarés
    dans la mission (« Règle de go : cas 1 »), ou mots de la règle dans la mission (seuls levables par « Hors go : … »)."""
    r = []
    if go_lu(go, sujet) is not None: r.append("go demandé pour ce sujet")
    c = GO_CAS.search(mission or "")
    if c: r.append(f"déclaré : cas {c.group(1).replace(' ', '')}")
    m = mots_go(mission, mots)
    if m: r.append("mots : " + ", ".join(m))
    return r


def hors_go(mission):
    """La raison « Hors go : … » de la mission (≥ 20 caractères), sinon None."""
    h = HORS_GO.search(mission or "")
    return h.group(1) if h and len(h.group(1)) >= HORS_GO_MIN else None


def go_de_la_demande(go, sujet, mission, spec_lue, mots=None):
    """Le champ « go » d'une demande de fusion (inscrit comme les portes), ou None si le sujet n'est pas de la règle de go.
    spec_lue(chemin) → le texte de la spec dans la branche demandée (None si absente). ValueError = demande refusée :
    sujet marqué sans go inscrit, ou spec changée depuis le go."""
    g = go_lu(go, sujet)
    if g and g.get("etat") == "inscrit":
        t = spec_lue(g["spec"])
        if t is not None and empreinte(t) != g["empreinte"]:
            raise ValueError(f"règle de go : la spec {g['spec']} a changé depuis le go n° {g.get('validation') or '?'} — "
                             f"redemande le go sur cette version (berger-outil equipe go …), ou remets la spec validée")
        return {"validation": g.get("validation"), "spec": g["spec"], "empreinte": g["empreinte"], "spec_dans_branche": t is not None}
    raisons = marquage(go, sujet, mission, mots)
    if not raisons: return None
    h = (Path(go) / f"{sujet}.hors-go.json")
    if g is None and not GO_CAS.search(mission or "") and h.is_file():
        return {"hors_go": json.loads(h.read_text()).get("raison", "")}
    raise ValueError(f"règle de go : sujet « {sujet} » marqué ({' ; '.join(raisons)}) sans go inscrit du propriétaire — "
                     f"pas de demande ; le chef ou le coordinateur demande le go : berger-outil equipe go --fichier .transport/requete.json (JSON : <projet> {sujet} <cas> <spec>)")


# ── SemVer 2.0.0 (semver.org, expression régulière officielle ; §11 précédence) ──
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
                    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?")


def precedence(version):
    """Clé de tri SemVer §11 (la métadonnée de construction « +… » est ignorée) ; None si ce n'est pas une version SemVer."""
    m = SEMVER.fullmatch(version)
    if not m: return None
    pre = m.group(4)
    ids = tuple((0, int(x), "") if x.isdigit() else (1, 0, x) for x in pre.split(".")) if pre else ()
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), 0 if pre else 1, ids)


def entree_journal(changelog, version):
    """L'entrée « ## [<version>] - AAAA-MM-JJ » d'un CHANGELOG.md (Keep a Changelog 1.1.0), jusqu'à la suivante ; None si absente.
    Un titre APRÈS la date, séparé par un espace, est toléré (MonCab : « ## [3.480.2] - 2026-10-05 — *Titre* ») ; rien
    avant « ## », et la date doit exister."""
    lignes = changelog.splitlines()
    tete = re.compile(r"##\s*\[" + re.escape(version) + r"\]\s*-\s*(\d{4}-\d{2}-\d{2})(\s.*)?")
    for i, l in enumerate(lignes):
        m = tete.fullmatch(l.strip())
        if m and date_valide(m.group(1)):
            fin = next((j for j in range(i + 1, len(lignes)) if lignes[j].startswith("## ")), len(lignes))
            corps = "\n".join(lignes[i:fin]).strip()
            return corps if len(corps.splitlines()) > 1 and any(x.strip() for x in lignes[i + 1:fin]) else None
    return None


def date_valide(texte):
    try: datetime.date.fromisoformat(texte); return True
    except ValueError: return False
