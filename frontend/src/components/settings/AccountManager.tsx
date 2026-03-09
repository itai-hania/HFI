"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAddInspirationAccount, useDeleteInspirationAccount, useInspirationAccounts } from "@/hooks/useInspiration";

export function AccountManager() {
  const accountsQuery = useInspirationAccounts();
  const addAccount = useAddInspirationAccount();
  const deleteAccount = useDeleteInspirationAccount();

  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [category, setCategory] = useState("");

  const handleAdd = async () => {
    if (!username.trim()) {
      toast.error("Username required");
      return;
    }
    try {
      await addAccount.mutateAsync({ username, display_name: displayName, category });
      setUsername("");
      setDisplayName("");
      setCategory("");
      toast.success("Account added");
    } catch {
      toast.error("Failed to add account");
    }
  };

  return (
    <div className="space-y-3">
      <div className="grid gap-2 md:grid-cols-4">
        <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" />
        <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Display name" />
        <Input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Category" />
        <Button onClick={handleAdd} disabled={addAccount.isPending}>
          Add
        </Button>
      </div>

      <div className="space-y-2">
        {(accountsQuery.data || []).map((account) => (
          <div key={account.id} className="flex items-center justify-between rounded-xl border border-[var(--border)] px-3 py-2">
            <div>
              <p className="text-sm">@{account.username}</p>
              <p className="text-xs text-[var(--muted)]">{account.display_name || "-"}</p>
            </div>
            <Button
              variant="danger"
              onClick={() => deleteAccount.mutate(account.id, { onSuccess: () => toast.success("Removed") })}
            >
              Remove
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
