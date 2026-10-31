"use client";
import * as React from "react";
import { Plus, Trash2 } from "lucide-react";
import type { Category, Product, ProductFields } from "@/types";
import { api } from "@/services/api";
import { useApi } from "@/hooks/use-api";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Select, Field } from "@/components/ui/input";
import { ListEditor, Tabs } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";

const EMPTY: ProductFields = {
  name: "", brand: "", model_number: "", category_id: null, description: "", specifications: {}, features: [], applications: [],
  compatibility: [], accessories: [], pricing: "", warranty: "", installation: "", maintenance: "", troubleshooting: "", source_urls: [], tags: [], status: "verified",
};

type Tab = "basic" | "specs" | "lists" | "support" | "meta";

export function ProductEditor({ open, onClose, product, onSaved }: { open: boolean; onClose: () => void; product?: Product | null; onSaved: (p: Product) => void }) {
  const toast = useToast();
  const { data: categories, reload: reloadCats } = useApi<Category[]>(open ? "/categories" : null);
  const [f, setF] = React.useState<ProductFields>(EMPTY);
  const [specs, setSpecs] = React.useState<[string, string][]>([]);
  const [note, setNote] = React.useState("");
  const [tab, setTab] = React.useState<Tab>("basic");
  const [busy, setBusy] = React.useState(false);
  const [newCat, setNewCat] = React.useState("");

  React.useEffect(() => {
    if (!open) return;
    const base = product ? (Object.fromEntries(Object.keys(EMPTY).map((k) => [k, (product as unknown as Record<string, unknown>)[k] ?? (EMPTY as unknown as Record<string, unknown>)[k]])) as unknown as ProductFields) : EMPTY;
    setF(base);
    setSpecs(Object.entries(base.specifications || {}));
    setNote("");
    setTab("basic");
  }, [open, product]);

  const set = <K extends keyof ProductFields>(k: K, v: ProductFields[K]) => setF((x) => ({ ...x, [k]: v }));
  const save = async () => {
    if (!f.name.trim()) { toast.error("Product name is required"); setTab("basic"); return; }
    setBusy(true);
    try {
      const body = { ...f, specifications: Object.fromEntries(specs.filter(([k]) => k.trim())), change_note: note || undefined };
      const saved = product
        ? await api<Product>(`/products/${product.id}`, { method: "PUT", json: body })
        : await api<Product>("/products", { method: "POST", json: body });
      toast.success(product ? `Saved version ${saved.version}` : "Product created", "The knowledge index was updated automatically.");
      onSaved(saved);
      onClose();
    } catch (e) { toast.error("Could not save product", (e as Error).message); } finally { setBusy(false); }
  };
  const addCategory = async () => {
    if (!newCat.trim()) return;
    try {
      const c = await api<Category>("/categories", { method: "POST", json: { name: newCat } });
      await reloadCats(); set("category_id", c.id); setNewCat("");
    } catch (e) { toast.error((e as Error).message); }
  };

  return (
    <Dialog open={open} onClose={onClose} size="xl" title={product ? `Edit ${product.name}` : "Add product"}
      description="All changes are versioned, audited and re-indexed automatically."
      footer={<>
        <Input className="sm:mr-auto sm:max-w-xs" placeholder="Change note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button onClick={save} loading={busy}>{product ? "Save changes" : "Create product"}</Button>
      </>}>
      <Tabs className="mb-5" value={tab} onChange={setTab} tabs={[
        { value: "basic", label: "Basics" }, { value: "specs", label: "Specifications", count: specs.length }, { value: "lists", label: "Features & more" },
        { value: "support", label: "Warranty & support" }, { value: "meta", label: "Sources & tags" },
      ]} />
      {tab === "basic" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Product name *"><Input value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. AquaFlow 500" /></Field>
          <Field label="Model number"><Input value={f.model_number || ""} onChange={(e) => set("model_number", e.target.value)} placeholder="e.g. AF-500" /></Field>
          <Field label="Brand"><Input value={f.brand || ""} onChange={(e) => set("brand", e.target.value)} /></Field>
          <Field label="Information status" hint="Draft products are hidden from team members and not used for answers.">
            <Select value={f.status} onChange={(e) => set("status", e.target.value as ProductFields["status"])}>
              <option value="verified">Verified</option><option value="needs_review">Needs review</option><option value="draft">Draft</option><option value="archived">Archived</option>
            </Select>
          </Field>
          <Field label="Category">
            <Select value={f.category_id ?? ""} onChange={(e) => set("category_id", e.target.value ? Number(e.target.value) : null)}>
              <option value="">— None —</option>
              {categories?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
          <Field label="New category">
            <div className="flex gap-2"><Input value={newCat} onChange={(e) => setNewCat(e.target.value)} placeholder="Create a category" /><Button type="button" variant="outline" onClick={addCategory}>Add</Button></div>
          </Field>
          <Field label="Description" className="sm:col-span-2"><Textarea rows={4} value={f.description || ""} onChange={(e) => set("description", e.target.value)} /></Field>
        </div>
      )}
      {tab === "specs" && (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">Technical specifications exactly as approved. BUI quotes these verbatim and never estimates missing values.</p>
          {specs.map(([k, v], i) => (
            <div key={i} className="flex gap-2">
              <Input className="w-2/5" placeholder="Name (e.g. Voltage)" value={k} onChange={(e) => setSpecs(specs.map((s, j) => (j === i ? [e.target.value, s[1]] : s)))} />
              <Input className="flex-1" placeholder="Value (e.g. 220-240 V AC)" value={v} onChange={(e) => setSpecs(specs.map((s, j) => (j === i ? [s[0], e.target.value] : s)))} />
              <Button variant="ghost" size="icon" onClick={() => setSpecs(specs.filter((_, j) => j !== i))} aria-label="Remove specification"><Trash2 /></Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={() => setSpecs([...specs, ["", ""]])}><Plus />Add specification</Button>
        </div>
      )}
      {tab === "lists" && (
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Features & advantages"><ListEditor value={f.features} onChange={(v) => set("features", v)} /></Field>
          <Field label="Applications"><ListEditor value={f.applications} onChange={(v) => set("applications", v)} /></Field>
          <Field label="Compatibility"><ListEditor value={f.compatibility} onChange={(v) => set("compatibility", v)} /></Field>
          <Field label="Accessories"><ListEditor value={f.accessories} onChange={(v) => set("accessories", v)} /></Field>
        </div>
      )}
      {tab === "support" && (
        <div className="grid gap-4">
          <Field label="Warranty"><Textarea rows={3} value={f.warranty || ""} onChange={(e) => set("warranty", e.target.value)} /></Field>
          <Field label="Installation instructions"><Textarea rows={5} value={f.installation || ""} onChange={(e) => set("installation", e.target.value)} /></Field>
          <Field label="Maintenance instructions"><Textarea rows={3} value={f.maintenance || ""} onChange={(e) => set("maintenance", e.target.value)} /></Field>
          <Field label="Troubleshooting"><Textarea rows={4} value={f.troubleshooting || ""} onChange={(e) => set("troubleshooting", e.target.value)} /></Field>
          <Field label="Pricing information" hint="Only enter approved pricing."><Textarea rows={2} value={f.pricing || ""} onChange={(e) => set("pricing", e.target.value)} /></Field>
        </div>
      )}
      {tab === "meta" && (
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Source URLs" hint="Official manufacturer pages. Their domains are treated as official during research."><ListEditor value={f.source_urls} onChange={(v) => set("source_urls", v)} placeholder="https://…" /></Field>
          <Field label="Tags & keywords"><ListEditor value={f.tags} onChange={(v) => set("tags", v)} /></Field>
        </div>
      )}
    </Dialog>
  );
}
