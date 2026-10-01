import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Weatherwise — Outdoor decisions, grounded", description: "Live weather and written safety policies for your outdoor plans." };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
