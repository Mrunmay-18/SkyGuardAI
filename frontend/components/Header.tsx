// components/Header.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Radar } from "lucide-react";

export default function Header() {
  const pathname = usePathname();

  const navLinks = [
    { href: "/", label: "Dashboard" },
    { href: "/network", label: "Network" },
    { href: "/parameters", label: "Parameters" },
    { href: "/reality-check", label: "Reality Check" },
    { href: "/test", label: "Test AI" },
    { href: "/maintenance", label: "Maintenance" },
    { href: "/stations", label: "AWS Stations" },
  ];

  return (
    <header className="h-16 flex items-center justify-between px-6 bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm backdrop-blur-sm bg-white/95">
      <Link href="/" className="flex items-center gap-2.5 group">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-teal-500 to-teal-700 flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow">
          <Radar size={20} className="text-white" />
        </div>
        <div className="flex flex-col">
          <span className="font-bold text-base text-gray-900 leading-tight tracking-tight">
            SkyGuard AI
          </span>
          <span className="text-[11px] text-gray-500 leading-tight font-medium">
            IMD AWS Monitoring
          </span>
        </div>
      </Link>

      <nav className="flex items-center gap-1">
        {navLinks.map((link) => {
          const isActive = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`text-sm px-3.5 py-2 rounded-md transition-all duration-150 font-medium ${
                isActive
                  ? "text-teal-700 bg-teal-50"
                  : "text-gray-600 hover:text-teal-700 hover:bg-gray-50"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}