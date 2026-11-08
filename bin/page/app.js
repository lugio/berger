// Interface web de Berger, v2 (spec docs/plans/2026-11-03-interface-web-v2-spec.md, lot 1 : lecture ; finition :
// docs/plans/2026-11-05-interface-finition-ui-spec.md — composants partagés, À lire en deux volets, décision en 2 clics) — sans cadriciel ni étape
// de construction. La MAQUETTE du propriétaire fait foi (docs/plans/interface-web-v2/maquette-accueil.html) : Accueil court
// (« pour toi » en tête, le reste replié), Tableau, À lire, Coulisses, une page par agent ; menu latéral repliable (mémorisé
// sur ce poste) ; fenêtres de détail ; 1440 / 820 / 390 px sans débordement ; icônes SVG au trait, AUCUN émoji, AUCUNE bordure
// colorée à gauche.
// La page ne connaît AUCUNE règle : chaque donnée vient d'une vue (berger vue <type> --json) ; la navigation vient de /api/vues.
// Les icônes et les libellés viennent de la SOURCE COMMUNE avec Herdr (/icones.json = bin/page/icones.json) : aucun tracé ici.
// Les vues ne sont nommées que dans le bloc DEDIES. Tout texte venu des données est inséré comme texte (textContent), jamais
// comme HTML, et nettoyé : sans émoji, empreintes Git courtes, phrases coupées proprement (le texte entier est dans la fenêtre).
"use strict";

// ── Les rendus connus : un par mot « x-rendu » des schémas (tests/interface.py exige que chaque mot employé soit ici) ──
const RENDUS = {
  texte: (s, v) => texte(s && s.enum ? humain(v) : v),
  nombre: (s, v) => texte(v === null || v === undefined ? "" : String(v)),
  quand: (s, v) => texte(court(v)),
  "oui-non": (s, v) => texte(v === true ? "oui" : v === false ? "non" : ""),
  ton: (s, v) => v ? badge(v, v) : null,
  agent: (s, v) => v ? nomAgent(v) : null,
  statuts: (s, v) => statuts(v),
  checklist: (s, v) => travail(v),
  validation: (s, v) => ecriture(v),
  lignes: (s, v) => lignes(v),
  liste: (s, v) => liste(s, v),
  lien: (s, v) => v ? ouvrir(v.vue, v.a) : null,
  markdown: (s, v) => markdown(v),
  cache: () => null,
};

// ── Rendus dédiés des vues principales : la clé est le type de la vue ; `absorbe` = vues du même onglet que ce rendu montre
// déjà (elles ne se répètent pas dessous) ; `replie` = vue lue seulement quand on déplie son bloc ; `compteur` = [vue,
// nombre affiché dans la navigation] ; `global` = ce que la vue donne à l'en-tête ; `fixe` = vue affichée une fois, sans
// relecture automatique ; `fenetre` = vue d'objet ouverte dans une fenêtre de détail. ──
const G_DECIDER = ["valider", "refuser"], G_LU = ["lu"];               // gestes du propriétaire d'une fenêtre (lot 2)
const DEDIES = {
  livrables: { rendre: d => livrables(d.livrables, "livrable") },
  documents: { rendre: d => ged(d.documents, "livrable"), fixe: true },  // fixe : la recherche en cours n'est pas effacée toutes les 5 s
  livrable: { rendre: d => livrable(d), fixe: true, fenetre: true, large: true },   // fixe : la maquette ne se recharge pas ; large : sa fenêtre aussi
  accueil: { absorbe: ["synthese", "tokens"], replie: "tokens", rendre: d => accueil(d, "document"),
             compteur: ["accueil", pourToi] },
  colonnes: { rendre: d => colonnes(d) },
  alire: { rendre: d => alire(d.documents, "document"), compteur: ["accueil", d => d.a_lire.length], plein: true },
  echanges: { rendre: d => echanges(d) },
  courtier: { global: etatCourtier },
  document: { fenetre: true, gestes: G_LU, rendre: d => lecture(d), sous: d => metaDocument(d), titre: d => d.titre },   // titre : celui du document
  validation: { fenetre: true, gestes: G_DECIDER }, demande: { fenetre: true },   // gestes : lot 2
  reglages: { rendre: d => reglages(d), fixe: true },                   // fixe : relu à chaque ouverture de l'onglet, pas en direct
  extensions: { rendre: d => extensions(d), fixe: true },               // lot 2 des extensions : lecture seule, relue à chaque ouverture
};

// ── Rendus dédiés des pages d'AGENT (une vue d'onglet « agent ») : `pour` = l'agent a-t-il cette page (sinon son sous-onglet est caché). ──
const DEDIES_AGENT = {
  conversation: { rendre: d => conversation(d), pour: a => CONVERSATIONS.includes(a), apres: (meme, enBas) => { if ((!meme || enBas) && document.documentElement) window.scrollTo(0, document.documentElement.scrollHeight); } },
};

let SOURCE = { icones: {}, onglets: {}, roles: {}, etats: {}, libelles: {} };   // la source commune (/icones.json), lue au démarrage
let CONVERSATIONS = [], MESSAGES = false;                                // MESSAGES : écrire à un agent permis ici (127.0.0.1, actions actives)                                                  // les agents dont la page « Conversation » est ouverte (/api/conversations)
let SCHEMAS = {}, VUES = [], AGENTS = [], COMPTES = {}, GLOBAL = [], courant = null, affiche = null, enVol = false, encore = false, dernier = null;
const L = k => SOURCE.libelles[k] || k;                                    // un libellé de la source commune
function etatCourtier(d) { return { texte: d.actif ? "Courtier actif" : "Courtier arrêté", ton: d.actif ? "vert" : "rouge" }; }
function pourToi(d) { return d.attentes.filter(e => e.pour === "toi").length; }   // ce qui t'attend

// ── outils ──
// Texte propre : sans émoji (règle du propriétaire), empreintes Git courtes, blancs réduits.
const EMOJI = /[\p{Extended_Pictographic}\u{1F1E6}-\u{1F1FF}\u{FE0F}\u{200D}\u{20E3}]/gu;
function propre(t, morceau) {                                           // morceau : un bout de phrase (Markdown en ligne) — ses blancs de bord restent
  const p = String(t).replace(EMOJI, "").replace(/\b([0-9a-f]{7})[0-9a-f]{33}\b/g, "$1").replace(/[ \t]{2,}/g, " ");
  return morceau ? p : p.trim();
}
function coupe(t, n) {                                                   // phrase coupée proprement, au mot, avec « … »
  const p = propre(t); if (p.length <= n) return p;
  const c = p.slice(0, n + 1), i = c.lastIndexOf(" ");
  return (i > n * 0.6 ? c.slice(0, i) : c.slice(0, n)).replace(/[\s,;:.·—-]+$/, "") + " …";
}
function el(nom, attrs, ...enfants) {
  const n = document.createElement(nom);
  for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
  for (const e of enfants) if (e !== null && e !== undefined && e !== false) n.append(typeof e === "string" ? document.createTextNode(propre(e)) : e);
  return n;
}
const NS = "http://www.w3.org/2000/svg", FORMES = new Set(["path", "rect", "circle"]);
function icone(nom, classe) {                                            // une icône de la source commune, en SVG au trait
  const s = document.createElementNS(NS, "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("class", "icone" + (classe ? " " + classe : ""));
  const i = SOURCE.icones[nom] || SOURCE.icones.generique || { svg: [] };
  for (const [forme, attrs] of i.svg) {
    if (!FORMES.has(forme)) continue;
    const f = document.createElementNS(NS, forme);
    for (const [k, v] of Object.entries(attrs)) f.setAttribute(k, v);
    s.append(f);
  }
  return s;
}
const iconeOnglet = libelle => (SOURCE.onglets[libelle] || {}).icone;
const iconeAgent = a => SOURCE.roles[a.role] || SOURCE.roles.agent;
// Le nom de la barre latérale (QA 05/11 : « Berger · interface-l… ») : un développeur s'y nomme par son SUJET, l'icône d'équipe (clé)
// dit le reste ; le nom entier reste au survol (title) et pour les lecteurs d'écran (aria-label).
const nomCourt = a => a.role === "developpeur" && / · /.test(a.nom) ? a.nom.slice(a.nom.lastIndexOf(" · ") + 3) : a.nom;
const entreeAgent = (a, point) => entree({ "data-agent": a.id, title: a.nom, "aria-label": a.nom }, iconeAgent(a), nomCourt(a), 0, !!point && point.actif, point ? point.ton : TONS_ETAT[a.etat] || "gris");
function nomAgent(a) { return el("span", { class: "nom-agent" }, icone(iconeAgent(a)), el("span", {}, a.nom)); }
function texte(v) { return vide(v) ? null : el("span", {}, String(v)); }
function vide(v) { return v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length); }
function pale(t) { return el("span", { class: "pale" }, t); }
// ── composants partagés (spec finition §3) : une définition chacun, réutilisés partout (le lot 3 aussi) ──
function badge(ton, t) { return el("span", { class: "badge ton-" + (ton || "gris") }, t); }      // Badge d'état : un fond teinté, jamais une bordure
const etiquette = badge;
// Bouton : quatre genres. Le genre d'une action est FIXE (Valider et Répondre primaires, Voir secondaire, Refuser danger,
// Annuler lien) : le même geste a la même apparence sur toutes les cartes.
const GENRES = { valider: "primaire", repondre: "primaire", envoyer: "primaire", voir: "secondaire", ouvrir: "secondaire", lu: "secondaire",
                 refuser: "danger", annuler: "lien", detail: "lien" };
