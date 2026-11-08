// La page dans un VRAI navigateur (Playwright, s'il est présent : PAS une dépendance du projet) — lancé par tests/interface-v2.py
// avec le lien d'entrée d'une installation jetable. Sortie : une ligne JSON {contrôle: "ok" | ce qui ne va pas}, ou
// {"#lancement": "NON JOUÉ …"} quand le navigateur ne démarre pas sur cette machine.
"use strict";
const lien = process.argv[2];
let pw;
try { pw = require(process.env.BERGER_PLAYWRIGHT || "playwright"); } catch (e) { console.log(JSON.stringify({ "#lancement": "NON JOUÉ navigateur réel : module Playwright introuvable" })); process.exit(0); }
const LARGEURS = [[1440, 900], [820, 1100], [390, 844]];
const ONGLETS = 6;                                                       // Accueil, Tableau, À lire, Coulisses, Documents, Réglages (Décisions retiré ; Réglages : spec 2026-11-05-interface-reglages)
const POIDS_MAX = 400 * 1024;                                            // premier chargement (page, script, style, icônes, données) : 400 Kio au plus
// Attendre un ÉTAT, jamais une durée : la vue demandée est affichée (le rafraîchissement a fini).
const vueAffichee = p => p.waitForFunction(() => typeof affiche !== "undefined" && affiche && affiche === courant && document.querySelector("#vue").children.length > 0, null, { timeout: 20000 });

// ce que la page montre : débordement, « null », émoji, bordure gauche colorée, onglet Décisions
function constat() {
  const corps = document.body.innerText, gauche = [];
  for (const x of document.querySelectorAll("body *")) {
    const s = getComputedStyle(x);
    // une bordure GAUCHE qui se distingue (plus épaisse ou d'une autre couleur que la droite) : le liseré interdit ; un cadre égal tout autour est permis
    if (parseFloat(s.borderLeftWidth) > 0 && s.borderLeftStyle !== "none" && x.offsetParent !== null
        && (s.borderLeftWidth !== s.borderRightWidth || s.borderLeftColor !== s.borderRightColor || s.borderRightStyle === "none")) gauche.push(x.className || x.tagName);
  }
  return { large: document.documentElement.scrollWidth, vue: window.innerWidth, nul: /\b(null|undefined|NaN)\b/.test(corps),
           emoji: corps.match(/\p{Extended_Pictographic}/u), gauche: [...new Set(gauche)].slice(0, 5),
           decisions: [...document.querySelectorAll("#onglets .entree, .sous-onglets button")].some(b => /Décisions/.test(b.textContent)) };
}

