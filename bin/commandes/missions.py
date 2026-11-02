"""Les missions (modulaire, lot 4a) : un agent en confie une à un autre, la suit, relit son rapport, la termine.

Les verbes ne font qu'aiguiller : les LECTURES passent par l'API (suivi, rapport_mission), les ACTIONS par les services du noyau (confier_mission,
terminer_mission : noyau/actions.py). Aucun contrôle ici : agent inscrit, une mission à la fois, plafond, moteur et modèle, checklist finie sont
dans le service ; les droits entre agents (mission:<agent>, chef, coordinateur) dans le courtier. Corps des verbes : ceux de bin/berger, mot pour mot."""

FAMILLE = "missions"


def _opt(args, nom): return args[args.index(nom) + 1] if nom in args else None


def verbe_mission(args, prive=False):                                 # berger mission <agent> "<texte>" [--par <qui>]
    opt = lambda nom: _opt(args, nom)
    reste, i = [], 1
    while i < len(args):
        if args[i] in ("--par", "--moteur", "--modele"): i += 2; continue
        reste.append(args[i]); i += 1
    print(confier_mission(args[0], " ".join(reste), opt("--par") or PROPRIETAIRE, opt("--moteur"), opt("--modele")))

def verbe_suivi(args, prive=False): print(json.dumps(suivi(args[0]), ensure_ascii=False, indent=1))
def verbe_rapport_mission(args, prive=False): print(json.dumps(rapport_mission(args[0]), ensure_ascii=False, indent=1))
def verbe_fin_mission(args, prive=False): print(terminer_mission(args[0], _opt(args, "--par") or PROPRIETAIRE, _opt(args, "--motif")))


VERBES = {"mission": verbe_mission, "suivi": verbe_suivi, "rapport-mission": verbe_rapport_mission, "fin-mission": verbe_fin_mission}
AIDE = {
    "mission": "berger --stdin [\"mission\", agent, texte]   confie une mission ; options --moteur/--modele/--par dans le même tableau",
    "suivi": "berger suivi <agent>                état d'une mission (JSON : statut, checklist, journal, validations)",
    "rapport-mission": "berger rapport-mission <agent>       le rapport d'une mission terminée (JSON)",
    "fin-mission": "berger fin-mission <agent>          range la mission et ferme l'espace de l'agent",
}
DROITS = {"mission": {"prive": True, "cas_go": None}, "suivi": {"prive": False, "cas_go": None},
          "rapport-mission": {"prive": False, "cas_go": None}, "fin-mission": {"prive": False, "cas_go": None}}
# Ce qui passe sans écarter la famille : l'IndexError d'un argument manquant (comme avant), un refus d'usage (Refus) et une panne du CŒUR sortie d'un
# service d'action (ErreurService : commandes.lancer ressort l'exception d'origine, telle qu'avant). Toute autre erreur, dans la famille ou dans une lecture,
# écarte la famille, nommée.
PASSE = {v: (IndexError, Refus, ErreurService) for v in VERBES}
