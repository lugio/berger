"""Publication vers le dépôt en ligne (spec docs/plans/2026-10-29-publication-github-spec.md) : après une installation réussie,
le commit installé et contrôlé part sur le remote de `publication` ([equipes.<p>] qui a `installer_outil`), en avance rapide
seule ; l'action manuelle `publier` emploie la même fonction.

Écart de place : la spec la mettait dans bin/berger ; elle est ici à cause du cliquet de taille de bin/berger
(tests/taille-fichiers.py). Comportement identique. INSTALLATIONS et trace_installation y sont DÉPLACÉS tels quels depuis
bin/berger (même fichier, même format de ligne) : l'installation, le redémarrage et la publication écrivent la même trace.
Module du cœur : il n'importe pas bin/berger ; il n'est ni l'API de lecture ni l'API d'action (absent de noyau/api.py)."""
import datetime, os, re, subprocess
from noyau.config import *
from noyau.lectures import *
from noyau.bandeaux import *

INSTALLATIONS = BERGER / "courtier/installations.log"


def trace_installation(avant, apres, etat, detail):
    INSTALLATIONS.parent.mkdir(parents=True, exist_ok=True)
    with open(INSTALLATIONS, "a") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\t{avant[:10]}\t{apres[:10]}\t{etat}\t{' '.join(detail.split())[:400]}\n")


# Vécu : après les fusions n° 48, 54, 74/75, 80, 82 et 84, rien n'était parti en ligne ; `publier` visait un remote absent.
def publication_active():
    """Une équipe à `installer_outil` a `publication` : installer passe `--publier <forge>` (l'équipe de CETTE forge est cherchée ensuite)."""
    return any(e.get("publication") for e in EQUIPES.values() if e.get("installer_outil"))


def equipes_installation(forge):
    """Les équipes à `installer_outil` dont le dépôt (`depot`) a CETTE forge pour origin — renvoi n° 90 : l'option n'est plus prise
    dans « la première équipe à installer_outil », sans lien avec la forge demandée ; plus d'une = ambiguïté, refusée."""
    cible = os.path.realpath(forge_absolue(forge))
    def forge_de(e):
        if not e.get("depot"): return ""
        r = git_publication(os.path.expanduser(str(e["depot"])), "remote", "get-url", "origin"); url = r.stdout.strip().removeprefix("file://")
        return os.path.realpath(os.path.expanduser(url)) if r.returncode == 0 and url else ""
    return [e for e in EQUIPES.values() if e.get("installer_outil") and forge_de(e) == cible]


def forge_absolue(forge):
    f = os.path.expanduser(forge); return os.path.abspath(f) if os.path.isdir(f) else forge


