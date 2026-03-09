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
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
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
      toast.error("Wrong password");
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
          <p className="mt-2 text-sm text-[var(--muted)]">Sign in to access your editorial command center.</p>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleLogin}>
            <Input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              dir="ltr"
              autoComplete="current-password"
            />
            <Button type="submit" className="w-full" disabled={loading || !password.trim()}>
              {loading ? "Signing in..." : "Login"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
