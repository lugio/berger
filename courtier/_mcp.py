# -*- coding: utf-8 -*-
"""Serveurs MCP des agents strict, côté courtier (berger-mcp, 18/10/2026, docs/plans/2026-10-18-berger-mcp-spec.md).

Le relais `bin/berger-mcp <agent> <serveur>`, lancé par le moteur, se connecte à courtier/mcp/<agent>.sock et demande un
serveur. Le courtier (1) vérifie que CET agent y a droit (`mcp =` de son agent.conf) ; (2) demande à `berger mcp-enveloppe`
comment le lancer (la seule source des refus) et le lance ENFERMÉ (bac_a_sable de outils/_commandes.py : masques du mur de
l'agent et du courtier, réseau coupé, écriture limitée, environnement vidé ; bwrap absent ou en échec : aucun serveur, jamais
de repli) — un processus par session, tué quand le relais se ferme ; puis relaie les messages JSON-RPC, une ligne chacun :
(3) journal de chaque appel (méthode, outil, durée, taille, verdict — aucune valeur) ; (4) tout message du serveur qui contient
un secret est bloqué (réponse → erreur MCP, le reste écarté), tracé et notifié ; (5) débit et taille bornés.
Serveur déclaré `web` (voie B, fusion 2/3) : le dossier du socket du proxy web de l'agent est remonté en lecture seule dans
l'enveloppe, réseau toujours coupé (socat et lanceur du navigateur : bin/berger, serveur_mcp).
Ce module ne lit ni le coffre ni la config : le courtier lui passe ses fonctions (contient_secret, journal, alerte)."""
import json, os, re, subprocess, threading, time

BLOQUEE = "réponse bloquée : elle contient un secret"


def lignes(flux, maxi):
    """(ligne, trop_longue) pour chaque ligne de `flux` ; au-delà de `maxi` octets, le début seul (la suite est lue et jetée)."""
    while True:
        b = flux.readline(maxi + 1)
        if not b: return
        if len(b) > maxi and not b.endswith(b"\n"):
            while True:
                r = flux.readline(65536)
                if not r or r.endswith(b"\n"): break
            yield b[:maxi], True
        else: yield b, False


def textes(x):
    """Toutes les chaînes d'un message décodé (une valeur échappée dans le JSON y est en clair)."""
    if isinstance(x, dict): return [t for k, v in x.items() for t in [str(k), *textes(v)]]
    if isinstance(x, list): return [t for v in x for t in textes(v)]
    return [str(x)] if x is not None else []


def erreur(i, message, code=-32000):
    return (json.dumps({"jsonrpc": "2.0", "id": i, "error": {"code": code, "message": message}}, ensure_ascii=False) + "\n").encode()


