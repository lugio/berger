#!/usr/bin/env node
// Propriétaire uniquement. Aucun état sur disque, stdout réservé à l'état filtré.
import {pathToFileURL} from 'node:url';
const [modulePath, executablePath, domaine, server, spki] = process.argv.slice(2);
let browser;
let interrompu = false;
async function annuler() {
  interrompu = true;
  try { await browser?.close(); } finally { process.exitCode = 1; }
}
process.on('SIGTERM', annuler);
process.on('SIGINT', annuler);
try {
  const {chromium} = await import(pathToFileURL(modulePath).href);
  browser = await chromium.launch({headless: false, chromiumSandbox: true, executablePath,
    proxy: {server, bypass: '<-loopback>'},
    args: [`--ignore-certificate-errors-spki-list=${spki}`, '--disable-quic',
      '--force-webrtc-ip-handling-policy=disable_non_proxied_udp',
      '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1']});
  if (interrompu) throw new Error();
  const context = await browser.newContext();
  const page = await context.newPage();
  // Un seul onglet est la fin explicite de la saisie propriétaire.
  const ferme = page.waitForEvent('close', {timeout: 0});
  await page.goto(`https://${domaine}/`);
  await ferme;
  if (interrompu) throw new Error();
  const state = await context.storageState();
  const propre = {
    cookies: (state.cookies || []).filter(c => {
      const parent = c.domain.startsWith('.') ? c.domain.slice(1) : c.domain;
      return c.domain.startsWith('.') ? domaine === parent || domaine.endsWith('.' + parent) : domaine === parent;
    }),
    origins: (state.origins || []).filter(o => o.origin === `https://${domaine}`)
  };
  // Fermer avant publication : une fermeture ratée ne produit aucun état.
  await browser.close(); browser = undefined;
  if (interrompu) throw new Error();
  const sortie = JSON.stringify(propre);
  if (Buffer.byteLength(sortie) > 256 * 1024) throw new Error();
  process.stdout.write(sortie);
} catch {
  process.stderr.write('connexion interrompue\n'); process.exitCode = 1;
} finally {
  try { await browser?.close(); } catch { process.exitCode = 1; }
}
