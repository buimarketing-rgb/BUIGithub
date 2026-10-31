"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/services/api";

/** Minimal data-fetching hook with loading/error state and manual reload. */
export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(!!path);
  const seq = useRef(0);

  const load = useCallback(async () => {
    if (!path) { setLoading(false); return; }
    const id = ++seq.current;
    setLoading(true);
    try {
      const res = await api<T>(path);
      if (id === seq.current) { setData(res); setError(null); }
    } catch (e) {
      if (id === seq.current) setError((e as Error).message);
    } finally {
      if (id === seq.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);

  useEffect(() => { load(); }, [load]);
  return { data, error, loading, reload: load, setData };
}

export function useDebounced<T>(value: T, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}
