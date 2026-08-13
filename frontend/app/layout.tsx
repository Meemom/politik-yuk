import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Politik Yuk",
  description: "Source-grounded political news context for young Indonesians.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
