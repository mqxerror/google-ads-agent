// useDraftJob — client driver for the unified copy-jobs contract (Epic 16,
// stories 16.2/16.3/16.4 · FR1.7/1.9/1.10). One hook POSTs a copy job
// (draft | rewrite_row | diversify), polls it, and survives a page refresh via a
// localStorage resume key — the poll+resume pattern lifted from the wizards'
// draft-copy client (demand_gen.py:583-639 client side), now shared.
//
// Jobs are DB rows server-side (fence F6), so `interrupted` after a backend
// restart surfaces as a re-runnable error, never a silent hang (Honesty #4).

import { useCallback, useEffect, useRef, useState } from 'react';
import type { CopyRow } from '@/lib/copyRows';

export type DraftMode = 'draft' | 'rewrite_row' | 'diversify';

export interface CopyJobBody {
  campaign_type: string;
  mode: DraftMode;
  brief?: string;
  final_url?: string;
  business_name?: string;
  campaign_name?: string;
  rows?: CopyRow[];
  row_index?: number;
  target_angle?: string;
  locked_rows?: number[];
  flagged_rows?: number[];
  dismissed_dup_pairs?: [number, number][];
}

export interface CopyJobResult {
  rows: CopyRow[];
  business_name?: string;
  row_index?: number;
  flagged_after?: number[];
  below_threshold?: boolean;
  dismissed_dup_pairs?: [number, number][];
}

const POLL_MS = 3000;
const TIMEOUT_MS = 6 * 60_000;

async function pollJob(jobId: string, resumeKey: string): Promise<CopyJobResult> {
  const started = Date.now();
  while (Date.now() - started < TIMEOUT_MS) {
    await new Promise(r => setTimeout(r, POLL_MS));
    try {
      const res = await fetch(`/api/creative/copy-jobs/${jobId}`);
      const job = await res.json();
      if (job.status === 'done') {
        localStorage.removeItem(resumeKey);
        return (job.result || { rows: [] }) as CopyJobResult;
      }
      if (job.status === 'error') {
        localStorage.removeItem(resumeKey);
        throw new Error(job.message || 'copy job failed');
      }
      if (job.status === 'interrupted') {
        // Backend restart killed the in-flight job — no transparent resume.
        localStorage.removeItem(resumeKey);
        throw new Error(job.message || 'Draft was interrupted by a restart — run it again.');
      }
      // still running — keep polling (transient fetch errors just retry)
    } catch (e) {
      if (e instanceof Error && e.message !== 'Failed to fetch') throw e;
    }
  }
  throw new Error('Copy job timed out after 6 minutes — try again.');
}

export interface UseDraftJob {
  status: 'idle' | 'running' | 'done' | 'error';
  error: string | null;
  resuming: boolean;
  start: (body: CopyJobBody) => Promise<CopyJobResult>;
}

/**
 * @param accountId  the account the job runs under
 * @param resumeKey  localStorage key holding the in-flight job id (per field/mode)
 * @param onResume   applied when a refresh-resumed job completes (FR1.9)
 */
export function useDraftJob(
  accountId: string,
  resumeKey: string,
  onResume?: (result: CopyJobResult) => void,
): UseDraftJob {
  const [status, setStatus] = useState<UseDraftJob['status']>('idle');
  const [error, setError] = useState<string | null>(null);
  const [resuming, setResuming] = useState(false);
  const onResumeRef = useRef(onResume);
  onResumeRef.current = onResume;

  const start = useCallback(async (body: CopyJobBody): Promise<CopyJobResult> => {
    setStatus('running');
    setError(null);
    try {
      const res = await fetch(`/api/accounts/${accountId}/creative/copy-jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok || !data.job_id) {
        throw new Error(data.detail?.message || data.error || `HTTP ${res.status}`);
      }
      localStorage.setItem(resumeKey, data.job_id);
      const result = await pollJob(data.job_id, resumeKey);
      setStatus('done');
      return result;
    } catch (e) {
      setStatus('error');
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    }
  }, [accountId, resumeKey]);

  // FR1.9 — resume an in-flight job after a page refresh.
  useEffect(() => {
    const pending = localStorage.getItem(resumeKey);
    if (!pending) return;
    setResuming(true);
    pollJob(pending, resumeKey)
      .then(r => onResumeRef.current?.(r))
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setResuming(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeKey]);

  return { status, error, resuming, start };
}
