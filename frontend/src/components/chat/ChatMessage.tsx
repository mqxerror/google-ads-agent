import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';
import ToolCallBlock from './ToolCallBlock';
import type { ChatMessage as ChatMessageType } from '@/types';

interface ChatMessageProps {
  message: ChatMessageType;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('px-3 py-2', isUser ? 'flex justify-end' : '')}>
      <div
        className={cn(
          'rounded-lg px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'max-w-[85%] bg-primary text-primary-foreground'
            : 'w-full bg-secondary/40 text-foreground'
        )}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{message.content}</div>
        ) : (
          <div className="prose prose-sm prose-invert max-w-none
            [&_h1]:text-base [&_h1]:font-bold [&_h1]:mt-4 [&_h1]:mb-2
            [&_h2]:text-sm [&_h2]:font-bold [&_h2]:mt-4 [&_h2]:mb-2
            [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-3 [&_h3]:mb-1
            [&_h4]:text-xs [&_h4]:font-semibold [&_h4]:mt-3 [&_h4]:mb-1 [&_h4]:text-muted-foreground
            [&_p]:my-1.5 [&_p]:text-sm
            [&_ul]:my-1.5 [&_ul]:pl-4 [&_ul]:text-sm
            [&_ol]:my-1.5 [&_ol]:pl-4 [&_ol]:text-sm
            [&_li]:my-0.5
            [&_strong]:text-foreground [&_strong]:font-semibold
            [&_hr]:my-3 [&_hr]:border-border
            [&_table]:text-xs [&_table]:w-full [&_table]:my-2
            [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:font-medium [&_th]:border-b [&_th]:border-border [&_th]:text-muted-foreground
            [&_td]:px-2 [&_td]:py-1 [&_td]:border-b [&_td]:border-border/50
            [&_code]:text-xs [&_code]:bg-background/50 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded
            [&_pre]:bg-background/50 [&_pre]:rounded-md [&_pre]:p-3 [&_pre]:my-2 [&_pre]:overflow-x-auto
            [&_blockquote]:border-l-2 [&_blockquote]:border-primary/50 [&_blockquote]:pl-3 [&_blockquote]:italic [&_blockquote]:text-muted-foreground
          ">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.toolCalls.map((tc) => (
              <ToolCallBlock key={tc.id} toolCall={tc} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
