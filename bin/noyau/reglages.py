"""La page « Réglages » de l'interface web, en LECTURE SEULE (spec docs/plans/2026-11-05-interface-reglages-spec.md, go n° 169).

Le lecteur de config.toml, son catalogue (une phrase simple par réglage connu) et le MASQUAGE, décidé ici, côté serveur, AVANT toute
sérialisation : une valeur masquée devient « [masqué] » dans les données mêmes ; elle n'atteint jamais la réponse HTTP, le journal ni la page.

Autonome (bibliothèque standard seulement, aucun autre module du noyau) : le serveur de l'interface (bin/interface.py) l'appelle EN DIRECT,
à chaque ouverture de l'onglet, et peut donc dire qu'un config.toml est invalide même quand `berger` ne démarre plus ; la vue `reglages`
(berger vue reglages --json) rend les mêmes données par l'API du noyau (reglages_donnees).

Ce qui est masqué :
  1. une liste FERMÉE de clés, quelle que soit la section (CLES_MASQUEES), plus quelques clés d'une section précise (CLES_SECTION) ;
  2. toute clé dont un MOT ENTIER du nom (segments séparés par « _ », « - », « . » ou une majuscule) est sensible (MOTS_SENSIBLES) :
     « ip » masque ip_secours, jamais description, principale ni equipe ; « cle » masque cle_api, jamais cycle ni boucle ;
  3. toute valeur restante qui a une forme de clé (MOTIFS_CLES de courtier/_secrets.py, la définition unique), une adresse (schéma
     « xxx:// », adresse IP, utilisateur@hôte) ou l'une des marques privées déclarées (marques_privees) ;
  4. une liste dont UN élément est masqué l'est en entier ; une table est parcourue clé par clé (une clé sensible masque toute sa table).
Le coffre n'est JAMAIS lu, ni même regardé (ni ouverture, ni stat) : aucun chemin de son dossier n'est examiné.
Le dossier personnel est écrit « ~ » dans toute valeur montrée."""
import importlib.util, ipaddress, json, os, re, tomllib, unicodedata
from pathlib import Path

ICI = Path(__file__).resolve().parent                                      # bin/noyau


class Public(str):
    """Un texte du CODE (catalogue, titres connus, en-tête) : public par son ORIGINE, ni filtré ni contrôlé. Une valeur de config.toml
    égale à l'un d'eux reste une simple chaîne, filtrée comme les autres (relecture de la n° 178)."""
    __slots__ = ()


MASQUE = Public("[masqué]")
FICHIER_MONTRE = Public("~/berger/config.toml")                            # le seul chemin montré, tel quel (spec)
PHRASE_ENV = Public("Une variable d'environnement (sa valeur n'est jamais montrée).")
COFFRE_DEFAUT = "~/.config/berger/coffre.json"

CLES_MASQUEES = frozenset({"coffre", "cle", "cle_fichier", "utilisateur_cle", "mot_de_passe_cle", "port_cle", "hote", "hotes", "ip_secours", "webdav",
                           "adresse", "sources", "marques_privees", "masques", "masques_si_presents", "masque_fichier", "chemins_bloques",
                           "entete_appelant", "depot_public", "utilisateur", "base"})
CLES_SECTION = {("interface", "nom")}                                      # le nom interne derrière le mandataire : un hôte
MOTS_SENSIBLES = frozenset({"cle", "cles", "secret", "secrets", "jeton", "jetons", "token", "tokens", "pass", "password", "passwd", "passphrase",
                            "hote", "hotes", "host", "hosts", "ip", "ips", "url", "urls", "uri", "dsn", "apikey"})