function bouton(genre, libelle, attrs, ...enfants) {
  return el("button", { type: "button", ...(attrs || {}), class: "bouton " + (GENRES[genre] || genre) + (attrs && attrs.class ? " " + attrs.class : "") }, ...enfants, libelle);
}
function chargement() { return el("p", { class: "chargement", role: "status" }, L("chargement")); }   // visible après 300 ms (CSS)
// Liste clé/valeur : une grille compacte (deux colonnes sur bureau, une sur mobile) ; paires = [[libellé, nœud]…]
function cles(paires, uneColonne) {
  const dl = el("dl", { class: "cles" + (uneColonne ? " une-colonne" : "") });
  for (const [k, v] of paires) dl.append(el("div", {}, el("dt", {}, k), el("dd", {}, v)));
  return dl;
}
// Libellés humains : aucune clé interne (« a_decider ») n'est affichée telle quelle.
function humain(v) { const t = String(v); return LIBELLES_GENRE[t] || (/^[a-z]+(_[a-z]+)+$/.test(t) ? (t[0].toUpperCase() + t.slice(1)).replace(/_/g, " ") : t); }
function bloc(titre, compte, ...corps) {
  return el("section", { class: "bloc" }, el("header", {}, el("h2", {}, titre), compte !== null && compte !== undefined ? el("span", { class: "nombre" }, String(compte)) : null),
            el("div", { class: "corps" }, ...corps));
}
function replie(titre, nomIcone, resume, corps, ouvert, cle) {            // un bloc replié (« Le reste ») : <details>, ouvert à la demande
  const d = el("details", { class: "replie", "data-cle": cle || titre, ...(ouvert ? { open: "" } : {}) },   // la clé : son ouverture survit au rafraîchissement
               el("summary", {}, el("span", { class: "titre-replie" }, icone(nomIcone), titre), el("span", { class: "resume" }, resume || "", icone("chevron", "petite"))));
  d.append(el("div", { class: "corps-replie" }, corps));
  return d;
}
function court(v) {                                                    // « 21:32 » aujourd'hui, sinon « 13/10 21:20 » (ou « 13/10 »)
  if (!v) return "";
  const d = new Date(v);
  if (isNaN(d)) return String(v);
  const deux = n => String(n).padStart(2, "0"), heure = deux(d.getHours()) + ":" + deux(d.getMinutes());
  if (!/T\d\d:/.test(v)) return deux(d.getDate()) + "/" + deux(d.getMonth() + 1);
  return d.toDateString() === new Date().toDateString() ? heure : deux(d.getDate()) + "/" + deux(d.getMonth() + 1) + " " + heure;
}
const TONS_ETAT = { working: "bleu", idle: "vert", done: "vert", blocked: "jaune" };
const libelleEtat = e => SOURCE.etats[e] || SOURCE.etats.ferme || "fermé";          // un état inconnu (agent fermé) : « fermé », jamais « ? »
function statuts(v) {
  if (!v || !v.length) return el("span", { class: "etat" }, el("span", { class: "point p-gris" }), libelleEtat("ferme"));
  return el("span", { class: "statuts" }, ...v.map(s => el("span", { class: "etat" }, el("span", { class: "point p-" + (TONS_ETAT[s.etat] || "gris") }), libelleEtat(s.etat))));
}
function etatPrincipal(v) { const e = (v || []).map(s => s.etat); return e.includes("blocked") ? "blocked" : e.includes("working") ? "working" : e.length && e.every(x => x in TONS_ETAT) ? e[0] : "ferme"; }
function barre(faites, total) {
  const p = total ? Math.round(100 * faites / total) : 0;
  const plein = el("span", {}); plein.style.width = Math.max(3, p) + "%";   // par le CSSOM : la politique de contenu interdit l'attribut style
  return el("div", { class: "progression" }, el("div", { class: "barre" }, plein), el("span", { class: "chiffre" }, faites + "/" + total));
}
function travail(c) {
  if (!c || c.fini) return pale("—");
  return el("div", { class: "travail" }, el("div", { class: "titre-travail" }, coupe(c.titre, 90)), barre(c.faites, c.total),
            c.bloque ? el("div", {}, etiquette("rouge", c.go ? "Go attendu" : "Bloqué"), " " + coupe(c.bloque, 140)) : null,
            c.question ? el("div", {}, etiquette("bleu", "Question"), " " + coupe(c.question, 140)) : null);
}
function ecriture(x) {
  if (!x) return null;
  const n = x.n === null ? "—" : x.n;
  return el("div", { class: "ligne-liste" }, el("div", { class: "l1" }, el("strong", {}, "n° " + n), " " + x.agent.nom + " · " + x.verbe, el("span", { class: "heure" }, court(x.demande))),
            el("div", { class: "pale" }, coupe(x.apercu, 200)),
            x.valideur ? el("div", { class: "pale" }, "attend " + x.valideur.nom) : el("div", {}, el("code", {}, "berger valider " + n)));
}
function ouvrir(vue, a, libelle, genre) { return bouton(genre || "lien", libelle || L("detail"), { "data-objet": vue, "data-a": a }); }
// Markdown : titres, listes (à puces et numérotées, un niveau d'imbrication), code en ligne et en bloc, citations, tableaux
// (qui défilent dans leur cadre) — en ÉLÉMENTS, jamais en HTML. Les liens [texte](adresse) gardent leur texte seul.
function enLigne(s) {
  return s.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").split(/(\*\*[^*]+\*\*|`[^`]+`)/).filter(Boolean).map(x =>
    x.startsWith("**") && x.endsWith("**") && x.length > 4 ? el("strong", {}, x.slice(2, -2)) : x.startsWith("`") && x.endsWith("`") && x.length > 2 ? el("code", {}, x.slice(1, -1))
      : document.createTextNode(propre(x, true)));   // « Avant **important** après » garde ses espaces
}
const PUCE = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/, CELLULES = l => l.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
function markdown(t) {
  const d = el("div", { class: "markdown" }), l = String(t || "").split("\n");
  for (let i = 0; i < l.length; i++) {
    const x = l[i];
    if (x.startsWith("```")) {                                              // bloc de code, jusqu'à la clôture
      const pre = el("pre", {}), code = el("code", {}); pre.append(code);
      for (i++; i < l.length && !l[i].startsWith("```"); i++) code.append(document.createTextNode(l[i].replace(EMOJI, "") + "\n"));
      d.append(pre); continue;
    }
    const m = x.match(/^(#{1,6})\s+(.*)/);
    if (m) { d.append(el("h" + Math.min(6, m[1].length + 2), {}, ...enLigne(m[2]))); continue; }
    if (PUCE.test(x)) {                                                     // une liste : les lignes qui suivent, retraits et suites comprises
      const racine = el(/^\d/.test(x.match(PUCE)[2]) ? "ol" : "ul", {}); let dernier = null, sous = null;
      for (; i < l.length && (PUCE.test(l[i]) || (l[i].trim() && /^\s+/.test(l[i]) && dernier)); i++) {
        const p = l[i].match(PUCE);
        if (!p) { (sous ? sous.dernier : dernier).append(" ", ...enLigne(l[i].trim())); continue; }
        if (p[1].length >= 2 && dernier) {                                  // un élément en retrait : une sous-liste du précédent
          if (!sous || sous.parent !== dernier) { sous = { parent: dernier, liste: el(/^\d/.test(p[2]) ? "ol" : "ul", {}) }; dernier.append(sous.liste); }
          sous.dernier = el("li", {}, ...enLigne(p[3])); sous.liste.append(sous.dernier);
        } else { dernier = el("li", {}, ...enLigne(p[3])); sous = null; racine.append(dernier); }
      }
      i--; d.append(racine); continue;
    }
    if (/^\s*\|/.test(x) && i + 1 < l.length && /^\s*\|?\s*:?-{2,}/.test(l[i + 1])) {   // un tableau Markdown
      const tetes = CELLULES(x), rangs = [];
      for (i += 2; i < l.length && /^\s*\|/.test(l[i]); i++) rangs.push(CELLULES(l[i]).map(c => el("span", {}, ...enLigne(c))));
      i--; d.append(tableau(tetes, rangs, true)); continue;
    }
    if (/^>\s?/.test(x)) {                                                  // une citation : les lignes « > » qui se suivent
      const q = el("blockquote", {});
      for (; i < l.length && /^>\s?/.test(l[i]); i++) { const y = l[i].replace(/^>\s?/, ""); if (y.trim()) q.append(el("p", {}, ...enLigne(y))); }
      i--; d.append(q); continue;
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(x)) { d.append(el("hr", {})); continue; }
    if (x.trim()) d.append(el("p", {}, ...enLigne(x)));
  }
  return d;
}
function lignes(v, n) {
  if (!v || !v.length) return null;
  const d = el("div", { class: "lignes" });
  for (const l of v) {
    if (Array.isArray(l)) d.append(el("div", {}, ...l.map(m => el("span", { class: m.ton ? "t-" + m.ton : "" }, n ? coupe(m.texte, n) : m.texte))));
    else { const ton = "gravite" in l ? l.gravite : ("ton" in l ? l.ton : null); d.append(el("div", { class: ton ? "t-" + ton : "" }, n ? coupe(l.texte, n) : l.texte)); }
  }
  return d;
}
function tableau(entetes, rangees, defile) {                             // rangées = [[cellule…]] ; data-label : la liste empilée du téléphone
  // defile : un tableau de document, qui défile dans son cadre (jamais la page) au lieu de s'empiler
  return el("div", { class: "table" + (defile ? "" : " empilable") }, el("table", {}, el("thead", {}, el("tr", {}, ...entetes.map(t => el("th", {}, t)))),
    el("tbody", {}, ...rangees.map(r => el("tr", {}, ...r.map((c, i) => el("td", { "data-label": entetes[i] }, c)))))));
}

// ── rendus dédiés ──
const ECRITURE = { validation: true };
const LIBELLES_GENRE = { validation: "Validation", go: "Go attendu", question: "Question", bloque: "Bloqué", terminal: "Terminal", a_decider: "À décider", a_lire: "À lire", fusion: "Fusion", besoin: "Besoin", proposition: "Proposition", propositions: "Propositions", toi: "Toi", agent: "Agent" };
function carteAttente(x) {                                               // une chose qui attend le propriétaire, en une carte
  const val = x.genre in ECRITURE && x.n !== null;                         // une écriture numérotée : son numéro en tête
  const tete = val ? "n° " + x.n : LIBELLES_GENRE[x.genre] || x.genre;
  const quoi = String(x.detail || "").split(/\s+→\s+/)[0];               // les commandes à taper sont montrées à part
  const nom = x.agent ? (AGENTS.find(a => a.id === x.agent) || { nom: x.agent }).nom : null;
  const qui = [nom, x.quand ? (/^\d{4}-\d\d-\d\d /.test(x.quand) ? court(x.quand.replace(" ", "T")) : x.quand) : null].filter(Boolean).join(" · ");
  const objet = val ? quoi : String(x.titre).split(" · ").filter(m => m !== nom).join(" · ") || x.titre;
  // le même composant d'action sur toutes les cartes : Valider (primaire : ouvre la décision, 1er clic), Répondre (primaire), Voir (secondaire)
  const agir = val ? boutonGeste("valider", x.n) : x.genre === "question" && x.agent ? boutonGeste("repondre", x.agent) : null;
  return el("div", { class: "carte decision", ...(val ? { "data-decision": String(x.n) } : {}) },
    el("div", { class: "tete" }, el("span", { class: "num" }, tete), el("span", { class: "objet" }, coupe(objet, 90)), qui ? el("span", { class: "qui date" }, qui) : null),
    !val && quoi ? el("p", {}, coupe(quoi, 180)) : null,
    el("div", { class: "boutons" }, agir,
       x.lien ? ouvrir(x.lien.vue, x.lien.a, L("voir"), "voir") : null,
       !val && !x.lien && propre(quoi).length > 180 ? bouton("voir", L("voir"), { "data-texte": quoi, "data-texte-titre": [tete, nom].filter(Boolean).join(" · ") }) : null,
       x.commande && !agir ? el("code", { class: "commande" }, x.commande) : null));
}
function carteAgent(x, vueAgent) {                                       // un agent au travail : nom, état, travail en cours
  const e = etatPrincipal(x.statuts), ck = x.checklist && !x.checklist.fini ? x.checklist : null;
  return el("button", { type: "button", class: "carte agent", "data-fenetre-agent": x.agent.id, "data-vue-agent": vueAgent || "" },
    el("span", { class: "nom" }, icone(iconeAgent(x.agent)), el("span", { class: "nom-texte" }, x.agent.nom), badge(TONS_ETAT[e] || "gris", libelleEtat(e))),
    ck ? el("span", { class: "quoi" }, coupe(ck.titre, 70) + " · " + ck.faites + "/" + ck.total) : x.derniere_action ? el("span", { class: "quoi" }, coupe(x.derniere_action, 70)) : null,
    ck ? barre(ck.faites, ck.total) : null);
}
// Tous les agents de l'Accueil (agents, puis développeurs des équipes), au même format : {agent, statuts, checklist, derniere_action}.
function tousAgents(d) {
  const devs = d.equipes.flatMap(e => e.membres.map(m => ({ agent: m.agent, statuts: m.statuts, derniere_action: m.sujet,
    checklist: m.total !== null ? { titre: m.sujet, faites: m.faites, total: m.total, fini: m.faites === m.total } : null })));
  return d.agents.concat(devs);
}
const ALERTES_VISIBLES = 5;                                              // l'Accueil reste court : le reste des alertes est replié
function accueil(d, vueDocument) {
  const toi = d.attentes.filter(x => x.pour === "toi");
  const dec = el("div", { class: "pile" }, ...toi.map(carteAttente));
  if (!toi.length) dec.append(el("div", { class: "vide" }, L("rien")));
  const alerte = a => el("button", { type: "button", class: "alerte a-" + a.gravite, "data-alerte": a.domaine + " — " + a.texte },
    icone(a.gravite === "rouge" ? "alerte" : "attention"), el("span", { class: "alerte-texte" }, coupe(a.domaine + " : " + a.texte, 120),
      el("small", {}, (a.nouveau ? "nouveau · " : "") + "depuis " + court(a.depuis))));
  const triees = d.alertes.filter(a => a.gravite === "rouge").concat(d.alertes.filter(a => a.gravite !== "rouge"));   // le rouge d'abord
  const al = el("div", { class: "pile" }, ...triees.slice(0, ALERTES_VISIBLES).map(alerte));
  if (triees.length > ALERTES_VISIBLES) al.append(replie((triees.length - ALERTES_VISIBLES) + " autres alertes", "attention", "", el("div", { class: "pile" }, ...triees.slice(ALERTES_VISIBLES).map(alerte)), false, "alertes-autres"));
  if (!d.alertes.length) al.append(el("div", { class: "vide" }, L("aucune_alerte")));
  const tous = tousAgents(d), vueAgent = (VUES.find(v => v.onglet === "agent") || {}).type;
  const actifs = tous.filter(x => ["working", "blocked"].includes(etatPrincipal(x.statuts)) || (x.checklist && !x.checklist.fini));
  const repos = tous.filter(x => !actifs.includes(x));
  const trav = el("div", { class: "pile" }, ...actifs.map(x => carteAgent(x, vueAgent)));
  if (!actifs.length) trav.append(el("div", { class: "vide" }, L("personne_au_travail")));
  const lis = el("ul", { class: "liste" }, ...d.a_lire.map(x => el("li", { class: "non-lu" }, el("button", { type: "button", class: "ligne-bouton", "data-objet": vueDocument, "data-a": x.id },
    el("span", { class: "point p-bleu" }), el("span", { class: "doc-titre" }, coupe(x.titre, 90))))));
  if (!d.a_lire.length) lis.append(el("li", { class: "pale" }, "Rien de nouveau."));
  const rep = el("ul", { class: "liste" }, ...repos.map(x => el("li", {}, el("button", { type: "button", class: "ligne-bouton", "data-fenetre-agent": x.agent.id, "data-vue-agent": vueAgent || "" },
    icone(iconeAgent(x.agent)), el("span", { class: "doc-titre" }, x.agent.nom), el("span", { class: "d" }, libelleEtat(etatPrincipal(x.statuts)))))));
  const conso = el("div", { class: "a-deplier", "data-deplier": DEDIES.accueil.replie }, chargement());
  const reste = el("section", { class: "o4" }, el("h2", {}, L("le_reste")),
    replie("À lire", iconeOnglet("À lire"), d.a_lire.length ? d.a_lire.length + " nouveau" + (d.a_lire.length > 1 ? "x" : "") : "rien de nouveau", lis),
    replie(L("au_repos"), "equipe", coupe(repos.map(x => x.agent.nom).join(", ") || "aucun", 60), rep),
    replie(L("conso"), "conso", "", conso));
  return el("div", { class: "grille" },
    el("div", { class: "colonne-g" }, el("section", { class: "o1" }, el("h2", {}, L("a_decider")), dec), reste),
    el("div", { class: "colonne-d" }, el("section", { class: "o2" }, el("h2", {}, L("alertes")), al), el("section", { class: "o3" }, el("h2", {}, L("au_travail")), trav)));
}
// À lire (spec finition §7) : au-delà de 1280 px, deux volets — la liste (360 px) et le document ouvert à droite ; en dessous, la
// liste pleine largeur, et le document s'ouvre dans la Fenêtre. Un document non lu est en gras avec un point d'état ; un document
// lu garde un poids normal et un contraste AA ; la date et l'agent sont sur une ligne douce.
let LECTURE = null, VOLET_LU = null;                                      // le document ouvert dans le volet (son id), gardé d'un rafraîchissement à l'autre ; ses données affichées
const DEUX_VOLETS = "(min-width: 1281px)";
const deuxVolets = () => typeof matchMedia === "function" && matchMedia(DEUX_VOLETS).matches;
function alire(docs, vueDocument) {
  const l = el("ul", { class: "liste carte-liste" });
  if (LECTURE && !docs.some(x => x.id === LECTURE)) LECTURE = null;
  for (const x of docs) {
    l.append(el("li", { class: x.lu ? "lu" : "non-lu" }, el("button", { type: "button", class: "ligne-bouton", "data-objet": vueDocument, "data-a": x.id, "data-volet": "1", "aria-current": String(x.id === LECTURE) },
      el("span", { class: "point " + (x.lu ? "p-vide" : "p-bleu"), title: x.lu ? L("lu") : L("non_lu") }),
      el("span", { class: "doc-texte" }, el("span", { class: "doc-titre" }, coupe(x.titre, 110)),
        el("span", { class: "doc-meta" }, (x.auteur ? x.auteur.nom : "commun") + " · " + court(x.date) + (x.lu ? " · " + L("lu") : "") + (x.regle ? " · réglé" : ""))))));
  }
  if (!docs.length) l.append(el("li", { class: "vide" }, "Rien à lire."));
  const premier = docs.find(x => !x.lu) || docs[0];
  return el("div", { class: "deux-volets" }, el("section", { class: "volets-liste", "aria-label": "Documents à lire" }, l),
            el("section", { class: "volet-lecture", "aria-label": "Document ouvert", "data-vue": vueDocument, "data-doc": LECTURE || (premier ? premier.id : "") }, docs.length ? chargement() : pale(L("choisir_document"))));
}
// Un document à lire : un en-tête d'une ligne (« agent · date · lu »), puis le texte (16 px, interligne 1,6, 75 caractères par ligne).
// Convention de fond : « **En bref** : … » puis « **Pour toi** : … » sont montrés en tête, dans un encadré doux ; la section
// « ## Détail » (et ce qui suit) est repliée (<details>). Un document sans cette forme s'affiche tel quel.
function metaDocument(d) { return [d.auteur ? d.auteur.nom : "commun", court(d.date), d.lu ? L("lu") : L("non_lu")].join(" · "); }
const BREF = /^\*\*En bref\*\*\s*:/i, POUR_TOI = /^\*\*Pour toi\*\*\s*:/i, DETAIL = /^##\s+D[ée]tails?\s*$/i;
function forme(texte, titre) {                                            // → {essentiel: [lignes] | null, tete: [lignes], detail: [lignes] | null}
  let l = String(texte || "").split("\n");
  const h1 = l.findIndex(x => x.trim());
  if (h1 >= 0 && /^#\s+/.test(l[h1]) && (!titre || propre(l[h1].replace(/^#\s+/, "")) === propre(titre)) && l.slice(h1 + 1).some(x => x.trim()))
    l = l.slice(h1 + 1);                                                  // le titre est déjà dans l'en-tête (gardé s'il est tout le document)
  const iDetail = l.findIndex(x => DETAIL.test(x.trim()));
  const tete = iDetail >= 0 ? l.slice(0, iDetail) : l, detail = iDetail >= 0 ? l.slice(iDetail + 1) : null;
  const paragraphe = re => {                                              // la ligne « **En bref** : … » et ses suites, jusqu'à la ligne vide
    const i = tete.findIndex(x => re.test(x.trim())); if (i < 0) return null;
    let j = i + 1; while (j < tete.length && tete[j].trim() && !/^(#|\*\*[^*]+\*\*\s*:)/.test(tete[j].trim())) j++;
    return [i, j];
  };
  const b = paragraphe(BREF), p = paragraphe(POUR_TOI);
  if (!b || !p) return { essentiel: null, tete: l, detail: null };
  const pris = new Set(); for (const [i, j] of [b, p]) for (let k = i; k < j; k++) pris.add(k);
  return { essentiel: [tete.slice(...b).join(" "), tete.slice(...p).join(" ")], tete: tete.filter((x, k) => !pris.has(k)), detail };
}
function lecture(d) {
  const f = forme(d.texte, d.titre), a = el("article", { class: "lecture" });
  if (f.essentiel) a.append(el("div", { class: "essentiel" }, ...f.essentiel.map(x => el("p", {}, ...enLigne(x.trim())))));
  a.append(markdown(f.tete.join("\n")));
  if (f.detail) a.append(el("details", { class: "detail", "data-cle": "detail" }, el("summary", {}, icone("chevron", "petite"), L("detail_replie")), markdown(f.detail.join("\n"))));
  if (d.tronque) a.append(pale("… coupé à 200 Ko"));
  return a;
}
const ORIGINES = { commun: "Commun", projet: "Projets d'équipe", travail: "Dossiers de travail", a_lire: "À lire", branche: "Branches en cours" };
const IMAGES = ["png", "jpeg", "gif", "webp"];
function ou(x) { return [ORIGINES[x.origine] || x.origine, x.branche ? x.projet + " · " + x.branche : null, x.chemin].filter(Boolean).join(" · "); }
function livrables(l, vueLivrable) {
  const liste = el("div", { class: "liste-lignes" });
  for (const x of l) {
    liste.append(el("div", { class: "ligne-liste doc" }, genre(x.genre),
      el("div", { class: "doc-texte" }, el("div", { class: "doc-titre" }, coupe(x.titre, 110)), pale((x.auteur ? x.auteur.nom : "commun") + " · " + court(x.date) + " · " + coupe(ou(x), 90))),
      ouvrir(vueLivrable, x.id, L("ouvrir"))));
  }
  if (!l.length) liste.append(el("p", { class: "vide" }, "Aucun livrable : les agents déposent specs, maquettes et rapports dans la bibliothèque (travail/<sujet>/) ou À lire."));
  return el("div", { class: "page" }, bloc("Specs, maquettes et rapports", l.length, liste));
}
function genre(g) { return etiquette(g === "html" ? "bleu" : g === "pdf" ? "jaune" : "gris", g === "html" ? "maquette" : IMAGES.includes(g) ? "image" : g); }
// Documents (mini GED, consultation seule) : rangés par origine puis par dossier ; la recherche filtre par nom ce qui est
// déjà reçu (présentation seulement : aucune donnée calculée, aucune requête de plus).
function ged(l, vueDocument) {
  const sans = t => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const lignes_ = [], corps = el("div", { class: "page" });
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
      b.append(el("div", { class: "sous-titre" }, coupe(d, 90)));
      for (const x of xs) {
        const ligne = el("div", { class: "ligne-liste doc", "data-nom": sans(x.titre + " " + x.chemin) }, genre(x.genre),
          el("div", { class: "doc-texte" }, el("div", { class: "doc-titre" }, coupe(x.titre, 110)), pale(coupe(x.chemin.slice(x.chemin.lastIndexOf("/") + 1), 60) + " · " + court(x.date) + " · " + x.taille + " octets")),
          ouvrir(vueDocument, x.id, L("ouvrir")));
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
  const tete = el("div", { class: "pale" }, (d.auteur ? d.auteur.nom : "commun") + " · " + court(d.date) + " · " + coupe(ou(d), 90) + " · " + d.taille + " octets");
  let corps;
  if (d.texte !== null) corps = el("div", {}, markdown(d.texte), d.tronque ? pale("… coupé à 200 Ko") : null);
  else if (d.genre === "html") corps = el("div", {}, el("iframe", { class: "cadre-livrable", sandbox: "allow-scripts", src: brut, title: d.titre, referrerpolicy: "no-referrer" }),
                                          el("a", { href: brut, target: "_blank", rel: "noopener noreferrer" }, "Ouvrir seul dans un onglet"));
  else if (d.genre === "pdf") corps = el("a", { href: brut, target: "_blank", rel: "noopener noreferrer" }, "Ouvrir le PDF dans un onglet");
  else if (IMAGES.includes(d.genre)) corps = el("img", { class: "image-document", src: brut, alt: d.titre });
  else corps = el("a", { href: brut, download: "" }, "Télécharger");
  return el("div", { class: "page" }, tete, corps);
}
// Tableau (spec finition §6) : pour chaque carte, l'action attendue en premier (badge), le reste en texte doux, 3 lignes au plus,
// puis « Voir » (la carte entière dans une Fenêtre). L'action attendue est la première ligne en jaune ou en rouge ; une carte
// mise en avant (vif) attend le propriétaire.
const LIGNES_CARTE = 3;
const texteLigne = l => Array.isArray(l) ? l.map(m => m.texte).join("") : l.texte;
const tonLigne = l => (Array.isArray(l) ? l.map(m => m.ton) : ["gravite" in l ? l.gravite : "ton" in l ? l.ton : null]).find(t => t === "rouge" || t === "jaune") || null;
function colonnes(d) {
  const g = el("div", { class: "kanban" });
  for (const c of d.colonnes) {
    const mes = d.cartes.filter(x => x.colonne === c.cle);
    g.append(el("section", { class: "colonne" }, el("h3", {}, el("span", { class: "point p-" + c.ton }), el("span", { class: "col-titre" }, c.libelle), el("span", { class: "nombre" }, String(mes.length))),
      ...mes.map(x => {
        const k = x.lignes.findIndex(l => tonLigne(l)), attendu = k >= 0 ? x.lignes[k] : null;
        const reste = x.lignes.filter((l, j) => j !== k);
        const lu = propre(texteLigne(attendu || [])).replace(/^[\u25b2\u26a0\u2717\u25cb\u25cf\u00b7\s]+/, "");
        return el("div", { class: "mini" + (x.vif ? " vif" : "") },
          attendu ? el("span", { class: "badge attendu ton-" + tonLigne(attendu) }, coupe(lu, 60)) : x.vif ? badge("bleu", L("attend_toi")) : null,
          el("strong", {}, coupe(x.titre, 60)), lignes(reste.slice(0, LIGNES_CARTE), 90),
          reste.length > LIGNES_CARTE || attendu ? bouton("voir", L("voir"), { "data-carte": JSON.stringify({ titre: x.titre, lignes: x.lignes.map(texteLigne) }) }) : null);
      }),
      mes.length ? null : el("p", { class: "vide" }, "—")));
  }
  return g;
}
function echanges(d) {
  const l = d.echanges.slice(-100).reverse();
  return bloc("Échanges" + (d.agent ? " de " + d.agent.nom : ""), d.echanges.length, l.length ? tableau(["Quand", "De", "À", "Type", "Texte"], l.map(e => [
    el("span", { class: "chiffre" }, court(e.quand)), el("strong", {}, e.de.nom), e.a.nom, badge("gris", humain(e.genre)), el("div", { class: "texte-long" }, coupe(e.texte, 220))]))
    : el("p", { class: "vide" }, "Aucun échange pour l'instant."));
}

// ── Réglages (spec docs/plans/2026-11-05-interface-reglages-spec.md) : config.toml en LECTURE SEULE, par sections ; les valeurs sensibles
// arrivent DÉJÀ « [masqué] » du serveur (la page ne voit jamais la valeur) ; aucun champ, aucun bouton qui modifie, aucune écriture. ──
function reglages(d) {
  const p = el("div", { class: "page reglages" }), s = d.signalements;
  p.append(el("div", { class: "reglages-tete" }, el("p", {}, document.createTextNode(L("reglages_ou") + " "), el("code", {}, d.fichier), "."),   // le blanc reste : el() rogne ses textes
                el("p", { class: "pale" }, L("reglages_lecture") + " " + L("masque_explique"))));
  p.append(bloc(L("a_signaler"), s.length, s.length ? el("ul", { class: "signalements" }, ...s.map(x => el("li", {},
    badge(x.ton, x.ton === "rouge" ? "À corriger" : "À savoir"), el("span", {}, x.quoi), el("span", { class: "pale" }, "→ " + x.consequence))))
    : el("p", { class: "pale" }, L("rien_a_signaler"))));
  for (const x of d.sections) {
    p.append(bloc(x.titre, null, x.phrase ? el("p", { class: "pale" }, x.phrase) : null,
                  ...x.cartes.map(c => el("div", { class: "carte-reglages" }, c.titre ? el("h3", {}, c.titre) : null, listeReglages(c.reglages)))));
  }
  return p;
}
// ── Extensions (spec docs/plans/2026-11-07-extensions-spec.md § 6) : une carte par extension, en LECTURE SEULE ; les données arrivent filtrées
// du serveur (liste blanche, forme de clé et marque privée masquées, aucun chemin privé) ; aucun champ, aucun bouton, aucune écriture. ──
function extensions(d) {
  const p = el("div", { class: "page extensions" }), s = d.signalements;
  p.append(el("div", { class: "reglages-tete" }, el("p", {}, document.createTextNode(L("extensions_ou") + " "), el("code", {}, "berger extension"), "."),
                el("p", { class: "pale" }, L("extensions_lecture"))));
  if (s.length) p.append(bloc(L("a_signaler"), s.length, el("ul", { class: "signalements" }, ...s.map(x => el("li", {},
    badge(x.ton, x.ton === "rouge" ? "À corriger" : "À savoir"), el("span", {}, x.quoi), el("span", { class: "pale" }, "→ " + x.consequence))))));
  p.append(bloc(L("extensions_installees"), d.extensions.length, d.extensions.length ? el("div", { class: "cartes-extensions" }, ...d.extensions.map(carteExtension))
    : el("p", { class: "pale" }, L("extensions_aucune"))));
  return p;
}
function carteExtension(x) {
  const ligne = (k, v) => el("div", {}, el("dt", {}, k), el("dd", {}, v));
  return el("div", { class: "carte-extension" },
    el("h3", {}, el("span", {}, x.nom), badge("gris", x.genre), x.reseau ? el("span", { class: "badge ton-rouge reseau" }, L("extensions_reseau")) : null,
       badge(x.etat === "active" ? "vert" : "rouge", x.etat)),
    x.description ? el("p", { class: "pale" }, x.description) : null,
    el("dl", { class: "reglages-liste" }, ligne("Version", x.version), ligne("Empreinte", el("code", {}, x.empreinte)),
       ligne("Agents", x.agents.length ? x.agents.join(", ") : "personne"), ligne("Installée le", x.installee), ligne("Dernier usage", x.dernier_usage),
       ...x.droits.map(r => ligne(r.cle, r.valeur))));
}
function listeReglages(l) {
  const dl = el("dl", { class: "reglages-liste" });
  for (const r of l) dl.append(el("div", {}, el("dt", {}, el("code", {}, r.cle)),
    el("dd", {}, el("span", { class: r.masque ? "valeur masque" : "valeur" }, r.valeur), el("span", { class: "phrase" }, r.phrase))));
  return dl;
}

// ── Conversation (lot 3, spec docs/plans/2026-11-05-interface-web-v2-lot3-spec.md) : le fil d'un agent, le propriétaire à droite, l'agent à
// gauche ; les actions entre deux messages repliées en « N actions » (outil et cible courte, JAMAIS une sortie) ; les demandes de validation
// en carte, avec les gestes du lot 2 (même aperçu, même jeton, même journal) ; « Copier » sur chaque réponse et chaque bloc de code. ──
function copier(t) { return bouton("lien", L("copier"), { "data-copier": t, title: L("copier"), class: "copier" }); }
function bulle(x) {
  const md = markdown(x.texte);
  for (const pre of md.querySelectorAll ? md.querySelectorAll("pre") : []) pre.append(copier(pre.textContent));   // chaque bloc de code
  return el("div", { class: "bulle " + x.genre }, el("div", { class: "bulle-tete" }, el("span", { class: "heure" }, court(x.quand)), x.genre === "agent" ? copier(x.texte) : null), md);
}
function actionsRepliees(x, k) {
  const n = x.actions.length;
  return el("details", { class: "actions-repliees", "data-cle": "actions-" + (x.quand || "") + "-" + k },
    el("summary", {}, icone("chevron", "petite"), n + " action" + (n > 1 ? "s" : ""), el("span", { class: "heure" }, court(x.quand))),
    el("ul", { class: "liste-actions" }, ...x.actions.map(a => el("li", {}, el("code", { class: "outil" }, a.outil), a.cible ? el("span", { class: "cible" }, a.cible) : null))));
}
function carteFil(x) {
  const v = x.validation, attend = v.valideur ? pale("attend " + v.valideur.nom) : null;
  return el("div", { class: "carte decision fil-carte", "data-decision": String(v.n) },
    el("div", { class: "tete" }, el("span", { class: "num" }, "n° " + v.n), el("span", { class: "objet" }, coupe(v.apercu, 120)), el("span", { class: "qui date" }, court(x.quand))),
    el("div", { class: "boutons" }, v.valideur ? attend : boutonGeste("valider", v.n)));   // Valider ouvre la décision du lot 2 (aperçu exact, empreinte, Refuser)
}
function conversation(d) {
  const p = el("div", { class: "page conversation" });
  if (!d.ouverte) return el("div", { class: "page" }, el("p", { class: "vide" }, d.raison || L("rien")));
  const fil = el("div", { class: "fil", role: "log", "aria-label": L("fil") });
  if (d.tronque) fil.append(el("p", { class: "pale fil-coupe" }, L("fil_coupe")));
  d.tours.forEach((x, k) => fil.append(x.actions ? actionsRepliees(x, k) : x.validation ? carteFil(x) : bulle(x)));
  if (!d.tours.length) fil.append(el("p", { class: "vide" }, L("aucun_message")));
  p.append(fil);
  if (!d.vivant) p.append(el("p", { class: "etat-agent pale" }, d.raison || ""));
  p.append(saisie(d));
  return p;
}
// La zone de saisie (spec §2) : UNE par agent, gardée d'un rafraîchissement à l'autre (le même nœud : une saisie en cours n'est jamais
// effacée). Entrée envoie, Maj+Entrée va à la ligne. Un long collage (plus de 4 000 caractères ou 80 lignes) devient une pièce jointe
// texte, repliée ; une image collée ou glissée devient une pièce jointe ; le micro (s'il est actif) transcrit en local, le texte paraît
// ici, corrigeable avant l'envoi, et l'audio part avec le message. L'envoi porte l'EMPREINTE de ce qui est montré (agent, texte, pièces).
const SAISIES = new Map(), COLLAGE_MAX = 4000, COLLAGE_LIGNES = 80, IMAGES_PERMISES = { "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp" };
function saisie(d) {
  const a = d.agent.id;
  let z = SAISIES.get(a);
  if (!z) {
    const t = el("textarea", { id: "c-texte", class: "c-texte", rows: "2", maxlength: "20000", "aria-label": L("ecrire_a") + " " + d.agent.nom, placeholder: L("ecrire_a") + " " + d.agent.nom + "…" });
    z = { agent: a, pieces: [], noeud: null, texte: t, liste: el("div", { class: "c-pieces", "aria-live": "polite" }), etat: el("p", { class: "f-etat pale", id: "c-etat" }),
          micro: bouton("secondaire", "", { class: "icone-seule c-micro", "data-micro": a }, icone("micro")),
          envoi: bouton("envoyer", L("envoyer"), { "data-envoyer": a }) };
    z.noeud = el("form", { class: "saisie", "data-saisie": a, "aria-label": L("ecrire_a") + " " + d.agent.nom }, z.liste, el("div", { class: "c-ligne" }, t, z.micro, z.envoi), z.etat);
    z.noeud.addEventListener("submit", ev => { ev.preventDefault(); envoyerMessage(z); });
    t.addEventListener("keydown", ev => { if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); envoyerMessage(z); } });
    t.addEventListener("paste", ev => coller(z, ev));
    z.noeud.addEventListener("dragover", ev => { ev.preventDefault(); });
    z.noeud.addEventListener("drop", ev => { ev.preventDefault(); for (const f of (ev.dataTransfer && ev.dataTransfer.files) || []) joindreFichier(z, f); });
    SAISIES.set(a, z);
  }
  const ferme = !MESSAGES ? L("ecrire_poste") : !d.vivant ? d.raison || L("au_repos") : null;   // écrire : 127.0.0.1 et agent vivant seulement
  z.ferme = ferme; z.texte.disabled = !!ferme; z.envoi.disabled = !!ferme || z.enCours === true;
  const raisonMicro = ferme || (d.micro.actif ? null : d.micro.raison);
  z.micro.setAttribute("aria-disabled", String(!!raisonMicro)); z.micro.setAttribute("title", raisonMicro || L(z.enregistre ? "micro_arreter" : "micro"));
  z.micro.setAttribute("aria-label", raisonMicro ? L("micro") + " — " + raisonMicro : L(z.enregistre ? "micro_arreter" : "micro")); z.microRaison = raisonMicro;
  if (ferme && (!z.etat.textContent || z.etatFerme)) { z.etat.textContent = ferme; z.etat.className = "f-etat pale"; z.etatFerme = true; }
  else if (!ferme && z.etatFerme) { z.etat.textContent = ""; z.etatFerme = false; }
  return z.noeud;
}
const tailleLisible = n => n >= 1048576 ? (n / 1048576).toFixed(1).replace(".", ",") + " Mio" : Math.max(1, Math.round(n / 1024)) + " Kio";
function montrerPieces(z) {
  z.liste.replaceChildren(...z.pieces.map((p, k) => el("div", { class: "c-piece" },
    p.genre === "texte" ? el("details", {}, el("summary", {}, L("collage") + " · " + p.lignes + " lignes · " + tailleLisible(p.octets.length)), el("pre", { class: "c-apercu" }, p.apercu))
                        : el("span", {}, (p.genre === "image" ? L("image") : L("audio")) + " · " + tailleLisible(p.octets.length)),
    bouton("lien", L("retirer"), { "data-retirer": String(k), "data-saisie-agent": z.agent }))));
}
function coller(z, ev) {
  const cb = ev.clipboardData; if (!cb) return;
  const fichiers = [...(cb.files || [])].filter(f => f.type in IMAGES_PERMISES);
  if (fichiers.length) { ev.preventDefault(); for (const f of fichiers) joindreFichier(z, f); return; }
  const t = cb.getData("text/plain") || "";
  if (t.length > COLLAGE_MAX || t.split("\n").length > COLLAGE_LIGNES) {   // un long collage : une pièce jointe texte, repliée
    ev.preventDefault();
    const n = t.replace(/\r\n?/g, "\n");
    z.pieces.push({ nom: "collage.txt", genre: "texte", octets: new TextEncoder().encode(n), lignes: n.split("\n").length, apercu: n.slice(0, 600) + (n.length > 600 ? "\n…" : "") });
    montrerPieces(z);
  }
}
async function joindreFichier(z, f) {
  const ext = IMAGES_PERMISES[f.type];
  if (!ext) { z.etat.textContent = L("type_refuse"); z.etat.className = "f-etat t-rouge"; return; }
  z.pieces.push({ nom: "image." + ext, genre: "image", octets: new Uint8Array(await f.arrayBuffer()) }); montrerPieces(z);
}
async function sha256(octets) { return [...new Uint8Array(await crypto.subtle.digest("SHA-256", octets))].map(x => x.toString(16).padStart(2, "0")).join(""); }
function base64(octets) { let s = ""; for (let i = 0; i < octets.length; i += 32768) s += String.fromCharCode.apply(null, octets.subarray(i, i + 32768)); return btoa(s); }
async function envoyerMessage(z) {
  if (z.ferme || z.enCours) return;
  const texte = z.texte.value.replace(/\r\n?/g, "\n"), pieces = z.pieces.slice();
  if (!texte.trim() && !pieces.length) return;
  z.enCours = true; z.envoi.disabled = true; z.etat.textContent = L("envoi"); z.etat.className = "f-etat pale";
  try {
    const meta = await Promise.all(pieces.map(async p => ({ ext: p.nom.split(".").pop().toLowerCase(), taille: p.octets.length, sha256: await sha256(p.octets) })));
    const empreinte = await sha256(new TextEncoder().encode([z.agent, texte, ...meta.map(m => m.ext + ":" + m.taille + ":" + m.sha256)].join("\0")));   // ce qui est MONTRÉ
    const j = await lire("/api/message/jeton?agent=" + encodeURIComponent(z.agent));
    const r = await fetch("/api/message", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-Berger-Jeton": j.jeton },
      body: JSON.stringify({ agent: z.agent, texte, pieces: pieces.map(p => ({ nom: p.nom, donnees: base64(p.octets) })), empreinte, nonce: j.nonce }) });
    const x = await r.json().catch(() => ({ erreur: "réponse illisible" }));
    if (!r.ok) throw new Error(x.erreur || "erreur " + r.status);
    if (z.texte.value.replace(/\r\n?/g, "\n") === texte) z.texte.value = "";    // ce qui a été envoyé, et seulement cela, quitte la zone
    z.pieces = z.pieces.filter(p => !pieces.includes(p)); montrerPieces(z);
    z.etat.textContent = ""; annoncer(x.message || L("envoye"));
    RECENTES.clear(); afficher(true);
  } catch (e) { z.etat.textContent = String(e.message || e); z.etat.className = "f-etat t-rouge"; }
  finally { z.enCours = false; z.envoi.disabled = !!z.ferme; }
}
// Le micro : actif SEULEMENT si une transcription locale est déclarée ([interface] transcription) ; sinon grisé, sa raison au survol et au
// toucher. Enregistrer → arrêter → le serveur transcrit en local → le texte s'ajoute à la zone, corrigeable ; l'audio est gardé en pièce jointe.
async function micro(z) {
  if (z.microRaison) { z.etat.textContent = z.microRaison; z.etat.className = "f-etat pale"; return; }
  if (z.enregistre) { z.enregistre.stop(); return; }
  try {
    const flux = await navigator.mediaDevices.getUserMedia({ audio: true });
    const type = ["audio/webm", "audio/ogg"].find(t => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(t)) || "audio/webm";
    const rec = new MediaRecorder(flux, { mimeType: type }), bouts = [];
    rec.ondataavailable = e => bouts.push(e.data);
    rec.onstop = async () => {
      for (const p of flux.getTracks()) p.stop();
      z.enregistre = null; z.micro.setAttribute("title", L("micro")); z.micro.classList.remove("actif");
      const octets = new Uint8Array(await new Blob(bouts, { type }).arrayBuffer()), nom = "dictee." + (type === "audio/ogg" ? "ogg" : "webm");
      z.etat.textContent = L("transcription"); z.etat.className = "f-etat pale";
      try {
        const j = await lire("/api/message/jeton?usage=transcription&agent=" + encodeURIComponent(z.agent));   // usage unique, lié à l'agent et à la dictée
        const r = await fetch("/api/transcrire", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-Berger-Jeton": j.jeton },
          body: JSON.stringify({ agent: z.agent, nom, donnees: base64(octets), empreinte: await sha256(octets), nonce: j.nonce }) });
        const x = await r.json().catch(() => ({ erreur: "réponse illisible" }));
        if (!r.ok) throw new Error(x.erreur || "erreur " + r.status);
        z.texte.value = (z.texte.value ? z.texte.value.replace(/\s+$/, "") + " " : "") + x.texte; z.texte.focus();
        z.pieces.push({ nom, genre: "audio", octets }); montrerPieces(z); z.etat.textContent = "";
      } catch (e) { z.etat.textContent = String(e.message || e); z.etat.className = "f-etat t-rouge"; }
    };
    rec.start(); z.enregistre = rec; z.micro.classList.add("actif"); z.micro.setAttribute("title", L("micro_arreter"));
    z.etat.textContent = L("enregistrement"); z.etat.className = "f-etat pale";
  } catch (e) { z.etat.textContent = L("micro_refuse"); z.etat.className = "f-etat t-rouge"; }
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
  const paires = [];
  for (const [k, sous] of visibles(s, v)) {
    const r = rendre(sous, v[k]);
    if (r) paires.push([libelle(sous, k), r]);
  }
  return cles(paires);
}
const HUMAINS = { Genre: "Type", Quoi: "Objet" };                         // libellés humains, même si un schéma ancien dit autrement
const libelle = (s, k) => { const x = s["x-libelle"] || humain(k); return HUMAINS[x] || x; };
const SIMPLES = new Set(["texte", "nombre", "quand", "oui-non", "ton", "agent", "statuts", "lien", "cache"]);
function liste(s, v) {
  if (vide(v)) return null;
  if (!Array.isArray(v)) return objet(resoudre(s, v), v);
  const item = resoudre(s.items || {}, v[0]);
  if (s.items && s.items["x-rendu"]) return el("div", { class: "liste-lignes" }, ...v.map(x => el("div", { class: "ligne-liste" }, rendre(s.items, x))));
  const cols = Object.entries(item.properties || {}).filter(([k, p]) => p["x-rendu"] !== "cache" && v.some(x => x && !vide(x[k])));
  if (cols.length && cols.every(([, p]) => SIMPLES.has(p["x-rendu"])))   // éléments plats : un tableau, les libellés une seule fois
    return tableau(cols.map(([k, p]) => libelle(p, k)), v.map(x => cols.map(([k, p]) => rendre(p, x[k]) || pale("—"))));
  return el("div", { class: "liste-lignes" }, ...v.map(x => (x !== null && typeof x === "object") ? el("div", { class: "ligne-liste" }, objet(resoudre(s.items || {}, x), x)) : texte(x)));
}
// Les valeurs simples (texte, nombre, date, état…) vont ensemble dans UNE Liste clé/valeur en tête, jamais chacune dans son grand
// cadre ; les listes, textes longs et objets gardent leur bloc titré.
function generique(s, d) {
  const sortie = el("div", { class: "page" }), simples = [], blocs = [];
  for (const [k, sous] of visibles(s, d)) {
    const r = rendre(sous, d[k]);
    if (!r) continue;
    const rendu = resoudre(sous, d[k])["x-rendu"] || sous["x-rendu"];
    if (SIMPLES.has(rendu) && (!Array.isArray(d[k]) || rendu === "statuts")) simples.push([libelle(sous, k), r]);
    else blocs.push(bloc(libelle(sous, k), Array.isArray(d[k]) ? d[k].length : null, r));
  }
  if (simples.length) sortie.append(el("section", { class: "bloc" }, el("div", { class: "corps" }, cles(simples))));
  sortie.append(...blocs);
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
  if (!SCHEMAS.communs) SCHEMAS.communs = await lire("/api/schema/communs");   // lus à la demande : le premier chargement reste léger
  if (!SCHEMAS[nom]) SCHEMAS[nom] = await lire("/api/schema/" + nom);
  return SCHEMAS[nom];
}
// UNE requête par vue (audit, défaut 8) : la même vue demandée deux fois en moins de 4 s (affichage, compteurs, en-tête) n'est lue qu'une fois.
const RECENTES = new Map(), FRAIS = 4000;
function donnees(type, a) {
  const cle = type + "|" + (a || ""), x = RECENTES.get(cle);
  if (x && (x.enCours || Date.now() - x.t < FRAIS)) return x.p;         // une lecture EN COURS est toujours réutilisée, puis valable 4 s après sa réponse
  const p = lire("/api/vue/" + type + (a ? "?a=" + encodeURIComponent(a) : "")).then(r => r.donnees), y = { t: Date.now(), p, enCours: true };
  RECENTES.set(cle, y);
  p.then(() => { y.enCours = false; y.t = Date.now(); }, () => { if (RECENTES.get(cle) === y) RECENTES.delete(cle); });
  return p;
}
const existe = type => VUES.some(v => v.type === type && v.donnees);

// ── menu latéral repliable : l'état est gardé dans CE navigateur seulement (localStorage), jamais ailleurs ──
const MENU = "berger-menu";
function menuReplie() { try { return localStorage.getItem(MENU) === "replie"; } catch (e) { return false; } }
function replierMenu(oui) {
  try { localStorage.setItem(MENU, oui ? "replie" : ""); } catch (e) { /* stockage refusé : l'état vaut pour la page seulement */ }
  appliquerMenu(oui);
}
function appliquerMenu(oui) {
  const a = document.getElementById("app"); if (a) a.setAttribute("data-menu", oui ? "replie" : "ouvert");
  const b = document.getElementById("replier"); if (b) b.setAttribute("aria-expanded", oui ? "false" : "true");
}

// ── Fenêtre (une validation, un document, un agent, une alerte) : un en-tête (titre + une ligne de métadonnées), un corps, un pied
// d'actions collé en bas. Échap la ferme ; le focus reste piégé dedans tant qu'elle est ouverte, puis revient à l'élément qui l'a
// ouverte — retrouvé par ses attributs s'il a été remplacé par un rafraîchissement entre-temps. ──
let avantFenetre = null, numFenetre = 0;                                  // chaque fenêtre ouverte (ou fermée) change le numéro
const RETROUVER = ["data-objet", "data-a", "data-geste", "data-cible", "data-fenetre-agent", "data-alerte", "data-texte", "data-carte", "data-vue", "data-agent", "data-plus"];
function reperer(x) {                                                     // l'élément d'origine, et de quoi le retrouver s'il est remplacé
  if (!x || !x.getAttribute) return null;
  const attrs = RETROUVER.filter(a => x.getAttribute(a) !== null).map(a => "[" + a + '="' + (typeof CSS !== "undefined" && CSS.escape ? CSS.escape(x.getAttribute(a)) : x.getAttribute(a)) + '"]');
  return { el: x, choix: attrs.length ? x.tagName.toLowerCase() + attrs.join("") : null };
}
const fenetreOuverte = () => !document.getElementById("voile").hidden;
function fenetre(titre, sous, corps, large, pied) {
  numFenetre++;
  const v = document.getElementById("voile");
  if (v.hidden) avantFenetre = reperer(document.activeElement);            // une fenêtre qui en remplace une autre garde l'origine de la première
  document.getElementById("f-titre").textContent = propre(titre); document.getElementById("f-sous").textContent = propre(sous || "");
  remplir(corps, pied);
  document.getElementById("fenetre").setAttribute("data-large", large ? "1" : "0");
  v.hidden = false; document.getElementById("f-fermer").focus();
}
function remplir(corps, pied) {                                           // le corps, et le pied d'actions (caché s'il est vide)
  document.getElementById("f-corps").replaceChildren(...[].concat(corps).filter(Boolean));
  const p = document.getElementById("f-pied"), b = [].concat(pied || []).filter(Boolean);
  p.replaceChildren(...b); p.hidden = !b.length;
}
function fermerFenetre() {
  const v = document.getElementById("voile"); if (v.hidden) return;
  numFenetre++; v.hidden = true; GESTE = null; remplir([], []);
  const o = avantFenetre; avantFenetre = null;
  const cible = o && (o.el.isConnected ? o.el : o.choix ? document.querySelector(o.choix) : null);
  (cible || document.getElementById("vue")).focus({ preventScroll: true });
}
function pieger(ev) {                                                     // Tab reste dans la fenêtre ouverte
  const f = document.getElementById("fenetre");
  const l = [...f.querySelectorAll("button, [href], textarea, input, select, summary, iframe, [tabindex]:not([tabindex='-1'])")]
    .filter(x => !x.disabled && x.getClientRects().length && getComputedStyle(x).visibility !== "hidden");
  if (!l.length) return;
  const i = l.indexOf(document.activeElement);
  if (i < 0 || (ev.shiftKey && i === 0) || (!ev.shiftKey && i === l.length - 1)) { ev.preventDefault(); l[ev.shiftKey ? l.length - 1 : 0].focus(); }
}
async function copierTexte(b) {                                         // « Copier » : le texte de la réponse (ou du bloc), jamais du HTML
  try { await navigator.clipboard.writeText(b.dataset.copier); annoncer(L("copie_faite")); }
  catch (e) { annoncer(L("copie_impossible")); }
}
let minuterieAnnonce = null;
function annoncer(t) {                                                    // une confirmation courte (« n° 160 validée »), qui s'efface seule
  const a = document.getElementById("annonce"); a.textContent = propre(t); a.hidden = false;
  clearTimeout(minuterieAnnonce); minuterieAnnonce = setTimeout(() => { a.hidden = true; }, 5000);
}
// Une réponse arrivée après qu'une autre fenêtre a été ouverte (ou celle-ci fermée) est ignorée : seule la fenêtre courante se remplit.
const courante = n => n === numFenetre;
const erreur = e => el("p", { class: "t-rouge" }, String(e.message || e));
async function fenetreObjet(type, a) {
  const ded = DEDIES[type] || {};
  fenetre((VUES.find(v => v.type === type) || {}).titre || type, "", chargement(), !!ded.large); const n = numFenetre;
  try {
    const d = await donnees(type, a);
    const corps = ded.rendre ? ded.rendre(d) : generique(await schema(type), d);
    if (!courante(n)) return;
    if (ded.titre) document.getElementById("f-titre").textContent = propre(ded.titre(d));
    document.getElementById("f-sous").textContent = ded.sous ? propre(ded.sous(d)) : d.titre ? coupe(d.titre, 80) : "";
    remplir(corps, ACTIONS ? gestesDe(ded, a, d) : []);
  } catch (e) { if (courante(n)) remplir(erreur(e), []); }
}
// Les gestes d'une vue d'objet, dans le pied : Refuser (danger) puis Valider (primaire) ; « Marquer lu » seulement si non lu.
const gestesDe = (ded, a, d) => (ded.gestes || []).filter(g => !(g === "lu" && d && d.lu === true)).sort((x, y) => (GENRES[x] === "primaire") - (GENRES[y] === "primaire")).map(g => boutonGeste(g, a));
// ── gestes du propriétaire (lot 2) : seulement si le serveur les active ([interface] actions = true) et que la source est le poste ou le VPN ──
// Chaque geste montre d'abord ce qui sera fait (numéro, aperçu EXACT, empreinte), puis part avec le jeton anti-rejeu et le jeton d'aperçu.
// Une décision (spec finition §4) : la carte ouvre CETTE fenêtre (1er clic) ; son pied porte Valider (2e clic) et Refuser, qui
// ouvre le champ du motif puis se confirme. Mêmes appels qu'au lot 2 (/api/action/apercu, puis /api/action) : rien ne change côté serveur.
let ACTIONS = false, GESTE = null;
function boutonGeste(action, cible) {
  return ACTIONS && cible !== null && cible !== undefined ? bouton(action, L("geste_" + action), { "data-geste": action, "data-cible": String(cible) }) : null;
}
const CHAMPS = { refuser: "motif", repondre: "reponse" };                 // les gestes qui demandent un texte
async function geste(action, cible) {
  GESTE = null; fenetre(L("geste_" + action), L("verifier"), chargement()); const n = numFenetre;
  try {
    const ap = await lire("/api/action/apercu?action=" + encodeURIComponent(action) + "&cible=" + encodeURIComponent(cible));
    if (!courante(n)) return;
    GESTE = ap;
    document.getElementById("f-sous").textContent = coupe(ap.titre, 80);
    const champ = CHAMPS[action] ? champTexte(action) : null;
    const pied = action === "valider"
      ? [bouton("refuser", L("geste_refuser"), { "data-refus": String(cible) }), bouton("valider", L("geste_valider"), { "data-confirmer": "1" })]
      : [bouton("annuler", L("annuler"), { "data-fermer": "1" }), bouton(action === "refuser" ? "refuser" : action === "repondre" ? "envoyer" : action,
           action === "refuser" ? L("confirmer_refus") : action === "repondre" ? L("envoyer") : L("confirmer") + " : " + L("geste_" + action), { "data-confirmer": "1", ...(champ ? { disabled: "" } : {}) })];
    remplir(apercu(ap, champ), pied);
    if (champ) champ.focus();
  } catch (e) { if (courante(n)) remplir(erreur(e), []); }
}
function apercu(ap, champ) {
  return el("div", { class: "confirmation" },
    el("p", { class: "g-titre" }, document.createTextNode(ap.titre)),
    el("p", { class: "g-apercu" }, document.createTextNode(ap.apercu)),                       // l'aperçu EXACT : jamais retouché
    el("p", { class: "pale" }, L("empreinte") + " : ", el("code", { title: ap.empreinte, class: "sha" }, ap.empreinte.slice(0, 16))),
    champ, el("p", { id: "g-etat", class: "f-etat pale" }));
}
function champTexte(action) {                                             // le motif (ou la réponse) : la confirmation reste grise tant qu'il est vide
  const nom = CHAMPS[action];
  return el("textarea", { id: "g-texte", class: "g-texte", rows: action === "refuser" ? "3" : "5", maxlength: "2000", "aria-label": L(nom), placeholder: L(nom), required: "" });
}
async function ouvrirRefus(cible) {                                        // Refuser, depuis la décision : son propre aperçu (le geste « refuser » du lot 2), puis le motif
  const n = numFenetre, etat = document.getElementById("g-etat");
  for (const b of document.querySelectorAll("#f-pied button")) b.disabled = true;
  try {
    const ap = await lire("/api/action/apercu?action=refuser&cible=" + encodeURIComponent(cible));
    if (!courante(n)) return;
    GESTE = ap; numFenetre++;                                              // la fenêtre change de geste : une réponse tardive du précédent est ignorée
    document.getElementById("f-titre").textContent = L("geste_refuser"); document.getElementById("f-sous").textContent = coupe(ap.titre, 80);
    const champ = champTexte("refuser");
    remplir(apercu(ap, champ), [bouton("annuler", L("annuler"), { "data-fermer": "1" }), bouton("refuser", L("confirmer_refus"), { "data-confirmer": "1", disabled: "" })]);
    champ.focus();
  } catch (e) { if (courante(n)) { for (const b of document.querySelectorAll("#f-pied button")) b.disabled = false; if (etat) { etat.textContent = String(e.message || e); etat.className = "f-etat t-rouge"; } } }
}
async function confirmer(bouton_) {
  const ap = GESTE, t = document.getElementById("g-texte"), etat = document.getElementById("g-etat"); if (!ap) return;
  const corps = { action: ap.action, cible: ap.cible, empreinte: ap.empreinte, nonce: ap.nonce };
  if (t) {
    if (!t.value.trim()) { etat.textContent = L(ap.action === "refuser" ? "motif_obligatoire" : "reponse_obligatoire"); etat.className = "f-etat t-rouge"; return t.focus(); }
    corps[ap.action === "refuser" ? "motif" : "texte"] = t.value;
  }
  GESTE = null; bouton_.disabled = true; const n = numFenetre;             // un jeton d'aperçu ne sert qu'une fois
  try {
    const r = await fetch("/api/action", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-Berger-Jeton": ap.jeton }, body: JSON.stringify(corps) });
    const x = await r.json().catch(() => ({ erreur: "réponse illisible" }));
    if (!r.ok) throw new Error((x.erreur || "erreur " + r.status) + (r.status === 409 || r.status === 403 ? " — " + L("rouvrir") : ""));
    // fait : une confirmation courte, l'élément traité disparaît tout de suite, le défilement ne bouge pas
    const decision = ap.action === "valider" || ap.action === "refuser";
    if (decision) for (const c of document.querySelectorAll('#vue [data-decision="' + ap.cible + '"]')) c.remove();
    if (courante(n)) fermerFenetre();
    annoncer(decision ? "n° " + ap.cible + " " + L(ap.action === "valider" ? "valide_fait" : "refuse_fait") : (x.message || "fait"));
    RECENTES.clear(); afficher(true); compter();
  } catch (e) { if (courante(n)) { bouton_.disabled = false; etat.textContent = String(e.message || e); etat.className = "f-etat t-rouge"; } }
}
async function fenetreAgent(id, vue) {
  const a = AGENTS.find(x => x.id === id) || { id, nom: id, role: "agent" };
  const page = bouton("ouvrir", L("page_agent"), { "data-agent": id });
  fenetre(a.nom, "agent", chargement()); const n = numFenetre;
  try {
    const d = await donnees(vue, id), corps = generique(await schema(vue), d);
    if (courante(n)) remplir(corps, [page]);
  } catch (e) { if (courante(n)) remplir(erreur(e), [page]); }
}
// À lire, deux volets : le document choisi s'affiche à droite, sans fenêtre ; il reste ouvert au rafraîchissement.
async function remplirVolet(v, id) {
  if (!v || !deuxVolets()) return;
  id = id || v.getAttribute("data-doc"); if (!id) return;
  LECTURE = id; v.setAttribute("data-doc", id);
  for (const b of document.querySelectorAll('#vue .volets-liste [data-volet]')) b.setAttribute("aria-current", String(b.getAttribute("data-a") === id));
  const type = v.getAttribute("data-vue");
  try {
    const d = await donnees(type, id), signe = JSON.stringify(d);
    if (LECTURE !== id || !v.isConnected) return;
    if (v.getAttribute("data-charge") === id && VOLET_LU === signe) return;  // rien n'a changé : le volet reste tel quel (Détail ouvert, défilement)
    const ouvert = v.getAttribute("data-charge") === id && !!v.querySelector("details.detail[open]");
    const actions = ACTIONS ? gestesDe(DEDIES[type] || {}, id, d) : [];
    v.replaceChildren(el("header", {}, el("h2", {}, d.titre), el("p", { class: "meta-ligne" }, metaDocument(d))), lecture(d),
                      ...(actions.length ? [el("div", { class: "pied" }, ...actions)] : []));   // jamais null : replaceChildren() l'écrirait « null »
    if (ouvert) { const x = v.querySelector("details.detail"); if (x) x.open = true; }
    v.setAttribute("data-charge", id); VOLET_LU = signe;
  } catch (e) { if (LECTURE === id) v.replaceChildren(erreur(e)); }
}
async function deplier(zone) {                                            // un bloc replié se lit seulement quand on le déplie
  const type = zone.getAttribute("data-deplier"); if (!type || !existe(type)) return zone.replaceChildren(pale("—"));
  try { zone.replaceChildren(generique(await schema(type), await donnees(type))); }
  catch (e) { zone.replaceChildren(el("p", { class: "t-rouge" }, String(e.message || e))); }
}

// ── navigation, en-tête, vue courante ──
function dire(t, erreur) { const e = document.getElementById("etat"); e.textContent = t; e.className = erreur ? "t-rouge" : "pale"; }
function age() { if (dernier && !document.getElementById("etat").classList.contains("t-rouge")) dire("mis à jour il y a " + Math.round((Date.now() - dernier) / 1000) + " s"); }
// courant = { mode : "berger" | "agent", type, a (agent) }
function entree(attrs, nomIcone, libelle, n, actif, point) {
  return el("button", { type: "button", class: "entree", title: libelle, "aria-current": actif ? "page" : "false", ...attrs },
            point ? el("span", { class: "point p-" + point }) : null, icone(nomIcone),
            el("span", { class: "entree-libelle" }, libelle), n ? el("span", { class: "compteur" }, String(n)) : null);
}
// Un onglet de la navigation = un groupe de vues (regroupement 11 → 5, 31/10/2026) : le « groupe » d'une vue (sinon son titre) est son onglet ;
// l'onglet s'ouvre sur la première vue du groupe et les montre toutes, l'une sous l'autre (celles que la vue de tête montre déjà, `absorbe`, ne se répètent pas).
const groupeDe = v => v.groupe || (VUES.some(x => x.onglet === "berger" && x.groupe === v.titre) ? v.titre : null);
function ongletsBerger() {
  const vus = new Set(), sortie = [];
  for (const v of VUES.filter(v => v.onglet === "berger")) {
    const g = groupeDe(v) || v.titre;
    if (vus.has(g)) continue; vus.add(g);
    const tous = groupeDe(v) ? VUES.filter(x => x.onglet === "berger" && groupeDe(x) === g) : [v];
    const tete = tous.find(x => !x.groupe) || tous[0];                    // la vue de tête (celle qui porte le nom de l'onglet), puis les autres dans l'ordre
    const o = SOURCE.onglets[g] || {};
    sortie.push({ cle: g, libelle: o.libelle || g, icone: o.icone, tete, membres: [tete, ...tous.filter(x => x !== tete)] });
  }
  return sortie.sort((a, b) => a.tete.ordre - b.tete.ordre);
}
function sections(type) {
  const o = ongletsBerger().find(o => o.membres.some(x => x.type === type));
  if (!o) return [type];
  const lues = new Set(((DEDIES[o.tete.type] || {}).absorbe) || []);
  return o.membres.map(x => x.type).filter(t => t === o.tete.type || !lues.has(t));
}
const BARRE_BAS = 4;                                                     // téléphone : les 4 premiers onglets, le reste sous « Plus »
function navigation() {
  const nav = document.getElementById("onglets"); nav.replaceChildren();
  const ongs = ongletsBerger();
  for (const [k, o] of ongs.entries()) {
    nav.append(entree({ "data-vue": o.tete.type, "data-rang": String(k) }, o.icone, o.libelle, COMPTES[o.tete.type], !!courant && courant.mode === "berger" && o.membres.some(x => x.type === courant.type)));
  }
  nav.append(entree({ "data-plus": "1", class: "entree seulement-mobile" }, "plus", L("plus"), 0, false));
  const la = document.getElementById("liste-agents"); la.replaceChildren();
  for (const a of AGENTS) la.append(entreeAgent(a, { actif: !!courant && courant.mode === "agent" && courant.a === a.id, ton: TONS_ETAT[a.etat] || "gris" }));
  document.getElementById("rubrique-agents").hidden = !AGENTS.length;
  const sous = document.getElementById("agents"); sous.replaceChildren();
  sous.hidden = !(courant && courant.mode === "agent");
  if (!sous.hidden) sous.append(...vuesAgent(courant.a).map(v => el("button", { type: "button", "data-vue-agent": v.type, "data-a": courant.a, "aria-pressed": String(courant.type === v.type) }, v.titre)));
  const g = document.getElementById("global"); g.replaceChildren();
  for (const x of GLOBAL) g.append(el("span", { class: "etat" }, el("span", { class: "point p-" + x.ton }), x.texte));
  const n = COMPTES[(ongs[0] || { tete: {} }).tete.type] || 0, puce = document.getElementById("puce");
  puce.hidden = !n; puce.textContent = n + " " + L("pour_toi"); if (ongs[0]) puce.setAttribute("data-vue", ongs[0].tete.type);
}
// Les vues d'un agent (sous-onglets) : une page dédiée qui ne vaut que pour certains agents (Conversation) est cachée pour les autres.
const vuesAgent = a => VUES.filter(v => v.onglet === "agent" && (!DEDIES_AGENT[v.type] || !DEDIES_AGENT[v.type].pour || DEDIES_AGENT[v.type].pour(a)));
function menuPlus() {                                                    // téléphone : ce qui ne tient pas dans la barre du bas
  const l = el("div", { class: "pile" });
  for (const [k, o] of ongletsBerger().entries()) if (k >= BARRE_BAS) l.append(entree({ "data-vue": o.tete.type }, o.icone, o.libelle, COMPTES[o.tete.type], false));
  if (AGENTS.length) l.append(el("h4", {}, L("agents")));
  for (const a of AGENTS) l.append(entreeAgent(a));
  fenetre(L("plus"), "", l);
}
async function compter() {
  const globaux = [];
  for (const [type, ded] of Object.entries(DEDIES)) {
    if (!existe(type)) continue;
    try {
      if (ded.compteur) {
        const d = await donnees(ded.compteur[0]);
        COMPTES[type] = ded.compteur[1](d);
        if (ded.compteur[0] === type) etatsAgents(d);
      }
      if (ded.global) globaux.push(ded.global(await donnees(type)));
    } catch (e) { COMPTES[type] = 0; }
  }
  GLOBAL = globaux; navigation();
}
// La liste des agents de la barre latérale vient de l'Accueil (agents et développeurs, avec leur état) : pas de lecture en plus.
function etatsAgents(d) {
  if (!d || !d.agents || !d.equipes) return;
  AGENTS = tousAgents(d).map(x => Object.assign({}, x.agent, { etat: etatPrincipal(x.statuts) }));
}
async function afficher(auto) {
  if (!courant || document.hidden) return;
  if (auto && affiche === courant && (DEDIES[courant.type] || {}).fixe) return;   // vue fixe déjà affichée : on ne la recharge pas
  if (enVol) { encore = true; return; }                                   // une vue à la fois ; un clic pendant ce temps est rejoué ensuite
  enVol = true; encore = false;
  const vise = courant;
  // la saisie en cours garde son focus et sa sélection (le même champ est remis en place, relevé AVANT de reconstruire la vue) ; un fil lu en bas y reste
  const actif = document.activeElement && document.activeElement.id && document.getElementById("vue").contains(document.activeElement) ? document.activeElement : null;
  const sel = actif && "selectionStart" in actif ? [actif.selectionStart, actif.selectionEnd] : null;
  const racine = document.documentElement, enBas = !!racine && window.innerHeight + window.scrollY >= racine.scrollHeight - 80;
  try {
    const corpsDe = async (type, a) => {
      const ded = vise.mode !== "agent" ? DEDIES[type] : DEDIES_AGENT[type] || null;
      const d = await donnees(type, a);
      if (ded && ded.compteur && ded.compteur[0] === type) etatsAgents(d);
      if (ded && ded.rendre) return ded.rendre(d);
      return generique(await schema(type), d);
    };
    let corps;
    const parts = vise.mode === "berger" ? sections(vise.type) : [vise.type];
    if (parts.length > 1) {                                                // un onglet à plusieurs vues : la première, puis les autres repliées (lues à la demande)
      corps = el("div", { class: "groupe" }, await corpsDe(parts[0]));
      for (const t of parts.slice(1)) {
        const v = VUES.find(x => x.type === t) || {};
        corps.append(replie(v.titre || t, (SOURCE.onglets[v.titre] || {}).icone || "generique", "", el("div", { class: "a-deplier", "data-deplier": t }, chargement())));
      }
    } else corps = await corpsDe(vise.type, vise.a);
    if (courant !== vise) return;                                          // la vue a changé pendant la lecture : on n'affiche pas l'ancienne
    const titre = VUES.find(v => v.type === courant.type);
    const onglet_ = vise.mode === "berger" ? ongletsBerger().find(o => o.membres.some(x => x.type === courant.type)) : null;
    document.getElementById("titre-vue").textContent = (onglet_ ? onglet_.libelle : titre ? titre.titre : courant.type) + (courant.mode === "agent" ? " · " + (AGENTS.find(a => a.id === courant.a) || { nom: courant.a }).nom : "");
    // relecture de la MÊME vue : ce qui était déplié le reste, AVEC son contenu déjà lu (aucun saut : la place reste prise pendant la
    // relecture), et le document du volet de lecture reste affiché tel quel
    const meme = affiche === courant, ouverts = new Map();
    if (meme) for (const d of document.querySelectorAll("#vue details[open][data-cle]")) {
      const z = d.querySelector(":scope > .corps-replie > .a-deplier");
      ouverts.set(d.getAttribute("data-cle"), z ? [...z.childNodes] : null);
    }
    const ancienVolet = meme ? document.querySelector("#vue .volet-lecture[data-charge]") : null;
    const vue = document.getElementById("vue");
    vue.setAttribute("data-plein", vise.mode === "berger" && (DEDIES[parts[0]] || {}).plein ? "1" : "0");
    vue.replaceChildren(corps);
    if (actif && actif.isConnected && document.activeElement !== actif) { actif.focus({ preventScroll: true }); if (sel) actif.setSelectionRange(...sel); }
    const dedA = vise.mode === "agent" ? DEDIES_AGENT[vise.type] : null;
    if (dedA && dedA.apres) dedA.apres(meme, enBas);
    for (const d of document.querySelectorAll("#vue details[data-cle]")) if (ouverts.has(d.getAttribute("data-cle"))) {
      d.open = true; const z = d.querySelector(":scope > .corps-replie > .a-deplier"), avant = ouverts.get(d.getAttribute("data-cle"));
      if (z) { if (avant && avant.length) z.replaceChildren(...avant); deplier(z); }
    }
    const volet = document.querySelector("#vue .volet-lecture");
    if (volet && ancienVolet && ancienVolet.getAttribute("data-charge") === volet.getAttribute("data-doc")) { volet.replaceWith(ancienVolet); remplirVolet(ancienVolet); }   // gardé, relu : remplacé seulement s'il a changé
    else if (volet) remplirVolet(volet);
    affiche = courant; dernier = Date.now(); dire("mis à jour il y a 0 s"); document.getElementById("vue").classList.remove("perime");
    navigation();
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
  flux.addEventListener("change", () => { signal = Date.now(); RECENTES.clear(); afficher(true); compter(); });
  flux.addEventListener("battement", () => { signal = Date.now(); });
  flux.onerror = () => {
    fluxOuvert = false;
    if (flux.readyState === 2) { flux = null; setTimeout(ouvrirFlux, 30000); }      // fermé pour de bon : on réessaie plus tard
  };
}
function boucle(f, ms) { setTimeout(async () => { try { await f(); } finally { boucle(f, ms); } }, ms); }   // la suivante APRÈS la fin
function aller(c) { courant = c; fermerFenetre(); navigation(); afficher(); window.scrollTo(0, 0); }
// ── thème : celui du système, puis le choix mémorisé dans CE navigateur (localStorage, clé berger-theme) ──
const THEME = "berger-theme", THEMES = ["", "clair", "sombre"];
function themeChoisi() { try { const t = localStorage.getItem(THEME); return THEMES.includes(t) ? t : ""; } catch (e) { return ""; } }
function appliquerTheme(t) {
  const r = document.documentElement; if (!r) return;
  if (t) r.setAttribute("data-theme", t); else if (r.removeAttribute) r.removeAttribute("data-theme");
  const b = document.getElementById("theme"), l = L(t ? "theme_" + t : "theme_systeme");
  if (b) { b.setAttribute("aria-label", l); b.setAttribute("title", l); }
}
function changerTheme() {
  const t = THEMES[(THEMES.indexOf(themeChoisi()) + 1) % THEMES.length];
  try { localStorage.setItem(THEME, t); } catch (e) { /* stockage refusé : le choix vaut pour la page seulement */ }
  appliquerTheme(t);
}
document.addEventListener("click", ev => {
  if (ev.target.id === "voile") return fermerFenetre();
  const b = ev.target.closest("button"); if (!b) return;
  const vueAgent = (VUES.find(v => v.onglet === "agent") || {}).type;
  if (b.id === "replier") return replierMenu(!menuReplie());
  if (b.id === "theme") return changerTheme();
  if (b.dataset.fermer) return fermerFenetre();
  if (b.dataset.copier !== undefined) return copierTexte(b);
  if (b.dataset.envoyer) { const z = SAISIES.get(b.dataset.envoyer); return z && envoyerMessage(z); }
  if (b.dataset.micro) { const z = SAISIES.get(b.dataset.micro); return z && micro(z); }
  if (b.dataset.retirer) { const z = SAISIES.get(b.dataset.saisieAgent); if (z) { z.pieces.splice(+b.dataset.retirer, 1); montrerPieces(z); } return; }
  if (b.dataset.refus) return ouvrirRefus(b.dataset.refus);
  if (b.dataset.plus) return menuPlus();
  if (b.dataset.geste) return geste(b.dataset.geste, b.dataset.cible);
  if (b.dataset.confirmer) return confirmer(b);
  if (b.dataset.texte) return fenetre(b.dataset.texteTitre || L("detail"), "", el("p", { class: "texte-entier" }, b.dataset.texte));   // le texte entier
  if (b.dataset.alerte) return fenetre(L("alertes"), "", el("p", {}, b.dataset.alerte));
  if (b.dataset.carte) { const c = JSON.parse(b.dataset.carte); return fenetre(c.titre, "", el("div", { class: "lignes" }, ...c.lignes.map(t => el("div", {}, t)))); }
  if (b.dataset.objet && b.dataset.volet && deuxVolets()) return remplirVolet(document.querySelector("#vue .volet-lecture"), b.dataset.a);   // deux volets : à droite, sans fenêtre
  if (b.dataset.objet) return fenetreObjet(b.dataset.objet, b.dataset.a);
  if (b.dataset.fenetreAgent) return fenetreAgent(b.dataset.fenetreAgent, b.dataset.vueAgent || vueAgent);
  if (b.dataset.vue) return aller({ mode: "berger", type: b.dataset.vue });
  if (b.dataset.agent) { const t = courant && courant.mode === "agent" ? courant.type : vueAgent;
    return aller({ mode: "agent", type: vuesAgent(b.dataset.agent).some(v => v.type === t) ? t : vueAgent, a: b.dataset.agent }); }
  if (b.dataset.vueAgent && b.dataset.a) return aller({ mode: "agent", type: b.dataset.vueAgent, a: b.dataset.a });
});
document.addEventListener("toggle", ev => {                              // un bloc replié qu'on déplie : sa vue est lue maintenant
  const d = ev.target; if (!d.open || !d.querySelector) return;
  const z = d.querySelector(".a-deplier"); if (z) deplier(z);
}, true);
document.addEventListener("keydown", ev => {
  if (!fenetreOuverte()) return;
  if (ev.key === "Escape") { ev.preventDefault(); fermerFenetre(); }
  else if (ev.key === "Tab") pieger(ev);
});
document.addEventListener("input", ev => {                               // la confirmation d'un refus (ou d'une réponse) reste grise tant que le texte est vide
  if (ev.target.id !== "g-texte") return;
  const b = document.querySelector("#f-pied [data-confirmer]"); if (b) b.disabled = !ev.target.value.trim();
});
document.addEventListener("focusin", ev => {                             // le focus ne sort pas d'une fenêtre ouverte (clic, lecteur d'écran)
  if (fenetreOuverte() && !document.getElementById("fenetre").contains(ev.target)) document.getElementById("f-fermer").focus();
});
document.addEventListener("visibilitychange", () => { if (!document.hidden) afficher(true); });

async function demarrer() {
  appliquerMenu(menuReplie()); appliquerTheme(themeChoisi());
  try {
    await connexion();
    SOURCE = await lire("/icones.json");
    for (const x of document.querySelectorAll("[data-icone]")) x.replaceWith(icone(x.getAttribute("data-icone")));   // icônes fixes de la page
    appliquerTheme(themeChoisi());                                                     // le libellé du bouton vient de la source commune
    if (typeof matchMedia === "function") matchMedia(DEUX_VOLETS).addEventListener("change", () => { if (affiche) { affiche = null; afficher(); } });   // passage à deux volets (ou retour)
    VUES = (await lire("/api/vues")).vues;
    const permis = await lire("/api/actions").catch(() => ({}));
    ACTIONS = permis.actives === true; MESSAGES = permis.messages === true;            // sans [interface] actions = true : aucun bouton, aucun envoi
    CONVERSATIONS = await lire("/api/conversations").then(x => x.agents, () => []);    // les pages « Conversation » ouvertes
    const ongs = ongletsBerger();
    courant = { mode: "berger", type: ongs[0].tete.type };
    navigation(); await afficher(); await compter();
    boucle(() => fluxVivant() ? null : afficher(true), 5000);                          // repli : la vue visible, 5 s APRÈS la fin de la précédente
    ouvrirFlux();
    boucle(compter, 30000); setInterval(age, 1000);
  } catch (e) {
    dire(String(e.message || e), true);
  }
}
demarrer();
