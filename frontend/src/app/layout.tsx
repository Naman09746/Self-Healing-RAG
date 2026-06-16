import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Nexus Core — Self-Healing GraphRAG Platform",
  description:
    "Experience the future of knowledge retrieval. Nexus Core is a multi-agent RAG pipeline with automatic hallucination detection, self-correction, and enterprise-grade security. Ask questions, get verified answers.",
  keywords: [
    "RAG",
    "AI",
    "GraphRAG",
    "knowledge base",
    "self-healing",
    "hallucination detection",
    "LLM",
    "retrieval augmented generation",
    "enterprise AI"
  ],
  openGraph: {
    title: "Nexus Core — Self-Healing GraphRAG Platform",
    description:
      "Multi-agent RAG pipeline with automatic hallucination detection and self-correction. Enterprise-grade knowledge retrieval.",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "Nexus Core — Self-Healing GraphRAG",
    description:
      "Multi-agent RAG pipeline with automatic hallucination detection and self-correction.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

/** Inline script to set data-theme before React hydrates — prevents flash */
const themeScript = `
(function() {
  try {
    var t = localStorage.getItem('nexus-theme');
    if (t === 'light' || t === 'dark') {
      document.documentElement.setAttribute('data-theme', t);
    } else {
      var m = window.matchMedia('(prefers-color-scheme: light)');
      document.documentElement.setAttribute('data-theme', m.matches ? 'light' : 'dark');
    }
  } catch(e) {}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body
        className={`${inter.variable} ${geistMono.variable} antialiased`}
        style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}
      >
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}