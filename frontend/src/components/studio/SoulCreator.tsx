/**
 * SoulCreator — guided Soul character flow for the Studio hub (Epic
 * 12, story 12.3). Replaces the flat SoulCharactersPanel.
 *
 * Brief §5: guided 3-step card — upload 5-10 face refs → name + train
 * (progress states) → "ready" gallery with test-generate. Status chips
 * reuse the plan-state dots (training = pulse, ready = success,
 * failed = danger).
 *
 * Backend (Studio S5, reused as-is):
 *   POST /api/studio/soul/train   (FormData, 5-20 images)
 *   GET  /api/studio/soul         (list, polled while training)
 *
 * Copy honesty: the higgsfield CLI has no cost-estimate command for
 * Soul training (only `generate cost` for renders), so we promise the
 * 5-15 min window the backend asserts and say credits are billed by
 * Higgsfield — no invented credit numbers.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle, ArrowLeft, ArrowRight, Loader2, Sparkles, Upload,
  UserPlus, Wand2, X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { formatRelativeTime } from './AssetLibrary';
import {
  studioListSouls,
  studioTrainSoul,
  type SoulCharacter,
} from '@/lib/api';

interface SoulCreatorProps {
  accountId: string;
  /** Ready soul → host opens StudioPanel with this soul preselected. */
  onTestGenerate?: (soul: SoulCharacter) => void;
}

