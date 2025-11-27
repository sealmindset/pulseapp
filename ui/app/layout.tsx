import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { SessionProvider } from "@/components/SessionContext";

const enableTraining =
  process.env.NEXT_PUBLIC_ENABLE_TRAINING === "true" &&
  process.env.NEXT_PUBLIC_ENV_NAME !== "prod";

export const metadata: Metadata = {
  title: "PULSE Selling Behavioral Certification",
  description: "RESTRICTED IP: Hyper-Engineered Behavioral Sales (PULSE Selling, formerly SBN)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-gray-900 antialiased">
        <SessionProvider>
          <header className="border-b bg-white/80 backdrop-blur supports-[backdrop-filter]:bg-white/60">
            <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
              <div className="font-semibold">PULSE/H2</div>
              <ul className="flex items-center gap-4 text-sm">
                <li><Link href="/">Pre-Session</Link></li>
                <li><Link href="/session">Session</Link></li>
                {enableTraining && <li><Link href="/training">Training</Link></li>}
                <li><Link href="/feedback">Feedback</Link></li>
                <li><Link href="/admin">Admin</Link></li>
              </ul>
            </nav>
          </header>
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        </SessionProvider>
      </body>
    </html>
  );
}
