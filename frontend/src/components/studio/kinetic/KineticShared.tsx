/**
 * KineticShared — token-clean shared UI for the Kinetic lanes.
 *
 * Every raw Tailwind color from the legacy VideoCreator (pink-500 /
 * amber-500 / violet-500 / emerald-500 / red-*) is replaced with DESIGN.md
 * OKLCH tokens (surface, surface-2, border, accent, accent-soft, text,
 * text-muted, warning, warning-soft, danger, danger-soft). No em dashes in
 * UI copy.
 */

import { Loader2, X, Folder, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { LibraryImage, LibraryAudio } from './useKineticLibrary';
import { isLogoFilename } from './useKineticLibrary';

// ── Section label (DESIGN.md .label-section) ──
export function LaneLabel({ children }: { children: React.ReactNode }) {
  return <div className="label-section mb-2">{children}</div>;
}

// ── Shared text field (token-clean) ──
export function Field({
  value, onChange, placeholder, disabled, multiline, minH,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
  multiline?: boolean;
  minH?: string;
}) {
  const base =
    'w-full text-[13px] bg-surface-2 border border-border rounded-md px-2.5 py-1.5 ' +
    'text-text placeholder:text-muted-foreground/70 focus:outline-none focus:border-accent ' +
    'transition-colors disabled:opacity-60';
  if (multiline) {
    return (
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        className={cn(base, 'resize-y', minH || 'min-h-[60px]')}
      />
    );
  }
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      placeholder={placeholder}
      className={base}
    />
  );
}

// ── Render (primary) button — the one solid accent button per lane ──
export function RenderButton({
  onClick, disabled, busy, label,
}: { onClick: () => void; disabled: boolean; busy: boolean; label: string }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-md text-[13px] font-medium',
        'bg-accent text-on-accent hover:bg-accent-hover',
        'disabled:opacity-50 disabled:cursor-not-allowed transition-colors',
        'shadow-[var(--shadow-resting)]',
      )}
    >
      {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
      {label}
    </button>
  );
}

