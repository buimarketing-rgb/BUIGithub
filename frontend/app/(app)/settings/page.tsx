"use client";
import * as React from "react";
import { Settings, User as UserIcon, Lock, Palette, SlidersHorizontal, HeartPulse, ScrollText, CheckCircle2, XCircle, Sun, Moon, Monitor } from "lucide-react";
import type { User } from "@/types";
import { api, qs } from "@/services/api";
import { useApi } from "@/hooks/use-api";
import { useAuth, useTheme } from "@/components/providers";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Switch, Textarea } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ErrorBox, PageHeader, Pagination, Skeleton, Table, Tabs, Td, Th } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { VOICE_LANGUAGES } from "@/hooks/use-speech";
import { cn, formatDate } from "@/lib/utils";

function Profile() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [name, setName] = React.useState(user?.full_name || "");
  const [lang, setLang] = React.useState(user?.preferred_language || "en-US");
  const [busy, setBusy] = React.useState(false);
  const save = async () => {
    setBusy(true);
    try { setUser(await api<User>("/auth/me", { method: "PATCH", json: { full_name: name, preferred_language: lang } })); toast.success("Profile saved"); }
    catch (e) { toast.error((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <Card className="max-w-xl"><CardHeader><CardTitle>Profile</CardTitle><CardDescription>{user?.email}</CardDescription></CardHeader><CardContent className="space-y-4">
      <Field label="Full name"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Preferred language" hint="Default language for chat answers and voice."><Select value={lang} onChange={(e) => setLang(e.target.value)}>{VOICE_LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}</Select></Field>
      <Button onClick={save} loading={busy}>Save profile</Button>
    </CardContent></Card>
  );
}

function Security() {
  const toast = useToast();
  const [cur, setCur] = React.useState(""); const [pw, setPw] = React.useState(""); const [pw2, setPw2] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pw !== pw2) { toast.error("New passwords do not match"); return; }
    setBusy(true);
    try { await api("/auth/change-password", { method: "POST", json: { current_password: cur, new_password: pw } }); toast.success("Password changed"); setCur(""); setPw(""); setPw2(""); }
    catch (err) { toast.error("Could not change password", (err as Error).message); } finally { setBusy(false); }
  };
  return (
    <Card className="max-w-xl"><CardHeader><CardTitle>Change password</CardTitle><CardDescription>At least 10 characters with upper- and lower-case letters and a number.</CardDescription></CardHeader><CardContent>
      <form onSubmit={save} className="space-y-4">
        <Field label="Current password"><Input type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} required /></Field>
        <Field label="New password"><Input type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} required minLength={10} /></Field>
        <Field label="Confirm new password"><Input type="password" autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} required /></Field>
        <Button loading={busy}>Update password</Button>
      </form>
    </CardContent></Card>
  );
}

function Appearance() {
  const { theme, setTheme } = useTheme();
  const opts = [{ v: "light", l: "Light", I: Sun }, { v: "dark", l: "Dark", I: Moon }, { v: "system", l: "System", I: Monitor }] as const;
  return (
    <Card className="max-w-xl"><CardHeader><CardTitle>Appearance</CardTitle></CardHeader><CardContent className="grid grid-cols-3 gap-3">
      {opts.map(({ v, l, I }) => (
        <button key={v} onClick={() => setTheme(v)} className={cn("flex flex-col items-center gap-2 rounded-lg border p-4 text-sm transition-colors", theme === v ? "border-primary bg-accent" : "hover:bg-secondary")}><I className="size-5" />{l}</button>
      ))}
    </CardContent></Card>
  );
}