SUITES_SENSIBLES = (("mot", "de", "passe"), ("api", "key"))                # des mots qui ne sont sensibles qu'ensemble
ADRESSE = re.compile(r"[a-z][a-z0-9+.-]*://|[\w.+-]+@[\w-]+(\.[\w-]+)*", re.I)
IP4 = re.compile(r"(?<![\d.])(\d{1,3}\.){3}\d{1,3}(?![\d.])")
IP6 = re.compile(r"(?<![\w:])([0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![\w:])", re.I)
PEM = re.compile(r"-----BEGIN [A-Z0-9 ]+-----")                          # tout bloc PEM (clé privée, certificat…), même sous un nom anodin
PEM_BLOC = re.compile(r"-----BEGIN [A-Z0-9 ]+-----.*?(?:-----END [A-Z0-9 ]+-----|\Z)", re.S)
URL_ENTIERE = re.compile(r"[a-z][a-z0-9+.-]*://\S*", re.I)
AROBASE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)*")
RETENUE_MIN = 3                                                           # plus courte, une valeur masquée n'est cherchée qu'en MOT ENTIER
_MOTIFS = None


class Fuite(Exception):
    """Le dernier passage a trouvé une valeur masquée ou un motif de clé dans la réponse : rien n'est rendu."""


def motifs_cles():
    """MOTIFS_CLES de courtier/_secrets.py (jamais recopié), chargé une fois depuis le code de Berger."""
    global _MOTIFS
    if _MOTIFS is None:
        sp = importlib.util.spec_from_file_location("berger_secrets_reglages", ICI.parents[1] / "courtier/_secrets.py")
        m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); _MOTIFS = m.MOTIFS_CLES
    return _MOTIFS


def mots(nom):
    """Les mots entiers d'un nom de clé : sans accent, en minuscules, coupés aux « _ », « - », « . », blancs et majuscules (apiToken)."""
    t = unicodedata.normalize("NFKD", str(nom)); t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", t)
    t = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", t)                       # sigles : APIToken → API_Token, URLInterne → URL_Interne
    return [m for m in re.split(r"[^A-Za-z0-9]+", t.lower()) if m]


def cle_sensible(nom, section=None):
    """Une clé dont la VALEUR est masquée : liste fermée, clé d'une section précise, ou un mot entier sensible."""
    m = mots(nom)
    if "_".join(m) in CLES_MASQUEES or (section, "_".join(m)) in CLES_SECTION: return True
    if any(x in MOTS_SENSIBLES for x in m): return True
    return any(tuple(m[i:i + len(s)]) == s for s in SUITES_SENSIBLES for i in range(len(m)))


def est_env(nom):
    """Une table d'environnement (`env` d'un serveur MCP, ou d'ailleurs) : TOUTES ses valeurs sont masquées, seuls les noms se montrent."""
    return mots(nom) == ["env"]


def motif_valeur(v):
    """Comment chercher une valeur masquée (ou une marque privée) dans un texte : sans tenir compte de la casse ; en mot entier si elle a
    moins de RETENUE_MIN caractères (« db » dans « ssh db uptime », jamais dans « dbus »), n'importe où sinon."""
    e = re.escape(v)
    return re.compile(rf"(?<!\w){e}(?!\w)" if len(v) < RETENUE_MIN else e, re.I)


def valeur_sensible(t, marques=()):
    """Une valeur texte à masquer : forme de clé (MOTIFS_CLES), bloc PEM, adresse (schéma, IP, utilisateur@hôte), marque privée déclarée."""
    t = str(t)
    if motifs_cles().search(t) or PEM.search(t) or ADRESSE.search(t) or IP4.search(t): return True
    for x in IP6.finditer(t):
        try: ipaddress.ip_address(x.group(0)); return True
        except ValueError: pass
    return any(motif_valeur(m).search(t) for m in marques if m)


