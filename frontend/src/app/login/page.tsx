"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import api from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [password, setPassword] = useState("");
  const router = useRouter();
  const { setToken } = useAuth();

  async function handleLogin(event: FormEvent) {
    event.preventDefault();
    setLoading(true);

    try {
      const { data } = await api.post<{ access_token: string }>("/api/auth/login", { password });
      setToken(data.access_token);
      toast.success("Signed in");
      router.push("/");
    } catch {
      toast.error("Sign in failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <p className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">Welcome back</p>
          <CardTitle className="font-display mt-2 text-3xl leading-tight">HFI Content Studio</CardTitle>
          <p className="mt-2 text-sm text-[var(--muted)]">Continue to access your editorial command center.</p>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleLogin}>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-[var(--ink)]" htmlFor="password">
                Password
              </label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter dashboard password"
                disabled={loading}
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading || !password.trim()}>
              {loading ? "Signing in..." : "Continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