type SettingsMap = Record<string, { value: unknown; description: string }>;
function SystemSettings() {
  const { can } = useAuth();
  const toast = useToast();
  const { data, reload } = useApi<SettingsMap>("/settings");
  const [vals, setVals] = React.useState<Record<string, unknown>>({});
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => { if (data) setVals(Object.fromEntries(Object.entries(data).map(([k, v]) => [k, v.value]))); }, [data]);
  if (!data) return <Skeleton className="h-96" />;
  const editable = can("super_admin");
  const save = async () => {
    setBusy(true);
    try { await api("/settings", { method: "PUT", json: { values: vals } }); toast.success("Settings saved"); reload(); }
    catch (e) { toast.error("Could not save settings", (e as Error).message); } finally { setBusy(false); }
  };
  const set = (k: string, v: unknown) => setVals((x) => ({ ...x, [k]: v }));
  const d = (k: string) => data[k]?.description;
  return (
    <Card className="max-w-3xl"><CardHeader><CardTitle>System configuration</CardTitle><CardDescription>{editable ? "Changes apply immediately. API keys and credentials are configured only through server environment variables." : "Only a Super Admin can change these settings."}</CardDescription></CardHeader>
      <CardContent><fieldset disabled={!editable} className="grid gap-4 sm:grid-cols-2">
        <Field label="Company name" hint={d("company_name")}><Input value={String(vals.company_name ?? "")} onChange={(e) => set("company_name", e.target.value)} /></Field>
        <Field label="Default language"><Select value={String(vals.default_language ?? "en-US")} onChange={(e) => set("default_language", e.target.value)}>{VOICE_LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}</Select></Field>
        <Field label="AI model provider" hint="Ollama (local, free), any OpenAI-compatible API, or Extractive (no LLM — answers quoted directly from verified sources).">
          <Select value={String(vals.llm_provider)} onChange={(e) => set("llm_provider", e.target.value)}><option value="ollama">Ollama (local)</option><option value="openai">OpenAI-compatible API</option><option value="extractive">Extractive (no LLM)</option></Select>
        </Field>
        <Field label="Model name" hint="Empty = server default (OLLAMA_MODEL / OPENAI_MODEL). e.g. llama3.2:3b, qwen2.5:7b"><Input placeholder="Server default" value={String(vals.llm_model ?? "")} onChange={(e) => set("llm_model", e.target.value)} /></Field>
        <Field label="Temperature" hint={d("llm_temperature")}><Input type="number" step="0.05" min="0" max="1.5" value={String(vals.llm_temperature ?? 0.1)} onChange={(e) => set("llm_temperature", Number(e.target.value))} /></Field>
        <Field label="Minimum relevance to answer" hint={d("answer_min_score")}><Input type="number" step="0.01" min="0" max="1" value={String(vals.answer_min_score ?? 0.3)} onChange={(e) => set("answer_min_score", Number(e.target.value))} /></Field>
        <Field label="Sources per answer" hint={d("retrieval_top_k")}><Input type="number" min="1" max="20" value={String(vals.retrieval_top_k ?? 6)} onChange={(e) => set("retrieval_top_k", Number(e.target.value))} /></Field>
        <Field label="Answer cache (seconds)" hint={d("answer_cache_ttl_seconds")}><Input type="number" min="0" value={String(vals.answer_cache_ttl_seconds ?? 3600)} onChange={(e) => set("answer_cache_ttl_seconds", Number(e.target.value))} /></Field>
        <div className="flex items-center justify-between gap-4 rounded-lg border p-3 sm:col-span-2"><div><p className="text-sm font-medium">Online research</p><p className="text-xs text-muted-foreground">{d("web_research_enabled")}</p></div><Switch checked={!!vals.web_research_enabled} onChange={(v) => set("web_research_enabled", v)} disabled={!editable} /></div>
        <div className="flex items-center justify-between gap-4 rounded-lg border p-3 sm:col-span-2"><div><p className="text-sm font-medium">Team members can research from chat</p><p className="text-xs text-muted-foreground">{d("team_can_research_from_chat")}</p></div><Switch checked={!!vals.team_can_research_from_chat} onChange={(v) => set("team_can_research_from_chat", v)} disabled={!editable} /></div>
        <Field label="Official manufacturer domains" className="sm:col-span-2" hint="One per line. Sources on these domains are prioritised and marked official.">
          <Textarea rows={3} value={((vals.official_domains as string[]) || []).join("\n")} onChange={(e) => set("official_domains", e.target.value.split("\n").map((x) => x.trim()).filter(Boolean))} />
        </Field>
      </fieldset>
      {editable && <Button className="mt-4" onClick={save} loading={busy}>Save settings</Button>}
      </CardContent></Card>
  );
}