class Lecteur:
    """Un passage : les marques privées (pour le masquage) et le dossier personnel (écrit « ~ »)."""

    def __init__(self, marques, maison):
        self.marques = tuple(m for m in marques if isinstance(m, str) and m.strip()); self.maison = str(maison)
        self.retenues = set(); self._motifs = (None, ())                                             # chaque valeur masquée : recherchée ensuite dans TOUTE la réponse

    def retenir(self, v):
        """Retient une valeur masquée (et tout ce qu'elle contient), sous ses formes montrables : telle quelle, « ~/… », chemin développé."""
        if isinstance(v, dict):
            for x in v.values(): self.retenir(x)
        elif isinstance(v, list):
            for x in v: self.retenir(x)
        elif isinstance(v, (str, int, float)) and not isinstance(v, bool):
            t = str(v).strip()
            formes = {t}
            if self.maison and len(self.maison) > 1: formes.add(t.replace(self.maison, "~"))
            if t.startswith("~"): formes.add(os.path.expanduser(t)); formes.add(t.replace("~", self.maison, 1))
            self.retenues |= {f for f in formes if f and f != "~" and f != self.maison}   # même courte (en mot entier) ; le « ~ » se montre

    def motifs(self):
        """Les motifs des valeurs retenues (les plus longues d'abord), recalculés seulement si elles ont changé."""
        cle = frozenset(self.retenues)
        if self._motifs[0] != cle: self._motifs = (cle, tuple(motif_valeur(r) for r in sorted(cle, key=len, reverse=True)))
        return self._motifs[1]

    def texte(self, v):
        """→ (texte montré, masqué ?) d'une valeur simple."""
        if isinstance(v, bool): return ("oui" if v else "non"), False
        if isinstance(v, (int, float)): return str(v), False
        t = str(v)
        if valeur_sensible(t, self.marques): self.retenir(t); return MASQUE, True
        if self.maison and len(self.maison) > 1: t = t.replace(self.maison, "~")
        return (t if t.strip() else "(vide)"), False

    def valeur(self, v):
        """→ (texte montré, masqué ?) : une liste masquée si UN élément l'est ; une table en ligne (liste de tables) parcourue clé par clé."""
        if isinstance(v, list):
            parts = []
            for x in v:
                t, m = self.valeur(x)
                if m: self.retenir(v); return MASQUE, True
                parts.append(t)
            return (", ".join(parts) if parts else "(liste vide)"), False
        if isinstance(v, dict):
            parts = []
            for k, x in v.items():
                if cle_sensible(k) or est_env(k): self.retenir(v); return MASQUE, True
                t, m = self.valeur(x)
                if m: self.retenir(v); return MASQUE, True
                parts.append(f"{k} = {t}")
            return "{" + ", ".join(parts) + "}", False
        return self.texte(v)

    def reglages(self, section, table, prefixe=""):
        """Les réglages d'une carte, une table imbriquée parcourue (clés pointées) ; une clé sensible masque toute sa valeur."""
        out = []
        for k, v in table.items():
            cle = prefixe + str(k)
            if est_env(k) and isinstance(v, dict):                         # les NOMS des variables, jamais leurs valeurs
                self.retenir(v)
                out += [{"cle": f"{cle}.{n}", "valeur": MASQUE, "masque": True, "phrase": PHRASE_ENV}
                        for n in v]
            elif cle_sensible(k, section if not prefixe else None) or est_env(k):
                self.retenir(v)
                out.append({"cle": cle, "valeur": MASQUE, "masque": True, "phrase": phrase(section, cle)})
            elif isinstance(v, dict) and v:
                out += self.reglages(section, v, cle + ".")
            else:
                t, m = self.valeur(v)
                out.append({"cle": cle, "valeur": t, "masque": m, "phrase": phrase(section, cle)})
        return out


