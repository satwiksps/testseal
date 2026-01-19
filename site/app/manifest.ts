import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "TestSeal",
    short_name: "TestSeal",
    description: "Deterministic test integrity for Python and pytest diffs.",
    start_url: "/",
    display: "standalone",
    background_color: "#09090b",
    theme_color: "#09090b",
    icons: [{ src: "/icon", sizes: "64x64", type: "image/png" }],
  };
}