// Relecture Codex du lot 1 (points 1 à 5) : un scénario chacun, dans la vraie page.
async function scenarios(p, sortie) {
  // 1. Chaque bloc replié garde son ouverture au rafraîchissement (pas seulement ceux qui lisent une vue à la demande)
  await p.locator("#onglets .entree[data-rang=\"0\"]").click(); await vueAffichee(p);
  const cles = await p.evaluate(() => { const l = [...document.querySelectorAll("#vue details[data-cle]")].filter(d => !d.querySelector(".a-deplier")).map(d => d.getAttribute("data-cle"));
                                        for (const d of document.querySelectorAll("#vue details[data-cle]")) if (l.includes(d.getAttribute("data-cle"))) d.open = true; return l; });
  await p.evaluate(async () => { RECENTES.clear(); await afficher(true); }); await vueAffichee(p);
  const restes = await p.evaluate(l => l.filter(c => (document.querySelector(`#vue details[data-cle="${CSS.escape(c)}"]`) || {}).open), cles);
  sortie[`1. blocs repliés ouverts gardés au rafraîchissement (${cles.join(", ")})`] = cles.length >= 2 && restes.length === cles.length ? "ok" : `ouverts avant ${cles}, après ${restes}`;
  // 2. Une réponse tardive ne remplace pas la fenêtre ouverte entre-temps
  const r2 = await p.evaluate(async () => {
    const vrai = donnees, type = (VUES.find(v => v.type === "validation") || VUES.find(v => v.donnees) || {}).type;
    donnees = (t, a) => new Promise(ok => setTimeout(() => ok(vrai(t, a)), 700));
    try {
      fenetreObjet(type, "1");
      fenetre("Autre fenêtre", "", el("p", { id: "temoin" }, "témoin"));
      await new Promise(ok => setTimeout(ok, 1500));
      return { titre: document.getElementById("f-titre").textContent, temoin: !!document.getElementById("temoin") };
    } finally { donnees = vrai; fermerFenetre(); }
  });
  sortie["2. réponse tardive ignorée : la fenêtre ouverte entre-temps reste intacte"] = r2.temoin && r2.titre === "Autre fenêtre" ? "ok" : JSON.stringify(r2);
  // 3. Une question (ou un go) trop longue s'ouvre en entier dans une fenêtre
  const long = "Faut-il garder l'ancien écran de connexion pendant la transition, sachant que " + "les utilisateurs du cabinet s'y sont habitués et que ".repeat(4) + "la nouvelle version change le parcours ? FIN-DU-TEXTE";
  const r3 = await p.evaluate(async t => {
    const c = carteAttente({ pour: "toi", genre: "question", titre: "Agent fictif", detail: "« " + t + " »", quand: "", agent: null, n: null, lien: null, commande: null });
    document.getElementById("vue").append(c); const b = c.querySelector("button[data-texte]"); if (!b) return { bouton: false };
    b.click(); const texte = document.getElementById("f-corps").textContent; fermerFenetre(); c.remove();
    return { bouton: true, entier: texte.includes("FIN-DU-TEXTE"), coupe: c.textContent.includes("…") };
  }, long);
  sortie["3. question longue : coupée dans la carte, entière dans une fenêtre"] = r3.bouton && r3.entier && r3.coupe ? "ok" : JSON.stringify(r3);
  // 4. propre() ne colle pas les mots autour du Markdown
  const r4 = await p.evaluate(() => markdown("Avant **important** après `code` fin").textContent);
  sortie["4. Markdown en ligne : les espaces autour restent (« Avant important après code fin »)"] = r4 === "Avant important après code fin" ? "ok" : JSON.stringify(r4);
  // 5. Une lecture encore en cours n'expire pas : la même vue n'est pas relancée
  const r5 = await p.evaluate(async () => {
    const vraiFetch = window.fetch; let n = 0;
    window.fetch = (u, o) => { if (String(u).includes("/api/vue/alire")) { n++; return new Promise(ok => setTimeout(() => ok(vraiFetch(u, o)), 800)); } return vraiFetch(u, o); };
    try {
      RECENTES.clear(); const a = donnees("alire");
      for (const x of RECENTES.values()) x.t -= 60000;                    // plus vieille que le cache de 4 s, mais toujours en cours
      const b = donnees("alire"); await Promise.all([a, b]);
      return { meme: a === b, requetes: n };
    } finally { window.fetch = vraiFetch; }
  });
  sortie["5. cache : une lecture en cours est réutilisée, jamais relancée"] = r5.meme && r5.requetes === 1 ? "ok" : JSON.stringify(r5);
}

