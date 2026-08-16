# TestSeal website

The public landing site for TestSeal. It is a standalone Next.js, TypeScript,
and Tailwind CSS application kept inside the main repository so product copy
and shipped behavior can evolve together.

## Local development

```bash
npm ci
npm run dev
```

Open `http://localhost:3000`.

Copy `.env.example` to `.env.local` when you want production canonical links
locally:

```env
NEXT_PUBLIC_SITE_URL=https://testseal-integrity.vercel.app
```

Repository calls to action always use the canonical
[`satwiksps/testseal`](https://github.com/satwiksps/testseal) URL.

## Verification

```bash
npm run verify
```

This checks lint, types, source-level content invariants, and the production
Next.js build.

## Deploy to Vercel

1. Import the main TestSeal repository in Vercel.
2. Set the project **Root Directory** to `site`.
3. Keep the detected framework as **Next.js** and use the default commands.
4. Optionally set `NEXT_PUBLIC_SITE_URL` to a custom production origin. If it is
   omitted, the site uses Vercel's system-provided production URL and fails
   closed if no public Vercel URL is available.
   No database, server secret, or external service is required.
