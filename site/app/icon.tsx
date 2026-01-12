import { ImageResponse } from "next/og";

export const size = { width: 64, height: 64 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          alignItems: "center",
          background: "#09090b",
          border: "1px solid #3f3f46",
          borderRadius: 12,
          color: "#93c5fd",
          display: "flex",
          fontFamily: "monospace",
          fontSize: 21,
          fontWeight: 700,
          height: "100%",
          justifyContent: "center",
          letterSpacing: -1,
          width: "100%",
        }}
      >
        TS
      </div>
    ),
    size,
  );
}
