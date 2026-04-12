import { useState, useCallback, useRef } from 'react';
import {
  Gauge, Eye, Search, Palette, Target, Code, Briefcase,
  ArrowLeft, ArrowRight, Loader2, Play, CheckCircle2,
  Circle, Upload, X, LinkIcon, Globe, Languages, DollarSign,
  Sparkles, Rocket,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useClientAccountId } from '@/hooks/useClientAccountId';

interface CampaignBuilderProps {
  onClose: () => void;
}

interface BuildAttachment {
  filename: string;
  path: string;
  is_image: boolean;
  ext: string;
  url: string;
  size: number;
}

const STAGE_ICONS = [Gauge, Eye, Search, Palette, Target, Code, Briefcase];
const STAGE_COLORS = [
  'text-indigo-500', 'text-red-500', 'text-blue-500', 'text-purple-500',
  'text-orange-500', 'text-cyan-500', 'text-gray-500',
];

type WizardStep = 'input' | 'pipeline' | 'review';

export default function CampaignBuilder({ onClose }: CampaignBuilderProps) {
  const accountId = useClientAccountId();
  const [step, setStep] = useState<WizardStep>('input');

  // Input state
  const [url, setUrl] = useState('');
  const [brief, setBrief] = useState('');
  const [budget, setBudget] = useState(50);
  const [geoTargets, setGeoTargets] = useState('United States');
  const [languages, setLanguages] = useState('English');
  const [attachments, setAttachments] = useState<BuildAttachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Pipeline state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [stages, setStages] = useState<Array<{
    stage: number;
    role_id: string;
    role_name: string;
    avatar: string;
    title: string;
    status: string;
    prompt: string;
  }>>([]);
  const [currentStage, setCurrentStage] = useState(0);
  const [pipelineRunning, setPipelineRunning] = useState(false);

  // File upload
  const handleFileUpload = useCallback(async (files: FileList | null) => {
    if (!files) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const formData = new FormData();
        formData.append('conversation_id', `build-${Date.now()}`);
        formData.append('file', file);
        const res = await fetch('/api/uploads', { method: 'POST', body: formData });
        if (res.ok) {
          const data = await res.json();
          setAttachments(prev => [...prev, data]);
        }
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, []);

  // Start build
  const handleStartBuild = async () => {
    const res = await fetch('/api/campaigns/build', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        account_id: accountId,
        landing_page_url: url,
        brief,
        budget_daily: budget,
        geo_targets: geoTargets.split(',').map(s => s.trim()),
        languages: languages.split(',').map(s => s.trim()),
        attachments: attachments.map(a => ({ filename: a.filename, path: a.path })),
      }),
    });
    const session = await res.json();
    setSessionId(session.id);
    setStages(session.stages);
    setCurrentStage(0);
    setStep('pipeline');
  };

  // Run a pipeline stage — sends to chat
  const runStage = useCallback(async (stageNum: number) => {
    if (!sessionId) return;

    const stage = stages.find(s => s.stage === stageNum);
    if (!stage) return;

    // Mark as running
    setStages(prev => prev.map(s => s.stage === stageNum ? { ...s, status: 'running' } : s));
    setCurrentStage(stageNum);
    setPipelineRunning(true);

    // Send to chat via window event
    const event = new CustomEvent('chat:send', {
      detail: {
        text: stage.prompt,
        roleId: stage.role_id,
        model: 'opus',
      },
    });
    window.dispatchEvent(event);

    // Mark complete after a delay (user will see the chat output)
    // In v2, we'd listen for the agent's done event
    setTimeout(() => {
      setStages(prev => prev.map(s => s.stage === stageNum ? { ...s, status: 'completed' } : s));
      setPipelineRunning(false);

      // Mark on backend
      fetch(`/api/campaigns/build/${sessionId}/stage/${stageNum}/complete`, { method: 'POST' });

      // Auto-advance to next stage prompt
      if (stageNum < 7) {
        setCurrentStage(stageNum + 1);
      } else {
        setStep('review');
      }
    }, 3000);
  }, [sessionId, stages]);

  // ── INPUT STEP ─────────────────────────────────────────────
  if (step === 'input') {
    return (
      <div className="max-w-2xl mx-auto py-8 px-6">
        <div className="flex items-center gap-3 mb-8">
          <button onClick={onClose} className="p-1.5 hover:bg-secondary rounded-md">
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Rocket className="h-6 w-6 text-primary" />
              Campaign Builder
            </h1>
            <p className="text-sm text-muted-foreground">
              Your agency team will research, plan, and build the campaign collaboratively
            </p>
          </div>
        </div>

        <div className="space-y-6">
          {/* URL */}
          <div>
            <label className="text-sm font-medium flex items-center gap-2 mb-2">
              <LinkIcon className="h-4 w-4" />
              Landing Page URL *
            </label>
            <Input
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://example.com/landing-page"
              className="text-sm"
            />
            <p className="text-xs text-muted-foreground mt-1">The CRO Specialist will analyze this page first</p>
          </div>

          {/* Brief */}
          <div>
            <label className="text-sm font-medium mb-2 block">Campaign Brief</label>
            <textarea
              value={brief}
              onChange={e => setBrief(e.target.value)}
              placeholder="Describe the product/service, target audience, and campaign goals..."
              rows={4}
              className="w-full bg-secondary/50 border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring resize-y"
            />
          </div>

          {/* Budget + Geo + Language */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-medium flex items-center gap-1 mb-1.5">
                <DollarSign className="h-3 w-3" />
                Daily Budget
              </label>
              <Input
                type="number"
                value={budget}
                onChange={e => setBudget(Number(e.target.value))}
                min={1}
                className="text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium flex items-center gap-1 mb-1.5">
                <Globe className="h-3 w-3" />
                Geo Targets
              </label>
              <Input
                value={geoTargets}
                onChange={e => setGeoTargets(e.target.value)}
                placeholder="US, UK, Canada"
                className="text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium flex items-center gap-1 mb-1.5">
                <Languages className="h-3 w-3" />
                Languages
              </label>
              <Input
                value={languages}
                onChange={e => setLanguages(e.target.value)}
                placeholder="English"
                className="text-sm"
              />
            </div>
          </div>

          {/* File uploads */}
          <div>
            <label className="text-sm font-medium mb-2 block">
              Attachments (optional)
            </label>
            <p className="text-xs text-muted-foreground mb-3">
              Upload spy reports, competitor screenshots, industry data, or any reference files
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={e => handleFileUpload(e.target.files)}
            />
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-border rounded-lg p-6 text-center cursor-pointer hover:border-primary/50 hover:bg-secondary/30 transition-colors"
            >
              <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">
                {uploading ? 'Uploading...' : 'Click or drag files here'}
              </p>
            </div>
            {attachments.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {attachments.map(att => (
                  <div key={att.filename} className="flex items-center gap-1.5 px-2 py-1 rounded bg-secondary/60 border border-border text-xs">
                    <span className="truncate max-w-[150px]">{att.filename}</span>
                    <button onClick={() => setAttachments(prev => prev.filter(a => a.filename !== att.filename))}>
                      <X className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Pipeline preview */}
          <div className="bg-card border border-border rounded-lg p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">
              Your team will run 7 stages:
            </h3>
            <div className="space-y-2">
              {['CRO Analysis', 'Competitor Research', 'Keyword Strategy', 'Ad Copy Creation', 'Campaign Structure', 'Tracking Check', 'Final Review'].map((name, i) => {
                const Icon = STAGE_ICONS[i];
                return (
                  <div key={i} className="flex items-center gap-3 text-sm">
                    <div className={cn('p-1 rounded', STAGE_COLORS[i])}>
                      <Icon className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-xs">{i + 1}. {name}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Start button */}
          <Button
            onClick={handleStartBuild}
            size="lg"
            className="w-full gap-2"
            disabled={!url.trim()}
          >
            <Sparkles className="h-4 w-4" />
            Start Building Campaign
          </Button>
        </div>
      </div>
    );
  }

  // ── PIPELINE STEP ──────────────────────────────────────────
  if (step === 'pipeline') {
    return (
      <div className="max-w-3xl mx-auto py-8 px-6">
        <div className="flex items-center gap-3 mb-8">
          <button onClick={() => setStep('input')} className="p-1.5 hover:bg-secondary rounded-md">
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-xl font-bold">Building Campaign</h1>
            <p className="text-xs text-muted-foreground">{url}</p>
          </div>
        </div>

        {/* Pipeline timeline */}
        <div className="space-y-3">
          {stages.map((stage, i) => {
            const Icon = STAGE_ICONS[i] || Briefcase;
            const isActive = stage.stage === currentStage;
            const isDone = stage.status === 'completed';
            const isRunning = stage.status === 'running';

            return (
              <div
                key={stage.stage}
                className={cn(
                  'border rounded-lg p-4 transition-all',
                  isDone && 'border-emerald-500/40 bg-emerald-500/5',
                  isRunning && 'border-primary/50 bg-primary/5 ring-2 ring-primary/20',
                  isActive && !isRunning && !isDone && 'border-border bg-secondary/30',
                  !isActive && !isDone && !isRunning && 'border-border/50 opacity-50',
                )}
              >
                <div className="flex items-center gap-3">
                  {/* Status indicator */}
                  {isDone ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" />
                  ) : isRunning ? (
                    <Loader2 className="h-5 w-5 text-primary animate-spin shrink-0" />
                  ) : (
                    <Circle className="h-5 w-5 text-muted-foreground/40 shrink-0" />
                  )}

                  {/* Role icon + info */}
                  <div className={cn('p-1.5 rounded', STAGE_COLORS[i])}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold">{stage.title}</h3>
                      <span className="text-[10px] text-muted-foreground">{stage.role_name}</span>
                    </div>
                    {isRunning && (
                      <p className="text-xs text-muted-foreground mt-1 animate-pulse">
                        Working... check the chat panel for live output →
                      </p>
                    )}
                    {isDone && (
                      <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1">
                        Completed — findings saved to campaign memory
                      </p>
                    )}
                  </div>

                  {/* Run button */}
                  {isActive && !isDone && !isRunning && (
                    <Button
                      size="sm"
                      onClick={() => runStage(stage.stage)}
                      disabled={pipelineRunning}
                      className="gap-1"
                    >
                      <Play className="h-3 w-3" />
                      Run
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Progress info */}
        <div className="mt-6 text-center">
          <p className="text-xs text-muted-foreground">
            Stage {currentStage} of {stages.length} · Each role reads the previous role's findings automatically
          </p>
          {currentStage > 0 && currentStage <= stages.length && (
            <Button
              variant="outline"
              size="sm"
              className="mt-3 gap-1"
              onClick={() => runStage(currentStage)}
              disabled={pipelineRunning}
            >
              <ArrowRight className="h-3 w-3" />
              Run Stage {currentStage}
            </Button>
          )}
        </div>
      </div>
    );
  }

  // ── REVIEW STEP ────────────────────────────────────────────
  return (
    <div className="max-w-2xl mx-auto py-8 px-6 text-center">
      <CheckCircle2 className="h-16 w-16 mx-auto text-emerald-500 mb-4" />
      <h1 className="text-2xl font-bold mb-2">Campaign Plan Complete!</h1>
      <p className="text-sm text-muted-foreground mb-6">
        All 7 specialists have contributed. The Agency Director's final plan is in the chat.
        Review it and say "CREATE" to build the campaign via Google Ads.
      </p>
      <div className="flex gap-3 justify-center">
        <Button variant="outline" onClick={onClose}>
          Close Builder
        </Button>
        <Button onClick={() => {
          const event = new CustomEvent('chat:send', {
            detail: { text: 'CREATE the campaign based on the plan above', roleId: 'director', model: 'opus' },
          });
          window.dispatchEvent(event);
          onClose();
        }}>
          <Sparkles className="h-4 w-4 mr-1" />
          Create Campaign
        </Button>
      </div>
    </div>
  );
}
