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
import importlib.util, os, subprocess
from pathlib import Path

import importlib.util
_spec_transport = importlib.util.spec_from_file_location('berger_transport', Path(__file__).with_name('_transport.py'))
_transport = importlib.util.module_from_spec(_spec_transport); _spec_transport.loader.exec_module(_transport)

_spec = importlib.util.spec_from_file_location("outil_copie", Path(__file__).with_name("copie.py"))
_copie = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_copie)
_spec = importlib.util.spec_from_file_location("outil__portes", Path(__file__).with_name("_portes.py"))
_portes = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_portes)


class Outil(_copie.Outil):
    def __init__(self, reglages, secret, verifier_hote):
        self.principale = reglages.get("principale", "main"); self.demandes = Path(reglages["demandes"])
        self.chef_projet = reglages.get("chef_projet", ""); self.motif_tests = reglages.get("motif_tests", _portes.MOTIF_TESTS)
        self.portes = _portes.declarees(reglages)                          # {porte: ("commande", cmd) | ("outil", "<outil> <verbe>")}
        self.finition = reglages.get("finition", "developpeur")             # "chef" : la finition (pret) est faite par le chef de projet
        if self.finition not in ("developpeur", "chef"): raise ValueError(f"finition = « {self.finition} » : \"developpeur\" ou \"chef\"")
        self.portes_outil = {p: v for p, (genre, v) in self.portes.items() if genre == "outil"}
        self.regle_go = reglages.get("regle_go", True) is not False; self.go_mots = reglages.get("go_mots") or None   # spec 2026-10-15-regle-go
        self.portes_par = {}                                               # {porte: verbe de lecture}, posé par le courtier (<porte>_outil)
        lecture = {"etat": "git status -sb && echo && echo '--- mes commits pas encore dans {principale} :' && git log --oneline origin/{principale}..HEAD",
                   "mettre-a-jour": "git fetch origin {principale} && git merge --no-edit origin/{principale}",
                   "pousser": "git push -u origin {branche}"}
        for p, (genre, cmd) in self.portes.items():
            if genre == "commande": lecture[p] = f"set -o pipefail; {cmd} 2>&1 | tail -n 200"
        lecture.update(reglages.get("lecture", {}))
        super().__init__({**reglages, "lecture": lecture, "actions": reglages.get("actions", {})}, secret, verifier_hote)
        self.verbes["demander-fusion"] = self.demander_fusion
        for p in self.portes_outil: self.verbes[p] = self.fabriquer_distant(p)
        self.hors_bac = {"etat", "mettre-a-jour", "pousser"}             # git seulement (réseau, clé SSH) ; tout le reste en bac à sable

    def remplir(self, cmd):
        return super().remplir(cmd.replace("{principale}", self.principale))

    def git(self, v, *args):
        return subprocess.run(["git", *args], cwd=v["copie"], capture_output=True, text=True, timeout=120, env={**os.environ, **_copie._base.ENV_GIT})

    def fabriquer_distant(self, porte):
        def distant(args):
            if args: raise ValueError(f"{porte} n'accepte aucun argument : c'est ta branche poussée qui est vérifiée")
            return self.porte_distante(porte)
        distant.__doc__ = f"{porte} : la porte de l'équipe, lancée par l'outil « {self.portes_outil[porte]} » sur ta branche POUSSÉE"
        return distant

    def porte_distante(self, porte):
        """<porte>_outil : le verbe de lecture d'un outil du courtier, avec SA branche (jamais un argument de l'agent)."""
        if not self.portes_par.get(porte): raise RuntimeError(f"{porte}_outil « {self.portes_outil[porte]} » indisponible (outil non chargé)")
        return self.portes_par[porte]([self.valeurs()["branche"]])

    def jouer_portes(self, sans=()):
        """Les 4 portes (sauf `sans` : « non mesuré »), dans l'ordre, chacune inscrite : commande dans la copie (bac à sable),
        outil sur la branche poussée."""
        def commande(p, cmd):
            r = self.executer(f"set -o pipefail; {cmd} 2>&1 | tail -n 200", p); return r.returncode, r.stdout
        def outil(p):
            r = self.porte_distante(p); return r.get("code", 1), r.get("sortie", "")
        return _portes.jouer({p: x for p, x in self.portes.items() if p not in sans}, commande, outil)

    def demander_fusion(self, args):
        """demander-fusion "<résumé>" : branche propre, poussée, à jour, règle du correctif, porte pret déclarée, puis les
        4 portes jouées et inscrites (une rouge = pas de demande) → demande au chef de projet."""
        v = self.valeurs(); resume = " ".join(args).strip(); chef_finit = self.finition == "chef"
        git = lambda *a: self.git(v, *a)
        tete = _portes.controler_demande(git, "HEAD", v["branche"], self.principale, resume, self.portes, self.motif_tests,
                                         sale=bool(git("status", "--porcelain").stdout.strip()), pret=not chef_finit)
        go = None
        if self.regle_go:                                                  # règle de go : go inscrit (ou hors go tracé), recopié dans la demande
            mission = ""
            try: mission = (Path(self.contexte.get("dossier") or "/nulle-part") / "MISSION.md").read_text()
            except OSError: pass
            def spec_lue(chemin):
                r = git("show", f"{tete}:{chemin}"); return r.stdout if r.returncode == 0 else None
            go = _portes.go_de_la_demande(self.demandes.parent / "go", v["sujet"], mission, spec_lue, self.go_mots)
        res, sorties = self.jouer_portes(sans=("pret",) if chef_finit else ())   # outils : sur la branche POUSSÉE (vérifiée ci-dessus)
        _portes.refuser_rouges(res, sorties)
        # finition = chef (spec 2026-10-13) : la même demande, « à finir » — la branche est LIVRÉE au chef, qui fait la finition
        _portes.inscrire_demande(self.demandes, v["sujet"], v["branche"], tete, resume, self.contexte.get("agent"), res,
                                 **({"etat": "à finir"} if chef_finit else {}), **({"go": go} if go else {}))
        if self.chef_projet:                                               # prévenir le chef de projet : relecture ou finition à faire
            texte = (f"Livraison de {v['sujet']} ({v['branche']}, {tete[:10]}) à FINIR : {resume[:300]} — crée ta branche de finition depuis "
                     f"origin/{v['branche']}, fais la finition, puis « pousser » et « demander-fusion » de ton outil chef de projet."
                     if chef_finit else
                     f"Demande de fusion de {v['sujet']} ({v['branche']}) : {resume[:300]} — relis-la (« demandes » puis "
                     f"« relire {v['sujet']} » de ton outil chef de projet), puis renvoie-la ou demande la fusion.")
            _transport.lancer(str(Path(__file__).resolve().parents[2] / "bin/berger"), ['parler', self.chef_projet, '--stdin'], input=texte,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if chef_finit: return {"livraison": f"{v['branche']} livrée à ton chef de projet, qui fait la finition (pret)", "commit": tete[:10],
                               "portes": _portes.resume(res)}
        return {"demande": f"fusion de {v['branche']} demandée au chef de projet", "commit": tete[:10], "portes": _portes.resume(res)}
