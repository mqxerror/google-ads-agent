// BrandPresetToggle (Epic 16, story 16.5) — extracted 1:1 from DemandGenWizard's
// corporate-brand checkbox so BOTH wizards drive the same image preset from ONE
// component (FR1.12). When ON, generated images use the corporate/editorial,
// text-free preset (Google renders the headline itself, so baked-in text gets
// disapproved).

export default function BrandPresetToggle({
  checked, onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-2 cursor-pointer select-none border border-border rounded-md p-3 bg-secondary/20">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} className="mt-0.5" />
      <span>
        <span className="text-xs font-medium">Corporate-brand images</span>
        <span className="block text-[10px] text-muted-foreground mt-0.5">
          Generated images use the premium, editorial, text-free preset (Google renders the headline
          itself, so baked-in text gets disapproved). Turn off for a looser creative style.
        </span>
      </span>
    </label>
  );
}
