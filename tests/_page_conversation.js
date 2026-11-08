// Interface web v2, lot 3 : la page « Conversation » MESURÉE dans un vrai navigateur (Playwright, s'il est présent : PAS une dépendance du
// projet) — lancé par tests/interface-conversation.py avec le lien d'entrée d'une installation jetable (actions actives, vigie vivant dans
// un faux Herdr). Aux largeurs du lot « finition UI » (1920, 1440, 820, 390) et dans les 2 thèmes : la zone de saisie visible et sans
// débordement, le propriétaire à droite et l'agent à gauche, « N actions » qui se déplie (outil et cible, jamais une sortie), Maj+Entrée va
// à la ligne, Entrée envoie (le message part par /api/message et la zone se vide), le collage d'une image devient une pièce jointe, un
// long collage devient une pièce texte, le micro grisé avec sa raison, la saisie gardée au rafraîchissement, ni « null » ni « undefined ».
// Sortie : une ligne JSON {contrôle: "ok" | ce qui ne va pas}, ou {"#lancement": "NON JOUÉ …"} sans navigateur.
"use strict";
const [, , lien, agent] = process.argv;
let pw;
try { pw = require(process.env.BERGER_PLAYWRIGHT || "playwright"); } catch (e) { console.log(JSON.stringify({ "#lancement": "NON JOUÉ navigateur réel : module Playwright introuvable" })); process.exit(0); }
const LARGEURS = [[1920, 1080], [1440, 900], [820, 1100], [390, 844]], THEMES = ["light", "dark"];
const vueAffichee = p => p.waitForFunction(() => typeof affiche !== "undefined" && affiche && affiche === courant && document.querySelector("#vue").children.length > 0, null, { timeout: 20000 });

