import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Check, X, Loader2, Play, Square } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchSettings, updateSettings, launchChrome, stopChrome } from '@/lib/api';

interface SettingsPageProps {
  onClose: () => void;
}

export default function SettingsPage({ onClose }: SettingsPageProps) {
  const queryClient = useQueryClient();
  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
    staleTime: 5_000,
  });

  const [saving, setSaving] = useState(false);
  const [gtmCommand, setGtmCommand] = useState('');
  const [gtmCommandDirty, setGtmCommandDirty] = useState(false);
  const [chromeAction, setChromeAction] = useState<'idle' | 'launching' | 'stopping'>('idle');
  const [chromeMessage, setChromeMessage] = useState<string | null>(null);

  // Initialize gtmCommand from settings on first load
  if (settings && !gtmCommandDirty && gtmCommand === '' && settings.gtm_mcp_command) {
    setGtmCommand(settings.gtm_mcp_command);
  }

  const handleToggle = async (key: 'chrome_mcp_enabled' | 'gtm_mcp_enabled' | 'chrome_reuse_existing' | 'chrome_use_default_profile', value: boolean) => {
    setSaving(true);
    try {
      await updateSettings({ [key]: value });
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    } finally {
      setSaving(false);
    }
  };

  const handleLaunchChrome = async () => {
    setChromeAction('launching');
    setChromeMessage(null);
    try {
      const result = await launchChrome();
      setChromeMessage(result.message || `Chrome ${result.status}`);
      // Refresh settings to update connection status
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['settings'] }), 1000);
    } catch (e) {
      setChromeMessage(e instanceof Error ? e.message : 'Failed to launch Chrome');
    } finally {
      setChromeAction('idle');
    }
  };

  const handleStopChrome = async () => {
    setChromeAction('stopping');
    setChromeMessage(null);
    try {
      await stopChrome();
      setChromeMessage('Chrome stopped');
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['settings'] }), 500);
    } catch (e) {
      setChromeMessage(e instanceof Error ? e.message : 'Failed to stop Chrome');
    } finally {
      setChromeAction('idle');
    }
  };

  const handleSaveGtmCommand = async () => {
    setSaving(true);
    try {
      await updateSettings({ gtm_mcp_command: gtmCommand });
      setGtmCommandDirty(false);
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!settings) return null;

  const mcpStatus = settings.mcp_status;

  return (
    <div className="h-full overflow-y-auto bg-background">
      {/* Header */}
      <div className="sticky top-0 bg-background border-b border-border px-6 py-4 flex items-center gap-3 z-10">
        <button onClick={onClose} className="p-1 hover:bg-secondary rounded-md transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <h1 className="text-lg font-semibold">Settings</h1>
        {saving && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground ml-2" />}
      </div>

      <div className="max-w-2xl mx-auto px-6 py-6 space-y-8">
        {/* MCP Servers Section */}
        <section>
          <h2 className="text-sm font-semibold mb-1">MCP Servers</h2>
          <p className="text-xs text-muted-foreground mb-4">
            MCP servers give the AI agent direct API access to external services.
            Changes take effect on the next chat message.
          </p>

          <div className="space-y-3">
            {/* Google Ads MCP — always on */}
            <MCPServerCard
              name="Google Ads"
              icon="🔌"
              description="Campaign management, keyword research, ad creation, bidding, reporting"
              tools={mcpStatus.google_ads?.tools}
              enabled={true}
              available={true}
              alwaysOn
            />

            {/* Chrome MCP */}
            <MCPServerCard
              name="Chrome Browser"
              icon="🌐"
              description="Browser automation — navigate GTM UI, audit landing pages, verify tags"
              info={mcpStatus.chrome?.info}
              enabled={settings.chrome_mcp_enabled}
              available={mcpStatus.chrome?.available ?? false}
              reason={mcpStatus.chrome?.reason}
              onToggle={(v) => handleToggle('chrome_mcp_enabled', v)}
            >
              {/* Browser mode toggle */}
              <div className="mt-3 bg-secondary/30 border border-border/50 rounded-md p-3 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium">Reuse my Chrome browser</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {settings.chrome_reuse_existing
                        ? 'Agent uses your open Chrome with logged-in sessions (GTM, Google Ads, etc.)'
                        : 'Agent opens a fresh browser — you\'ll need to log in to each service'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleToggle('chrome_reuse_existing', !settings.chrome_reuse_existing)}
                    className={cn(
                      'relative w-9 h-5 rounded-full transition-colors shrink-0',
                      settings.chrome_reuse_existing ? 'bg-primary' : 'bg-secondary',
                    )}
                  >
                    <span
                      className={cn(
                        'absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform',
                        settings.chrome_reuse_existing ? 'translate-x-4' : 'translate-x-0.5',
                      )}
                    />
                  </button>
                </div>

                {settings.chrome_reuse_existing && (
                  <div className="pt-2 border-t border-border/40 space-y-2">
                    <p className="text-[10px] text-muted-foreground">
                      Opens a dedicated Chrome window for the agent — runs side-by-side with your main Chrome.
                      Log in to Google/GTM once and logins are remembered between sessions.
                    </p>

                    {mcpStatus.chrome?.available ? (
                      <div className="flex items-center justify-between gap-2 bg-status-enabled/10 border border-status-enabled/30 rounded-md px-3 py-2">
                        <span className="text-[11px] flex items-center gap-1.5 text-status-enabled">
                          <Check className="h-3 w-3" /> Chrome is running and connected
                        </span>
                        <button
                          onClick={handleStopChrome}
                          disabled={chromeAction !== 'idle'}
                          className="text-[10px] flex items-center gap-1 px-2 py-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors disabled:opacity-50"
                        >
                          {chromeAction === 'stopping' ? <Loader2 className="h-3 w-3 animate-spin" /> : <Square className="h-3 w-3" />}
                          Stop
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={handleLaunchChrome}
                        disabled={chromeAction !== 'idle'}
                        className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md text-xs font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                      >
                        {chromeAction === 'launching' ? (
                          <><Loader2 className="h-3 w-3 animate-spin" /> Launching Chrome...</>
                        ) : (
                          <><Play className="h-3 w-3" /> Launch Chrome for Agent</>
                        )}
                      </button>
                    )}

                    {chromeMessage && (
                      <p className="text-[10px] text-muted-foreground bg-secondary/40 rounded px-2 py-1.5">
                        {chromeMessage}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </MCPServerCard>

            {/* GTM MCP */}
            <MCPServerCard
              name="Google Tag Manager"
              icon="🏷️"
              description="Programmatic tag management — create/edit/publish tags, triggers, variables"
              tools={mcpStatus.gtm?.tools}
              info={mcpStatus.gtm?.info}
              enabled={settings.gtm_mcp_enabled}
              available={mcpStatus.gtm?.available ?? false}
              reason={mcpStatus.gtm?.reason}
              onToggle={(v) => handleToggle('gtm_mcp_enabled', v)}
            >
              {/* GTM binary path input */}
              <div className="mt-3 space-y-2">
                <label className="text-[11px] text-muted-foreground block">
                  Binary path
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={gtmCommand}
                    onChange={(e) => { setGtmCommand(e.target.value); setGtmCommandDirty(true); }}
                    placeholder="/usr/local/bin/google-tag-manager-mcp"
                    className="flex-1 bg-secondary/50 border border-border rounded-md px-3 py-1.5 text-xs font-mono placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                  {gtmCommandDirty && (
                    <button
                      onClick={handleSaveGtmCommand}
                      className="px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-xs font-medium hover:bg-primary/90 transition-colors"
                    >
                      Save
                    </button>
                  )}
                </div>
                <div className="mt-3 bg-secondary/30 border border-border/50 rounded-md p-3 space-y-2">
                  <p className="text-[11px] font-medium">Setup Guide</p>
                  <ol className="text-[10px] text-muted-foreground space-y-1.5 list-decimal list-inside">
                    <li>
                      <strong>Install Go 1.24+</strong> — <code className="bg-secondary/60 px-1 rounded">brew install go</code> (macOS) or from golang.org
                    </li>
                    <li>
                      <strong>Build the binary:</strong>
                      <pre className="mt-1 bg-background/50 rounded p-1.5 text-[10px] font-mono overflow-x-auto">
{`git clone https://github.com/VasthavM/google-tag-manager-mcp
cd google-tag-manager-mcp
go build -o google-tag-manager-mcp .`}</pre>
                    </li>
                    <li>
                      <strong>Set up Google credentials:</strong>
                      <ul className="mt-1 ml-4 space-y-0.5 list-disc">
                        <li>Go to Google Cloud Console → APIs & Services → Credentials</li>
                        <li>Create OAuth 2.0 Client ID (type: Desktop app)</li>
                        <li>Enable the Tag Manager API in your project</li>
                        <li>Download the credentials JSON file</li>
                        <li>Save to: <code className="bg-secondary/60 px-1 rounded">~/.config/google-tag-manager-mcp/credentials.json</code></li>
                      </ul>
                    </li>
                    <li>
                      <strong>Authenticate (one-time):</strong>
                      <pre className="mt-1 bg-background/50 rounded p-1.5 text-[10px] font-mono">./google-tag-manager-mcp</pre>
                      <span>Opens browser for Google OAuth — grant access and the token saves automatically.</span>
                    </li>
                    <li>
                      <strong>Set the binary path above</strong> and enable the toggle.
                    </li>
                  </ol>
                </div>
              </div>
            </MCPServerCard>
          </div>
        </section>

        {/* Google Ads Credentials */}
        <section>
          <h2 className="text-sm font-semibold mb-1">Google Ads API</h2>
          <p className="text-xs text-muted-foreground mb-4">
            Credentials are configured via the backend .env file.
          </p>

          <div className="bg-card border border-border rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Status</span>
              <span className={cn(
                'text-xs font-medium flex items-center gap-1',
                settings.google_ads_configured ? 'text-status-enabled' : 'text-destructive'
              )}>
                {settings.google_ads_configured ? (
                  <><Check className="h-3 w-3" /> Connected</>
                ) : (
                  <><X className="h-3 w-3" /> Not configured</>
                )}
              </span>
            </div>
            {settings.google_ads_login_customer_id && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Login Customer ID</span>
                <span className="text-xs font-mono">{settings.google_ads_login_customer_id}</span>
              </div>
            )}
            <p className="text-[10px] text-muted-foreground">
              Edit credentials in <code className="bg-secondary/60 px-1 rounded">backend/.env</code> — requires server restart.
            </p>
          </div>
        </section>

        {/* About */}
        <section>
          <h2 className="text-sm font-semibold mb-1">About</h2>
          <div className="bg-card border border-border rounded-lg p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Version</span>
              <span className="text-xs font-mono">2.0.0</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Architecture</span>
              <span className="text-xs">Claude Code CLI + MCP + FastAPI + React</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}


// ── MCP Server Card ────────────────────────────────────────

interface MCPServerCardProps {
  name: string;
  icon: string;
  description: string;
  tools?: string;
  info?: string;
  enabled: boolean;
  available: boolean;
  reason?: string;
  alwaysOn?: boolean;
  onToggle?: (enabled: boolean) => void;
  children?: React.ReactNode;
}

function MCPServerCard({
  name, icon, description, tools, info, enabled, available, reason, alwaysOn, onToggle, children,
}: MCPServerCardProps) {
  return (
    <div className={cn(
      'border rounded-lg p-4 transition-colors',
      enabled ? 'border-border bg-card' : 'border-border/50 bg-card/50 opacity-70',
    )}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <span className="text-lg mt-0.5">{icon}</span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{name}</span>
              {enabled && available && (
                <span className="text-[10px] px-1.5 py-0.5 bg-status-enabled/15 text-status-enabled rounded-full font-medium">
                  connected
                </span>
              )}
              {enabled && !available && !alwaysOn && (
                <span className="text-[10px] px-1.5 py-0.5 bg-yellow-500/15 text-yellow-500 rounded-full font-medium">
                  unavailable
                </span>
              )}
              {alwaysOn && (
                <span className="text-[10px] px-1.5 py-0.5 bg-primary/15 text-primary rounded-full font-medium">
                  always on
                </span>
              )}
            </div>
            <p className="text-[11px] text-muted-foreground mt-0.5">{description}</p>
            {tools && enabled && (
              <p className="text-[10px] text-muted-foreground/70 mt-1">{tools}</p>
            )}
            {reason && enabled && !available && (
              <p className="text-[10px] text-yellow-500/80 mt-1">{reason}</p>
            )}
          </div>
        </div>

        {/* Toggle */}
        {!alwaysOn && onToggle && (
          <button
            onClick={() => onToggle(!enabled)}
            className={cn(
              'relative w-9 h-5 rounded-full transition-colors shrink-0 mt-1',
              enabled ? 'bg-primary' : 'bg-secondary',
            )}
          >
            <span
              className={cn(
                'absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform',
                enabled ? 'translate-x-4' : 'translate-x-0.5',
              )}
            />
          </button>
        )}
      </div>

      {enabled && children}
    </div>
  );
}
