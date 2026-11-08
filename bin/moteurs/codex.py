"""Le moteur Codex : sa version, son verdict d'admission, ses arguments de lancement (et son profil « mur ouvert »), son lecteur de
consommation, et ce qui n'appartient qu'à lui — l'ouverture interactive d'un développeur Codex strict (dialogue de confiance, remise
de la mission) et ses constantes CODEX_*. Déplacé de bin/berger (modulaire, lot 2) : aucun comportement changé.
Ce que les réglages du mur génèrent pour Codex (config_codex, FEATURES_CODEX_STRICT) reste au cœur (lot 4, cas 1)."""
import json, re, time

NOM = "codex"
ORDRE = 2
efforts_permis = ("low", "medium", "high", "xhigh")      # -c model_reasoning_effort=… : à confirmer sur la version installée (codex-cli 0.165.0)
# Recherche web intégrée (outil web_search, hors bac à sable et hors courtier) : coupée pour tout strict (web-integre, lot 1).
# Mesuré en 0.165.0 sur un faux fournisseur local : sans réglage, l'outil part au modèle (mode « cached ») ; « disabled » le
# retire, et -c l'emporte sur le profil -p.
RECHERCHE_WEB_COUPEE = ["-c", 'web_search="disabled"']
# Sous-agents et clock coupés pour tout strict (31/10/2026, demande du propriétaire) : hors de la liste fermée du contrat (12).
# Mesuré en 0.165.0 : features.multi_agent=false retire le namespace multi_agent_v1 (et tool_search, dont c'était la seule source
# différée) ; features.sleep_tool=false retire le namespace clock du modèle par défaut. Le namespace collaboration (sous-agents v2
# du modèle par défaut gpt-6.1-sol) n'est retiré par AUCUN réglage mesuré : il reste, et fait rougir (12) — voulu.
SOUS_AGENTS_COUPES = ["-c", "features.multi_agent=false", "-c", "features.sleep_tool=false"]


def executable(): return executable_moteur(NOM)


def version(): return version_moteur(NOM)


def verdict(): return verdict_moteur(NOM)


def ecrire_profil_ouvert(a, instructions):
    """Configuration persistante générée, sans contenu dans les arguments du moteur.

    Ce profil ne remplace que les instructions ; les autres réglages du mur ouvert
    viennent toujours de la configuration de base de l'utilisateur.
    """
    nom = f"ouvert-{a}"
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", nom):
        raise ValueError("nom de profil invalide")
    CODEX_HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    texte = "# Configuration générée par Berger.\n"
    if instructions:
        texte += "developer_instructions = " + json.dumps(instructions, ensure_ascii=False) + "\n"
    transport.ecrire_configuration(CODEX_HOME, nom + ".config.toml", texte)
    return nom


def args(a, interactif=True):
    """Arguments de Codex selon le mur de l'agent."""
    w = str(travail(a)); extra = consigne_systeme(a)
    if ouvert(a):
        profil = ecrire_profil_ouvert(a, extra)
        return ["-C", w, "--dangerously-bypass-approvals-and-sandbox", "-p", profil]
    return ["-C", w, "-p", a, *RECHERCHE_WEB_COUPEE, *SOUS_AGENTS_COUPES]


def args_modele(modele, effort=None):
    """Le modèle (et l'effort de raisonnement) de la mission, en arguments de lancement (-c : valeur TOML, ou chaîne telle quelle)."""
    return ["-m", modele] + (["-c", f"model_reasoning_effort={effort}"] if effort else [])


def modele_impose(a):
    """Option de l'installation pour les stricts : aucun repli silencieux sur un modèle choisi côté serveur."""
    if ouvert(a) or "codex_modele_strict" not in CONFIG: return None
    modele = CONFIG["codex_modele_strict"]
    if not isinstance(modele, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", modele):
        raise ValueError("codex_modele_strict invalide : nom de modèle attendu (lettres, chiffres, . _ - ; 64 signes au plus ; pas de tiret initial)")
    return modele


def lecteur_conso(): return lire_conso_codex


def lire_conso_codex(index):
    """Codex : <CODEX_HOME>/sessions/**/rollout-*.jsonl ; session_meta donne le dossier (cwd), chaque token_count le
    décompte du tour (last_token_usage) et les limites d'usage (rate_limits), relevées dans quota_codex.json."""
    out = []; quota = None
    for f in sorted((CODEX_HOME / "sessions").glob("**/*.jsonl")):
        a = index.get("cwd:" + str(f)); mod = index.get("mod:" + str(f), "")
        for brut in lignes_neuves(f, index):
            try: d = json.loads(brut); pl = d.get("payload") or {}
            except ValueError: continue
            if d.get("type") == "session_meta":
                a = agent_du_dossier(pl.get("cwd")); index["cwd:" + str(f)] = a; continue
            if d.get("type") == "turn_context" and pl.get("model"): mod = pl["model"]; index["mod:" + str(f)] = mod; continue
            if pl.get("type") != "token_count": continue
            try: t = datetime.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).timestamp()
            except (ValueError, KeyError): continue
            if pl.get("rate_limits"): quota = {"t": t, "rate_limits": pl["rate_limits"]}
            u = (pl.get("info") or {}).get("last_token_usage") or {}
            if a and u:
                out.append({"t": t, "a": a, "m": "codex", "mod": mod, "lus": u.get("input_tokens") or 0,
                            "ecr": (u.get("output_tokens") or 0) + (u.get("reasoning_output_tokens") or 0),
                            "ctx": u.get("input_tokens") or 0, "id": f"{f.name}:{t}"})
    if quota:
        CONSO.mkdir(parents=True, exist_ok=True); (CONSO / "quota-codex.json").write_text(json.dumps(quota))
    return out


