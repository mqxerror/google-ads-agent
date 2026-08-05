/**
 * TargetingFields — shared geo + language targeting controls for the campaign
 * wizards (Demand Gen, RDA, and any future wizard with a Targeting step).
 *
 * Replaces the old raw comma-separated numeric-id inputs ("the language
 * shouldn't be numbers"): languages are a NAMED multi-select (default English),
 * locations use a searchable async picker backed by
 * GeoTargetConstantService.suggest ("Dubai" → the named emirate + city). The
 * component still PERSISTS ids (comma-separated strings) into the wizard bundle
 * — the bundle shape is unchanged, so saved drafts stay compatible — but it
 * DISPLAYS names. A collapsed "advanced: paste ids" section keeps power use.
 *
 * Thin consumers: both DemandGenWizard.StepTargeting and RdaWizard render just
 * <TargetingFields .../>, so the whole feature lives here once.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Globe, Languages, ChevronDown, X, Check, Loader2, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Popover, PopoverContent, PopoverTrigger,
} from '@/components/ui/popover';
import {
  Command, CommandInput, CommandList, CommandEmpty, CommandItem,
} from '@/components/ui/command';
import {
  Collapsible, CollapsibleContent, CollapsibleTrigger,
} from '@/components/ui/collapsible';

// ── shared id-string helpers (bundle stores comma-separated ids) ──────
const parseIds = (raw: string): string[] =>
  raw.split(',').map(s => s.trim()).filter(Boolean);
const joinIds = (ids: string[]): string => ids.join(', ');

interface LanguageOption { id: string; name: string; code: string; }
interface GeoOption {
  id: string; name: string; canonical_name?: string;
  target_type?: string; country_code?: string; reach?: number;
}

export type TargetingField = 'locationIds' | 'excludedLocationIds' | 'languageIds';

// ── Language multi-select (named, default English) ────────────────────

function LanguageMultiSelect({
  value, onChange,
}: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState<LanguageOption[]>([]);
  const selected = parseIds(value);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/targeting/languages')
      .then(r => (r.ok ? r.json() : []))
      .then((data: LanguageOption[]) => { if (!cancelled) setOptions(data); })
      .catch(() => { /* leave empty; advanced paste still works */ });
    return () => { cancelled = true; };
  }, []);

  const nameOf = (id: string) =>
    options.find(o => o.id === id)?.name ?? id;

  const toggle = (id: string) => {
    const next = selected.includes(id)
      ? selected.filter(s => s !== id)
      : [...selected, id];
    onChange(joinIds(next));
  };

  return (
    <div>
      <label className="text-xs font-medium flex items-center gap-1.5 mb-1.5">
        <Languages className="h-3.5 w-3.5" /> Languages
      </label>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button" variant="outline"
            className="w-full justify-between font-normal h-auto min-h-9 py-1.5"
          >
            <span className="flex flex-wrap gap-1 items-center text-left">
              {selected.length === 0
                ? <span className="text-muted-foreground">All languages</span>
                : selected.map(id => (
                    <Badge key={id} variant="secondary" className="gap-1">
                      {nameOf(id)}
                      <X
                        className="h-3 w-3 cursor-pointer opacity-60 hover:opacity-100"
                        onClick={(e) => { e.stopPropagation(); toggle(id); }}
                      />
                    </Badge>
                  ))}
            </span>
            <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <Command>
            <CommandInput placeholder="Search languages..." />
            <CommandList>
              <CommandEmpty>No language found.</CommandEmpty>
              {options.map(o => (
                <CommandItem key={o.id} value={`${o.name} ${o.code}`} onSelect={() => toggle(o.id)}>
                  <Check className={cn('h-4 w-4', selected.includes(o.id) ? 'opacity-100' : 'opacity-0')} />
                  <span>{o.name}</span>
                  <span className="ml-auto text-xs text-muted-foreground">{o.code}</span>
                </CommandItem>
              ))}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}

// ── Geo target picker (searchable, named; include or exclude) ─────────

