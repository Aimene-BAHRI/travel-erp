import type { Metadata } from "next";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Wakaltcom ERP",
  description: "منصة إدارة عمليات وكالات السفر والعمرة",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ar" dir="rtl">
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
