#!/usr/bin/env python3
"""Interface web v2 : la page « Réglages » en LECTURE SEULE (spec docs/plans/2026-11-05-interface-reglages-spec.md, go n° 169). Sans modèle,
faux Herdr, installation JETABLE (tests/_jeu_vues.py), vraies requêtes HTTP sur 127.0.0.1. Vérifie :
 1. le lecteur (bin/noyau/reglages.py) : des MARQUEURS uniques, construits à l'exécution, placés dans chaque clé de la liste fermée, dans des
    clés nouvelles au nom sensible (api_token, hote_secours…), dans des valeurs à forme de clé, dans une adresse, une marque privée, une
    liste et une table imbriquée, ne sortent JAMAIS des données ; les autres valeurs, si (une liste sans élément sensible, la clé voisine
    d'une table imbriquée) ;
 2. MOTS ENTIERS (remarque de relecture du chef) : « ip », « cle », « url » masquent ip_secours, cle_api, url_webhook, jamais description,
    principale, equipe, cycle, boucle ni curling ;
 3. le coffre n'est JAMAIS ouvert : un faux coffre (un tube nommé, qui bloquerait toute lecture) surveillé par un crochet d'audit — aucun
    accès à son dossier, ni pour dire s'il existe ;
 4. ce qui manque, avec sa conséquence : transcription absente ou non exécutable (micro grisé), actions absentes (décisions en lecture
    seule), outil sans son fichier dans courtier/outils/, équipe sans dépôt lisible ; config.toml invalide, absent : dit sans son contenu ;
 5. le serveur : GET /api/vue/reglages (session exigée, Host contrôlé) → réponse complète (corps ET en-têtes) sans aucun marqueur, journal
    du serveur non plus ; toute autre méthode (POST, PUT, DELETE, PATCH, HEAD, OPTIONS) → 405 ; config.toml rendu invalide pendant que le
    serveur tourne → la page le dit (200, lisible = non), toujours sans marqueur ; mêmes en-têtes stricts (CSP inchangée) ;
 6. la vue `berger vue reglages` (texte et --json) : même masquage ; web seulement (aucun onglet Herdr) ; la page (app.js) la rend sans
    champ ni bouton qui modifie, avec l'en-tête « Ces réglages se changent dans ~/berger/config.toml » ;
 7. AVEC Playwright (s'il est présent ; sinon « NON JOUÉ », jamais « ok ») : tests/_page_reglages.js à 390, 820, 1280, 1440 et 1920 px,
    dans les 2 thèmes — en-tête, « [masqué] », signalements, aucun marqueur dans le DOM, ni « null » ni « undefined », aucun débordement.
Usage : python3 tests/interface-reglages.py (0 = tout passe). Playwright : BERGER_PLAYWRIGHT=<dossier du module>, comme tests/interface-finition.py."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import http.client, importlib.util, json, os, random, re, shutil, signal, socket, string, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def marqueur():
    """Un marqueur unique, en lettres seulement (aucun chiffre ni signe : jamais pris pour une fuite)."""
    return "repere" + "".join(random.choice(string.ascii_lowercase) for _ in range(14))


def forme_de_cle():
    """Une valeur à forme de clé (MOTIFS_CLES), construite à l'exécution."""
    return "-".join(["sk", "ant", "api"]) + "".join(random.choice(string.ascii_letters) for _ in range(40))


def charger_lecteur():
    if str(SRC / "bin") not in sys.path: sys.path.insert(0, str(SRC / "bin"))
    try:
        import noyau.reglages as R
        return R
    except ImportError as e:
        dire(False, f"bin/noyau/reglages.py : le lecteur des réglages existe ({e})"); return None


R = charger_lecteur()
if R is None:
    print(f"---- {ko} échec(s)"); sys.exit(1)

# ── la liste fermée de la spec, et des noms nouveaux au nom sensible ──
FERMEE = ["coffre", "cle", "cle_fichier", "utilisateur_cle", "mot_de_passe_cle", "port_cle", "hote", "hotes", "ip_secours", "webdav", "adresse",
          "sources", "marques_privees", "masques", "masques_si_presents", "masque_fichier", "chemins_bloques", "entete_appelant"]
NOUVEAUX = ["api_token", "hote_secours", "cle_api", "url_webhook", "jeton_session", "secret_partage", "pass_admin", "mot_de_passe_base",
            "apiToken", "clé_privée", "urls_sondes"]
VISIBLES = ["description", "principale", "equipe", "cycle", "boucle", "curling", "boucle_max", "tipi", "clef_usb_absente"]


def toml(v):
    return json.dumps(v, ensure_ascii=False)


