import type { Metadata } from "next";
import { Footer } from "@/components/Footer";
import "./globals.css";

export const metadata: Metadata = {
  title: "OddsX Clearinghouse",
  description: "Subjective prediction markets resolved by GenLayer validator consensus.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col bg-slate-50">
        {children}
        <Footer />
      </body>
    </html>
  );
}
