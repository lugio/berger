// Interface web de Berger (spec docs/plans/2026-10-13-interface-spec.md) — lecture seule, sans cadriciel ni étape de
// construction. La page ne connaît AUCUNE règle : chaque donnée vient d'une vue (berger vue <type> --json) ; la navigation
// vient de /api/vues (une vue nouvelle — actions, livrables, versions, santé — y apparaît d'elle-même, rendue par le gabarit
// générique). Les vues principales ont un rendu dédié (bloc DEDIES) ; les icônes de navigation sont dans le bloc ICONES :
// ce sont les SEULS endroits où une vue est nommée. Tout texte venu des données est inséré comme texte (textContent),
// jamais comme HTML. Présentation : tableau de bord d'exploitation, neutre (retour du propriétaire, 14/10).
"use strict";

// ── Les rendus connus : un par mot « x-rendu » des schémas (tests/interface.py exige que chaque mot employé soit ici) ──
const RENDUS = {
  texte: (s, v) => texte(v),
  nombre: (s, v) => texte(v === null || v === undefined ? "" : String(v)),
  quand: (s, v) => texte(court(v)),
  "oui-non": (s, v) => texte(v === true ? "oui" : v === false ? "non" : ""),
  ton: (s, v) => v ? etiquette(v, v) : null,
  agent: (s, v) => v ? texte(((v.icone || "") + " " + v.nom).trim()) : null,
  statuts: (s, v) => statuts(v),
  checklist: (s, v) => travail(v),
  validation: (s, v) => ecriture(v),
  lignes: (s, v) => lignes(v),
  liste: (s, v) => liste(s, v),
  lien: (s, v) => v ? ouvrir(v.vue, v.a) : null,
  markdown: (s, v) => markdown(v),
  cache: () => null,
};

// ── Rendus dédiés des vues principales : la clé est le type de la vue ; `autres` = vues lues en plus (leurs données) ;
// `compteur` = [vue, nombre affiché dans la navigation] ; `global` = ce que la vue donne à l'en-tête (état global) ;
// `fixe` = vue d'objet affichée une fois à l'ouverture, sans relecture automatique. ──
const DEDIES = {
  livrables: { rendre: d => livrables(d.livrables, "livrable") },
  documents: { rendre: d => ged(d.documents, "livrable"), fixe: true },  // fixe : la recherche en cours n'est pas effacée toutes les 5 s
  livrable: { rendre: d => livrable(d), fixe: true },                     // fixe : pas relue toutes les 5 s (la maquette ne se recharge pas)
  accueil: { autres: ["synthese", "alire", "decisions"], rendre: (d, x) => accueil(d, x.synthese, x.alire, x.decisions, "document"),
             compteur: ["decisions", pourToi] },
  colonnes: { rendre: d => colonnes(d) },
  decisions: { rendre: d => decisions(d) },
  alire: { rendre: d => alire(d.documents, "document"), compteur: ["alire", d => d.non_lus] },
  echanges: { rendre: d => echanges(d) },
  courtier: { global: etatCourtier },
};

// ── Icônes de la navigation (tracés 24 × 24, trait) : par type de vue ; une vue sans icône prend le carré générique ──
const ICONES = {
  livrables: "M4 20h16M6 16L16 6l2 2L8 18H6z",
  documents: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  accueil: "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z",
  colonnes: "M4 4h4v16H4zM10 4h4v10h-4zM16 4h4v13h-4z",
  synthese: "M12 3l9 16H3zM12 10v4M12 17h.01",
  sources: "M4 6h16M4 12h16M4 18h10",
  decisions: "M9 11l3 3 8-8M20 12v7a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h11",
  checklists: "M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01",
  alire: "M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2zM4 21V5",
  courtier: "M6 11V8a6 6 0 0 1 12 0v3M5 11h14v10H5z",
  echanges: "M4 5h16v11H8l-4 4z",
  catalogue: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  tokens: "M4 20V10M10 20V4M16 20v-7M22 20H2",
};
const ICONE_AGENTS = "M16 20v-2a4 4 0 0 0-8 0v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z", ICONE_GENERIQUE = "M5 5h14v14H5z";

function etatCourtier(d) { return { texte: d.actif ? "Courtier actif" : "Courtier arrêté", ton: d.actif ? "vert" : "rouge" }; }
function pourToi(d) { return d.decisions.filter(e => e.pour === "toi").length; }   // ce qui t'attend
let SCHEMAS = {}, VUES = [], AGENTS = [], COMPTES = {}, GLOBAL = [], courant = null, affiche = null, enVol = false, encore = false, dernier = null;