class Relais:
    """Les messages d'UNE session : du client (le moteur, par berger-mcp) vers le serveur, et retour, filtrés."""

    def __init__(self, agent, serveur, vers_client, vers_serveur, contient_secret, journal, alerte, max_par_minute=30, max_reponse=2 * 1024 * 1024):
        self.agent, self.serveur, self.au_client, self.au_serveur = agent, serveur, vers_client, vers_serveur
        self.secret, self.journal, self.alerte = contient_secret, journal, alerte
        self.debit, self.maxi = max_par_minute, max_reponse
        self.attente, self.recents, self.verrou = {}, [], threading.Lock()

    def noter(self, methode, outil, ok, detail):
        self.journal(self.agent, f"mcp:{self.serveur}", methode or "?", [outil] if outil else [], ok, detail)

    def du_client(self, b):
        """Un message du moteur : une requête est comptée (débit) et retenue (journal à sa réponse), puis transmise telle quelle."""
        try: m = json.loads(b)
        except ValueError: m = None
        if isinstance(m, dict) and m.get("method") and "id" in m:
            t = time.time()
            with self.verrou:
                self.recents = [x for x in self.recents if t - x < 60]
                trop = len(self.recents) >= self.debit
                if not trop: self.recents.append(t)
            outil = (m.get("params") or {}).get("name") if m["method"] == "tools/call" and isinstance(m.get("params"), dict) else None
            outil = str(outil)[:60] if outil else None
            if trop:
                self.noter(m["method"], outil, False, f"limite : {self.debit} appels par minute")
                return self.au_client(erreur(m["id"], f"trop d'appels ({self.debit} par minute au plus)"))
            self.attente[json.dumps(m["id"])] = (m["method"], outil, t)
        self.au_serveur(b)

    def du_serveur(self, b, trop_long=False):
        """Un message du serveur : bloqué s'il est trop long ou contient un secret, sinon transmis. Une réponse attendue est
        journalisée (durée, taille, verdict) ; bloquée, le moteur reçoit une erreur MCP à la place."""
        try: m = None if trop_long else json.loads(b)
        except ValueError: m = None
        i = m.get("id") if isinstance(m, dict) else None
        if trop_long and i is None:                                      # début de la ligne : son id, s'il est lisible
            x = re.search(rb'"id"\s*:\s*(\d+|"[^"\\]{0,200}")', b); i = json.loads(x.group(1)) if x else None
        cle = json.dumps(i) if i is not None else None
        methode, outil, t0 = self.attente.pop(cle, (None, None, None)) if cle and (m is None or "method" not in m) else (None, None, None)
        quoi = f"{len(b)} o" + (f", {int((time.time() - t0) * 1000)} ms" if t0 else "")
        if trop_long:
            self.noter(methode or "réponse", outil, False, f"trop grande (> {self.maxi} o) : bloquée")
            return self.au_client(erreur(i, f"réponse trop grande ({self.maxi} octets au plus)")) if t0 else None
        texte = b.decode("utf-8", "replace")
        # un seul passage sur les chaînes décodées (une valeur échappée dans le JSON y est en clair), jointes par NUL : ni une
        # valeur du coffre ni une forme de clé ne contient NUL, donc rien ne se forme à cheval sur deux chaînes (vécu le 18/10 :
        # un appel par chaîne sur le tools/list de 3 Mo de REA tenait le courtier à 99 % pendant des minutes)
        if self.secret(texte) or (m is not None and self.secret("\x00".join(textes(m)))):
            genre = methode or (m.get("method") if isinstance(m, dict) else None) or "message"
            self.noter(genre, outil, False, f"BLOQUÉ (secret dans la réponse), {quoi}")
            self.alerte(f"Berger · MCP {self.serveur}", f"{self.agent} : une réponse du serveur MCP « {self.serveur} » contenait un secret : bloquée ({genre})")
            return self.au_client(erreur(i, BLOQUEE)) if t0 else None
        if t0: self.noter(methode, outil, not (isinstance(m, dict) and "error" in m), quoi + (", erreur du serveur" if isinstance(m, dict) and "error" in m else ""))
        self.au_client(b)


