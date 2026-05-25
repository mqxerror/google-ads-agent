/**
 * SoulCharactersPanel — Studio's Soul character library.
 *
 * Lists all trained Soul references for the current account, lets the
 * operator train a new one from 5-20 reference photos (face-consistent
 * generation across all visa-campaign creatives), and shows status
 * live as training runs.
 *
 * Once a Soul is `ready`, picking text2image_soul_v2 / soul_cinematic
 * / soul_cast in HiggsfieldGenerator surfaces a Soul dropdown that
 * pulls from this list. The selected soul_id flows through to the
 * higgsfield CLI's --soul-id flag, producing recognizably the same
 * person across every render.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import {
  User, UserPlus, Loader2, Check, AlertCircle, X, Upload, Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  studioListSouls,
  studioTrainSoul,
  type SoulCharacter,
} from '@/lib/api';

interface SoulCharactersPanelProps {
  accountId: string;
}

export default function SoulCharactersPanel({ accountId }: SoulCharactersPanelProps) {
  const [souls, setSouls] = useState<SoulCharacter[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTrainer, setShowTrainer] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const list = await studioListSouls(accountId);
      setSouls(list);
    } catch {
      setSouls([]);
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    refresh();
    // Poll while any soul is still training so the UI surfaces ready
    // state without manual refresh. Stops once everything is terminal.
    const interval = window.setInterval(() => {
      if (souls.some((s) => s.status === 'pending' || s.status === 'training')) {
        refresh();
      }
    }, 10_000);
    return () => window.clearInterval(interval);
  }, [refresh, souls]);

  return (
    <section className="border border-border rounded-md p-3 flex flex-col gap-2 bg-card">
      <div className="flex items-center gap-2">
        <User className="h-3.5 w-3.5 text-primary" />
        <span className="text-[10px] uppercase font-mono text-muted-foreground">Higgsfield</span>
        <span className="text-xs font-medium">Soul characters</span>
        <span className="text-[10px] text-muted-foreground italic">
          Face-consistent generation across all your ads
        </span>
        <Button
          size="sm"
          onClick={() => setShowTrainer(true)}
          className="ml-auto gap-1.5"
        >
          <UserPlus className="h-3.5 w-3.5" />
          Train new Soul
        </Button>
      </div>

      {loading && souls.length === 0 ? (
        <div className="text-xs text-muted-foreground py-2 flex items-center gap-2">
          <Loader2 className="h-3 w-3 animate-spin" /> Loading…
        </div>
      ) : souls.length === 0 ? (
        <p className="text-xs text-muted-foreground py-2">
          No Souls trained yet. Train one with 5-20 reference photos of a
          person and Higgsfield will produce face-consistent images / videos
          for that character across every campaign.
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          {souls.map((s) => (
            <SoulTile key={s.id} soul={s} />
          ))}
        </div>
      )}

      {showTrainer && (
        <SoulTrainerModal
          accountId={accountId}
          onClose={() => setShowTrainer(false)}
          onTrained={() => {
            setShowTrainer(false);
            refresh();
          }}
        />
      )}
    </section>
  );
}

function SoulTile({ soul }: { soul: SoulCharacter }) {
  const isReady = soul.status === 'ready';
  const isFailed = soul.status === 'failed';
  const isWorking = soul.status === 'pending' || soul.status === 'training';

  return (
    <div
      className={cn(
        'border rounded-md p-2 text-xs flex flex-col gap-1',
        isReady && 'border-green-500/40 bg-green-500/5',
        isFailed && 'border-red-500/40 bg-red-500/5',
        isWorking && 'border-amber-500/40 bg-amber-500/5',
      )}
      title={
        isFailed && soul.error_message
          ? `${soul.error_code || 'error'}: ${soul.error_message}`
          : soul.status
      }
    >
      <div className="flex items-center justify-between gap-1">
        <span className="font-semibold truncate" title={soul.name}>{soul.name}</span>
        {isReady && <Check className="h-3.5 w-3.5 text-green-600 dark:text-green-400 shrink-0" />}
        {isFailed && <AlertCircle className="h-3.5 w-3.5 text-red-600 dark:text-red-400 shrink-0" />}
        {isWorking && <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-600 dark:text-amber-400 shrink-0" />}
      </div>
      <div className="text-[10px] text-muted-foreground font-mono truncate">
        {soul.training_model}
      </div>
      <div className="text-[10px] text-muted-foreground">
        {soul.status}
        {soul.reference_image_paths && (
          <> · {soul.reference_image_paths.length} refs</>
        )}
      </div>
      {isReady && soul.soul_id && (
        <code className="text-[9px] text-muted-foreground truncate" title={soul.soul_id}>
          {soul.soul_id.slice(0, 8)}…
        </code>
      )}
      {isFailed && soul.error_message && (
        <div className="text-[10px] text-red-600 dark:text-red-400 line-clamp-2">
          {soul.error_message}
        </div>
      )}
    </div>
  );
}

function SoulTrainerModal({
  accountId,
  onClose,
  onTrained,
}: {
  accountId: string;
  onClose: () => void;
  onTrained: () => void;
}) {
  const [name, setName] = useState('');
  const [trainingModel, setTrainingModel] = useState<'soul-2' | 'soul-cinematic'>('soul-2');
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validCount = files.length >= 5 && files.length <= 20;
  const canSubmit = !!name.trim() && validCount && !busy;

  const handleFiles = (selected: FileList | null) => {
    if (!selected) return;
    const next = [...files, ...Array.from(selected)].slice(0, 20);
    setFiles(next);
    setError(null);
  };

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      await studioTrainSoul({
        accountId,
        name: name.trim(),
        trainingModel,
        images: files,
      });
      onTrained();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-start justify-center pt-16 px-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-background border border-border rounded-lg shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div>
            <div className="text-sm font-semibold flex items-center gap-2">
              <UserPlus className="h-4 w-4 text-primary" />
              Train a new Soul
            </div>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Higgsfield needs 5-20 reference photos. Best results: varied angles,
              lighting, and expressions of the same person.
            </p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-secondary rounded" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-3">
          <div>
            <label className="text-[10px] uppercase font-mono text-muted-foreground block mb-1">Character name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Wassim, Sarah, the host"
              disabled={busy}
            />
          </div>

          <div>
            <label className="text-[10px] uppercase font-mono text-muted-foreground block mb-1">Training model</label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setTrainingModel('soul-2')}
                disabled={busy}
                className={cn(
                  'flex-1 border rounded px-3 py-2 text-xs text-left',
                  trainingModel === 'soul-2'
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:bg-secondary/50'
                )}
              >
                <div className="font-semibold">Soul 2.0</div>
                <div className="text-[10px] text-muted-foreground">General purpose · faster training</div>
              </button>
              <button
                type="button"
                onClick={() => setTrainingModel('soul-cinematic')}
                disabled={busy}
                className={cn(
                  'flex-1 border rounded px-3 py-2 text-xs text-left',
                  trainingModel === 'soul-cinematic'
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:bg-secondary/50'
                )}
              >
                <div className="font-semibold">Soul Cinematic</div>
                <div className="text-[10px] text-muted-foreground">Film-quality · longer training</div>
              </button>
            </div>
          </div>

          <div>
            <label className="text-[10px] uppercase font-mono text-muted-foreground block mb-1">
              Reference photos ({files.length}/5-20)
            </label>
            <div className="flex flex-wrap gap-1.5">
              {files.map((f, i) => (
                <div
                  key={i}
                  className="border border-border rounded p-1 text-[10px] font-mono flex items-center gap-1 bg-secondary/30"
                >
                  <span className="truncate max-w-[120px]" title={f.name}>{f.name}</span>
                  <button
                    onClick={() => setFiles(files.filter((_, j) => j !== i))}
                    className="hover:bg-secondary rounded p-0.5"
                    aria-label="Remove"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
              {files.length < 20 && (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={busy}
                  className="border border-dashed border-border rounded px-3 py-1.5 text-xs flex items-center gap-1.5 hover:bg-secondary/50 transition-colors"
                >
                  <Upload className="h-3.5 w-3.5" />
                  Add photos
                </button>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => {
                handleFiles(e.target.files);
                if (fileInputRef.current) fileInputRef.current.value = '';
              }}
            />
            {!validCount && files.length > 0 && (
              <p className="text-[10px] text-amber-500 mt-1">
                {files.length < 5
                  ? `Add ${5 - files.length} more photo${5 - files.length === 1 ? '' : 's'}`
                  : `Max 20 photos (you have ${files.length})`}
              </p>
            )}
          </div>

          {error && (
            <div className="border border-red-500/40 bg-red-500/5 rounded p-2 text-[11px] text-red-600 dark:text-red-400 flex items-start gap-2">
              <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
              <span className="break-words">{error}</span>
            </div>
          )}
        </div>

        <div className="px-4 py-3 border-t border-border flex items-center justify-between bg-secondary/30">
          <p className="text-[10px] text-muted-foreground">
            Training runs 5-15 min after submit · cost: ~50-200 credits
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button size="sm" onClick={submit} disabled={!canSubmit} className="gap-1.5">
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              {busy ? 'Submitting…' : 'Start training'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