// ── Status strip — token-clean render/error state (from VideoCreator @1782) ──
export function StatusStrip({
  rendering, error, stage, stageMsg, elapsed,
}: { rendering: boolean; error: string; stage: string; stageMsg: string; elapsed: number }) {
  if (!rendering && !error) return null;
  return (
    <div
      className={cn(
        'mt-3 text-xs rounded-md px-3 py-2 flex items-center gap-2 border',
        error
          ? 'bg-danger-soft text-danger border-danger/30'
          : 'bg-surface-2 text-muted-foreground border-border',
      )}
    >
      {rendering && !error && <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0 text-accent" />}
      {error ? (
        <span className="flex items-center gap-1.5"><AlertTriangle className="h-3.5 w-3.5 shrink-0" /> {error}</span>
      ) : (
        <>
          <span className="label-section text-accent">{stage}</span>
          <span className="flex-1">{stageMsg}</span>
          <span className="text-muted-foreground tabular-nums font-mono">{elapsed}s</span>
        </>
      )}
    </div>
  );
}

// ── Modal shell ──
export function Modal({
  title, onClose, maxW, children,
}: { title: React.ReactNode; onClose: () => void; maxW?: string; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 bg-text/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className={cn(
          'bg-surface border border-border rounded-lg w-full max-h-[80vh] flex flex-col overflow-hidden',
          'shadow-[var(--shadow-elevated)]', maxW || 'max-w-4xl',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-border">
          <span className="text-sm font-medium text-text flex items-center gap-1.5">{title}</span>
          <button onClick={onClose} className="p-1 text-muted-foreground hover:text-text">
            <X className="h-4 w-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ── B-roll single-image picker modal ──
export function BrollPickerModal({
  images, loading, onPick, onClearAndClose, onClose,
}: {
  images: LibraryImage[];
  loading: boolean;
  onPick: (img: LibraryImage) => void;
  onClearAndClose: () => void;
  onClose: () => void;
}) {
  return (
    <Modal
      title={<><Folder className="h-4 w-4 text-accent" /> Pick a b-roll image <span className="text-[11px] text-muted-foreground ml-1">from your local library</span></>}
      onClose={onClose}
      maxW="max-w-3xl"
    >
      <div className="flex-1 overflow-y-auto p-3">
        {loading ? (
          <div className="text-xs text-muted-foreground flex items-center gap-1.5 py-8 justify-center">
            <Loader2 className="h-3 w-3 animate-spin" /> loading library…
          </div>
        ) : images.length === 0 ? (
          <div className="text-xs text-muted-foreground py-8 text-center">
            No uploaded images in your library yet. Upload some in Studio first, then come back here.
          </div>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
            {images.map((img) => (
              <button
                key={img.id}
                onClick={() => onPick(img)}
                className="group aspect-video rounded-md overflow-hidden border border-border hover:border-accent bg-surface-2 relative text-left transition-colors"
                title={img.filename}
              >
                <img src={img.url} alt={img.filename} className="w-full h-full object-cover" />
                <div className="absolute inset-x-0 bottom-0 bg-text/70 px-1.5 py-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <span className="text-[9px] text-surface truncate block">{img.filename}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="border-t border-border px-3 py-2 flex items-center justify-between text-[11px] text-muted-foreground">
        <span>{images.length} image{images.length === 1 ? '' : 's'}</span>
        <button onClick={onClearAndClose} className="text-muted-foreground hover:text-text">
          Use brand gradient instead (no image)
        </button>
      </div>
    </Modal>
  );
}

// ── Storyboard multi-image picker modal ──
export function StoryboardPickerModal({
  images, loading, selected, onToggle, onClear, onClose,
}: {
  images: LibraryImage[];
  loading: boolean;
  selected: Set<string>;
  onToggle: (filename: string) => void;
  onClear: () => void;
  onClose: () => void;
}) {
  return (
    <Modal
      title={<><Folder className="h-4 w-4 text-accent" /> Pick images for the Brand Story <span className="text-[11px] text-muted-foreground ml-1">click to toggle, the Director assigns each to a scene</span></>}
      onClose={onClose}
    >
      <div className="flex-1 overflow-y-auto p-3">
        {loading ? (
          <div className="text-xs text-muted-foreground flex items-center gap-1.5 py-8 justify-center">
            <Loader2 className="h-3 w-3 animate-spin" /> loading library…
          </div>
        ) : images.length === 0 ? (
          <div className="text-xs text-muted-foreground py-8 text-center">
            No uploaded images in your library yet. Upload some in Studio first.
          </div>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 gap-2">
            {images.map((img) => {
              const isSelected = selected.has(img.filename);
              return (
                <button
                  key={img.id}
                  onClick={() => onToggle(img.filename)}
                  className={cn(
                    'group aspect-video rounded-md overflow-hidden border-2 bg-surface-2 relative text-left transition-all',
                    isSelected ? 'border-accent ring-2 ring-accent/30' : 'border-border hover:border-accent/60',
                  )}
                  title={img.filename}
                >
                  <img src={img.url} alt={img.filename} className="w-full h-full object-cover" />
                  {isSelected && (
                    <div className="absolute inset-0 bg-accent-soft/60 flex items-center justify-center">
                      <div className="bg-accent text-on-accent rounded-full w-7 h-7 flex items-center justify-center text-xs font-bold shadow-[var(--shadow-resting)]">✓</div>
                    </div>
                  )}
                  <div className="absolute inset-x-0 bottom-0 bg-text/70 px-1.5 py-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <span className="text-[9px] text-surface truncate block">{img.filename}</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
      <div className="border-t border-border px-3 py-2 flex items-center justify-between text-[11px]">
        <button onClick={onClear} className="text-muted-foreground hover:text-text">Clear selection</button>
        <button onClick={onClose} className="px-3 py-1 rounded-md bg-accent-soft text-accent hover:bg-accent-soft/80">
          Done · {selected.size} selected
        </button>
      </div>
    </Modal>
  );
}

// ── Music bed picker modal ──
export function MusicPickerModal({
  audio, loading, onPick, onClose,
}: {
  audio: LibraryAudio[];
  loading: boolean;
  onPick: (a: LibraryAudio) => void;
  onClose: () => void;
}) {
  return (
    <Modal title={<>Pick a music bed</>} onClose={onClose} maxW="max-w-2xl">
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {loading ? (
          <div className="text-xs text-muted-foreground py-8 text-center flex items-center justify-center gap-2">
            <Loader2 className="h-3 w-3 animate-spin" /> loading audio…
          </div>
        ) : audio.length === 0 ? (
          <div className="text-xs text-muted-foreground py-8 text-center">
            No audio in your library yet. Upload .mp3 or .wav files in Studio, then they show here.
          </div>
        ) : (
          audio.map((a) => {
            const sizeKb = a.size_bytes ? Math.round(a.size_bytes / 1024) : null;
            return (
              <div key={a.id} className="flex items-center gap-2 p-2 rounded-md border border-border hover:border-accent/40 bg-surface hover:bg-surface-2 transition-colors">
                <button onClick={() => onPick(a)} className="text-left flex-1 min-w-0" title={a.filename}>
                  <div className="text-[11px] font-medium truncate text-text">{a.filename}</div>
                  {sizeKb && <div className="text-[9px] text-muted-foreground">{sizeKb} KB</div>}
                </button>
                <audio src={a.url} controls className="h-7 w-48" />
              </div>
            );
          })
        )}
      </div>
      <div className="border-t border-border px-3 py-2 text-[11px] text-muted-foreground">
        Music plays under VO at -18 dB if a voiceover is set, otherwise solo at -6 dB. Fades in 1s, out 1.5s.
      </div>
    </Modal>
  );
}

// ── Per-scene image swap modal — Library / Stock / AI tabs (token-clean) ──
export function SceneImageSwapModal({
  sceneIdx, images, swapMode, setSwapMode,
  stockQuery, setStockQuery, stockMatches, stockSearching, runStockSearch,
  aiPrompt, setAiPrompt, aiGenerating,
  onPickLibrary, onAdoptStock, onGenerateAi, onClose,
}: {
  sceneIdx: number;
  images: LibraryImage[];
  swapMode: 'library' | 'stock' | 'ai';
  setSwapMode: (m: 'library' | 'stock' | 'ai') => void;
  stockQuery: string;
  setStockQuery: (q: string) => void;
  stockMatches: Array<Record<string, unknown>>;
  stockSearching: boolean;
  runStockSearch: (q: string) => void;
  aiPrompt: string;
  setAiPrompt: (p: string) => void;
  aiGenerating: boolean;
  onPickLibrary: (img: LibraryImage) => void;
  onAdoptStock: (m: Record<string, unknown>) => void;
  onGenerateAi: (prompt: string) => void;
  onClose: () => void;
}) {
  return (
    <Modal title={<>Image for scene {sceneIdx + 1}</>} onClose={onClose}>
      {/* Tabs */}
      <div className="flex items-center gap-0.5 px-3 pt-2 border-b border-border">
        {([
          { k: 'library', label: 'My library', count: images.length },
          { k: 'stock', label: 'Stock photo', count: null },
          { k: 'ai', label: 'AI generate', count: null },
        ] as const).map((tab) => (
          <button
            key={tab.k}
            onClick={() => setSwapMode(tab.k)}
            className={cn(
              'px-3 py-1.5 text-[11px] rounded-t border-b-2 transition-colors',
              swapMode === tab.k
                ? 'border-accent text-accent bg-accent-soft'
                : 'border-transparent text-muted-foreground hover:text-text',
            )}
          >
            {tab.label}{tab.count !== null && tab.count > 0 ? ` · ${tab.count}` : ''}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {swapMode === 'library' && (
          images.length === 0 ? (
            <div className="text-xs text-muted-foreground py-8 text-center">No uploaded images yet. Try the Stock or AI tab.</div>
          ) : (
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              {images.map((img) => {
                const logo = isLogoFilename(img.filename);
                return (
                  <button
                    key={img.id}
                    onClick={() => onPickLibrary(img)}
                    className="group aspect-video rounded-md overflow-hidden border border-border hover:border-accent bg-surface-2 relative text-left transition-colors"
                    title={img.filename}
                  >
                    <img src={img.url} alt={img.filename} className="w-full h-full object-cover" />
                    {logo && <span className="absolute top-1 right-1 text-[8px] px-1 py-0.5 bg-warning-soft text-warning rounded font-mono uppercase">logo</span>}
                    <div className="absolute inset-x-0 bottom-0 bg-text/70 px-1.5 py-1">
                      <span className="text-[9px] text-surface truncate block">{img.filename}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )
        )}
        {swapMode === 'stock' && (
          <div className="space-y-2">
            <div className="flex gap-1.5">
              <input
                value={stockQuery}
                onChange={(e) => setStockQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') runStockSearch(stockQuery); }}
                placeholder="Search stock photos (e.g. luxury hotel exterior, family arriving airport)"
                className="flex-1 text-xs bg-surface-2 border border-border rounded-md px-2 py-1.5 text-text focus:outline-none focus:border-accent"
              />
              <button
                onClick={() => runStockSearch(stockQuery)}
                disabled={stockSearching || !stockQuery.trim()}
                className="px-3 py-1.5 text-xs bg-accent-soft text-accent hover:bg-accent-soft/80 rounded-md disabled:opacity-50"
              >
                {stockSearching ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Search'}
              </button>
            </div>
            {stockMatches.length === 0 && !stockSearching ? (
              <div className="text-[11px] text-muted-foreground py-6 text-center">
                Searches Unsplash and Pexels (free). Add UNSPLASH_ACCESS_KEY and/or PEXELS_API_KEY to .env if no results show.
              </div>
            ) : (
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                {stockMatches.map((m, mi) => (
                  <button
                    key={mi}
                    onClick={() => onAdoptStock(m)}
                    className="group aspect-video rounded-md overflow-hidden border border-border hover:border-accent bg-surface-2 relative text-left transition-colors"
                    title={String(m.description || '')}
                  >
                    <img src={String(m.thumb_url || m.image_url)} alt="" className="w-full h-full object-cover" />
                    <span className="absolute top-1 left-1 text-[7px] px-1 py-0.5 bg-surface/90 text-muted-foreground rounded font-mono uppercase">{String(m.provider || 'stock')}</span>
                    {m.photographer ? (
                      <div className="absolute inset-x-0 bottom-0 bg-text/70 px-1.5 py-1">
                        <span className="text-[8px] text-surface/90 truncate block">© {String(m.photographer)}</span>
                      </div>
                    ) : null}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        {swapMode === 'ai' && (
          <div className="space-y-2">
            <textarea
              value={aiPrompt}
              onChange={(e) => setAiPrompt(e.target.value)}
              placeholder="Describe the image you want. Be specific about subject, lighting, lens, mood. Example: 'modern boutique hotel exterior at golden hour, mediterranean coast, cinematic wide shot, warm light, shallow depth of field'"
              className="w-full min-h-[90px] text-xs bg-surface-2 border border-border rounded-md px-2 py-1.5 text-text focus:outline-none focus:border-accent resize-y"
            />
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <span className="font-mono">Replicate FLUX-schnell · ~$0.003 · ~3s · 1920×1080 16:9</span>
              <button
                onClick={() => onGenerateAi(aiPrompt)}
                disabled={aiGenerating || !aiPrompt.trim()}
                className="px-3 py-1 text-xs bg-accent-soft text-accent hover:bg-accent-soft/80 rounded-md disabled:opacity-50 flex items-center gap-1"
              >
                {aiGenerating ? <Loader2 className="h-3 w-3 animate-spin" /> : null} Generate
              </button>
            </div>
            <div className="text-[11px] text-muted-foreground italic border-t border-border pt-2">
              Add REPLICATE_API_TOKEN to .env to enable. Get one free at replicate.com.
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
