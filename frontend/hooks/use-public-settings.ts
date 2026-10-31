"use client";
import { useApi } from "./use-api";

export interface PublicSettings { company_name: string; default_language: string; web_research_enabled: boolean; team_can_research_from_chat: boolean; whisper_enabled: boolean; max_upload_mb: number }

export function usePublicSettings() {
  const { data } = useApi<PublicSettings>("/settings/public");
  return data;
}
