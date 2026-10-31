"use client";
import * as React from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { FileText, Upload, Search, FileSpreadsheet, FileType, File as FileIcon } from "lucide-react";
import type { KnowledgeDocument, Page } from "@/types";
import { qs } from "@/services/api";
import { useApi, useDebounced } from "@/hooks/use-api";
import { useAuth } from "@/components/providers";
import { usePublicSettings } from "@/hooks/use-public-settings";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { EmptyState, ErrorBox, PageHeader, Pagination, Skeleton, Table, Td, Th } from "@/components/ui/misc";
import { DocumentDetailDialog, UploadDialog, useCategories } from "@/components/documents/document-dialogs";
import { formatBytes, label, timeAgo } from "@/lib/utils";

const iconFor = (name?: string | null) => (/\.(xlsx|csv)$/i.test(name || "") ? FileSpreadsheet : /\.pdf$/i.test(name || "") ? FileType : name ? FileIcon : FileText);

function DocumentsInner() {
  const { can } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const settings = usePublicSettings();
  const categories = useCategories();
  const [q, setQ] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [sourceType, setSourceType] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [upload, setUpload] = React.useState(false);
  const dq = useDebounced(q);
  React.useEffect(() => setPage(1), [dq, category, status, sourceType]);
  const { data, error, loading, reload } = useApi<Page<KnowledgeDocument>>(`/documents${qs({ q: dq, category, status, source_type: sourceType, page, page_size: 20 })}`);
  const openId = params.get("open") ? Number(params.get("open")) : null;
  const setOpen = (id: number | null) => router.replace(id ? `/documents?open=${id}` : "/documents", { scroll: false });

  React.useEffect(() => {
    if (!data?.items.some((d) => ["pending", "processing"].includes(d.processing_status))) return;
    const t = setTimeout(reload, 2000);
    return () => clearTimeout(t);
  }, [data, reload]);

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-6">
      <PageHeader icon={FileText} title="Document Management" description="Upload manuals, guides, spreadsheets and policies. BUI extracts, chunks and indexes them automatically."
        actions={can("admin") && <Button onClick={() => setUpload(true)}><Upload />Upload documents</Button>} />
      <Card className="p-4">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative"><Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" /><Input className="pl-8" placeholder="Search title or content…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search documents" /></div>
          <Select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category"><option value="">All categories</option>{categories.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</Select>
          <Select value={sourceType} onChange={(e) => setSourceType(e.target.value)} aria-label="Source"><option value="">All sources</option><option value="file">Uploaded files</option><option value="manual">Manual entries</option><option value="url">From URL</option></Select>
          {can("admin") && <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status"><option value="">Any status</option><option value="published">Published</option><option value="draft">Draft</option><option value="archived">Archived</option></Select>}
        </div>
        <div className="mt-4">
          {error && <ErrorBox message={error} onRetry={reload} />}
          {loading && !data && <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}</div>}
          {data?.items.length === 0 && <EmptyState icon={FileText} title="No documents" description="Upload PDFs, Word, Excel, CSV or text files." action={can("admin") && <Button onClick={() => setUpload(true)}><Upload />Upload</Button>} />}
          {!!data?.items.length && (
            <Table>
              <thead><tr><Th>Document</Th><Th className="hidden md:table-cell">Category</Th><Th>Status</Th><Th className="hidden lg:table-cell">Size</Th><Th className="hidden sm:table-cell">Updated</Th></tr></thead>
              <tbody>{data.items.map((d) => {
                const Icon = iconFor(d.original_filename);
                return (
                  <tr key={d.id} className="cursor-pointer hover:bg-secondary/50" onClick={() => setOpen(d.id)}>
                    <Td><div className="flex items-center gap-3"><Icon className="size-5 shrink-0 text-primary" /><div className="min-w-0"><p className="truncate font-medium">{d.title}</p>
                      <p className="truncate text-xs text-muted-foreground">{d.original_filename || "Manual entry"}{d.product_name && ` · ${d.product_name}`} · v{d.current_version}</p></div></div></Td>
                    <Td className="hidden md:table-cell"><Badge variant="secondary">{label(d.category)}</Badge></Td>
                    <Td><div className="flex flex-wrap gap-1"><StatusBadge status={d.processing_status === "ready" ? d.status : d.processing_status} />{d.visibility === "restricted" && <StatusBadge status="restricted" />}</div></Td>
                    <Td className="hidden lg:table-cell text-xs text-muted-foreground">{formatBytes(d.file_size)}</Td>
                    <Td className="hidden sm:table-cell whitespace-nowrap text-xs text-muted-foreground">{timeAgo(d.updated_at)}</Td>
                  </tr>
                );
              })}</tbody>
            </Table>
          )}
          {data && <Pagination page={page} pageSize={20} total={data.total} onChange={setPage} />}
        </div>
      </Card>
      <UploadDialog open={upload} onClose={() => setUpload(false)} onUploaded={reload} maxMb={settings?.max_upload_mb || 25} />
      <DocumentDetailDialog id={openId} onClose={() => setOpen(null)} onChanged={reload} />
    </div>
  );
}

export default function DocumentsPage() { return <React.Suspense><DocumentsInner /></React.Suspense>; }
