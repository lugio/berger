// Finition de l'interface (spec docs/plans/2026-11-05-interface-finition-ui-spec.md) : la page MESURÉE dans un vrai navigateur
// (Playwright, s'il est présent : PAS une dépendance du projet) — lancé par tests/interface-finition.py avec le lien d'entrée d'une
// installation jetable (actions actives, faux courtier). Aux 4 largeurs de la spec et dans les 2 thèmes : contraste calculé sur
// chaque nœud de texte visible (le pire cas est cité), tailles, cibles, débordement, titre jamais coupé au milieu d'un mot ; puis
// clavier (Échap, Tab piégé, retour du focus), parcours d'une décision en 2 clics, refus sans motif impossible, rafraîchissement
// fenêtre ouverte (motif gardé), CLS, À lire en deux volets, convention En bref / Pour toi / Détail replié, thème mémorisé.
// Sortie : une ligne JSON {contrôle: "ok" | ce qui ne va pas}, ou {"#lancement": "NON JOUÉ …"} sans navigateur.
"use strict";
const [, , lien, cibleValider, cibleRefuser] = process.argv;
let pw;
try { pw = require(process.env.BERGER_PLAYWRIGHT || "playwright"); } catch (e) { console.log(JSON.stringify({ "#lancement": "NON JOUÉ navigateur réel : module Playwright introuvable" })); process.exit(0); }
const LARGEURS = [[1920, 1080], [1440, 900], [820, 1100], [390, 844]], THEMES = ["light", "dark"];
const vueAffichee = p => p.waitForFunction(() => typeof affiche !== "undefined" && affiche && affiche === courant && document.querySelector("#vue").children.length > 0, null, { timeout: 20000 });
const fenetreChargee = p => p.waitForFunction(() => !document.getElementById("voile").hidden && !document.querySelector("#f-corps .chargement"), null, { timeout: 20000 });

