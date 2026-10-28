# -*- coding: utf-8 -*-
"""Outil de type « nextcloud » pour le courtier de Berger — fichiers par WebDAV, LIMITÉS à des dossiers racines.

Réglages (config.toml, [outils.<nom>]) :
  webdav           URL WebDAV, avec {utilisateur} (ex. https://cloud.exemple.fr/remote.php/dav/files/{utilisateur}/)
  utilisateur_cle  chemin de l'identifiant dans le coffre
  mot_de_passe_cle chemin du mot de passe (d'application) dans le coffre
  racines          dossiers autorisés (ex. ["Comptabilité"]) : rien n'est lu ni déposé ailleurs
  ip_secours       adresse de secours facultative (VPN)
Lecture : lister, lire (texte seulement). Écriture : déposer un fichier de l'agent — TOUJOURS soumis à validation.
Jamais de suppression ni de déplacement. Les identifiants passent à curl par l'entrée standard."""
import importlib.util, json, re, subprocess, urllib.parse
from pathlib import Path

_spec = importlib.util.spec_from_file_location("outil__contexte", Path(__file__).with_name("_contexte.py"))
_contexte = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_contexte)   # contexte propre à chaque appel


class Outil:
    contexte = _contexte.ContexteDeLAppel({})                        # posé par le courtier pour CET appel

    def __init__(self, reglages, secret, verifier_hote):
        self.r = reglages; self.valeur_coffre = secret; self.verifier_hote = verifier_hote
        self.racines = [x.strip("/") for x in reglages.get("racines", [])]
        if not self.racines: raise ValueError("nextcloud : au moins une racine autorisée (racines = […])")
        self.hote = re.match(r"https://([^/:]+)", reglages["webdav"]).group(1)
        self.verbes = {"lister": self.lister, "lire": self.lire}
        self.ecritures = {"deposer": (self.apercu_deposer, self.deposer)}

    def hotes(self):
        return {self.r["mot_de_passe_cle"]: {self.hote}}

    def chemin(self, c):
        c = (c or "").strip().strip("/")
        if ".." in c.split("/") or not any(c == r or c.startswith(r + "/") for r in self.racines):
            raise PermissionError(f"chemin hors des dossiers autorisés ({', '.join(self.racines)})")
        return c

    def url(self, c):
        u = str(self.valeur_coffre(self.r["utilisateur_cle"]))
        return self.r["webdav"].replace("{utilisateur}", u).rstrip("/") + "/" + urllib.parse.quote(c), u

    def dav(self, url, utilisateur, *args):
        self.verifier_hote(self.r["mot_de_passe_cle"], url)
        auth = f'user = "{utilisateur}:{self.valeur_coffre(self.r["mot_de_passe_cle"])}"\n'
        essais = [[]] + ([["--resolve", f"{self.hote}:443:{self.r['ip_secours']}"]] if self.r.get("ip_secours") else [])
        for extra in essais:
            p = subprocess.run(["curl", "-s", "-K", "-", "--max-time", "120", "-w", "\n%{http_code}", *args, *extra, url],
                               input=auth.encode(), capture_output=True)
            corps, _, code = p.stdout.rpartition(b"\n")
            if code and code != b"000": return code.decode(), corps
        raise RuntimeError("Nextcloud injoignable")

    def lister(self, args):
        """Contenu d'un dossier autorisé : nom, taille, date (ex. lister Comptabilité/Factures_Fournisseurs/OVH)."""
        c = self.chemin(args[0] if args else self.racines[0]); url, u = self.url(c + "/")
        code, corps = self.dav(url, u, "-X", "PROPFIND", "-H", "Depth: 1")
        if code != "207": raise RuntimeError(f"Nextcloud : HTTP {code}")
        t = corps.decode(errors="ignore"); out = []
        for bloc in re.findall(r"<d:response>(.*?)</d:response>", t, re.S)[1:]:
            href = urllib.parse.unquote(re.search(r"<d:href>(.*?)</d:href>", bloc).group(1)).rstrip("/").split("/")[-1]
            taille = re.search(r"<d:getcontentlength>(\d+)", bloc); date = re.search(r"<d:getlastmodified>(.*?)<", bloc)
            out.append({"nom": href + ("/" if "<d:collection" in bloc else ""), "ko": int(taille.group(1)) // 1024 if taille else None,
                        "modifie": date.group(1) if date else None})
        return sorted(out, key=lambda x: x["nom"])[:300]

    def lire(self, args):
        """Contenu d'un fichier TEXTE d'un dossier autorisé (20 000 caractères au plus)."""
        c = self.chemin(args[0] if args else ""); url, u = self.url(c)
        code, corps = self.dav(url, u)
        if code != "200": raise RuntimeError(f"Nextcloud : HTTP {code}")
        try: t = corps.decode("utf-8")
        except UnicodeDecodeError: return {"fichier": c, "binaire": True, "ko": len(corps) // 1024}
        return {"fichier": c, "texte": t[:20000], "coupe": len(t) > 20000}

    def _depot(self, args):
        if len(args) < 2: raise ValueError("arguments : <fichier de ton dossier> <dossier/nom de destination>")
        bases = [Path(p) for p in (self.contexte.get("dossier"), self.contexte.get("travail")) if p]
        src = None
        for b in bases:
            x = (b / args[0]).resolve()
            if x.is_file() and any(x.is_relative_to(bb.resolve()) for bb in bases): src = x; break
        if not src: raise PermissionError("fichier introuvable dans ton dossier")
        if src.stat().st_size > 20 * 1024 * 1024: raise ValueError("fichier trop gros (20 Mo au plus)")
        return src, self.chemin(args[1])

    def apercu_deposer(self, args):
        """Déposer un fichier de ton dossier dans Nextcloud : <fichier> <dossier/nom de destination>."""
        src, dest = self._depot(args)
        return f"déposer {src.name} ({src.stat().st_size // 1024} Ko) dans Nextcloud : {dest}"

    def deposer(self, args):
        src, dest = self._depot(args); url, u = self.url(dest)
        code, _ = self.dav(url, u, "-T", str(src))
        if code not in ("201", "204"): raise RuntimeError(f"dépôt refusé par Nextcloud : HTTP {code}")
        return f"déposé : {dest}"
