"""Les besoins Berger (modulaire, lot 4b) : les lire, en ranger un, le clore ; annoncer aux agents la consigne changée d'un outil.

Les verbes ne font qu'aiguiller : la LECTURE passe par l'API (besoins), les ACTIONS par les services du noyau (ranger_besoin, clore_besoin, annoncer_outil :
noyau/actions.py), dont le geste reste au cœur. Aucun contrôle ici : qui peut envoyer un besoin, débit, doublons, secrets et chaîne d'équipe sont au
courtier ; gardien, état de clôture, besoin introuvable, consigne absente, dans le geste. Corps des verbes : ceux de bin/berger, mot pour mot."""

FAMILLE = "besoins"


def _opt(args, nom): return args[args.index(nom) + 1] if nom in args else None


def verbe_besoin(args, prive=False):
    opt = lambda nom: _opt(args, nom)
    if args[:1] == ["clore"] and len(args) >= 3:     # berger besoin clore <n°> fait|refuse|transmis "<suite>" [--par <gardien>]
        reste = [x for i, x in enumerate(args[3:]) if x != "--par" and (i == 0 or args[3:][i - 1] != "--par")]
        print(clore_besoin(args[1], args[2], " ".join(reste).strip(), opt("--par")))
    elif args[:1] in ([], ["liste"]):
        l = besoins()
        if "--json" in args: print(json.dumps(l, ensure_ascii=False, indent=1))
        else: print("\n".join(f"n° {b['n']}  {b['quand'][:16].replace('T', ' ')}  {b['de']} → {b.get('a', '?')}  [{b['genre']}] {b['texte']}" for b in l) or "aucun besoin ouvert")
    else: return NotImplemented

def verbe_besoin_ranger(args, prive=False): print(ranger_besoin(args[0], args[1], " ".join(args[2:])))   # usage interne (courtier, berger-outil besoin)
def verbe_annonce_outil(args, prive=False): print(annoncer_outil(args[0], "--premiere" in args))   # usage interne (courtier : consigne d'un outil changée)


VERBES = {"besoin": verbe_besoin, "besoin-ranger": verbe_besoin_ranger, "annonce-outil": verbe_annonce_outil}
AIDE = {
    "besoin": "berger besoin [liste] [--json] | clore <n°> fait|refuse|transmis \"<suite>\"   besoins Berger ouverts, et leur clôture",
    "besoin-ranger": "berger besoin-ranger <de> <genre> <texte>   (courtier, berger-outil besoin) range un besoin Berger",
    "annonce-outil": "berger annonce-outil <outil> [--premiere]   (courtier) annonce aux agents la consigne changée d'un outil",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}
# Ce qui passe sans écarter la famille : l'IndexError d'un argument manquant (comme avant), un refus d'usage (Refus) et une panne du CŒUR sortie d'un
# service d'action (ErreurService : commandes.lancer ressort l'exception d'origine, telle qu'avant). Toute autre erreur, dans la famille ou dans la lecture
# (besoins), l'écarte, nommée.
PASSE = {v: (IndexError, Refus, ErreurService) for v in VERBES}
