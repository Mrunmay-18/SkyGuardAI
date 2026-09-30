// components/Header.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Radar, WifiOff } from "lucide-react";
import { isOfflineMode } from "@/lib/api";

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
    <header className="h-16 flex items-center justify-between px-6 bg-white/90 backdrop-blur-md border-b border-stone-200/80 sticky top-0 z-40 shadow-soft transition-all">
      <Link href="/" className="flex items-center gap-3 group">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-teal-600 via-teal-700 to-teal-800 flex items-center justify-center shadow-sm shadow-teal-900/15 ring-1 ring-white/30 group-hover:shadow-md group-hover:scale-[1.03] transition-all duration-200">
          <Radar size={19} className="text-teal-50 transition-transform duration-300 group-hover:rotate-12" />
        </div>
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-base text-stone-900 leading-tight tracking-tight">
              SkyGuard AI
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-teal-600 animate-pulse" />
          </div>
          <span className="text-[11px] text-stone-500 leading-tight font-medium">
            IMD AWS Monitoring
          </span>
        </div>
      </Link>

      {/* Offline indicator */}
      {typeof window !== "undefined" && isOfflineMode() && (
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-[11px] font-medium text-amber-700">
          <WifiOff size={12} />
          Offline mode — cached data
        </div>
      )}

      <nav className="flex items-center gap-1 overflow-x-auto py-1">
        {navLinks.map((link) => {
          const isActive = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`text-sm px-3.5 py-1.5 rounded-full transition-all duration-150 font-medium ${
                isActive
                  ? "text-teal-800 bg-teal-50 font-semibold ring-1 ring-teal-600/20 shadow-xs"
                  : "text-stone-600 hover:text-stone-900 hover:bg-stone-100/70"
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