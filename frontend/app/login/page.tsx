"use client";
import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Sparkles, ShieldCheck, Mic, BookOpen } from "lucide-react";
import { useAuth } from "@/components/providers";
import { Button } from "@/components/ui/button";
import { Input, Field } from "@/components/ui/input";
import { Logo } from "@/components/layout/logo";

function LoginForm() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/assistant";
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => { if (!loading && user) router.replace(next.startsWith("/") ? next : "/assistant"); }, [user, loading, router, next]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try { await login(email, password); } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="Work e-mail"><Input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" /></Field>
      <Field label="Password"><Input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <Button type="submit" className="w-full" size="lg" loading={busy}>Sign in</Button>
      <p className="text-center text-sm"><Link href="/reset-password" className="text-primary hover:underline">Forgot your password?</Link></p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-gradient-to-br from-[#163f73] via-primary to-[#0f2c52] p-12 text-white relative overflow-hidden">
        <div className="absolute -right-24 -top-24 size-96 rounded-full bg-brandred/30 blur-3xl" />
        <Logo className="[&_p]:text-white [&_.text-muted-foreground]:text-white/70" />
        <div className="relative space-y-6">
          <h1 className="text-4xl font-bold leading-tight">Your Intelligent Business<br />&amp; Product Assistant.</h1>
          <ul className="space-y-3 text-white/85">
            <li className="flex gap-3"><BookOpen className="size-5 shrink-0" />Answers grounded in your approved company knowledge, with sources.</li>
            <li className="flex gap-3"><Mic className="size-5 shrink-0" />Ask by voice — BUI listens and reads answers aloud.</li>
            <li className="flex gap-3"><Sparkles className="size-5 shrink-0" />Online product research with an approval workflow.</li>
            <li className="flex gap-3"><ShieldCheck className="size-5 shrink-0" />Role-based access. BUI never invents specifications.</li>
          </ul>
        </div>
        <p className="relative text-sm text-white/60">BUI – Business Unified Intelligence</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-8">
          <Logo className="lg:hidden" />
          <div>
            <h2 className="text-2xl font-semibold">Welcome back</h2>
            <p className="text-sm text-muted-foreground mt-1">Sign in to your BUI workspace.</p>
          </div>
          <React.Suspense><LoginForm /></React.Suspense>
        </div>
      </div>
    </div>
  );
}
