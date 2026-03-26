import { useState } from 'react';
import { format, subDays, startOfMonth } from 'date-fns';
import { CalendarIcon } from 'lucide-react';
import type { DateRange } from 'react-day-picker';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';

const presets = [
  { label: 'Today', getDates: () => ({ from: new Date(), to: new Date() }) },
  { label: 'Yesterday', getDates: () => ({ from: subDays(new Date(), 1), to: subDays(new Date(), 1) }) },
  { label: 'Last 7 days', getDates: () => ({ from: subDays(new Date(), 6), to: new Date() }) },
  { label: 'Last 14 days', getDates: () => ({ from: subDays(new Date(), 13), to: new Date() }) },
  { label: 'Last 30 days', getDates: () => ({ from: subDays(new Date(), 29), to: new Date() }) },
  { label: 'This month', getDates: () => ({ from: startOfMonth(new Date()), to: new Date() }) },
];

interface DateRangePickerProps {
  dateRange: DateRange | undefined;
  onDateRangeChange: (range: DateRange | undefined) => void;
}

export default function DateRangePicker({ dateRange, onDateRangeChange }: DateRangePickerProps) {
  const [open, setOpen] = useState(false);
  // Local state to allow picking from+to before committing
  const [localRange, setLocalRange] = useState<DateRange | undefined>(dateRange);

  const handleOpen = (isOpen: boolean) => {
    if (isOpen) {
      setLocalRange(dateRange);
    }
    setOpen(isOpen);
  };

  const applyRange = (range: DateRange | undefined) => {
    onDateRangeChange(range);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={handleOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn(
            'justify-start text-left font-normal text-xs gap-2 h-8',
            !dateRange && 'text-muted-foreground',
          )}
        >
          <CalendarIcon className="h-3.5 w-3.5" />
          {dateRange?.from ? (
            dateRange.to ? (
              <>
                {format(dateRange.from, 'MMM d, yyyy')} – {format(dateRange.to, 'MMM d, yyyy')}
              </>
            ) : (
              format(dateRange.from, 'MMM d, yyyy')
            )
          ) : (
            'Select date range'
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-auto p-0"
        align="end"
        onInteractOutside={(e) => {
          // Prevent closing when clicking inside the popover content
          e.preventDefault();
        }}
        onPointerDownOutside={(e) => {
          // Only close if clicking outside the popover entirely
          const target = e.target as HTMLElement;
          if (target.closest('[data-slot="calendar"]') || target.closest('[data-radix-popper-content-wrapper]')) {
            e.preventDefault();
          }
        }}
      >
        <div className="flex">
          {/* Presets */}
          <div className="border-r border-border p-2 space-y-1 min-w-[130px]">
            <p className="text-xs font-medium text-muted-foreground px-2 py-1">Quick Select</p>
            {presets.map((preset) => (
              <Button
                key={preset.label}
                variant="ghost"
                size="sm"
                className="w-full justify-start text-xs h-7"
                onClick={() => {
                  const range = preset.getDates();
                  applyRange(range);
                }}
              >
                {preset.label}
              </Button>
            ))}
          </div>
          {/* Calendar */}
          <div className="p-2">
            <Calendar
              mode="range"
              defaultMonth={localRange?.from ?? subDays(new Date(), 30)}
              selected={localRange}
              onSelect={(range) => {
                setLocalRange(range);
                // Auto-apply when both dates selected
                if (range?.from && range?.to) {
                  applyRange(range);
                }
              }}
              numberOfMonths={2}
              disabled={{ after: new Date() }}
            />
            {/* Apply / Cancel buttons for when only one date picked */}
            <div className="flex justify-end gap-2 px-2 pt-2 border-t border-border mt-2">
              <Button
                variant="ghost"
                size="sm"
                className="text-xs h-7"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                className="text-xs h-7"
                disabled={!localRange?.from}
                onClick={() => {
                  // If only from is selected, use it as both from and to
                  const range = localRange?.from
                    ? { from: localRange.from, to: localRange.to ?? localRange.from }
                    : localRange;
                  applyRange(range);
                }}
              >
                Apply
              </Button>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
