#!/usr/bin/env python3
"""Marques fixes du produit : vraie CLI, dépôt et maison jetables, aucun secret réel."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SRC = Path(__file__).resolve().parent.parent
MARQUES = ("her" + "mes", "open" + "claw")
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok
    print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as td:
    racine = Path(td)
    depot = racine / "depot"
    maison = racine / "maison"
    depot.mkdir()
    maison.mkdir()
    coffre = racine / "coffre.json"
    coffre.write_text("{}")
    (depot / "config.toml").write_text(
        f'proprietaire = "Proprietaire fictif"\ncoffre = "{coffre}"\n')
    subprocess.run(["git", "init", "-q", str(depot)], check=True)
    fichier = depot / "presentation.md"
    fichier.write_text("Berger : agents en fichiers texte.\n")
    subprocess.run(["git", "-C", str(depot), "add", "presentation.md"], check=True)
    env = {**os.environ, "HOME": str(maison), "BERGER_DIR": str(depot)}

    def verifier():
        return subprocess.run([sys.executable, str(SRC / "bin/berger"), "verifier-depot"],
                              env=env, capture_output=True, text=True, timeout=30)

    r = verifier()
    dire(r.returncode == 0 and "dépôt propre" in r.stdout, "présentation neutre acceptée")
    for numero, marque in enumerate(MARQUES, 1):
        for casse, texte in (("minuscule", marque), ("majuscule", marque.upper())):
            fichier.write_text(f"Une référence : « {texte} ».\n")
            r = verifier()
            dire(r.returncode == 1 and "presentation.md" in r.stdout
                 and "marque fixe du produit" in r.stdout,
                 f"marque {numero} en {casse} refusée dans un fichier suivi")
    fichier.write_text("Berger : agents en fichiers texte.\n")
    r = verifier()
    dire(r.returncode == 0 and "dépôt propre" in r.stdout, "retrait de la marque : dépôt accepté")

    # Exception : seule l'URL exacte du dépôt public (`depot_public`) peut porter une marque privée.
    marque = "temoin-proprio"
    url = f"https://forge.example/{marque}/berger.git"

    def configurer(depot_public=None):
        ligne = f'depot_public = "{depot_public}"\n' if depot_public else ""
        (depot / "config.toml").write_text(
            f'proprietaire = "Proprietaire fictif"\ncoffre = "{coffre}"\nmarques_privees = ["{marque}"]\n{ligne}')

    def essai(config, texte, accepte, nom):
        configurer(config)
        fichier.write_text(texte)
        r = verifier()
        if accepte:
            dire(r.returncode == 0 and "dépôt propre" in r.stdout, nom)
        else:
            dire(r.returncode == 1 and "presentation.md" in r.stdout and "marque privée" in r.stdout, nom)

    essai(url, f"git clone {url} ~/berger\n", True, "URL exacte du dépôt public acceptée")
    essai(url, f"[source]({url})\n", True, "URL exacte acceptée entre parenthèses")
    essai(None, f"git clone {url} ~/berger\n", False, "sans depot_public, la même URL est refusée")
    essai(url, f"git clone {url} ~/berger\nAuteur : {marque}\n", False, "marque hors de l'URL refusée malgré l'exception")
    essai(url, f"git clone https://forge.example/{marque}/autre.git\n", False, "autre dépôt du même compte refusé")
    essai(url, f"git clone {url}/suite\n", False, "URL prolongée refusée")
    essai(url, f"git clone {url[:-4]}\n", False, "URL sans .git refusée")
    essai(url, f"git clone {url.upper()}\n", False, "URL en majuscules refusée")
    essai(url, f"git clone http://forge.example/{marque}/berger.git\n", False, "URL en http refusée")
    essai(marque, f"Auteur : {marque}\n", False, "depot_public qui n'est pas une URL de dépôt : aucune exception")
    # Une marque privée collée à un point, un tiret ou un souligné reste refusée ; collée à une lettre, ce n'est plus elle.
    for texte, nom in ((f"[outils.veille-{marque}]\n", "nom d'outil composé"), (f"client.{marque}.example\n", "hôte"),
                       (f"Patch_{marque.upper()} CONNECT.pdf\n", "nom de fichier avec souligné"), (f"doc-{marque}\n", "verbe composé")):
        essai(None, texte, False, f"marque privée refusée dans un {nom}")
    essai(None, f"Auteur : {marque}e\n", True, "marque privée prolongée d'une lettre : un autre mot, accepté")
    configurer()
    fichier.write_text("Berger : agents en fichiers texte.\n")

    # Données embarquées (data URI base64, 08/11/2026, spec 2026-11-08-verifier-datauri) : la recherche porte sur le CONTENU
    # décodé, pas sur l'encodage. Le nom du propriétaire est cherché même à l'intérieur d'un mot : une suite de lettres tirée au
    # hasard dans le base64 d'une image le formait, et l'installation de v0.4.0 a été refusée à tort.
    import base64 as _b64
    nom = "Zorglub"                                                            # propriétaire fictif, d'un seul mot
    valeur = "Valeur-Du-Coffre-0123456789"
    coffre.write_text('{"outil": {"mot_de_passe": "' + valeur + '"}}')
    (depot / "config.toml").write_text(f'proprietaire = "{nom}"\ncoffre = "{coffre}"\n')
    image = depot / "apercu.html"
    subprocess.run(["git", "-C", str(depot), "add", "-N", "apercu.html"], check=False)
    def avec(texte):
        image.write_text(texte); subprocess.run(["git", "-C", str(depot), "add", "apercu.html"], check=True); return verifier()
    hasard = "AAAA" + nom + "A"                                                # le nom DANS l'encodage ; les octets décodés ne le portent pas
    assert nom.encode() not in _b64.b64decode(hasard)
    r = avec(f'<img src="data:image/png;base64,{hasard}">\n')
    dire(r.returncode == 0 and "dépôt propre" in r.stdout, "data URI : le nom dans l'encodage seulement (hasard), dépôt accepté")
    cache = _b64.b64encode(f"auteur : {nom}".encode()).decode()
    r = avec(f'<img src="data:text/plain;base64,{cache}">\n')
    dire(r.returncode == 1 and "nom du propriétaire" in r.stdout, "data URI : le nom dans le contenu DÉCODÉ, refusé")
    r = avec(f"Auteur : {nom}.\n")
    dire(r.returncode == 1 and "nom du propriétaire" in r.stdout, "le nom en clair hors data URI, refusé")
    r = avec('<img src="data:application/json;base64,' + _b64.b64encode(valeur.encode()).decode() + '">\n')
    dire(r.returncode == 1 and "VALEUR DU COFFRE" in r.stdout, "data URI : une valeur du coffre dans le contenu décodé, refusée")
    r = avec(f'<img src="data:image/png;base64,{nom}!!">\n')                  # base64 invalide : gardé tel quel, sans exemption
    dire(r.returncode == 1 and "nom du propriétaire" in r.stdout, "data URI au base64 invalide qui porte le nom, refusée")
    jeton = "AbCdEfGh12345678IjKlMnOp"                                         # une valeur du coffre faite de caractères base64
    coffre.write_text('{"outil": {"mot_de_passe": "' + jeton + '"}}')
    r = avec(f'<img src="data:image/png;base64,{jeton}">\n')                  # écrite TELLE QUELLE comme données : le texte brut compte aussi
    dire(r.returncode == 1 and "VALEUR DU COFFRE" in r.stdout, "data URI : une valeur du coffre écrite telle quelle comme données, refusée")
    image.unlink(); subprocess.run(["git", "-C", str(depot), "rm", "-q", "--cached", "apercu.html"], check=False)

sys.exit(1 if ko else 0)
