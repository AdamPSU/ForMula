import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";

const archivo = localFont({
  src: [
    { path: "../public/fonts/archivo.woff2", weight: "400", style: "normal" },
    { path: "../public/fonts/archivo-italic.woff2", weight: "400", style: "italic" },
    { path: "../public/fonts/archivo-bold.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-archivo",
  display: "swap",
});

const clashDisplay = localFont({
  src: [{ path: "../public/fonts/clash-display.woff2", weight: "400", style: "normal" }],
  variable: "--font-clash",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ForMula",
  description: "The formula that fits your hair.",
};

export const viewport: Viewport = {
  themeColor: "#000000",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${archivo.variable} ${clashDisplay.variable} antialiased`}>
      <body>{children}</body>
    </html>
  );
}
