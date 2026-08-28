import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OSIRIS Imhotep — Engineering SOW Generator",
  description:
    "AI-assisted engineering Scope of Work generator. Upload site media and notes, get a formatted, exportable SOW.",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
