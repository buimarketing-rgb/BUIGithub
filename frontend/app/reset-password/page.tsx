"use client";
import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input, Field } from "@/components/ui/input";
import { Logo } from "@/components/layout/logo";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

function ResetInner() {
  const token = useSearchParams().get("token");
  const [email, setEmail] = React.useState("");
  const [pw, setPw] = React.useState("");
  const [pw2, setPw2] = React.useState("");
  const [msg, setMsg] = React.useState<string | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [done, setDone] = React.useState(false);

  const request = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { const r = await api<{ message: string }>("/auth/forgot-password", { method: "POST", json: { email } }); setMsg(r.message); }
    catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  const reset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pw !== pw2) { setErr("Passwords do not match."); return; }
    setBusy(true); setErr(null);
    try { await api("/auth/reset-password", { method: "POST", json: { token, new_password: pw } }); setDone(true); }
    catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>{token ? "Choose a new password" : "Reset your password"}</CardTitle>
        <CardDescription>{token ? "At least 10 characters with upper- and lower-case letters and a number." : "Enter your work e-mail to receive a reset link."}</CardDescription>
      </CardHeader>
      <CardContent>
        {done ? (
          <div className="space-y-4"><p className="text-sm">Your password has been changed.</p><Link href="/login"><Button className="w-full">Sign in</Button></Link></div>
        ) : token ? (
          <form onSubmit={reset} className="space-y-4">
            <Field label="New password"><Input type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} required minLength={10} /></Field>
            <Field label="Confirm password"><Input type="password" autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} required /></Field>
            {err && <p className="text-sm text-destructive">{err}</p>}
            <Button className="w-full" loading={busy}>Update password</Button>
          </form>
        ) : msg ? (
          <p className="text-sm">{msg}</p>
        ) : (
          <form onSubmit={request} className="space-y-4">
            <Field label="Work e-mail"><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
            {err && <p className="text-sm text-destructive">{err}</p>}
            <Button className="w-full" loading={busy}>Send reset link</Button>
          </form>
        )}
        <p className="mt-4 text-center text-sm"><Link className="text-primary hover:underline" href="/login">Back to sign in</Link></p>
      </CardContent>
    </Card>
  );
}

export default function ResetPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 p-6">
      <Logo />
      <React.Suspense><ResetInner /></React.Suspense>
    </div>
  );
}
