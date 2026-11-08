# -*- coding: utf-8 -*-
"""Outil « equipe_dev » du courtier de Berger — ce qu'un DÉVELOPPEUR d'équipe peut faire, dans SA copie seulement.

Créé automatiquement pour chaque projet de [equipes.<projet>] (outil « <projet>-dev ») ; jamais à déclarer à la main.
Les valeurs {copie} {branche} {sujet} {port} {principale} viennent de l'agent.conf du demandeur (voir copie.py).

Pratique d'équipe suivie (sources dans la skill berger) : une branche par sujet (GitHub flow, Fowler « Feature
Branching ») ; push de SA branche dans le dépôt partagé (GitHub, « shared repository model ») ; branche saine = tests
au vert (Fowler « Healthy Branch ») ; intégrer souvent depuis la branche principale (Fowler « Integration
Frequency ») ; demande de fusion relue avant d'entrer dans la branche principale (GitHub, pull request).

Verbes : etat, mettre-a-jour, pousser, une par porte déclarée (verify, tests, gate, pret : voir _portes.py),
demander-fusion "<résumé>", + les commandes propres au projet ([equipes.<projet>.lecture], ex. démarrer / arrêter /
réinitialiser SA pile). Circuit et sources : docs/plans/2026-10-12-processus-dev-generique-spec.md."""
import contextlib, importlib.util, os, re, shutil, subprocess, threading
from pathlib import Path

import importlib.util
_spec_transport = importlib.util.spec_from_file_location('berger_transport', Path(__file__).with_name('_transport.py'))
_transport = importlib.util.module_from_spec(_spec_transport); _spec_transport.loader.exec_module(_transport)

_spec = importlib.util.spec_from_file_location("outil_copie", Path(__file__).with_name("copie.py"))
_copie = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_copie)
_spec = importlib.util.spec_from_file_location("outil__portes", Path(__file__).with_name("_portes.py"))
_portes = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_portes)
_spec = importlib.util.spec_from_file_location("outil__file_tests", Path(__file__).with_name("_file_tests.py"))
_file = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_file)