// ── mesures dans la page (une portée : la page, ou la fenêtre ouverte) ──
function mesurer({ portee, mobile }) {
  const racine = document.querySelector(portee);
  const rgba = s => { const m = String(s).match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const melange = (c, f) => [0, 1, 2].map(k => c[k] * c[3] + f[k] * (1 - c[3])).concat(1);
  const lum = c => { const v = c.slice(0, 3).map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); }); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  function fond(e) {                                                     // le fond effectif : les fonds des ancêtres composés jusqu'au premier opaque
    const pile = [];
    for (let x = e; x; x = x.parentElement) { const c = rgba(getComputedStyle(x).backgroundColor); if (c && c[3] > 0) { pile.push(c); if (c[3] >= 1) break; } }
    let f = pile.length && pile[pile.length - 1][3] >= 1 ? pile.pop() : [255, 255, 255, 1];
    while (pile.length) f = melange(pile.pop(), f);
    return f;
  }
  const opacite = e => { let o = 1; for (let x = e; x; x = x.parentElement) o *= parseFloat(getComputedStyle(x).opacity); return o; };
  const visible = e => e.getClientRects().length > 0 && getComputedStyle(e).visibility === "visible";
  const nom = e => (e.tagName.toLowerCase() + (e.className && typeof e.className === "string" ? "." + e.className.trim().split(/\s+/).join(".") : ""));
  const pires = [], petits = [], vus = new Set();
  const w = document.createTreeWalker(racine, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const e = n.parentElement; if (!e || !n.textContent.trim() || vus.has(e)) continue; vus.add(e);
    if (!visible(e) || e.closest("svg, option, [aria-hidden='true']")) continue;
    if (e.closest("button:disabled") || opacite(e) < 1) continue;       // un bouton désactivé n'est pas tenu au contraste (WCAG 1.4.3)
    const s = getComputedStyle(e), taille = parseFloat(s.fontSize), gras = parseInt(s.fontWeight, 10) >= 700;
    let c = rgba(s.color); if (!c) continue;
    const f = fond(e); if (c[3] < 1) c = melange(c, f);
    const r = ratio(c, f), seuil = taille >= 24 || (taille >= 18.66 && gras) ? 3 : 4.5;
    if (r < seuil) pires.push({ r: Math.round(r * 100) / 100, seuil, texte: n.textContent.trim().slice(0, 40), ou: nom(e), taille });
    if (taille < 12) petits.push({ taille, texte: n.textContent.trim().slice(0, 30), ou: nom(e) });
  }
  // bordures de champ et de bouton secondaire : 3:1 contre leur fond
  const bords = [];
  for (const e of racine.querySelectorAll("textarea, input, .bouton.secondaire, .bouton.danger")) {
    if (!visible(e) || e.disabled) continue;
    const s = getComputedStyle(e), b = rgba(s.borderTopColor); if (!b || !parseFloat(s.borderTopWidth)) continue;
    const r = ratio(b[3] < 1 ? melange(b, fond(e.parentElement)) : b, fond(e.parentElement));
    if (r < 3) bords.push({ r: Math.round(r * 100) / 100, ou: nom(e) });
  }
  // cibles : 44 px sur mobile pour tout ce qui se touche ; 40 px pour un Bouton partout
  const cibles = [];
  for (const e of racine.querySelectorAll("button, a[href], summary, input, textarea, select")) {
    if (!visible(e) || e.closest("[hidden]")) continue;
    const h = e.getBoundingClientRect().height, min = mobile ? 44 : e.classList.contains("bouton") ? 40 : 0;
    if (h + 0.5 < min) cibles.push({ h: Math.round(h), ou: nom(e), texte: (e.textContent || e.getAttribute("aria-label") || "").trim().slice(0, 25) });
  }
  const f = document.getElementById("f-corps");
  return { pires: pires.sort((a, b) => a.r - b.r).slice(0, 4), nbPires: pires.length, petits: petits.slice(0, 4), bords: bords.slice(0, 4), cibles: cibles.slice(0, 5),
           corps: parseFloat(getComputedStyle(document.body).fontSize), large: document.documentElement.scrollWidth, vue: window.innerWidth,
           fenetre: document.getElementById("voile").hidden ? null : { corps: f.scrollWidth - f.clientWidth, cadre: document.getElementById("fenetre").scrollWidth - document.getElementById("fenetre").clientWidth } };
}
function motsCoupes(sel) {                                              // un mot dont les morceaux tombent sur deux lignes = coupé au milieu
  const e = document.querySelector(sel); if (!e) return ["(absent)"];
  const coupes = [], w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) for (const m of n.textContent.matchAll(/\S+/g)) {
    const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
    const hauts = new Set([...r.getClientRects()].filter(x => x.width > 0).map(x => Math.round(x.top)));
    if (hauts.size > 1) coupes.push(m[0]);
  }
  return coupes;
}
function lecture(sel) {                                                 // le document : 16 px, interligne 1,6, 75 caractères par ligne au plus
  const a = document.querySelector(sel + " .lecture"); if (!a) return { absent: true };
  const s = getComputedStyle(a), t = document.createElement("span"); t.textContent = "0".repeat(75); t.style.whiteSpace = "nowrap"; t.style.position = "absolute"; t.style.visibility = "hidden";
  a.append(t); const mesure = t.getBoundingClientRect().width; t.remove();
  const p = a.querySelector(".markdown") || a;
  return { taille: parseFloat(s.fontSize), interligne: Math.round(parseFloat(s.lineHeight) / parseFloat(s.fontSize) * 100) / 100, largeur: Math.round(p.getBoundingClientRect().width), mesure: Math.round(mesure) };
}
const texteMesure = m => {
  const pb = [];
  if (m.nbPires) pb.push(`${m.nbPires} texte(s) sous le seuil, pire : ${JSON.stringify(m.pires[0])}`);
  if (m.petits.length) pb.push("sous 12 px : " + JSON.stringify(m.petits));
  if (m.bords.length) pb.push("bordure de champ sous 3:1 : " + JSON.stringify(m.bords));
  return pb.length ? pb.join(" ; ") : "ok";
};

