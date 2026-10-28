# -*- coding: utf-8 -*-
"""Outil de type « imap » pour le courtier de Berger — messagerie en LECTURE SEULE.

Réglages (config.toml, [outils.<nom>]) : chemins dans le coffre de l'adresse (`utilisateur_cle`), du mot de passe
(`mot_de_passe_cle`), du serveur (`hote_cle`) et du port (`port_cle`) ; `dossiers` = dossiers autorisés (vide = tous).
Les dossiers sont ouverts en lecture seule (EXAMINE) et les messages lus sans être marqués comme lus (BODY.PEEK).
Aucun envoi, aucun déplacement, aucune suppression : ces verbes n'existent pas."""
import email, email.header, email.policy, imaplib, re


class Outil:
    def __init__(self, reglages, secret, verifier_hote):
        self.r = reglages; self.valeur_coffre = secret
        self.autorises = reglages.get("dossiers", [])
        self.verbes = {"dossiers": self.dossiers, "liste": self.liste, "lire": self.lire, "chercher": self.chercher}

    def hotes(self): return {}          # le mot de passe ne part que vers le serveur IMAP lu dans la même section du coffre

    def connexion(self):
        m = imaplib.IMAP4_SSL(str(self.valeur_coffre(self.r["hote_cle"])), int(self.valeur_coffre(self.r["port_cle"])), timeout=30)
        m.login(str(self.valeur_coffre(self.r["utilisateur_cle"])), str(self.valeur_coffre(self.r["mot_de_passe_cle"])))
        return m

    def ouvrir(self, m, dossier):
        if self.autorises and dossier not in self.autorises: raise PermissionError(f"dossier non autorisé : {dossier}")
        if not re.fullmatch(r"[\w .&@/-]{1,80}", dossier): raise ValueError("nom de dossier invalide")
        t, _ = m.select(f'"{dossier}"', readonly=True)
        if t != "OK": raise RuntimeError(f"dossier introuvable : {dossier}")

    @staticmethod
    def decoder(v):
        return str(email.header.make_header(email.header.decode_header(v or ""))) if v else ""

    def entetes(self, m, uids):
        out = []
        for uid in uids:
            t, d = m.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM DATE SUBJECT)])")
            if t != "OK" or not d or not d[0]: continue
            h = email.message_from_bytes(d[0][1])
            out.append({"uid": uid.decode() if isinstance(uid, bytes) else uid, "date": h.get("Date", "")[:31],
                        "de": self.decoder(h.get("From"))[:80], "objet": self.decoder(h.get("Subject"))[:150]})
        return out

    def dossiers(self, args):
        """Liste des dossiers de la boîte."""
        m = self.connexion()
        try:
            _, l = m.list()
            noms = [re.search(rb'"([^"]+)"\s*$|\s(\S+)$', x).group(1 if b'"' in x.split()[-1] else 2).decode(errors="ignore") for x in l]
            return [n for n in noms if not self.autorises or n in self.autorises]
        finally: m.logout()

    def liste(self, args):
        """Les N derniers messages d'un dossier (défaut INBOX, 15 ; max 50) : date, expéditeur, objet, n° (uid)."""
        dossier = args[0] if args else "INBOX"; n = min(int(args[1]) if len(args) > 1 and args[1].isdigit() else 15, 50)
        m = self.connexion()
        try:
            self.ouvrir(m, dossier); _, d = m.uid("search", None, "ALL")
            return self.entetes(m, d[0].split()[-n:][::-1])
        finally: m.logout()

    def chercher(self, args):
        """Messages d'un dossier dont l'expéditeur ou l'objet contient un mot : <dossier> <mot> (30 au plus)."""
        if len(args) < 2: raise ValueError("arguments : <dossier> <mot>")
        mot = " ".join(args[1:])[:60]
        if not re.fullmatch(r"[\w .@&'-]{2,60}", mot): raise ValueError("mot de recherche invalide")
        m = self.connexion()
        try:
            self.ouvrir(m, args[0]); m.literal = None
            _, a = m.uid("search", "CHARSET", "UTF-8", "OR", "FROM", f'"{mot}"', "SUBJECT", f'"{mot}"') if mot.isascii() else (None, [b""])
            return self.entetes(m, a[0].split()[-30:][::-1])
        finally: m.logout()

    def lire(self, args):
        """Un message : <dossier> <uid> — texte (8 000 caractères au plus) et noms des pièces jointes."""
        if len(args) < 2 or not args[1].isdigit(): raise ValueError("arguments : <dossier> <uid>")
        m = self.connexion()
        try:
            self.ouvrir(m, args[0]); t, d = m.uid("fetch", args[1], "(BODY.PEEK[])")
            if t != "OK" or not d or not d[0]: return None
            msg = email.message_from_bytes(d[0][1], policy=email.policy.default)
            corps = msg.get_body(preferencelist=("plain", "html")); texte = corps.get_content() if corps else ""
            if corps is not None and corps.get_content_type() == "text/html": texte = re.sub(r"<[^>]+>", " ", texte)
            return {"de": str(msg.get("From", ""))[:120], "a": str(msg.get("To", ""))[:200], "date": str(msg.get("Date", "")),
                    "objet": str(msg.get("Subject", ""))[:200], "texte": re.sub(r"\n{3,}", "\n\n", texte)[:8000],
                    "pieces_jointes": [p.get_filename() for p in msg.iter_attachments()][:20]}
        finally: m.logout()