# ─── Le catalogue : une phrase simple par réglage connu (sinon « réglage non décrit ») ───
NON_DECRIT = Public("réglage non décrit")
SECTIONS = {
    "": ("Propriétaire et généralités", "Qui tu es pour les agents, et les protections de base de l'installation."),
    "interface": ("Interface", "Cette page web : où elle écoute, qui peut l'ouvrir, ce qu'on peut y faire."),
    "conversation": ("Conversation", "Les agents à qui tu peux écrire depuis la page web."),
    "equipes": ("Équipes", "Les équipes de développement : dépôt, branches, portes, qui valide."),
    "outils": ("Outils", "Les outils du courtier : ce que les agents peuvent lire ou demander, sans jamais voir les clés."),
    "panneaux": ("Panneaux", "Les panneaux de sources : ce que le courtier relève à intervalle régulier."),
    "missions": ("Missions", "Les missions confiées entre agents."),
    "modeles": ("Modèles", "Les modèles permis par moteur et par niveau de travail."),
    "skills": ("Skills", "Le catalogue des méthodes données aux agents selon leur rôle."),
    "mcp": ("MCP", "Les serveurs d'outils (MCP) branchés sur les agents."),
    "tests": ("Tests", "L'auto-test de l'installation."),
    "gardes": ("Gardes", "Les commandes lancées avant ou après chaque outil d'un agent (code 2 = refus)."),
    "sauvegarde": ("Sauvegarde", "La sauvegarde chiffrée des données de Berger."),
    "coffre_sauvegarde": ("Sauvegarde du coffre", "La copie chiffrée du coffre avant de le modifier."),
    "bibliotheque": ("Bibliothèque", "Les dossiers de travail des agents et le dossier commun."),
    "checklists": ("Checklists", "Le dossier des listes cochables affichées dans Berger."),
    "courtier": ("Courtier", "Les garde-fous du courtier de secrets."),
    "relance": ("Relance", "Quand un agent en boucle peut être relancé."),
    "annonces": ("Annonces", "L'annonce aux agents d'un outil qui change."),
    "besoins": ("Besoins", "Les besoins que les agents adressent au gardien de Berger."),
    "web": ("Accès web", "L'accès web d'un agent à un domaine, et la connexion visible du propriétaire."),
    "wiki": ("Wiki", "Les outils du wiki pour l'alignement après une mise en production."),
    "supervision": ("Supervision", "La relance automatique et l'escalade quand un travail n'avance plus."),
    "espaces": ("Espaces", "Les panneaux de l'espace de chaque agent dans Herdr."),
}
PHRASES = {
    "": {"proprietaire": "Ton nom, tel que les agents le voient.", "fuseau": "Le fuseau horaire de l'installation.",
         "icone_berger": "L'icône de l'espace de pilotage dans Herdr.", "coffre": "Le fichier du coffre de secrets (seul le courtier le lit).",
         "masques": "Les dossiers rendus illisibles à tous les agents.", "masques_si_presents": "Les dossiers masqués seulement s'ils existent.",
         "masque_fichier": "Le fichier isolé masqué à Codex.", "codex_identifiants": "Où Codex garde ses identifiants (trousseau ou fichier).",
         "marques_privees": "Les mentions propres à ton installation, refusées dans le dépôt.", "depot_public": "L'adresse du dépôt public.",
         "entete_appelant": "L'en-tête qui nomme l'agent appelant auprès d'une passerelle.", "pied_codex": "La ligne d'état de Codex.",
         "codex_modele_strict": "Le modèle imposé aux agents stricts sous Codex.", "lecteur_fichiers": "Le lecteur de fichiers de Herdr."},
    "interface": {"port": "Le port de cette page.", "adresse": "L'adresse où la page écoute.", "nom": "Le nom de la page derrière le mandataire.",
                  "sources": "Les adresses admises à ouvrir la page.", "tls": "Le chiffrement jusqu'à la machine.",
                  "actions": "Les gestes depuis la page (valider, refuser, répondre, marquer lu, écrire à un agent).",
                  "transcription": "Le programme local qui transcrit le micro.", "transcription_delai": "Le temps laissé à la transcription (secondes)."},
    "conversation": {"agents": "Les agents qui ont une page « Conversation »."},
    "equipes": {"lecture": "Une commande en plus pour le développeur, dans sa copie.", "modules": "Un module du projet et ce qu'il faut relire.",
                "depot": "Le dépôt du chef de projet.", "principale": "La branche principale.", "copies": "Où sont créées les copies des développeurs.",
                "prefixe": "Le début du nom des branches des développeurs.", "chef_projet": "L'agent chef de projet.",
                "coordinateur": "L'agent qui confie les sujets et suit le chef.", "fusion_par": "Qui valide les fusions.",
                "projet_par": "Qui valide l'ouverture d'un projet.", "copie_chef": "La copie de travail du chef.",
                "verify": "La porte rapide (vérification).", "tests": "La porte des tests complets.", "pret": "La porte de finition.",
                "gate": "La porte facultative de qualité.", "doc": "La porte courte, quand seule la doc change.", "finition": "Qui passe la porte de finition.",
                "motif_tests": "Ce qui compte comme fichier de test.", "moteur": "Le moteur des développeurs.", "ports": "Un port par développeur.",
                "skills": "Les méthodes données à chaque développeur.", "memoire": "La mémoire de l'équipe.",
                "outils_developpeur": "Les outils en plus pour chaque développeur.", "installer_outil": "L'action lancée après une fusion validée.",
                "publication": "Où part le commit installé.", "regle_go": "Le contrôle du go de la règle de go.", "go_mots": "Les mots qui marquent un sujet à go.",
                "pile_creer": "La création de l'application d'un développeur.", "pile_supprimer": "La suppression de l'application d'un développeur.",
                "crochet_ecriture": "Le contrôle du projet avant chaque écriture.", "alignement": "Ce qui est tenu après une mise en production."},
    "outils": {"type": "Le genre d'outil (son fichier dans le courtier).", "port": "Le port du service.", "delai": "Le temps laissé à une commande (secondes).",
               "taille_max": "La taille maximale d'un téléchargement (Mo).", "max_lignes": "Le nombre de lignes rendues au plus.",
               "pilote": "Le pilote de la base.", "consigne": "Le verbe qui dit ce que fait l'outil.", "dossier": "Le dossier de travail de l'outil.",
               "autorises": "Les scripts permis.", "zones": "Les zones permises.", "aide": "L'aide d'un verbe.", "motif": "Ce qu'un argument doit suivre.",
               "sql": "La requête fixée.", "nom": "Le nom de l'outil vu par le service.", "parametres": "Les paramètres d'une requête.",
               "hote": "Le serveur visé.", "hotes": "Les serveurs permis.", "ip_secours": "L'adresse de secours.", "cle": "Le nom de la clé dans le coffre.",
               "cle_fichier": "Le fichier de la clé privée.", "utilisateur": "Le compte utilisé sur le serveur.", "utilisateur_cle": "Le nom de l'identifiant dans le coffre.",
               "mot_de_passe_cle": "Le nom du mot de passe dans le coffre.", "port_cle": "Le nom du port dans le coffre.", "base": "La base lue.",
               "url": "L'adresse fixée du verbe.", "lecture": "Une lecture permise, sans validation.", "actions": "Une écriture : chacune attend ta validation.",
               "verbes": "Un verbe de l'outil."},
    "panneaux": {"titre": "Le titre du panneau.", "outil": "L'outil lu.", "verbe": "Le verbe de lecture lancé.", "args": "Ses arguments.",
                 "cadence": "L'intervalle entre deux relevés (secondes).", "rouge": "Ce qui passe en rouge.", "jaune": "Ce qui passe en jaune.",
                 "max_lignes": "Les lignes affichées.", "ignorer": "Les lignes connues, jamais en couleur."},
    "missions": {"max": "Le nombre de missions en même temps.", "modeles_claude": "Les modèles Claude permis (ancienne liste).",
                 "modeles_codex": "Les modèles Codex permis (ancienne liste)."},
    "modeles": {"gros": "Les modèles du niveau « gros ».", "moyen": "Les modèles du niveau « moyen ».", "leger": "Les modèles du niveau « léger »."},
    "skills": {"dossier": "Le dossier du catalogue des méthodes.", "partager_utilisateur": "Les méthodes de ~/.claude/skills données à tous.",
               "interdits": "Ce qu'une méthode ne doit jamais contenir."},
    "tests": {"courtier_agent": "L'agent de l'appel d'essai au courtier.", "courtier_outil": "L'outil de l'appel d'essai.", "courtier_verbe": "Le verbe de l'appel d'essai."},
    "gardes": {"moment": "Avant ou après l'outil.", "outils": "Les outils concernés.", "commande": "La commande lancée.", "timeout": "Le temps laissé (secondes)."},
    "sauvegarde": {"webdav": "Le serveur de la sauvegarde.", "utilisateur_cle": "Le nom de l'identifiant dans le coffre.",
                   "mot_de_passe_cle": "Le nom du mot de passe dans le coffre.", "dossier": "Le dossier de la sauvegarde.", "garder": "Le nombre de sauvegardes gardées."},
    "coffre_sauvegarde": {"destinataire": "La clé publique de chiffrement.", "dossier": "Le dossier des copies chiffrées.", "garder_jours": "Les jours de copies gardées."},
    "bibliotheque": {"racine": "Le dossier de la bibliothèque."},
    "checklists": {"dossier": "Le dossier des listes cochables."},
    "courtier": {"boucle_max": "Le même appel refusé au-delà de ce nombre par heure (0 = éteint).", "mission_max": "La longueur maximale d'une mission.",
                 "redemarrage_attente": "L'attente avant un redémarrage du courtier (secondes).", "redemarrage_reessai": "Le délai avant un nouvel essai (secondes).",
                 "redemarrage_essais": "Le nombre d'essais."},
    "relance": {"inactif_min": "Les minutes sans sollicitation avant une relance possible."},
    "annonces": {"actif": "L'annonce d'un outil qui change.", "cadence": "L'intervalle entre deux relectures (secondes).",
                 "validation": "Chaque nouvelle version attend ton accord."},
    "besoins": {"actif": "Les besoins des agents vers le gardien."},
    "web": {"attente": "Le délai d'expiration d'une demande d'accès.", "node": "Le programme node de la connexion visible.",
            "playwright_module": "Le module Playwright de la connexion visible.", "navigateur": "Le navigateur de la connexion visible.",
            "chemins_bloques": "Les chemins refusés pendant la connexion visible."},
    "wiki": {"lecture": "L'outil de lecture du wiki.", "ecriture": "L'outil d'écriture du wiki."},
    "supervision": {"sans_avancee_min": "Les minutes sans avancée avant une relance.", "escalade_min": "Les minutes avant de te prévenir d'un blocage.",
                    "max_renvois": "Les renvois d'une demande avant de remonter la chaîne."},
    "espaces": {"auto": "L'espace de chaque agent remis en ordre de lui-même.", "a_cote": "Les panneaux à côté de l'agent.", "onglets": "Ses autres onglets."},
}


