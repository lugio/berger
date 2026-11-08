"""Commandes « veille » (modulaire, lot 3) : veille.
Le temps réel de l'interface (une ligne par changement). reveil, tache, relancer et notifier restent au cœur (fonctions du cœur, bac à sable, réglages moteur).

Code déplacé de bin/berger : aucun comportement changé. Contrat : FAMILLE, VERBES {verbe: fonction(args, prive=False)}, AIDE, DROITS.
Une fonction de verbe rend NotImplemented quand la forme demandée n'est pas la sienne (« commande inconnue » comme avant).
Ce module n'emploie que l'API du noyau et la bibliothèque standard : voir commandes/__init__.py."""


VEILLE_PAS, VEILLE_REGROUPE, VEILLE_STATUTS = 0.5, 0.3, 5                    # s : relevé des fichiers, regroupement, statuts Herdr


VEILLE_APPELS = 30   # s : courtier/appels.log relevé à ce rythme seulement — il change à chaque appel du courtier (mesuré le


def empreinte_veille(statuts=None, appels=None):
    """Ce qui fait changer les vues (spec interface §6 quater) : échanges, appels du courtier, écritures en attente, demandes
    de fusion, lectures, et pour chaque agent (Claude ou Codex : mêmes fichiers) checklist, TODO, mission, journal du jour,
    À lire, panneaux — date et taille de chaque fichier, rien de son contenu ; plus les statuts Herdr relevés à part."""
    fichiers = [ECHANGES, LECTURES]
    fichiers += sorted((BERGER / "courtier" / "validations").glob("*.json")) + sorted((BERGER / "equipes").glob("*/demandes/*.json"))
    fichiers += sorted((BERGER / "a-lire").glob("*.md"))
    for a in agents():
        d = AGENTS / a
        fichiers += [d / x for x in ("CHECKLIST.md", "TODO.md", "MISSION.md", ".herdr.json", f"memory/{aujourdhui()}.md")]
        fichiers += sorted((d / "a-lire").glob("*.md"))
    vu = []
    for f in fichiers:
        try: st = f.stat(); vu.append((str(f), st.st_mtime_ns, st.st_size))
        except OSError: pass
    return hash((tuple(vu), statuts, appels))


def veille(fois=None):
    """berger veille : pour le serveur de l'interface (temps réel, §6 quater). Relève l'empreinte toutes les 0,5 s (os.stat,
    Python standard), les statuts Herdr toutes les 5 s et courtier/appels.log toutes les 30 s (VEILLE_APPELS), et écrit une ligne « changement » quand quelque chose a changé
    (regroupé sur 0,3 s). N'écrit rien d'autre : la page relit ses vues elle-même (donnees(), la source unique)."""
    releve_statuts = lambda: tuple(sorted((a, m, statut_herdr(p, ttl=0)) for a in agents() for m, p in herdr_ids(a).get("agents", {}).items()))
    def releve_appels():
        try: st = (BERGER / "courtier/appels.log").stat(); return (st.st_mtime_ns, st.st_size)
        except OSError: return None
    statuts, appels, releve, releve_a = releve_statuts(), releve_appels(), time.time(), time.time()   # l'état de départ n'est pas un changement
    avant = empreinte_veille(statuts, appels); n = 0
    while fois is None or n < fois:
        time.sleep(VEILLE_PAS); n += 1
        if time.time() - releve >= VEILLE_STATUTS: statuts, releve = releve_statuts(), time.time()
        if time.time() - releve_a >= VEILLE_APPELS: appels, releve_a = releve_appels(), time.time()
        e = empreinte_veille(statuts, appels)
        if e == avant: continue
        while True:                                                         # regroupe une rafale d'écritures en un seul signal
            time.sleep(VEILLE_REGROUPE); e2 = empreinte_veille(statuts, appels)
            if e2 == e: break
            e = e2
        avant = e
        print("changement", datetime.datetime.now().isoformat(timespec="milliseconds"), flush=True)


# ─── Les verbes (corps déplacés de main(), inchangés) ───

def verbe_veille(args, prive=False):                                  # temps réel de l'interface : une ligne par changement
    if args: return NotImplemented
    try: veille()
    except (KeyboardInterrupt, BrokenPipeError): pass


FAMILLE = "veille"
VERBES = {"veille": verbe_veille}
AIDE = {
    "veille": "berger veille                       une ligne « changement » quand les données des vues changent (temps réel de l'interface)",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}
