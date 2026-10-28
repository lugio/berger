# -*- coding: utf-8 -*-
"""Outil « equipe_chef » du courtier de Berger — ce que le CHEF DE PROJET d'une équipe peut faire sur les demandes
de fusion des développeurs. Créé automatiquement pour chaque projet de [equipes.<projet>] (outil « <projet>-chef »).

Pratique d'équipe suivie (sources dans la skill berger) : la branche principale est PROTÉGÉE — relecture approuvée,
tests au vert, seuls certains y écrivent, jamais de force push (GitHub, « About protected branches ») ; fusion à
historique linéaire en avance rapide (GitHub, « About merge methods ») ; branche supprimée après fusion (GitHub flow,
étape 6) ; le relecteur approuve ce qui améliore l'état général du code (Google, « The Standard of Code Review »).

Verbes : demandes (liste), relire <sujet>, rejouer <sujet> (les 4 portes rejouées sur le commit demandé, l'annonce
recomptée), renvoyer <sujet> "<motif>" (au développeur, à corriger), attente <sujet> "<motif>" (garée exprès : ni rappel
ni fusion) et reprendre <sujet> (de nouveau à relire) ; SA branche de finition, au chef de projet seul
et par le même chemin que celle d'un développeur : pousser <branche>, demander-fusion <branche> "<résumé>" ; ÉCRITURES, validées par le coordinateur de l'équipe
(valide_par) ou le propriétaire : fusionner <sujet> (pret rejouée ; main avancée : mise à jour automatique sûre, portes
rejouées ; avance rapide, push, branche du développeur supprimée ; projet qui EST l'installation — `installer_outil` — :
l'installation suit, sans autre validation), etiqueter <version> (étiquette SemVer + entrée du CHANGELOG.md ; SANS
validation sur le commit d'une fusion validée, version la plus récente du journal). Circuit et sources :
docs/plans/2026-10-12-processus-dev-generique-spec.md, docs/plans/2026-10-13-moins-validations-spec.md."""
import datetime, importlib.util, json, os, re, shutil, subprocess, tempfile, threading
from pathlib import Path

import importlib.util
_spec_transport = importlib.util.spec_from_file_location('berger_transport', Path(__file__).with_name('_transport.py'))
_transport = importlib.util.module_from_spec(_spec_transport); _spec_transport.loader.exec_module(_transport)

_spec = importlib.util.spec_from_file_location("outil__portes", Path(__file__).with_name("_portes.py"))
_portes = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_portes)
_spec = importlib.util.spec_from_file_location("outil__commandes", Path(__file__).with_name("_commandes.py"))
_base = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_base)
# Auteur des commits de mise à jour et des étiquettes faits par le courtier (jamais l'identité d'un agent)
AUTEUR = {"GIT_AUTHOR_NAME": "berger (courtier)", "GIT_AUTHOR_EMAIL": "courtier@berger.invalid",
          "GIT_COMMITTER_NAME": "berger (courtier)", "GIT_COMMITTER_EMAIL": "courtier@berger.invalid"}


# git lancé hors bac à sable dans un dépôt où un agent écrit : hooks et fsmonitor désactivés (voir _commandes.py)
ENV_GIT = {"GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/dev/null",
           "GIT_CONFIG_KEY_1": "core.fsmonitor", "GIT_CONFIG_VALUE_1": "false"}

# Un verrou par dépôt du chef (spec 2026-10-14-validation-a-part) : une fusion validée s'exécute à part et le chef peut
# appeler ses verbes pendant ce temps — deux commandes git en même temps dans le même dépôt se gêneraient (« cannot lock
# ref », merge vu à moitié). Pris autour de CHAQUE commande git du dépôt (quelques secondes), jamais pendant les portes
# (copie jetable) ; attente bornée, puis refus clair : jamais une attente sans fin.
VERROUS, _VERROUS = {}, threading.Lock()
ATTENTE_DEPOT = float(os.environ.get("BERGER_ATTENTE_DEPOT", "120"))


def verrou_depot(depot):
    with _VERROUS: return VERROUS.setdefault(str(Path(depot).resolve()), threading.Lock())


