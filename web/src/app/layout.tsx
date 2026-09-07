import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hion — Autonomous Work System",
  description:
    "Give Hion a goal. Its AI workforce plans, delegates, critiques and executes the mission.",
};

export const viewport: Viewport = {
  themeColor: "#F7F7F5",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="bg-paper text-ink-900 antialiased">{children}</body>
    </html>
  );
}
