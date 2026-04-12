import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Gauge, Eye, Search, Palette, Target, Code, Briefcase,
  ArrowLeft, ArrowRight, Loader2, Play, CheckCircle2,
  Circle, Upload, X, LinkIcon, Globe, Languages, DollarSign,
  Sparkles, Rocket, Zap, Brain,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useClientAccountId } from '@/hooks/useClientAccountId';

type ModelId = 'sonnet' | 'opus' | 'haiku';
const MODELS: { id: ModelId; label: string; desc: string; icon: typeof Zap }[] = [
  { id: 'opus', label: 'Opus', desc: 'Best quality (recommended)', icon: Brain },
  { id: 'sonnet', label: 'Sonnet', desc: 'Fast & smart', icon: Zap },
  { id: 'haiku', label: 'Haiku', desc: 'Quick & cheap', icon: Sparkles },
];

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

  // Persist form inputs in sessionStorage so they survive errors/restarts
  const loadSaved = (key: string, fallback: string) => {
    try { return sessionStorage.getItem(`campaign-builder-${key}`) || fallback; } catch { return fallback; }
  };
  const save = (key: string, value: string) => {
    try { sessionStorage.setItem(`campaign-builder-${key}`, value); } catch {}
  };

  // Input state — restored from sessionStorage
  const [url, setUrl] = useState(() => loadSaved('url', ''));
  const [brief, setBrief] = useState(() => loadSaved('brief', ''));
  const [budget, setBudget] = useState(() => Number(loadSaved('budget', '50')));
  const [geoTargets, setGeoTargets] = useState(() => loadSaved('geo', 'United States'));
  const [languages, setLanguages] = useState(() => loadSaved('lang', 'English'));
  const [attachments, setAttachments] = useState<BuildAttachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-save inputs as user types
  const setUrlSaved = (v: string) => { setUrl(v); save('url', v); };
  const setBriefSaved = (v: string) => { setBrief(v); save('brief', v); };
  const setBudgetSaved = (v: number) => { setBudget(v); save('budget', String(v)); };
  const setGeoSaved = (v: string) => { setGeoTargets(v); save('geo', v); };
  const setLangSaved = (v: string) => { setLanguages(v); save('lang', v); };

  // Pipeline state — persisted to sessionStorage
  const loadPipeline = () => {
    try {
      const saved = sessionStorage.getItem('campaign-builder-pipeline');
      return saved ? JSON.parse(saved) : null;
    } catch { return null; }
  };
  const savedPipeline = loadPipeline();

  const [sessionId, setSessionId] = useState<string | null>(savedPipeline?.sessionId || null);
  const [stages, setStages] = useState<Array<{
    stage: number;
    role_id: string;
    role_name: string;
    avatar: string;
    title: string;
    status: string;
    prompt: string;
  }>>(savedPipeline?.stages || []);
  const [currentStage, setCurrentStage] = useState(savedPipeline?.currentStage || 0);
  const [pipelineRunning, setPipelineRunning] = useState(false);

  // Auto-restore to pipeline step if there's saved progress
  const [step, setStep] = useState<WizardStep>(
    savedPipeline?.stages?.length > 0
      ? (savedPipeline.stages.every((s: { status: string }) => s.status === 'completed') ? 'review' : 'pipeline')
      : 'input'
  );

  // Auto-save pipeline state whenever it changes
  useEffect(() => {
    if (stages.length > 0) {
      try {
        sessionStorage.setItem('campaign-builder-pipeline', JSON.stringify({
          sessionId, stages, currentStage,
        }));
      } catch {}
    }
  }, [sessionId, stages, currentStage]);

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

  const [noLandingPage, setNoLandingPage] = useState(false);
  const [buildModel, setBuildModel] = useState<ModelId>('opus');

  // Start build
  const handleStartBuild = async () => {
    const finalUrl = noLandingPage ? `NO_LANDING_PAGE: ${brief.slice(0, 50)}` : url;
    const res = await fetch('/api/campaigns/build', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        account_id: accountId,
        landing_page_url: finalUrl,
        brief: noLandingPage
          ? `${brief}\n\nIMPORTANT: The user does NOT have a landing page yet. As part of this campaign build, suggest a landing page structure, wireframe, and key sections that should be created BEFORE launching ads. The CRO Specialist should provide a landing page blueprint.`
          : brief,
        budget_daily: budget,
        geo_targets: geoTargets.split(',').map(s => s.trim()),
        languages: languages.split(',').map(s => s.trim()),
        attachments: attachments.map(a => ({ filename: a.filename, path: a.path })),
      }),
    });
    const session = await res.json();
    setSessionId(session.id);
    setStages(session.stages);
    setCurrentStage(1);
    setStep('pipeline');

    // Save immediately (useEffect will also catch this, but belt-and-suspenders)
    try {
      sessionStorage.setItem('campaign-builder-pipeline', JSON.stringify({
        sessionId: session.id, stages: session.stages, currentStage: 1,
      }));
    } catch {}

    // Auto-run stage 1 after a short delay
    setTimeout(() => runStage(1), 500);
  };

  // Run a pipeline stage — sends to chat
  const runStage = useCallback(async (stageNum: number) => {
    const stage = stages.find(s => s.stage === stageNum);
    if (!stage) return;

    // Mark as running — use updater function to always get latest state
    setStages(prev => prev.map(s => s.stage === stageNum ? { ...s, status: 'running' } : s));
    setCurrentStage(stageNum);
    setPipelineRunning(true);

    // Register listener FIRST (before dispatching chat:send to avoid race)
    const handleDone = () => {
      // Use updater function — this always sees the latest state
      setStages(prev => prev.map(s => s.stage === stageNum ? { ...s, status: 'completed' } : s));
      setPipelineRunning(false);

      if (sessionId) {
        fetch(`/api/campaigns/build/${sessionId}/stage/${stageNum}/complete`, { method: 'POST' }).catch(() => {});
      }

      if (stageNum < 7) {
        setCurrentStage(stageNum + 1);
        setTimeout(() => runStage(stageNum + 1), 3000);
      } else {
        setStep('review');
      }
    };

    const doneHandler = () => {
      window.removeEventListener('agent:done', doneHandler);
      clearTimeout(fallbackTimer);
      handleDone();
    };
    window.addEventListener('agent:done', doneHandler);

    // Fallback timer
    const fallbackTimer = setTimeout(() => {
      window.removeEventListener('agent:done', doneHandler);
      handleDone();
    }, 240000);

    // NOW dispatch to chat (listener is already registered)
    const chatEvent = new CustomEvent('chat:send', {
      detail: {
        text: stage.prompt,
        roleId: stage.role_id,
        model: buildModel,
      },
    });
    window.dispatchEvent(chatEvent);
  }, [sessionId, stages, buildModel]);

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
          {/* Resume banner */}
          {savedPipeline?.stages?.length > 0 && step === 'input' && (
            <div className="border border-blue-500/40 bg-blue-500/5 rounded-lg p-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold">Resume Previous Build?</h3>
                <p className="text-xs text-muted-foreground">
                  {savedPipeline.stages.filter((s: { status: string }) => s.status === 'completed').length} of 7 stages completed
                </p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => setStep('pipeline')}>Resume</Button>
                <Button size="sm" variant="outline" onClick={() => {
                  sessionStorage.removeItem('campaign-builder-pipeline');
                  setSessionId(null); setStages([]); setCurrentStage(0);
                }}>Discard</Button>
              </div>
            </div>
          )}

          {/* URL */}
          <div>
            <label className="text-sm font-medium flex items-center gap-2 mb-2">
              <LinkIcon className="h-4 w-4" />
              Landing Page URL {noLandingPage ? '' : '*'}
            </label>
            {!noLandingPage ? (
              <>
                <Input
                  value={url}
                  onChange={e => setUrlSaved(e.target.value)}
                  placeholder="https://example.com/landing-page"
                  className="text-sm"
                />
                <div className="flex items-center justify-between mt-2">
                  <p className="text-xs text-muted-foreground">The CRO Specialist will analyze this page first</p>
                  <button
                    onClick={() => setNoLandingPage(true)}
                    className="text-[10px] text-primary hover:underline"
                  >
                    I don't have a landing page yet
                  </button>
                </div>
              </>
            ) : (
              <div className="border border-blue-500/30 bg-blue-500/5 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <Sparkles className="h-5 w-5 text-blue-500 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-semibold mb-1">Landing Page Creation Mode</h4>
                    <p className="text-xs text-muted-foreground mb-3">
                      The CRO Specialist will design a landing page blueprint with recommended sections,
                      copy structure, and conversion elements. Each role will build their strategy around this blueprint.
                    </p>
                    <div className="flex items-center gap-3">
                      <Input
                        value={url}
                        onChange={e => setUrlSaved(e.target.value)}
                        placeholder="Your website URL (optional, for brand reference)"
                        className="text-sm flex-1"
                      />
                      <button
                        onClick={() => setNoLandingPage(false)}
                        className="text-[10px] text-muted-foreground hover:text-foreground shrink-0"
                      >
                        I have a landing page
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Brief */}
          <div>
            <label className="text-sm font-medium mb-2 block">Campaign Brief</label>
            <textarea
              value={brief}
              onChange={e => setBriefSaved(e.target.value)}
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
                onChange={e => setBudgetSaved(Number(e.target.value))}
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
                onChange={e => setGeoSaved(e.target.value)}
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
                onChange={e => setLangSaved(e.target.value)}
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

          {/* Model selector */}
          <div>
            <label className="text-sm font-medium mb-2 block">AI Model</label>
            <div className="flex gap-2">
              {MODELS.map((m) => {
                const Icon = m.icon;
                return (
                  <button
                    key={m.id}
                    onClick={() => setBuildModel(m.id)}
                    className={cn(
                      'flex-1 flex items-center gap-2 px-4 py-3 rounded-lg border text-left transition-colors',
                      buildModel === m.id
                        ? 'border-primary bg-primary/10 text-foreground'
                        : 'border-border bg-card hover:bg-secondary/50 text-muted-foreground'
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <div>
                      <div className="text-sm font-medium">{m.label}</div>
                      <div className="text-[10px]">{m.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Buttons */}
          <div className="flex gap-3">
          <Button
            onClick={handleStartBuild}
            size="lg"
            className="flex-1 gap-2"
            disabled={!noLandingPage && !url.trim()}
          >
            <Sparkles className="h-4 w-4" />
            Start Building Campaign
          </Button>
          <Button
            variant="outline"
            size="lg"
            onClick={() => {
              sessionStorage.removeItem('campaign-builder-pipeline');
              ['url', 'brief', 'budget', 'geo', 'lang'].forEach(k => sessionStorage.removeItem(`campaign-builder-${k}`));
              setUrl(''); setBrief(''); setBudget(50); setGeoTargets('United States'); setLanguages('English');
              setAttachments([]); setSessionId(null); setStages([]); setCurrentStage(0);
            }}
          >
            Clear All
          </Button>
          </div>
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
                    {stage.status === 'error' && (
                      <p className="text-xs text-red-500 mt-1">
                        Failed — click Run to retry
                      </p>
                    )}
                  </div>

                  {/* Run / Retry button */}
                  {(isActive || stage.status === 'error') && !isDone && !isRunning && (
                    <Button
                      size="sm"
                      onClick={() => runStage(stage.stage)}
                      disabled={pipelineRunning}
                      className="gap-1"
                    >
                      <Play className="h-3 w-3" />
                      {stage.status === 'error' ? 'Retry' : 'Run'}
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
  const handleExportReport = () => {
    // Combine all role notes + chat into a markdown report
    const event = new CustomEvent('chat:send', {
      detail: {
        text: `As the Agency Director, compile a COMPLETE CAMPAIGN BUILD REPORT combining ALL role findings into one document:

Include these sections:
1. EXECUTIVE SUMMARY
2. LANDING PAGE ANALYSIS (from CRO Specialist notes)
3. COMPETITOR RESEARCH (from Competitor Intel notes)
4. KEYWORD STRATEGY (from Search Term Hunter notes)
5. AD COPY (from Creative Director notes — all headlines & descriptions)
6. CAMPAIGN STRUCTURE (from PPC Strategist notes)
7. TRACKING STATUS (from GTM Specialist notes)
8. LAUNCH CHECKLIST
9. EXPECTED RESULTS

READ ALL role_notes from campaign memory and compile them.
Format as a clean, professional document that could be shared with a client or stakeholder.`,
        roleId: 'director',
        model: buildModel,
      },
    });
    window.dispatchEvent(event);
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-6 text-center">
      <CheckCircle2 className="h-16 w-16 mx-auto text-emerald-500 mb-4" />
      <h1 className="text-2xl font-bold mb-2">Campaign Plan Complete!</h1>
      <p className="text-sm text-muted-foreground mb-6">
        All 7 specialists have contributed. The Agency Director's final plan is in the chat.
        Review it and say "CREATE" to build the campaign via Google Ads.
      </p>
      <div className="flex gap-3 justify-center flex-wrap">
        <Button variant="outline" onClick={onClose}>
          Close Builder
        </Button>
        <Button variant="outline" onClick={handleExportReport}>
          <ArrowRight className="h-4 w-4 mr-1" />
          Export Full Report
        </Button>
        <Button onClick={() => {
          const event = new CustomEvent('chat:send', {
            detail: { text: 'CREATE the campaign based on the plan above', roleId: 'director', model: buildModel },
          });
          window.dispatchEvent(event);
          onClose();
        }}>
          <Sparkles className="h-4 w-4 mr-1" />
          Create Campaign
        </Button>
      </div>
      <p className="text-xs text-muted-foreground mt-4">
        Pipeline progress saved. You can close and resume later.
      </p>
    </div>
  );
}
