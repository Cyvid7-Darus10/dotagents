# Next.js (App Router) + Supabase + Vercel

The base skill assumes bearer ID tokens and a generic host. This stack differs in ways that
each cost real time. Verified end to end on a live deployment, 2026-08.

---

## Auth: cookies, not bearer tokens

There is no ID token to verify. The browser IS the client and Supabase's SSR helper reads a
session cookie. Resolve the user server-side on every paid route:

```ts
// src/app/api/polar/checkout/route.ts
import { getUser } from "@/lib/supabase/auth";        // wraps supabase.auth.getUser()

export const runtime = "nodejs";                       // the SDK is not edge-safe

export async function POST(request: Request) {
  const user = await getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  // ...body carries a plan SLUG, never a product id, never a user id
}
```

The rule is unchanged, only the mechanism: **the client never states its own identity.**

## Entitlements: a dedicated table, read-own, write-nobody

Put the entitlement in its own table rather than a column on the profile — you need Polar's
`modified_at` for the ordering guard, and the customer/subscription ids for the portal.

```sql
create table sc_subscriptions (
  user_id               uuid not null unique references auth.users (id) on delete cascade,
  plan                  text not null check (plan in ('monthly','six_month')),
  status                text not null,
  expires_at            timestamptz,      -- NULL for recurring; see below
  current_period_end    timestamptz,      -- display only
  cancel_at_period_end  boolean not null default false,
  polar_customer_id     text,
  polar_subscription_id text unique,
  polar_order_id        text unique,
  polar_modified_at     timestamptz not null
);

alter table sc_subscriptions enable row level security;
create policy "select_own" on sc_subscriptions for select using (user_id = auth.uid());
-- No insert/update/delete policy. The webhook's service role bypasses RLS;
-- everyone else is read-only by construction.
```

Verify it, don't assume it:

```sql
select c.relrowsecurity, string_agg(p.polname || ':' || p.polcmd::text, ', ')
from pg_class c join pg_namespace n on n.oid = c.relnamespace
left join pg_policy p on p.polrelid = c.oid
where n.nspname='public' and c.relname='sc_subscriptions' group by 1;
-- want: true | select_own:r        (r = SELECT only)
```

`polcmd` is `"char"`; cast it or Postgres errors with `operator is not unique: text || "char"`.

The writer uses `createClient(url, SERVICE_ROLE_KEY)` from `@supabase/supabase-js` directly —
not the SSR helper, which carries the user's cookies and therefore the user's RLS.

## `server-only` breaks vitest

Server modules that `import "server-only"` throw under vitest. Alias it:

```ts
// vitest.config.ts
resolve: { alias: { "server-only": path.resolve(__dirname, "./src/test/server-only-stub.ts") } }
```

## CSP will silently block the checkout modal

**This is the one that will bite you.** A nonce/`strict-dynamic` CSP on the pricing route
blocks Polar's checkout iframe, and the upgrade button does nothing — no console error you'd
attribute to it, nothing in your logs, nothing in Sentry.

```ts
"frame-src 'self' https://polar.sh https://sandbox.polar.sh https://*.polar.sh",
```

Pin it with a test, because nothing else can see this class of failure:

```ts
it("allows the Polar checkout iframe", () => {
  expect(buildCsp("'self' 'nonce-x' 'strict-dynamic'")).toContain("https://polar.sh");
});
```

## `NEXT_PUBLIC_SITE_URL` must be an embed host

`embedOrigin` comes from this value. If it is the default `*.vercel.app` while Polar's
enforced `embed_hosts` lists only the custom domain, the modal never opens. Check the two
against each other in preflight — a green "env var is set" proves nothing.

A tell that this is already wrong in the repo: code elsewhere hardcoding the real domain
(`const siteUrl = process.env.NEXT_PUBLIC_SITE_URL === "http://localhost:3000" ? ... :
"https://realdomain.com"`). Someone hit it and patched around it.

## Preview builds run as production, so a throwing env schema breaks them all

**Every dynamic route on every preview deployment 500s, while the prerendered homepage
returns 200.** That asymmetry is the whole tell, and it reads like a bug in whichever route
you happen to be testing.

Preview builds set `NODE_ENV=production`. A startup validator that *warns* in development and
*throws* in production will therefore throw on preview for any variable scoped to the
production target only:

```ts
if (isProduction) throw new Error(`Invalid environment configuration: ${problems}`);
```

