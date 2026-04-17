import type { Metadata, Viewport } from "next";
import { Geist_Mono } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const archivo = localFont({
  src: [
    { path: "../public/fonts/archivo.woff2", style: "normal", weight: "100 900" },
    { path: "../public/fonts/archivo-italic.woff2", style: "italic", weight: "100 900" },
  ],
  variable: "--font-archivo",
  display: "swap",
});

const clashDisplay = localFont({
  src: "../public/fonts/clash-display.woff2",
  variable: "--font-display-serif",
  weight: "200 700",
  style: "normal",
  display: "swap",
});

const telma = localFont({
  src: "../public/fonts/telma.woff2",
  variable: "--font-title",
  weight: "300 900",
  style: "normal",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ForMula",
  description: "Ingredient-aware hair product research.",
};

export const viewport: Viewport = {
  themeColor: "#6760f7",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${geistMono.variable} ${clashDisplay.variable} ${telma.variable} h-full antialiased`}
    >
      <body className="h-full flex flex-col overflow-hidden">{children}</body>
    </html>
  );
}