function GeoTargetPicker({
  value, onChange, label, exclude = false,
}: {
  value: string;
  onChange: (v: string) => void;
  label: string;
  exclude?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GeoOption[]>([]);
  const [loading, setLoading] = useState(false);
  // id → resolved name cache (from suggest results, selections, and resolve).
  const [names, setNames] = useState<Record<string, string>>({});
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const selected = parseIds(value);

  // Resolve any selected ids we don't yet have a name for (draft reload).
  useEffect(() => {
    const missing = selected.filter(id => !names[id]);
    if (missing.length === 0) return;
    let cancelled = false;
    fetch(`/api/targeting/geo/resolve?ids=${encodeURIComponent(missing.join(','))}`)
      .then(r => (r.ok ? r.json() : []))
      .then((data: GeoOption[]) => {
        if (cancelled) return;
        setNames(prev => {
          const next = { ...prev };
          for (const g of data) next[g.id] = g.name;
          return next;
        });
      })
      .catch(() => { /* leave ids showing raw */ });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  // Debounced live suggest.
  useEffect(() => {
    if (!open) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = query.trim();
    if (q.length < 2) { setResults([]); setLoading(false); return; }
    setLoading(true);
    debounceRef.current = setTimeout(() => {
      fetch(`/api/targeting/geo/suggest?q=${encodeURIComponent(q)}`)
        .then(r => (r.ok ? r.json() : []))
        .then((data: GeoOption[]) => {
          setResults(data);
          setNames(prev => {
            const next = { ...prev };
            for (const g of data) next[g.id] = g.name;
            return next;
          });
        })
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, open]);

  const add = (g: GeoOption) => {
    if (selected.includes(g.id)) return;
    setNames(prev => ({ ...prev, [g.id]: g.name }));
    onChange(joinIds([...selected, g.id]));
    setQuery('');
    setResults([]);
  };
  const remove = (id: string) => onChange(joinIds(selected.filter(s => s !== id)));

  const nameOf = (id: string) => names[id] ?? id;

  return (
    <div>
      <label className="text-xs font-medium flex items-center gap-1.5 mb-1.5">
        <Globe className={cn('h-3.5 w-3.5', exclude && 'text-red-500')} /> {label}
      </label>
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1.5">
          {selected.map(id => (
            <Badge key={id} variant={exclude ? 'destructive' : 'secondary'} className="gap-1">
              {nameOf(id)}
              <X
                className="h-3 w-3 cursor-pointer opacity-60 hover:opacity-100"
                onClick={() => remove(id)}
              />
            </Badge>
          ))}
        </div>
      )}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button" variant="outline"
            className="w-full justify-between font-normal text-muted-foreground"
          >
            <span className="flex items-center gap-2">
              <Search className="h-3.5 w-3.5" />
              {exclude ? 'Search a place to exclude...' : 'Search a place to target...'}
            </span>
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput
              placeholder="Type a place, e.g. Dubai"
              value={query}
              onValueChange={setQuery}
            />
            <CommandList>
              {loading && (
                <div className="flex items-center gap-2 py-4 justify-center text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" /> Searching...
                </div>
              )}
              {!loading && query.trim().length < 2 && (
                <div className="py-4 text-center text-sm text-muted-foreground">
                  Type at least 2 characters.
                </div>
              )}
              {!loading && query.trim().length >= 2 && results.length === 0 && (
                <CommandEmpty>No locations found.</CommandEmpty>
              )}
              {!loading && results.map(g => (
                <CommandItem
                  key={g.id}
                  value={g.id}
                  onSelect={() => add(g)}
                  disabled={selected.includes(g.id)}
                >
                  <span className="flex flex-col">
                    <span>{g.canonical_name || g.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {g.target_type}{g.country_code ? ` · ${g.country_code}` : ''}
                    </span>
                  </span>
                  {selected.includes(g.id) && <Check className="ml-auto h-4 w-4" />}
                </CommandItem>
              ))}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}

// ── Composite: the whole Targeting step, one import for every wizard ──

export default function TargetingFields({
  locationIds, excludedLocationIds, languageIds, onChange,
}: {
  locationIds: string;
  excludedLocationIds: string;
  languageIds: string;
  onChange: (field: TargetingField, value: string) => void;
}) {
  const [advOpen, setAdvOpen] = useState(false);
  const set = useCallback(
    (f: TargetingField) => (v: string) => onChange(f, v),
    [onChange],
  );

  return (
    <div className="space-y-4">
      <p className="text-[11px] text-muted-foreground leading-relaxed border border-border bg-secondary/20 rounded-md p-3">
        Targeting is optional — leave locations empty and Google targets all
        regions. Search a place by name to include or exclude it; pick one or
        more languages (defaults to English).
      </p>
      <GeoTargetPicker
        label="Included locations"
        value={locationIds}
        onChange={set('locationIds')}
      />
      <GeoTargetPicker
        label="Excluded locations"
        value={excludedLocationIds}
        onChange={set('excludedLocationIds')}
        exclude
      />
      <LanguageMultiSelect value={languageIds} onChange={set('languageIds')} />

      <Collapsible open={advOpen} onOpenChange={setAdvOpen}>
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
          >
            <ChevronDown className={cn('h-3 w-3 transition-transform', advOpen && 'rotate-180')} />
            Advanced: paste constant ids
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-2 pt-2">
          <div>
            <label className="text-[11px] text-muted-foreground">Included geo ids</label>
            <Input value={locationIds} onChange={e => onChange('locationIds', e.target.value)} placeholder="comma-separated ids" />
          </div>
          <div>
            <label className="text-[11px] text-muted-foreground">Excluded geo ids</label>
            <Input value={excludedLocationIds} onChange={e => onChange('excludedLocationIds', e.target.value)} placeholder="comma-separated ids" />
          </div>
          <div>
            <label className="text-[11px] text-muted-foreground">Language ids</label>
            <Input value={languageIds} onChange={e => onChange('languageIds', e.target.value)} placeholder="comma-separated ids" />
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
