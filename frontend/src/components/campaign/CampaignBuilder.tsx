import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Gauge, Eye, Search, Palette, Target, Code, Briefcase,
  ArrowLeft, ArrowRight, Loader2, Play, CheckCircle2,
  Circle, Upload, X, LinkIcon, Globe, Languages, DollarSign,
  Sparkles, Rocket, Zap, Brain, RefreshCw,
  Layers, Video,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import PMaxWizard from './PMaxWizard';
// chatApi used for atomic conversation creation in runStage and Research

type ModelId = 'fable' | 'sonnet' | 'opus' | 'haiku';
const MODELS: { id: ModelId; label: string; desc: string; icon: typeof Zap }[] = [
  { id: 'fable', label: 'Fable 5', desc: 'Best quality (recommended)', icon: Brain },
  { id: 'opus', label: 'Opus', desc: 'Deep analysis', icon: Brain },
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

type WizardStep = 'type' | 'input' | 'pipeline' | 'review';
type CampaignType = 'search' | 'pmax' | 'video';

export default function CampaignBuilder({ onClose }: CampaignBuilderProps) {
  const accountId = useClientAccountId();

  // Campaign type picker — defaults to 'search' so existing behaviour
  // is preserved if the user picks Search; PMax routes to a different
  // wizard, Video shows a coming-soon card.
  const [campaignType, setCampaignType] = useState<CampaignType | null>(() => {
    try { return (sessionStorage.getItem('campaign-builder-type') as CampaignType) || null; } catch { return null; }
  });
  const persistCampaignType = (t: CampaignType | null) => {
    try {
      if (t) sessionStorage.setItem('campaign-builder-type', t);
      else sessionStorage.removeItem('campaign-builder-type');
    } catch {}
    setCampaignType(t);
  };

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

  // Pipeline state — derived from BACKEND role_notes files (the source of truth)
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [stages, setStages] = useState<Array<{
    stage: number;
    role_id: string;
    role_name: string;
    avatar: string;
    title: string;
    status: string;
    prompt?: string;
  }>>([]);
  const [currentStage, setCurrentStage] = useState(1);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  // Persisted so navigating away from the builder and back resumes the SAME
  // conversation thread instead of forking a new one (which desynced the chat
  // panel from the pipeline and stranded the old thread).
  const [buildConversationId, _setBuildConversationId] = useState<string | null>(
    () => loadSaved('conv_id', '') || null,
  );
  const setBuildConversationId = useCallback((id: string | null) => {
    _setBuildConversationId(id);
    if (id) save('conv_id', id);
    else { try { sessionStorage.removeItem('campaign-builder-conv_id'); } catch {} }
  }, []);
  // Re-entrancy guards: a triple-click must not spawn 3 builds / 3 stage runs.
  const startingRef = useRef(false);
  const stageInFlightRef = useRef(false);
  const [isStarting, setIsStarting] = useState(false);
  const [autoMode, setAutoMode] = useState(true); // true = run all stages non-stop
  // Step state: `type` first (campaign-type picker), then forks to the
  // existing Search input or to PMaxWizard. Resumes wherever the user
  // left off if a previous session set a campaign type.
  const [step, setStep] = useState<WizardStep>(() => {
    try {
      const savedType = sessionStorage.getItem('campaign-builder-type');
      return savedType ? 'input' : 'type';
    } catch { return 'type'; }
  });

  // On mount: check backend for existing pipeline progress
  useEffect(() => {
    if (!accountId) return;
    // Use a known campaign_id or a "build" namespace
    const campaignId = loadSaved('build_campaign_id', '');
    if (!campaignId) return;

    fetch(`/api/campaigns/build/status/${accountId}/${campaignId}`)
      .then(r => r.json())
      .then(data => {
        if (data.completed_stages?.length > 0) {
          setStages(data.stages);
          setCurrentStage(data.next_stage);
          setStep(data.all_done ? 'review' : 'pipeline');
        }
      })
      .catch(() => {});
  }, [accountId]);

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
  const [buildModel, setBuildModel] = useState<ModelId>('fable');

  // Start build
  const handleStartBuild = async () => {
    // Re-entrancy guard: ignore rapid double/triple-clicks. The ref flips
    // synchronously (before any await) so a burst of clicks in the same tick
    // can't each pass the check and fire 3 POST /campaigns/build.
    if (startingRef.current) return;
    startingRef.current = true;
    setIsStarting(true);
    try {
      // Fresh build → drop any previous build's conversation thread.
      setBuildConversationId(null);
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
      if (!res.ok) throw new Error(`Build start failed: ${res.status}`);
      const session = await res.json();
      setSessionId(session.id);
      setStages(session.stages);
      setCurrentStage(1);
      setStep('pipeline');

      // Save campaign context so we can derive status on reload
      save('build_campaign_id', session.input?.campaign_id || `build-${session.id.slice(0, 8)}`);
    } catch (err) {
      console.error('Start build failed:', err);
    } finally {
      startingRef.current = false;
      setIsStarting(false);
    }
  };

  // Refresh pipeline status from backend
  const refreshPipelineStatus = useCallback(async () => {
    const campaignId = loadSaved('build_campaign_id', '');
    if (!accountId || !campaignId) return;
    try {
      const res = await fetch(`/api/campaigns/build/status/${accountId}/${campaignId}`);
      const data = await res.json();
      if (data.stages) {
        setStages(data.stages);
        setCurrentStage(data.next_stage);
        if (data.all_done) setStep('review');
      }
    } catch {}
  }, [accountId]);

  // Run a pipeline stage — sends to chat, then user clicks "Run Next" for the next one
  // `chain` controls auto-advance. A manual per-stage Run is a one-shot
  // (chain=false) so firing any agent out of order doesn't drag the whole
  // sequential pipeline behind it. The "Run all remaining" path passes
  // chain=true to keep the in-order behaviour.
  const runStage = useCallback(async (stageNum: number, chain: boolean = autoMode) => {
    const stage = stages.find(s => s.stage === stageNum);
    if (!stage) return;
    // Re-entrancy guard: a manual click can land on top of the auto-advance
    // setTimeout (or a triple-click on "Run"). Without this, two runStage calls
    // fire concurrent POST /message for different stages on the same thread.
    if (stageInFlightRef.current) return;
    stageInFlightRef.current = true;

    setStages(prev => prev.map(s => s.stage === stageNum ? { ...s, status: 'running' } : s));
    setCurrentStage(stageNum);
    setPipelineRunning(true);

    // Listen for completion — mark done and optionally auto-advance
    const doneHandler = () => {
      window.removeEventListener('agent:done', doneHandler);
      clearTimeout(fallbackTimer);

      // Mark current stage as completed
      setStages(prev => prev.map(s => s.stage === stageNum ? { ...s, status: 'completed' } : s));
      if (sessionId) {
        fetch(`/api/campaigns/build/${sessionId}/stage/${stageNum}/complete`, { method: 'POST' }).catch(() => {});
      }

      if (stageNum >= 7) {
        setPipelineRunning(false);
        setStep('review');
        return;
      }

      const nextStage = stageNum + 1;
      setCurrentStage(nextStage);

      if (chain) {
        // Auto-advance: run the next un-completed stage after a short delay.
        // Skip stages already done so out-of-order progress isn't re-run.
        const upcoming = stages.find(s => s.stage >= nextStage && s.status !== 'completed');
        if (upcoming) setTimeout(() => runStage(upcoming.stage, true), 1500);
        else { setPipelineRunning(false); setStep('review'); }
      } else {
        setPipelineRunning(false);
      }
    };
    window.addEventListener('agent:done', doneHandler);

    const fallbackTimer = setTimeout(() => {
      window.removeEventListener('agent:done', doneHandler);
      setPipelineRunning(false);
    }, 300000); // 5 min timeout per stage

    // Atomic approach: create conversation + send message in one flow, no events
    try {
      let convId = buildConversationId;
      const tempCampaignId = loadSaved('build_campaign_id', '');

      // Only create a conversation when we genuinely don't have one. A fresh
      // build clears conv_id in handleStartBuild, so this no longer forks a new
      // thread when re-running/retrying stage 1 on an in-progress build. If the
      // persisted id is stale, the backend auto-heals it on POST rather than
      // 404-ing, so reusing it is always safe.
      if (!convId) {
        const { createConversation } = await import('@/lib/api');
        const conv = await createConversation({
          account_id: accountId,
          campaign_id: tempCampaignId || undefined,
          campaign_name: `Build: ${url || 'New Campaign'}`,
          title: `Campaign Build: ${url || 'New Campaign'}`,
        });
        convId = conv.id;
        setBuildConversationId(convId);
      }

      // Send the message directly to the API — bypasses all React state issues
      const msgRes = await fetch(`/api/conversations/${convId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: stage.prompt || `Run stage ${stageNum} for campaign build`,
          account_id: accountId,
          campaign_id: tempCampaignId || undefined,
          model: buildModel,
          active_role: stage.role_id,
        }),
      });

      if (!msgRes.ok) throw new Error(`API error ${msgRes.status}`);

      // Tell ChatPanel to show this conversation (it will load messages from DB)
      window.dispatchEvent(new CustomEvent('chat:display', { detail: { conversationId: convId } }));
    } catch (err) {
      setPipelineRunning(false);
      setStages(prev => prev.map(s => s.stage === stageNum ? { ...s, status: 'error' } : s));
      console.error('Builder send failed:', err);
    } finally {
      // Released once the network send settles — not on stage completion. The
      // next stage's auto-advance runs well after this, so the guard is free.
      stageInFlightRef.current = false;
    }
  }, [stages, buildModel, refreshPipelineStatus, accountId, buildConversationId, url, setBuildConversationId, sessionId, autoMode]);

  // ── INPUT STEP ─────────────────────────────────────────────
  // Short-circuit to the PMax wizard when the user picked PMax. The
  // existing Search wizard's state machine (input → pipeline → review)
  // doesn't apply — PMax has its own asset-bundle flow.
  if (campaignType === 'pmax') {
    return (
      <PMaxWizard
        onClose={onClose}
        onBackToTypePicker={() => {
          persistCampaignType(null);
          setStep('type');
        }}
      />
    );
  }

  // Campaign-type picker — first step on a fresh session.
  if (step === 'type') {
    const TYPE_CARDS: { id: CampaignType; label: string; tagline: string; icon: typeof Search; available: boolean; note?: string }[] = [
      { id: 'search', label: 'Search', tagline: 'Keyword-driven text ads on Google.com', icon: Search, available: true },
      { id: 'pmax',   label: 'Performance Max', tagline: "Google's all-network campaign with auto-placed creative.", icon: Layers, available: true },
      { id: 'video',  label: 'Video (YouTube)', tagline: 'YouTube + Discover video ads.', icon: Video, available: false, note: 'Coming soon — needs YouTube channel linked.' },
    ];
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
            <p className="text-sm text-muted-foreground">Pick a campaign type to start.</p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {TYPE_CARDS.map(({ id, label, tagline, icon: Icon, available, note }) => (
            <button
              key={id}
              disabled={!available}
              onClick={() => {
                if (!available) return;
                persistCampaignType(id);
                setStep('input');
              }}
              className={cn(
                'text-left border rounded-lg p-4 transition-all',
                available
                  ? 'border-border hover:border-primary hover:bg-secondary/50 cursor-pointer'
                  : 'border-border/50 opacity-60 cursor-not-allowed'
              )}
            >
              <Icon className="h-6 w-6 text-primary mb-2" />
              <div className="font-semibold text-sm mb-1">{label}</div>
              <p className="text-xs text-muted-foreground leading-snug">{tagline}</p>
              {note && (
                <p className="text-[10px] text-amber-500/80 mt-2">{note}</p>
              )}
            </button>
          ))}
        </div>
      </div>
    );
  }

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

          {/* Build mode toggle */}
          <div className="flex items-center gap-3 bg-secondary/30 rounded-lg p-3">
            <label className="flex items-center gap-2 cursor-pointer flex-1">
              <input
                type="checkbox"
                checked={autoMode}
                onChange={(e) => setAutoMode(e.target.checked)}
                className="rounded"
              />
              <div>
                <span className="text-sm font-medium">{autoMode ? 'Automatic Mode' : 'Manual Mode'}</span>
                <p className="text-[10px] text-muted-foreground">
                  {autoMode
                    ? 'All 7 stages run non-stop. Review the final plan when done.'
                    : 'You control each stage. Click "Run" to advance, edit between stages.'}
                </p>
              </div>
            </label>
          </div>

          {/* Buttons */}
          <div className="flex gap-3">
          <Button
            onClick={handleStartBuild}
            size="lg"
            className="flex-1 gap-2"
            disabled={(!noLandingPage && !url.trim()) || isStarting}
          >
            <Sparkles className="h-4 w-4" />
            {isStarting
              ? 'Starting…'
              : autoMode ? 'Start Building (Auto)' : 'Start Building (Manual)'}
          </Button>
          <Button
            variant="outline"
            size="lg"
            className="gap-2"
            disabled={!noLandingPage && !url.trim()}
            onClick={async () => {
              const researchPrompt = `Research the market and keywords for a new campaign:\n\nLanding page: ${url || 'Not provided'}\nBrief: ${brief || 'Not specified'}\nTarget: ${geoTargets}\nLanguage: ${languages}\nBudget: $${budget}/day\n\nDo a thorough analysis:\n1. Use keyword_plan_idea__generate_keyword_ideas_from_url to find keyword opportunities from the landing page\n2. Estimate search volume and competition for the top keywords\n3. Identify 3-5 competitor domains and their positioning\n4. Suggest optimal campaign structure (ad groups, match types)\n5. Recommend a realistic CPA target based on the niche\n\nPresent findings as a research report — do NOT create any campaigns yet.`;
              try {
                const { createConversation } = await import('@/lib/api');
                const conv = await createConversation({
                  account_id: accountId,
                  title: `Research: ${url || brief || 'New Campaign'}`,
                });
                await fetch(`/api/conversations/${conv.id}/message`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    content: researchPrompt,
                    account_id: accountId,
                    model: buildModel,
                    active_role: 'competitor_intel',
                  }),
                });
                window.dispatchEvent(new CustomEvent('chat:display', { detail: { conversationId: conv.id } }));
              } catch (err) {
                console.error('Research send failed:', err);
              }
            }}
          >
            <Search className="h-4 w-4" />
            Research First
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
                  // Every stage is independently runnable now — no dimming/lock
                  // on non-active stages.
                  !isActive && !isDone && !isRunning && 'border-border/60',
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

                  {/* Every stage is independently runnable, in any order. A
                      manual click is a one-shot (chain=false) so it doesn't
                      drag the rest of the pipeline. Disabled only while ANY
                      stage is mid-send (one conversation turn at a time). */}
                  {!isRunning && (
                    <Button
                      size="sm"
                      variant={isDone ? 'outline' : 'default'}
                      onClick={() => runStage(stage.stage, false)}
                      disabled={pipelineRunning}
                      className="gap-1"
                    >
                      <Play className="h-3 w-3" />
                      {stage.status === 'error' ? 'Retry' : isDone ? 'Re-run' : 'Run'}
                    </Button>
                  )}
                  {/* Mark done — reconcile a stage whose status detection was
                      wrong (e.g. work already done in a prior session) without
                      having to re-run the agent. Available on any not-done
                      stage, plus the running one (auto-detection fallback). */}
                  {!isDone && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        if (sessionId) {
                          await fetch(`/api/campaigns/build/${sessionId}/stage/${stage.stage}/complete`, { method: 'POST' }).catch(() => {});
                        }
                        setStages(prev => prev.map(s => s.stage === stage.stage ? { ...s, status: 'completed' } : s));
                        if (isRunning) {
                          setPipelineRunning(false);
                          stageInFlightRef.current = false;
                        }
                      }}
                      className="gap-1 text-muted-foreground"
                      title="Mark this stage complete without running the agent"
                    >
                      <CheckCircle2 className="h-3 w-3" />
                      {isRunning ? 'Mark Done' : 'Skip'}
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Progress info */}
        <div className="mt-6 text-center space-y-3">
          <p className="text-xs text-muted-foreground">
            {stages.filter(s => s.status === 'completed').length} of {stages.length} stages completed · Run any agent above in any order, or chain the rest:
          </p>
          <div className="flex gap-2 justify-center">
          {stages.some(s => s.status !== 'completed') && !pipelineRunning && (
            <Button
              size="sm"
              className="gap-1"
              onClick={() => {
                const next = stages.find(s => s.status !== 'completed');
                if (next) runStage(next.stage, true);
              }}
            >
              <Play className="h-3 w-3" />
              Run all remaining (in order)
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            className="gap-1"
            onClick={() => refreshPipelineStatus()}
          >
            <RefreshCw className="h-3 w-3" />
            Refresh Status
          </Button>
          </div>
        </div>
      </div>
    );
  }

  // ── REVIEW STEP ────────────────────────────────────────────
  const handleExportReport = () => {
    const text = `As the Agency Director, compile a COMPLETE CAMPAIGN BUILD REPORT combining ALL role findings into one document:

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
Format as a clean, professional document that could be shared with a client or stakeholder.`;
    window.dispatchEvent(new CustomEvent('chat:send', {
      detail: { text, roleId: 'director', model: buildModel },
    }));
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
          window.dispatchEvent(new CustomEvent('chat:send', {
            detail: { text: 'CREATE the campaign based on the plan above', roleId: 'director', model: buildModel },
          }));
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
