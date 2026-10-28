"""Ce qui s'affiche sur le bureau et dans les barres d'état : badge, barre d'état Claude Code, titres Herdr, notification (modulaire, lot 3 bis).

Code déplacé de bin/berger : aucun comportement changé."""
import datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, tomllib, unicodedata
import importlib.util
import shutil as _sh, textwrap
from pathlib import Path
from noyau.config import *
from noyau.transport import *
from noyau.affichage import *
from noyau.agents import *
from noyau.herdr import *
from noyau.lectures import *


COULEURS_BADGE = ("44;97", "45;97", "42;30", "43;30", "46;30", "41;97", "100;97")   # fond;texte ANSI, un par agent


def badge(a):
    """Badge coloré « icône NOM » d'un agent, comme sur les barres d'état : couleur = réglage `couleur` d'agent.conf
    (codes ANSI fond;texte, ex. 44;97), sinon une couleur stable tirée de la liste selon le rang de l'agent."""
    if a not in agents(): return f"\033[1;100;97m {a} \033[0m"
    c = conf(a); code = c.get("couleur") or COULEURS_BADGE[agents().index(a) % len(COULEURS_BADGE)]
    return f"\033[1;{code}m {c['icone']} {c['nom'].upper()} \033[0m"


def statusline(a):
    """Barre d'état Claude Code d'un agent (réglage statusLine posé par regenerer ; doc code.claude.com/docs/en/statusline) :
    relève le quota de l'abonnement (rate_limits) pour le panneau Tokens, affiche « modèle · 5 h x % · 7 j y % ».
    Ne doit jamais échouer : une barre d'état en erreur gêne l'agent."""
    try:
        d = json.load(sys.stdin); rl = d.get("rate_limits") or {}
        if rl:
            CONSO.mkdir(parents=True, exist_ok=True); tmp = CONSO / f".quota-claude-{a}.tmp"
            tmp.write_text(json.dumps({"t": time.time(), "agent": a, "rate_limits": {k: {"used_percentage": (v or {}).get("used_percentage"),
                                       "resets_at": (v or {}).get("resets_at")} for k, v in rl.items() if isinstance(v, dict)}}))
            os.replace(tmp, CONSO / "quota-claude.json")
        morceaux = [(d.get("model") or {}).get("display_name") or "Claude"]
        for k, n in (("five_hour", "5 h"), ("seven_day", "7 j")):
            v = rl.get(k) or {}
            if v.get("used_percentage") is not None: morceaux.append(f"{n} {float(v['used_percentage']):.0f} % → {quand_remise(v.get('resets_at'))}")
        if len(morceaux) == 1: morceaux.append("quota non transmis (passerelle, ou 1re réponse)")
        ctx = (d.get("context_window") or {}).get("used_percentage")
        if ctx is not None: morceaux.append(f"contexte {float(ctx):.0f} %")
        print(badge(a) + " " + " · ".join(morceaux))
    except Exception:
        print("Claude")


def notifier(titre, texte, urgent=False):
    """Notification sur le bureau (notify-send) et dans Herdr (s'il est installé : c'est la seule visible sur un
    serveur sans bureau) ; toujours écrite dans le journal de Berger, avec l'échec éventuel de Herdr."""
    if shutil.which(NOTIFY_SEND):
        subprocess.run([NOTIFY_SEND, *(["-u", "critical"] if urgent else []), "Berger", "Une information est disponible dans le panneau Berger."], capture_output=True)
    echec_herdr = ""
    if shutil.which(HERDR):
        try:
            r = subprocess.run([HERDR, "notification", "show", "Berger", "--body", "Une information est disponible dans le panneau Berger.", "--sound", "request"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode: echec_herdr = f" [herdr : échec, code {r.returncode}]"
        except (OSError, subprocess.TimeoutExpired) as e: echec_herdr = f" [herdr : échec, {type(e).__name__}]"
    with open(BERGER / "courtier/notifications.log", "a") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M}\t{'URGENT' if urgent else 'info'}\t{titre}\t{' '.join(texte.split())[:300]}{echec_herdr}\n")


def titre_herdr(a):
    c = conf(a); ck = checklist(a); p = len(pendants(a))
    morceaux = [f"{c['icone']} {c['nom']}"]
    if ck and not ck["fini"]:
        t = ck["titre"] if len(ck["titre"]) <= 30 else ck["titre"][:30].rsplit(" ", 1)[0]
        if t.count("(") > t.count(")"): t = t[:t.rfind("(")]                # pas de parenthèse ouverte au bout
        if t != ck["titre"]: t = t.rstrip(" ,;:") + "…"
        morceaux.append(f"{t} {ck['faites']}/{ck['total']}" + (" ⚠ bloqué" if ck["bloque"] else ""))
    if p: morceaux.append(f"{p} à valider")
    return " · ".join(morceaux)


_LIBELLES = None


def libelles_espaces():
    """{workspace_id: libellé} des espaces Herdr, lu UNE fois par passage (planificateur : chaque minute)."""
    global _LIBELLES
    if _LIBELLES is None: _LIBELLES = {w.get("workspace_id"): w.get("label") for w in herdr("workspace", "list").get("workspaces", [])}
    return _LIBELLES


def mettre_a_jour_titres(a):
    ids = herdr_ids(a)
    # L'espace suit le nom AFFICHÉ (agent.conf : icone + nom) : renommer un agent ne change ni son identifiant ni son
    # dossier (sa conversation est rangée par dossier), seulement ce qui s'affiche — espace, titres, panneaux.
    ws, voulu = ids.get("workspace"), f"{conf(a)['icone']} {conf(a)['nom']}"
    if ws in libelles_espaces() and libelles_espaces()[ws] != voulu:
        herdr("workspace", "rename", ws, voulu); libelles_espaces()[ws] = voulu
    for moteur, pane in ids.get("agents", {}).items():
        herdr("pane", "report-metadata", pane, "--source", "berger", "--title", f"{titre_herdr(a)} · {moteur}")


__all__ = ('COULEURS_BADGE', 'badge', 'statusline', 'notifier', 'titre_herdr', 'libelles_espaces', 'mettre_a_jour_titres',)
