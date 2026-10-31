"use client";
import * as React from "react";
import type { FAQ } from "@/types";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Dialog } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { useProductOptions } from "@/components/documents/document-dialogs";

export function FAQEditor({ open, onClose, faq, onSaved, initialQuestion }: { open: boolean; onClose: () => void; faq?: FAQ | null; onSaved: () => void; initialQuestion?: string }) {
  const toast = useToast();
  const products = useProductOptions(open);
  const [f, setF] = React.useState({ question: "", answer: "", product_id: "", status: "published", visibility: "internal", tags: "" });
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => {
    if (open) setF(faq ? { question: faq.question, answer: faq.answer, product_id: faq.product_id ? String(faq.product_id) : "", status: faq.status, visibility: faq.visibility, tags: faq.tags.join(", ") }
      : { question: initialQuestion || "", answer: "", product_id: "", status: "published", visibility: "internal", tags: "" });
  }, [open, faq, initialQuestion]);
  const save = async () => {
    setBusy(true);
    const body = { ...f, product_id: f.product_id ? Number(f.product_id) : null, tags: f.tags.split(",").map((t) => t.trim()).filter(Boolean) };
    try {
      await api(faq ? `/faqs/${faq.id}` : "/faqs", { method: faq ? "PUT" : "POST", json: body });
      toast.success(faq ? "FAQ updated" : "FAQ added"); onSaved(); onClose();
    } catch (e) { toast.error("Could not save FAQ", (e as Error).message); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onClose={onClose} size="lg" title={faq ? "Edit FAQ" : "Add FAQ"} footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={save} loading={busy} disabled={!f.question.trim() || !f.answer.trim()}>Save</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Question *" className="sm:col-span-2"><Input value={f.question} onChange={(e) => setF({ ...f, question: e.target.value })} /></Field>
        <Field label="Answer *" className="sm:col-span-2" hint="Markdown supported"><Textarea rows={6} value={f.answer} onChange={(e) => setF({ ...f, answer: e.target.value })} /></Field>
        <Field label="Product"><Select value={f.product_id} onChange={(e) => setF({ ...f, product_id: e.target.value })}><option value="">General</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
        <Field label="Status"><Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="published">Published</option><option value="draft">Draft</option><option value="archived">Archived</option></Select></Field>
        <Field label="Visibility"><Select value={f.visibility} onChange={(e) => setF({ ...f, visibility: e.target.value })}><option value="internal">All team members</option><option value="restricted">Restricted (admins)</option></Select></Field>
        <Field label="Tags"><Input value={f.tags} onChange={(e) => setF({ ...f, tags: e.target.value })} placeholder="comma, separated" /></Field>
      </div>
    </Dialog>
  );
}

