"""Commandes « gestes » (interface web v2, lot 2 ; spec docs/plans/2026-11-03-interface-web-v2-spec.md, go n° 140) : berger action.

Les QUATRE gestes du propriétaire depuis l'interface web — valider, refuser (motif obligatoire), répondre à une question, marquer lu —
et rien d'autre. Chaque geste prend le chemin de la ligne de commande (garde-fou 1) : `berger valider <n>` / `berger refuser <n>` lancés
tels quels, `parler_agent` (berger parler), `lire_document` (berger lire <n> : marque lu). Aucun pouvoir nouveau.

    berger action apercu <action> <cible>                       → JSON {action, cible, titre, apercu, agent, empreinte}
    berger action faire <action> <cible> --empreinte <e> --source <ip>   (JSON {"motif"|"texte"} sur stdin) → JSON {fait, message}

`empreinte` (garde-fou 4) : l'IDENTITÉ de la chose visée — sha256 du fichier de la demande (valider, refuser), de la clé du document
(chemin + date en ns : marquer lu), de la question (répondre). Elle va jusqu'à l'écriture : `berger valider|refuser <n> --empreinte`
la revérifie sous le verrou des décisions ; `lire_document(cle=…)` / `marquer_lu` revérifient la clé sous le verrou des lectures ;
la réponse cite la question à laquelle elle répond. Jamais un rang dans une liste qui bouge.
Le journal de l'agent concerné reçoit chaque geste « via l'interface web » avec la source (garde-fou 5) ; le serveur tient, lui, le
journal de TOUTES les tentatives, refus compris, et le débit. Propriétaire seul : refusé à un agent (BERGER_AGENT)."""
import contextlib, hashlib, io

ACTIONS_WEB = ("valider", "refuser", "repondre", "lu")
TEXTE_MAX = 2000
PROGRAMME = Path(__file__).resolve().parent.parent / "berger"


def _empreinte(*morceaux):
    return hashlib.sha256("\n".join(str(m) for m in morceaux).encode("utf-8")).hexdigest()


def _cible(action, cible):
    """(titre, apercu, agent, empreinte, objet) de la chose visée, ou Refus nommé. Les mêmes lectures que les vues."""
    if action in ("valider", "refuser"):
        if not re.fullmatch(r"\d{1,9}", cible or ""): raise Refus(f"{action} : un numéro d'écriture")
        f = BERGER / "courtier/validations" / f"{cible}.json"
        try: brut = f.read_bytes(); d = json.loads(brut)
        except (OSError, ValueError): raise Refus(f"pas de demande n° {cible} en attente (déjà décidée, ou numéro inconnu)") from None
        if not isinstance(d, dict): raise Refus(f"demande n° {cible} illisible")
        titre = f"Écriture n° {cible} · {d.get('agent', '?')} · {d.get('outil', '?')} {d.get('verbe', '?')}"
        return titre, str(d.get("apercu", "")), str(d.get("agent", "")), hashlib.sha256(brut).hexdigest(), d
    if action == "repondre":
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", cible or ""): raise Refus("repondre : l'identifiant d'un agent")
        q = next((x for x in decisions() if x["genre"] == "question" and x["pour"] == "toi" and x["agent"] == cible), None)
        if q is None: raise Refus(f"aucune question de {cible} ne t'attend (déjà répondue, ou adressée à son chef)")
        return f"Question de {conf(cible)['nom']}", q["detail"], cible, _empreinte(cible, q["detail"]), q
    if action == "lu":
        if not re.fullmatch(r"[0-9a-f]{16}", cible or ""): raise Refus("lu : l'identifiant d'un document")
        d = next((x for x in documents_a_lire() if not x["regle"] and id_document(x) == cible), None)
        if d is None: raise Refus(f"document {cible} absent d'À lire (déjà réglé, ou retiré)")
        return "Marquer lu", d["titre"], d["auteur"] or "", _empreinte(d["cle"]), d
    raise Refus(f"action inconnue : {action} (valider, refuser, repondre, lu)")


def _texte(brut, quoi):
    t = "".join(c for c in str(brut or "") if c == "\n" or c >= " ").strip()      # caractères de contrôle retirés, sauts de ligne gardés
    if not t: raise Refus(f"{quoi} obligatoire")
    if len(t) > TEXTE_MAX: raise Refus(f"{quoi} trop long ({len(t)} caractères ; {TEXTE_MAX} au plus)")
    return t


