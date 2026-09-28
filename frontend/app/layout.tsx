// app/layout.tsx
import "./globals.css";
import { Inter } from "next/font/google";
import Header from "@/components/Header";
import StatusBar from "@/components/StatusBar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata = {
  title: "SkyGuard AI",
  description: "Intelligent AWS Anomaly Detection",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} font-sans`}
        style={{ backgroundColor: "#F7F8F6", color: "#17201E" }}
      >
                <Header />
        <StatusBar />
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}