SECTIONS = {k: (Public(t), Public(p)) for k, (t, p) in SECTIONS.items()}
PHRASES = {s: {k: Public(v) for k, v in d.items()} for s, d in PHRASES.items()}


def phrase(section, cle):
    """La phrase simple d'un réglage connu du catalogue (clé exacte, puis dernier segment d'une clé pointée), sinon « réglage non décrit »."""
    p = PHRASES.get(section, {})
    return p.get(cle) or p.get(cle.rsplit(".", 1)[-1]) or ("." in cle and p.get(cle.split(".", 1)[0])) or NON_DECRIT


def titre_section(nom):
    return SECTIONS.get(nom, (nom.replace("_", " ").capitalize(), None))


# ─── Ce qui manque ou est invalide ───
def _dans(p, dossier):
    try: return p == dossier or dossier in p.parents
    except (TypeError, ValueError): return False


def signalements(c, berger, maison):
    """Ce qui manque, avec sa conséquence en clair. Aucun chemin du dossier du coffre n'est examiné (ni ouvert ni « stat »)."""
    out = []
    coffre = Path(os.path.expanduser(str(c.get("coffre") or COFFRE_DEFAUT))).parent
    def regarde(p):                                                        # un chemin qu'on a le droit de regarder : jamais près du coffre
        return not _dans(Path(os.path.abspath(p)), Path(os.path.abspath(coffre)))
    i = c.get("interface") if isinstance(c.get("interface"), dict) else {}
    t = i.get("transcription")
    if not t: out.append({"quoi": "[interface] transcription absent", "consequence": "micro grisé dans Conversation", "ton": "jaune"})
    else:
        p = Path(str(t))
        ok = isinstance(t, str) and p.is_absolute() and regarde(p) and p.is_file() and os.access(p, os.X_OK)
        if not ok: out.append({"quoi": "[interface] transcription : programme absent ou non exécutable", "consequence": "micro grisé dans Conversation", "ton": "jaune"})
    if i.get("actions") is not True:
        out.append({"quoi": "[interface] actions absent", "consequence": "décisions en lecture seule dans la page", "ton": "jaune"})
    outils = c.get("outils") if isinstance(c.get("outils"), dict) else {}
    for nom, o in outils.items():
        if not isinstance(o, dict): continue
        ty = o.get("type")
        if not isinstance(ty, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", ty) or not (berger / "courtier/outils" / f"{ty}.py").is_file():
            out.append({"quoi": f"outil « {nom} » : son fichier est absent de courtier/outils/", "consequence": "le courtier refuse cet outil", "ton": "rouge"})
    equipes = c.get("equipes") if isinstance(c.get("equipes"), dict) else {}
    for nom, e in equipes.items():
        if not isinstance(e, dict): continue
        d = e.get("depot")
        p = Path(os.path.expanduser(str(d))) if isinstance(d, str) and d else None
        if p is None or not regarde(p) or not p.is_dir() or not os.access(p, os.R_OK | os.X_OK):
            out.append({"quoi": f"équipe « {nom} » : dépôt absent ou illisible", "consequence": "l'équipe ne peut ni ouvrir de développeur ni fusionner", "ton": "rouge"})
    return out


def donnees(berger, maison=None):
    """Les données de la page : {fichier, lisible, signalements, sections}. Relu à chaque appel ; masqué AVANT de rendre quoi que ce soit."""
    berger = Path(berger); maison = Path(maison) if maison else Path.home()
    base = {"fichier": FICHIER_MONTRE, "lisible": False, "signalements": [], "sections": []}
    try: brut = (berger / "config.toml").read_bytes()
    except FileNotFoundError:
        base["signalements"] = [{"quoi": "config.toml absent", "consequence": "Berger ne démarre pas sans lui", "ton": "rouge"}]; return base
    except OSError:
        base["signalements"] = [{"quoi": "config.toml illisible", "consequence": "Berger ne démarre pas sans lui", "ton": "rouge"}]; return base
    try: c = tomllib.loads(brut.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):                 # jamais le message de l'analyseur : il pourrait citer le contenu
        base["signalements"] = [{"quoi": "config.toml invalide (pas du TOML lisible)", "consequence": "Berger ne démarre pas tant qu'il n'est pas corrigé", "ton": "rouge"}]
        return base
    marques = c.get("marques_privees") if isinstance(c.get("marques_privees"), list) else []
    lec = Lecteur(marques, maison)
    racine = {k: v for k, v in c.items() if not isinstance(v, dict) and not (isinstance(v, list) and v and all(isinstance(x, dict) for x in v))}
    sections = []
    if racine:
        t, p = titre_section("")
        sections.append({"nom": "", "titre": t, "phrase": p, "cartes": [{"titre": None, "reglages": lec.reglages("", racine)}]})
    for nom, v in c.items():
        if nom in racine: continue
        t, p = titre_section(nom)
        s = {"nom": nom, "titre": t, "phrase": p, "cartes": []}
        if est_env(nom) and isinstance(v, dict):                           # [env] à la racine : les NOMS seuls (relecture de la n° 178)
            s["cartes"].append({"titre": None, "reglages": lec.reglages(nom, {nom: v})})
        elif cle_sensible(nom) or est_env(nom):                            # une section au nom sensible : masquée en entier
            lec.retenir(v); s["cartes"].append({"titre": None, "reglages": [{"cle": nom, "valeur": MASQUE, "masque": True, "phrase": NON_DECRIT}]})
        elif isinstance(v, list):                                          # section répétée ([[gardes]]) : une carte par entrée
            for n, x in enumerate(v, 1): s["cartes"].append({"titre": f"n° {n}", "reglages": lec.reglages(nom, x, "")})
        else:
            simples = {k: x for k, x in v.items() if not isinstance(x, dict)}
            if simples: s["cartes"].append({"titre": None, "reglages": lec.reglages(nom, simples)})
            for k, x in v.items():                                         # famille ([outils.<nom>]) : une carte par entrée
                if not isinstance(x, dict): continue
                if est_env(k): s["cartes"].append({"titre": str(k), "reglages": lec.reglages(nom, {k: x})})
                elif cle_sensible(k):
                    lec.retenir(x); s["cartes"].append({"titre": str(k), "reglages": [{"cle": str(k), "valeur": MASQUE, "masque": True, "phrase": NON_DECRIT}]})
                else: s["cartes"].append({"titre": str(k), "reglages": lec.reglages(nom, x)})
        sections.append(s)
    for x in (c.get("coffre"), COFFRE_DEFAUT): lec.retenir(x) if isinstance(x, str) and x else None   # le chemin du coffre, jamais montré (jamais lu)
    base.update(lisible=True, signalements=signalements(c, berger, maison), sections=sections)
    base = filtrer(base, lec)
    controler(base, lec)
    return base


# ─── Le filtre de TOUTE la réponse, puis le dernier passage (renvoi n° 177) ───
def constantes():
    """Les textes du code (catalogue, titres connus, en-tête), tous Public : ni filtrés ni contrôlés, parce qu'ils viennent du code."""
    out = {NON_DECRIT, FICHIER_MONTRE, MASQUE, PHRASE_ENV}
    for t, p in SECTIONS.values(): out |= {t, p}
    for d in PHRASES.values(): out |= set(d.values())
    return out


def nettoyer(t, lec):
    """Un texte de la réponse (valeur, clé, titre, signalement) : chaque valeur masquée retenue, chaque bloc PEM, forme de clé, adresse,
    IP et marque privée qu'il contient devient « [masqué] » ; le reste reste lisible."""
    if lec.maison and len(lec.maison) > 1: t = t.replace(lec.maison, "~")
    for m in lec.motifs(): t = m.sub(MASQUE, t)                           # sans tenir compte de la casse (titre mis en capitale)
    t = PEM_BLOC.sub(MASQUE, t); t = motifs_cles().sub(MASQUE, t); t = URL_ENTIERE.sub(MASQUE, t); t = AROBASE.sub(MASQUE, t); t = IP4.sub(MASQUE, t)
    t = IP6.sub(lambda x: MASQUE if _ip(x.group(0)) else x.group(0), t)
    for m in lec.marques: t = motif_valeur(m).sub(MASQUE, t)
    return t


def _ip(t):
    try: ipaddress.ip_address(t); return True
    except ValueError: return False


def filtrer(d, lec):
    """Le même filtre sur TOUTE la réponse (titres, clés, valeurs, signalements), pas seulement sur les valeurs. Seuls les textes Public
    (venus du code) en sont exemptés : l'exemption tient à l'origine du texte, jamais à son contenu."""
    if isinstance(d, dict): return {k: filtrer(x, lec) for k, x in d.items()}
    if isinstance(d, list): return [filtrer(x, lec) for x in d]
    if isinstance(d, str) and not isinstance(d, Public): return nettoyer(d, lec)
    return d


def motif_restant(texte):
    """Un motif de clé (MOTIFS_CLES) ou un bloc PEM dans un texte (le JSON complet) ?"""
    return bool(motifs_cles().search(texte) or PEM.search(texte))


def controler(d, lec):
    """Le dernier passage : si une valeur masquée retenue ou un motif de clé figure encore dans la réponse, REFUS (Fuite) — rien n'est rendu.
    Il ne compare qu'aux valeurs de config.toml : le coffre n'est jamais lu."""
    motifs = lec.motifs(); pile = [d]
    while pile:
        x = pile.pop()
        if isinstance(x, dict): pile += list(x.values()); continue
        if isinstance(x, list): pile += x; continue
        if not isinstance(x, str) or isinstance(x, Public): continue
        reste = x.replace(MASQUE, "\0")
        if any(m.search(reste) for m in motifs) or motif_restant(x): raise Fuite("valeur masquée ou motif de clé dans la réponse")
    if motif_restant(json.dumps(d, ensure_ascii=False)): raise Fuite("motif de clé dans la réponse")
