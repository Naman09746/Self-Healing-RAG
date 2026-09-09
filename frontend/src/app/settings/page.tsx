"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SettingsLegacyRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/app/settings");
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 text-xs text-slate-500">
      Redirecting to Settings...
    </div>
  );
}
