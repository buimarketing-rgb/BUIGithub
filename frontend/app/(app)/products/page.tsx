"use client";
import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Package, Plus, Search } from "lucide-react";
import type { Category, Page, ProductListItem } from "@/types";
import { qs } from "@/services/api";
import { useApi, useDebounced } from "@/hooks/use-api";
import { useAuth } from "@/components/providers";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/badge";
import { EmptyState, ErrorBox, PageHeader, Pagination, Skeleton, Table, Td, Th } from "@/components/ui/misc";
import { ProductEditor } from "@/components/products/product-editor";
import { timeAgo } from "@/lib/utils";

export default function ProductsPage() {
  const { can } = useAuth();
  const router = useRouter();
  const [q, setQ] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [brand, setBrand] = React.useState("");
  const [sort, setSort] = React.useState("updated");
  const [page, setPage] = React.useState(1);
  const [editor, setEditor] = React.useState(false);
  const dq = useDebounced(q);
  React.useEffect(() => setPage(1), [dq, category, status, brand, sort]);
  const { data, error, loading, reload } = useApi<Page<ProductListItem>>(`/products${qs({ q: dq, category_id: category, status, brand, sort, page, page_size: 20 })}`);
  const { data: categories } = useApi<Category[]>("/categories");
  const { data: brands } = useApi<string[]>("/products/brands");

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-6">
      <PageHeader icon={Package} title="Product Database" description="Structured, versioned product information that BUI uses to answer questions."
        actions={can("admin") && <Button onClick={() => setEditor(true)}><Plus />Add product</Button>} />
      <Card className="p-4">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <div className="relative lg:col-span-2">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input className="pl-8" placeholder="Search name, model, brand…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search products" />
          </div>
          <Select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
            <option value="">All categories</option>{categories?.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.product_count})</option>)}
          </Select>
          <Select value={brand} onChange={(e) => setBrand(e.target.value)} aria-label="Brand">
            <option value="">All brands</option>{brands?.map((b) => <option key={b} value={b}>{b}</option>)}
          </Select>
          <div className="flex gap-2">
            {can("admin") && (
              <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
                <option value="">Active</option><option value="verified">Verified</option><option value="needs_review">Needs review</option><option value="draft">Draft</option><option value="archived">Archived</option>
              </Select>
            )}
            <Select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
              <option value="updated">Recently updated</option><option value="name">Name</option><option value="created">Newest</option>
            </Select>
          </div>
        </div>
        <div className="mt-4">
          {error && <ErrorBox message={error} onRetry={reload} />}
          {loading && !data && <div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>}
          {data && data.items.length === 0 && (
            <EmptyState icon={Package} title="No products found" description={dq || category || brand ? "Try different filters." : "Add your first product to start building BUI's knowledge."}
              action={can("admin") && <Button onClick={() => setEditor(true)}><Plus />Add product</Button>} />
          )}
          {data && data.items.length > 0 && (
            <Table>
              <thead><tr><Th>Product</Th><Th>Model</Th><Th className="hidden md:table-cell">Brand</Th><Th className="hidden md:table-cell">Category</Th><Th>Status</Th><Th className="hidden sm:table-cell">Updated</Th></tr></thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.id} className="cursor-pointer hover:bg-secondary/50" onClick={() => router.push(`/products/${p.id}`)}>
                    <Td><Link href={`/products/${p.id}`} className="font-medium hover:text-primary">{p.name}</Link><p className="text-xs text-muted-foreground line-clamp-1 max-w-sm">{p.description}</p></Td>
                    <Td className="font-mono text-xs">{p.model_number || "—"}</Td>
                    <Td className="hidden md:table-cell">{p.brand || "—"}</Td>
                    <Td className="hidden md:table-cell">{p.category_name || "—"}</Td>
                    <Td><StatusBadge status={p.status} /></Td>
                    <Td className="hidden sm:table-cell text-xs text-muted-foreground whitespace-nowrap">v{p.version} · {timeAgo(p.updated_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
          {data && <Pagination page={page} pageSize={20} total={data.total} onChange={setPage} />}
        </div>
      </Card>
      <ProductEditor open={editor} onClose={() => setEditor(false)} onSaved={(p) => router.push(`/products/${p.id}`)} />
    </div>
  );
}
