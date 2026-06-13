import { useState, useEffect, useCallback, useRef } from "react";
import { apiGet } from "../../api";

export interface UseApiGetResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useApiGet<T>(
  url: string,
  options?: {
    skip?: boolean;
    transform?: (raw: unknown) => T;
  }
): UseApiGetResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(!options?.skip);
  const [error, setError] = useState<string | null>(null);
  const [fetchCount, setFetchCount] = useState(0);

  const transformRef = useRef(options?.transform);
  transformRef.current = options?.transform;

  const refetch = useCallback(() => setFetchCount((n) => n + 1), []);

  useEffect(() => {
    if (options?.skip) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const run = async () => {
      try {
        const res = await apiGet(url, { signal: controller.signal });
        if (!res.ok) throw new Error(`Request failed: ${res.statusText}`);
        const raw: unknown = await res.json();
        const value = transformRef.current ? transformRef.current(raw) : (raw as T);
        setData(value);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError((err as Error).message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };

    run();
    return () => controller.abort();
  }, [url, options?.skip, fetchCount]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading, error, refetch };
}
