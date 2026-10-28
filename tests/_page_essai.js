// Essai de la page (bin/page/app.js) dans un FAUX DOM, sans navigateur ni réseau — lancé par tests/interface.py (node, s'il
// est présent sur la machine : ce n'est PAS une dépendance du projet ; absent, le contrôle est dit NON JOUÉ).
// Entrée (fichier JSON) : { schemas: {nom: schéma}, jeux: [{type, a, dedie, donnees, autres: {vue: données}}] }. Chaque donnée est enveloppée
// dans un Proxy qui LÈVE une erreur si la page lit un champ absent des données : la page ne lit que des champs déclarés
// (les données sont déjà contrôlées contre leur schéma). Sortie : une ligne JSON {jeu: "ok" | "ERREUR …" | "TEXTE …"}.
"use strict";
const fs = require("fs"), vm = require("vm");
const [, , fichierApp, fichierJeux] = process.argv;

class Noeud {
  constructor(nom) { this.nom = nom; this.enfants = []; this.attrs = {}; this.dataset = {}; this.style = {}; this.hidden = false;
                     this.classList = { contains: c => (this.attrs.class || "").split(" ").includes(c), add() {}, remove() {} }; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  addEventListener(type, f) { (this.ecouteurs = this.ecouteurs || {})[type] = (this.ecouteurs[type] || []).concat(f); }
  append(...x) { this.enfants.push(...x); }
  replaceChildren(...x) { this.enfants = x; }
  get childNodes() { return this.enfants; }
  get textContent() { return this.enfants.map(e => e.textContent).join(""); }
  set textContent(t) { this.enfants = [{ textContent: String(t) }]; }
}
const document = { createElement: n => new Noeud(n), createElementNS: (ns, n) => new Noeud(n), createTextNode: t => ({ textContent: String(t) }), getElementById: () => new Noeud("x"),
                   addEventListener() {}, hidden: false };
// flux temps réel : un faux EventSource (les instances sont gardées) et un faux setTimeout (les minuteries aussi)
const sources = [], minuteries = [];
class FauxEventSource { constructor(url) { this.url = url; this.readyState = 0; this.ecoutes = {}; sources.push(this); }
                        addEventListener(t, f) { this.ecoutes[t] = f; } }
const contexte = vm.createContext({ EventSource: FauxEventSource, setTimeout: (f, ms) => { minuteries.push([f, ms]); }, document, location: { hash: "", pathname: "/" }, history: { replaceState() {} }, window: { scrollTo() {} },
                                    fetch: async () => ({ ok: false, json: async () => ({}) }), setInterval() {}, console, Date, Math, JSON, Object, Array,
                                    String, Number, Set, Error, encodeURIComponent });
const code = fs.readFileSync(fichierApp, "utf8").replace(/\ndemarrer\(\);\s*$/, "\n");
vm.runInContext(code + "\n;globalThis.__page = { DEDIES, generique, lire, ouvrirFlux, etatFlux: () => ({ ouvert: fluxVivant(), flux }), vieillir: () => { signal -= 41000; }, viser: c => { courant = c; }, SCHEMAS_mettre: s => { Object.assign(SCHEMAS, s); } };", contexte);
const page = contexte.__page;
const { schemas, jeux } = JSON.parse(fs.readFileSync(fichierJeux, "utf8"));
page.SCHEMAS_mettre(schemas);

function strict(v, chemin) {                                             // lire un champ absent = erreur nommée
  if (v === null || typeof v !== "object") return v;
  const enfants = Array.isArray(v) ? v.map((x, i) => strict(x, chemin + "[" + i + "]"))
                                   : Object.fromEntries(Object.entries(v).map(([k, x]) => [k, strict(x, chemin + "." + k)]));
  if (Array.isArray(v)) return enfants;
  return new Proxy(enfants, { get(t, k) {
    if (typeof k === "symbol" || k in t || k === "toJSON" || k === "then") return t[k];
    throw new Error("champ absent des données : " + chemin + "." + String(k));
  } });
}
const sortie = {}, cadres = [];
function chercher(n, nom, out) { if (n && n.nom === nom) out.push(n); for (const e of (n && n.enfants) || []) chercher(e, nom, out); return out; }
for (const j of jeux) {
  const nom = j.type + (j.a ? "." + j.a : "");
  try {
    const d = strict(j.donnees, "$");
    const ded = j.dedie ? page.DEDIES[j.type] : null;
    const n = ded && ded.rendre ? ded.rendre(d, Object.fromEntries(Object.entries(j.autres || {}).map(([k, x]) => [k, strict(x, k)])))
                                : page.generique(schemas[j.type], d);
    if (ded && ded.global) {                                             // ce que la vue donne à l'en-tête : {texte, ton}
      const g = ded.global(d);
      if (!g || typeof g.texte !== "string" || !g.texte || typeof g.ton !== "string") throw new Error("global invalide : " + JSON.stringify(g));
    }
    chercher(n, "iframe", cadres);
    if (j.type === "documents" && j.dedie) sortie["#recherche"] = recherche(n, j.donnees.documents);                                       // tout cadre de la page : isolé (vérifié plus bas)
    const t = n.textContent;
    const mauvais = ["undefined", "null", "[object", "NaN"].find(m => t.includes(m));
    sortie[nom] = !t.trim() ? "TEXTE vide" : mauvais ? "TEXTE contient « " + mauvais + " »" : "ok";
    if (j.dedie && DEDIES_COMPTEUR(j)) sortie[nom + "#compteur"] = DEDIES_COMPTEUR(j);
  } catch (e) { sortie[nom] = "ERREUR " + e.message; }
}
function DEDIES_COMPTEUR(j) {                                            // la pastille de l'onglet se calcule sur les données de sa vue
  const c = page.DEDIES[j.type].compteur;
  if (!c) return null;
  if (!j.autres || !(c[0] in j.autres)) return "compteur : données de la vue « " + c[0] + " » absentes";
  const n = c[1](strict(j.autres[c[0]], c[0]));
  return Number.isInteger(n) && n >= 0 ? null : "compteur invalide : " + n;
}
// Documents : la recherche par nom masque les lignes qui ne correspondent pas (sans accent ni casse), et les rend toutes à vide
function recherche(n, docs) {
  const champ = chercher(n, "input", [])[0], lignes_ = [];
  (function f(x) { if (x && x.attrs && "data-nom" in x.attrs) lignes_.push(x); for (const e of (x && x.enfants) || []) f(e); })(n);
  if (!champ || !champ.ecouteurs || !champ.ecouteurs.input) return "aucun champ de recherche";
  if (lignes_.length !== docs.length) return "lignes : " + lignes_.length + " pour " + docs.length + " documents";
  const mot = docs[0].titre.toUpperCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  champ.value = mot; champ.ecouteurs.input.forEach(f => f());
  const vues = lignes_.filter(x => !x.hidden).length;
  champ.value = "zzzz-rien"; champ.ecouteurs.input.forEach(f => f());
  const aucune = lignes_.every(x => x.hidden);
  champ.value = ""; champ.ecouteurs.input.forEach(f => f());
  return vues >= 1 && vues < lignes_.length && aucune && lignes_.every(x => !x.hidden) ? "ok" : "recherche : " + vues + " visibles pour « " + mot + " », aucune=" + aucune;
}
// un livrable .html s'affiche dans un cadre isolé : sandbox = « allow-scripts » exactement (jamais allow-same-origin : origine
// opaque, ni cookie ni accès à la page), source = le livrable tel quel servi par l'interface, sans référent
const html = jeux.some(j => j.donnees && j.donnees.genre === "html" && j.donnees.texte === null);
sortie["#cadre"] = !html ? "aucun livrable .html dans le jeu" : !cadres.length ? "aucun cadre rendu"
  : cadres.every(c => c.attrs.sandbox === "allow-scripts" && /^\/api\/livrable\/[0-9a-f]{16}\/html$/.test(c.attrs.src) && c.attrs.referrerpolicy === "no-referrer")
    ? "ok" : "cadre mal isolé : " + JSON.stringify(cadres.map(c => c.attrs));
// une seule demande en vol pour toute la page : 6 lectures lancées ensemble passent l'une après l'autre, même si l'une échoue
(async () => {
  let enCours = 0, maxi = 0, n = 0;
  contexte.fetch = async (url) => { enCours++; maxi = Math.max(maxi, enCours); n++; await new Promise(r => setTimeout(r, 15)); enCours--;
                                    return url.includes("echec") ? { ok: false, status: 504, json: async () => ({ erreur: "délai" }) }
                                                                 : { ok: true, status: 200, json: async () => ({ ok: 1 }) }; };
  const r = await Promise.allSettled(["/a", "/b", "/echec", "/c", "/d", "/e"].map(u => page.lire(u)));
  sortie["#file"] = maxi === 1 && n === 6 && r.filter(x => x.status === "rejected").length === 1 ? "ok" : "demandes en vol : " + maxi + " (" + n + " lancées)";
  // temps réel : flux ouvert → la boucle de 5 s se tait ; « change » → la page relit ; coupure → repli à 5 s, puis le flux
  // reprend seul (EventSource se reconnecte) ; fermé pour de bon (503) → nouvel essai 30 s plus tard
  const e = [];
  page.viser({ mode: "berger", type: "essai" }); page.ouvrirFlux(); const es = sources[0];
  if (!es || es.url !== "/api/flux") e.push("pas de flux ouvert sur /api/flux");
  else {
    es.onopen(); if (!page.etatFlux().ouvert) e.push("ouvert : la boucle de 5 s ne se tait pas");
    const avant = n; es.ecoutes.change(); await new Promise(r => setTimeout(r, 120));
    if (n === avant) e.push("« change » : aucune relecture");
    es.readyState = 0; es.onerror(); if (page.etatFlux().ouvert) e.push("coupure : pas de repli à 5 s");
    if (sources.length !== 1) e.push("coupure passagère : un second flux a été ouvert (EventSource se reconnecte seul)");
    es.readyState = 1; es.onopen(); if (!page.etatFlux().ouvert) e.push("reconnexion : le flux ne reprend pas seul");
    page.vieillir(); if (page.etatFlux().ouvert) e.push("flux muet plus de 40 s : la boucle de 5 s ne reprend pas");
    es.ecoutes.battement(); if (!page.etatFlux().ouvert) e.push("battement : le flux n'est pas tenu pour vivant");
    es.readyState = 2; es.onerror();
    const m = minuteries.find(x => x[1] === 30000);
    if (page.etatFlux().ouvert || !m) e.push("fermé (503) : pas de repli ou pas de nouvel essai à 30 s");
    else { m[0](); if (sources.length !== 2) e.push("nouvel essai : pas de nouveau flux"); }
  }
  sortie["#flux"] = e.length ? e.join(" ; ") : "ok";
  console.log(JSON.stringify(sortie));
})();
