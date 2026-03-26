import { useState, type ReactNode } from 'react';
import { Eye, Edit3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import GuidelinesEditor from './GuidelinesEditor';

const MOCK_GUIDELINES = `# Campaign Guidelines

## Target Audience
- High-net-worth individuals looking for EU residency
- Investors interested in real estate opportunities in Portugal
- Families seeking access to European education and healthcare

## Messaging Guidelines
- Always emphasize **security** and **legitimacy** of the Golden Visa program
- Highlight the benefits: EU travel, tax advantages, quality of life
- Use professional, trustworthy tone
- Avoid aggressive sales language

## Budget Rules
- Maintain daily budget between $100-$200 per campaign
- Pause keywords with CPA above $250
- Allocate more budget to high-converting ad groups

## Keyword Strategy
- Focus on exact match for high-intent keywords
- Use phrase match for medium-intent queries
- Broad match only with smart bidding enabled
- Negative keywords: "free", "cheap", "scam", "review"

## Ad Copy Best Practices
- Include year in headlines (e.g., "2025")
- Always have a clear CTA: "Free Consultation", "Book a Call"
- Test at least 3 ad variations per ad group
- Highlight unique selling propositions:
  - 15 years of experience
  - 98% approval rate
  - 500+ families served
`;

export default function GuidelinesViewer() {
  const [editMode, setEditMode] = useState(false);
  const [content, setContent] = useState(MOCK_GUIDELINES);

  if (editMode) {
    return (
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium">Edit Guidelines</h3>
          <Button
            variant="outline"
            size="sm"
            className="text-xs gap-1.5"
            onClick={() => setEditMode(false)}
          >
            <Eye className="h-3.5 w-3.5" />
            View
          </Button>
        </div>
        <GuidelinesEditor content={content} onChange={setContent} />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium">Guidelines</h3>
        <Button
          variant="outline"
          size="sm"
          className="text-xs gap-1.5"
          onClick={() => setEditMode(true)}
        >
          <Edit3 className="h-3.5 w-3.5" />
          Edit
        </Button>
      </div>
      <div className="bg-card border border-border rounded-lg p-6 prose-sm">
        <MarkdownRenderer content={content} />
      </div>
    </div>
  );
}

/** Minimal markdown-to-HTML renderer */
function MarkdownRenderer({ content }: { content: string }) {
  const lines = content.split('\n');
  const elements: ReactNode[] = [];
  let key = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('# ')) {
      elements.push(
        <h1 key={key++} className="text-xl font-bold mb-3 mt-4 first:mt-0">
          {line.slice(2)}
        </h1>
      );
    } else if (line.startsWith('## ')) {
      elements.push(
        <h2 key={key++} className="text-base font-semibold mb-2 mt-4">
          {line.slice(3)}
        </h2>
      );
    } else if (line.startsWith('- ')) {
      elements.push(
        <li key={key++} className="text-sm text-foreground/80 ml-4 mb-1 list-disc">
          {renderInline(line.slice(2))}
        </li>
      );
    } else if (line.startsWith('  - ')) {
      elements.push(
        <li key={key++} className="text-sm text-foreground/80 ml-8 mb-1 list-disc">
          {renderInline(line.slice(4))}
        </li>
      );
    } else if (line.trim() === '') {
      elements.push(<div key={key++} className="h-2" />);
    } else {
      elements.push(
        <p key={key++} className="text-sm text-foreground/80 mb-2">
          {renderInline(line)}
        </p>
      );
    }
  }

  return <>{elements}</>;
}

function renderInline(text: string): (string | ReactNode)[] {
  const parts: (string | ReactNode)[] = [];
  let remaining = text;
  let k = 0;

  while (remaining.length > 0) {
    const boldStart = remaining.indexOf('**');
    if (boldStart === -1) {
      parts.push(remaining);
      break;
    }
    const boldEnd = remaining.indexOf('**', boldStart + 2);
    if (boldEnd === -1) {
      parts.push(remaining);
      break;
    }
    if (boldStart > 0) parts.push(remaining.slice(0, boldStart));
    parts.push(
      <strong key={k++} className="font-semibold text-foreground">
        {remaining.slice(boldStart + 2, boldEnd)}
      </strong>
    );
    remaining = remaining.slice(boldEnd + 2);
  }
  return parts;
}
