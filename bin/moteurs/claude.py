"""Le moteur Claude Code : sa version, son verdict d'admission, ses arguments de lancement, son lecteur de consommation et
l'écriture de son type d'abonnement. Déplacé de bin/berger (modulaire, lot 2) : aucun comportement changé.
Ce que les réglages du mur (permissions, bac à sable) génèrent pour Claude reste au cœur (lot 4, cas 1)."""
import json, os, re
from pathlib import Path

NOM = "claude"
ORDRE = 1                                   # ordre déclaré : MOTEURS = claude, puis codex


def executable(): return executable_moteur(NOM)


def version(): return version_moteur(NOM)


def verdict(): return verdict_moteur(NOM)


def args(a, interactif=True):
    """Arguments de Claude Code selon le mur de l'agent. Remote Control (rc =) seulement en interactif."""
    c = conf(a); extra = consigne_systeme(a)
    args = ["--dangerously-skip-permissions"]
    # Tout strict : aucun serveur MCP hors d'un --mcp-config (il n'y en a pas) — ni .mcp.json, ni connecteurs claude.ai
    # (mesuré le 17/10 : seuls les serveurs du --mcp-config passent). Drapeau sans valeur, en tête : jamais juste après
    # --mcp-config, variadique, qui avalerait l'argument suivant.
    if not ouvert(a):
        f = ecrire_mcp_claude(a)   # berger-mcp : ses serveurs, relayés ; --mcp-config est variadique : suivi d'une option, jamais d'un argument
        args += (["--mcp-config", str(f)] if f else []) + ["--strict-mcp-config"]
    if not ouvert(a) and externe(a):
        f = dossier(a) / ".reglages-claude.json"; t = json.dumps(reglages_strict_externe(a), ensure_ascii=False, indent=2)
        if lire(f) != t: f.write_text(t)
        args += ["--settings", str(f)]
    elif not ouvert(a):
        args = ["--setting-sources", "project,local"] + args
        f = ecrire_reseau_claude(a)     # sites permis : strictAllowlist n'est lu QUE par --settings
        if f: args += ["--settings", str(f)]
    elif externe(a) and env_appelant(a):   # mur ouvert dans un dossier existant : rien n'est écrit chez lui, l'appelant passe par --settings
        f = dossier(a) / ".appelant-claude.json"; t = json.dumps({"env": env_appelant(a)}, ensure_ascii=False, indent=2)
        if lire(f) != t: f.write_text(t)
        args += ["--settings", str(f)]
    if interactif and c.get("rc"): args += ["--remote-control", c["rc"]]
    if extra:   # par FICHIER : Herdr refuse une consigne longue en argument (« cannot be encoded safely », mesuré le 04/10)
        f = transport.ecrire_configuration(dossier(a) / ".consignes", "systeme.md", extra)
        ancien = dossier(a) / ".consigne-systeme.md"
        if os.path.lexists(ancien):
            import stat
            meta = ancien.lstat()
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_nlink != 1:
                raise ValueError("ancienne configuration système non conforme")
            ancien.unlink()
        args += ["--append-system-prompt-file", str(f)]
    return args


def lecteur_conso(): return lire_conso_claude


def lire_conso_claude(index):
    """Claude Code : ~/.claude/projects/<dossier de travail en tirets>/*.jsonl ; chaque réponse porte message.usage."""
    cles = {re.sub(r"[^A-Za-z0-9-]", "-", str(travail(a))): a for a in agents()}
    out = []
    for f in sorted((HOME / ".claude/projects").glob("*/**/*.jsonl")):
        racine = f.relative_to(HOME / ".claude/projects").parts[0]
        a = next((cles[c] for c in sorted(cles, key=len, reverse=True) if racine == c or racine.startswith(c + "-")), None)
        if not a: continue
        for brut in lignes_neuves(f, index):
            if b'"usage"' not in brut: continue
            try:
                d = json.loads(brut); m = d.get("message") or {}; u = m.get("usage") or {}
                t = datetime.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).timestamp()
            except (ValueError, KeyError, TypeError, AttributeError): continue
            if not u: continue
            ctx = (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
            out.append({"t": t, "a": a, "m": "claude", "mod": m.get("model", ""), "lus": ctx, "ecr": u.get("output_tokens") or 0,
                        "ctx": ctx, "id": m.get("id") or d.get("requestId") or d.get("uuid")})
    return out


ABONNEMENTS_CLAUDE = {"max", "pro", "team", "enterprise"}


def abonnement_claude(type_, palier, fichier=None):
    """Claude Code range le type d'abonnement et le palier dans ses identifiants (claudeAiOauth.subscriptionType /
    rateLimitTier) en lisant le profil du compte sur api.anthropic.com — adresse fixe, que le pare-feu de Berger bloque
    (seule la passerelle sort). Sans eux il affiche « Claude API » et se croit hors abonnement. On les écrit une fois
    (valeurs du compte, lues sur un poste qui voit le profil) ; au renouvellement du jeton Claude Code garde l'ancienne
    valeur quand la nouvelle manque. Aucun autre champ touché, rien d'affiché du fichier ; à refaire après un /login."""
    if type_ not in ABONNEMENTS_CLAUDE: raise SystemExit(f"type inconnu : {type_} (attendu : {', '.join(sorted(ABONNEMENTS_CLAUDE))})")
    if not re.fullmatch(r"[a-z0-9_]{3,60}", palier): raise SystemExit(f"palier illisible : {palier}")
    f = Path(fichier or HOME / ".claude/.credentials.json")
    try: d = json.loads(f.read_text())
    except (OSError, ValueError): raise SystemExit(f"{f} illisible : rien écrit")
    o = d.get("claudeAiOauth")
    if not isinstance(o, dict): raise SystemExit("pas de connexion par compte (claudeAiOauth) : rien écrit")
    o["subscriptionType"], o["rateLimitTier"] = type_, palier
    t = f.with_name(f.name + ".tmp")
    with os.fdopen(os.open(t, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as w: json.dump(d, w)
    os.replace(t, f)
    return f"ok : subscriptionType, rateLimitTier écrits ({type_}, {palier}) ; relancer les agents Claude pour l'affichage"
