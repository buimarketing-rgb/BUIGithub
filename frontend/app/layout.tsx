import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: { default: "BUI – Business Unified Intelligence", template: "%s · BUI" },
  description: "BUI – Your Intelligent Business & Product Assistant.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: [{ color: "#1F5FA8" }] };

const themeScript = `try{var t=localStorage.getItem('bui-theme')||'system';var d=t==='dark'||(t==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);if(d)document.documentElement.classList.add('dark')}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
