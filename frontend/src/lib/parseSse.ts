// Shared SSE reader (Chat Orchestration v2, story 3.1 / §6.3).
//
// The single `data:` line parser for the whole app. Extracted verbatim-
// structurally from the three hand-rolled loops that existed before:
//   - ChatPanel.actualSend        (the send reader)
//   - ChatPanel reconnect reader
//   - WorkflowPanel.run
//
// Framework-agnostic: no React. Runs the while(true) reader + TextDecoder +
// line-split + `data:` JSON.parse loop, invoking `onEvent` for each parsed
// object. Malformed lines are skipped (never throw). `[DONE]` terminates.
//
// Cancellation: pass an AbortSignal. When it aborts, the underlying fetch's
// reader.read() rejects with an AbortError which we swallow — the loop simply
// ends. Callers that need per-chunk identity guards should do that inside
// `onEvent` (as ChatPanel does via conversationIdRef), NOT here.

export interface ParseSseOptions {
  /** Called once per successfully-parsed `data:` JSON object. */
  onEvent: (event: unknown) => void;
  /** Optional cancel signal. When aborted the loop ends quietly. */
  signal?: AbortSignal;
}

type StreamLike =
  | Response
  | ReadableStream<Uint8Array>
  | { getReader(): ReadableStreamDefaultReader<Uint8Array> };

function resolveReader(source: StreamLike): ReadableStreamDefaultReader<Uint8Array> | null {
  // A fetch Response — read its body.
  if (typeof Response !== 'undefined' && source instanceof Response) {
    return source.body?.getReader() ?? null;
  }
  // A ReadableStream or anything exposing getReader().
  if (typeof (source as { getReader?: unknown }).getReader === 'function') {
    return (source as ReadableStream<Uint8Array>).getReader();
  }
  return null;
}

/**
 * Read an SSE stream to completion, calling `onEvent(parsedJson)` for every
 * `data:` line. Resolves when the stream ends, `[DONE]` is seen, or the signal
 * aborts. Never rejects on malformed lines or on abort.
 */
export async function parseSse(source: StreamLike, opts: ParseSseOptions): Promise<void> {
  const { onEvent, signal } = opts;
  const reader = resolveReader(source);
  if (!reader) throw new Error('parseSse: no readable stream');

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      if (signal?.aborted) break;
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        // Tolerate both "data: {…}" and "data:{…}".
        const dataStr = line.slice(5).trim();
        if (!dataStr || dataStr === '[DONE]') continue;
        try {
          onEvent(JSON.parse(dataStr));
        } catch {
          // Malformed JSON line — skip, mirror the old behaviour.
        }
      }
    }
  } catch (err) {
    // Abort is expected (user stop / switch). Anything else re-throws so the
    // caller's catch can surface a connection error.
    if (err instanceof DOMException && err.name === 'AbortError') return;
    if (signal?.aborted) return;
    throw err;
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* already released */
    }
  }
}
