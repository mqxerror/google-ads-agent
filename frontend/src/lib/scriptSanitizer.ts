/**
 * Extract the spoken content from a script generator's output.
 *
 * The script_generator role emits blocks like:
 *
 *   VARIANT A — Family Security Angle
 *   LENGTH: 15s
 *   HOOK: What's your family's Plan B?
 *   SCRIPT: Portugal Golden Visa gets your family an EU passport in 5 years...
 *   CTA: Book a free consultation today.
 *   B-ROLL NOTES: Open on family at airport...
 *
 * If we pass that raw to TTS, the voice reads out "HOOK colon", "CTA colon",
 * and the B-roll stage directions. This parser strips the scaffolding and
 * returns just the spoken line: HOOK + SCRIPT + CTA concatenated with spaces.
 *
 * When the input doesn't look structured, it's returned as-is (minus obvious
 * noise like variant headers and markdown fences).
 */

// Lines that should never be spoken
const NOISE_LINE_PATTERNS = [
  /^---+$/,                        // horizontal rules
  /^VARIANT\s+[A-Z0-9]/i,          // "VARIANT A"
  /^LENGTH\s*:/i,
  /^B-?ROLL(\s+NOTES)?\s*:/i,
  /^Word\s+count\s*:/i,
  /^```/,                          // markdown code fences
  /^\s*$/,                         // blank
];

// Prefixes we want to keep the content of, not the label itself
const SPOKEN_PREFIXES = [/^HOOK\s*:\s*/i, /^SCRIPT\s*:\s*/i, /^CTA\s*:\s*/i];

function stripMarkdown(s: string): string {
  return s
    .replace(/\*\*(.+?)\*\*/g, '$1')   // bold
    .replace(/\*(.+?)\*/g, '$1')        // italic
    .replace(/^[-*•]\s+/, '')           // leading bullets
    .replace(/^\s*\d+[.)]\s+/, '')      // leading "1." / "1)"
    .trim();
}

export interface SanitizedScript {
  spoken: string;       // the text that should actually be sent to TTS
  hadStructure: boolean; // whether we detected and parsed a structured block
}

export function sanitizeScript(raw: string): SanitizedScript {
  const text = (raw ?? '').trim();
  if (!text) return { spoken: '', hadStructure: false };

  // Detect the structured format — look for SCRIPT: marker as the strongest signal
  const hasStructure = /^\s*SCRIPT\s*:/im.test(text);

  if (hasStructure) {
    // Only read the FIRST variant if multiple are present
    const firstVariantEnd = text.search(/\n\s*(?:---+|VARIANT\s+[A-Z0-9])/i);
    const section = firstVariantEnd > 0 ? text.slice(0, firstVariantEnd) : text;

    const lines = section.split('\n').map(stripMarkdown);
    const parts: string[] = [];

    for (const raw of lines) {
      const line = raw.trim();
      if (!line) continue;
      if (NOISE_LINE_PATTERNS.some(re => re.test(line))) continue;

      // Pull out the content after the label for spoken prefixes
      let matched = false;
      for (const re of SPOKEN_PREFIXES) {
        if (re.test(line)) {
          const content = line.replace(re, '').trim();
          if (content) parts.push(content);
          matched = true;
          break;
        }
      }
      if (matched) continue;

      // Lines without a known prefix in a structured block are likely extra
      // commentary ("Want me to adjust...", italic notes) — skip them.
      if (/^[A-Z][A-Z\s-]+:/.test(line)) continue; // unknown "LABEL:" line
    }

    return { spoken: parts.join(' ').replace(/\s+/g, ' ').trim(), hadStructure: true };
  }

  // No structured markers — treat whole thing as spoken text, but strip common noise
  const cleaned = text
    .split('\n')
    .map(stripMarkdown)
    .filter(line => line && !NOISE_LINE_PATTERNS.some(re => re.test(line)))
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();

  return { spoken: cleaned, hadStructure: false };
}