// ── outils ──
function el(nom, attrs, ...enfants) {
  const n = document.createElement(nom);
  for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
  for (const e of enfants) if (e !== null && e !== undefined && e !== false) n.append(typeof e === "string" ? document.createTextNode(e) : e);
  return n;
}
function icone(trace) {
  const ns = "http://www.w3.org/2000/svg", s = document.createElementNS(ns, "svg"), p = document.createElementNS(ns, "path");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("class", "icone");
  p.setAttribute("d", trace); s.append(p); return s;
}
function texte(v) { return vide(v) ? null : el("span", {}, String(v)); }
function vide(v) { return v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length); }
function pale(t) { return el("span", { class: "pale" }, t); }
function etiquette(ton, t) { return el("span", { class: "etiquette e-" + ton }, t); }
function bloc(titre, compte, ...corps) {
  return el("section", { class: "bloc" }, el("header", {}, el("h2", {}, titre), compte !== null && compte !== undefined ? el("span", { class: "nombre" }, String(compte)) : null),
            el("div", { class: "corps" }, ...corps));
}
function court(v) {                                                    // « 21:32 » aujourd'hui, sinon « 13/10 21:20 » (ou « 13/10 »)
  if (!v) return "";
  const d = new Date(v);
  if (isNaN(d)) return String(v);
  const deux = n => String(n).padStart(2, "0"), heure = deux(d.getHours()) + ":" + deux(d.getMinutes());
  if (!/T\d\d:/.test(v)) return deux(d.getDate()) + "/" + deux(d.getMonth() + 1);
  return d.toDateString() === new Date().toDateString() ? heure : deux(d.getDate()) + "/" + deux(d.getMonth() + 1) + " " + heure;
}
const TONS_ETAT = { working: "bleu", idle: "vert", done: "vert", blocked: "rouge" };
function statuts(v) {
  if (!v || !v.length) return el("span", { class: "etat" }, el("span", { class: "point p-gris" }), "pas ouvert");
  return el("span", { class: "statuts" }, ...v.map(s => el("span", { class: "etat" }, el("span", { class: "point p-" + (TONS_ETAT[s.etat] || "gris") }), s.libelle)));
}
function barre(faites, total) {
  const p = total ? Math.round(100 * faites / total) : 0;
  const plein = el("span", {}); plein.style.width = p + "%";              // par le CSSOM : la politique de contenu interdit l'attribut style
  return el("div", { class: "progression" }, el("div", { class: "barre" }, plein), el("span", { class: "chiffre" }, faites + "/" + total));
}
function travail(c) {
  if (!c || c.fini) return pale("—");
  return el("div", { class: "travail" }, el("div", { class: "titre-travail" }, c.titre), barre(c.faites, c.total),
            c.bloque ? el("div", {}, etiquette("rouge", c.go ? "Go attendu" : "Bloqué"), " " + c.bloque) : null,
            c.question ? el("div", {}, etiquette("bleu", "Question"), " " + c.question) : null);
}
function ecriture(x) {
  if (!x) return null;
  const n = x.n === null ? "?" : x.n;
  return el("div", { class: "ligne-liste" }, el("div", { class: "l1" }, el("strong", {}, "n° " + n), " " + x.agent.nom + " · " + x.verbe, el("span", { class: "heure" }, court(x.demande))),
            el("div", { class: "pale" }, x.apercu),
            x.valideur ? el("div", { class: "pale" }, "attend " + x.valideur.nom) : el("div", {}, el("code", {}, "berger valider " + n)));
}
function ouvrir(vue, a, libelle) { return el("button", { type: "button", class: "lien", "data-objet": vue, "data-a": a }, libelle || "Détail"); }
function markdown(t) {                                                  // titres, listes, code : en éléments, jamais en HTML
  const d = el("div", { class: "markdown" }); let pre = null;
  const enLigne = s => s.split(/(\*\*[^*]+\*\*|`[^`]+`)/).filter(Boolean).map(x =>
    x.startsWith("**") ? el("strong", {}, x.slice(2, -2)) : x.startsWith("`") ? el("code", {}, x.slice(1, -1)) : document.createTextNode(x));
  for (const l of String(t || "").split("\n")) {
    if (l.startsWith("```")) { if (pre) { d.append(pre); pre = null; } else pre = el("pre", {}); continue; }
    if (pre) { pre.append(l + "\n"); continue; }
    const m = l.match(/^(#{1,6})\s+(.*)/);
    if (m) d.append(el("h" + Math.min(6, m[1].length + 2), {}, m[2]));
    else if (/^\s*[-*]\s+/.test(l)) d.append(el("p", { class: "puce" }, "• ", ...enLigne(l.replace(/^\s*[-*]\s+/, ""))));
    else if (l.trim()) d.append(el("p", {}, ...enLigne(l)));
  }
  if (pre) d.append(pre);
  return d;
}
function lignes(v) {
  if (!v || !v.length) return null;
  const d = el("div", { class: "lignes" });
  for (const l of v) {
    if (Array.isArray(l)) d.append(el("div", {}, ...l.map(m => el("span", { class: m.ton ? "t-" + m.ton : "" }, m.texte))));
    else { const ton = "gravite" in l ? l.gravite : ("ton" in l ? l.ton : null); d.append(el("div", { class: ton ? "t-" + ton : "" }, l.texte)); }
  }
  return d;
}
function tableau(entetes, rangees) {                                     // rangées = [[cellule…]] ; data-label : la liste empilée du téléphone
  return el("div", { class: "table" }, el("table", {}, el("thead", {}, el("tr", {}, ...entetes.map(t => el("th", {}, t)))),
    el("tbody", {}, ...rangees.map(r => el("tr", {}, ...r.map((c, i) => el("td", { "data-label": entetes[i] }, c)))))));
}

// ── rendus dédiés ──
function accueil(d, synthese, alire_, decisions_, vueDocument) {
  const rouges = synthese.alertes.filter(a => a.gravite === "rouge").length, toi = pourToi(decisions_);
  const tuiles = el("div", { class: "tuiles" },
    tuile("T'attend", toi, toi ? "jaune" : null), tuile("Écritures à valider", d.a_toi.length, d.a_toi.length ? "jaune" : null),
    tuile("Bloqués", d.bloques.length, d.bloques.length ? "rouge" : null), tuile("Alertes rouges", rouges, rouges ? "rouge" : null),
    tuile("À lire", alire_.non_lus, null));
  const ech = el("div", { class: "liste-lignes" }, ...d.a_toi.map(ecriture),
                 ...d.delegues.map(x => el("div", { class: "ligne-liste pale" }, "n° " + x.n + " attend " + x.valideur.nom + " · " + x.apercu)));
  if (!ech.childNodes.length) ech.append(el("p", { class: "vide" }, "Rien n'attend ta décision."));
  const al = el("div", { class: "liste-lignes" }, ...synthese.alertes.map(a => el("div", { class: "ligne-liste alerte a-" + a.gravite },
    el("div", { class: "l1" }, el("strong", {}, a.domaine), a.nouveau ? etiquette("bleu", "nouveau") : null, el("span", { class: "heure" }, court(a.depuis))), el("div", {}, a.texte))));
  if (!synthese.alertes.length) al.append(el("p", { class: "vide" }, "Rien en rouge ni en jaune."));
  const agents_ = tableau(["Agent", "État", "Travail en cours", "Dernière action"], d.agents.map(x => [
    el("strong", {}, ((x.agent.icone || "") + " " + x.agent.nom).trim()), statuts(x.statuts), travail(x.checklist), pale(x.derniere_action || "—")]));
  const eq = el("div", { class: "liste-lignes" });
  for (const e of d.equipes) {
    eq.append(el("div", { class: "sous-titre" }, e.projet,
      pale([e.chef ? "chef : " + e.chef.nom : null, e.coordinateur ? "coordinateur : " + e.coordinateur.nom : null].filter(Boolean).map(x => " · " + x).join(""))));
    for (const m of e.membres) eq.append(el("div", { class: "ligne-liste" }, el("div", { class: "l1" }, statuts(m.statuts), el("strong", {}, m.sujet),
      el("span", { class: "heure" }, [m.total !== null ? m.faites + "/" + m.total : null, m.demande].filter(Boolean).join(" · ")))));
    if (e.fusionnes.length) eq.append(el("div", { class: "pale petit" }, "Fusionnés : " + e.fusionnes.join(", ")));
    if (!e.membres.length && !e.fusionnes.length) eq.append(el("p", { class: "vide" }, "Aucun développeur ouvert."));
  }
  if (!d.equipes.length) eq.append(el("p", { class: "vide" }, "Aucune équipe."));
  return el("div", { class: "page" }, tuiles,
    el("div", { class: "deux" }, bloc("À toi de décider", d.a_toi.length, ech), bloc("Alertes", synthese.alertes.length, al)),
    bloc("Agents", d.agents.length, agents_),
    el("div", { class: "deux" }, bloc("Équipes", null, eq), bloc("À lire", alire_.non_lus, alire(alire_.documents, vueDocument))));
}
function tuile(libelle, n, ton) {
  return el("div", { class: "tuile" + (ton ? " u-" + ton : "") }, el("div", { class: "valeur" }, String(n)), el("div", { class: "libelle" }, libelle));
}
function alire(docs, vueDocument) {
  const l = el("div", { class: "liste-lignes" });
  for (const x of docs) {
    l.append(el("div", { class: "ligne-liste doc" + (x.lu ? " lu" : "") }, el("span", { class: "point " + (x.lu ? "p-vide" : "p-bleu") }),
      el("div", { class: "doc-texte" }, el("div", { class: "doc-titre" }, x.titre),
        pale((x.auteur ? x.auteur.nom : "commun") + " · " + court(x.date) + (x.regle ? " · réglé : " + x.regle : ""))),
      ouvrir(vueDocument, x.id, "Lire")));
  }
  if (!docs.length) l.append(el("p", { class: "vide" }, "Rien à lire."));
  return l;
}
const ORIGINES = { commun: "Commun", projet: "Projets d'équipe", travail: "Dossiers de travail", a_lire: "À lire", branche: "Branches en cours" };
const IMAGES = ["png", "jpeg", "gif", "webp"];
function ou(x) { return [ORIGINES[x.origine] || x.origine, x.branche ? x.projet + " · " + x.branche : null, x.chemin].filter(Boolean).join(" · "); }
function livrables(l, vueLivrable) {
  const liste = el("div", { class: "liste-lignes" });
  for (const x of l) {
    liste.append(el("div", { class: "ligne-liste doc" }, genre(x.genre),
      el("div", { class: "doc-texte" }, el("div", { class: "doc-titre" }, x.titre), pale((x.auteur ? x.auteur.nom : "commun") + " · " + court(x.date) + " · " + ou(x))),
      ouvrir(vueLivrable, x.id, "Ouvrir")));
  }
  if (!l.length) liste.append(el("p", { class: "vide" }, "Aucun livrable : les agents déposent specs, maquettes et rapports dans la bibliothèque (travail/<sujet>/) ou À lire."));
  return el("div", { class: "page" }, bloc("Specs, maquettes et rapports", l.length, liste));
}
function genre(g) { return etiquette(g === "html" ? "bleu" : g === "pdf" ? "jaune" : "gris", g === "html" ? "maquette" : IMAGES.includes(g) ? "image" : g); }
// Documents (mini GED, consultation seule) : rangés par origine puis par dossier ; la recherche filtre par nom ce qui est
// déjà reçu (présentation seulement : aucune donnée calculée, aucune requête de plus).
function ged(l, vueDocument) {
  const sans = t => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const lignes_ = [], corps = el("div", {});
  for (const [o, libelle] of Object.entries(ORIGINES)) {
    const mes = l.filter(x => x.origine === o);
    if (!mes.length) continue;
    const dossiers = {};
    for (const x of mes) {
      const d = [x.projet, x.branche, x.chemin.includes("/") ? x.chemin.slice(0, x.chemin.lastIndexOf("/")) : null].filter(Boolean).join(" · ") || "—";
      (dossiers[d] = dossiers[d] || []).push(x);
    }
    const b = el("div", { class: "liste-lignes" });
    for (const [d, xs] of Object.entries(dossiers).sort()) {
      b.append(el("div", { class: "sous-titre" }, d));
      for (const x of xs) {
        const ligne = el("div", { class: "ligne-liste doc", "data-nom": sans(x.titre + " " + x.chemin) }, genre(x.genre),
          el("div", { class: "doc-texte" }, el("div", { class: "doc-titre" }, x.titre), pale(x.chemin.slice(x.chemin.lastIndexOf("/") + 1) + " · " + court(x.date) + " · " + x.taille + " octets")),
          ouvrir(vueDocument, x.id, "Ouvrir"));
        lignes_.push(ligne); b.append(ligne);
      }
    }
    corps.append(bloc(libelle, mes.length, b));
  }
  if (!l.length) corps.append(el("p", { class: "vide" }, "Aucun document dans la bibliothèque ni dans À lire."));
  const cherche = el("input", { type: "search", class: "recherche", placeholder: "Chercher par nom…", "aria-label": "Chercher un document par nom" });
  cherche.addEventListener("input", () => { const q = sans(cherche.value.trim()); for (const x of lignes_) x.hidden = !!q && !x.getAttribute("data-nom").includes(q); });
  return el("div", { class: "page" }, cherche, corps);
}
// Un livrable : un .md en texte ; un .html (maquette, aperçu) dans un cadre isolé — sandbox SANS allow-same-origin : origine
// opaque, ni cookie ni accès à cette page ; le serveur ajoute sa propre CSP (aucun réseau) ; un pdf s'ouvre dans un onglet,
// une image s'affiche, le reste se télécharge (en-têtes du serveur, genre vérifié par berger).
function livrable(d) {
  const brut = "/api/livrable/" + d.id + "/" + d.genre;
  const tete = el("div", { class: "pale" }, (d.auteur ? d.auteur.nom : "commun") + " · " + court(d.date) + " · " + ou(d) + " · " + d.taille + " octets");
  let corps;
  if (d.texte !== null) corps = el("div", {}, markdown(d.texte), d.tronque ? pale("… coupé à 200 Ko") : null);
  else if (d.genre === "html") corps = el("div", {}, el("iframe", { class: "cadre-livrable", sandbox: "allow-scripts", src: brut, title: d.titre, referrerpolicy: "no-referrer" }),
                                          el("a", { href: brut, target: "_blank", rel: "noopener noreferrer" }, "Ouvrir seul dans un onglet"));
  else if (d.genre === "pdf") corps = el("a", { href: brut, target: "_blank", rel: "noopener noreferrer" }, "Ouvrir le PDF dans un onglet");
  else if (IMAGES.includes(d.genre)) corps = el("img", { class: "image-document", src: brut, alt: d.titre });
  else corps = el("a", { href: brut, download: "" }, "Télécharger");
  return el("div", { class: "page" }, bloc(d.titre, null, tete, corps));
}
function colonnes(d) {
  const g = el("div", { class: "kanban" });
  for (const c of d.colonnes) {
    const mes = d.cartes.filter(x => x.colonne === c.cle);
    g.append(el("section", { class: "colonne" }, el("header", {}, el("span", { class: "point p-" + c.ton }), el("h2", {}, c.libelle), el("span", { class: "nombre" }, String(mes.length))),
      ...mes.map(x => el("div", { class: "carte-kanban" + (x.vif ? " vif" : "") }, el("div", { class: "l1" }, el("strong", {}, x.titre)), lignes(x.lignes))),
      mes.length ? null : el("p", { class: "vide" }, "—")));
  }
  return g;
}
const TONS_GENRE = { validation: "jaune", go: "bleu", question: "bleu", bloque: "rouge", terminal: "rouge", a_decider: "jaune", a_lire: "gris", fusion: "gris", besoin: "jaune" };
const LIBELLES_GENRE = { validation: "Validation", go: "Go", question: "Question", bloque: "Bloqué", terminal: "Terminal", a_decider: "Décision", a_lire: "À lire", fusion: "Fusion", besoin: "Besoin" };
function decisions(d) {
  const sortie = el("div", { class: "page" });
  for (const [pour, titre] of [["toi", "T'attend"], ["agent", "Attend un agent"]]) {
    const mes = d.decisions.filter(x => x.pour === pour);
    sortie.append(bloc(titre, mes.length, mes.length ? tableau(["Type", "Objet", "Détail", "Depuis", ""], mes.map(x => [
      etiquette(TONS_GENRE[x.genre] || "gris", LIBELLES_GENRE[x.genre] || x.genre), el("strong", {}, x.titre),
      el("div", {}, x.detail ? el("div", {}, x.detail) : null, x.commande ? el("code", {}, x.commande) : null),
      el("span", { class: "chiffre" }, x.quand || "—"), x.lien ? ouvrir(x.lien.vue, x.lien.a) : pale("")]))
      : el("p", { class: "vide" }, pour === "toi" ? "Rien n'attend ton geste." : "—")));
  }
  return sortie;
}
function echanges(d) {
  const l = d.echanges.slice(-200).reverse();
  return bloc("Échanges" + (d.agent ? " de " + d.agent.nom : ""), d.echanges.length, l.length ? tableau(["Quand", "De", "À", "Genre", "Texte"], l.map(e => [
    el("span", { class: "chiffre" }, court(e.quand)), el("strong", {}, e.de.nom), e.a.nom, etiquette("gris", e.genre), el("div", { class: "texte-long" }, e.texte)]))
    : el("p", { class: "vide" }, "Aucun échange pour l'instant."));
}

// ── gabarit générique (toutes les autres vues, y compris celles à venir) : jamais un champ vide, jamais un libellé répété ──
function resoudre(s, v) {
  if (!s) return {};
  if (s.$ref) {
    const [fichier, chemin] = s.$ref.split("#");
    const racine = fichier ? SCHEMAS[fichier.replace(".schema.json", "")] : null;
    let cible = racine || {};
    for (const p of (chemin || "").split("/").filter(Boolean)) cible = (cible || {})[p];
    return Object.assign({}, cible, s, { $ref: undefined });
  }
  if (s.anyOf) {
    const branches = s.anyOf.map(b => resoudre(b, v));
    const b = v === null ? branches.find(x => x.type === "null") : branches.find(x => x.type !== "null");
    return Object.assign({}, b || {}, { "x-rendu": s["x-rendu"], "x-libelle": s["x-libelle"] });
  }
  return s;
}
function rendre(s, v) {
  if (vide(v)) return null;
  const r = (s || {})["x-rendu"];
  if (r && RENDUS[r]) return RENDUS[r](resoudre(s, v), v);
  if (typeof v === "object") return objet(resoudre(s, v), v);
  return texte(v);
}
function visibles(s, v) {
  return Object.entries((s && s.properties) || {}).filter(([k, sous]) => sous["x-rendu"] !== "cache" && k in v && !vide(v[k]));
}
function objet(s, v) {
  if (vide(v)) return null;
  const dl = el("dl", { class: "proprietes" });
  for (const [k, sous] of visibles(s, v)) {
    const r = rendre(sous, v[k]);
    if (r) dl.append(el("dt", {}, sous["x-libelle"] || k), el("dd", {}, r));
  }
  return dl;
}
const SIMPLES = new Set(["texte", "nombre", "quand", "oui-non", "ton", "agent", "statuts", "lien", "cache"]);
function liste(s, v) {
  if (vide(v)) return null;
  if (!Array.isArray(v)) return objet(resoudre(s, v), v);
  const item = resoudre(s.items || {}, v[0]);
  if (s.items && s.items["x-rendu"]) return el("div", { class: "liste-lignes" }, ...v.map(x => el("div", { class: "ligne-liste" }, rendre(s.items, x))));
  const cols = Object.entries(item.properties || {}).filter(([k, p]) => p["x-rendu"] !== "cache" && v.some(x => x && !vide(x[k])));
  if (cols.length && cols.every(([, p]) => SIMPLES.has(p["x-rendu"])))   // éléments plats : un tableau, les libellés une seule fois
    return tableau(cols.map(([k, p]) => p["x-libelle"] || k), v.map(x => cols.map(([k, p]) => rendre(p, x[k]) || pale("—"))));
  return el("div", { class: "liste-lignes" }, ...v.map(x => (x !== null && typeof x === "object") ? el("div", { class: "ligne-liste" }, objet(resoudre(s.items || {}, x), x)) : texte(x)));
}
function generique(s, d) {
  const sortie = el("div", { class: "page" });
  for (const [k, sous] of visibles(s, d)) {
    const r = rendre(sous, d[k]);
    if (r) sortie.append(bloc(sous["x-libelle"] || k, Array.isArray(d[k]) ? d[k].length : null, r));
  }
  if (!sortie.childNodes.length) sortie.append(el("p", { class: "vide" }, "Rien à montrer."));
  return sortie;
}

// ── échanges avec le serveur ──
// UNE seule demande en vol pour toute la page (14/10 : les rafraîchissements se chevauchaient, les commandes lentes
// s'empilaient côté serveur — 503 puis 504) : chaque lecture attend la fin de la précédente.
let file = Promise.resolve();
function enFile(f) { const p = file.then(f, f); file = p.catch(() => {}); return p; }
function lire(chemin) { return enFile(() => lire_(chemin)); }
async function lire_(chemin) {
  const r = await fetch(chemin, { credentials: "same-origin" });
  const corps = await r.json().catch(() => ({ erreur: "réponse illisible" }));
  if (!r.ok) throw new Error(corps.erreur || ("erreur " + r.status));
  return corps;
}
async function connexion() {
  const m = location.hash.match(/jeton=([A-Za-z0-9_-]+)/);
  if (!m) return;
  history.replaceState(null, "", location.pathname);                   // le jeton quitte la barre d'adresse tout de suite
  await fetch("/connexion", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ jeton: m[1] }) });
}
async function schema(nom) {
  if (!SCHEMAS[nom]) SCHEMAS[nom] = await lire("/api/schema/" + nom);
  return SCHEMAS[nom];
}
const donnees = (type, a) => lire("/api/vue/" + type + (a ? "?a=" + encodeURIComponent(a) : "")).then(r => r.donnees);
const existe = type => VUES.some(v => v.type === type && v.donnees);

