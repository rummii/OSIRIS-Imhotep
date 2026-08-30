import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import ServiceWorkerRegister from "@/components/ServiceWorkerRegister";

export const metadata: Metadata = {
  title: "OSIRIS Imhotep — Engineering SOW Generator",
  description:
    "AI-assisted engineering Scope of Work generator. Upload site media and notes, get a formatted, exportable SOW.",
  icons: {
    icon: "/favicon.svg",
  },
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <ServiceWorkerRegister />
        {children}
      </body>
    </html>
  );
}
