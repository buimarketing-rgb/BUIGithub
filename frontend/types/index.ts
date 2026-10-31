export type Role = "super_admin" | "admin" | "team_member";

export interface User {
  id: number; email: string; full_name: string; role: Role; is_active: boolean;
  preferred_language: string; last_login_at: string | null; created_at: string;
}
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface Category { id: number; name: string; description: string | null; parent_id: number | null; product_count: number }
export interface ProductImage { id: number; original_name: string; caption: string | null; url: string }
export interface ProductFields {
  name: string; brand: string | null; model_number: string | null; category_id: number | null; description: string | null;
  specifications: Record<string, string>; features: string[]; applications: string[]; compatibility: string[]; accessories: string[];
  pricing: string | null; warranty: string | null; installation: string | null; maintenance: string | null; troubleshooting: string | null;
  source_urls: string[]; tags: string[]; status: "draft" | "verified" | "needs_review" | "archived";
}
export interface Product extends ProductFields {
  id: number; category_name: string | null; version: number; created_at: string; updated_at: string;
  images: ProductImage[]; document_count: number; faq_count: number;
}
export interface ProductListItem {
  id: number; name: string; brand: string | null; model_number: string | null; category_id: number | null;
  category_name: string | null; status: string; version: number; updated_at: string; description: string | null;
}
export interface ProductVersion { id: number; version: number; change_note: string | null; created_at: string; snapshot: ProductFields }

export interface DocumentVersion { id: number; version: number; title: string; original_filename: string | null; file_size: number | null; change_note: string | null; created_at: string; download_url: string | null }
export interface KnowledgeDocument {
  id: number; title: string; category: string; source_type: string; source_url: string | null; product_id: number | null;
  product_name: string | null; tags: string[]; status: string; visibility: string; processing_status: string;
  processing_error: string | null; current_version: number; original_filename: string | null; content_type: string | null;
  file_size: number | null; chunk_count: number; created_at: string; updated_at: string; content_preview: string | null;
}
export interface DocumentDetail extends KnowledgeDocument { content: string | null; versions: DocumentVersion[]; download_url: string | null }

export interface FAQ {
  id: number; question: string; answer: string; product_id: number | null; product_name: string | null; category: string;
  tags: string[]; status: string; visibility: string; origin: string; created_at: string; updated_at: string;
}

export interface Source {
  n: number; source_type: string; source_id: number; title: string; section: string | null; url: string | null;
  verified: boolean; updated_at: string | null; version: number | null; product_id: number | null; snippet: string; official?: boolean;
}
export interface ChatMessage {
  id: number; role: "user" | "assistant"; content: string; sources: Source[]; related_questions: string[];
  answered: boolean | null; confidence: number | null; used_web: boolean; provider: string | null; latency_ms: number | null;
  created_at: string; feedback: boolean | null; pending?: boolean; status?: string; research_job_id?: number | null;
}
export interface Conversation { id: number; title: string; language: string; is_voice: boolean; created_at: string; updated_at: string; snippet: string | null }

export interface ResearchJob {
  id: number; query: string | null; url: string | null; product_id: number | null; product_name: string | null; status: string;
  error: string | null; origin: string; schedule_hours: number | null; next_run_at: string | null; last_run_at: string | null;
  created_at: string; finding_counts: Record<string, number>;
}
export interface ResearchSource { id: number; url: string; domain: string; title: string | null; is_official: boolean; robots_allowed: boolean; fetch_status: string; http_status: number | null; retrieved_at: string | null }
export interface ResearchFinding {
  id: number; job_id: number; product_id: number | null; category: string; key: string | null; value: string; status: string;
  is_duplicate: boolean; has_conflict: boolean; conflict_with: string | null; confidence: number; review_note: string | null;
  source_url: string | null; source_domain: string | null; source_official: boolean; retrieved_at: string | null;
}
export interface ResearchJobDetail extends ResearchJob { log: { at: string; msg: string }[]; sources: ResearchSource[]; findings: ResearchFinding[] }
