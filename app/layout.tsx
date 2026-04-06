import "./css/style.css";

import type { Metadata } from "next";
import { Inter, Bebas_Neue, IBM_Plex_Mono } from "next/font/google";

import Header from "@/components/ui/header";
import Footer from "@/components/ui/footer";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const bebasNeue = Bebas_Neue({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-bebas",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  weight: ["300", "400", "600"],
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Luka Tennis Player",
  description: "React migration baseline for Luka Tennis Player",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${bebasNeue.variable} ${ibmPlexMono.variable}`}>
      <body className="min-h-screen bg-luka-off-white font-sans text-luka-black antialiased">
        <div className="flex min-h-screen flex-col">
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
