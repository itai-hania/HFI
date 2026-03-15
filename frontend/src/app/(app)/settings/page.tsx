"use client";

import { AccountManager } from "@/components/settings/AccountManager";
import { FeedbackWeights } from "@/components/settings/FeedbackWeights";
import { GlossaryEditor } from "@/components/settings/GlossaryEditor";
import { PreferencesForm } from "@/components/settings/PreferencesForm";
import { StyleExampleManager } from "@/components/settings/StyleExampleManager";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <header className="surface-glow rounded-3xl px-5 py-5 md:px-6 md:py-6">
        <h2 className="font-display text-3xl leading-tight">Settings</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">Manage glossary, style, accounts, and publishing preferences.</p>
      </header>

      <details open className="rounded-3xl border border-[var(--border)] bg-[var(--card)]/75">
        <summary className="cursor-pointer px-5 py-4 font-medium">Inspiration Accounts</summary>
        <div className="px-5 pb-5">
          <AccountManager />
        </div>
      </details>

      <details className="rounded-3xl border border-[var(--border)] bg-[var(--card)]/75">
        <summary className="cursor-pointer px-5 py-4 font-medium">Glossary</summary>
        <div className="px-5 pb-5">
          <GlossaryEditor />
        </div>
      </details>

      <details className="rounded-3xl border border-[var(--border)] bg-[var(--card)]/75">
        <summary className="cursor-pointer px-5 py-4 font-medium">Style Examples</summary>
        <div className="px-5 pb-5">
          <StyleExampleManager />
        </div>
      </details>

      <details className="rounded-3xl border border-[var(--border)] bg-[var(--card)]/75">
        <summary className="cursor-pointer px-5 py-4 font-medium">Telegram</summary>
        <div className="space-y-2 px-5 pb-5 text-sm text-[var(--muted)]">
          <p>Status: configured via `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.</p>
          <p>Use `/brief` to fetch latest stories and `/status` to view queue stats.</p>
        </div>
      </details>

      <details className="rounded-3xl border border-[var(--border)] bg-[var(--card)]/75">
        <summary className="cursor-pointer px-5 py-4 font-medium">Brief Preferences</summary>
        <div className="px-5 pb-5">
          <FeedbackWeights />
        </div>
      </details>

      <Card>
        <CardHeader>
          <CardTitle>Preferences</CardTitle>
        </CardHeader>
        <CardContent>
          <PreferencesForm />
        </CardContent>
      </Card>
    </div>
  );
}