(async () => {
  const sortie = {}, ok = (k, v) => { sortie[k] = v === true ? "ok" : v === false ? "non" : v; };
  let b;
  try { b = await pw.chromium.launch(process.env.BERGER_CHROMIUM ? { executablePath: process.env.BERGER_CHROMIUM } : {}); }
  catch (e) { console.log(JSON.stringify({ "#lancement": "NON JOUÉ navigateur réel : chromium ne démarre pas ici (" + String(e.message).split("\n")[0].slice(0, 120) + ")" })); return; }
  try {
    for (const [lg, ht] of LARGEURS) for (const theme of THEMES) {
      const ctx = await b.newContext({ viewport: { width: lg, height: ht }, colorScheme: theme }), p = await ctx.newPage(), erreurs = [], envois = [];
      p.on("pageerror", e => erreurs.push(e.message));
      p.on("request", r => { if (r.url().endsWith("/api/message") && r.method() === "POST") envois.push(JSON.parse(r.postData() || "{}")); });
      const nomC = `${lg} px ${theme === "light" ? "clair" : "sombre"}`;
      await p.goto(lien); await vueAffichee(p);
      await p.evaluate(a => aller({ mode: "agent", type: "conversation", a }), agent); await vueAffichee(p);
      await p.waitForSelector("#vue .fil .bulle", { timeout: 20000 });
      // le sous-onglet n'existe que pour les agents déclarés
      const onglets = await p.evaluate(() => [...document.querySelectorAll("#agents button")].map(x => x.getAttribute("data-vue-agent")));
      if (lg === 1440 && theme === "light") {
        const autre = await p.evaluate(() => { aller({ mode: "agent", type: (VUES.find(v => v.onglet === "agent") || {}).type, a: "demo-ecran" }); return [...document.querySelectorAll("#agents button")].map(x => x.getAttribute("data-vue-agent")); });
        ok("le sous-onglet « Conversation » n'existe que pour un agent déclaré", onglets.includes("conversation") && !autre.includes("conversation") || JSON.stringify([onglets, autre]));
        await p.evaluate(a => aller({ mode: "agent", type: "conversation", a }), agent); await vueAffichee(p); await p.waitForSelector("#vue .fil .bulle");
      }
      const g = await p.evaluate(() => {
        const f = document.querySelector("#vue .fil").getBoundingClientRect(), pr = document.querySelector("#vue .bulle.proprio").getBoundingClientRect(), ag = document.querySelector("#vue .bulle.agent").getBoundingClientRect();
        const s = document.querySelector("#vue .saisie"), t = document.querySelector("#c-texte"), r = s.getBoundingClientRect();
        return { droite: Math.round(f.right - pr.right), gaucheP: Math.round(pr.left - f.left), gauche: Math.round(ag.left - f.left), saisie: r.height > 0 && r.bottom <= window.innerHeight + 1 && r.top >= 0,
                 large: document.documentElement.scrollWidth, vue: window.innerWidth, champ: Math.round(t.getBoundingClientRect().width), texte: document.getElementById("vue").innerText };
      });
      ok(`${nomC} : le propriétaire à droite, l'agent à gauche`, g.droite <= 2 && g.gauche <= 2 && g.gaucheP > 8 || JSON.stringify(g));
      ok(`${nomC} : la zone de saisie est visible (collée en bas), champ de ${g.champ} px`, g.saisie && g.champ >= 160 || JSON.stringify(g));
      ok(`${nomC} : aucun défilement horizontal`, g.large <= g.vue || `${g.large} pour ${g.vue}`);
      ok(`${nomC} : ni « null » ni « undefined », aucune sortie d'outil, la clé masquée`, !/\b(null|undefined)\b/.test(g.texte) && !/SORTIE-D-OUTIL|sk-factice/.test(g.texte) && /masqué : secret possible/.test(g.texte) || g.texte.slice(0, 200));
      // « N actions » se déplie : l'outil et sa cible, jamais une sortie
      await p.locator("#vue details.actions-repliees > summary").first().click();
      const d = await p.evaluate(() => { const x = document.querySelector("#vue details.actions-repliees"); return { ouvert: x.open, resume: x.querySelector("summary").textContent, lignes: [...x.querySelectorAll("li")].map(l => l.textContent) }; });
      ok(`${nomC} : « ${d.resume.trim()} » se déplie — outil et cible courte`, d.ouvert && /3 actions/.test(d.resume) && d.lignes.length === 3 && /Bash/.test(d.lignes[0]) && /ls -la/.test(d.lignes[0]) || JSON.stringify(d));
      // Maj+Entrée : à la ligne ; la saisie survit au rafraîchissement ; Entrée : envoi
      const champ = p.locator("#c-texte"); await champ.click(); await champ.type("Première ligne"); await p.keyboard.press("Shift+Enter"); await champ.type("seconde");
      await p.evaluate(async () => { RECENTES.clear(); await afficher(true); });
      const garde = await p.evaluate(() => ({ v: document.getElementById("c-texte").value, focus: document.activeElement && document.activeElement.id, ouvert: document.querySelector("#vue details.actions-repliees").open }));
      ok(`${nomC} : Maj+Entrée va à la ligne ; un rafraîchissement garde la saisie, son focus et « N actions » déplié`, garde.v === "Première ligne\nseconde" && garde.focus === "c-texte" && garde.ouvert || JSON.stringify(garde));
      if (theme === "light") {
        // une image collée (Ctrl+V d'une capture) devient une pièce jointe ; un long collage, une pièce texte repliée
        await p.evaluate(() => {
          const png = Uint8Array.from(atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="), c => c.charCodeAt(0));
          const dt = new DataTransfer(); dt.items.add(new File([png], "capture.png", { type: "image/png" }));
          document.getElementById("c-texte").dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
          const dt2 = new DataTransfer(); dt2.setData("text/plain", Array.from({ length: 120 }, (_, k) => "ligne " + k).join("\n"));
          document.getElementById("c-texte").dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt2, bubbles: true, cancelable: true }));
        });
        await p.waitForFunction(() => document.querySelectorAll("#vue .c-piece").length === 2, null, { timeout: 5000 }).catch(() => {});
        const pcs = await p.evaluate(() => ({ n: document.querySelectorAll("#vue .c-piece").length, t: document.querySelector("#vue .c-pieces").textContent, v: document.getElementById("c-texte").value }));
        ok(`${nomC} : le collage d'une image devient une pièce jointe ; un long collage (120 lignes) une pièce texte repliée, hors du champ`, pcs.n === 2 && /Image/.test(pcs.t) && /Texte collé · 120 lignes/.test(pcs.t) && !/ligne 119/.test(pcs.v) || JSON.stringify(pcs));
      }
      await champ.focus(); await p.keyboard.press("Enter");
      await p.waitForFunction(() => document.getElementById("c-texte").value === "", null, { timeout: 30000 }).catch(() => {});
      const env = envois[envois.length - 1] || {}, apres = await p.evaluate(() => ({ v: document.getElementById("c-texte").value, etat: document.getElementById("c-etat").textContent, pieces: document.querySelectorAll("#vue .c-piece").length }));
      ok(`${nomC} : Entrée envoie (POST /api/message avec l'empreinte et le jeton à usage unique), la zone se vide`,
         env.agent && env.texte === "Première ligne\nseconde" && /^[0-9a-f]{64}$/.test(env.empreinte) && env.nonce && apres.v === "" && apres.pieces === 0 && (theme !== "light" || env.pieces.length === 2) || JSON.stringify({ env: { ...env, pieces: (env.pieces || []).length }, apres }));
      // le micro : grisé avec sa raison (aucune transcription locale déclarée), au survol et au toucher
      const m = await p.evaluate(() => { const x = document.querySelector("#vue .c-micro"); x.click(); return { aria: x.getAttribute("aria-disabled"), titre: x.getAttribute("title"), etat: document.getElementById("c-etat").textContent }; });
      ok(`${nomC} : micro grisé, sa raison au survol et au toucher (« ${m.titre} »)`, m.aria === "true" && /aucune transcription locale/.test(m.titre) && /aucune transcription locale/.test(m.etat) || JSON.stringify(m));
      ok(`${nomC} : aucune erreur de script`, erreurs.length ? erreurs.join(" ; ").slice(0, 200) : true);
      await ctx.close();
    }
  } catch (e) { sortie["#exécution"] = "ERREUR " + String(e.message).split("\n")[0]; }
  await b.close();
  console.log(JSON.stringify(sortie));
})();