function Health() {
  const { data, error, reload, loading } = useApi<Record<string, { ok?: boolean; detail?: string; provider?: string; fallback?: boolean; browser?: boolean; whisper?: boolean }>>("/system/health");
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return <Skeleton className="h-64" />;
  const rows: [string, boolean, string][] = [
    ["Database (PostgreSQL + pgvector)", !!data.database?.ok, data.database?.detail || ""],
    ["Cache", true, data.cache?.detail === "redis" ? "Redis" : "In-memory (Redis not reachable)"],
    ["Embeddings", !data.embeddings?.fallback, data.embeddings?.fallback ? `${data.embeddings?.detail} — fallback mode; semantic quality reduced` : data.embeddings?.detail || ""],
    [`AI model (${data.llm?.provider})`, !!data.llm?.ok, data.llm?.ok ? data.llm?.detail || "ready" : `${data.llm?.detail} — BUI falls back to extractive answers`],
    ["Web search", !!data.search?.ok, data.search?.detail || ""],
    ["Voice", true, `Browser speech: yes · Server Whisper: ${data.voice?.whisper ? "enabled" : "disabled"}`],
  ];
  return (
    <Card className="max-w-3xl"><CardHeader className="flex-row items-center justify-between"><CardTitle>System health</CardTitle><Button size="sm" variant="outline" onClick={reload} loading={loading}>Re-check</Button></CardHeader><CardContent className="divide-y">
      {rows.map(([name, ok, detail]) => (
        <div key={name} className="flex items-start gap-3 py-3">
          {ok ? <CheckCircle2 className="size-5 shrink-0 text-success" /> : <XCircle className="size-5 shrink-0 text-warning" />}
          <div><p className="text-sm font-medium">{name}</p><p className="text-xs text-muted-foreground break-all">{detail}</p></div>
        </div>
      ))}
    </CardContent></Card>
  );
}

interface AuditRow { id: number; created_at: string; user_email: string | null; action: string; entity_type: string; entity_id: string | null; summary: string | null; ip_address: string | null }
function AuditLog() {
  const [q, setQ] = React.useState(""); const [entity, setEntity] = React.useState(""); const [page, setPage] = React.useState(1);
  const { data } = useApi<{ items: AuditRow[]; total: number }>(`/audit-logs${qs({ q, entity_type: entity, page, page_size: 50 })}`);
  return (
    <Card><CardHeader><CardTitle>Audit log</CardTitle><CardDescription>Every change to company knowledge, users and settings.</CardDescription></CardHeader><CardContent>
      <div className="mb-3 grid gap-2 sm:grid-cols-[1fr_200px]">
        <Input placeholder="Search summaries…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <Select value={entity} onChange={(e) => { setEntity(e.target.value); setPage(1); }}><option value="">All entities</option>{["product", "document", "faq", "user", "research_job", "research_finding", "category", "system_settings", "knowledge"].map((x) => <option key={x} value={x}>{x.replace("_", " ")}</option>)}</Select>
      </div>
      <Table><thead><tr><Th>When</Th><Th>User</Th><Th>Action</Th><Th>Summary</Th></tr></thead>
        <tbody>{data?.items.map((r) => (
          <tr key={r.id}><Td className="whitespace-nowrap text-xs">{formatDate(r.created_at, true)}</Td><Td className="text-xs">{r.user_email || "system"}</Td>
            <Td><Badge variant={r.action.includes("delete") || r.action.includes("failed") ? "destructive" : "secondary"}>{r.action}</Badge></Td><Td className="text-xs">{r.summary}</Td></tr>
        ))}</tbody></Table>
      {data && <Pagination page={page} pageSize={50} total={data.total} onChange={setPage} />}
    </CardContent></Card>
  );
}

export default function SettingsPage() {
  const { can } = useAuth();
  type T = "profile" | "security" | "appearance" | "system" | "health" | "audit";
  const [tab, setTab] = React.useState<T>("profile");
  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-6">
      <PageHeader icon={Settings} title="Settings" />
      <Tabs className="mb-4" value={tab} onChange={setTab} tabs={[
        { value: "profile", label: "Profile", icon: UserIcon }, { value: "security", label: "Password", icon: Lock }, { value: "appearance", label: "Appearance", icon: Palette },
        ...(can("admin") ? [{ value: "system" as T, label: "System", icon: SlidersHorizontal }, { value: "health" as T, label: "Health", icon: HeartPulse }, { value: "audit" as T, label: "Audit log", icon: ScrollText }] : []),
      ]} />
      {tab === "profile" && <Profile />}
      {tab === "security" && <Security />}
      {tab === "appearance" && <Appearance />}
      {tab === "system" && <SystemSettings />}
      {tab === "health" && <Health />}
      {tab === "audit" && <AuditLog />}
    </div>
  );
}
