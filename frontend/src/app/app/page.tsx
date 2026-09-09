"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AppIndexRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/app/dashboard");
  }, [router]);

  return (
    <div className="min-h-[50vh] flex items-center justify-center text-xs text-slate-500">
      Redirecting to dashboard...
    </div>
  );
}