def _berger(*args):
    """`berger <args>` tel qu'en ligne de commande (le même code, le même journal du courtier) → sa dernière ligne ; Refus s'il échoue."""
    r = subprocess.run([sys.executable, str(PROGRAMME), *args], capture_output=True, text=True, timeout=60)
    sortie = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    if r.returncode: raise Refus((sortie or ["échec"])[-1][:300])
    return (sortie or ["fait"])[-1][:300]


def apercu(action, cible):
    titre, ap, agent, emp, _ = _cible(action, cible)
    return {"action": action, "cible": cible, "titre": titre, "apercu": ap, "agent": agent or None, "empreinte": emp}


def faire(action, cible, empreinte, source, entree):
    via = f"via l'interface web ({source})"
    try: titre, ap, agent, emp, objet = _cible(action, cible)
    except Refus as e: raise Refus(f"demande modifiée depuis l'aperçu : {e} — rien n'est fait") from None   # la chose vue n'est plus là
    if not empreinte or empreinte != emp:
        if agent in agents(): journal(agent, f"{via} : {action} {cible} REFUSÉ — la demande a changé depuis l'aperçu")
        raise Refus("demande modifiée depuis l'aperçu : rien n'est fait — rouvre-la et relis-la")
    if action == "valider":
        message = _berger("valider", cible, "--empreinte", emp)              # revérifiée sous le verrou des décisions, au moment d'écrire
        if agent in agents(): journal(agent, f"{via} : écriture n° {cible} validée par {PROPRIETAIRE} ({ap}) → {message}")
    elif action == "refuser":
        motif = _texte(entree.get("motif"), "motif du refus")
        if agent in agents():                                    # AVANT la décision : le courtier dit à l'agent de lire le motif
            journal(agent, f"{via} : écriture n° {cible} refusée par {PROPRIETAIRE} — motif : {' '.join(motif.split())}")
            tracer_echange(PROPRIETAIRE, agent, "message", f"motif du refus de l'écriture n° {cible} : {motif}")
        try: message = _berger("refuser", cible, "--empreinte", emp)
        except Refus as e:
            if agent in agents(): journal(agent, f"{via} : refus de l'écriture n° {cible} NON enregistré ({e}) — le motif ci-dessus ne vaut pas")
            raise
    elif action == "repondre":
        texte = _texte(entree.get("texte"), "réponse")
        message_agent = f"Réponse de {PROPRIETAIRE} à ta question {objet['detail']} :\n{texte}"   # la question citée : l'identité va jusqu'à la remise
        with contextlib.redirect_stdout(io.StringIO()): parler_agent(agent, message_agent, None, PROPRIETAIRE)   # berger parler : tracé dans les échanges
        journal(agent, f"{via} : réponse de {PROPRIETAIRE} à ta question {objet['detail']}")
        message = f"réponse envoyée à {conf(agent)['nom']}"
    else:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie): rc = lire_document(None, True, objet["cle"])   # berger lire, par l'identité du document
        if rc: raise Refus("demande modifiée depuis l'aperçu : " + (sortie.getvalue().strip() or "document changé") + " — rien n'est fait")
        if agent in agents(): journal(agent, f"{via} : « {ap} » marqué lu par {PROPRIETAIRE}")
        message = "marqué lu"
    return {"fait": True, "message": message}


def verbe_action(args, prive=False):
    if os.environ.get("BERGER_AGENT"): sys.exit("berger action : réservé au propriétaire (interface web), jamais à un agent")
    opt = lambda nom: args[args.index(nom) + 1] if nom in args and args.index(nom) + 1 < len(args) else None
    try:
        if len(args) == 3 and args[0] == "apercu": r = apercu(args[1], args[2])
        elif len(args) >= 3 and args[0] == "faire":
            try: entree = json.loads(sys.stdin.read(TEXTE_MAX * 4 + 200) or "{}")
            except ValueError: raise Refus("entrée illisible (JSON attendu)") from None
            if not isinstance(entree, dict): raise Refus("entrée illisible (objet JSON attendu)")
            r = faire(args[1], args[2], opt("--empreinte"), opt("--source") or "?", entree)
        else: return NotImplemented
    except Refus as e: sys.exit(f"refusé : {e}")
    print(json.dumps(r, ensure_ascii=False)); return 0


FAMILLE = "gestes"
VERBES = {"action": verbe_action}
AIDE = {"action": "berger action apercu|faire <valider|refuser|repondre|lu> <cible> …   geste du propriétaire depuis l'interface web (même chemin que la ligne de commande)"}
DROITS = {"action": {"prive": False, "cas_go": None}}
