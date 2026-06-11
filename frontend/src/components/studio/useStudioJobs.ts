/**
 * useStudioJobs — shared generation-job watcher.
 *
 * Extracted from HiggsfieldGenerator's inline SSE logic so StudioPanel
 * (and future hosts) reuse one implementation instead of duplicating
 * it. Watches /api/studio/jobs/:id/stream per asset with a one-shot
 * poll fallback when SSE drops; the DB row stays the single source of
 * truth (the worker keeps writing whether or not anyone is watching).
 *
 * HiggsfieldGenerator itself is left untouched for now — it retires in
 * the Studio hub redesign (Phase B).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { studioGetJob, type StudioJobStatus } from '@/lib/api';

export interface JobVariant {
  asset_id: string;
  status: StudioJobStatus['status'];
  url: string | null;
  thumbnail_url: string | null;
  error_message: string | null;
  error_code: string | null;
}

const TERMINAL = ['completed', 'failed', 'nsfw'];

export function isTerminal(status: string): boolean {
  return TERMINAL.includes(status);
}

export function useStudioJobs(onSettled?: (asset: StudioJobStatus) => void) {
  const [variants, setVariants] = useState<JobVariant[]>([]);
  const sourcesRef = useRef<EventSource[]>([]);
  // Keep the latest callback without re-subscribing streams.
  const onSettledRef = useRef(onSettled);
  onSettledRef.current = onSettled;

  const closeAll = useCallback(() => {
    sourcesRef.current.forEach((es) => es.close());
    sourcesRef.current = [];
  }, []);

  useEffect(() => closeAll, [closeAll]);

  const applyUpdate = useCallback((assetId: string, data: StudioJobStatus) => {
    setVariants((prev) =>
      prev.map((v) =>
        v.asset_id === assetId
          ? {
              ...v,
              status: data.status,
              url: data.url,
              thumbnail_url: data.thumbnail_url,
              error_message: data.error_message,
              error_code: data.error_code,
            }
          : v,
      ),
    );
    if (isTerminal(data.status)) onSettledRef.current?.(data);
  }, []);

  /** Start watching a fresh batch of asset ids (replaces any previous
   * batch — close old sockets first so we don't leak). */
  const watch = useCallback((assetIds: string[]) => {
    closeAll();
    setVariants(
      assetIds.map((id) => ({
        asset_id: id,
        status: 'pending',
        url: null,
        thumbnail_url: null,
        error_message: null,
        error_code: null,
      })),
    );
    assetIds.forEach((assetId) => {
      const es = new EventSource(`/api/studio/jobs/${assetId}/stream`);
      sourcesRef.current.push(es);
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as StudioJobStatus;
          applyUpdate(assetId, data);
          if (isTerminal(data.status)) es.close();
        } catch {
          // Malformed event — the poll fallback below covers us.
        }
      };
      es.onerror = () => {
        es.close();
        studioGetJob(assetId)
          .then((data) => applyUpdate(assetId, data))
          .catch(() => {});
      };
    });
  }, [applyUpdate, closeAll]);

  /** Append additional asset ids to the CURRENT batch (per-item retry:
   * the failed tile is removed and the fresh job appended). */
  const watchMore = useCallback((assetIds: string[], removeIds: string[] = []) => {
    setVariants((prev) => [
      ...prev.filter((v) => !removeIds.includes(v.asset_id)),
      ...assetIds.map((id) => ({
        asset_id: id,
        status: 'pending',
        url: null,
        thumbnail_url: null,
        error_message: null,
        error_code: null,
      })),
    ]);
    assetIds.forEach((assetId) => {
      const es = new EventSource(`/api/studio/jobs/${assetId}/stream`);
      sourcesRef.current.push(es);
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as StudioJobStatus;
          applyUpdate(assetId, data);
          if (isTerminal(data.status)) es.close();
        } catch { /* poll fallback covers us */ }
      };
      es.onerror = () => {
        es.close();
        studioGetJob(assetId)
          .then((data) => applyUpdate(assetId, data))
          .catch(() => {});
      };
    });
  }, [applyUpdate]);

  /** Surface a submit-time failure (network / 4xx) as one failed tile. */
  const failSubmit = useCallback((message: string) => {
    closeAll();
    setVariants([{
      asset_id: 'submit-error',
      status: 'failed',
      url: null,
      thumbnail_url: null,
      error_message: message,
      error_code: 'submit',
    }]);
  }, [closeAll]);

  const reset = useCallback(() => {
    closeAll();
    setVariants([]);
  }, [closeAll]);

  const settledCount = variants.filter((v) => isTerminal(v.status)).length;
  const runningCount = variants.filter((v) => !isTerminal(v.status)).length;
  const errorCount = variants.filter((v) => v.status === 'failed' || v.status === 'nsfw').length;

  return { variants, watch, watchMore, failSubmit, reset, settledCount, runningCount, errorCount };
}