def git_publication(forge, *a):
    """git dans la forge, sans invite (GIT_TERMINAL_PROMPT=0), délai borné : un réseau muet devient une cause, pas une attente ;
    git impossible à lancer (OSError) aussi."""
    try: return subprocess.run(["git", "-C", str(forge), *a], capture_output=True, text=True, timeout=120, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except subprocess.TimeoutExpired: return subprocess.CompletedProcess(a, 124, "", "délai dépassé (120 s)")
    except OSError as e: return subprocess.CompletedProcess(a, 127, "", f"git impossible ({type(e).__name__})")


# Renvoi n° 90 : la fin de la sortie de git allait telle quelle dans installations.log et les notifications (URL avec identifiant, jeton)
MASQUES_SORTIE = ((re.compile(r"(\w[\w+.-]*://)[^/\s@'\"]+@"), r"\1***@"),                                 # identifiants d'URL
                  (re.compile(r"\b(gh[pousr]_|github_pat_|glpat-|xox[abps]-)[\w-]+"), r"\1***"),              # jetons de forme connue
                  (re.compile(r"(?i)\b(token|jeton|password|passwd|authorization|bearer|secret)(\s*[=:]\s*|\s+)[^\s'\"]+"), r"\1\2***"),
                  (re.compile(r"\b(?![0-9a-f]{40}\b)(?=[\w-]*\d)(?=[\w-]*[A-Za-z])[\w-]{24,}"), "***"))          # longue suite lettres+chiffres, hors SHA


def masquer(texte):
    for motif, par in MASQUES_SORTIE: texte = motif.sub(par, texte)
    return texte


def cause_publication(sortie):
    """La cause nommée ; sinon les 200 derniers caractères de git, MASQUÉS (jamais la sortie brute)."""
    s = sortie.lower()
    if any(x in s for x in ("non-fast-forward", "fetch first", "[rejected]")):
        return "divergence (le dépôt en ligne a des commits absents de la forge : synchroniser)"
    if any(x in s for x in ("permission denied", "publickey", "host key verification failed", "authentication failed")): return "clé refusée"
    if any(x in s for x in ("could not resolve", "timed out", "connection refused", "network is unreachable", "délai dépassé", "connection closed")): return "réseau"
    return masquer(" ".join(sortie.split()))[-200:] or "git en échec"


def echec_publication(avant, commit, cause):
    """« publication échouée : <cause> » dans installations.log ET notification urgente ; l'un qui échoue n'empêche pas l'autre et
    rien ne remonte (le redémarrage reste à 0). Seule la cause est écrite : jamais la sortie brute de git."""
    texte = f"publication échouée : {cause}"
    for geste in (lambda: trace_installation(avant or commit, commit, texte, "rien n'est réessayé ; la forge locale reste la référence"),
                  lambda: notifier("Berger · publication échouée", f"{cause} — {commit[:10] or 'aucun commit'} n'est pas en ligne ; la forge locale reste la référence", urgent=True)):
        try: geste()
        except Exception as e: print(f"{texte} ({type(e).__name__} en traçant l'échec)")
    return False, texte


def publier_forge(forge, commit, remote, avant=None):
    """<commit> de la forge part sur refs/heads/main de <remote>, en avance rapide SEULEMENT : jamais --force, --mirror ni refspec en
    « + » (git refuse ce qui n'est pas une avance rapide), jamais d'étiquette suivie (--no-follow-tags) ; puis les étiquettes v* qui
    en sont des ancêtres, une par une, par leur OID figé (une étiquette en ligne n'est jamais remplacée) ; puis fetch et contrôle
    par ls-remote. Réussite ou échec : une ligne dans courtier/installations.log ; un échec est notifié en urgence, jamais
    réessayé — la forge locale reste la référence ; aucune exception ne sort. → (ok, texte)."""
    commit = str(commit or "")
    try: return _publier_forge(forge, commit, remote, avant or commit)
    except Exception as e: return echec_publication(avant, commit, f"erreur locale ({type(e).__name__})")


def _publier_forge(forge, commit, remote, avant):
    echec, g = (lambda cause: echec_publication(avant, commit, cause)), (lambda *a: git_publication(forge, *a))
    lignes = lambda r: [l.strip() for l in r.stdout.splitlines() if l.strip()]
    # un HEAD illisible donnait « :refs/heads/main », une SUPPRESSION de la branche en ligne (renvoi n° 90)
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or g("rev-parse", "-q", "--verify", f"{commit}^{{commit}}").stdout.strip() != commit:
        return echec("commit invalide (un SHA complet d'un commit de la forge est exigé)")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", remote or ""): return echec(f"remote absent ({remote or 'aucun'})")
    lecture, envoi = g("remote", "get-url", "--all", remote), g("remote", "get-url", "--push", "--all", remote)
    if lecture.returncode or not lignes(lecture): return echec(f"remote absent ({remote})")
    # destinations EFFECTIVES de l'envoi (pushurl, pushInsteadOf) : une seule, la même que celle que relit le contrôle
    if envoi.returncode or len(lignes(envoi)) != 1 or len(lignes(lecture)) != 1:
        return echec(f"destinations multiples pour {remote} ({len(lignes(envoi))} d'envoi, {len(lignes(lecture))} de lecture) : une seule est permise")
    if lignes(envoi) != lignes(lecture): return echec(f"destination d'envoi de {remote} différente de son URL (pushurl) : le contrôle relirait un autre dépôt")
    if g("config", "--bool", f"remote.{remote}.mirror").stdout.strip() == "true":
        return echec(f"remote {remote} en miroir (refusé : un miroir écrase le dépôt en ligne)")
    r = g("for-each-ref", "--merged", commit, "--format=%(objectname) %(refname)", "refs/tags/v*")
    if r.returncode: return echec(f"étiquettes illisibles dans la forge ({cause_publication(r.stdout + r.stderr)})")
    etiquettes = [(o, ref.removeprefix("refs/tags/")) for o, ref in (l.split(" ", 1) for l in lignes(r) if " " in l)]   # OID figés ici
    pousser = lambda ref: g("push", "--porcelain", "--no-follow-tags", remote, ref)
    r = pousser(f"{commit}:refs/heads/main")
    if r.returncode: return echec(cause_publication(r.stdout + r.stderr))
    for oid, v in etiquettes:
        r = pousser(f"{oid}:refs/tags/{v}")
        if r.returncode:
            sortie = r.stdout + r.stderr
            return echec(f"étiquette {v} différente en ligne" if "[rejected]" in sortie or "already exists" in sortie else cause_publication(sortie))
    r = g("fetch", "-q", remote)
    if r.returncode: return echec(f"contrôle après l'envoi impossible : {cause_publication(r.stdout + r.stderr)}")
    # contrôle sur le dépôt en ligne lui-même (ls-remote), jamais sur une référence locale qui peut être périmée
    r = g("ls-remote", remote, "refs/heads/main", *(f"refs/tags/{v}" for _, v in etiquettes))
    if r.returncode: return echec(f"contrôle après l'envoi impossible : {cause_publication(r.stdout + r.stderr)}")
    lu = {ref: o for o, ref in (l.split("\t", 1) for l in lignes(r) if "\t" in l)}
    if lu.get("refs/heads/main") != commit: return echec(f"contrôle : en ligne/main = {lu.get('refs/heads/main', '?')[:10]}, pas {commit[:10]}")
    ecarts = [v for o, v in etiquettes if lu.get(f"refs/tags/{v}") != o]
    if ecarts: return echec(f"contrôle : étiquette(s) {', '.join(ecarts)} absente(s) ou différente(s) en ligne")
    texte = f"publié : {commit[:10]} → {remote}"
    trace_installation(avant, commit, texte, f"étiquettes : {', '.join(v for _, v in etiquettes) or 'aucune'} ; avance rapide, sans force, contrôlé (ls-remote)")
    return True, texte


def publier_installation(forge, commit, avant):
    """Après « courtier redémarré » (redemarrer_controle) : <commit> part en ligne si `--publier <forge>` est donné ET l'option
    `publication` de l'équipe de CETTE forge est active. Un échec est tracé et notifié, l'installation reste : → 0, toujours."""
    if not forge or not publication_active(): return 0
    try:
        equipes = equipes_installation(forge)
        if len(equipes) > 1: print(echec_publication(avant, commit, f"option publication ambiguë : {len(equipes)} équipes à installer_outil sur la forge {forge}")[1])
        elif not equipes: print(echec_publication(avant, commit, f"aucune équipe à installer_outil n'a pour dépôt un clone de la forge {forge}")[1])
        elif equipes[0].get("publication"): print(publier_forge(forge, commit, str(equipes[0]["publication"]), avant)[1])
    except Exception as e: print(echec_publication(avant, str(commit or ""), f"erreur locale ({type(e).__name__})")[1])
    return 0


def publier_main(forge):
    """Action manuelle `publier` (validée à chaque fois) : main de la forge, la même fonction que la publication automatique ; le
    remote de l'option de l'équipe de cette forge, sinon origin. Tout échec (même sans main) est tracé et notifié."""
    f = forge_absolue(forge)
    try:
        equipes = equipes_installation(f)
        if len(equipes) > 1: ok, texte = echec_publication("", "", f"option publication ambiguë : {len(equipes)} équipes à installer_outil sur la forge {forge}")
        else:
            commit = git_publication(f, "rev-parse", "-q", "--verify", "refs/heads/main^{commit}").stdout.strip()
            ok, texte = publier_forge(f, commit, str((equipes[0].get("publication") if equipes else "") or "origin"))
    except Exception as e: ok, texte = echec_publication("", "", f"erreur locale ({type(e).__name__})")
    print(texte); return 0 if ok else 1
