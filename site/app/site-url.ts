const LOCAL_SITE_URL = "http://localhost:3000";
const PRODUCTION_SITE_URL = "https://testseal-integrity.vercel.app";

function normalizeSiteUrl(value: string): string {
  const candidate = value.trim();
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(candidate) && !/^https?:\/\//i.test(candidate)) {
    throw new Error("The public site URL must use http or https.");
  }
  const withProtocol = /^https?:\/\//i.test(candidate)
    ? candidate
    : `https://${candidate}`;
  let url: URL;
  try {
    url = new URL(withProtocol);
  } catch {
    throw new Error("The public site URL must be a valid http or https URL.");
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("The public site URL must use http or https.");
  }

  return url.origin;
}

export function getSiteUrl(): string {
  const configuredUrl =
    process.env.NEXT_PUBLIC_SITE_URL ??
    process.env.VERCEL_PROJECT_PRODUCTION_URL ??
    process.env.VERCEL_URL;

  if (configuredUrl) return normalizeSiteUrl(configuredUrl);

  if (process.env.NODE_ENV === "production" && process.env.VERCEL === "1") {
    throw new Error(
      "A public site URL is required on Vercel. Set NEXT_PUBLIC_SITE_URL or enable Vercel system environment variables.",
    );
  }

  return process.env.NODE_ENV === "production" ? PRODUCTION_SITE_URL : LOCAL_SITE_URL;
}
