/**
 * Conversations — the routed home for the Conversation Map (Epic 13,
 * Story 13.5). The map used to dominate the old Account Overview; it's
 * an archive that answers "where did I talk", not "what should I do", so
 * v2 moves it off the home to its own page reachable from the header nav.
 *
 * The existing ConversationGraph component is hosted UNCHANGED — this
 * page is just a titled frame around it.
 */

import { ArrowLeft, GitBranch } from 'lucide-react';
import { useAppStore } from '@/stores/appStore';
import ConversationGraph from '@/components/dashboard/ConversationGraph';

export default function ConversationsPage() {
  const { setShowConversations } = useAppStore();
  return (
    <div className="mx-auto max-w-[1000px] px-6 py-6">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-lg font-semibold text-foreground">
            <GitBranch className="h-5 w-5 text-accent" />
            Conversations
          </h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Every thread, grouped by campaign, with the decisions and actions it produced.
          </p>
        </div>
        <button
          onClick={() => setShowConversations(false)}
          className="flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to home
        </button>
      </div>
      <ConversationGraph />
    </div>
  );
}