class Outil:
    contexte = _base._contexte.ContexteDeLAppel({})                  # posé par le courtier pour CET appel : {"agent", "dossier"}

    def __init__(self, reglages, secret, verifier_hote):
        self.depot = Path(reglages["depot"]).expanduser(); self.principale = reglages.get("principale", "main")
        self.demandes = Path(reglages["demandes"]); self.valide_par = reglages.get("valide_par")
        self.chef_projet = reglages.get("chef_projet", ""); self.prefixe = reglages.get("prefixe", "equipe/")
        self.projet = reglages.get("projet") or self.depot.name                  # copie de travail du chef par défaut : travail/<projet>-fin
        self.copie_chef = reglages.get("copie_chef", "")                          # sinon <dossier de l'appelant>/travail/<projet>-fin
        self.installation = [Path(x) for x in {reglages.get("installation") or "", str(Path(__file__).resolve().parents[2])} if x]
        self.motif_tests = reglages.get("motif_tests", _portes.MOTIF_TESTS)
        self.portes = _portes.declarees(reglages)                          # les mêmes que celles du développeur
        self.portes_outil = {p: v for p, (genre, v) in self.portes.items() if genre == "outil"}
        self.portes_par = {}                                               # {porte: verbe de lecture}, posé par le courtier
        self.installer_outil = reglages.get("installer_outil", "")         # « <outil> <verbe> » : ce projet EST l'installation
        self.installer_par = None                                          # l'action d'installation, posée par le courtier
        self.masques = reglages.get("masques", []); self.reseau = bool(reglages.get("reseau")); self.delai = int(reglages.get("delai", 900))
        self.regle_go = reglages.get("regle_go", True) is not False; self.go_mots = reglages.get("go_mots") or None   # spec 2026-10-15-regle-go
        self.travail = Path(reglages.get("travail") or tempfile.gettempdir())   # copies jetables du courtier (portes rejouées)
        self.verbes = {"demandes": self.liste, "relire": self.relire, "rejouer": self.rejouer, "renvoyer": self.renvoyer,
                       "attente": self.attente, "reprendre": self.reprendre, "pousser": self.pousser, "demander-fusion": self.demander_fusion}
        self.ecritures = {"fusionner": (self.apercu_fusion, self.fusionner), "etiqueter": (self.apercu_etiquette, self.etiqueter)}

    def hotes(self): return {}

    def git(self, *args, verifier=False):
        verrou = verrou_depot(self.depot)
        if not verrou.acquire(timeout=ATTENTE_DEPOT):
            raise RuntimeError(f"dépôt du chef occupé : une autre commande git y tourne depuis plus de {int(ATTENTE_DEPOT)} s "
                               f"(git {args[0] if args else ''} non lancé) — réessaie dans quelques minutes")
        try: r = subprocess.run(["git", "-C", str(self.depot), *args], capture_output=True, text=True, timeout=300, env={**os.environ, **ENV_GIT, **AUTEUR})
        finally: verrou.release()
        if verifier and r.returncode: raise RuntimeError(f"git {args[0]} : {(r.stderr or r.stdout).strip()[-300:]}")
        return r

    def valideur(self, verbe, args):
        """Qui valide CETTE écriture : valide_par, sauf la fusion d'une demande dont l'auteur est valide_par, ou d'une
        branche de finition du chef (écrite et relue par lui seul) → personne : le propriétaire seul."""
        if verbe == "fusionner":
            try: _, d = self.demande((args or [""])[0])
            except ValueError: return self.valide_par
            if d.get("finition") or d.get("agent") == self.valide_par: return None
        return self.valide_par

    def demande(self, sujet):
        f = self.demandes / f"{sujet}.json"
        if not sujet.replace("-", "").replace("_", "").isalnum() or not f.is_file(): raise ValueError(f"aucune demande de fusion pour « {sujet} »")
        return f, json.loads(f.read_text())

    def liste(self, args):
        """demandes : les demandes de fusion des développeurs (à relire, à finir, renvoyées, fusionnées)."""
        return [{k: d.get(k) for k in ("sujet", "branche", "etat", "resume", "demande", "motif", "motif_attente", "origine")
                 if k not in ("origine", "motif_attente") or d.get(k)}
                for d in (json.loads(f.read_text()) for f in sorted(self.demandes.glob("*.json")))] if self.demandes.is_dir() else []

    def go_dossier(self): return self.demandes.parent / "go"

    def controler_go(self, d):
        """Règle de go à la fusion : un go demandé mais pas inscrit, ou inscrit sur une autre version de la spec que celle
        recopiée dans la demande → refus (la demande doit être refaite)."""
        if not self.regle_go: return
        g = _portes.go_lu(self.go_dossier(), d.get("sujet", ""))
        if g is None: return
        if g.get("etat") != "inscrit":
            raise ValueError(f"règle de go : le go du sujet « {d['sujet']} » est demandé, pas inscrit — fusion refusée")
        if (d.get("go") or {}).get("empreinte") != g.get("empreinte"):
            raise ValueError(f"règle de go : la demande « {d['sujet']} » ne porte pas le go inscrit n° {g.get('validation') or '?'} "
                             "(demande faite avant le go, ou spec changée) — le développeur redemande la fusion")

    def conflit(self, a, b):
        """Fichiers en conflit si l'on fusionnait a et b (git merge-tree, sans rien écrire) ; [] = fusion propre."""
        r = self.git("merge-tree", "--write-tree", "--name-only", "--no-messages", a, b)
        if r.returncode not in (0, 1): raise RuntimeError(f"git merge-tree : {(r.stderr or r.stdout).strip()[-300:]}")
        return r.stdout.splitlines()[1:] if r.returncode == 1 else []

    def conflits(self, d):
        """Conflits de la demande d avec la branche principale et avec les AUTRES demandes à relire (branches poussées)."""
        autres = [x for x in (json.loads(f.read_text()) for f in sorted(self.demandes.glob("*.json")))
                  if x.get("etat") == "à relire" and x.get("sujet") != d["sujet"]]
        for b in [self.principale, d["branche"], *[x["branche"] for x in autres]]: self.git("fetch", "origin", b)
        moi = f"origin/{d['branche']}"
        out = {"avec " + self.principale: self.conflit(f"origin/{self.principale}", moi)}
        for x in autres:
            if self.git("rev-parse", "--verify", "--quiet", f"origin/{x['branche']}").returncode == 0:   # branche encore sur la forge
                out[f"avec la demande {x['sujet']}"] = self.conflit(f"origin/{x['branche']}", moi)
        return {k: v for k, v in out.items() if v}

    def relire(self, args):
        """relire <sujet> : commits, fichiers touchés, différence avec la branche principale, et conflits (avec elle et
        avec les autres demandes à relire) — une demande en conflit se renvoie au développeur."""
        _, d = self.demande((args or [""])[0]); b = d["branche"]
        self.git("fetch", "origin", self.principale, b)
        base = f"origin/{self.principale}"
        return {"demande": d, "conflits": self.conflits(d) or "aucun", "portes annoncées": _portes.resume(d.get("portes", {})) or "aucune",
                "règle de go": d.get("go") or "sujet hors règle de go",
                "commits": self.git("log", "--oneline", f"{base}..origin/{b}").stdout,
                "fichiers": self.git("diff", "--stat", f"{base}...origin/{b}").stdout[-4000:],
                "difference": self.git("diff", f"{base}...origin/{b}").stdout[:12000]}

    def renvoyer(self, args):
        """renvoyer <sujet> "<motif>" : la demande retourne au développeur, avec ce qu'il doit corriger."""
        if len(args) < 2 or len(" ".join(args[1:]).strip()) < 10: raise ValueError("renvoyer <sujet> \"<motif précis>\"")
        f, d = self.demande(args[0])
        d.update(etat="renvoyée", motif=" ".join(args[1:]), renvoyee=datetime.datetime.now().isoformat(timespec="minutes"),
                 renvois=int(d.get("renvois", 0)) + 1)                    # condition d'arrêt : trop de renvois → escalade (superviser)
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
        berger = Path(__file__).resolve().parents[2] / "bin/berger"           # prévenir le développeur, dans sa conversation
        _transport.lancer(str(berger), ['parler', d['agent'], '--stdin', '--de', self.contexte.get('agent') or 'chef de projet'], input=f"Ta demande de fusion « {d['sujet']} » est RENVOYÉE par le chef de projet : {d['motif']} — corrige dans ta copie, reteste, repousse, puis redemande la fusion.",
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"renvoyée": d["sujet"], "motif": d["motif"], "prevenu": d["agent"]}

    def attente(self, args):
        """attente <sujet> "<motif>" : la demande est GARÉE exprès (ex. une spec seule, à fusionner avec le code plus tard) —
        ni rappel au développeur ni au chef, ni alerte de renvois, et elle ne se fusionne pas. En sort par « reprendre » ou par
        un nouveau demander-fusion du développeur (spec 2026-10-15-regle-go, point d : une spec renvoyée exprès relançait
        son développeur sans fin)."""
        if len(args) < 2 or len(" ".join(args[1:]).strip()) < 10: raise ValueError("attente <sujet> \"<motif précis, 10 caractères au moins>\"")
        f, d = self.demande(args[0])
        if d.get("etat") in ("fusionnée", "en attente"): raise ValueError(f"demande « {d['sujet']} » : {d.get('etat')}, rien à mettre en attente")
        d.update(etat="en attente", etat_avant=d.get("etat"), motif_attente=" ".join(args[1:]).strip(),
                 attente_depuis=datetime.datetime.now().isoformat(timespec="minutes"), attente_par=self.contexte.get("agent") or "chef de projet")
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
        return {"en attente": d["sujet"], "motif": d["motif_attente"], "reprendre": f"reprendre {d['sujet']}"}

    def reprendre(self, args):
        """reprendre <sujet> : une demande « en attente » redevient « à relire » (relue, rejouée, fusionnée comme avant)."""
        if len(args) != 1: raise ValueError("reprendre <sujet>")
        f, d = self.demande(args[0])
        if d.get("etat") != "en attente": raise ValueError(f"demande « {d['sujet']} » : {d.get('etat')} (seule une demande « en attente » se reprend)")
        for k in ("etat_avant", "motif_attente", "attente_depuis", "attente_par"): d.pop(k, None)
        d["etat"] = "à relire"; f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
        return {"à relire": d["sujet"]}

    # ── SA branche de finition : le même chemin que celle d'un développeur (portes, demande, relecture, fusion validée) ──
    def branche_finition(self, args, n):
        """La branche de finition du chef, contrôlée : appelant = le chef de projet de l'équipe (contexte de CET appel),
        n arguments, préfixe de l'équipe + nom simple (ni « .. », ni tiret initial, ni espace, ni option), jamais la
        branche principale ; importée de SA copie de travail (avance rapide seule), puis présente dans le dépôt du chef.
        → (branche, sujet)."""
        agent = self.contexte.get("agent")
        if not self.chef_projet or agent != self.chef_projet:
            raise PermissionError(f"réservé au chef de projet de l'équipe ({self.chef_projet or 'aucun déclaré'}) : un développeur "
                                  f"pousse SA branche et demande la fusion avec son outil <projet>-dev")
        if len(args) != n: raise ValueError("pousser <branche>  |  demander-fusion <branche> \"<résumé>\"")
        b = args[0]; sujet = b[len(self.prefixe):] if b.startswith(self.prefixe) else ""
        if b == self.principale or not self.prefixe or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", sujet):
            raise ValueError(f"« {b} » refusée : une branche de finition est « {self.prefixe}<nom> » (lettres, chiffres, _ -), "
                             f"jamais {self.principale}")
        copie = self.importer(b)                                           # SA copie de travail → le dépôt, en avance rapide seule
        if self.git("rev-parse", "--verify", "--quiet", f"refs/heads/{b}").returncode:
            raise ValueError(f"pas de branche « {b} » ni dans ta copie de travail ({copie}) ni dans le dépôt du chef")
        return b, sujet

    def forge(self):
        """La forge (origin du dépôt du chef) si c'est un chemin local, sinon None (une URL : rien à protéger ici)."""
        url = self.git("remote", "get-url", "origin").stdout.strip()
        if url.startswith("file://"): url = url[len("file://"):]
        if not url or re.match(r"[A-Za-z][A-Za-z0-9+.-]*://", url) or re.match(r"[^/]+:", url): return None
        f = Path(url).expanduser()
        return f if f.is_absolute() else self.depot / f

    def copie_de_travail(self):
        """La copie de travail du chef, là où il écrit (le dépôt lui est en lecture seule : c'est la cible des fusions) :
        copie_chef déclarée, sinon <dossier de l'agent de CET appel>/travail/<projet>-fin. Refusée si elle n'est pas
        strictement dans ce dossier, passe par un lien symbolique (realpath, aucun lien suivi), touche le dépôt du chef ou
        la forge, ou est (ou contient) l'installation. → son chemin réel."""
        dossier = self.contexte.get("dossier")
        if not dossier: raise PermissionError("dossier de l'agent appelant inconnu : pas de copie de travail")
        brut = Path(self.copie_chef).expanduser() if self.copie_chef else Path(dossier) / "travail" / f"{self.projet}-fin"
        if not brut.is_absolute(): raise ValueError(f"copie_chef « {brut} » refusée : chemin absolu attendu")
        dos, reel, n = Path(os.path.realpath(dossier)), Path(os.path.realpath(brut)), Path(os.path.normpath(brut))
        rel = next((n.relative_to(b) for b in (Path(os.path.normpath(dossier)), dos) if n.is_relative_to(b)), None)
        if rel is None or not rel.parts: raise ValueError(f"copie de travail « {brut} » refusée : elle doit être DANS le dossier de l'agent ({dossier})")
        if dos / rel != reel: raise ValueError(f"copie de travail « {brut} » refusée : un lien symbolique sur le chemin (aucun lien n'est suivi)")
        for nom, x in (("le dépôt du chef", self.depot), ("la forge", self.forge())):
            xr = Path(os.path.realpath(x)) if x else None
            if xr and (reel == xr or xr.is_relative_to(reel) or reel.is_relative_to(xr)): raise ValueError(f"copie de travail « {brut} » refusée : elle touche {nom}")
        for x in self.installation:
            if Path(os.path.realpath(x)).is_relative_to(reel): raise ValueError(f"copie de travail « {brut} » refusée : elle contient l'installation")
        return reel

    def importer(self, b):
        """La branche b de la copie de travail du chef importée dans SON dépôt, en avance rapide seule (refspec sans « + » :
        git refuse une branche réécrite). Le courtier ne lance AUCUNE commande git dans la copie : seul upload-pack y lit
        les objets (fetch par fichier), et il n'exécute rien de la config locale (uploadpack.packObjectsHook n'est lu que
        d'une config protégée) ; côté dépôt, ENV_GIT désactive crochets et fsmonitor. Copie ou branche absente : rien.
        → le chemin de la copie (pour les messages)."""
        copie = self.copie_de_travail(); g = copie / ".git"
        if not os.path.lexists(g): return copie
        if g.is_symlink() or not g.is_dir(): raise ValueError(f"copie de travail « {copie} » refusée : son .git n'est pas un vrai dossier (lien ou renvoi ailleurs)")
        r = self.git("ls-remote", "--heads", str(g), f"refs/heads/{b}")
        if r.returncode: raise RuntimeError(f"copie de travail illisible ({copie}) : {(r.stderr or r.stdout).strip()[-300:]}")
        if not r.stdout.strip(): return copie
        r = self.git("fetch", "--no-tags", "--no-recurse-submodules", "--no-write-fetch-head", "--no-auto-maintenance",
                     str(g), f"refs/heads/{b}:refs/heads/{b}")
        if r.returncode: raise RuntimeError(f"import de « {b} » depuis ta copie de travail refusé (avance rapide seule : ne réécris pas "
                                            f"ce qui est déjà dans le dépôt) : {(r.stderr or r.stdout).strip()[-300:]}")
        return copie

    def pousser(self, args):
        """pousser <branche> : SA branche de finition, importée de sa copie de travail dans le dépôt (avance rapide seule),
        puis poussée du dépôt vers la forge, sans force (un historique réécrit est refusé)."""
        b, _ = self.branche_finition(args, 1)
        r = self.git("push", "origin", f"refs/heads/{b}:refs/heads/{b}")
        if r.returncode: raise RuntimeError(f"push refusé (jamais de force : mets ta branche à jour, sans réécrire ce qui est poussé) : {r.stderr.strip()[-300:]}")
        return {"poussée": b, "commit": self.git("rev-parse", f"refs/heads/{b}").stdout.strip()[:10]}

    def demander_fusion(self, args):
        """demander-fusion <branche> "<résumé>" : les contrôles d'un développeur (poussée, à jour, correctif, pret), les 4
        portes rejouées dans une copie jetable du courtier, puis la demande — sa fusion : le propriétaire seul."""
        b, sujet = self.branche_finition(args[:1], 1); resume = " ".join(args[1:]).strip()
        try: _, autre = self.demande(sujet)
        except ValueError: autre = None
        origine = self.reprise_a_finir(sujet, autre, b)                    # finition = chef : la trace du développeur, ou None
        if autre and autre.get("branche") != b and not origine: raise ValueError(f"le sujet « {sujet} » est déjà la demande de {autre.get('branche')} : renomme ta branche")
        extraite = self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == b
        commit = _portes.controler_demande(lambda *a: self.git(*a), f"refs/heads/{b}", b, self.principale, resume, self.portes, self.motif_tests,
                                           sale=extraite and bool(self.git("status", "--porcelain").stdout.strip()),
                                           maj=f"fusionne origin/{self.principale} dans ta branche")
        go = None
        if self.regle_go:                                                  # règle de go : la finition aussi (fichier de go du sujet)
            def spec_lue(chemin):
                r = self.git("show", f"{commit}:{chemin}"); return r.stdout if r.returncode == 0 else None
            go = _portes.go_de_la_demande(self.go_dossier(), sujet, "", spec_lue, self.go_mots)
        res, sorties = self.jouer_portes(commit, b)
        _portes.refuser_rouges(res, sorties)
        n = _portes.inscrire_demande(self.demandes, sujet, b, commit, resume, self.contexte.get("agent"), res, a="propriétaire", finition=True,
                                     **({"origine": origine} if origine else {}), **({"go": go} if go else {}))
        for g, x in self.livraisons_reprises(self.demandes / f"{sujet}.json", n, commit):    # reprise sous un autre sujet : le chef a fait sa part
            x["reprise_par"] = b; g.write_text(json.dumps(x, ensure_ascii=False, indent=1))
        return {"demande": f"fusion de {b} inscrite (sujet {sujet}) : relis-la, rejoue-la, puis « fusionner {sujet} » — validée par le propriétaire seul",
                "commit": commit[:10], "portes": _portes.resume(res)}

    def reprise_a_finir(self, sujet, autre, b):
        """finition = chef (docs/plans/2026-10-13-hierarchie-equipe-spec.md) : la branche de finition `b` du chef REMPLACE la
        livraison « à finir » du développeur (même sujet, même dossier de demandes) seulement si elle CONTIENT le commit livré.
        → la trace du développeur (origine : agent, branche, commit, date) ; None si ce n'est pas une reprise ; refus si la
        branche ne contient pas le commit livré."""
        if not autre or autre.get("branche") == b or autre.get("etat") != "à finir": return None
        if not autre.get("commit") or self.git("merge-base", "--is-ancestor", autre["commit"], f"refs/heads/{b}").returncode:
            raise ValueError(f"le sujet « {sujet} » est déjà la demande de {autre.get('branche')} : renomme ta branche (ou pars du "
                             f"commit livré {str(autre.get('commit'))[:10]} : ta branche de finition doit le contenir)")
        return autre.get("origine") or {k: autre.get(k) for k in ("agent", "branche", "commit", "demande")}

    # ── portes rejouées dans une copie jetable du courtier ──
    def jouer_portes(self, commit, branche, seules=None):
        """Les portes (toutes, ou `seules`) sur `commit`, dans une copie JETABLE (clone --shared du dépôt du chef : ses objets
        restent en lecture seule pour le bac à sable) ; commandes en bac à sable, outils sur `branche` (poussée, = commit).
        La copie est effacée ensuite et le courtier n'y lance plus jamais git : le code testé a pu modifier son .git."""
        portes = {p: v for p, v in self.portes.items() if seules is None or p in seules}
        self.travail.mkdir(parents=True, exist_ok=True)
        copie = Path(tempfile.mkdtemp(prefix="portes-", dir=self.travail))
        try:
            env = {**os.environ, **ENV_GIT}
            principale = self.git("rev-parse", f"origin/{self.principale}").stdout.strip()
            for cmd in (["clone", "-q", "--shared", "--no-checkout", str(self.depot), str(copie)],
                        ["-C", str(copie), "checkout", "-q", "--detach", commit],
                        ["-C", str(copie), "update-ref", f"refs/remotes/origin/{self.principale}", principale]):   # base des portes (diff)
                r = subprocess.run(["git", *cmd], capture_output=True, text=True, timeout=300, env=env)
                if r.returncode: raise RuntimeError(f"copie des portes : git {' '.join(cmd[:4])} : {(r.stderr or r.stdout).strip()[-300:]}")
            h = str(Path.home()); env["PATH"] = f"{h}/.local/bin:{h}/.local/share/mise/shims:" + env.get("PATH", "/usr/local/bin:/usr/bin:/bin")

            def commande(p, cmd):
                try:
                    r = _transport.executer_shell(f"set -o pipefail; {cmd} 2>&1 | tail -n 200",
                                       construire=lambda args: _base.bac_a_sable(args, copie, self.masques, self.reseau),
                                       cwd=copie, capture_output=True, text=True, timeout=self.delai, env=env)
                except subprocess.TimeoutExpired: return 1, f"porte {p} trop longue (plus de {self.delai} s) : arrêtée"
                return r.returncode, r.stdout

            def outil(p):
                if not self.portes_par.get(p): raise RuntimeError(f"{p}_outil « {self.portes_outil[p]} » indisponible (outil non chargé)")
                r = self.portes_par[p]([branche]); return r.get("code", 1), r.get("sortie", "")
            return _portes.jouer(portes, commande, outil)
        finally:
            shutil.rmtree(copie, ignore_errors=True)

    def rejouer(self, args):
        """rejouer <sujet> : les 4 portes rejouées sur le commit demandé (copie du courtier), comparées à l'annonce."""
        _, d = self.demande((args or [""])[0])
        self.git("fetch", "origin", self.principale, d["branche"], verifier=True)
        if self.git("rev-parse", f"origin/{d['branche']}").stdout.strip() != d["commit"]:
            raise ValueError("la branche a changé depuis la demande : le développeur doit redemander la fusion")
        res, sorties = self.jouer_portes(d["commit"], d["branche"])
        annonce = d.get("portes", {}); out = {}
        for p, r in res.items():
            a = annonce.get(p, {"etat": "non annoncée"})
            out[p] = {"annoncé": _portes.resume({p: a}), "mesuré": _portes.resume({p: r}),
                      "identique": a.get("etat") == r["etat"] and a.get("bilan", "") == r.get("bilan", "")}
        ecarts = [p for p, x in out.items() if not x["identique"]]
        recompte = "conforme à l'annonce" if not ecarts else f"ÉCART avec l'annonce : {', '.join(ecarts)} — renvoie la demande"
        # le rejeu est INSCRIT dans la demande (les 5 derniers) : le propriétaire voit qui l'a joué, quand, et le recompte
        f, d = self.demande((args or [""])[0]); quand = datetime.datetime.now().isoformat(timespec="minutes"); par = self.contexte.get("agent") or "chef de projet"
        d["rejeux"] = (d.get("rejeux") or [])[-4:] + [{"par": par, "quand": quand, "recompte": recompte, "portes": _portes.signer(res, par, quand)}]
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
        return {"commit": d["commit"][:10], "portes": out, "recompte": recompte, "sorties": {p: x[-1500:] for p, x in sorties.items()}}

    # ── fusion ──
    def communs(self, d):
        """Fichiers modifiés des DEUX côtés depuis la base commune (main et la branche) : une mise à jour automatique y
        changerait peut-être le sens sans conflit git — refusée, le développeur se met à jour lui-même."""
        base = self.git("merge-base", f"origin/{self.principale}", d["commit"], verifier=True).stdout.strip()
        cote = lambda x: set(self.git("diff", "--name-only", base, x, verifier=True).stdout.split())
        return sorted(cote(f"origin/{self.principale}") & cote(d["commit"]))

    def controler(self, d):
        """Ce qui refuse une fusion avant tout calcul : état, porte pret, conflit, fichier commun. → « avance rapide » ou « mise à jour »."""
        if d.get("etat") != "à relire": raise ValueError(f"demande « {d['sujet']} » : {d.get('etat')} (seule une demande « à relire » se fusionne)")
        self.controler_go(d)
        if "pret" not in self.portes: raise ValueError("aucune porte « pret » déclarée pour ce projet (pret ou pret_outil) : pas de fusion")
        avec_principale = self.conflits(d).get("avec " + self.principale)
        if avec_principale: raise ValueError(f"demande « {d['sujet']} » en conflit avec {self.principale} ({', '.join(avec_principale)}) : "
                                             f"renvoie-la au développeur (mettre-a-jour, résoudre, retester, redemander)")
        if self.git("merge-base", "--is-ancestor", f"origin/{self.principale}", d["commit"]).returncode == 0: return "avance rapide"
        communs = self.communs(d)
        if communs: raise ValueError(f"{self.principale} a avancé et touche un fichier commun avec la demande « {d['sujet']} » "
                                     f"({', '.join(communs)}) : pas de mise à jour automatique — renvoie-la au développeur "
                                     f"(mettre-a-jour, retester, repousser, redemander)")
        return "mise à jour"

    def apercu_fusion(self, args):
        """fusionner <sujet> : pret rejouée ; main avancée sans fichier commun : mise à jour automatique, portes rejouées ;
        avance rapide dans la branche principale + push (validé par le coordinateur ou le propriétaire)."""
        _, d = self.demande((args or [""])[0])
        mode = self.controler(d)
        plus = (f" — {self.principale} a avancé : mise à jour automatique (aucun fichier commun), les 4 portes rejouées avant l'avance rapide"
                if mode == "mise à jour" else " — porte pret rejouée avant")
        return f"fusionner {d['branche']} ({d['commit'][:10]}) dans {self.principale} et pousser{plus} — {d['resume'][:200]}"

    def fusionner(self, args):
        f, d = self.demande(args[0])
        if self.git("status", "--porcelain").stdout.strip(): raise RuntimeError("le dépôt du chef de projet a des changements non commités")
        if self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != self.principale:
            raise RuntimeError(f"le dépôt du chef de projet n'est pas sur {self.principale}")
        self.git("fetch", "origin", self.principale, d["branche"], verifier=True)
        if self.git("rev-parse", f"origin/{d['branche']}").stdout.strip() != d["commit"]:
            raise RuntimeError("la branche a changé depuis la demande : le développeur doit redemander la fusion")
        mode = self.controler(d)
        self.git("merge", "--ff-only", f"origin/{self.principale}", verifier=True)         # dépôt local à jour d'abord
        if mode == "avance rapide":
            res, sorties = self.jouer_portes(d["commit"], d["branche"], seules={"pret"})
            if _portes.rouges(res): raise RuntimeError(f"porte pret rouge au rejeu : pas de fusion — {_portes.resume(res)}\n{sorties.get('pret', '')[-800:]}")
            res = _portes.completer(res, d)                                   # les autres : jouées à la demande, sur ce même commit
            cible = d["commit"]
        else:
            cible = self.mise_a_jour(d)
            res, sorties = self.portes_integration(d, cible) if self.portes_outil else self.jouer_portes(cible, None)
            if _portes.rouges(res):
                raise RuntimeError(f"portes rouges après la mise à jour automatique : rien n'est poussé — {_portes.resume(res)}\n"
                                   + "\n".join(f"--- {p}\n{sorties.get(p, '')[-600:]}" for p in _portes.rouges(res))
                                   + "\nRenvoie la demande au développeur (mettre-a-jour, retester, redemander).")
        self.git("push", "origin", f"{cible}:refs/heads/{self.principale}", verifier=True)   # avance rapide ou refus, jamais de force
        self.git("merge", "--ff-only", cible, verifier=True)
        self.git("push", "origin", "--delete", d["branche"])                                 # branche supprimée après fusion
        d.update(etat="fusionnée", fusionnee=datetime.datetime.now().isoformat(timespec="minutes"),
                 fusion="avance rapide" if mode == "avance rapide" else f"mise à jour automatique ({cible[:10]})",
                 commit_fusion=cible, portes_fusion=res)                  # commit_fusion : ce que etiqueter reconnaît
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
        soldees = self.solder_livraisons(f, d, cible)
        texte = f"{d['branche']} fusionnée dans {self.principale} et poussée ({cible[:10]}, {d['fusion']}) — {_portes.resume(res)}"
        if soldees: texte += f"\nlivraison(s) « à finir » soldée(s) par cette finition : {', '.join(soldees)}"
        return self.installer_apres(f, d, texte) if self.installer_par else texte

    def livraisons_reprises(self, f, d, commit):
        """Les livraisons « à finir » (fichier, demande) qu'une demande de FINITION reprend : celle de son `origine`, et toute
        autre dont le commit livré est dans `commit` (sujet différent, ex. `<sujet>-fin` : la reprise ne remplace alors aucun fichier)."""
        origine = d.get("origine") or {}; reprises = []
        for g in sorted(self.demandes.glob("*.json")):
            if g == f: continue
            try: x = json.loads(g.read_text())
            except ValueError: continue
            if x.get("etat") != "à finir" or not x.get("commit"): continue
            memes = origine.get("branche") and x.get("branche") == origine["branche"] and x["commit"] == origine.get("commit")
            if memes or self.git("merge-base", "--is-ancestor", x["commit"], commit).returncode == 0: reprises.append((g, x))
        return reprises

    def solder_livraisons(self, f, d, cible):
        """finition = chef : la fusion d'une branche de FINITION solde les livraisons « à finir » qu'elle a reprises : elles
        passent à « fusionnée (par la finition <branche>) ». Sans cela la supervision relançait le chef à l'infini pour un
        travail déjà livré (vécu le 13/10). → les sujets soldés."""
        if not d.get("finition"): return []
        soldees = []
        for g, x in self.livraisons_reprises(f, d, cible):
            x.update(etat="fusionnée", fusionnee=d["fusionnee"], fusion=f"par la finition {d['branche']}", soldee_par=d["branche"])
            g.write_text(json.dumps(x, ensure_ascii=False, indent=1)); soldees.append(x.get("sujet", g.stem))
        return soldees

    def solder_deja_finies(self):
        """Rattrapage : une livraison « à finir » dont la finition a été fusionnée AVANT que le correctif de solde existe n'a
        jamais reçu reprise_par ni soldee_par, et la supervision la rappelait sans fin (mesuré le 14/10 : 65 rappels). Même test
        de reprise que la fusion (livraisons_reprises), même solde (solder_livraisons) pour chaque finition déjà fusionnée.
        → les sujets soldés ; une livraison réellement non reprise reste « à finir »."""
        soldees = []
        for f in sorted(self.demandes.glob("*.json")):
            try: d = json.loads(f.read_text())
            except ValueError: continue
            cible = d.get("commit_fusion") or d.get("commit")
            if d.get("finition") and d.get("etat") == "fusionnée" and d.get("fusionnee") and cible:
                soldees += [(x, d["branche"]) for x in self.solder_livraisons(f, d, cible)]
        return soldees

    def installer_apres(self, f, d, texte):
        """Le projet EST l'installation (`installer_outil` de [equipes.<p>]) : sa fusion validée lance l'action d'installation
        déclarée — la MÊME commande que l'action manuelle (spec 2026-10-13-moins-validations) : une seule validation pour
        les deux. Installation en échec (retour arrière fait par elle) → code ≠ 0 : « validé mais ÉCHEC », fusion faite."""
        try: r = self.installer_par([])
        except Exception as e: r = {"code": 1, "sortie": f"installation non lancée : {e}"}
        ok = isinstance(r, dict) and r.get("code") == 0
        sortie = (r.get("sortie", "") if isinstance(r, dict) else str(r)).strip()
        d.update(installation="faite" if ok else "en ÉCHEC", installee=datetime.datetime.now().isoformat(timespec="minutes"))
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
        if ok: return f"{texte}\ninstallation automatique ({self.installer_outil}) : {sortie[-1500:]}"
        return {"code": r.get("code", 1) if isinstance(r, dict) else 1,
                "sortie": f"fusion FAITE : {texte}\ninstallation automatique ({self.installer_outil}) en ÉCHEC : {sortie[-2500:]}"}

    def mise_a_jour(self, d):
        """Le commit de mise à jour (main + la branche), calculé DANS le dépôt du chef sans copie de travail : git merge-tree
        puis commit-tree. Rien n'est poussé ici."""
        r = self.git("merge-tree", "--write-tree", f"origin/{self.principale}", d["commit"])
        if r.returncode: raise RuntimeError(f"mise à jour impossible (conflit) : {r.stdout.strip()[-300:]}")
        arbre = r.stdout.split()[0]
        return self.git("commit-tree", arbre, "-p", f"origin/{self.principale}", "-p", d["commit"], "-m",
                        f"Merge {self.principale} into {d['branche']} (mise à jour automatique par le courtier, portes rejouées)",
                        verifier=True).stdout.strip()

    def portes_integration(self, d, cible):
        """Portes rejouées sur le commit de mise à jour quand certaines sont des outils : il leur faut une branche poussée —
        integration/<sujet>, effacée ensuite quoi qu'il arrive."""
        branche = f"integration/{d['sujet']}"
        self.git("push", "origin", f"{cible}:refs/heads/{branche}", verifier=True)
        try: return self.jouer_portes(cible, branche)
        finally: self.git("push", "origin", "--delete", branche)

    # ── étiquette de version ──
    def version(self, args):
        """Contrôles de etiqueter : SemVer, plus grande que la dernière, absente, entrée de journal. → (version, entrée, commit)."""
        if len(args) != 1: raise ValueError("etiqueter <version> (ex. 1.4.0)")
        v = args[0]
        if _portes.precedence(v) is None: raise ValueError(f"« {v} » n'est pas une version SemVer 2.0.0 (MAJEUR.MINEUR.CORRECTIF, ex. 1.4.0, sans « v »)")
        self.git("fetch", "origin", self.principale, verifier=True)
        distantes = self.git("ls-remote", "--tags", "origin", verifier=True).stdout.split()
        etiquettes = {x.split("refs/tags/", 1)[1].removesuffix("^{}") for x in distantes if x.startswith("refs/tags/")}
        etiquettes |= set(self.git("tag", "-l").stdout.split())
        if f"v{v}" in etiquettes: raise ValueError(f"l'étiquette v{v} existe déjà : une version publiée ne se déplace jamais (SemVer §3)")
        avant = [x[1:] for x in etiquettes if x.startswith("v") and _portes.precedence(x[1:])]
        derniere = max(avant, key=_portes.precedence) if avant else None
        if derniere and _portes.precedence(v) <= _portes.precedence(derniere):
            raise ValueError(f"{v} n'est pas plus grande que la dernière version publiée ({derniere})")
        journal = self.git("show", f"origin/{self.principale}:CHANGELOG.md")
        entree = _portes.entree_journal(journal.stdout, v) if journal.returncode == 0 else None
        if not entree: raise ValueError(f"pas d'entrée « ## [{v}] - AAAA-MM-JJ » (non vide) dans le CHANGELOG.md de {self.principale} "
                                        f"(Keep a Changelog 1.1.0) : elle arrive par une demande de fusion, avant l'étiquette")
        return v, entree, self.git("rev-parse", f"origin/{self.principale}").stdout.strip()

    def apercu_etiquette(self, args):
        """etiqueter <version> : étiquette annotée v<version> sur la branche principale (message = l'entrée du CHANGELOG.md), poussée sans force — SANS validation si c'est le commit d'une fusion validée et la version la plus récente du journal."""
        v, entree, commit = self.version(args)
        return f"étiqueter v{v} sur {self.principale} ({commit[:10]}) et pousser l'étiquette — {entree.splitlines()[0]}"

    def etiqueter(self, args): return self.poser_etiquette(*self.version(args))

    def fusion_validee(self, commit):
        """La demande « fusionnée » dont le commit de fusion est `commit` (commit_fusion ; ancienne demande en avance rapide :
        son commit) — `fusionner` ne s'exécute qu'après validation : c'est la preuve d'une fusion validée. None sinon."""
        for x in sorted(self.demandes.glob("*.json")) if self.demandes.is_dir() else []:
            try: d = json.loads(x.read_text())
            except (OSError, ValueError): continue
            fait = d.get("commit_fusion") or (d.get("commit") if d.get("fusion") == "avance rapide" else None)
            if d.get("etat") == "fusionnée" and fait == commit: return d
        return None

    def sans_validation(self, verbe, args):
        """Une écriture qui se passe de validation (spec 2026-10-13-moins-validations) : `etiqueter` quand l'étiquette porte
        sur le commit d'une fusion déjà validée (tête de la branche principale = commit de fusion inscrit) ET que la version
        est la plus récente du CHANGELOG.md de cette branche. → (raison, geste) — le geste pose l'étiquette sur CE commit
        contrôlé — ou None : validation comme avant."""
        if verbe != "etiqueter": return None
        v, entree, commit = self.version(args)                            # mêmes contrôles (refus : erreur, comme l'aperçu)
        d = self.fusion_validee(commit)
        journal = self.git("show", f"{commit}:CHANGELOG.md").stdout
        derniere = next((m.group(1) for m in re.finditer(r"(?m)^##\s*\[([^\]]+)\]", journal) if _portes.precedence(m.group(1))), None)
        if not d or derniere != v: return None
        return (f"v{v} sur {commit[:10]}, commit de la fusion validée « {d.get('sujet')} », version la plus récente du CHANGELOG.md",
                lambda: self.poser_etiquette(v, entree, commit))

    def poser_etiquette(self, v, entree, commit):
        self.git("tag", "-a", f"v{v}", "-m", f"Version {v}\n\n{entree}", commit, verifier=True)
        self.git("push", "origin", f"refs/tags/v{v}", verifier=True)                          # jamais de force : refus si elle existe
        _transport.executer(str(Path(__file__).resolve().parents[2] / "bin/berger"), ['echange', self.contexte.get('agent') or 'chef de projet', 'équipe', 'version publiée', f'v{v} ({commit[:10]}) : {entree[:600]}'], capture_output=True)
        return f"étiquette v{v} posée sur {self.principale} ({commit[:10]}) et poussée"
