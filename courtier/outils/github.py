# -*- coding: utf-8 -*-
"""Outil de type « github » pour le courtier de Berger — LECTURE des pull requests d'une liste FERMÉE de dépôts,
et leur fusion comme ÉCRITURE soumise à validation (du propriétaire seulement : pas de `valide_par` ici, voir README).

Réglages (config.toml, section [outils.<nom>]) :
  cle         chemin du jeton dans le coffre (ex. github.jeton) — il ne part QUE vers api.github.com
  depots      liste des dépôts permis, « propriétaire/nom »
  valide_par  facultatif : l'agent qui valide les fusions (ex. le coordinateur dev)…
  [outils.<nom>.sensibles]  …SAUF pour une PR qui touche un de ces chemins (préfixes, par dépôt) : propriétaire seul.
              Ex. "proprietaire/berger" = ["courtier/", "bin/", "crochets/", "commun/REGLES.md"] : le code qui enferme les
              agents ne peut pas être validé par un agent qu'il enferme.
Verbes : prs <dépôt>, pr <dépôt> <n°>, difference <dépôt> <n°> ; fusionner <dépôt> <n°> (ÉCRITURE, validée).
Le jeton passe à curl par l'entrée standard, jamais en argument ni dans une réponse."""
import json, re, subprocess

HOTE = "api.github.com"


class Outil:
    def __init__(self, reglages, secret, verifier_hote):
        self.cle = reglages["cle"]; self.depots = set(reglages.get("depots", []))
        self.valide_par = reglages.get("valide_par"); self.sensibles = reglages.get("sensibles", {})
        self.valeur_coffre = secret; self.verifier_hote = verifier_hote
        self.verbes = {"prs": self.prs, "pr": self.pr, "difference": self.difference}
        self.ecritures = {"fusionner": (self.apercu_fusion, self.fusionner)}

    def hotes(self): return {self.cle: {HOTE}}

    def depot(self, args, avec_numero=False):
        if not args or args[0] not in self.depots: raise ValueError(f"dépôt non permis (permis : {', '.join(sorted(self.depots))})")
        if avec_numero and (len(args) < 2 or not args[1].isdigit()): raise ValueError("numéro de pull request attendu")
        return args[0], (int(args[1]) if avec_numero else None)

    def appel(self, chemin, methode="GET", corps=None, accept="application/vnd.github+json"):
        url = f"https://{HOTE}/repos/{chemin}"; self.verifier_hote(self.cle, url)
        options = [("header", f"Authorization: Bearer {self.valeur_coffre(self.cle)}"),
                   ("header", f"Accept: {accept}"), ("header", "X-GitHub-Api-Version: 2022-11-28"),
                   ("header", "User-Agent: berger-courtier"), ("request", methode), ("url", url)]
        if corps is not None:
            options += [("header", "Content-Type: application/json"),
                        ("data-binary", json.dumps(corps, ensure_ascii=False))]
        configuration = "".join(k + " = " + json.dumps(v, ensure_ascii=False) + "\n" for k, v in options)
        r = subprocess.run(["curl", "-s", "-K", "-", "--max-time", "30", "-w", "\n%{http_code}"],
                           input=configuration, capture_output=True, text=True)
        texte, _, code = r.stdout.rpartition("\n")
        if not code.startswith("2"): raise RuntimeError(f"GitHub : HTTP {code or 'aucune réponse'} — {texte[:200]}")
        return texte if accept.endswith("diff") else json.loads(texte or "null")

    def prs(self, args):
        """prs <dépôt> : les pull requests ouvertes."""
        d, _ = self.depot(args)
        return [{"n": p["number"], "titre": p["title"], "auteur": p["user"]["login"], "branche": p["head"]["ref"],
                 "vers": p["base"]["ref"], "creee": p["created_at"][:16]} for p in self.appel(f"{d}/pulls?state=open&per_page=50")]

    def pr(self, args):
        """pr <dépôt> <n°> : description, fichiers, état de fusion et vérifications."""
        d, n = self.depot(args, True); p = self.appel(f"{d}/pulls/{n}")
        fichiers = [{"fichier": f["filename"], "+": f["additions"], "-": f["deletions"]} for f in self.appel(f"{d}/pulls/{n}/files?per_page=100")]
        return {"n": n, "titre": p["title"], "auteur": p["user"]["login"], "etat": p["state"], "fusionnable": p.get("mergeable"),
                "branche": p["head"]["ref"], "commit": p["head"]["sha"], "vers": p["base"]["ref"], "description": (p.get("body") or "")[:6000],
                "fichiers": fichiers}

    def difference(self, args):
        """difference <dépôt> <n°> : la différence complète (12 000 caractères au plus)."""
        d, n = self.depot(args, True)
        return self.appel(f"{d}/pulls/{n}", accept="application/vnd.github.diff")[:12000]

    def touche_sensible(self, d, n):
        prefixes = self.sensibles.get(d, [])
        return sorted({f["filename"] for f in self.appel(f"{d}/pulls/{n}/files?per_page=100") for p in prefixes if f["filename"].startswith(p)})

    def valideur(self, verbe, args):
        """Qui valide CETTE demande : valide_par, sauf PR touchant un chemin sensible → None (propriétaire seul)."""
        if verbe != "fusionner" or not self.valide_par: return None
        d, n = self.depot(args, True)
        return None if self.touche_sensible(d, n) else self.valide_par

    def apercu_fusion(self, args):
        """fusionner <dépôt> <n°> : fusionne la pull request (validation du propriétaire)."""
        d, n = self.depot(args, True); p = self.appel(f"{d}/pulls/{n}")
        if p["state"] != "open": raise ValueError(f"la pull request #{n} n'est pas ouverte ({p['state']})")
        s = self.touche_sensible(d, n)
        return (f"fusionner la pull request #{n} de {d} « {p['title']} » ({p['head']['ref']} → {p['base']['ref']}, commit {p['head']['sha'][:10]})"
                + (f" — touche du code SENSIBLE ({', '.join(s[:5])}) : propriétaire seul" if s else ""))

    def fusionner(self, args):
        d, n = self.depot(args, True); p = self.appel(f"{d}/pulls/{n}")
        r = self.appel(f"{d}/pulls/{n}/merge", "PUT", {"sha": p["head"]["sha"], "merge_method": "merge"})   # le commit relu, pas un autre
        return f"#{n} fusionnée : {r.get('message', '')} ({(r.get('sha') or '')[:10]})"
