import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Work Order Inbox — Elenos AI",
  description: "AI-extracted maintenance work orders, ready to review and push to AppFolio.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