class Outil(_copie.Outil):
    def __init__(self, reglages, secret, verifier_hote):
        self.principale = reglages.get("principale", "main"); self.demandes = Path(reglages["demandes"])
        self.chef_projet = reglages.get("chef_projet", ""); self.motif_tests = reglages.get("motif_tests", _portes.MOTIF_TESTS)
        self.portes = _portes.declarees(reglages)                          # {porte: ("commande", cmd) | ("outil", "<outil> <verbe>")}
        self.finition = reglages.get("finition", "developpeur")             # "chef" : la finition (pret) est faite par le chef de projet
        if self.finition not in ("developpeur", "chef"): raise ValueError(f"finition = « {self.finition} » : \"developpeur\" ou \"chef\"")
        self.doc = _portes.declaree_doc(reglages)                          # la porte courte (documentation seule), facultative
        self.portes_outil = {p: v for p, (genre, v) in {**self.portes, **({"doc": self.doc} if self.doc else {})}.items() if genre == "outil"}
        self.regle_go = reglages.get("regle_go", True) is not False; self.go_mots = reglages.get("go_mots") or None   # spec 2026-10-15-regle-go
        self.portes_par = {}                                               # {porte: verbe de lecture}, posé par le courtier (<porte>_outil)
        lecture = {"etat": "git status -sb && echo && echo '--- mes commits pas encore dans {principale} :' && git log --oneline origin/{principale}..HEAD",
                   "mettre-a-jour": "git fetch origin {principale} && git merge --no-edit origin/{principale}",
                   "pousser": "git push -u origin {branche}"}
        for p, (genre, cmd) in {**self.portes, **({"doc": self.doc} if self.doc else {})}.items():
            if genre == "commande": lecture[p] = f"set -o pipefail; {cmd} 2>&1 | tail -n 200"
        lecture.update(reglages.get("lecture", {}))
        super().__init__({**reglages, "lecture": lecture, "actions": reglages.get("actions", {})}, secret, verifier_hote)
        self.verbes["demander-fusion"] = self.demander_fusion
        for p in self.portes_outil: self.verbes[p] = self.fabriquer_distant(p)
        self.env_verbe = {"mettre-a-jour": _copie._base.AUTEUR_COURTIER}   # la copie n'a pas d'identité git : la fusion est signée du courtier
        self.hors_bac = {"etat", "mettre-a-jour", "pousser"}             # git seulement (réseau, clé SSH) ; tout le reste en bac à sable
        self._fil = threading.local()                                      # ce fil tient-il le tour des tests ? (lot A)

    # ── file des tests (lot A, spec 2026-11-04-acceleration-fusions) : Berger tient le tour, l'agent ne le demande plus ──
    def tour(self, v):
        """Le tour des tests pour CE fil (ticket, attente bornée, verrou des suites) ; déjà tenu : rien de plus."""
        if getattr(self._fil, "tenu", False): return contextlib.nullcontext()
        c = self.contexte or {}
        marqueur = Path(c["dossier"]) / "courrier/file" / c["demande"] if c.get("dossier") and c.get("demande") else None
        @contextlib.contextmanager
        def tenir():
            with _file.tour(v["sujet"], v["copie"], agent=c.get("agent"), projet=v.get("projet"), marqueur=marqueur):   # projet : agent.conf
                self._fil.tenu = True
                try: yield
                finally: self._fil.tenu = False
        return tenir()

    def env_en_plus(self, verbe):
        return {**super().env_en_plus(verbe), **(_file.ENV_TENU if getattr(self._fil, "tenu", False) else {})}

    def executer(self, cmd, verbe=None, dossier=None):
        """La porte `tests` jouée seule passe par la file : le délai de la porte ne court qu'une fois le tour obtenu."""
        if verbe == "tests" and "tests" in self.portes and self.portes["tests"][0] == "commande" and not getattr(self._fil, "tenu", False):
            with self.tour(self.valeurs()): return super().executer(cmd, verbe, dossier)
        return super().executer(cmd, verbe, dossier)

    @contextlib.contextmanager
    def copie_figee(self, v, sha):
        """Une copie FIGÉE de `sha` pour les portes inscrites : clone --no-local de la forge (l'origine de la copie), extrait en tête
        détachée dans l'état du courtier (<installation>/courtier/portes-figees/, hors de portée de l'agent), effacée ensuite. Le
        transfert par paquet (--no-local) recalcule l'empreinte de chaque objet reçu : le contenu extrait EST celui de `sha`, même si
        l'agent a changé l'adresse de son origine ; rien n'est partagé avec sa copie (ni objets, ni alternates). Ce qu'il fait de sa
        copie pendant l'attente du tour ou pendant les portes ne change donc rien au contenu testé. Le courtier n'y relance plus git
        après les portes (le code testé a pu modifier son .git)."""
        forge = self.git(v, "config", "--get", "remote.origin.url").stdout.strip()
        if not forge: raise RuntimeError("copie figée impossible : la copie n'a pas d'origine (remote.origin.url)")
        d, usage = _file.creer_copie(re.sub(r"[^A-Za-z0-9_-]", "_", v["sujet"])[:40] + "-")   # tenue : nettoyer_figees (démarrage) ne la prend pas
        try:
            env = {**os.environ, **_copie._base.ENV_GIT}
            for cmd in (["clone", "-q", "--no-local", "--no-checkout", "--", forge, str(d)], ["-C", str(d), "checkout", "-q", "--detach", sha]):
                r = subprocess.run(["git", *cmd], capture_output=True, text=True, timeout=300, env=env)
                if r.returncode: raise RuntimeError(f"copie figée des portes : git {' '.join(cmd[:4])} : {(r.stderr or r.stdout).strip()[-300:]}")
            tete = subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=60, env=env).stdout.strip()
            if tete != sha: raise RuntimeError(f"copie figée des portes : tête {tete[:10]} au lieu de {sha[:10]}")
            yield d
        finally:
            shutil.rmtree(d, ignore_errors=True); os.close(usage)

    def remplir(self, cmd):
        return super().remplir(cmd.replace("{principale}", self.principale))

    def git(self, v, *args):
        return subprocess.run(["git", *args], cwd=v["copie"], capture_output=True, text=True, timeout=120, env={**os.environ, **_copie._base.ENV_GIT})

    def fabriquer_distant(self, porte):
        def distant(args):
            if args: raise ValueError(f"{porte} n'accepte aucun argument : c'est ta branche poussée qui est vérifiée")
            return self.porte_distante(porte, self.tete_poussee())
        distant.__doc__ = f"{porte} : la porte de l'équipe, lancée par l'outil « {self.portes_outil[porte]} » sur le commit de ta branche POUSSÉE"
        return distant

    def tete_poussee(self):
        """Le SHA de HEAD, à condition que ce soit celui de la branche poussée (sinon l'outil testerait autre chose)."""
        v = self.valeurs(); git = lambda *a: self.git(v, *a)
        git("fetch", "origin", v["branche"])
        tete = git("rev-parse", "--verify", "--quiet", "HEAD").stdout.strip()
        if not tete or git("rev-parse", f"origin/{v['branche']}").stdout.strip() != tete:
            raise ValueError("ta branche n'est pas poussée telle quelle : lance « pousser » d'abord")
        return tete

    def porte_distante(self, porte, sha):
        """<porte>_outil : le verbe de lecture d'un outil du courtier, sur le SHA contrôlé par le courtier (jamais une branche ni un
        argument de l'agent : spec 2026-10-29-sha-fige)."""
        if not self.portes_par.get(porte): raise RuntimeError(f"{porte}_outil « {self.portes_outil[porte]} » indisponible (outil non chargé)")
        return _portes.distante(self.portes_par[porte], sha)

    def jouer_portes(self, sha, sans=(), portes=None, court=False):
        """Les 4 portes (sauf `sans` : « non mesuré »), dans l'ordre, chacune inscrite : commande dans une copie FIGÉE de `sha`
        (copie_figee, bac à sable), outil sur `sha`, le commit demandé (poussé). `portes`/`court` : le choix du courtier
        (_portes.choisir) ; en mode court, `tests` est la porte doc."""
        a_jouer = {p: x for p, x in (portes or self.portes).items() if p not in sans}
        figee = self.copie_figee(self.valeurs(), sha) if any(x[0] == "commande" for x in a_jouer.values()) else contextlib.nullcontext()
        with figee as d:
            def commande(p, cmd):
                r = self.executer(f"set -o pipefail; {cmd} 2>&1 | tail -n 200", "doc" if court and p == "tests" else p, dossier=d); return r.returncode, r.stdout
            def outil(p):
                r = self.porte_distante("doc" if court and p == "tests" else p, sha); return r.get("code", 1), r.get("sortie", "")
            res, sorties = _portes.jouer(a_jouer, commande, outil)
        return _portes.marquer_court(res, court), sorties

    def demander_fusion(self, args):
        """demander-fusion "<résumé>" : branche propre, poussée, à jour, règle du correctif, porte pret déclarée, puis les
        4 portes jouées et inscrites (une rouge = pas de demande) → demande au chef de projet."""
        v = self.valeurs(); resume = " ".join(args).strip(); chef_finit = self.finition == "chef"
        git = lambda *a: self.git(v, *a); notes = []
        tete = _portes.controler_demande(git, "HEAD", v["branche"], self.principale, resume, self.portes, self.motif_tests,
                                         sale=bool(git("status", "--porcelain").stdout.strip()), pret=not chef_finit, notes=notes)
        plus = {"retard": notes[0]} if notes else {}                       # lot B : en retard sans fichier commun, la fusion mettra à jour
        go = None
        if self.regle_go:                                                  # règle de go : go inscrit (ou hors go tracé), recopié dans la demande
            mission = ""
            try: mission = (Path(self.contexte.get("dossier") or "/nulle-part") / "MISSION.md").read_text()
            except OSError: pass
            def spec_lue(chemin):
                r = git("show", f"{tete}:{chemin}"); return r.stdout if r.returncode == 0 else None
            go = _portes.go_de_la_demande(self.demandes.parent / "go", v["sujet"], mission, spec_lue, self.go_mots)
        # porte courte (spec 2026-10-28) : le courtier lit le diff (jamais l'agent) ; `doc` remplace `tests` pour une demande de documentation seule
        portes, court, mode = _portes.choisir(self.portes, self.doc, git, f"origin/{self.principale}", tete, self.motif_tests, depots=(v["copie"],) if v.get("copie") else ())
        with self.tour(v) if _file.avec_tests(portes) else contextlib.nullcontext():   # lot A : le tour AVANT les portes, gardé jusqu'à la dernière
            res, sorties = self.jouer_portes(tete, sans=("pret",) if chef_finit else (), portes=portes, court=court)   # outils : sur le commit demandé
        _portes.refuser_rouges(res, sorties)
        # finition = chef (spec 2026-10-13) : la même demande, « à finir » — la branche est LIVRÉE au chef, qui fait la finition
        _portes.inscrire_demande(self.demandes, v["sujet"], v["branche"], tete, resume, self.contexte.get("agent"), res,
                                 **({"etat": "à finir"} if chef_finit else {}), **({"go": go} if go else {}), **plus)
        if self.chef_projet:                                               # prévenir le chef de projet : relecture ou finition à faire
            texte = (f"Livraison de {v['sujet']} ({v['branche']}, {tete[:10]}) à FINIR : {resume[:300]} — crée ta branche de finition depuis "
                     f"origin/{v['branche']}, fais la finition, puis « pousser » et « demander-fusion » de ton outil chef de projet."
                     if chef_finit else
                     f"Demande de fusion de {v['sujet']} ({v['branche']}) : {resume[:300]} — relis-la (« demandes » puis "
                     f"« relire {v['sujet']} » de ton outil chef de projet), puis renvoie-la ou demande la fusion.")
            _transport.lancer(str(Path(__file__).resolve().parents[2] / "bin/berger"), ['parler', self.chef_projet, '--stdin'], input=texte,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if chef_finit: return {"livraison": f"{v['branche']} livrée à ton chef de projet, qui fait la finition (pret)", "commit": tete[:10],
                               "portes": _portes.resume(res), **({"mode": mode} if mode else {}), **plus}
        return {"demande": f"fusion de {v['branche']} demandée au chef de projet", "commit": tete[:10], "portes": _portes.resume(res),
                **({"mode": mode} if mode else {}), **plus}
