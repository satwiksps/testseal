import type { Metadata } from "next";
import "./globals.css";
import { getSiteUrl } from "./site-url";

const siteUrl = getSiteUrl();

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "TestSeal — Catch Test Weakening Before It Merges",
  description:
    "Deterministic, diff-aware checks for weakened assertions, new skips, wider tolerances, and other Python test-integrity risks.",
  keywords: [
    "pytest test integrity",
    "Python static analysis",
    "weakened assertions",
    "AI code review",
    "GitHub Action",
    "pre-commit",
    "SARIF",
  ],
  applicationName: "TestSeal",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "/",
    siteName: "TestSeal",
    title: "Catch test weakening before it merges.",
    description:
      "Deterministic, offline test-integrity checks for Python and pytest diffs.",
    images: [{ url: "/og.png", width: 1731, height: 909, alt: "TestSeal test-integrity report" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Catch test weakening before it merges.",
    description:
      "Deterministic test-integrity checks for Python and pytest diffs.",
    images: ["/og.png"],
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
