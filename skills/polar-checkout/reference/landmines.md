# Landmines

Failures from real builds. Many are invisible on a dev server and appear only in the deployed
function; several are invisible *everywhere* until a customer pays. Check each before shipping.

---

## 1. Empty embed hosts silently kill the checkout modal

**Symptom:** the embedded checkout never opens. No error worth reading.

**Cause:** a new Polar organization starts with `embed_hosts: []` and
`embed_hosts_enforced: true`. Embedded checkout only renders on a host in that list.

**Fix:** There **is** an API for this, contrary to earlier versions of this skill — you do not
need to wait on the human:

```bash
curl -sL -X PATCH "https://api.polar.sh/v1/organizations/$ORG_ID" \
  -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
  -d '{"embed_hosts":["example.com","www.example.com","localhost:3000"]}'
```

**This PATCH replaces the whole array, it does not append.** Read the current value first and
send existing entries back with yours. That matters most in sandbox, where teams reuse one
organization across projects — sending only your own hosts silently breaks every other
project's checkout, and nothing tells you or them:

```bash
CURRENT=$(curl -sL https://api.polar.sh/v1/organizations/ -H "Authorization: Bearer $T" \
  | python3 -c 'import sys,json;print(json.dumps(json.load(sys.stdin)["items"][0]["embed_hosts"]))')
```

The dashboard route is Settings → Preferences → Embedding. Add every host, per environment:
production domain, preview domains (`*.vercel.app` wildcards work), and the local dev host with
its port. Check it with:

```bash
curl -sL https://api.polar.sh/v1/organizations/ -H "Authorization: Bearer $T" | grep embed_hosts
```

Two traps: an entry without a port matches the default port only, and a dev server that falls
back from its usual port (`4321` taken → `4322`) is no longer an allowed host, with no message
saying so.

---

## 2. `firebase-admin` v14 cannot load in a bundled ESM function

**Symptom:** every route touching the admin SDK returns 500. Works perfectly in dev.

**Cause:** `firebase-admin@14` → `jwks-rsa@4` → `jose@6`, and `jose@6` is ESM-only while
`jwks-rsa` `require()`s it. The bundled function throws
`require() of ES Module ... not supported`.

**Fix:** pin `firebase-admin@^13`, which uses `jwks-rsa@3` → `jose@4` (CommonJS). Before ever
upgrading, deploy and hit an authenticated route: **401 means it works, 500 means it doesn't.**

Generalise: any admin SDK is a CJS/ESM interop risk in a serverless bundle. Never trust a dev
server as evidence.

---

## 3. Deep subpath imports get dropped from the deployment bundle

**Symptom:** `Cannot find module '/var/task/node_modules/@polar-sh/sdk/dist/esm/webhooks.js'`
in production. Resolves fine locally.