(async () => {
  const sortie = {}, ok = (k, v) => { sortie[k] = v === true ? "ok" : v === false ? "non" : v; };
  let b;
  try { b = await pw.chromium.launch(process.env.BERGER_CHROMIUM ? { executablePath: process.env.BERGER_CHROMIUM } : {}); }
  catch (e) { console.log(JSON.stringify({ "#lancement": "NON JOUÉ navigateur réel : chromium ne démarre pas ici (" + String(e.message).split("\n")[0].slice(0, 120) + ")" })); return; }
  try {
    for (const [lg, ht] of LARGEURS) for (const theme of THEMES) {
      const ctx = await b.newContext({ viewport: { width: lg, height: ht }, colorScheme: theme }), p = await ctx.newPage(), erreurs = [];
      p.on("pageerror", e => erreurs.push(e.message));
      const mobile = lg <= 390, nomC = `${lg} px ${theme === "light" ? "clair" : "sombre"}`;
      await p.goto(lien); await p.waitForSelector("#vue .grille", { timeout: 20000 }); await vueAffichee(p);
      const corps = await p.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize));
      ok(`${nomC} : corps du texte en 15 px au moins (${corps} px)`, corps >= 15);
      // QA du 05/11 (1920 px) : l'Accueil occupe sa place, centré — jamais un grand vide d'un seul côté ; le logo est dans la marque ;
      // aucun nom d'agent coupé sans moyen de le lire (le nom entier au survol)
      if (lg >= 1440) {
        const g = await p.evaluate(() => { const x = document.querySelector("#vue .grille").getBoundingClientRect(), l = document.querySelector(".laterale").getBoundingClientRect();
                                           return { gauche: Math.round(x.left - l.right), droite: Math.round(window.innerWidth - x.right), w: window.innerWidth }; });
        ok(`${nomC} : Accueil centré (vide ${g.gauche} px à gauche, ${g.droite} px à droite), vide à droite ≤ 10 %`, Math.abs(g.gauche - g.droite) <= 4 && g.droite <= 0.1 * g.w || JSON.stringify(g));
        const n = await p.evaluate(() => [...document.querySelectorAll("#liste-agents .entree")].map(e => { const t = e.querySelector(".entree-libelle");
          return { nom: e.getAttribute("title"), libelle: t.textContent, coupe: t.scrollWidth > t.clientWidth + 1 }; }));
        const pb = n.filter(x => !x.nom || x.coupe && !x.nom.endsWith(x.libelle));
        ok(`${nomC} : barre latérale — ${n.length} agents, chacun avec son nom entier au survol, aucun libellé coupé sans lui`, n.length > 0 && !pb.length || JSON.stringify(pb.slice(0, 3)));
        const logo = await p.evaluate(() => { const i = document.querySelector(".marque img.logo"); return i && i.complete && i.naturalWidth === 512 && i.getBoundingClientRect().width === 32; });
        ok(`${nomC} : le logo est dans la marque de la barre latérale (512 px réduit à 32 px)`, logo);
      } else if (mobile) {
        const logo = await p.evaluate(() => { const i = document.querySelector(".entete img.logo-entete"); return !!i && i.complete && i.naturalWidth === 512 && i.getClientRects().length > 0; });
        ok(`${nomC} : le logo reste visible dans l'en-tête (marque latérale cachée)`, logo);
      }
      // chaque onglet : contraste, tailles, cibles, débordement
      const n = await p.locator("#onglets .entree[data-rang]").count(), pbs = { contraste: [], cibles: [], debord: [] };
      for (let o = 0; o < n; o++) {
        const e = p.locator(`#onglets .entree[data-rang="${o}"]`);
        if (o) {
          if (await e.isVisible()) await e.click();
          else { await p.locator("#onglets .entree[data-plus]").click(); await p.waitForSelector("#voile:not([hidden])"); await p.locator(`#f-corps .entree[data-vue="${await e.getAttribute("data-vue")}"]`).click(); }
          await p.waitForFunction(r => document.querySelector(`#onglets .entree[data-rang="${r}"]`).getAttribute("aria-current") === "page", o, { timeout: 20000 }); await vueAffichee(p);
        }
        await p.waitForTimeout(150);
        const m = await p.evaluate(mesurer, { portee: "body", mobile }), t = texteMesure(m);
        if (t !== "ok") pbs.contraste.push(`onglet ${o + 1} : ${t}`);
        if (m.cibles.length) pbs.cibles.push(`onglet ${o + 1} : ${JSON.stringify(m.cibles)}`);
        if (m.large > m.vue) pbs.debord.push(`onglet ${o + 1} : ${m.large} pour ${m.vue}`);
      }
      ok(`${nomC} : contraste AA et rien sous 12 px, sur chaque nœud de texte des ${n} onglets`, pbs.contraste.join(" | ") || true);
      ok(`${nomC} : cibles ${mobile ? "de 44 px (mobile)" : "de 40 px (Boutons)"} au moins`, pbs.cibles.join(" | ") || true);
      ok(`${nomC} : aucun défilement horizontal de la page`, pbs.debord.join(" | ") || true);
      // À lire : un document ouvert (volet à 1920, Fenêtre en dessous de 1280)
      const alire = await p.evaluate(() => (ongletsBerger().find(o => o.membres.some(v => DEDIES[v.type] && DEDIES[v.type].plein)) || {}).tete.type);
      await p.evaluate(t => aller({ mode: "berger", type: t }), alire); await vueAffichee(p);
      if (lg > 1280) {
        await p.waitForSelector("#vue .volet-lecture[data-charge] .lecture", { timeout: 20000 });
        const g = await p.evaluate(() => { const l = document.querySelector("#vue .volets-liste").getBoundingClientRect(), v = document.querySelector("#vue .volet-lecture").getBoundingClientRect(),
                                                 t = document.querySelector("#vue .volet-lecture .lecture").getBoundingClientRect(), s = document.querySelector(".laterale").getBoundingClientRect();
                                           return { liste: Math.round(l.width), gauche: Math.round(l.left - s.right), droite: Math.round(window.innerWidth - v.right), w: window.innerWidth, cote: v.left > l.right,
                                                    cadre: Math.round(v.right - t.right), cadreLarge: Math.round(v.width) }; });
        if (lg === 1920) {
          ok(`${nomC} : À lire en deux volets (liste ${g.liste} px à gauche, document à droite), centrés (vide ${g.gauche} px à gauche, ${g.droite} px à droite ≤ 300)`,
             g.cote && Math.abs(g.liste - 360) <= 2 && Math.abs(g.gauche - g.droite) <= 4 && g.droite <= 300 || JSON.stringify(g));
          ok(`${nomC} : le cadre du document suit sa colonne de lecture (${g.cadreLarge} px, ${g.cadre} px entre le texte et le bord, ≤ 40)`, g.cadre <= 40 || JSON.stringify(g));
        }
        const m = await p.evaluate(mesurer, { portee: "#vue .volet-lecture", mobile });
        ok(`${nomC} : document ouvert dans le volet — contraste AA, rien sous 12 px`, texteMesure(m));
        // un document SANS geste (déjà lu, ou actions désactivées) : le volet n'écrit jamais « null » ni « undefined »
        const lu = p.locator("#vue .volets-liste li.lu button[data-objet]").first();
        if (await lu.count()) {
          const id = await lu.getAttribute("data-a"); await lu.click();
          await p.waitForFunction(i => { const v = document.querySelector("#vue .volet-lecture"); return v && v.getAttribute("data-charge") === i; }, id, { timeout: 20000 });
          const t = await p.evaluate(() => ({ vue: document.getElementById("vue").innerText, geste: !!document.querySelector("#vue .volet-lecture [data-geste]") }));
          ok(`${nomC} : volet d'un document déjà lu, sans geste — ni « null » ni « undefined » dans la vue`, !t.geste && !/\b(null|undefined)\b/.test(t.vue) || JSON.stringify({ geste: t.geste, mot: (t.vue.match(/.{0,30}\b(null|undefined)\b.{0,10}/) || [])[0] }));
          await p.locator("#vue .volets-liste button[data-objet]").first().click();
          await p.waitForFunction(() => { const v = document.querySelector("#vue .volet-lecture"); return v && v.getAttribute("data-charge") === v.getAttribute("data-doc"); }, null, { timeout: 20000 });
        } else ok(`${nomC} : volet d'un document déjà lu, sans geste`, "aucun document lu dans le jeu");
        const lec = await p.evaluate(lecture, "#vue .volet-lecture");
        ok(`${nomC} : document en 16 px, interligne 1,6, 75 caractères par ligne au plus`, lec.taille === 16 && lec.interligne === 1.6 && lec.largeur <= lec.mesure + 1 || JSON.stringify(lec));
      } else {
        const v = await p.evaluate(() => getComputedStyle(document.querySelector("#vue .volet-lecture")).display);
        ok(`${nomC} : À lire en une liste pleine largeur (pas de volet)`, v === "none" || v);
        await p.locator("#vue .volets-liste button[data-objet]").first().click(); await fenetreChargee(p);
        const m = await p.evaluate(mesurer, { portee: "#fenetre", mobile }), t = texteMesure(m);
        ok(`${nomC} : document ouvert dans la Fenêtre — contraste AA, rien sous 12 px${mobile ? ", cibles de 44 px" : ""}`, t === "ok" && !m.cibles.length ? true : t + (m.cibles.length ? " ; cibles " + JSON.stringify(m.cibles) : ""));
        ok(`${nomC} : aucun défilement horizontal dans la Fenêtre`, m.fenetre && m.fenetre.corps <= 0 && m.fenetre.cadre <= 0 && m.large <= m.vue || JSON.stringify(m.fenetre));
        const lec = await p.evaluate(lecture, "#f-corps");
        ok(`${nomC} : document en 16 px, interligne 1,6, 75 caractères par ligne au plus`, lec.taille === 16 && lec.interligne === 1.6 && lec.largeur <= lec.mesure + 1 || JSON.stringify(lec));
        const larg = await p.evaluate(() => Math.round(document.getElementById("fenetre").getBoundingClientRect().width));
        ok(`${nomC} : Fenêtre de ${lg > 820 ? "820 px" : "toute la largeur"} (${larg} px)`, lg > 820 ? larg === 820 : larg === lg);
        if (mobile) {
          const coupes = await p.evaluate(motsCoupes, "#f-titre");
          await p.evaluate(() => { document.getElementById("f-titre").textContent = (VUES.find(v => DEDIES[v.type] && DEDIES[v.type].titre) || {}).titre; });
          const coupes2 = await p.evaluate(motsCoupes, "#f-titre"), titre2 = await p.textContent("#f-titre");
          ok(`${nomC} : titre de la Fenêtre jamais coupé au milieu d'un mot (« ${titre2} », puis le titre du document)`, !coupes.length && !coupes2.length || JSON.stringify([coupes, coupes2]));
        }
        await p.keyboard.press("Escape"); await p.waitForSelector("#voile", { state: "hidden" });
      }
      // clavier : Échap ferme, Tab reste dans la fenêtre, le focus revient à l'élément d'origine (même après un rafraîchissement)
      if (theme === "light" && (lg === 1440 || lg === 390)) {
        await p.evaluate(() => aller({ mode: "berger", type: ongletsBerger()[0].tete.type })); await vueAffichee(p);
        const origine = p.locator("#vue button[data-objet]").first(), cle = await origine.getAttribute("data-a");
        await origine.focus(); await p.keyboard.press("Enter"); await fenetreChargee(p);
        let dehors = 0;
        for (let k = 0; k < 12; k++) { await p.keyboard.press(k % 4 === 3 ? "Shift+Tab" : "Tab"); if (!(await p.evaluate(() => document.getElementById("fenetre").contains(document.activeElement)))) dehors++; }
        await p.evaluate(async () => { RECENTES.clear(); await afficher(true); });   // la carte d'origine est remplacée pendant que la fenêtre est ouverte
        await p.keyboard.press("Escape");
        const r = await p.evaluate(() => ({ ferme: document.getElementById("voile").hidden, a: document.activeElement && document.activeElement.getAttribute("data-a") }));
        ok(`${lg} px : Échap ferme la Fenêtre, Tab y reste (12 appuis, ${dehors} dehors), le focus revient à l'élément d'origine`, r.ferme && !dehors && r.a === cle || JSON.stringify({ ...r, dehors, cle }));
      }
      // parcours d'une décision en 2 clics, refus sans motif impossible, rafraîchissement fenêtre ouverte (une seule fois)
      if (lg === 1440 && theme === "light" && cibleValider) {
        await p.evaluate(() => aller({ mode: "berger", type: ongletsBerger()[0].tete.type })); await vueAffichee(p);
        let clics = 0; const y0 = await p.evaluate(() => window.scrollY);
        await p.locator(`#vue [data-decision="${cibleValider}"] button[data-geste="valider"]`).click(); clics++;
        await p.waitForSelector("#f-pied button[data-confirmer]:not([disabled])", { timeout: 20000 });
        const apercu = await p.evaluate(() => ({ titre: document.getElementById("f-corps").textContent, refuser: !!document.querySelector("#f-pied [data-refus]") }));
        await p.locator("#f-pied button[data-confirmer]").click(); clics++;
        await p.waitForFunction(n => !document.getElementById("annonce").hidden && document.getElementById("annonce").textContent.includes("n° " + n), cibleValider, { timeout: 30000 }).catch(() => {});
        const fin = await p.evaluate(n => ({ annonce: document.getElementById("annonce").hidden ? null : document.getElementById("annonce").textContent, carte: !!document.querySelector(`#vue [data-decision="${n}"]`),
                                            fenetre: !document.getElementById("voile").hidden, y: window.scrollY }), cibleValider);
        ok(`parcours : la décision n° ${cibleValider} se valide en ${clics} clics depuis l'Accueil (aperçu et empreinte, Refuser dans le pied), disparaît, « ${fin.annonce} » s'affiche, le défilement ne bouge pas`,
           clics === 2 && apercu.refuser && /Empreinte/.test(apercu.titre) && fin.annonce === `n° ${cibleValider} validée` && !fin.carte && !fin.fenetre && fin.y === y0 || JSON.stringify({ apercu, fin }));
        // refuser : le motif d'abord ; sans motif, la confirmation reste impossible ; un rafraîchissement forcé ne ferme rien et garde le motif
        await p.locator(`#vue [data-decision="${cibleRefuser}"] button[data-geste="valider"]`).click();
        await p.waitForSelector("#f-pied [data-refus]:not([disabled])", { timeout: 20000 }); await p.locator("#f-pied [data-refus]").click();
        await p.waitForSelector("#g-texte", { timeout: 20000 });
        const sansMotif = await p.evaluate(() => document.querySelector("#f-pied [data-confirmer]").disabled);
        await p.locator("#f-pied [data-confirmer]").click({ force: true }).catch(() => {});
        const encore = await p.evaluate(n => !!document.querySelector(`#vue [data-decision="${n}"]`) && !document.getElementById("voile").hidden, cibleRefuser);
        ok("refuser sans motif est impossible (confirmation désactivée, rien n'est envoyé)", sansMotif && encore);
        await p.fill("#g-texte", "motif-du-test-de-finition");
        const avant = await p.evaluate(() => document.getElementById("f-titre").textContent);
        await p.evaluate(async () => { RECENTES.clear(); await afficher(true); await compter(); });
        const apres = await p.evaluate(() => ({ ouverte: !document.getElementById("voile").hidden, motif: (document.getElementById("g-texte") || {}).value, titre: document.getElementById("f-titre").textContent }));
        ok("un rafraîchissement forcé, fenêtre ouverte et motif saisi, ne ferme pas la fenêtre et garde le motif", apres.ouverte && apres.motif === "motif-du-test-de-finition" && apres.titre === avant || JSON.stringify(apres));
        await p.locator("#f-pied [data-confirmer]").click();
        await p.waitForFunction(n => !document.getElementById("annonce").hidden && document.getElementById("annonce").textContent.includes("n° " + n), cibleRefuser, { timeout: 30000 }).catch(() => {});
        const r = await p.evaluate(n => ({ annonce: document.getElementById("annonce").textContent, carte: !!document.querySelector(`#vue [data-decision="${n}"]`) }), cibleRefuser);
        ok(`refuser avec motif : « n° ${cibleRefuser} refusée », la carte disparaît`, r.annonce === `n° ${cibleRefuser} refusée` && !r.carte || JSON.stringify(r));
      }
      // fluidité : aucun déplacement de la mise en page de plus de 0,1 (CLS) au rafraîchissement, Accueil et À lire
      if (theme === "light") for (const [qui, type] of [["Accueil", null], ["À lire", alire]]) {
        await p.evaluate(t => aller({ mode: "berger", type: t || ongletsBerger()[0].tete.type }), type); await vueAffichee(p);
        if (type && lg > 1280) await p.waitForSelector("#vue .volet-lecture[data-charge]", { timeout: 20000 });
        await p.evaluate(() => { for (const d of document.querySelectorAll("#vue details[data-cle]")) d.open = true; });
        await p.waitForTimeout(400);
        const cls = await p.evaluate(async () => {
          let total = 0; const o = new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) total += e.value; });
          o.observe({ type: "layout-shift", buffered: false });
          for (let k = 0; k < 3; k++) { RECENTES.clear(); await afficher(true); await compter(); await new Promise(r => setTimeout(r, 250)); }
          o.disconnect(); return Math.round(total * 1000) / 1000;
        });
        ok(`${lg} px : ${qui} rafraîchi 3 fois (blocs dépliés) — CLS ${cls} ≤ 0,1`, cls <= 0.1);
      }
      if (process.env.BERGER_CAPTURES) for (const [k, type] of [["accueil", null], ["alire", alire], ["tableau", "__2"], ["coulisses", "__4"]]) {   // captures pour l'œil (facultatives)
        await p.evaluate(t => { fermerFenetre(); aller({ mode: "berger", type: t && t.startsWith("__") ? ongletsBerger()[+t.slice(2) - 1].tete.type : t || ongletsBerger()[0].tete.type }); }, type); await vueAffichee(p);
        if (type === alire && lg > 1280) await p.waitForSelector("#vue .volet-lecture[data-charge]", { timeout: 20000 }).catch(() => {});
        await p.waitForTimeout(300); await p.screenshot({ path: `${process.env.BERGER_CAPTURES}/${lg}-${theme}-${k}.png`, fullPage: false });
        if (type === alire && lg <= 1280) { await p.locator("#vue .volets-liste button[data-objet]").first().click(); await fenetreChargee(p);
          await p.screenshot({ path: `${process.env.BERGER_CAPTURES}/${lg}-${theme}-document.png` }); await p.keyboard.press("Escape"); }
      }
      ok(`${nomC} : aucune erreur de script`, erreurs.length ? erreurs.join(" ; ").slice(0, 200) : true);
      await ctx.close();
    }

    // À lire : convention En bref / Pour toi en tête, Détail replié puis ouvert au clic ; document lu au contraste AA, poids normal
    {
      const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 } }), p = await ctx.newPage();
      await p.goto(lien); await p.waitForSelector("#vue .grille", { timeout: 20000 }); await vueAffichee(p);
      await p.evaluate(() => aller({ mode: "berger", type: ongletsBerger().find(o => o.membres.some(v => DEDIES[v.type] && DEDIES[v.type].plein)).tete.type })); await vueAffichee(p);
      const forme = p.locator("#vue .volets-liste button[data-objet]", { hasText: "Forme de fond" });
      await forme.click(); await p.waitForFunction(() => { const v = document.querySelector("#vue .volet-lecture"); return v && v.getAttribute("data-charge") === v.getAttribute("data-doc") && /Forme de fond/.test(v.textContent); }, null, { timeout: 20000 });
      const r = await p.evaluate(() => {
        const a = document.querySelector("#vue .volet-lecture .lecture"), e = a && a.firstElementChild, d = a && a.querySelector("details.detail");
        return { premier: e && e.className, bref: e && /^En bref/.test(e.children[0].textContent), toi: e && /^Pour toi/.test(e.children[1].textContent),
                 bord: e && getComputedStyle(e).borderLeftWidth, ouvert: d && d.open, cache: d && !d.querySelector(".markdown").checkVisibility() };
      });
      ok("À lire : « En bref » puis « Pour toi » rendus en tête, dans un encadré doux sans bordure gauche", r.premier === "essentiel" && r.bref && r.toi && r.bord === "0px" || JSON.stringify(r));
      ok("À lire : la section « Détail » est repliée à l'ouverture", r.ouvert === false && r.cache || JSON.stringify(r));
      await p.locator("#vue .volet-lecture details.detail > summary").click();
      const ouvert = await p.evaluate(() => { const d = document.querySelector("#vue .volet-lecture details.detail"); return d.open && /le d[ée]tail complet/.test(d.textContent) && d.querySelector(".markdown").checkVisibility(); });
      ok("À lire : « Détail » s'ouvre d'un clic", ouvert);
      await p.evaluate(async () => { RECENTES.clear(); await afficher(true); });
      ok("À lire : le document du volet et son Détail ouvert restent tels quels au rafraîchissement", await p.evaluate(() => { const d = document.querySelector("#vue .volet-lecture details.detail"); return !!d && d.open; }));
      // « Marquer lu » depuis le volet : le volet se relit (« lu », plus de bouton), le Détail ouvert le reste
      await p.locator('#vue .volet-lecture .pied button[data-geste="lu"]').click();
      await p.waitForSelector("#f-pied button[data-confirmer]:not([disabled])", { timeout: 20000 }); await p.locator("#f-pied button[data-confirmer]").click();
      await p.waitForFunction(() => { const v = document.querySelector("#vue .volet-lecture"); return v && /· lu$/.test((v.querySelector(".meta-ligne") || {}).textContent || ""); }, null, { timeout: 30000 }).catch(() => {});
      const apresLu = await p.evaluate(() => { const v = document.querySelector("#vue .volet-lecture"); return { meta: (v.querySelector(".meta-ligne") || {}).textContent, bouton: !!v.querySelector('[data-geste="lu"]'),
                                                 detail: !!(v.querySelector("details.detail") || {}).open, fenetre: !document.getElementById("voile").hidden }; });
      ok("À lire : « Marquer lu » depuis le volet — le volet passe à « lu », sans bouton, Détail toujours ouvert", /· lu$/.test(apresLu.meta) && !apresLu.bouton && apresLu.detail && !apresLu.fenetre || JSON.stringify(apresLu));
      for (const theme of ["clair", "sombre"]) {
        await p.evaluate(t => { document.documentElement.setAttribute("data-theme", t); }, theme);
        const lu = await p.evaluate(mesurer, { portee: "#vue .volets-liste .lu", mobile: false }), poids = await p.evaluate(() => getComputedStyle(document.querySelector("#vue .volets-liste .lu .doc-titre")).fontWeight);
        ok(`À lire (${theme}) : un document lu garde un contraste de 4,5:1 et un poids normal (${poids})`, texteMesure(lu) === "ok" && poids === "400" || texteMesure(lu) + " poids " + poids);
      }
      await ctx.close();
    }
    // thème : celui du système, puis le choix mémorisé (clair → sombre → système), gardé au rechargement
    {
      const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light" }), p = await ctx.newPage();
      await p.goto(lien); await vueAffichee(p);
      const fond = () => p.evaluate(() => getComputedStyle(document.body).backgroundColor);
      const f0 = await fond(); await p.click("#theme"); const f1 = await fond(); await p.click("#theme"); const f2 = await fond();
      await p.reload(); await vueAffichee(p); const f3 = await fond(), t3 = await p.getAttribute("html", "data-theme");
      await p.click("#theme"); const f4 = await fond();
      ok("thème : clair puis sombre au choix, mémorisé au rechargement, puis retour au thème du système", f0 === f1 && f2 !== f1 && f3 === f2 && t3 === "sombre" && f4 === f0 || JSON.stringify([f0, f1, f2, f3, t3, f4]));
      const d = await p.evaluate(() => [...document.querySelectorAll("*")].map(e => getComputedStyle(e).transitionDuration.split(",").map(parseFloat)).flat().reduce((a, b) => Math.max(a, b), 0));
      ok(`transitions de 150 ms au plus (la plus longue : ${d * 1000} ms)`, d <= 0.15);
      const c = await p.evaluate(() => { const x = document.createElement("p"); x.className = "chargement"; document.body.append(x); const s = getComputedStyle(x); const r = s.animationDelay; x.remove(); return r; });
      ok(`l'état « chargement » devient visible après 300 ms (${c})`, c === "0.3s");
      await ctx.close();
      const ctx2 = await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" }), p2 = await ctx2.newPage();
      await p2.goto(lien); await vueAffichee(p2);
      const d2 = await p2.evaluate(() => [...document.querySelectorAll("*")].map(e => getComputedStyle(e).transitionDuration.split(",").map(parseFloat)).flat().reduce((a, b) => Math.max(a, b), 0));
      ok("prefers-reduced-motion : rien ne bouge (aucune transition)", d2 === 0);
      await ctx2.close();
    }
  } catch (e) { sortie["#exécution"] = "ERREUR " + String(e.message).split("\n")[0]; }
  await b.close();
  console.log(JSON.stringify(sortie));
})();