# Ouverture interactive d'un développeur Codex strict : chaque attente et chaque appel est borné.
CODEX_OUVERTURE_DELAI = 60
CODEX_RECEPTION_DELAI = 15
CODEX_SCRUTATION = 0.5
CODEX_MISSION_TENTATIVES = 2
CODEX_TITRE_CONFIANCE = re.compile(r"^[ \t]*Folder access[ \t]*$", re.M)
CODEX_OPTION_RESTREINTE = re.compile(r"^[ \t]*›[ \t]+1\.[ \t]+Open restricted[ \t]*$", re.M)
CODEX_OPTION_QUITTER = re.compile(r"^[ \t]*2\.[ \t]+Quit[ \t]*$", re.M)
CODEX_VALIDATION_RESTREINTE = re.compile(r"^[ \t]*enter continue · esc quit[ \t]*$", re.M)


def dialogue_confiance_codex(texte):
    """Dialogue réel 0.163.0 fourni par le propriétaire ; bannière permise, sélection restreinte exigée."""
    motifs = (CODEX_TITRE_CONFIANCE, CODEX_OPTION_RESTREINTE, CODEX_OPTION_QUITTER, CODEX_VALIDATION_RESTREINTE)
    lignes = [list(m.finditer(texte)) for m in motifs]
    if any(len(x) != 1 for x in lignes): return False
    positions = [x[0].start() for x in lignes]
    if positions != sorted(positions): return False
    options = re.findall(r"^[ \t]*[›❯>]?[ \t]*([1-9])\.[ \t]+(.+?)[ \t]*$", texte, re.M)
    return options == [("1", "Open restricted"), ("2", "Quit")]


def ecran_developpeur_codex(a, pane):
    """Uniquement le panneau de cet agent vivant ; absent/illisible = état inconnu à attendre.
    Jamais le scrollback ni le contenu d'écran dans une erreur.
    """
    vivants = herdr("agent", "list").get("agents", [])
    if not any(x.get("name") == f"{a}-codex" and x.get("pane_id") == pane for x in vivants):
        return "", "unknown"
    r = herdr("pane", "read", pane, "--source", "visible", "--format", "text")
    if not isinstance(r.get("text"), str): return "", "unknown"
    return ANSI.sub("", r["text"]), statut_herdr(pane, ttl=0)


def mission_codex_recue(message, texte, statut):
    """Working confirme l'activité ; un écho au repos doit être dans l'historique, jamais dans le compositeur."""
    if statut == "working": return True
    lignes = texte.splitlines()
    invites = [i for i, ligne in enumerate(lignes) if re.match(r"^[ \t]*[›❯](?:[ \t]|$)", ligne)]
    if not invites: return False              # pas de frontière de saisie visible : aucune preuve d'écho soumis
    historique = "\n".join(lignes[:invites[-1]])
    return " ".join(message.split()) in " ".join(historique.split())


def attendre_developpeur_codex(a, pane, message_deja_envoye=None):
    """Valide par Entrée le choix restreint déjà sélectionné du vrai dialogue, puis attend l'invite.
    Un autre écran (hooks, login…) n'est jamais validé automatiquement.
    Au second tour, une réception tardive vaut succès (True) ; une invite prête vaut False.
    """
    fin = time.monotonic() + CODEX_OUVERTURE_DELAI; choisi = False
    while time.monotonic() < fin:
        texte, statut = ecran_developpeur_codex(a, pane)
        if message_deja_envoye is not None and mission_codex_recue(message_deja_envoye, texte, statut): return True
        if dialogue_confiance_codex(texte) and "? for shortcuts" not in texte:
            if not choisi:
                herdr("pane", "send-keys", pane, "enter"); choisi = True
        elif statut in AU_REPOS and re.search(r"^\s*[›❯](?:[ \t].*)?$", texte, re.M):
            # Ne pas confondre le sélecteur d'un autre dialogue avec l'invite.
            if not re.search(r"^\s*[›❯]\s*[1-9]\.", texte, re.M) and "? for shortcuts" in texte:
                return False
        time.sleep(CODEX_SCRUTATION)
    raise ValueError("invite Codex restreinte non prête dans le délai")


def remettre_mission_codex(a, pane, message):
    """L'API accepte le transport ; working ou l'écho complet confirment la réception.
    Avant le réessai unique, revérifier ces témoins pour éviter un second envoi déjà reçu.
    """
    for tentative in range(CODEX_MISSION_TENTATIVES):
        if attendre_developpeur_codex(a, pane, message if tentative else None): return
        try:
            herdr_api("agent.prompt", {"target": f"{a}-codex", "text": message}, strict=True)
        except ValueError:
            continue
        fin = time.monotonic() + CODEX_RECEPTION_DELAI
        while time.monotonic() < fin:
            texte, statut = ecran_developpeur_codex(a, pane)
            if mission_codex_recue(message, texte, statut): return
            time.sleep(CODEX_SCRUTATION)
    raise ValueError("réception de mission Codex non confirmée après deux tentatives")
