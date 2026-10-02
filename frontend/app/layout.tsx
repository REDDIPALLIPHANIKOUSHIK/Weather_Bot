import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Weatherwise — Outdoor Activity Weather Advisory Bot",
  description:
    "Production-grade weather advisory platform evaluating outdoor activities against live Open-Meteo forecasts and written deterministic SOP policies.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 antialiased min-h-screen selection:bg-cyan-500/20 selection:text-cyan-200">
        {children}
      </body>
    </html>
  );
}