with tempfile.TemporaryDirectory() as t:
    t = Path(t); i = t / "berger"; maison = t / "maison"; (i / "courtier/outils").mkdir(parents=True); maison.mkdir()
    shutil.copy2(SRC / "courtier/outils/ssh.py", i / "courtier/outils/ssh.py")
    caches, visibles = {}, {}
    def cache(nom): caches[nom] = marqueur(); return caches[nom]
    def montre(nom): visibles[nom] = marqueur(); return visibles[nom]
    # le faux coffre : un TUBE nommé dans un dossier à lui (toute ouverture en lecture bloquerait) ; le crochet d'audit relève tout accès
    dcoffre = t / "coffre-surveille"; dcoffre.mkdir(); coffre = dcoffre / "coffre.json"; os.mkfifo(coffre)
    marque = marqueur()
    lignes = [f'proprietaire = "Proprio"', f"coffre = {toml(str(coffre))}"]
    for k in FERMEE:
        if k == "coffre": continue
        lignes.append(f"{k} = [{toml(cache('racine.' + k))}]" if k in ("hotes", "sources", "marques_privees", "masques", "masques_si_presents", "chemins_bloques")
                      else f"{k} = {toml(cache('racine.' + k))}")
    lignes[lignes.index(f"marques_privees = [{toml(caches['racine.marques_privees'])}]")] = f"marques_privees = [{toml(marque)}]"
    for k in NOUVEAUX: lignes.append(f"{toml(k)} = {toml(cache('racine.' + k))}")
    for k in VISIBLES: lignes.append(f"{k} = {toml(montre('racine.' + k))}")
    lignes += [f"note_libre = {toml('commentaire ' + forme_de_cle() + ' ' + cache('valeur.forme'))}",
               f"miroir = {toml('https://' + cache('valeur.url') + '.exemple.invalid/')}",
               f"compte = {toml(cache('valeur.arobase') + '@serveur.exemple.invalid')}",
               f"passerelle = {toml('10.20.30.40 ' + cache('valeur.ip'))}",
               f"mention = {toml('chez ' + marque + ' ' + cache('valeur.marque'))}",
               f"liste_mixte = [{toml(cache('liste.visible_avant'))}, {toml(forme_de_cle())}]",
               f"liste_claire = [{toml(montre('liste.claire_a'))}, {toml(montre('liste.claire_b'))}]",
               f"chemin_perso = {toml(str(maison) + '/projets/' + montre('chemin.perso'))}",
               "[interface]", "port = 8765", f"adresse = {toml(cache('interface.adresse'))}", f"sources = [{toml(cache('interface.sources'))}]",
               f"nom = {toml(cache('interface.nom'))}",
               "[sauvegarde]", f"webdav = {toml(cache('sauvegarde.webdav'))}", f"utilisateur_cle = {toml(cache('sauvegarde.utilisateur_cle'))}",
               f"mot_de_passe_cle = {toml(cache('sauvegarde.mot_de_passe_cle'))}", f"dossier = {toml(montre('sauvegarde.dossier'))}",
               "[outils.serveur]", 'type = "ssh"', f"hote = {toml(cache('outils.hote'))}", "port = 22", f"cle_fichier = {toml(cache('outils.cle_fichier'))}",
               f"cle = {toml(cache('outils.cle'))}", f"port_cle = {toml(cache('outils.port_cle'))}",
               "[outils.serveur.lecture]", f"etat = {toml('docker ps ' + montre('outils.lecture'))}",
               "[outils.serveur.imbrique]", f"secret = {toml(cache('imbrique.secret'))}", f"clair = {toml(montre('imbrique.clair'))}",
               "[outils.serveur.imbrique.profond]", f"token = {toml(cache('imbrique.token'))}", f"libelle = {toml(montre('imbrique.libelle'))}",
               "[outils.serveur.ip]", f"ici = {toml(cache('table.ip'))}",
               "[outils.inconnu]", 'type = "outil_qui_nexiste_pas"',
               "[outils.pages]", 'type = "pages_publiques"', f"hotes = [{toml(cache('outils.pages.hotes'))}]",
               "[outils.pages.verbes.doc]", f"url = {toml(cache('outils.pages.url'))}", f"aide = {toml(montre('outils.pages.aide'))}",
               "[web]", f"chemins_bloques = [{toml(cache('web.chemins'))}]", "attente = \"4h\"",
               "[equipes.fantome]", f"depot = {toml(str(t / 'depot-absent'))}", f"principale = {toml(montre('equipes.principale'))}",
               "[[gardes]]", 'moment = "avant"', f"commande = {toml('python3 ' + montre('gardes.commande'))}",
               "[[gardes]]", f"commande = {toml('curl https://' + cache('gardes.url') + '.invalid/')}"]
    (i / "config.toml").write_text("\n".join(lignes) + "\n")

    # ── 3. le coffre surveillé ──
    acces = []
    def audit(evenement, args):
        if evenement in ("open", "os.listdir", "os.scandir", "os.chmod", "os.remove", "os.rename", "shutil.copyfile") and args:
            if str(dcoffre) in str(args[0]): acces.append((evenement, str(args[0])))
    sys.addaudithook(audit)
    def bloque(*_): raise TimeoutError("lecture bloquée : le tube du faux coffre a été ouvert")
    signal.signal(signal.SIGALRM, bloque); signal.alarm(30)
    try: d = R.donnees(i, maison); erreur = None
    except Exception as e: d = {}; erreur = f"{type(e).__name__}: {e}"
    finally: signal.alarm(0)
    dire(erreur is None and d.get("lisible") is True, f"le lecteur rend les réglages d'un config.toml valide ({erreur or 'lisible'})")
    dire(not acces, f"le coffre n'est jamais ouvert ni listé, même pour dire s'il existe (accès relevés : {acces[:3]})")
    corps = json.dumps(d, ensure_ascii=False)

    # ── 1. aucun marqueur ne sort ; les valeurs claires, si ──
    sortis = sorted(k for k, m in caches.items() if m in corps)
    dire(not sortis and str(coffre) not in corps and "coffre-surveille" not in corps,
         f"aucune valeur masquée dans les données ({len(caches)} marqueurs : liste fermée, noms sensibles nouveaux, formes de clé, adresses, marque privée, tables) — sortis : {sortis}")
    dire(marque not in corps, "la marque privée déclarée ne sort ni comme valeur, ni dans une autre valeur")
    absents = sorted(k for k, m in visibles.items() if m not in corps)
    dire(not absents, f"les valeurs claires restent visibles (liste sans élément sensible, clé voisine d'une table imbriquée, commande de lecture…) — absentes : {absents}")
    dire(str(maison) not in corps and "~/projets/" + visibles["chemin.perso"] in corps, "le dossier personnel est écrit « ~ » dans une valeur montrée")
    regl = {(s["nom"], c["titre"], r["cle"]): r for s in d.get("sections", []) for c in s["cartes"] for r in c["reglages"]}
    masques = {k: r for k, r in regl.items() if r["masque"]}
    dire(all(r["valeur"] == R.MASQUE == "[masqué]" for r in masques.values()) and len(masques) >= len(FERMEE) + len(NOUVEAUX),
         f"chaque valeur masquée s'affiche « [masqué] » ({len(masques)} masquées)")
    dire(regl.get(("", None, "liste_mixte"), {}).get("valeur") == "[masqué]", "une liste dont UN élément est sensible est masquée en entier")
    dire(regl.get(("outils", "serveur", "imbrique.secret"), {}).get("masque") is True and regl.get(("outils", "serveur", "imbrique.clair"), {}).get("masque") is False
         and regl.get(("outils", "serveur", "imbrique.profond.token"), {}).get("masque") is True and regl.get(("outils", "serveur", "imbrique.profond.libelle"), {}).get("masque") is False,
         "une table imbriquée est parcourue clé par clé (la clé sensible masquée, sa voisine visible, à tous les niveaux)")
    dire(regl.get(("outils", "serveur", "ip"), {}).get("masque") is True, "une table au nom sensible ([outils.serveur.ip]) est masquée en entier")

    # ── 2. mots entiers ──
    for k in ("ip_secours", "cle_api", "url_webhook", "api_token", "hote_secours", "apiToken", "clé_privée", "mot_de_passe_base"):
        dire(R.cle_sensible(k), f"mot entier sensible : « {k} » est masquée")
    for k in ("description", "principale", "equipe", "cycle", "boucle", "curling", "boucle_max", "tipi", "clef_usb_absente", "proprietaire", "port", "type"):
        dire(not R.cle_sensible(k), f"pas un mot entier sensible : « {k} » reste visible")
    dire(all(regl.get(("", None, k), {}).get("masque") is False for k in VISIBLES), "dans les données aussi : description, principale, equipe, cycle, boucle… visibles")
    dire(all(regl.get(("", None, k), {}).get("masque") is True for k in NOUVEAUX), f"dans les données aussi : {', '.join(NOUVEAUX)} masquées")

    # ── catalogue et sections ──
    noms = [s["nom"] for s in d.get("sections", [])]
    dire(noms == ["", "interface", "sauvegarde", "outils", "web", "equipes", "gardes"], f"sections dans l'ordre du fichier, généralités en tête ({noms})")
    dire(regl.get(("", None, "proprietaire"), {}).get("phrase", "").startswith("Ton nom") and regl.get(("", None, "tipi"), {}).get("phrase") == "réglage non décrit",
         "une phrase simple pour un réglage connu ; « réglage non décrit » sinon")
    cartes = {s["nom"]: [c["titre"] for c in s["cartes"]] for s in d.get("sections", [])}
    dire(cartes.get("outils") == ["serveur", "inconnu", "pages"] and cartes.get("gardes") == ["n° 1", "n° 2"],
         f"une carte par entrée d'une famille ([outils.<nom>]) et d'une section répétée ([[gardes]]) ({cartes.get('outils')}, {cartes.get('gardes')})")
    dire(d.get("fichier") == "~/berger/config.toml", f"le chemin montré : ~/berger/config.toml, tel quel ({d.get('fichier')})")

    # ── 4. signalements ──
    sig = " | ".join(f"{x['quoi']} → {x['consequence']}" for x in d.get("signalements", []))
    dire("micro grisé dans Conversation" in sig and "transcription" in sig, f"transcription absente → « micro grisé dans Conversation » ({sig[:120]})")
    dire("décisions en lecture seule dans la page" in sig and "actions" in sig, "actions absentes → « décisions en lecture seule dans la page »")
    dire("« inconnu »" in sig and "courtier/outils/" in sig and "« serveur »" not in sig and "« pages »" in sig,
         "outil déclaré sans son fichier dans courtier/outils/ signalé (inconnu, pages) ; l'outil qui a le sien, non")
    dire("« fantome »" in sig and "dépôt" in sig, "équipe sans dépôt lisible signalée")
    exe = t / "transcripteur"; exe.write_text("#!/bin/sh\necho texte\n"); exe.chmod(0o755)
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\ncoffre = {toml(str(coffre))}\n[interface]\nactions = true\ntranscription = {toml(str(exe))}\n')
    d2 = R.donnees(i, maison)
    dire(d2["lisible"] and not d2["signalements"], f"transcription exécutable et actions = true : rien à signaler ({d2['signalements']})")
    exe.chmod(0o644); d3 = R.donnees(i, maison)
    dire(any("micro grisé" in x["consequence"] for x in d3["signalements"]), "transcription non exécutable → micro grisé")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\ncoffre = {toml(str(coffre))}\n[interface]\ntranscription = {toml(str(coffre))}\n')
    acces.clear(); signal.alarm(30)
    try: d4 = R.donnees(i, maison)
    finally: signal.alarm(0)
    dire(not acces and any("micro grisé" in x["consequence"] for x in d4["signalements"]), f"une transcription qui pointe le coffre n'est pas regardée ({acces[:2]})")
    m_invalide = marqueur()
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\ncle = "{m_invalide}"\n[interface\nport = = 3\n')
    d5 = R.donnees(i, maison); c5 = json.dumps(d5, ensure_ascii=False)
    dire(d5["lisible"] is False and not d5["sections"] and any("invalide" in x["quoi"] for x in d5["signalements"]) and m_invalide not in c5 and "line" not in c5,
         f"config.toml invalide : la page le dit, sans son contenu ni le message de l'analyseur ({d5['signalements']})")
    (i / "config.toml").unlink(); d6 = R.donnees(i, maison)
    dire(d6["lisible"] is False and any("absent" in x["quoi"] for x in d6["signalements"]), "config.toml absent : dit")
    (i / "config.toml").write_bytes(b'proprietaire = "\xff\xfe"\n'); d7 = R.donnees(i, maison)
    dire(d7["lisible"] is False and any("invalide" in x["quoi"] for x in d7["signalements"]), "config.toml qui n'est pas de l'UTF-8 : dit invalide")
    sys.modules.pop("noyau.reglages", None)
    CONFIG_MARQUEE = "\n".join(lignes) + "\n"

# ── 1 bis. renvoi n° 177 (relecture Codex) : les quatre fuites, et le dernier passage qui refuse ──
def pem(genre):
    corps = "".join(random.choice(string.ascii_letters) for _ in range(64))
    return f"-----BEGIN {genre}-----\n{corps}\n{corps[::-1]}\n-----END {genre}-----"


with tempfile.TemporaryDirectory() as t:
    t = Path(t); i = t / "berger"; maison = t / "maison"; (i / "courtier/outils").mkdir(parents=True); maison.mkdir()
    shutil.copy2(SRC / "courtier/outils/ssh.py", i / "courtier/outils/ssh.py")
    M = {n: marqueur() for n in ("env_cle", "env_pass", "env_libelle", "env_ligne", "hote", "coffre", "marque", "nom_ip", "pem_cle", "pem_cert", "url_interne")}
    pem_cle, pem_cert = pem("OPENSSH PRIVATE KEY"), pem("CERTIFICATE")
    coffre = f"/srv/{M['coffre']}/coffre.json"
    ip_nom = "192.0.2.77"
    (i / "config.toml").write_text("\n".join([
        'proprietaire = "Proprio"', f"coffre = {toml(coffre)}", f"marques_privees = [{toml(M['marque'])}]",
        f"note_anodine = {toml(pem_cle)}", f"autre_note = {toml(pem_cert)}", f"URLInterne = {toml(M['url_interne'])}",
        "[outils.serveur]", 'type = "ssh"', f"hote = {toml(M['hote'])}",
        f'[outils."{ip_nom}"]', 'type = "ssh"',
        f"[outils.{M['marque']}]", 'type = "absent"',
        f"[equipes.{M['marque']}-equipe]", f"depot = {toml(str(t / 'absent'))}",
        "[mcp.erp]", f"commande = {toml('ssh ' + M['hote'] + ' uptime --coffre ' + coffre)}",
        "[mcp.erp.env]", f"DOLAPIKEY = {toml(M['env_cle'])}", f"PGPASSWORD = {toml(M['env_pass'])}", f"LIBELLE = {toml(M['env_libelle'])}",
        "[mcp.autre]", f"env = {{ ZONE = {toml(M['env_ligne'])} }}",
        "[[gardes]]", f"commande = {toml('cat ' + coffre.replace('/coffre.json', '') + '/coffre.json')}",
    ]) + "\n")
    try: d = R.donnees(i, maison); erreur = None
    except Exception as e: d = {}; erreur = f"{type(e).__name__}: {e}"
    corps = json.dumps(d, ensure_ascii=False)
    dire(erreur is None and d.get("lisible") is True, f"renvoi n° 177 : un config.toml d'essai aux quatre fuites se lit ({erreur or 'lisible'})")
    regl = {(s["nom"], c["titre"], r["cle"]): r for s in d.get("sections", []) for c in s["cartes"] for r in c["reglages"]}
    # 1. env des tables mcp : toute valeur masquée, les noms seuls visibles ; camelCase à sigles
    env = {k: r for k, r in regl.items() if k[0] == "mcp" and "env" in k[2].split(".")}
    dire(not [n for n in ("env_cle", "env_pass", "env_libelle", "env_ligne") if M[n] in corps],
         "1. [mcp.<n>.env] : aucune valeur ne sort (DOLAPIKEY, PGPASSWORD, et même une variable au nom anodin, en table ou en ligne)")
    dire({("mcp", "erp", "env.DOLAPIKEY"), ("mcp", "erp", "env.PGPASSWORD"), ("mcp", "erp", "env.LIBELLE")} <= set(env) and all(r["valeur"] == "[masqué]" for r in env.values()),
         f"1. env : le NOM de chaque variable s'affiche, sa valeur « [masqué] » ({sorted(k[2] for k in env)})")
    dire(R.mots("APIToken") == ["api", "token"] and R.mots("URLInterne") == ["url", "interne"] and R.cle_sensible("APIToken") and R.cle_sensible("URLInterne")
         and M["url_interne"] not in corps, f"1. camelCase à sigles : APIToken → api, token ; URLInterne → url, interne ({R.mots('APIToken')}, {R.mots('URLInterne')})")
    # 2. une valeur masquée réutilisée ailleurs
    dire(M["hote"] not in corps and M["coffre"] not in corps,
         "2. une valeur masquée (hôte, chemin du coffre) ne ressort pas où elle est réutilisée (mcp.*.commande « ssh <hôte> uptime », garde)")
    dire(regl.get(("mcp", "erp", "commande"), {}).get("valeur", "").startswith("ssh [masqué] uptime"),
         f"2. elle y devient « [masqué] », le reste de la commande lisible ({regl.get(('mcp', 'erp', 'commande'), {}).get('valeur')})")
    # 3. noms de tables, clés et signalements filtrés aussi
    dire(ip_nom not in corps, "3. une adresse IP en nom de table (outil) ne sort ni en titre, ni en clé, ni en signalement")
    dire(M["marque"] not in corps, "3. une marque privée en nom d'outil ou d'équipe ne sort nulle part (titres, signalements)")
    sig = " | ".join(x["quoi"] for x in d.get("signalements", []))
    dire("[masqué]" in sig, f"3. le signalement nomme l'outil masqué « [masqué] » ({sig[:160]})")
    # 4. bloc PEM sous un nom anodin
    dire("BEGIN" not in corps and pem_cle[40:60] not in corps and pem_cert[40:60] not in corps and regl.get(("", None, "note_anodine"), {}).get("valeur") == "[masqué]",
         "4. un bloc « -----BEGIN … PRIVATE KEY----- » (et tout bloc PEM) sous un nom anodin est masqué")
    # le dernier passage refuse de répondre s'il reste une valeur masquée ou un motif de clé
    filtre = getattr(R, "filtrer", None)
    if filtre is None: dire(False, "dernier passage : R.filtrer existe (le filtre de toute la réponse)")
    else:
        R.filtrer = lambda x, *a, **k: x                                   # un filtre en panne : le dernier passage doit refuser
        try: R.donnees(i, maison); refus = None
        except Exception as e: refus = e
        finally: R.filtrer = filtre
        dire(isinstance(refus, getattr(R, "Fuite", ())), f"dernier passage : filtre en panne → refus (Fuite), rien n'est rendu ({type(refus).__name__})")
        reste = getattr(R, "motif_restant", lambda x: False)
        srv_code = (SRC / "bin/interface.py").read_text()
        dire("REGLAGES.motif_restant(corps" in srv_code and "Fuite" in srv_code, "dernier passage aussi dans le serveur, sur le corps exact qui part (500 sans détail sinon)")
        dire(reste("x " + pem("RSA PRIVATE KEY")) and reste("note " + forme_de_cle()) and not reste('{"valeur": "[masqué]"}'),
             "dernier passage : un bloc PEM ou une forme de clé dans le JSON est repéré ; « [masqué] » non")
    sys.modules.pop("noyau.reglages", None)
    import noyau.reglages as R


# ── 1 ter. relecture Codex de la n° 178 : cas limites (valeur courte, casse d'un titre, marque courte, constante du catalogue, [env] racine) ──
def court():
    """Deux lettres au hasard (sans chiffre ni signe) : une valeur sensible courte, absente des textes du code."""
    while True:
        v = random.choice(string.ascii_uppercase) + random.choice("qxzjvw")
        if not re.search(rf"(?<!\w){v}(?!\w)", " ".join(R.constantes() if hasattr(R, "constantes") else ()), re.I): return v


def mot_entier(v, texte):
    return re.search(rf"(?<!\w){re.escape(v)}(?!\w)", texte, re.I) is not None


with tempfile.TemporaryDirectory() as t:
    t = Path(t); i = t / "berger"; maison = t / "maison"; (i / "courtier/outils").mkdir(parents=True); maison.mkdir()
    shutil.copy2(SRC / "courtier/outils/ssh.py", i / "courtier/outils/ssh.py")
    hote_court, marque_courte = court().lower(), court()
    while marque_courte.lower() == hote_court: marque_courte = court()
    hote_long = marqueur() + "-fictif.invalid"
    m_env = marqueur()
    (i / "config.toml").write_text("\n".join([
        'proprietaire = "Proprio"', f"marques_privees = [{toml(marque_courte)}]",
        'password = "Conversation"', 'note = "Conversation"',
        f"mention = {toml('chez ' + marque_courte + ' demain')}",
        "[outils.serveur]", 'type = "ssh"', f"hote = {toml(hote_court)}", f"lecture = {{ etat = {toml('ssh ' + hote_court + ' uptime')} }}",
        "[outils.autre]", 'type = "ssh"', f"hote = {toml(hote_long)}",
        f"[{toml(hote_long)}]", 'libelle = "un titre de section"',
        "[env]", f"JETON_FACTICE = {toml(m_env)}", f"LIBELLE = {toml(m_env + 'b')}",
    ]) + "\n")
    try: d = R.donnees(i, maison); erreur = None
    except Exception as e: d = {}; erreur = f"{type(e).__name__}: {e}"
    corps = json.dumps(d, ensure_ascii=False)
    dire(erreur is None and d.get("lisible") is True, f"n° 178 : un config.toml d'essai aux cas limites se lit ({erreur or 'lisible'})")
    regl = {(s["nom"], c["titre"], r["cle"]): r for s in d.get("sections", []) for c in s["cartes"] for r in c["reglages"]}
    # (a) une valeur masquée de moins de 3 caractères, réutilisée comme mot entier
    etat = regl.get(("outils", "serveur", "lecture.etat"), {}).get("valeur", "")
    dire(not mot_entier(hote_court, corps) and etat == "ssh [masqué] uptime",
         f"(a) une valeur masquée courte (hôte de deux lettres) ne ressort pas en mot entier ailleurs (« {etat} »)")
    # (b) un titre de section mis en forme (capitale) à partir d'un nom d'hôte masqué
    dire(hote_long.lower() not in corps.lower(), "(b) un nom d'hôte masqué ne ressort pas dans un titre de section mis en forme (capitale)")
    # (c) une marque privée de moins de 3 caractères
    dire(not mot_entier(marque_courte, corps) and regl.get(("", None, "mention"), {}).get("masque") is True,
         f"(c) une marque privée courte n'est pas ignorée (mention : {regl.get(('', None, 'mention'), {}).get('valeur')})")
    # (d) une valeur égale à une constante du catalogue : l'exemption tient à l'ORIGINE du texte, pas au texte
    dire(regl.get(("", None, "password"), {}).get("valeur") == "[masqué]" and regl.get(("", None, "note"), {}).get("valeur") == "[masqué]",
         f"(d) une valeur masquée égale à un texte du catalogue (« Conversation ») est masquée aussi là où elle est réutilisée "
         f"(note : {regl.get(('', None, 'note'), {}).get('valeur')})")
    dire("Ton nom, tel que les agents le voient." in corps, "(d) les textes du catalogue eux-mêmes restent lisibles")
    # (e) une table [env] à la racine
    env = {k: r for k, r in regl.items() if k[0] == "env"}
    dire(m_env not in corps and env and all(r["valeur"] == "[masqué]" for r in env.values()) and any(k[2].endswith("LIBELLE") for k in env),
         f"(e) une table [env] à la racine : toute valeur masquée, les noms seuls visibles ({sorted(k[2] for k in env)})")
    sys.modules.pop("noyau.reglages", None)
    import noyau.reglages as R


# ── 5 et 6. le serveur et la vue, dans une installation jetable ──
with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t, marquages=True)
    env = {k: v for k, v in env.items() if k != "BERGER_AGENT"}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=120)
    base = (i / "config.toml").read_text()
    m = {"cle_api": marqueur(), "entete_appelant": marqueur(), "masque_fichier": marqueur(), "url_webhook": marqueur(), "api_token": marqueur()}
    m_outil = {"hote": marqueur(), "cle": marqueur(), "cle_fichier": marqueur(), "utilisateur_cle": marqueur(), "ip_secours": marqueur()}
    m_valeur = marqueur(); m_web = marqueur(); m_adresse = marqueur()
    tete = "\n".join(f"{k} = {toml(v)}" for k, v in m.items()) + f"\nnote_libre = {toml(forme_de_cle() + m_valeur)}\n"
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    queue = ("\n[outils.secretaire]\ntype = \"ssh\"\n" + "\n".join(f"{k} = {toml(v)}" for k, v in m_outil.items()) +
             f"\n[web]\nchemins_bloques = [{toml(m_web)}]\n[mcp.navigateur]\nurl = {toml('https://' + m_adresse + '.invalid/')}\n"
             f"[interface]\nport = {port}\n")
    # le jeu finit par [[gardes]] : les clés racine vont EN TÊTE, les tables neuves à la fin
    (i / "config.toml").write_text(tete + base + queue)
    tous = list(m.values()) + list(m_outil.values()) + [m_valeur, m_web, m_adresse]

    # 6. la vue en ligne de commande
    r = b("vue", "reglages", "--json"); rt = b("vue", "reglages")
    try: dv = json.loads(r.stdout)
    except ValueError: dv = {}
    dire(r.returncode == 0 and dv.get("vue") == "reglages" and dv.get("donnees", {}).get("lisible") is True, f"berger vue reglages --json : les réglages ({(r.stderr or '')[-200:]})")
    dire(not [x for x in tous if x in r.stdout + r.stderr + rt.stdout + rt.stderr], "berger vue reglages (texte et --json) : aucun marqueur")
    dire(rt.returncode == 0 and "Ces réglages se changent dans ~/berger/config.toml" in rt.stdout and "[masqué]" in rt.stdout, "le texte de la vue : l'en-tête et « [masqué] »")
    vues = json.loads(b("vues", "--json").stdout or "{}").get("vues", [])
    v = next((x for x in vues if x["type"] == "reglages"), None)
    dire(v is not None and v["onglet"] == "berger" and v["titre"] == "Réglages" and v["icone"] == "reglages", f"la vue Réglages est un onglet de la page web, avec son icône ({v})")
    pb = J.executer(i, env, 'print(json.dumps({"panneaux": list(g["PANNEAUX_BERGER"]), "onglets": [x[0] for x in g["ONGLETS_BERGER"]]}, ensure_ascii=False))')
    dire("Réglages" not in pb["panneaux"] and "Réglages" not in pb["onglets"] and "Coulisses" in pb["panneaux"],
         f"aucun onglet Réglages dans l'espace Herdr : web seulement ({pb['panneaux']})")

    # 5. le serveur
    lien = b("interface", "lien").stdout.strip(); jeton = lien.partition("#jeton=")[2]
    srv = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        for _ in range(100):
            try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
            except OSError: time.sleep(0.1)
        def req(methode, chemin, cookie=None, corps=None, hote=None, entetes=()):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=30); c.putrequest(methode, chemin, skip_host=True, skip_accept_encoding=True)
            c.putheader("Host", hote or f"localhost:{port}")
            if cookie: c.putheader("Cookie", cookie)
            for k, x in entetes: c.putheader(k, x)
            if corps is not None: c.putheader("Content-Type", "application/json"); c.putheader("Content-Length", str(len(corps)))
            c.endheaders(corps)
            r = c.getresponse(); return r.status, r.getheaders(), r.read()
        st, h, _ = req("POST", "/connexion", corps=json.dumps({"jeton": jeton}).encode())
        cookie = next((x for k, x in h if k.lower() == "set-cookie"), "").split(";")[0]
        dire(st == 204 and cookie, "connexion : une session")
        st, _, _ = req("GET", "/api/vue/reglages")
        dire(st == 401, f"sans session : 401 ({st})")
        st, _, _ = req("GET", "/api/vue/reglages", cookie, hote="ailleurs.invalid")
        dire(st == 403, f"Host étranger : 403 ({st})")
        st, h, c = req("GET", "/api/vue/reglages", cookie)
        brut = "\n".join(f"{k}: {x}" for k, x in h) + "\n" + c.decode("utf-8", "replace")
        try: dd = json.loads(c)
        except ValueError: dd = {}
        dire(st == 200 and dd.get("vue") == "reglages" and dd.get("donnees", {}).get("lisible") is True, f"GET /api/vue/reglages : 200, les réglages ({st})")
        sortis = [x for x in tous if x in brut]
        dire(not sortis, f"réponse HTTP complète (en-têtes et corps) : aucun des {len(tous)} marqueurs ({len(sortis)} sortis)")
        dire("[masqué]" in brut and str(i.parent) not in brut, "les valeurs masquées s'affichent « [masqué] » ; aucun chemin de l'installation jetable")
        hd = {k: x for k, x in h}
        dire(hd.get("Content-Security-Policy", "").startswith("default-src 'self'; script-src 'self'") and hd.get("Cache-Control") == "no-store"
             and hd.get("X-Frame-Options") == "DENY", "mêmes en-têtes stricts que les autres vues (CSP inchangée, pas de cache)")
        dire(dd.get("donnees") == json.loads(b("vue", "reglages", "--json").stdout or "{}").get("donnees"), "le serveur et `berger vue reglages --json` rendent les mêmes données")
        for meth in ("POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
            st, h, _ = req(meth, "/api/vue/reglages", cookie, corps=b"{}" if meth in ("POST", "PUT", "PATCH") else None,
                           entetes=[("Origin", f"http://localhost:{port}")])
            dire(st == 405 and dict(h).get("Allow") == "GET", f"{meth} /api/vue/reglages : 405, Allow: GET ({st})")
        # config.toml rendu invalide pendant que le serveur tourne : la page le dit, sans son contenu
        m_inv = marqueur()
        (i / "config.toml").write_text(f'cle = "{m_inv}"\n[interface\nport = {port}\n')
        st, h, c = req("GET", "/api/vue/reglages", cookie)
        try: di = json.loads(c)["donnees"]
        except (ValueError, KeyError): di = {}
        dire(st == 200 and di.get("lisible") is False and any("invalide" in x["quoi"] for x in di.get("signalements", [])) and m_inv.encode() not in c,
             f"config.toml devenu invalide : la page le dit (200, lisible = non), sans son contenu ({st})")
        (i / "config.toml").write_text(tete + base + queue)
    finally:
        srv.terminate()
        try: _, journal = srv.communicate(timeout=10)
        except subprocess.TimeoutExpired: srv.kill(); _, journal = srv.communicate()
    dire(not [x for x in tous + [m_inv] if x in journal] and "GET /api/vue/reglages 200" in journal,
         f"journal du serveur : la requête (méthode, chemin, code), aucun marqueur ({journal.count(chr(10))} lignes)")

    # 7. le navigateur
    module = os.environ.get("BERGER_PLAYWRIGHT") or next((p for p in ("playwright", "playwright-core") if shutil.which("node") and subprocess.run(
        ["node", "-e", f"require.resolve('{p}')"], capture_output=True).returncode == 0), None)
    if not module or not shutil.which("node"):
        print("NON JOUÉ navigateur réel (Réglages à 390, 820, 1280, 1440, 1920 px, 2 thèmes) : Playwright absent de cette machine")
    else:
        (i / "docs/assets").mkdir(parents=True, exist_ok=True); shutil.copy2(SRC / "docs/assets/berger.png", i / "docs/assets/berger.png")
        srv = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
                except OSError: time.sleep(0.1)
            r = subprocess.run(["node", str(SRC / "tests/_page_reglages.js"), lien, ",".join(tous)], env={**os.environ, "BERGER_PLAYWRIGHT": module},
                               capture_output=True, text=True, timeout=900)
            try: res = json.loads(r.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError): res = {"#lancement": "ERREUR " + (r.stderr or r.stdout)[-400:]}
            if str(res.get("#lancement", "")).startswith("NON JOUÉ"): print(res["#lancement"])
            else:
                dire(len(res) >= 10 and "#exécution" not in res and "#lancement" not in res, f"navigateur : {len(res)} mesures jouées ({res.get('#exécution', res.get('#lancement', 'sans erreur'))})")
                for k, x in res.items():
                    if not k.startswith("#"): dire(x == "ok", f"navigateur : {k} ({x})")
        finally:
            srv.terminate(); srv.wait(timeout=10)

# ── la page : aucun champ ni bouton qui modifie, l'en-tête ──
app = (SRC / "bin/page/app.js").read_text(); src = json.loads((SRC / "bin/page/icones.json").read_text())
f = re.search(r"\nfunction reglages\(d\) \{.*?\n\}\nfunction listeReglages\(l\) \{.*?\n\}\n", app, re.S)
code = f.group(0) if f else ""
dire(bool(f) and not re.search(r'"(input|textarea|select|form|button)"|bouton\(|data-geste|fetch\(|method', code),
     "app.js : le rendu des Réglages n'a ni champ, ni bouton, ni requête (lecture seule)")
dire(re.search(r"reglages: \{ rendre: d => reglages\(d\), fixe: true \}", app) is not None, "app.js : la vue Réglages, relue à chaque ouverture de l'onglet (pas en direct)")
dire(src["libelles"].get("reglages_ou") == "Ces réglages se changent dans" and "L(\"reglages_ou\")" in code and "d.fichier" in code,
     "en tête de page : « Ces réglages se changent dans ~/berger/config.toml » (le chemin vient du serveur, tel quel)")
dire(src["onglets"].get("Réglages", {}).get("icone") == "reglages" and "reglages" in src["icones"], "icones.json : l'onglet Réglages et son icône (source commune)")
srv_code = (SRC / "bin/interface.py").read_text()
dire('ROUTE_REGLAGES = "/api/vue/reglages"' in srv_code and "do_OPTIONS" in srv_code, "bin/interface.py : la route des réglages, GET seulement")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
