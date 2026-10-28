# -*- coding: utf-8 -*-
"""Outil de type « dolibarr » pour le courtier de Berger — LECTURE SEULE de l'API REST de Dolibarr (ERP libre).

Réglages (config.toml, section [outils.<nom>]) :
  hote       nom de l'hôte Dolibarr (ex. erp.exemple.fr) — la clé ne peut partir QUE vers lui
  cle        chemin de la clé API dans le coffre (ex. erp.cle_api)
  ip_secours adresse de secours facultative (VPN), utilisée si l'hôte public ne répond pas
Avec `ecriture = true`, l'outil n'offre QUE des écritures — toujours soumises à la validation du propriétaire par le
courtier — et jamais de validation de facture, de paiement ni de suppression. La clé passe à curl par l'entrée standard."""
import datetime, json, re, subprocess


class Outil:
    def __init__(self, reglages, secret, verifier_hote):
        self.hote = reglages["hote"]; self.cle = reglages["cle"]; self.secours = reglages.get("ip_secours", "")
        self.valeur_coffre = secret; self.verifier_hote = verifier_hote; self._noms = {}
        self.verbes = {"factures-impayees": self.factures_impayees, "factures-recentes": self.factures_recentes,
                       "facture": self.facture, "tiers": self.tiers}
        self.ecritures = {}
        if reglages.get("ecriture"):
            self.verbes = {}
            self.ecritures = {"brouillon-facture": (self.apercu_brouillon, self.creer_brouillon)}

    def hotes(self):
        return {self.cle: {self.hote}}

    def appel(self, chemin, methode="GET", corps=None):
        url = f"https://{self.hote}/api/index.php/{chemin}"
        self.verifier_hote(self.cle, url)
        options = [("header", f"DOLAPIKEY: {self.valeur_coffre(self.cle)}"),
                   ("header", "Accept: application/json"), ("request", methode), ("url", url)]
        if corps is not None:
            options += [("header", "Content-Type: application/json"),
                        ("data-binary", json.dumps(corps, ensure_ascii=False))]
        essais = [[]] + ([[("resolve", f"{self.hote}:443:{self.secours}")]] if self.secours else [])
        code = ""
        for extra in essais:
            configuration = "".join(k + " = " + json.dumps(v, ensure_ascii=False) + "\n" for k, v in options + extra)
            r = subprocess.run(["curl", "-s", "-K", "-", "--max-time", "20", "-w", "\n%{http_code}"],
                               input=configuration, capture_output=True, text=True)
            reponse, _, code = r.stdout.rpartition("\n")
            if code in ("200", "201"): return json.loads(reponse)
            if code == "404": return []                                  # Dolibarr : « aucun résultat » = 404
        raise RuntimeError(f"Dolibarr injoignable (dernier code HTTP : {code or 'aucun'})")

    @staticmethod
    def jour(ts):
        try: return datetime.date.fromtimestamp(int(ts)).isoformat()
        except (TypeError, ValueError): return None

    @staticmethod
    def montant(x):
        try: return round(float(x), 2)
        except (TypeError, ValueError): return None

    def nom_tiers(self, socid):
        if socid not in self._noms:
            t = self.appel(f"thirdparties/{int(socid)}")
            self._noms[socid] = t.get("name") if isinstance(t, dict) else None
        return self._noms[socid]

    def facture_courte(self, f):
        return {"ref": f.get("ref"), "client": self.nom_tiers(f.get("socid")), "date": self.jour(f.get("date")),
                "echeance": self.jour(f.get("date_lim_reglement")), "total_ttc": self.montant(f.get("total_ttc")),
                "reste_a_payer": self.montant(f.get("remaintopay")),
                "statut": {"0": "brouillon", "1": "impayée", "2": "payée", "3": "abandonnée"}.get(str(f.get("status")), f.get("status"))}

    def factures_impayees(self, args):
        """Factures clients validées non payées, la plus en retard d'abord."""
        return [self.facture_courte(f) for f in self.appel("invoices?limit=100&sortfield=t.date_lim_reglement&sortorder=ASC&sqlfilters=(t.fk_statut:=:1)")]

    def factures_recentes(self, args):
        """Les N dernières factures clients (défaut 10, max 50)."""
        n = min(int(args[0]) if args and args[0].isdigit() else 10, 50)
        return [self.facture_courte(f) for f in self.appel(f"invoices?limit={n}&sortfield=t.datef&sortorder=DESC")]

    def facture(self, args):
        """Une facture par sa référence (ex. FA2609-0123), avec ses lignes."""
        if not args or not re.fullmatch(r"[A-Z]{2,4}[0-9]{4}-[0-9]{3,5}", args[0]): raise ValueError("référence attendue, ex. FA2609-0123")
        d = self.appel(f"invoices/ref/{args[0]}")
        if not isinstance(d, dict) or not d: return None
        out = self.facture_courte(d)
        out["lignes"] = [{"libelle": (l.get("product_label") or l.get("desc") or "")[:120], "qte": self.montant(l.get("qty")),
                          "pu_ht": self.montant(l.get("subprice")), "tva": self.montant(l.get("tva_tx")), "total_ht": self.montant(l.get("total_ht"))}
                         for l in d.get("lines", [])]
        return out

    def tiers(self, args):
        """Chercher un tiers (client/fournisseur) par une partie de son nom."""
        nom = " ".join(args).strip()
        if not re.fullmatch(r"[\w .'&-]{2,60}", nom): raise ValueError("nom attendu (2 à 60 caractères simples)")
        d = self.appel(f"thirdparties?limit=20&sqlfilters=(t.nom:like:'%25{nom.replace(chr(39), '')}%25')")
        return [{"id": t.get("id"), "nom": t.get("name"), "ville": t.get("town"), "client": t.get("client"),
                 "fournisseur": t.get("fournisseur")} for t in d]

    # ── écritures (soumises à validation par le courtier) ──
    def _brouillon(self, args):
        if len(args) < 2 or not args[0].isdigit(): raise ValueError("arguments : <id du tiers> <lignes JSON>")
        lignes = json.loads(args[1])
        if not isinstance(lignes, list) or not 1 <= len(lignes) <= 30: raise ValueError("1 à 30 lignes attendues")
        propres = []
        for l in lignes:
            desc = str(l.get("desc", "")).strip()[:300]
            qte, pu, tva = float(l.get("qty", 1)), float(l.get("subprice", 0)), float(l.get("tva_tx", 20))
            if not desc or qte <= 0 or pu < 0 or tva not in (0.0, 2.1, 5.5, 10.0, 20.0): raise ValueError(f"ligne invalide : {l}")
            propres.append({"desc": desc, "qty": qte, "subprice": round(pu, 2), "tva_tx": tva, "product_type": 1})
        return int(args[0]), propres

    def apercu_brouillon(self, args):
        """Créer une facture client en BROUILLON : <id du tiers> '<lignes JSON : [{desc, qty, subprice, tva_tx}]>'."""
        socid, lignes = self._brouillon(args)
        ht = sum(l["qty"] * l["subprice"] for l in lignes)
        return f"facture BROUILLON pour {self.nom_tiers(socid) or 'tiers ' + str(socid)}, {len(lignes)} ligne(s), {ht:.2f} € HT"

    def creer_brouillon(self, args):
        socid, lignes = self._brouillon(args)
        nid = self.appel("invoices", "POST", {"socid": socid, "type": 0, "lines": lignes})
        f = self.appel(f"invoices/{int(nid)}")
        return {"id": int(nid), "ref": f.get("ref"), "statut": "brouillon", "total_ttc": self.montant(f.get("total_ttc"))}
