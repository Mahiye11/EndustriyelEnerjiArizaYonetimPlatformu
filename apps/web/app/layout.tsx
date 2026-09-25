import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {title: "FactoryPulse", description: "Industrial energy and maintenance command center"};

export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="tr"><body>{children}</body></html>;
}

