import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EconRoute — Cost Analytics",
  description:
    "Routes every LLM request to the cheapest capable model. Zero API cost, full cost analytics.",
};

// Server component — no hooks, no client APIs.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