Static pages were already rendered at build time, so they keep serving; anything server-rendered
dies at boot. You will chase the route, the bundler and the webhook signature before you check
env target scoping.

Audit the scoping directly rather than trusting the dashboard's per-variable view:

```bash
curl -s "https://api.vercel.com/v9/projects/$PROJ/env?teamId=$TEAM" -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import sys,json;t={}
for e in json.load(sys.stdin)["envs"]: t.setdefault(e["key"],set()).update(e["target"])
[print(k, sorted(v), "<-- MISSING ON PREVIEW" if "preview" not in v else "") for k,v in sorted(t.items())]'
```

Give preview its own value for anything secret — never copy production's into it. And note the
trap is armed for the future: a variable that is merely *optional* today becomes a
preview-wide outage the day someone adds it to the required schema.

## A failed `vercel env add` can write its own error text as the value

Related to the write-only problem below, and nastier. A malformed `vercel env add` invocation
can end up storing the CLI's usage error **as the variable's value**:

```
NEXT_PUBLIC_SUPABASE_ANON_KEY="Vercel CLI 50.5.0\nError: Invalid number of arguments. Usage: ..."
```

It is a non-empty string, so a `z.string().min(1)` schema passes it happily, and the failure
surfaces much later as `Invalid API key` from whatever consumes it. After any `vercel env pull`,
eyeball the values, not just the key names.

## Vercel env vars created by the CLI are write-only

`vercel env add` (CLI 54.x) creates `type: "sensitive"`. Both `vercel env pull` and the REST
API return an **empty string** for those — indistinguishable from a failed write, and it will
send you chasing a bug that isn't there. Preflight then cannot verify them either.

For values preflight must check, create them as `encrypted` via the API:

```bash
TOKEN=$(python3 -c "import json;print(json.load(open('$HOME/.local/share/com.vercel.cli/auth.json'))['token'])")
curl -s -X POST "https://api.vercel.com/v10/projects/$PROJ/env?teamId=$TEAM" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"key":"POLAR_PRODUCT_ID_MONTHLY","value":"...","type":"encrypted","target":["production"]}'
```

Then `vercel env pull` to a scratch path — **not** `.env.local`, which it overwrites by
default and which holds your sandbox credentials.

## Supabase migration drift

If `supabase db push` refuses and offers `migration repair --status reverted <48 versions>`,
**do not run it.** That marks real, applied migrations as reverted and risks them re-running.
Apply your migration through the API/MCP instead and log the drift as separate work.

Regenerating `database.types.ts` mid-billing-change is a trap: fresh types surface unrelated
pre-existing errors (Supabase types RPC args non-nullable even when the SQL accepts NULL). If
your billing code uses an untyped service client, you do not need the regeneration — keep the
diff to billing.

## Where billing lives in the app

Next.js app shells usually have **two** navs — a `lg:` sidebar and a mobile bottom bar with a
"More" sheet. Adding an entry to one puts nothing in the other. Add billing to:

- the account/profile page (one page, both layouts, and where people look first)
- the sidebar
- the mobile "More" sheet

and grep the shell for a dead flag before assuming the CTA renders:

```bash
grep -rn "showUpgradeCta\|showUpgrade\|isPro" src/components/layout/
```

A hardcoded `const showUpgradeCta = false` left over from the pre-billing era will render
nothing while looking entirely present in the component.

## The profile page needs the entitlement, not just the status

`getSubscriptionStatus()` answers "may they practise". The billing card also needs the renewal
date and whether it is set to cancel, which live on the entitlement row:

```ts
const [status, entitlement] = await Promise.all([
  getSubscriptionStatus(),
  readEntitlement(user.id),   // service-role read
]);
```

## Testing a signed-in page is harder than it looks

`supabase.auth.admin.createUser()` does **not** create your app's profile row — that happens in
the signup flow. Two consequences when scripting a browser test:

- Updating `sc_user_profiles` right after `createUser` silently affects **zero rows**, and any
  code that reads the profile takes its "missing" branch. A fail-open default then makes a
  broken filter look like it works.
- Insert the profile yourself, and set `onboarding_completed: true` — otherwise login redirects
  to onboarding, where the app shell (and therefore the nav, the bell, and everything you
  wanted to assert) does not render.

Clean up `sc_announcement_reads` and `sc_user_profiles` as well as the auth user, and check for
orphans afterwards. And when writing the cleanup filter, **look before you delete**: a pattern
like `email ~ '^ann'` matches real customers.

