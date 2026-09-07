import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hion — Autonomous Work System",
  description:
    "Give Hion a goal. Its AI workforce plans, delegates, critiques and executes the mission.",
};

export const viewport: Viewport = {
  themeColor: "#050609",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <div className="fixed inset-0 -z-10 bg-void-950" />
        {children}
      </body>
    </html>
  );
}
