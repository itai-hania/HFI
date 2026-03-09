import type { Metadata } from "next";
import { Heebo, Newsreader } from "next/font/google";
import "./globals.css";

import { Providers } from "@/app/providers";

const heebo = Heebo({
  subsets: ["latin", "hebrew"],
  weight: ["400", "500", "700"],
  display: "swap",
  variable: "--font-hebrew-ui",
});

const newsreader = Newsreader({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  display: "swap",
  variable: "--font-display-ui",
});

export const metadata: Metadata = {
  title: "HFI Content Studio",
  description: "Hebrew FinTech content creation tool",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl" className={`${heebo.variable} ${newsreader.variable} dark`}>
      <body className="font-hebrew min-h-screen antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
