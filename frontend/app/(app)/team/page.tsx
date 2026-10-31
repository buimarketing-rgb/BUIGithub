"use client";
import * as React from "react";
import { Users, UserPlus, Search, KeyRound, Trash2, Copy } from "lucide-react";
import type { Page, User } from "@/types";
import { api, qs } from "@/services/api";
import { useApi, useDebounced } from "@/hooks/use-api";
import { useAuth } from "@/components/providers";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Switch } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, useConfirm } from "@/components/ui/dialog";
import { ErrorBox, PageHeader, Pagination, Skeleton, Table, Td, Th } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { ROLE_LABEL, timeAgo } from "@/lib/utils";

export default function TeamPage() {
  const { user: me, can } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const [q, setQ] = React.useState("");
  const [role, setRole] = React.useState("");
  const [page, setPage] = React.useState(1);
  const dq = useDebounced(q);
  const { data, error, loading, reload } = useApi<Page<User>>(`/users${qs({ q: dq, role, page, page_size: 25 })}`);
  const [creating, setCreating] = React.useState(false);
  const [form, setForm] = React.useState({ email: "", full_name: "", role: "team_member", password: "" });
  const [busy, setBusy] = React.useState(false);
  const [resetLink, setResetLink] = React.useState<string | null>(null);
  const canManage = (u: User) => u.id !== me?.id && (can("super_admin") || u.role === "team_member");

  const create = async () => {
    setBusy(true);
    try { await api("/users", { method: "POST", json: form }); toast.success("User created", `Share the temporary password with ${form.email} securely.`); setCreating(false); reload(); }
    catch (e) { toast.error("Could not create user", (e as Error).message); } finally { setBusy(false); }
  };
  const update = async (u: User, body: Partial<User>) => {
    try { await api(`/users/${u.id}`, { method: "PATCH", json: body }); reload(); } catch (e) { toast.error("Update failed", (e as Error).message); }
  };
  const remove = async (u: User) => {
    if (!(await confirm({ title: `Delete ${u.full_name}?`, description: "Their chat history will also be deleted. Consider deactivating instead.", confirmLabel: "Delete", destructive: true }))) return;
    try { await api(`/users/${u.id}`, { method: "DELETE" }); reload(); } catch (e) { toast.error((e as Error).message); }
  };
  const reset = async (u: User) => {
    try { const r = await api<{ reset_url: string }>(`/users/${u.id}/reset-link`, { method: "POST" }); setResetLink(r.reset_url); } catch (e) { toast.error((e as Error).message); }
  };
  const genPassword = () => {
    const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
    const arr = new Uint32Array(14); crypto.getRandomValues(arr);
    return Array.from(arr, (n) => chars[n % chars.length]).join("") + "7a";
  };

  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-6">
      <PageHeader icon={Users} title="Team Management" description="Manage who can use BUI and what they can do."
        actions={<Button onClick={() => { setForm({ email: "", full_name: "", role: "team_member", password: genPassword() }); setCreating(true); }}><UserPlus />Add member</Button>} />
      <div className="mb-4 grid gap-3 md:grid-cols-3">
        {[["Super Admin", "Full access, administrators and system configuration."], ["Admin", "Products, documents, FAQs, research approval and team members."], ["Team Member", "Ask questions, voice assistant, view approved information."]].map(([t, d]) => (
          <Card key={t} className="p-4"><p className="text-sm font-medium">{t}</p><p className="mt-1 text-xs text-muted-foreground">{d}</p></Card>
        ))}
      </div>
      <Card className="p-4">
        <div className="mb-3 grid gap-2 sm:grid-cols-[1fr_200px]">
          <div className="relative"><Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" /><Input className="pl-8" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name or e-mail" aria-label="Search users" /></div>
          <Select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Role"><option value="">All roles</option><option value="super_admin">Super Admin</option><option value="admin">Admin</option><option value="team_member">Team Member</option></Select>
        </div>
        {error && <ErrorBox message={error} onRetry={reload} />}
        {loading && !data && <Skeleton className="h-40" />}
        {data && (
          <Table>
            <thead><tr><Th>Member</Th><Th>Role</Th><Th>Active</Th><Th className="hidden md:table-cell">Last sign-in</Th><Th /></tr></thead>
            <tbody>{data.items.map((u) => (
              <tr key={u.id}>
                <Td><p className="font-medium">{u.full_name}{u.id === me?.id && <Badge className="ml-2" variant="secondary">you</Badge>}</p><p className="text-xs text-muted-foreground">{u.email}</p></Td>
                <Td>{canManage(u) ? (
                  <Select className="h-8 w-36 text-xs" value={u.role} onChange={(e) => update(u, { role: e.target.value as User["role"] })} aria-label="Role">
                    <option value="team_member">Team Member</option>{can("super_admin") && <><option value="admin">Admin</option><option value="super_admin">Super Admin</option></>}
                  </Select>) : <Badge variant="secondary">{ROLE_LABEL[u.role]}</Badge>}</Td>
                <Td><Switch checked={u.is_active} disabled={!canManage(u)} onChange={(v) => update(u, { is_active: v })} label="Active" /></Td>
                <Td className="hidden md:table-cell text-xs text-muted-foreground">{u.last_login_at ? timeAgo(u.last_login_at) : "never"}</Td>
                <Td className="text-right whitespace-nowrap">{canManage(u) && <>
                  <Button size="icon-sm" variant="ghost" onClick={() => reset(u)} title="Generate password reset link" aria-label="Reset password"><KeyRound /></Button>
                  <Button size="icon-sm" variant="ghost" onClick={() => remove(u)} title="Delete" aria-label="Delete user"><Trash2 className="text-destructive" /></Button>
                </>}</Td>
              </tr>
            ))}</tbody>
          </Table>
        )}
        {data && <Pagination page={page} pageSize={25} total={data.total} onChange={setPage} />}
      </Card>

      <Dialog open={creating} onClose={() => setCreating(false)} title="Add team member" description="Create an account and share the temporary password securely. They can change it in Settings."
        footer={<><Button variant="outline" onClick={() => setCreating(false)}>Cancel</Button><Button onClick={create} loading={busy}>Create account</Button></>}>
        <div className="grid gap-4">
          <Field label="Full name"><Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
          <Field label="Work e-mail"><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Role"><Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}><option value="team_member">Team Member</option>{can("super_admin") && <><option value="admin">Admin</option><option value="super_admin">Super Admin</option></>}</Select></Field>
          <Field label="Temporary password" hint="At least 10 characters, mixed case and a number."><div className="flex gap-2"><Input value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="font-mono" />
            <Button type="button" variant="outline" size="icon" onClick={() => navigator.clipboard.writeText(form.password)} aria-label="Copy password"><Copy /></Button></div></Field>
        </div>
      </Dialog>
      <Dialog open={!!resetLink} onClose={() => setResetLink(null)} title="Password reset link" description="Valid for 60 minutes and can be used once. Send it to the user through a trusted channel.">
        <div className="flex gap-2"><Input readOnly value={resetLink || ""} className="font-mono text-xs" /><Button variant="outline" onClick={() => { navigator.clipboard.writeText(resetLink || ""); toast.success("Copied"); }}><Copy />Copy</Button></div>
      </Dialog>
    </div>
  );
}