(async () => {
  const sortie = {};
  let b;
  try { b = await pw.chromium.launch(process.env.BERGER_CHROMIUM ? { executablePath: process.env.BERGER_CHROMIUM } : {}); }
  catch (e) { console.log(JSON.stringify({ "#lancement": "NON JOUÉ navigateur réel : chromium ne démarre pas ici (" + String(e.message).split("\n")[0].slice(0, 120) + ")" })); return; }
  try {
    for (const [w, h] of LARGEURS) {
      const ctx = await b.newContext({ viewport: { width: w, height: h } }), p = await ctx.newPage();
      const erreurs = [], requetes = [], poids = [];
      p.on("pageerror", e => erreurs.push(e.message));
      p.on("request", r => { const u = new URL(r.url()); if (u.pathname.startsWith("/api/vue/")) requetes.push(u.pathname + u.search); });
      p.on("response", async r => { try { poids.push((await r.body()).length); } catch (e) { /* flux SSE : pas de corps fini */ } });
      await p.goto(lien); await p.waitForSelector("#vue .grille", { timeout: 20000 }); await vueAffichee(p);
      await p.waitForLoadState("networkidle").catch(() => {});
      const doublons = requetes.filter((x, k) => requetes.indexOf(x) !== k);
      if (w === 1440) {
        sortie["une seule requête par vue au premier chargement"] = doublons.length ? "en double : " + doublons.join(", ") : "ok";
        const total = poids.reduce((a, b) => a + b, 0);
        sortie[`poids du premier chargement ≤ ${POIDS_MAX / 1024} Kio (mesuré : ${Math.round(total / 1024)} Kio, ${poids.length} réponses)`] = total <= POIDS_MAX ? "ok" : `${total} octets`;
      }
      const n = await p.locator("#onglets .entree[data-rang]").count();
      sortie[`${w} px : ${ONGLETS} onglets dans la navigation`] = n === ONGLETS ? "ok" : `${n} onglets`;
      for (let onglet = 0; onglet < n; onglet++) {
        if (onglet) {
          const e = p.locator(`#onglets .entree[data-rang="${onglet}"]`);
          if (await e.isVisible()) await e.click();
          else {                                                           // téléphone, tablette : au-delà de la barre du bas, par « Plus »
            await p.locator("#onglets .entree[data-plus]").click(); await p.waitForSelector("#voile:not([hidden])");
            await p.locator(`#f-corps .entree[data-vue="${await e.getAttribute("data-vue")}"]`).click();
          }
          await p.waitForFunction(r => document.querySelector(`#onglets .entree[data-rang="${r}"]`).getAttribute("aria-current") === "page", onglet, { timeout: 20000 });
          await vueAffichee(p);
        }
        const c = await p.evaluate(constat), nom = `${w} px, onglet ${onglet + 1}`;
        sortie[`${nom} : pas de débordement horizontal`] = c.large <= c.vue ? "ok" : `largeur ${c.large} pour ${c.vue}`;
        sortie[`${nom} : ni « null » ni émoji ni bordure gauche`] = !c.nul && !c.emoji && !c.gauche.length ? "ok" : JSON.stringify({ nul: c.nul, emoji: c.emoji, gauche: c.gauche });
        sortie[`${nom} : pas d'onglet Décisions`] = c.decisions ? "Décisions présent" : "ok";
      }
      sortie[`${w} px : aucune erreur de script`] = erreurs.length ? erreurs.join(" ; ").slice(0, 200) : "ok";
      if (w === 1440) {                                                    // menu replié : mémorisé, gardé au rechargement
        await p.click("#replier"); await p.waitForSelector('#app[data-menu="replie"]');
        const avant = await p.getAttribute("#app", "data-menu");
        await p.reload(); await p.waitForSelector("#vue", { timeout: 20000 }); await vueAffichee(p);
        const apres = await p.getAttribute("#app", "data-menu");
        await p.click("#replier"); await p.waitForSelector('#app[data-menu="ouvert"]');
        sortie["menu replié mémorisé au rechargement"] = avant === "replie" && apres === "replie" && (await p.getAttribute("#app", "data-menu")) === "ouvert" ? "ok" : `${avant} → ${apres}`;
        await p.locator("#onglets .entree[data-rang=\"0\"]").click(); await p.waitForSelector("#vue .grille"); await vueAffichee(p);
        const detail = p.locator("#vue button[data-objet]").first();
        if (await detail.count()) {
          await detail.click(); await p.waitForFunction(() => !document.getElementById("voile").hidden && !document.querySelector("#f-corps .pale:only-child"), null, { timeout: 20000 });
          const ouverte = await p.isVisible("#voile"); await p.keyboard.press("Escape"); await p.waitForSelector("#voile", { state: "hidden" });
          sortie["fenêtre de détail : s'ouvre, se ferme avec Échap"] = ouverte && !(await p.isVisible("#voile")) ? "ok" : `ouverte=${ouverte}`;
        } else sortie["fenêtre de détail : s'ouvre, se ferme avec Échap"] = "aucun détail à ouvrir dans le jeu";
        await scenarios(p, sortie);
      }
      await ctx.close();
    }
  } catch (e) { sortie["#exécution"] = "ERREUR " + String(e.message).split("\n")[0]; }
  await b.close();
  console.log(JSON.stringify(sortie));
})();
