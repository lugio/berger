// Page « Réglages » (spec docs/plans/2026-11-05-interface-reglages-spec.md) MESURÉE dans un vrai navigateur (Playwright, s'il est présent :
// PAS une dépendance du projet) — lancé par tests/interface-reglages.py avec le lien d'entrée d'une installation jetable et la liste des
// marqueurs placés dans les valeurs sensibles. À 390, 820, 1280, 1440 et 1920 px, dans les 2 thèmes : l'onglet s'ouvre, l'en-tête
// « Ces réglages se changent dans ~/berger/config.toml », des valeurs « [masqué] », les signalements ; aucun marqueur dans le DOM ; ni
// « null » ni « undefined » ; aucun champ ni bouton qui modifie ; aucun défilement horizontal.
// Sortie : une ligne JSON {contrôle: "ok" | ce qui ne va pas}, ou {"#lancement": "NON JOUÉ …"} sans navigateur.
"use strict";
const [, , lien, marqueurs] = process.argv;
let pw;
try { pw = require(process.env.BERGER_PLAYWRIGHT || "playwright"); } catch (e) { console.log(JSON.stringify({ "#lancement": "NON JOUÉ navigateur réel : module Playwright introuvable" })); process.exit(0); }
const LARGEURS = [[390, 844], [820, 1100], [1280, 800], [1440, 900], [1920, 1080]], THEMES = ["light", "dark"];
const caches = (marqueurs || "").split(",").filter(Boolean);
const res = {};
const ok = (k, v) => { res[k] = v === true ? "ok" : (v === false ? "non" : String(v)); };

(async () => {
  let nav;
  try { nav = await pw.chromium.launch(process.env.BERGER_CHROMIUM ? { executablePath: process.env.BERGER_CHROMIUM } : {}); }
  catch (e) { console.log(JSON.stringify({ "#lancement": "NON JOUÉ navigateur réel : Chromium introuvable (" + String(e.message).split("\n")[0] + ")" })); return; }
  try {
    for (const theme of THEMES) for (const [lg, ht] of LARGEURS) {
      const nom = `${lg} px ${theme === "light" ? "clair" : "sombre"}`;
      const ctx = await nav.newContext({ viewport: { width: lg, height: ht }, colorScheme: theme }), p = await ctx.newPage();
      const requetes = [];
      p.on("request", r => { if (r.url().includes("/api/vue/reglages")) requetes.push(r.method()); });
      await p.goto(lien);
      await p.waitForFunction(() => typeof VUES !== "undefined" && VUES.length && typeof affiche !== "undefined" && affiche, null, { timeout: 20000 });
      const vu = await p.evaluate(() => ongletsBerger().some(o => o.tete.type === "reglages"));
      ok(`${nom} : l'onglet Réglages est dans la navigation`, vu);
      // l'onglet, par la navigation (sous « Plus » au téléphone)
      const e = p.locator('#onglets .entree[data-vue="reglages"]');
      if (await e.isVisible()) await e.click();
      else { await p.locator("#onglets .entree[data-plus]").click(); await p.waitForSelector("#voile:not([hidden])"); await p.locator('#f-corps .entree[data-vue="reglages"]').click(); }
      await p.waitForFunction(() => affiche && affiche.type === "reglages" && document.querySelector("#vue .reglages"), null, { timeout: 20000 });
      await p.waitForTimeout(150);
      const m = await p.evaluate(() => {
        const v = document.getElementById("vue");
        return { texte: v.innerText, html: document.documentElement.outerHTML, titre: document.getElementById("titre-vue").textContent,
                 champs: v.querySelectorAll("input, textarea, select, form, button, [contenteditable]").length,
                 masques: v.querySelectorAll(".valeur.masque").length, sections: v.querySelectorAll("section.bloc").length,
                 large: document.documentElement.scrollWidth, vue: window.innerWidth,
                 debordent: [...v.querySelectorAll("*")].filter(x => x.getBoundingClientRect().right > window.innerWidth + 1).length };
      });
      ok(`${nom} : titre « Réglages » et en-tête « Ces réglages se changent dans ~/berger/config.toml »`, m.titre === "Réglages" && m.texte.includes("Ces réglages se changent dans ~/berger/config.toml") || JSON.stringify({ titre: m.titre }));
      ok(`${nom} : valeurs sensibles affichées « [masqué] » (${m.masques})`, m.masques > 0 && m.texte.includes("[masqué]"));
      ok(`${nom} : les signalements (micro grisé, décisions en lecture seule)`, m.texte.includes("micro grisé dans Conversation") && m.texte.includes("décisions en lecture seule dans la page"));
      const fuites = caches.filter(x => m.html.includes(x));
      ok(`${nom} : aucun des ${caches.length} marqueurs dans la page (DOM complet)`, caches.length > 0 && !fuites.length || `${fuites.length} marqueur(s) visibles`);
      ok(`${nom} : ni « null » ni « undefined » dans la vue`, !/\b(null|undefined)\b/.test(m.texte) || (m.texte.match(/.{0,30}\b(null|undefined)\b.{0,10}/) || [])[0]);
      ok(`${nom} : lecture seule — aucun champ ni bouton dans la vue`, m.champs === 0 || `${m.champs} champ(s) ou bouton(s)`);
      ok(`${nom} : aucun défilement horizontal (page ${m.large} px pour ${m.vue} ; ${m.debordent} élément(s) au-delà)`, m.large <= m.vue && m.debordent === 0);
      ok(`${nom} : la page ne fait que des GET sur les réglages (${requetes.join(",") || "aucune"})`, requetes.length > 0 && requetes.every(x => x === "GET"));
      await ctx.close();
    }
  } catch (e) { res["#exécution"] = String(e.message || e).split("\n")[0]; }
  finally { await nav.close(); }
  console.log(JSON.stringify(res));
})();
