import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, ArrowRight, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

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
  { label: 'Complete', description: 'Setup complete' },
];

export default function SetupWizard() {
  const [step, setStep] = useState(0);
  const [data, setData] = useState<SetupData>(INITIAL_DATA);
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  const update = (field: keyof SetupData, value: string) => {
    setData((prev) => ({ ...prev, [field]: value }));
  };

  const handleFinish = async () => {
    setSaving(true);
    try {
      await fetch('/api/setup/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          developer_token: data.developerToken,
          client_id: data.clientId,
          client_secret: data.clientSecret,
          refresh_token: data.refreshToken,
          login_customer_id: data.loginCustomerId,
        }),
      });
      setStep(1);
    } catch {
      // Handle error
    } finally {
      setSaving(false);
    }
  };

  const canFinish =
    data.developerToken.trim() !== '' &&
    data.clientId.trim() !== '' &&
    data.clientSecret.trim() !== '' &&
    data.refreshToken.trim() !== '' &&
    data.loginCustomerId.trim() !== '';

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-xl">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold mb-1">Google Ads Manager Setup</h1>
          <p className="text-sm text-muted-foreground">
            Enter your Google Ads API credentials to get started
          </p>
        </div>

        <div className="flex items-center justify-center gap-2 mb-8">
          {STEPS.map((_, i) => (
            <div key={i} className="flex items-center gap-2">
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-colors',
                  i < step
                    ? 'bg-status-enabled text-white'
                    : i === step
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary text-muted-foreground'
                )}
              >
                {i < step ? <Check className="h-4 w-4" /> : i + 1}
              </div>
              {i < STEPS.length - 1 && (
                <div className={cn('w-8 h-0.5', i < step ? 'bg-status-enabled' : 'bg-secondary')} />
              )}
            </div>
          ))}
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-base font-medium mb-1">{STEPS[step].label}</h2>
          <p className="text-xs text-muted-foreground mb-6">{STEPS[step].description}</p>

          {step === 0 && (
            <div className="space-y-4">
              <Field label="Developer Token" value={data.developerToken} onChange={(v) => update('developerToken', v)} />
              <Field label="OAuth Client ID" value={data.clientId} onChange={(v) => update('clientId', v)} placeholder="xxxxx.apps.googleusercontent.com" />
              <Field label="OAuth Client Secret" value={data.clientSecret} onChange={(v) => update('clientSecret', v)} type="password" />
              <Field label="Refresh Token" value={data.refreshToken} onChange={(v) => update('refreshToken', v)} type="password" />
              <Field label="Login Customer ID (MCC)" value={data.loginCustomerId} onChange={(v) => update('loginCustomerId', v)} placeholder="1234567890 (no hyphens)" />
              <p className="text-xs text-muted-foreground mt-2">
                These credentials are stored locally and never sent to any third party.
                You can also set them in <code className="text-primary">backend/.env</code> instead.
              </p>
            </div>
          )}

          {step === 1 && (
            <div className="text-center py-8">
              <div className="w-16 h-16 rounded-full bg-status-enabled/20 flex items-center justify-center mx-auto mb-4">
                <Check className="h-8 w-8 text-status-enabled" />
              </div>
              <h3 className="text-lg font-medium mb-2">Setup Complete!</h3>
              <p className="text-sm text-muted-foreground mb-6">
                Your Google Ads Manager is ready to use.
              </p>
              <Button onClick={() => navigate('/')}>
                Go to Dashboard
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          )}
        </div>

        {step === 0 && (
          <div className="flex justify-end mt-4">
            <Button size="sm" disabled={!canFinish || saving} onClick={handleFinish}>
              {saving ? (
                <><Loader2 className="h-4 w-4 mr-1 animate-spin" />Saving...</>
              ) : (
                <><Check className="h-4 w-4 mr-1" />Finish Setup</>
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
