/**
 * Agent Identity System — each role has a human persona.
 *
 * Names, titles, colors, and avatar initials give each agent
 * a recognizable identity in the chat and reports.
 */

export interface AgentProfile {
  id: string;
  name: string;
  title: string;
  initials: string;
  color: string;      // Text/accent color
  bgColor: string;    // Background color for avatar
  borderColor: string; // Border accent
  emoji: string;      // Fallback emoji
  specialty: string;
}

export const AGENT_PROFILES: Record<string, AgentProfile> = {
  director: {
    id: 'director',
    name: 'Alex Morgan',
    title: 'Agency Director',
    initials: 'AM',
    color: '#475569',
    bgColor: '#F1F5F9',
    borderColor: '#94A3B8',
    emoji: '💼',
    specialty: 'Routing, synthesis, campaign oversight',
  },
  ppc_strategist: {
    id: 'ppc_strategist',
    name: 'Sarah Chen',
    title: 'PPC Strategist',
    initials: 'SC',
    color: '#2563EB',
    bgColor: '#EFF6FF',
    borderColor: '#3B82F6',
    emoji: '🎯',
    specialty: 'Bidding, budget allocation, campaign structure',
  },
  search_term_hunter: {
    id: 'search_term_hunter',
    name: 'Marcus Rivera',
    title: 'Search Term Hunter',
    initials: 'MR',
    color: '#059669',
    bgColor: '#ECFDF5',
    borderColor: '#10B981',
    emoji: '🔍',
    specialty: 'Negative keywords, match types, query analysis',
  },
  creative_director: {
    id: 'creative_director',
    name: 'Lina Dubois',
    title: 'Creative Director',
    initials: 'LD',
    color: '#7C3AED',
    bgColor: '#F5F3FF',
    borderColor: '#8B5CF6',
    emoji: '🎨',
    specialty: 'Ad copy, A/B testing, messaging strategy',
  },
  analytics_analyst: {
    id: 'analytics_analyst',
    name: 'James Park',
    title: 'Analytics Analyst',
    initials: 'JP',
    color: '#4338CA',
    bgColor: '#EEF2FF',
    borderColor: '#6366F1',
    emoji: '📊',
    specialty: 'Attribution, funnel analysis, data insights',
  },
  video_director: {
    id: 'video_director',
    name: 'Video Director',
    title: 'Video Director',
    initials: 'VD',
    color: '#4F46E5',
    bgColor: '#EEF0FF',
    borderColor: '#818CF8',
    emoji: '🎬',
    specialty: 'Storyboarding, scene direction, generative video',
  },
  competitor_intel: {
    id: 'competitor_intel',
    name: 'Nadia Kowalski',
    title: 'Competitor Intel',
    initials: 'NK',
    color: '#E11D48',
    bgColor: '#FFF1F2',
    borderColor: '#F43F5E',
    emoji: '👁️',
    specialty: 'Market research, auction insights, competitive gaps',
  },
  gtm_specialist: {
    id: 'gtm_specialist',
    name: 'Dev Patel',
    title: 'GTM Specialist',
    initials: 'DP',
    color: '#0891B2',
    bgColor: '#ECFEFF',
    borderColor: '#06B6D4',
    emoji: '💻',
    specialty: 'Tag management, conversion tracking, Clarity',
  },
  growth_hacker: {
    id: 'growth_hacker',
    name: 'Yuki Tanaka',
    title: 'Growth Hacker',
    initials: 'YT',
    color: '#EA580C',
    bgColor: '#FFF7ED',
    borderColor: '#F97316',
    emoji: '🚀',
    specialty: 'Scaling strategies, experiments, expansion',
  },
  script_generator: {
    id: 'script_generator',
    name: 'Kai Nakamura',
    title: 'Video Script Generator',
    initials: 'KN',
    color: '#DB2777',
    bgColor: '#FDF2F8',
    borderColor: '#EC4899',
    emoji: '🎬',
    specialty: 'Short video ad scripts tuned for spoken pace',
  },
  cro_specialist: {
    id: 'cro_specialist',
    name: 'Elena Rossi',
    title: 'CRO Specialist',
    initials: 'ER',
    color: '#0D9488',
    bgColor: '#F0FDFA',
    borderColor: '#14B8A6',
    emoji: '📏',
    specialty: 'Landing page optimization, conversion rate, UX audit',
  },
};

/**
 * Get an agent profile by role ID. Falls back to Director for unknown roles.
 */
export function getAgentProfile(roleId: string | undefined): AgentProfile {
  if (!roleId) return AGENT_PROFILES.director;
  return AGENT_PROFILES[roleId] || AGENT_PROFILES.director;
}

/**
 * Get profile from role name (e.g. "PPC Strategist" → ppc_strategist profile)
 */
export function getAgentProfileByName(roleName: string | undefined): AgentProfile {
  if (!roleName) return AGENT_PROFILES.director;
  const entry = Object.values(AGENT_PROFILES).find(
    p => p.title.toLowerCase() === roleName.toLowerCase()
  );
  return entry || AGENT_PROFILES.director;
}
