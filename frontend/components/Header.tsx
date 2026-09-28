// components/Header.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Radar } from "lucide-react";

export default function Header() {
  const pathname = usePathname();

  const navLinks = [
    { href: "/", label: "Dashboard" },
    { href: "/stations", label: "AWS Network" },
  ];

  return (
    <header className="h-16 flex items-center justify-between px-6 bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm">
      {/* Left: Logo + title */}
      <div className="flex items-center gap-2.5">
        <Radar size={24} className="text-teal-600" />
        <div className="flex flex-col">
          <span className="font-bold text-lg text-gray-900 leading-tight">
            SkyGuard AI
          </span>
          <span className="text-xs text-gray-500 leading-tight">
            IMD AWS Monitoring
          </span>
        </div>
      </div>

      {/* Right: Navigation links */}
      <nav className="flex items-center gap-1">
        {navLinks.map((link) => {
          const isActive = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`text-sm px-3 py-2 rounded-md transition-colors ${
                isActive
                  ? "text-teal-600 font-medium"
                  : "text-gray-600 hover:text-teal-600"
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