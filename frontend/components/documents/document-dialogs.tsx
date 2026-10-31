"use client";
import * as React from "react";
import { Download, RotateCcw, Trash2, Upload, RefreshCw, Pencil, FileText } from "lucide-react";
import type { DocumentDetail, ProductListItem, Page } from "@/types";
import { api, apiFetch } from "@/services/api";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/components/providers";
import { Dialog, useConfirm } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Spinner, Tabs } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { formatBytes, formatDate, label } from "@/lib/utils";

export function useCategories() {
  return useApi<{ value: string; label: string }[]>("/documents/categories").data || [];
}
export function useProductOptions(enabled = true) {
  return useApi<Page<ProductListItem>>(enabled ? "/products?page_size=100&sort=name" : null).data?.items || [];
}

/* -------- create / edit a manual knowledge entry -------- */
export function EntryEditor({ open, onClose, doc, onSaved, defaultCategory }: { open: boolean; onClose: () => void; doc?: DocumentDetail | null; onSaved: (d: DocumentDetail) => void; defaultCategory?: string }) {
  const toast = useToast();
  const categories = useCategories();
  const products = useProductOptions(open);
  const [f, setF] = React.useState({ title: "", category: "other", content: "", product_id: "", visibility: "internal", status: "published", tags: "", source_url: "", change_note: "" });
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => {
    if (!open) return;
    setF(doc ? { title: doc.title, category: doc.category, content: doc.content || "", product_id: doc.product_id ? String(doc.product_id) : "", visibility: doc.visibility, status: doc.status, tags: doc.tags.join(", "), source_url: doc.source_url || "", change_note: "" }
      : { title: "", category: defaultCategory || "company_information", content: "", product_id: "", visibility: "internal", status: "published", tags: "", source_url: "", change_note: "" });
  }, [open, doc, defaultCategory]);
  const save = async () => {
    if (!f.title.trim() || !f.content.trim()) { toast.error("Title and content are required"); return; }
    setBusy(true);
    const tags = f.tags.split(",").map((t) => t.trim()).filter(Boolean);
    try {
      const saved = doc
        ? await api<DocumentDetail>(`/documents/${doc.id}`, { method: "PATCH", json: { title: f.title, category: f.category, content: f.content, visibility: f.visibility, status: f.status, tags, source_url: f.source_url || null, change_note: f.change_note || null, product_id: f.product_id ? Number(f.product_id) : null, clear_product: !f.product_id } })
        : await api<DocumentDetail>("/documents", { method: "POST", json: { title: f.title, category: f.category, content: f.content, visibility: f.visibility, status: f.status, tags, source_url: f.source_url || null, product_id: f.product_id ? Number(f.product_id) : null } });
      toast.success(doc ? "Knowledge updated" : "Knowledge added", "BUI's index was updated automatically.");
      onSaved(saved); onClose();
    } catch (e) { toast.error("Could not save", (e as Error).message); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onClose={onClose} size="lg" title={doc ? "Edit knowledge" : "Add knowledge"} description="Give BUI new company information. It becomes searchable immediately."
      footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={save} loading={busy}>Save</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Title *" className="sm:col-span-2"><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. Customer support hours" /></Field>
        <Field label="Category"><Select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{categories.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</Select></Field>
        <Field label="Related product"><Select value={f.product_id} onChange={(e) => setF({ ...f, product_id: e.target.value })}><option value="">— None —</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
        <Field label="Content *" className="sm:col-span-2" hint="Markdown supported. Use headings (## Warranty) to help BUI cite the right section.">
          <Textarea rows={10} value={f.content} onChange={(e) => setF({ ...f, content: e.target.value })} />
        </Field>
        <Field label="Visibility" hint="Restricted = administrators only"><Select value={f.visibility} onChange={(e) => setF({ ...f, visibility: e.target.value })}><option value="internal">All team members</option><option value="restricted">Restricted (admins)</option></Select></Field>
        <Field label="Status"><Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="published">Published</option><option value="draft">Draft</option><option value="archived">Archived</option></Select></Field>
        <Field label="Tags" hint="Comma separated"><Input value={f.tags} onChange={(e) => setF({ ...f, tags: e.target.value })} /></Field>
        <Field label="Source URL"><Input value={f.source_url} onChange={(e) => setF({ ...f, source_url: e.target.value })} placeholder="https://…" /></Field>
        {doc && <Field label="Change note" className="sm:col-span-2"><Input value={f.change_note} onChange={(e) => setF({ ...f, change_note: e.target.value })} /></Field>}
      </div>
    </Dialog>
  );
}

/* -------- upload files -------- */
export function UploadDialog({ open, onClose, onUploaded, maxMb }: { open: boolean; onClose: () => void; onUploaded: () => void; maxMb: number }) {
  const toast = useToast();
  const categories = useCategories();
  const products = useProductOptions(open);
  const [files, setFiles] = React.useState<File[]>([]);
  const [meta, setMeta] = React.useState({ category: "user_manuals", product_id: "", visibility: "internal", status: "published", tags: "" });
  const [busy, setBusy] = React.useState(false);
  const [drag, setDrag] = React.useState(false);
  const accept = ".pdf,.docx,.xlsx,.csv,.txt,.md";
  React.useEffect(() => { if (open) setFiles([]); }, [open]);
  const add = (list: FileList | null) => {
    if (!list) return;
    const ok = Array.from(list).filter((f) => {
      if (f.size > maxMb * 1024 * 1024) { toast.error(`${f.name} is larger than ${maxMb} MB`); return false; }
      if (!accept.split(",").some((ext) => f.name.toLowerCase().endsWith(ext))) { toast.error(`${f.name}: unsupported file type`); return false; }
      return true;
    });
    setFiles((x) => [...x, ...ok]);
  };
  const upload = async () => {
    setBusy(true);
    let okCount = 0;
    for (const file of files) {
      const fd = new FormData();
      fd.append("file", file);
      Object.entries(meta).forEach(([k, v]) => v && fd.append(k, v));
      try { await apiFetch("/documents/upload", { method: "POST", body: fd }); okCount++; }
      catch (e) { toast.error(`${file.name} failed`, (e as Error).message); }
    }
    setBusy(false);
    if (okCount) { toast.success(`${okCount} file${okCount > 1 ? "s" : ""} uploaded`, "Processing and indexing runs in the background."); onUploaded(); onClose(); }
  };
  return (
    <Dialog open={open} onClose={onClose} size="lg" title="Upload documents" description={`PDF, Word (.docx), Excel (.xlsx), CSV, TXT or Markdown · max ${maxMb} MB each`}
      footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={upload} loading={busy} disabled={!files.length}><Upload />Upload {files.length || ""}</Button></>}>
      <label onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-colors ${drag ? "border-primary bg-accent" : "hover:bg-secondary/50"}`}>
        <Upload className="size-8 text-muted-foreground" />
        <p className="mt-2 text-sm font-medium">Drop files here or click to browse</p>
        <input type="file" multiple accept={accept} hidden onChange={(e) => add(e.target.files)} />
      </label>
      {files.length > 0 && (
        <ul className="mt-3 space-y-1">{files.map((f, i) => (
          <li key={i} className="flex items-center gap-2 rounded-md bg-muted px-3 py-1.5 text-sm"><FileText className="size-4" /><span className="flex-1 truncate">{f.name}</span><span className="text-xs text-muted-foreground">{formatBytes(f.size)}</span>
            <button onClick={() => setFiles(files.filter((_, j) => j !== i))} aria-label="Remove" className="text-muted-foreground hover:text-foreground">×</button></li>
        ))}</ul>
      )}
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Field label="Category"><Select value={meta.category} onChange={(e) => setMeta({ ...meta, category: e.target.value })}>{categories.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</Select></Field>
        <Field label="Related product"><Select value={meta.product_id} onChange={(e) => setMeta({ ...meta, product_id: e.target.value })}><option value="">— None —</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
        <Field label="Visibility"><Select value={meta.visibility} onChange={(e) => setMeta({ ...meta, visibility: e.target.value })}><option value="internal">All team members</option><option value="restricted">Restricted (admins)</option></Select></Field>
        <Field label="Status"><Select value={meta.status} onChange={(e) => setMeta({ ...meta, status: e.target.value })}><option value="published">Published</option><option value="draft">Draft</option></Select></Field>
        <Field label="Tags" className="sm:col-span-2"><Input value={meta.tags} onChange={(e) => setMeta({ ...meta, tags: e.target.value })} placeholder="comma, separated" /></Field>
      </div>
    </Dialog>
  );
}

/* -------- detail / versions -------- */
export function DocumentDetailDialog({ id, onClose, onChanged }: { id: number | null; onClose: () => void; onChanged: () => void }) {
  const { can } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const { data: doc, reload, setData } = useApi<DocumentDetail>(id ? `/documents/${id}` : null, [id]);
  const [tab, setTab] = React.useState<"content" | "versions">("content");
  const [editing, setEditing] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);
  React.useEffect(() => { setTab("content"); }, [id]);
  React.useEffect(() => {
    if (!doc || !["pending", "processing"].includes(doc.processing_status)) return;
    const t = setTimeout(reload, 1500);
    return () => clearTimeout(t);
  }, [doc, reload]);

  if (!id) return null;
  const newVersion = async (file?: File) => {
    if (!file || !doc) return;
    const fd = new FormData(); fd.append("file", file);
    try { await apiFetch(`/documents/${doc.id}/versions`, { method: "POST", body: fd }); toast.success("New version uploaded"); reload(); onChanged(); }
    catch (e) { toast.error("Upload failed", (e as Error).message); }
  };
  const restore = async (v: number) => {
    if (!doc || !(await confirm({ title: `Restore version ${v}?`, description: "This creates a new current version from the selected one." }))) return;
    setData(await api<DocumentDetail>(`/documents/${doc.id}/versions/${v}/restore`, { method: "POST" })); onChanged();
  };
  const remove = async () => {
    if (!doc || !(await confirm({ title: `Delete “${doc.title}”?`, description: "The document, all its versions and its index entries will be removed.", confirmLabel: "Delete", destructive: true }))) return;
    await api(`/documents/${doc.id}`, { method: "DELETE" }); toast.success("Document deleted"); onChanged(); onClose();
  };
  const reprocess = async () => { if (doc) { setData(await api<DocumentDetail>(`/documents/${doc.id}/reprocess`, { method: "POST" })); } };

  return (
    <>
      <Dialog open={!!id} onClose={onClose} size="xl" title={doc?.title || "Document"} description={doc ? `${label(doc.category)} · v${doc.current_version} · updated ${formatDate(doc.updated_at, true)}` : undefined}
        footer={doc && can("admin") ? <>
          <Button variant="ghost" className="mr-auto text-destructive" onClick={remove}><Trash2 />Delete</Button>
          {doc.processing_status === "failed" && <Button variant="outline" onClick={reprocess}><RefreshCw />Retry processing</Button>}
          <input ref={fileRef} type="file" hidden accept=".pdf,.docx,.xlsx,.csv,.txt,.md" onChange={(e) => newVersion(e.target.files?.[0])} />
          <Button variant="outline" onClick={() => fileRef.current?.click()}><Upload />Upload new version</Button>
          <Button onClick={() => setEditing(true)}><Pencil />Edit</Button>
        </> : undefined}>
        {!doc ? <Spinner /> : (
          <>
            <div className="mb-4 flex flex-wrap gap-2">
              <StatusBadge status={doc.status} /><StatusBadge status={doc.processing_status} /><StatusBadge status={doc.visibility} />
              {doc.product_name && <Badge variant="secondary">{doc.product_name}</Badge>}
              {doc.original_filename && <Badge variant="outline">{doc.original_filename} · {formatBytes(doc.file_size)}</Badge>}
              <Badge variant="outline">{doc.chunk_count} indexed chunks</Badge>
              {doc.download_url && <a href={doc.download_url} className="inline-flex items-center gap-1 text-xs text-primary hover:underline"><Download className="size-3" />Download</a>}
            </div>
            {doc.processing_error && <p className="mb-3 rounded-md bg-destructive/10 p-3 text-sm text-destructive">{doc.processing_error}</p>}
            <Tabs value={tab} onChange={setTab} tabs={[{ value: "content", label: "Extracted content" }, { value: "versions", label: "Versions", count: doc.versions.length }]} />
            {tab === "content" ? (
              <pre className="mt-3 max-h-[50vh] overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-4 text-xs leading-relaxed scrollbar-thin">{doc.content || (["pending", "processing"].includes(doc.processing_status) ? "Processing…" : "No text content.")}</pre>
            ) : (
              <ul className="mt-3 divide-y rounded-lg border">{doc.versions.map((v) => (
                <li key={v.id} className="flex flex-wrap items-center gap-3 p-3 text-sm">
                  <span className="font-medium">v{v.version}</span>{v.version === doc.current_version && <Badge>current</Badge>}
                  <span className="flex-1 text-muted-foreground">{v.change_note || "—"}{v.original_filename && ` · ${v.original_filename}`}</span>
                  <span className="text-xs text-muted-foreground">{formatDate(v.created_at, true)}</span>
                  {v.download_url && <a href={v.download_url} aria-label="Download version"><Download className="size-4 text-primary" /></a>}
                  {can("admin") && v.version !== doc.current_version && <Button size="sm" variant="ghost" onClick={() => restore(v.version)}><RotateCcw />Restore</Button>}
                </li>
              ))}</ul>
            )}
          </>
        )}
      </Dialog>
      <EntryEditor open={editing} onClose={() => setEditing(false)} doc={doc} onSaved={(d) => { setData(d); onChanged(); }} />
    </>
  );
}