def ouvrir(agent, serveur, droits, berger, bac_a_sable, masques_courtier, verifier=True):
    """(processus, enveloppe) du serveur lancé ENFERMÉ, ou lève PermissionError (le refus, en clair). `droits` = le `mcp =`
    de l'agent (lu par le courtier) ; `berger` = bin/berger (berger mcp-enveloppe : les refus § 3, une seule source)."""
    if serveur not in droits: raise PermissionError(f"{agent} n'a pas le droit au serveur MCP « {serveur} » (mcp = de son agent.conf)")
    r = subprocess.run([str(berger), "mcp-enveloppe", agent, serveur], capture_output=True, text=True, timeout=120)
    if r.returncode: raise PermissionError((r.stderr or r.stdout).strip()[-300:] or "refusé par berger mcp-enveloppe")
    e = json.loads(r.stdout); web = e.get("web")
    lecture = [web["dossier"]] if web else []                             # le dossier du socket du proxy web : vu, jamais inscriptible
    argv = lambda cmd: bac_a_sable(cmd, None, list(masques_courtier) + e["masques"], e["reseau"], ecriture=e["ecriture"], tmp=e["tmp"],
                                   env=e["env"], lecture=lecture)
    for d in e["ecriture"]: os.makedirs(d, exist_ok=True)
    if web:                                                               # 700, jamais un lien (le courtier y place le socket)
        os.makedirs(os.path.dirname(web["dossier"]), mode=0o700, exist_ok=True)
        try: os.mkdir(web["dossier"], 0o700)
        except FileExistsError: pass
        if os.path.islink(web["dossier"]) or not os.path.isdir(web["dossier"]): raise PermissionError(f"{web['dossier']} : pas un dossier (lien refusé)")
        os.chmod(web["dossier"], 0o700)
    if verifier:                                                          # l'enveloppe démarre-t-elle ? sinon RIEN (jamais sans elle)
        try: ok = subprocess.run(argv(["true"]), capture_output=True, timeout=30).returncode == 0
        except (OSError, subprocess.TimeoutExpired): ok = False
        if not ok: raise PermissionError("enveloppe (bwrap) absente ou en échec : aucun serveur MCP lancé (jamais de repli sans enveloppe)")
    p = subprocess.Popen(argv(e["commande"]), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return p, e


def session(agent, lire, ecrire, fermer, droits, berger, bac_a_sable, masques_courtier, contient_secret, journal, alerte):
    """Une session du relais : `lire` (flux binaire bufferisé), `ecrire(octets)`, `fermer()`. Première ligne : {"serveur": …} ;
    réponse {"ok": true} puis le relais, ou {"ok": false, "erreur": …} et fin."""
    try: tete = json.loads(lire.readline(512) or b"{}")
    except ValueError: tete = {}
    serveur = str(tete.get("serveur", ""))[:60]
    try: p, e = ouvrir(agent, serveur, droits, berger, bac_a_sable, masques_courtier)
    except (PermissionError, OSError, ValueError, subprocess.TimeoutExpired) as x:
        journal(agent, f"mcp:{serveur or '?'}", "session", [], False, f"refusée : {str(x)[:120]}")
        try: ecrire((json.dumps({"ok": False, "erreur": str(x)[:300]}, ensure_ascii=False) + "\n").encode())
        finally: fermer()
        return
    journal(agent, f"mcp:{serveur}", "session", [], True, "ouverte (enfermée" + (", réseau" if e["reseau"] else ", sans réseau")
            + (", web par le proxy du courtier" if e.get("web") else "") + ")")
    verrou = threading.Lock()
    def au_client(b):
        with verrou: ecrire(b)
    def au_serveur(b):
        try: p.stdin.write(b); p.stdin.flush()
        except (BrokenPipeError, ValueError, OSError): pass
    r = Relais(agent, serveur, au_client, au_serveur, contient_secret, journal, alerte, e["max_par_minute"], e["max_reponse"])
    au_client((json.dumps({"ok": True}) + "\n").encode())
    def du_client():
        try:
            for b, _ in lignes(lire, 16 * 1024 * 1024): r.du_client(b)
        except (OSError, ValueError): pass
        finally:                                                          # le relais s'est fermé : la session s'arrête
            try: p.stdin.close()
            except OSError: pass
            try: p.wait(5)                                                # le temps de rendre ses dernières réponses
            except subprocess.TimeoutExpired: p.terminate()
    threading.Thread(target=du_client, daemon=True).start()
    try:
        for b, long_ in lignes(p.stdout, e["max_reponse"]): r.du_serveur(b, long_)
    except (OSError, ValueError): pass
    finally:
        p.terminate()
        try: p.wait(5)
        except subprocess.TimeoutExpired: p.kill(); p.wait()
        fermer(); journal(agent, f"mcp:{serveur}", "session", [], True, f"fermée (code {p.returncode})")
