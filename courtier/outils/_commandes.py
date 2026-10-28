# -*- coding: utf-8 -*-
"""Base commune des outils à COMMANDES FIXÉES (types « ssh » et « commandes ») — pas un type d'outil en soi.

Les commandes sont écrites dans config.toml par le propriétaire, jamais fournies par l'agent :
  [outils.<nom>.lecture]   verbe = "commande"  — lancées SANS validation : n'y mettre QUE des lectures
  [outils.<nom>.actions]   verbe = "commande"  — des ÉCRITURES : chacune attend la validation du propriétaire
Une commande peut contenir {arg} : l'agent fournit alors UN argument (lettres, chiffres, . _ - /, 64 caractères au
plus, sans « .. »), passé entre guillemets. Sans {arg}, aucun argument n'est accepté. Une commande peut contenir {agent} :
le courtier y met l'agent QUI DEMANDE (jamais une valeur fournie par l'agent) — pour qu'un outil ne travaille que dans le
dossier de son appelant. Sortie : 15 000 caractères (la fin)."""
import importlib.util, re, shlex
from pathlib import Path

_spec = importlib.util.spec_from_file_location("outil__contexte", Path(__file__).with_name("_contexte.py"))
_contexte = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_contexte)   # contexte propre à chaque appel

_spec_transport = importlib.util.spec_from_file_location('berger_transport', Path(__file__).with_name('_transport.py'))
_transport = importlib.util.module_from_spec(_spec_transport); _spec_transport.loader.exec_module(_transport)

ARG = re.compile(r"[\w./-]{1,64}")
# git lancé par le courtier (HORS bac à sable) dans un dossier où un agent écrit : hooks et fsmonitor désactivés par
# l'environnement (prioritaire sur la config du dépôt) — un agent ne doit pas pouvoir faire exécuter une commande au courtier.
ENV_GIT = {"GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/dev/null",
           "GIT_CONFIG_KEY_1": "core.fsmonitor", "GIT_CONFIG_VALUE_1": "false"}
MAX = 15000


def bac_a_sable(cmd, dossier, masques, reseau=False, ecriture=(), tmp=None, env=None, lecture=()):
    """Commande lancée par le courtier dans un dossier où un AGENT écrit (tests, scripts du projet) : elle exécute du
    code que l'agent a pu modifier → jamais avec les droits du courtier. bubblewrap : tout en lecture seule sauf ce
    dossier, coffre/clés/autres agents masqués (tmpfs ou /dev/null), pas de réseau (sauf reseau=True : localhost des
    tests ; les secrets restent masqués), processus isolés et tués avec le courtier.
    Serveur MCP d'un agent (berger-mcp, 18/10/2026) : `cmd` en liste (argv, sans shell), `dossier` None, `ecriture` = ses
    seuls dossiers inscriptibles (montés APRÈS les masques : un masque ne les recouvre pas), `tmp` = SON temporaire monté en
    /tmp, `env` = l'environnement entier (vidé d'abord : --clearenv), `lecture` = dossiers remontés en lecture seule APRÈS les
    masques (accès web, 18/10/2026 : le dossier du socket du proxy, sous courtier/mcp masqué)."""
    import os
    if isinstance(cmd, str): raise ValueError("script littéral refusé : utiliser le transport privé")
    a = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", *(["--bind", str(tmp), "/tmp"] if tmp else ["--tmpfs", "/tmp"]),
         *(["--bind", str(dossier), str(dossier)] if dossier else []), "--unshare-pid", "--die-with-parent", "--new-session"]
    if not reseau: a.append("--unshare-net")
    vides = []
    for m in masques:
        if tmp and (m == "/tmp" or m.startswith("/tmp/")): continue     # /tmp est déjà le sien : rien à créer dedans
        if os.path.isdir(m): a += ["--tmpfs", m]; vides.append(m)
        elif os.path.exists(m): a += ["--ro-bind", "/dev/null", m]
    for e in ecriture: a += ["--bind", str(e), str(e)]
    for e in lecture: a += ["--ro-bind", str(e), str(e)]
    if env is not None:                                                  # serveur MCP : un masque est vide ET en lecture seule
        a += [x for m in dict.fromkeys(vides) for x in ("--remount-ro", m)]
        a.append("--clearenv"); a += [x for k, v in env.items() for x in ("--setenv", k, str(v))]
    return a + ["--chdir", str(dossier or (ecriture[0] if ecriture else "/tmp")), *cmd]


class Base:
    lieu = "?"                                                        # « où » la commande tourne, pour l'aperçu
    contexte = _contexte.ContexteDeLAppel(None)                        # posé par le courtier pour CET appel : {"agent": …}

    def __init__(self, reglages):
        self.verbes = {v: self.fabriquer(v, c) for v, c in reglages.get("lecture", {}).items()}
        self.ecritures = {v: (self.fabriquer_apercu(v, c), self.fabriquer(v, c)) for v, c in reglages.get("actions", {}).items()}

    def hotes(self): return {}

    def commande(self, modele, args):
        if "{agent}" in modele:
            a = (self.contexte or {}).get("agent", "")
            if not re.fullmatch(r"[\w-]{1,40}", a): raise ValueError("appelant inconnu : cette commande ne s'utilise que par un agent")
            modele = modele.replace("{agent}", shlex.quote(a))
        if "{arg}" in modele:
            if len(args) != 1 or not ARG.fullmatch(args[0]) or ".." in args[0] or args[0].startswith("-"):
                raise ValueError("cette commande attend UN argument simple (lettres, chiffres, . _ - /)")
            return modele.replace("{arg}", shlex.quote(args[0]))
        if args: raise ValueError("cette commande n'accepte aucun argument")
        return modele

    def fabriquer(self, verbe, modele):
        def lancer(args): return self.resultat(self.executer(self.commande(modele, args), verbe))
        lancer.__doc__ = f"{verbe} : {modele}"
        return lancer

    def fabriquer_apercu(self, verbe, modele):
        def apercu(args): return f"{self.lieu} : {self.commande(modele, args)}"
        apercu.__doc__ = f"{verbe} : {modele}"
        return apercu

    @staticmethod
    def resultat(r):
        sortie = r.stdout + ("\n[erreurs]\n" + r.stderr[-2000:] if r.stderr.strip() else "")
        return {"code": r.returncode, "sortie": sortie[-MAX:], "coupe": len(sortie) > MAX}

    def executer(self, cmd, verbe=None):                              # verbe : pour l'outil qui en a besoin (journal, délai…)
        raise NotImplementedError