// ── navigation, en-tête, vue courante ──
function dire(t, erreur) { const e = document.getElementById("etat"); e.textContent = t; e.className = erreur ? "t-rouge" : "pale"; }
function age() { if (dernier && !document.getElementById("etat").classList.contains("t-rouge")) dire("Mis à jour il y a " + Math.round((Date.now() - dernier) / 1000) + " s"); }
// courant = { mode : "berger" | "agent" | "objet", type, a (agent ou objet), retour (la vue d'avant un objet) }
function entree(attrs, trace, libelle, n, actif) {
  return el("button", { type: "button", class: "entree", "aria-current": actif ? "page" : "false", ...attrs }, icone(trace),
            el("span", { class: "entree-libelle" }, libelle), n ? el("span", { class: "compteur" }, String(n)) : null);
}
function navigation() {
  const nav = document.getElementById("onglets"); nav.replaceChildren();
  for (const v of VUES.filter(v => v.onglet === "berger")) {
    nav.append(entree({ "data-vue": v.type }, ICONES[v.type] || ICONE_GENERIQUE, v.titre, COMPTES[v.type], !!courant && courant.mode === "berger" && courant.type === v.type));
  }
  nav.append(entree({ "data-agents": "1", class: "entree seulement-mobile" }, ICONE_AGENTS, "Agents", 0, !!courant && courant.mode === "agent"));
  const la = document.getElementById("liste-agents"); la.replaceChildren();
  for (const a of AGENTS) la.append(entree({ "data-agent": a.id }, ICONE_AGENTS, ((a.icone || "") + " " + a.nom).trim(), 0, !!courant && courant.mode === "agent" && courant.a === a.id));
  const sous = document.getElementById("agents"); sous.replaceChildren();
  sous.hidden = !(courant && courant.mode === "agent");
  if (!sous.hidden) {
    const choix = el("div", { class: "choix-agent seulement-mobile" }, ...AGENTS.map(a => el("button", { type: "button", "data-agent": a.id, "aria-pressed": String(courant.a === a.id) }, a.nom)));
    sous.append(choix, ...VUES.filter(v => v.onglet === "agent").map(v => el("button", { type: "button", "data-vue-agent": v.type, "aria-pressed": String(courant.type === v.type) }, v.titre)));
  }
  const g = document.getElementById("global"); g.replaceChildren();
  for (const x of GLOBAL) g.append(el("span", { class: "etat" }, el("span", { class: "point p-" + x.ton }), x.texte));
  const toi = Object.values(DEDIES).find(x => x.compteur && x.compteur[1] === pourToi);
  const n = toi ? COMPTES[Object.keys(DEDIES).find(k => DEDIES[k] === toi)] : 0;
  if (n) g.append(el("span", { class: "etat" }, etiquette("jaune", String(n)), " t'attend"));
}
async function compter() {
  const globaux = [];
  for (const [type, ded] of Object.entries(DEDIES)) {
    if (!existe(type)) continue;
    try {
      if (ded.compteur) COMPTES[type] = ded.compteur[1](await donnees(ded.compteur[0]));
      if (ded.global) globaux.push(ded.global(await donnees(type)));
    } catch (e) { COMPTES[type] = 0; }
  }
  GLOBAL = globaux; navigation();
}
async function afficher(auto) {
  if (!courant || document.hidden) return;
  if (auto && affiche === courant && (DEDIES[courant.type] || {}).fixe) return;   // vue fixe déjà affichée : on ne la recharge pas
  if (enVol) { encore = true; return; }                                   // une vue à la fois ; un clic pendant ce temps est rejoué ensuite
  enVol = true; encore = false;
  const vise = courant;
  try {
    const ded = vise.mode !== "agent" ? DEDIES[vise.type] : null;
    const d = await donnees(vise.type, vise.a);
    let corps;
    if (ded && ded.rendre) {
      const autres = {};
      for (const t of ded.autres || []) autres[t] = await donnees(t);
      corps = ded.rendre(d, autres);
    } else corps = generique(await schema(vise.type), d);
    if (courant !== vise) return;                                          // la vue a changé pendant la lecture : on n'affiche pas l'ancienne
    const titre = VUES.find(v => v.type === courant.type);
    document.getElementById("titre-vue").textContent = (titre ? titre.titre : courant.type) + (courant.mode === "agent" ? " · " + (AGENTS.find(a => a.id === courant.a) || {}).nom : "");
    document.getElementById("vue").replaceChildren(
      ...(courant.retour ? [el("button", { type: "button", class: "retour", "data-retour": "1" }, "Retour")] : []), corps);
    affiche = courant; dernier = Date.now(); dire("Mis à jour il y a 0 s"); document.getElementById("vue").classList.remove("perime");
  } catch (e) {
    // une erreur se dit, et la dernière vue reçue reste affichée, marquée « données du HH:MM » (jamais une page vide)
    const h = dernier ? new Date(dernier).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : null;
    dire((h ? "Données de " + h + " — " : "") + String(e.message || e), true);
    if (dernier && courant === vise) document.getElementById("vue").classList.add("perime");
  } finally { enVol = false; if (encore) afficher(); }
}
// Temps réel (§6 quater) : un flux EventSource (même cookie, même origine) dit « change » quand les données bougent ; la
// page relit alors sa vue (la même lecture qu'à la main). Tant que le flux est ouvert, la boucle de 5 s se tait ; s'il
// tombe, elle reprend, et EventSource se reconnecte seul ; refusé (503 : trop de flux), un nouvel essai 30 s plus tard.
// Un flux « ouvert » mais muet plus de 40 s (battement toutes les 25 s ; un relais qui le retient) ne compte plus : la boucle reprend.
const fluxVivant = () => fluxOuvert && Date.now() - signal < 40000;
let flux = null, fluxOuvert = false, signal = 0;   // signal : dernier message du flux (ouverture, change, battement)
function ouvrirFlux() {
  if (typeof EventSource === "undefined" || flux) return;
  flux = new EventSource("/api/flux");
  flux.onopen = () => { fluxOuvert = true; signal = Date.now(); };
  flux.addEventListener("change", () => { signal = Date.now(); afficher(true); compter(); });
  flux.addEventListener("battement", () => { signal = Date.now(); });
  flux.onerror = () => {
    fluxOuvert = false;
    if (flux.readyState === 2) { flux = null; setTimeout(ouvrirFlux, 30000); }      // fermé pour de bon : on réessaie plus tard
  };
}
function boucle(f, ms) { setTimeout(async () => { try { await f(); } finally { boucle(f, ms); } }, ms); }   // la suivante APRÈS la fin
document.addEventListener("click", ev => {
  const b = ev.target.closest("button"); if (!b) return;
  const vueAgent = (VUES.find(v => v.onglet === "agent") || {}).type;
  if (b.dataset.vue) courant = { mode: "berger", type: b.dataset.vue };
  else if (b.dataset.agents) courant = { mode: "agent", type: vueAgent, a: (AGENTS[0] || {}).id };
  else if (b.dataset.agent) courant = { mode: "agent", type: courant && courant.mode === "agent" ? courant.type : vueAgent, a: b.dataset.agent };
  else if (b.dataset.vueAgent) courant = { mode: "agent", type: b.dataset.vueAgent, a: courant.a };
  else if (b.dataset.objet) courant = { mode: "objet", type: b.dataset.objet, a: b.dataset.a, retour: courant.mode === "objet" ? courant.retour : courant };
  else if (b.dataset.retour) courant = courant.retour;
  else return;
  navigation(); afficher(); window.scrollTo(0, 0);
});
document.addEventListener("visibilitychange", () => { if (!document.hidden) afficher(true); });

async function demarrer() {
  try {
    await connexion();
    await schema("communs");
    VUES = (await lire("/api/vues")).vues;
    AGENTS = (await lire("/api/etat")).donnees.agents.map(x => x.agent);
    document.getElementById("rubrique-agents").hidden = !AGENTS.length;
    courant = { mode: "berger", type: VUES.filter(v => v.onglet === "berger")[0].type };
    navigation(); await afficher(); await compter();
    boucle(() => fluxVivant() ? null : afficher(true), 5000);                          // repli : la vue visible, 5 s APRÈS la fin de la précédente
    ouvrirFlux();
    boucle(compter, 30000); setInterval(age, 1000);
  } catch (e) {
    dire(String(e.message || e), true);
  }
}
demarrer();