export default function SoulCreator({ accountId, onTestGenerate }: SoulCreatorProps) {
  const [souls, setSouls] = useState<SoulCharacter[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [prefillName, setPrefillName] = useState('');

  const refresh = useCallback(async () => {
    try {
      setSouls(await studioListSouls(accountId));
    } catch {
      setSouls([]);
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => { refresh(); }, [refresh]);

  // Poll while any soul is still training so ready state surfaces
  // without a manual refresh. Stops once everything is terminal.
  const anyWorking = souls.some((s) => s.status === 'pending' || s.status === 'training');
  useEffect(() => {
    if (!anyWorking) return;
    const interval = window.setInterval(refresh, 10_000);
    return () => window.clearInterval(interval);
  }, [anyWorking, refresh]);

  const startCreate = (name = '') => { setPrefillName(name); setCreating(true); };

  if (loading) {
    return (
      <div className="text-xs text-muted-foreground py-6 flex items-center gap-2">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading Souls…
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Soul characters</h2>
          <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
            Train Higgsfield on a person's face once, then every Soul-aware model
            renders recognizably the same person across all your creatives.
          </p>
        </div>
        {souls.length > 0 && !creating && (
          <Button size="sm" onClick={() => startCreate()} className="gap-1.5 shrink-0">
            <UserPlus className="h-3.5 w-3.5" /> New Soul
          </Button>
        )}
      </div>

      {/* Untrained state OR explicit create → the guided 3-step card */}
      {(creating || souls.length === 0) ? (
        <SoulWizardCard
          accountId={accountId}
          initialName={prefillName}
          onCancel={souls.length > 0 ? () => setCreating(false) : undefined}
          onSubmitted={() => { setCreating(false); setPrefillName(''); refresh(); }}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {souls.map((s) => (
            <SoulCard
              key={s.id}
              soul={s}
              onTestGenerate={onTestGenerate}
              onRetrain={() => startCreate(s.name)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── gallery card ──────────────────────────────────────────────────

function StatusDot({ status }: { status: string }) {
  if (status === 'ready') return <span className="h-2 w-2 rounded-full bg-success shrink-0" />;
  if (status === 'failed') return <span className="h-2 w-2 rounded-full bg-danger shrink-0" />;
  return <span className="h-2 w-2 rounded-full bg-accent studio-pulse shrink-0" />;
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'Queued', training: 'Training', ready: 'Ready', failed: 'Failed',
};

function SoulCard({ soul: s, onTestGenerate, onRetrain }: {
  soul: SoulCharacter;
  onTestGenerate?: (soul: SoulCharacter) => void;
  onRetrain: () => void;
}) {
  const working = s.status === 'pending' || s.status === 'training';
  return (
    <div className="border border-border rounded-md bg-card p-3 space-y-1.5">
      <div className="flex items-center gap-2">
        <StatusDot status={s.status} />
        <span className="text-xs font-semibold truncate" title={s.name}>{s.name}</span>
        <span className="ml-auto text-[10px] text-muted-foreground">
          {STATUS_LABEL[s.status] ?? s.status}
        </span>
      </div>
      <div className="text-[10px] text-muted-foreground font-mono">
        {s.training_model}
        {s.reference_image_paths ? ` · ${s.reference_image_paths.length} refs` : ''}
        {s.created_at ? ` · ${formatRelativeTime(s.created_at)}` : ''}
      </div>
      {working && (
        <p className="text-[10px] text-muted-foreground">
          Training usually finishes in 5-15 minutes. This list refreshes automatically.
        </p>
      )}
      {s.status === 'failed' && (
        <p className="text-[10px] text-danger leading-snug line-clamp-3" title={s.error_message ?? undefined}>
          {s.error_message || 'Training failed upstream.'}
        </p>
      )}
      <div className="flex items-center gap-1.5 pt-0.5">
        {s.status === 'ready' && s.soul_id && onTestGenerate && (
          <Button size="sm" variant="outline" className="h-6 gap-1 text-[11px]" onClick={() => onTestGenerate(s)}>
            <Wand2 className="h-3 w-3" /> Test generate
          </Button>
        )}
        {s.status === 'failed' && (
          <Button size="sm" variant="outline" className="h-6 gap-1 text-[11px]" onClick={onRetrain}>
            Train again
          </Button>
        )}
        {s.status === 'ready' && s.soul_id && (
          <code className="ml-auto text-[9px] text-muted-foreground truncate max-w-[100px]" title={s.soul_id}>
            {s.soul_id.slice(0, 8)}…
          </code>
        )}
      </div>
    </div>
  );
}

// ── the guided 3-step wizard card ─────────────────────────────────

type WizardStep = 1 | 2 | 3;

const STEPS: { n: WizardStep; label: string }[] = [
  { n: 1, label: 'Photos' },
  { n: 2, label: 'Name' },
  { n: 3, label: 'Train' },
];

function SoulWizardCard({ accountId, initialName, onCancel, onSubmitted }: {
  accountId: string;
  initialName?: string;
  onCancel?: () => void;
  onSubmitted: () => void;
}) {
  const [step, setStep] = useState<WizardStep>(1);
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState(initialName ?? '');
  const [trainingModel, setTrainingModel] = useState<'soul-2' | 'soul-cinematic'>('soul-2');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Object URLs for the thumbnails — revoked on change/unmount.
  const previews = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  const enoughPhotos = files.length >= 5;
  const validCount = enoughPhotos && files.length <= 20;

  const handleFiles = (selected: FileList | null) => {
    if (!selected) return;
    setFiles((prev) => [...prev, ...Array.from(selected)].slice(0, 20));
    setError(null);
  };

  const submit = async () => {
    if (!name.trim() || !validCount || busy) return;
    setBusy(true);
    setError(null);
    try {
      await studioTrainSoul({ accountId, name: name.trim(), trainingModel, images: files });
      onSubmitted();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      {/* Stepper */}
      <div className="flex items-center gap-1 px-4 py-2.5 border-b border-border">
        {STEPS.map((s, i) => (
          <div key={s.n} className="flex items-center gap-1">
            {i > 0 && <span className="w-6 h-px bg-border mx-1" />}
            <button
              type="button"
              onClick={() => { if (s.n < step) setStep(s.n); }}
              disabled={s.n > step}
              className={cn(
                'flex items-center gap-1.5 text-xs rounded px-1.5 py-0.5 transition-colors',
                s.n === step ? 'text-accent font-semibold bg-accent-soft'
                  : s.n < step ? 'text-foreground hover:bg-secondary/60'
                    : 'text-muted-foreground/60',
              )}
            >
              <span className={cn(
                'inline-flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-mono border',
                s.n === step ? 'border-accent text-accent' : 'border-border',
              )}>
                {s.n}
              </span>
              {s.label}
            </button>
          </div>
        ))}
        {onCancel && (
          <button onClick={onCancel} className="ml-auto p-1 hover:bg-secondary rounded" aria-label="Cancel">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <div className="p-4 space-y-3">
        {step === 1 && (
          <>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Add <b className="text-foreground">5-10 photos</b> of the same person (up to 20).
              Best results: varied angles, lighting, and expressions; just one face per photo.
            </p>
            <div className="grid grid-cols-5 sm:grid-cols-8 gap-1.5">
              {previews.map((url, i) => (
                <div key={i} className="relative aspect-square rounded overflow-hidden border border-border group">
                  <img src={url} alt={files[i]?.name ?? `ref ${i + 1}`} className="w-full h-full object-cover" />
                  <button
                    onClick={() => setFiles(files.filter((_, j) => j !== i))}
                    className="absolute top-0.5 right-0.5 bg-black/60 text-white rounded p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    aria-label="Remove photo"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                </div>
              ))}
              {files.length < 20 && (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="aspect-square rounded border border-dashed border-border flex flex-col items-center justify-center gap-0.5 text-muted-foreground hover:text-foreground hover:bg-secondary/40 transition-colors"
                >
                  <Upload className="h-3.5 w-3.5" />
                  <span className="text-[9px]">Add</span>
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
            <p className={cn('text-[11px]', enoughPhotos ? 'text-success' : 'text-muted-foreground')}>
              {files.length}/5 minimum
              {!enoughPhotos && files.length > 0 && ` — add ${5 - files.length} more`}
            </p>
          </>
        )}

        {step === 2 && (
          <>
            <div>
              <label className="label-section block mb-1">Character name</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Wassim, Sarah, the host"
                autoFocus
              />
            </div>
            <div>
              <label className="label-section block mb-1">Training model</label>
              <div className="flex gap-2">
                {([
                  ['soul-2', 'Soul 2.0', 'General purpose · faster training'],
                  ['soul-cinematic', 'Soul Cinematic', 'Film-quality · longer training'],
                ] as const).map(([id, label, hint]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setTrainingModel(id)}
                    className={cn(
                      'flex-1 border rounded px-3 py-2 text-xs text-left transition-colors',
                      trainingModel === id ? 'border-accent bg-accent-soft' : 'border-border hover:bg-secondary/50',
                    )}
                  >
                    <div className="font-semibold">{label}</div>
                    <div className="text-[10px] text-muted-foreground">{hint}</div>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <p className="text-xs leading-relaxed">
              Ready to train <b>{name || 'your Soul'}</b> on {files.length} photo{files.length === 1 ? '' : 's'} with{' '}
              <span className="font-mono text-[11px]">{trainingModel}</span>.
            </p>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Training runs on Higgsfield and usually finishes in 5-15 minutes; credits
              are billed by Higgsfield at training time. You can keep using the Studio
              while it runs — the gallery updates itself.
            </p>
          </>
        )}

        {error && (
          <div className="border border-danger/40 bg-danger-soft rounded p-2 text-[11px] text-danger flex items-start gap-2">
            <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            <span className="break-words">{error}</span>
          </div>
        )}
      </div>

      <div className="px-4 py-3 border-t border-border flex items-center justify-between bg-secondary/30">
        <div>
          {step > 1 && (
            <Button variant="ghost" size="sm" className="gap-1" onClick={() => setStep((s) => (s - 1) as WizardStep)} disabled={busy}>
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </Button>
          )}
        </div>
        {step < 3 ? (
          <Button
            size="sm"
            className="gap-1"
            onClick={() => setStep((s) => (s + 1) as WizardStep)}
            disabled={step === 1 ? !validCount : !name.trim()}
          >
            Next <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        ) : (
          <Button size="sm" onClick={submit} disabled={busy || !name.trim() || !validCount} className="gap-1.5">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            {busy ? 'Submitting…' : 'Start training'}
          </Button>
        )}
      </div>
    </div>
  );
}
