"use client";
import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Pencil, Archive, Trash2, MessageSquareText, Globe, ImagePlus, X, History, RotateCcw, FileText, HelpCircle, ExternalLink } from "lucide-react";
import type { FAQ, KnowledgeDocument, Page, Product, ProductVersion } from "@/types";
import { api, apiFetch } from "@/services/api";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/components/providers";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { EmptyState, ErrorBox, Skeleton, Tabs, Table, Td, Th } from "@/components/ui/misc";
import { useConfirm } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { ProductEditor } from "@/components/products/product-editor";
import { formatDate, label } from "@/lib/utils";

type Tab = "overview" | "specs" | "support" | "documents" | "faqs" | "versions";

function TextBlock({ title, text }: { title: string; text: string | null }) {
  if (!text) return null;
  return <div><h3 className="mb-1.5 text-sm font-semibold">{title}</h3><p className="whitespace-pre-line text-sm leading-relaxed text-muted-foreground">{text}</p></div>;
}
function ListBlock({ title, items }: { title: string; items: string[] }) {
  if (!items?.length) return null;
  return <div><h3 className="mb-1.5 text-sm font-semibold">{title}</h3><ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">{items.map((i) => <li key={i}>{i}</li>)}</ul></div>;
}

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { can } = useAuth();
  const confirm = useConfirm();
  const toast = useToast();
  const { data: p, error, reload, setData } = useApi<Product>(`/products/${id}`);
  const [tab, setTab] = React.useState<Tab>("overview");
  const [editing, setEditing] = React.useState(false);
  const docs = useApi<Page<KnowledgeDocument>>(tab === "documents" ? `/documents?product_id=${id}&page_size=50` : null);
  const faqs = useApi<Page<FAQ>>(tab === "faqs" ? `/faqs?product_id=${id}&page_size=50` : null);
  const versions = useApi<ProductVersion[]>(tab === "versions" && can("admin") ? `/products/${id}/versions` : null);
  const fileRef = React.useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = React.useState(false);

  if (error) return <div className="p-6"><ErrorBox message={error} onRetry={reload} /></div>;
  if (!p) return <div className="mx-auto max-w-6xl space-y-4 p-6"><Skeleton className="h-10 w-72" /><Skeleton className="h-64" /></div>;

  const archive = async () => {
    if (!(await confirm({ title: `Archive ${p.name}?`, description: "Archived products are removed from BUI's answers but kept for history.", confirmLabel: "Archive" }))) return;
    setData(await api<Product>(`/products/${p.id}/archive`, { method: "POST" }));
    toast.success("Product archived");
  };
  const remove = async () => {
    if (!(await confirm({ title: `Delete ${p.name}?`, description: "This permanently deletes the product, its images and version history. This cannot be undone.", confirmLabel: "Delete", destructive: true }))) return;
    await api(`/products/${p.id}`, { method: "DELETE" });
    toast.success("Product deleted");
    router.push("/products");
  };
  const research = async () => {
    try {
      const job = await api<{ id: number }>("/research/jobs", { method: "POST", json: { product_id: p.id } });
      toast.success("Research started", "Findings will wait for your review.");
      router.push(`/research/${job.id}`);
    } catch (e) { toast.error("Research failed to start", (e as Error).message); }
  };
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const fd = new FormData(); fd.append("file", file);
        await apiFetch(`/products/${p.id}/images`, { method: "POST", body: fd });
      }
      toast.success("Image uploaded"); reload();
    } catch (e) { toast.error("Upload failed", (e as Error).message); } finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };
  const deleteImage = async (imageId: number) => {
    if (!(await confirm({ title: "Delete image?", confirmLabel: "Delete", destructive: true }))) return;
    await api(`/products/${p.id}/images/${imageId}`, { method: "DELETE" }); reload();
  };
  const restore = async (v: number) => {
    if (!(await confirm({ title: `Restore version ${v}?`, description: "A new version will be created with the content of the selected version." }))) return;
    setData(await api<Product>(`/products/${p.id}/versions/${v}/restore`, { method: "POST" }));
    versions.reload(); toast.success(`Restored version ${v}`);
  };

  const specs = Object.entries(p.specifications || {});
  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-6">
      <Link href="/products" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" />Products</Link>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">{p.name}</h1>
            <StatusBadge status={p.status} />
            <Badge variant="outline">v{p.version}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {[p.brand, p.model_number && `Model ${p.model_number}`, p.category_name].filter(Boolean).join(" · ")} · Updated {formatDate(p.updated_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href={`/assistant?q=${encodeURIComponent(`Tell me about ${p.name}`)}`}><Button variant="outline"><MessageSquareText />Ask BUI</Button></Link>
          {can("admin") && <>
            <Button variant="outline" onClick={research}><Globe />Research online</Button>
            <Button onClick={() => setEditing(true)}><Pencil />Edit</Button>
            {p.status !== "archived" && <Button variant="ghost" size="icon" onClick={archive} title="Archive" aria-label="Archive"><Archive /></Button>}
            <Button variant="ghost" size="icon" onClick={remove} title="Delete" aria-label="Delete"><Trash2 className="text-destructive" /></Button>
          </>}
        </div>
      </div>

      <Tabs className="mt-6" value={tab} onChange={setTab} tabs={[
        { value: "overview", label: "Overview" }, { value: "specs", label: "Specifications", count: specs.length }, { value: "support", label: "Warranty & support" },
        { value: "documents", label: "Documents", count: p.document_count }, { value: "faqs", label: "FAQs", count: p.faq_count },
        ...(can("admin") ? [{ value: "versions" as Tab, label: "Version history", icon: History }] : []),
      ]} />

      <div className="mt-4">
        {tab === "overview" && (
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2"><CardContent className="space-y-5 pt-5">
              <TextBlock title="Description" text={p.description} />
              <ListBlock title="Features & advantages" items={p.features} />
              <ListBlock title="Applications" items={p.applications} />
              <ListBlock title="Compatibility" items={p.compatibility} />
              <ListBlock title="Accessories" items={p.accessories} />
              {p.source_urls.length > 0 && (
                <div><h3 className="mb-1.5 text-sm font-semibold">Source URLs</h3>
                  <ul className="space-y-1 text-sm">{p.source_urls.map((u) => <li key={u}><a href={u} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline break-all">{u}<ExternalLink className="size-3" /></a></li>)}</ul>
                </div>
              )}
              {p.tags.length > 0 && <div className="flex flex-wrap gap-1.5">{p.tags.map((t) => <Badge key={t} variant="secondary">#{t}</Badge>)}</div>}
            </CardContent></Card>
            <Card>
              <CardHeader className="flex-row items-center justify-between"><CardTitle>Images</CardTitle>
                {can("admin") && <><input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" multiple hidden onChange={(e) => upload(e.target.files)} />
                  <Button size="sm" variant="outline" onClick={() => fileRef.current?.click()} loading={uploading}><ImagePlus />Upload</Button></>}
              </CardHeader>
              <CardContent>
                {p.images.length === 0 ? <p className="text-sm text-muted-foreground">No images yet.</p> : (
                  <div className="grid grid-cols-2 gap-2">
                    {p.images.map((img) => (
                      <div key={img.id} className="group relative overflow-hidden rounded-lg border bg-muted">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={img.url} alt={img.caption || img.original_name} className="aspect-square w-full object-cover" />
                        {can("admin") && <button onClick={() => deleteImage(img.id)} aria-label="Delete image" className="absolute right-1 top-1 hidden rounded-full bg-black/60 p-1 text-white group-hover:block"><X className="size-3" /></button>}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
        {tab === "specs" && (
          <Card>{specs.length === 0 ? <EmptyState icon={FileText} title="No specifications" description="Add verified specifications so BUI can answer technical questions." /> : (
            <Table><tbody>{specs.map(([k, v]) => <tr key={k}><Td className="w-1/3 bg-muted/40 font-medium">{k}</Td><Td>{v}</Td></tr>)}</tbody></Table>
          )}</Card>
        )}
        {tab === "support" && (
          <Card><CardContent className="space-y-5 pt-5">
            <TextBlock title="Warranty" text={p.warranty} />
            <TextBlock title="Installation instructions" text={p.installation} />
            <TextBlock title="Maintenance" text={p.maintenance} />
            <TextBlock title="Troubleshooting" text={p.troubleshooting} />
            <TextBlock title="Pricing" text={p.pricing} />
            {!p.warranty && !p.installation && !p.maintenance && !p.troubleshooting && !p.pricing && <p className="text-sm text-muted-foreground">No support information yet.</p>}
          </CardContent></Card>
        )}
        {tab === "documents" && (
          <Card className="p-2">{docs.data?.items.length === 0 ? <EmptyState icon={FileText} title="No linked documents" description="Link manuals and guides to this product in Document Management." /> :
            docs.data?.items.map((d) => (
              <Link key={d.id} href={`/documents?open=${d.id}`} className="flex items-center gap-3 rounded-lg p-3 hover:bg-secondary">
                <FileText className="size-4 text-primary" /><span className="flex-1 text-sm font-medium">{d.title}</span>
                <Badge variant="secondary">{label(d.category)}</Badge><StatusBadge status={d.status} />
              </Link>
            ))}</Card>
        )}
        {tab === "faqs" && (
          <Card className="divide-y">{faqs.data?.items.length === 0 ? <EmptyState icon={HelpCircle} title="No FAQs for this product" /> :
            faqs.data?.items.map((f) => <div key={f.id} className="p-4"><p className="font-medium text-sm">{f.question}</p><p className="mt-1 text-sm text-muted-foreground whitespace-pre-line">{f.answer}</p></div>)}</Card>
        )}
        {tab === "versions" && (
          <Card>
            <Table>
              <thead><tr><Th>Version</Th><Th>Change</Th><Th>Date</Th><Th /></tr></thead>
              <tbody>{versions.data?.map((v) => (
                <tr key={v.id}><Td className="font-medium">v{v.version}{v.version === p.version && <Badge className="ml-2">current</Badge>}</Td>
                  <Td className="text-muted-foreground">{v.change_note || "—"}</Td><Td className="whitespace-nowrap text-xs">{formatDate(v.created_at, true)}</Td>
                  <Td className="text-right">{v.version !== p.version && <Button size="sm" variant="ghost" onClick={() => restore(v.version)}><RotateCcw />Restore</Button>}</Td></tr>
              ))}</tbody>
            </Table>
          </Card>
        )}
      </div>
      <ProductEditor open={editing} onClose={() => setEditing(false)} product={p} onSaved={(np) => setData(np)} />
    </div>
  );
}
