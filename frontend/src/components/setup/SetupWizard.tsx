import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, ArrowRight, Loader2, AlertTriangle, Scan } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { addAccount, onboardAccount } from '@/lib/api';
import type { OnboardingResult, CampaignGoal } from '@/types';

interface SetupData {
  developerToken: string;
  clientId: string;
  clientSecret: string;
  refreshToken: string;
  loginCustomerId: string;
}

const INITIAL_DATA: SetupData = {
  developerToken: '',
  clientId: '',
  clientSecret: '',
  refreshToken: '',
  loginCustomerId: '',
};

const STEPS = [
  { label: 'Credentials', description: 'Google Ads API credentials' },
  { label: 'Validate', description: 'Connect and verify' },
  { label: 'Onboarding', description: 'Scanning campaigns' },
  { label: 'Complete', description: 'Ready to go' },
];

const PHASE_COLORS: Record<string, string> = {
  launch: 'text-blue-500 bg-blue-500/10',
  learning: 'text-yellow-500 bg-yellow-500/10',
  optimization: 'text-green-500 bg-green-500/10',
  scaling: 'text-purple-500 bg-purple-500/10',
  sunset: 'text-muted-foreground bg-secondary',
  unknown: 'text-muted-foreground bg-secondary',
};

export default function SetupWizard() {
  const [step, setStep] = useState(0);
  const [data, setData] = useState<SetupData>(INITIAL_DATA);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [accountId, setAccountId] = useState('');
  const [onboardResult, setOnboardResult] = useState<OnboardingResult | null>(null);
  const navigate = useNavigate();

  const update = (field: keyof SetupData, value: string) => {
    setData((prev) => ({ ...prev, [field]: value }));
    setError('');
  };

  const handleValidate = async () => {
    setSaving(true);
    setError('');
    try {
      const account = await addAccount({
        developer_token: data.developerToken,
        client_id: data.clientId,
        client_secret: data.clientSecret,
        refresh_token: data.refreshToken,
        login_customer_id: data.loginCustomerId,
      });
      setAccountId(account.id);
      setStep(2);

      // Auto-start onboarding
      try {
        const result = await onboardAccount(account.id);
        setOnboardResult(result);
        setStep(3);
      } catch (e: any) {
        // Onboarding failed but account was added — still usable
        setOnboardResult({
          account_id: account.id,
          account_name: account.name,
          campaigns_found: 0,
          campaigns: [],
          guidelines_generated: [],
        });
        setStep(3);
      }
    } catch (e: any) {
      setError(e.message || 'Failed to connect. Check your credentials.');
    } finally {
      setSaving(false);
    }
  };

  const canValidate =
    data.developerToken.trim() !== '' &&
    data.clientId.trim() !== '' &&
    data.clientSecret.trim() !== '' &&
    data.refreshToken.trim() !== '' &&
    data.loginCustomerId.trim() !== '';

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-xl">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold mb-1">Google Ads Agent Setup</h1>
          <p className="text-sm text-muted-foreground">
            Connect your Google Ads account to get started
          </p>
        </div>

        {/* Step indicators */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {STEPS.map((_, i) => (
            <div key={i} className="flex items-center gap-2">
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-colors',
                  i < step
                    ? 'bg-green-500 text-white'
                    : i === step
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary text-muted-foreground'
                )}
              >
                {i < step ? <Check className="h-4 w-4" /> : i + 1}
              </div>
              {i < STEPS.length - 1 && (
                <div className={cn('w-8 h-0.5', i < step ? 'bg-green-500' : 'bg-secondary')} />
              )}
            </div>
          ))}
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-base font-medium mb-1">{STEPS[step].label}</h2>
          <p className="text-xs text-muted-foreground mb-6">{STEPS[step].description}</p>

          {/* Step 0: Credentials */}
          {step === 0 && (
            <div className="space-y-4">
              <Field label="Developer Token" value={data.developerToken} onChange={(v) => update('developerToken', v)} />
              <Field label="OAuth Client ID" value={data.clientId} onChange={(v) => update('clientId', v)} placeholder="xxxxx.apps.googleusercontent.com" />
              <Field label="OAuth Client Secret" value={data.clientSecret} onChange={(v) => update('clientSecret', v)} type="password" />
              <Field label="Refresh Token" value={data.refreshToken} onChange={(v) => update('refreshToken', v)} type="password" />
              <Field label="Login Customer ID (MCC)" value={data.loginCustomerId} onChange={(v) => update('loginCustomerId', v)} placeholder="1234567890 (no hyphens)" />
              <p className="text-xs text-muted-foreground mt-2">
                Credentials are encrypted and stored locally. Never sent to any third party.
              </p>
            </div>
          )}

          {/* Step 1: Validating (shown briefly during API call) */}
          {step === 1 && (
            <div className="text-center py-8">
              <Loader2 className="h-8 w-8 mx-auto mb-4 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">Validating credentials...</p>
            </div>
          )}

          {/* Step 2: Onboarding scan in progress */}
          {step === 2 && (
            <div className="text-center py-8">
              <Scan className="h-8 w-8 mx-auto mb-4 animate-pulse text-primary" />
              <p className="text-sm font-medium mb-2">Smart Onboarding</p>
              <p className="text-xs text-muted-foreground">
                Scanning campaigns, detecting goals and phases, generating guidelines...
              </p>
            </div>
          )}

          {/* Step 3: Complete */}
          {step === 3 && onboardResult && (
            <div className="space-y-4">
              <div className="text-center mb-4">
                <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-3">
                  <Check className="h-8 w-8 text-green-500" />
                </div>
                <h3 className="text-lg font-medium">Account Connected!</h3>
                <p className="text-sm text-muted-foreground">
                  Found {onboardResult.campaigns_found} campaign{onboardResult.campaigns_found !== 1 ? 's' : ''}
                  {onboardResult.guidelines_generated.length > 0 && (
                    <span> — {onboardResult.guidelines_generated.length} guideline file{onboardResult.guidelines_generated.length !== 1 ? 's' : ''} generated</span>
                  )}
                </p>
              </div>

              {/* Campaign summary with detected goals/phases */}
              {onboardResult.campaigns.length > 0 && (
                <div className="max-h-48 overflow-y-auto border border-border rounded-md">
                  <table className="w-full text-xs">
                    <thead className="bg-secondary sticky top-0">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">Campaign</th>
                        <th className="text-left px-3 py-2 font-medium">Goal</th>
                        <th className="text-left px-3 py-2 font-medium">Phase</th>
                      </tr>
                    </thead>
                    <tbody>
                      {onboardResult.campaigns.slice(0, 20).map((c) => (
                        <tr key={c.campaign_id} className="border-t border-border">
                          <td className="px-3 py-1.5 truncate max-w-[200px]">{c.campaign_name}</td>
                          <td className="px-3 py-1.5 text-muted-foreground">{c.objective.replace('_', ' ')}</td>
                          <td className="px-3 py-1.5">
                            <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium', PHASE_COLORS[c.phase] || PHASE_COLORS.unknown)}>
                              {c.phase}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {onboardResult.campaigns.length > 20 && (
                    <p className="text-[10px] text-muted-foreground text-center py-1">
                      + {onboardResult.campaigns.length - 20} more campaigns
                    </p>
                  )}
                </div>
              )}

              <div className="flex justify-center pt-2">
                <Button onClick={() => navigate('/')}>
                  Go to Dashboard
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Error display */}
        {error && (
          <div className="mt-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
            <p className="text-xs text-destructive">{error}</p>
          </div>
        )}

        {/* Action button */}
        {step === 0 && (
          <div className="flex justify-between mt-4">
            <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
              Back
            </Button>
            <Button size="sm" disabled={!canValidate || saving} onClick={handleValidate}>
              {saving ? (
                <><Loader2 className="h-4 w-4 mr-1 animate-spin" />Connecting...</>
              ) : (
                <>Connect Account<ArrowRight className="h-4 w-4 ml-1" /></>
              )}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({
  label, value, onChange, type = 'text', placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-muted-foreground mb-1.5">{label}</label>
      <Input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="bg-secondary/50 border-border" />
    </div>
  );
}
