/**
 * Production readiness check for a Polar checkout integration.
 *
 * Copy into the project as scripts/preflight.mjs and adapt the three constants below.
 * The Firebase section assumes Firebase Auth; swap it for whatever the project uses, but
 * keep the shape: check the live dashboards, not the code.
 *
 *   POLAR_ACCESS_TOKEN=... node scripts/preflight.mjs [--env production|sandbox]
 *
 * Every failure below has already happened at least once during setup, and none are
 * visible from reading the code: an empty embed-host list makes the checkout modal refuse
 * to open, an unauthorised domain kills the sign-in popup, a price that drifts from
 * plans.ts shows one number and charges another. Run before merging to main, and after
 * changing anything in either dashboard.
 *
 * Exits non-zero if any check fails, so it can gate a deploy.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// ---- adapt these three to the project ----
const SITE_HOST = 'example.com';
const WEBHOOK_URL = `https://${SITE_HOST}/api/polar/webhook`;
const NATIVE_BUNDLE_PREFIX = 'com.example'; // used to spot a bundle ID sitting in the Apple web client field
const REQUIRED_EVENTS = [
  'subscription.created',
  'subscription.active',
  'subscription.updated',
  'subscription.canceled',
  'subscription.uncanceled',
  'subscription.past_due',
  'subscription.revoked',
  // Required if any plan is a one-time term product (see Landmine 9).
  'order.paid',
  // Without this a refunded one-time term keeps its full access period: the
  // money goes back and the product stays open (see Landmine 19).
  'order.refunded',
];

// plan slug -> the env var holding that plan's product id.
const PRODUCT_ENV_BY_PLAN = {
  monthly: 'POLAR_PRODUCT_ID_MONTHLY',
  yearly: 'POLAR_PRODUCT_ID_YEARLY',
};

const target = process.argv.includes('--env')
  ? process.argv[process.argv.indexOf('--env') + 1]
  : 'production';
const polarApi = target === 'sandbox' ? 'https://sandbox-api.polar.sh' : 'https://api.polar.sh';

const results = [];
const record = (name, ok, detail) => results.push({ name, ok, detail });

function readEnvFile() {
  const file = path.join(ROOT, '.env');
  if (!fs.existsSync(file)) return {};
  return Object.fromEntries(
    fs.readFileSync(file, 'utf8').split('\n')
      .filter((line) => line.includes('=') && !line.trimStart().startsWith('#'))
      .map((line) => {
        const i = line.indexOf('=');
        return [line.slice(0, i).trim(), line.slice(i + 1).trim()];
      })
  );
}

/** Prices are display copy in plans.ts and the real thing in Polar. They drift silently. */
function pricesFromPlans() {
  const source = fs.readFileSync(path.join(ROOT, 'src/lib/plans.ts'), 'utf8');
  const found = {};
  for (const m of source.matchAll(/slug:\s*'(\w+)'[\s\S]*?price:\s*'\$([\d.]+)'/g)) {
    found[m[1]] = Math.round(parseFloat(m[2]) * 100);
  }
  return found;
}

async function polar(pathname, token) {
  const res = await fetch(`${polarApi}${pathname}`, {
    headers: { Authorization: `Bearer ${token}` },
    redirect: 'follow',
  });
  if (!res.ok) throw new Error(`${pathname} -> HTTP ${res.status}`);
  return res.json();
}