**Cause:** `@polar-sh/sdk/webhooks.js` is reached through a wildcard `exports` map, and file
tracers (Vercel's included) do not follow it into the bundle.

**Fix:** verify signatures with `standardwebhooks` directly, which is what the SDK does
internally. Self-contained, smaller, and nothing to trace:

```js
import { Webhook } from 'standardwebhooks';
const parsed = new Webhook(Buffer.from(secret, 'utf-8').toString('base64')).verify(body, headers);
```

**Consequence:** you lose the SDK's zod parsing, which camelCases the payload. Polar's raw
webhook JSON is **snake_case** (`current_period_end`, `cancel_at_period_end`, `product_id`,
`customer.external_id`). Write an explicit mapper, validate it at the boundary, and unit test
it. Throw on missing fields rather than guessing; a payload you cannot read is one you must
not act on.

---

## 4. `instanceof` does not survive CJS/ESM bundling

**Symptom:** a bad signature returns 500 instead of 403, only in production.

**Cause:** matching the library's error class with `instanceof` fails when the CommonJS export
is re-bundled; the class identity differs.

**Fix:** never branch on `instanceof` for third-party errors across a bundle boundary. For a
signature check, treat **every** failure as "not verified" and fail closed. That is correct
semantics anyway.

---

## 5. Native and web auth providers are different clients

**Symptom:** the sign-in popup opens and closes instantly, or Apple shows
`invalid_request — Invalid client id or web redirect url`.

**Causes, in order of likelihood:**

- **Unauthorised domain.** The host is not in the auth provider's allow list. Firebase:
  Authentication → Settings → Authorized domains. Every preview domain needs adding too.
- **Apple: the client ID is a bundle ID.** Native Sign in with Apple uses the app's Bundle ID
  and needs no secret. **Web needs a Services ID**, a return URL registered with Apple
  (`https://<project>.firebaseapp.com/__/auth/handler`), and a signing key. A bundle ID is not
  a valid web client_id and Apple rejects it outright. This cannot be fixed in code and needs
  the Apple Developer portal.
- **A platform's config is not portable.** An iOS `GoogleService-Info.plist` carries an iOS app
  ID and an iOS API key. They may work in a browser if unrestricted, but that is itself a
  finding: register a web app and keep one key per platform so each can be locked down.

**Also:** surface the real error code in the UI. `auth/unauthorized-domain` presented as
"something went wrong" is undebuggable from the outside; the popup blinking shut with no
message wastes an hour.

---

## 6. Required env vars couple unrelated routes

**Symptom:** an unset webhook secret takes down checkout and the portal, which never read it,
with a generic `EnvInvalidVariables`.

**Cause:** schema-validated env (`astro:env` and equivalents) validates the **whole** server
schema on first access, not per-variable.

**Fix:** mark anything a given route does not need as optional, and check it explicitly inside
the route that does, failing closed with a legible status. Each route should require only what
it uses. This also lets checkout be developed before a webhook tunnel exists.

---

## 7. The payer's id is NOT where you expect it

**Symptom:** none, until it is every purchase. Entitlements never get written, the webhook logs
`no_user_id`, and money has changed hands with nobody to give access to.

**Cause:** you set `externalCustomerId` on the checkout session, so you reasonably expect
`external_customer_id` on the subscription payload. **It is not there.** A real
`subscription.*` payload carries it only at `customer.external_id`.

**Worse: there is a decoy.** The payload has a top-level `user_id`, and it is **Polar's
customer id, not yours** — a well-formed UUID sitting under exactly the name you are looking
for. Verified against a real sandbox purchase, 2026-08:

```jsonc
{
  "id": "24c053ef-…",                       // subscription id
  "customer_id": "5b94dce1-…",
  "user_id":     "5b94dce1-…",              // ← the Polar customer id. NOT your user.
  "customer":  { "external_id": "<your app user id>" },   // ← the only real source
  "metadata":  { "user_id": "<your app user id>" },       // ← your own fallback
  "product":   { "metadata": { "plan": "monthly" } }
}
```

An absent field fails loudly the first time you test. A field that is present, correctly typed,
plausibly named and *wrong* does not — it writes entitlements for a user that does not exist,
and the row simply never appears for the person who paid.

**Fix:** resolve through a chain that never touches `data.user_id`, and unit test it against a
payload captured from a *real* purchase, not one you wrote:

```js
external_customer_id            // present on checkout/order objects
  ?? customer.external_id       // the only place it appears on subscriptions
  ?? metadata.user_id           // your own fallback, set at session creation
// NEVER data.user_id — that is Polar's customer, not your user.
```

Pin the decoy with an explicit assertion, so nobody "simplifies" the chain later:

```js
expect(resolveUserId(realPayload)).not.toBe(realPayload.user_id);
```

**Why this is the most dangerous item here:** hand-written fixtures share the author's
assumption about the shape, so the suite is green at 100% coverage while the integration is
broken. The only way to learn the true shape is to buy something in sandbox and read what
arrives. Do that once, then pin it as a fixture.

---

## 8. Polar DNS-checks `customer_email` and 422s the whole request

**Symptom:** checkout returns 502 for one specific user and works for everyone else. Or, while
testing, every attempt fails and you blame your own harness.

**Cause:** Polar validates the email's domain with a live DNS lookup. `.invalid`, `.test`,
made-up `.dev` names, and genuinely lapsed domains all fail, and the failure rejects the
**entire** checkout creation — not just the prefill.

**Fix:** the prefill is a convenience; the sale is not. Retry once without it:

```js
catch (error) {
  if (user.email && error?.data$?.detail?.some(d => Array.isArray(d.loc) && d.loc.includes("customer_email"))) {
    return retry({ ...session, customerEmail: undefined });   // keep externalCustomerId!
  }
}
```

Keep `externalCustomerId` and `metadata` on the retry or you have traded one failure for the
unattributable-purchase failure above. When writing tests, use a domain that actually resolves.

---

## 9. There is no six-month (or any custom) billing interval

**Symptom:** `recurring_interval` rejected with
`Input should be 'day', 'week', 'month' or 'year'`.

**Cause:** those four are the whole list. "6 months at a discount" is not expressible as a
subscription.

**Fix:** model a term plan as a **one-time product** and compute the expiry yourself:

- one-time order → `expires_at = paid_at + N months`, `status = 'active'`
- set `cancel_at_period_end = true` so the UI honestly says it will not renew
- handle `order.paid`, and **skip orders that carry a `subscription_id`** or you will
  double-write every renewal
- clamp month arithmetic: 31 Aug + 6 months is 28/29 Feb, not 3 March

Recurring plans must store **`expires_at = NULL`**. Dating them from `current_period_end`
revokes access in the gap between a period ending and the renewal webhook landing.

---

## 10. Organization tokens reject `organization_id`

**Symptom:** `Setting organization_id is disallowed when using an organization token.`

**Fix:** omit it. The token already scopes the request. (User tokens are the opposite.) Also,
org tokens cannot read `/v1/accounts/` at all, so you cannot inspect payout-account state on
the seller's behalf.

---

## 11. Multi-currency products need the org's default currency

**Symptom:** `The organization's default presentment currency must be present in the prices.`

**Cause:** you priced in PHP but the org's `default_presentment_currency` is USD — common when
reusing an existing sandbox org from another project.

**Fix:** either include a price in the org's default currency alongside yours, or use a sandbox
org whose default matches production. Note the consequence: sandbox checkout will then *display*
the default-currency price, which is fine — preflight is what verifies the production number.

---

## 12. Onboarding: `details_submitted_at` is the real signal

**Symptom:** the seller says onboarding is done; `checkout_payments` is still `false`.

**Cause:** connecting a payout account and submitting the organization's details are two
different steps. `payout_account_id` can be set while `details_submitted_at` is still `null`.

**Fix:** poll the org and read all three. `status: "created"` + `details_submitted_at: null`
means the form was never actually submitted — not that Polar is reviewing it. Report those
fields back rather than "it isn't done yet"; it tells the human which step to reopen.

```bash
curl -sL https://api.polar.sh/v1/organizations/ -H "Authorization: Bearer $T" \
  | python3 -c 'import sys,json;o=json.load(sys.stdin)["items"][0];print(o["status"],o["details_submitted_at"],o["capabilities"]["checkout_payments"])'
```

---

## 13. Shipping checkout is not shipping billing

**Symptom:** everything works, preflight is green, and a customer emails asking
how to cancel. Or: "there's no billing page on mobile."

**Cause:** the pricing page and the checkout route are the visible work, so they get
built. The **route into billing from inside the product** is not, and nobody notices
because the person building it always navigates by URL.

Three separate holes, all real:

- **No persistent nav entry.** The only links to `/upgrade` were inside a
  daily-limit banner that appears once you hit the cap. Fine for conversion,
  useless for a subscriber.
- **A dead feature flag.** The sidebar CTA existed but the shell hardcoded
  `const showUpgradeCta = false` — switched off while gating was stubbed, never
  switched back on. Grep for the flag; do not trust that the component renders.
- **Mobile has a different nav.** A desktop sidebar entry does not put anything
  in a bottom tab bar or its "More" sheet. Check every layout.

**Fix:** before calling it done, answer these as a signed-in **subscriber**, not
as the developer:

1. From the dashboard, how do I see what I am paying?
2. How do I get a receipt?
3. How do I cancel — **on my phone**?

If any answer is "type /upgrade into the address bar", billing is not shipped.
Put it on the account/profile page (where people look first, and which is one
page on every layout) and in every nav the app has.

**Why this one bites hardest:** your own terms almost certainly say the customer
may cancel "at any time from your account". If there is no route to the portal,
that sentence is false, and it is false specifically for the people who paid.

---

## 14. Public pricing sends signed-out visitors into an authenticated flow

**Symptom:** the upgrade button on `/upgrade` returns 401 and shows a generic
"could not start checkout" error — but only for visitors who arrived from
marketing.

**Cause:** checkout needs a session to attach `externalCustomerId` to. Before the
pricing page existed, only signed-in users ever reached `/upgrade`, so the case
never came up.

**Fix:** render a sign-in prompt instead of a buy button when there is no
session, and check that every "back" link on that page goes somewhere a
signed-out visitor can actually load.

---

## 15. Announcing the change to existing users needs an audience rule

**Symptom:** a new signup is told "you have 14 more days of full access before
anything changes" — about a product they joined yesterday.

**Cause:** most announcement systems show every active announcement to everyone.
An announcement describes a **change**; someone who arrived afterwards did not
experience one.

**Fix:** filter to announcements published before the user joined. Two further
notes from doing it:

- Prefer one announcement row with per-user read tracking over inserting a
  notification row per user. Same result at login, no write amplification, and
  nothing is "sent".
- Check how the bell renders a body before writing one — a `line-clamp-2` means
  your careful three-paragraph explanation is invisible. Put the reasoning on a
  page and link to it.

---

## 16. A pre-existing tier column becomes a second source of truth

**Symptom:** a real paying customer shows as "free" everywhere in the admin
dashboard. Separately, the admin "make this user Pro" button appears to work —
toast, row updates — and grants the user nothing at all.

**Cause:** the app already had somewhere to record who was paid before Polar
existed: `user_profiles.subscription_tier`, `is_pro`, `plan`, a `role` value.
The webhook writes the new entitlement table; every internal surface still reads
the old column; nothing syncs them. Both halves are silently wrong, in opposite
directions — the gates under-report on admin screens, and admin grants never
reach the gates.

This one hides well. The webhook path can be at 100% coverage and every test
green, because the bug is in the surfaces *outside* the money path that nobody
thought to point at the new table.

**Fix:** before writing the webhook, find the old column and decide its fate:

```bash
grep -rniE "subscription_tier|is_pro|\bplan\b|premium|tier" src/ --include='*.ts*' \
  | grep -viE "\.test\.|/polar/"
```

Make the entitlement table the only answer, and delete the reads — do not sync
the two, or you have bought a drift bug. Then handle the two jobs the old column
was really doing:

- **Comping someone Pro** (a tester, an influencer, a refund make-good). Write a
  real entitlement row with a `comp` plan slug rather than inventing a second
  mechanism. Every gate, dashboard and profile page already understands
  entitlements, so a comp needs no special case anywhere except where it is
  written. Extend the plan check constraint to accept it.
- **Reporting.** "Pro users" is now two populations. Keep them apart: conversion
  rate should count paid only, or comping a hundred testers reads as product
  success.

Two rules for the comp writer, both learned the hard way:

- **Refuse to overwrite a paid row.** A Polar entitlement carries the customer,
  subscription and order ids the billing portal needs. Replacing it with a comp
  strands a paying customer with no way to cancel. Refuse and say why.
- **Revoke only ever deletes a comp.** A paid entitlement is Polar's to end.
  Deleting it here hands back access the customer is still paying for, and the
  next webhook recreates it anyway.

Stamp the comp's `modified_at` with *now*, so a later real purchase wins the
freshness check and upgrades them from comp to paid.

And never show a comp the billing portal — there is no Polar customer behind
them, so it can only error. Gate the button on the customer id, not on `isPro`.

**Migrating the old column:** back-fill existing `tier = 'pro'` rows into comps
in the same migration, or those people silently drop to free on deploy. Count
them first — if it is zero, say so; if it is not, they are real users. Leave the
old column in place with a `DEPRECATED` comment rather than dropping it in the
same change, so an in-flight deploy cannot break on a missing column.

---

## 17. The plan the visitor chose does not survive sign-in

**Symptom:** nobody complains, and conversion is just quietly worse than it
should be. Walk it yourself signed out: pricing page → "Get 6 months" → sign-in
wall → sign in → you are on the dashboard, and the app has forgotten you came to
buy anything.

**Cause:** two independent gaps that compound.

1. The pricing CTA links to `/upgrade` with no plan, so a visitor who has
   already chosen re-chooses.
2. The sign-in link uses a query param the login page does not read. Ours sent
   `?next=/upgrade`; login read `?redirect=`. No error, no warning — the
   parameter is simply ignored and the default destination wins.

The param mismatch is invisible to types, tests and the compiler. It is a string
on one side and a string on the other.

**Fix:** carry the intent the whole way and verify it end to end.

```bash
# every place that links into an auth page, and what login actually reads
grep -rnoE 'href=[^>]*/(login|signup)\?[a-z]+=' src/
grep -rn 'searchParams.get' src/**/login*
```

Then: pricing CTA → `/upgrade?plan=six_month`; the signed-out wall →
`/login?redirect=` *and* `/signup?redirect=` with that path encoded; signup
honours the param instead of hardcoding a dashboard push; and on arrival, a
carried plan opens its checkout rather than asking for a third click.

Guard the auto-open with a ref, or React's double-invoked development effects
open two checkout sessions.

Assert it with curl rather than by eye — this is exactly the kind of thing that
looks right in the diff:

```bash
curl -s localhost:3000/pricing | grep -oE 'href="/upgrade\?plan=[a-z_]+"'
curl -s 'localhost:3000/upgrade?plan=six_month' | grep -oE 'href="/(login|signup)[^"]*"'
```

Whatever validates the redirect must pass a query string through untouched —
and still refuse `//evil.example`, backslashes and absolute URLs. Test both
halves; it is a security boundary and a funnel step at once.

---

## 18. The success page races the webhook

**Symptom:** the customer pays, lands on your success page, and it says
"You're on Pro" over a product still showing free-tier limits. Or, worse, the
page hedges: *"if the old limits are still showing, refresh the page."*

**Cause:** Polar redirects the customer back the instant payment succeeds. The
entitlement is written by the webhook, which is a separate request on a
different connection. For a second or two the payment is real and the
entitlement is not.

**Fix:** the success page waits for the entitlement instead of asserting it.
Read the entitlement server-side, render a "payment received, switching your
account over" state while it is absent, and have a small client component call
`router.refresh()` on an interval until the server renders the confirmed state.

Cap the attempts. If it never lands, say plainly that the payment went through,
that nothing is lost, and give a support address — do not leave a spinner
turning on a page where money has already changed hands.

Telling the customer to refresh is asking them to debug your race condition.

---

## 19. Refunds are not handled unless you subscribe to them

**Symptom:** you refund a customer and they keep the product. Nobody reports it,
because the only person who would notice is the one who benefits.

**Cause:** `order.refunded` is not in the default set anyone copies into their
webhook subscription. For a **one-time** product this is the whole gap — Polar
sends no `subscription.*` event for a one-off order, so refunding it delivers
nothing at all and the entitlement sits there until its computed expiry. A
six-month term refunded on day two is six months of free product.

**Fix:** subscribe to `order.refunded` and map it to a revoking status. Add it
to whatever list your preflight asserts, or it will fall back out the first time
someone recreates the endpoint.

```ts
const REFUND_EVENTS = new Set(["order.refunded"]);
```

Three judgement calls worth making the same way:

- **Partial refunds must not revoke.** Polar fires the same event for a partial
  refund. Check `refunded === true`, falling back to `refunded_amount >=
  total_amount`, and treat anything less as a deliberate no-op. Taking six
  months of access away over a partial credit is the worse error.
- **Subscription refunds are not yours to act on.** If the order belongs to a
  subscription, skip it — Polar drives that lifecycle and will send
  `subscription.revoked` if the refund ends it. Same `isSubscriptionOrder`
  guard you already use on `order.paid`.
- **Date the expiry to the refund, not the term.** `expiresAt` = the refund's
  timestamp, so access ends now rather than at the end of a term nobody paid
  for.

The revoking status still goes through the ordering guard, so a redelivered
older `order.paid` cannot resurrect a refunded entitlement.

---

## 20. The payment routes are the ones nobody rate limits

**Symptom:** none, until it costs you. Check it directly — if every other POST
in the app is limited and the three billing routes are not, that is not a
deliberate exemption, it is an oversight.

**Cause:** rate limiting gets added to the endpoints that obviously accept user
content (uploads, comments, signup). The billing routes are authenticated, so
they read as already-protected.

**Fix:** all three, each for a different reason.

- **Checkout** — keyed by user id. Every call creates a real checkout session in
  the merchant's Polar dashboard and spends their API quota. One signed-in
  account in a loop fills their account with abandoned sessions.
- **Portal** — keyed by user id. Same class, smaller blast radius.
- **Webhook** — keyed by IP, and **only on deliveries that already failed
  verification**. This endpoint is public by necessity, and a flood of unsigned
  bodies otherwise buys an attacker unbounded HMAC work on your function budget.

That last distinction is the one that matters. Rate limiting the webhook
*before* verification throttles Polar itself: real deliveries arrive in bursts
when a backlog drains, and dropping them costs you entitlements. Verify first,
and only meter what failed.

```ts
if (!verified.ok) {
  if (verified.reason === "not_configured") return json(503);   // ours, not an attack
  const limited = await rateLimit(`polar-webhook-bad:${ip}`, LIMITS.webhookRejected);
  if (!limited.success) return json(429);
  return json(403);
}
```

Do not meter the misconfiguration branch either — a missing secret is your
deploy being wrong, and throttling it just hides it.

---

## 21. Preflight matching a webhook URL with `startsWith`

**Symptom:** preflight reports on a webhook endpoint that receives nothing, and
passes (or fails) for reasons that have no bearing on production.

**Cause:** `items.find(h => h.url.startsWith(WEBHOOK_URL))`. A decoy endpoint at
`/api/polar/webhook-sandbox-unused` matches the prefix `/api/polar/webhook`
perfectly. Ours was also `enabled: false`, which the check never looked at.

**Fix:** compare `origin + pathname` exactly, and require `enabled !== false`.
Keep query strings out of the comparison — preview endpoints carry a bypass
token. Report "exists but is disabled" separately from "not found"; they are
different problems with different fixes.

A check that reports on the wrong object is worse than no check, because it
reads as coverage.

---

## 22. `PolarEmbedCheckout.create()` takes the checkout URL, not the client secret

**Symptom:** the upgrade button does nothing. No modal, no console error, nothing in Sentry,
a 200 from your own API. Indistinguishable from the CSP failure and from a dead click handler.

**Cause:** creating a checkout session returns **both** `clientSecret` and `url`, and
`clientSecret` is the one that reads like the thing an embed widget would want. It is not —
from `@polar-sh/checkout`'s own type definitions:

```ts
static create(url: string, options?: { theme?: 'light' | 'dark' })
```

Passing the client secret is a type-correct string, so TypeScript is happy and the call
resolves. The iframe just never mounts.

**Fix:**

```ts
const { url } = await res.json();
await PolarEmbedCheckout.create(url, { theme: 'light' });   // URL, not clientSecret
```

**How to catch it:** you cannot, by reading code or by unit test. Drive a real browser, click
the button, and assert that an iframe whose `src` contains `polar.sh` actually appears. That
single assertion covers this, the CSP `frame-src` landmine, and a dead handler — three
different silent failures with one identical symptom:

```js
const src = await page.evaluate(() =>
  [...document.querySelectorAll('iframe')].find(f => (f.src || '').includes('polar.sh'))?.src);
expect(src).toBeTruthy();
```

---

## 23. Signing your own webhooks does not prove Polar can reach you

**Symptom:** none. Every test is green, you report the integration verified, and no purchase
ever grants anything.

**Cause:** the self-signed webhook test in Phase 5 proves your *endpoint* — signature check,
mapper, database write. It says nothing about whether **Polar can deliver to that URL**, because
you were the one making the request. If your endpoint only ever existed on `localhost`, the
delivery path has never run once.

The tell is in Polar's dashboard, not your logs. Read what it actually recorded:

```bash
curl -sL "https://api.polar.sh/v1/webhooks/deliveries?limit=10" -H "Authorization: Bearer $T" \
  | python3 -c 'import sys,json;[print(d["created_at"][:19], d["succeeded"]) for d in json.load(sys.stdin)["items"]]'
```

`succeeded: False` on every row — while your own suite is green — is exactly this failure. In a
shared sandbox organization it is quieter still: the registered endpoints belong to *other*
projects, so your test purchase fires events at somebody else's URL and nothing surfaces.

**Fix:** deliver to a real, reachable deployment before you believe it. A preview deployment is
the right place — it runs the bundled serverless function, not a dev server, so it also
exercises the CJS/ESM landmines above.

On Vercel, three things bite in sequence:

- **Deployment protection blocks the webhook.** SSO-protected previews hand Polar a login page.
  Generate a **Protection Bypass for Automation** secret (32 alphanumeric chars, via
  `PATCH /v1/projects/{id}/protection-bypass`) and register the endpoint as
  `.../api/polar/webhook?x-vercel-protection-bypass=<secret>&x-vercel-set-bypass-cookie=false`.
- **Every deploy gets a fresh URL**, so the endpoint you just registered is stale immediately.
  `vercel alias set <deployment> <stable>.vercel.app` and point Polar at the alias.
- **`vercel deploy` uploads local files**, so all of this works without pushing a branch.

Then buy once with `4242 4242 4242 4242` against that deployment and read the row back. Assert
the delivery, not the response code:

| Assert | Why |
|---|---|
| entitlement row appears within ~60s | proves Polar to your code, the only untested link |
| `user_id` matches your test user | proves Landmine 7's chain against a live payload |
| revoking in Polar clears `is_active` | proves the revocation path, not just the grant |

That bypass secret is a standing credential that defeats preview auth for anyone holding it,
and it sits in plain sight inside the endpoint URL in Polar's dashboard. Delete the endpoint
and rotate the secret when the testing is done.

---

## 24. Automating the one real purchase

The skill tells you to buy something once. Doing that headlessly has three snags, each of which
costs time to rediscover:

- **`waitUntil: 'networkidle'` never settles** on Polar's checkout, because Stripe holds
  connections open. Use `domcontentloaded`, wait for `input[name=customer_email]`, then pause a
  few seconds for the Stripe iframes to mount.
- **The fields are split across documents.** `customer_email` and `customer_name` are Polar's
  own inputs in the top-level document; `number`, `expiry` and `cvc` live inside Stripe iframes,
  so you have to walk `page.frames()`. Missing the **cardholder name** fails validation quietly
  and the form simply does not submit.
- **Country is a React-controlled `<select>`** behind a custom button. Assigning `.value` does
  nothing; go through the native setter and dispatch `change`:

```js
const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
setter.call(sel, 'PH');
sel.dispatchEvent(new Event('change', { bubbles: true }));
```

---

## Bonus: two UI failures worth checking

- **`display: flex` beats the `hidden` attribute.** A container styled `display: flex` ignores
  `hidden`'s UA `display: none`, so "Sign out" showed to signed-out visitors. Add
  `[hidden] { display: none !important; }`.
- **Scoped styles do not reach elements created in JavaScript.** Astro (and similar) scope CSS
  with a generated attribute that `document.createElement` never gets, so those elements render
  unstyled. Server-render the markup and toggle it with `hidden` instead of building it in JS.