async function checkPolar(token) {
  const orgs = await polar('/v1/organizations/', token);
  const org = orgs.items?.[0];
  if (!org) return record('Polar organization', false, 'token sees no organization');
  record('Polar organization', true, `${org.name} (${org.status})`);

  const canCharge = org.capabilities?.checkout_payments === true;
  record('Polar can charge', canCharge, canCharge
    ? 'checkout_payments enabled'
    : `checkout_payments disabled${org.details_submitted_at ? ', awaiting review' : ', onboarding details never submitted'}`);

  const hosts = org.embed_hosts ?? [];
  record('Polar embed host', !org.embed_hosts_enforced || hosts.includes(SITE_HOST),
    hosts.length ? hosts.join(', ') : 'empty, so the checkout modal will not open');

  // embedOrigin is built from the app's own site URL. If that host is not an
  // embed host the modal never opens, and nothing in your logs says so.
  const siteUrl = env.PUBLIC_SITE_URL ?? env.NEXT_PUBLIC_SITE_URL;
  if (siteUrl) {
    let siteHost = '';
    try { const u = new URL(siteUrl); siteHost = u.port ? `${u.hostname}:${u.port}` : u.hostname; } catch {}
    record('SITE_URL is an embed host',
      Boolean(siteHost) && (!org.embed_hosts_enforced || hosts.includes(siteHost)),
      siteHost ? (hosts.includes(siteHost) ? `${siteHost} is registered`
                : `${siteHost} is NOT in embed_hosts — the checkout modal will not open`)
               : `not a valid URL: ${siteUrl}`);
  }

  const products = await polar('/v1/products/?limit=100', token);
  for (const [slug, cents] of Object.entries(pricesFromPlans())) {
    const product = products.items?.find((p) => p.metadata?.plan === slug && !p.is_archived);
    if (!product) { record(`Polar product (${slug})`, false, 'no live product tagged with this plan'); continue; }
    const actual = product.prices?.[0]?.price_amount;
    record(`Polar price (${slug})`, actual === cents, actual === cents
      ? `$${(cents / 100).toFixed(2)} matches plans.ts, id ${product.id}`
      : `Polar charges $${(actual / 100).toFixed(2)} but plans.ts shows $${(cents / 100).toFixed(2)}`);

    // The check that proves the DEPLOYMENT points at this environment's
    // products, rather than sandbox ids left over from local testing.
    const envName = PRODUCT_ENV_BY_PLAN[slug];
    if (envName) {
      const configured = env[envName];
      record(envName, configured === product.id,
        configured ? (configured === product.id ? product.id
          : `set to ${configured}, but the live ${slug} product is ${product.id}`)
        : 'not set');
    }
  }

  const hooks = await polar('/v1/webhooks/endpoints/?limit=100', token);

  // Match the path exactly. `startsWith` also matches decoys like
  // `/api/polar/webhook-sandbox-unused`, and this check then reports on an
  // endpoint that never receives anything (see Landmine 21). Query strings stay
  // out of the comparison because preview endpoints carry a bypass token.
  const samePath = (raw) => {
    try {
      const parsed = new URL(raw);
      return `${parsed.origin}${parsed.pathname}` === WEBHOOK_URL;
    } catch {
      return false;
    }
  };

  const candidates = (hooks.items ?? []).filter((h) => samePath(h.url));
  const hook = candidates.find((h) => h.enabled !== false);
  if (!hook) {
    return record('Polar webhook', false, candidates.length
      ? `endpoint for ${WEBHOOK_URL} exists but is disabled — nothing will be delivered`
      : `no endpoint pointing at ${WEBHOOK_URL}`);
  }
  const missing = REQUIRED_EVENTS.filter((e) => !hook.events.includes(e));
  record('Polar webhook', missing.length === 0,
    missing.length ? `missing events: ${missing.join(', ')}` : 'enabled, all required events');
}

async function checkFirebase(serviceAccountBase64) {
  const { initializeApp, cert } = await import('firebase-admin/app');
  const sa = JSON.parse(Buffer.from(serviceAccountBase64, 'base64').toString('utf8'));
  const credential = cert({ projectId: sa.project_id, clientEmail: sa.client_email, privateKey: sa.private_key });
  initializeApp({ credential }, `preflight-${Date.now()}`);
  const { access_token: token } = await credential.getAccessToken();
  const base = `https://identitytoolkit.googleapis.com/admin/v2/projects/${sa.project_id}`;
  const get = async (p) => (await fetch(`${base}${p}`, { headers: { Authorization: `Bearer ${token}` } })).json();

  const domains = (await get('/config')).authorizedDomains ?? [];
  record('Firebase authorized domain', domains.includes(SITE_HOST), domains.join(', '));

  for (const idp of (await get('/defaultSupportedIdpConfigs')).defaultSupportedIdpConfigs ?? []) {
    const id = idp.name.split('/').pop();
    if (id === 'apple.com') {
      // A bundle id works for the native flow and fails every web popup.
      const isServicesId = Boolean(idp.clientId) && !idp.clientId.startsWith(NATIVE_BUNDLE_PREFIX);
      record('Apple web sign-in', idp.enabled === true && isServicesId,
        isServicesId ? `Services ID ${idp.clientId}` : `clientId is ${idp.clientId}, a bundle ID`);
    }
    if (id === 'google.com') record('Google sign-in', idp.enabled === true, idp.enabled ? 'enabled' : 'disabled');
  }
}

const env = readEnvFile();
const token = process.env.POLAR_ACCESS_TOKEN || env.POLAR_ACCESS_TOKEN;
const serviceAccount = process.env.FIREBASE_SERVICE_ACCOUNT_BASE64 || env.FIREBASE_SERVICE_ACCOUNT_BASE64;

console.log(`\nPreflight, ${target}\n`);

if (!token) record('Polar access token', false, 'POLAR_ACCESS_TOKEN not set, all Polar checks skipped');
else await checkPolar(token).catch((e) => record('Polar checks', false, e.message));

if (!serviceAccount) record('Firebase credentials', false, 'FIREBASE_SERVICE_ACCOUNT_BASE64 not set');
else await checkFirebase(serviceAccount).catch((e) => record('Firebase checks', false, e.message));

const width = Math.max(...results.map((r) => r.name.length));
for (const { name, ok, detail } of results) {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name.padEnd(width)}  ${detail}`);
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} passed${failed ? `, ${failed} to fix` : ''}\n`);
process.exit(failed ? 1 : 0);
