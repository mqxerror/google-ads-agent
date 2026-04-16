/**
 * Human-readable descriptions for MCP tool calls.
 * Shows what the agent is doing in real-time.
 */

export const TOOL_DESCRIPTIONS: Record<string, string> = {
  // Google Ads MCP — Reading
  'google_ads_search_google_ads': '📊 Running GAQL query...',
  'search_search_campaigns': '📊 Fetching campaigns...',
  'search_search_ad_groups': '📊 Loading ad groups...',
  'search_search_keywords': '🔍 Loading keywords...',
  'search_execute_query': '📊 Executing query...',

  // Google Ads MCP — Creating
  'budget_create_campaign_budget': '💰 Creating campaign budget...',
  'campaign_create_campaign': '🚀 Creating campaign...',
  'ad_group_create_ad_group': '📁 Creating ad group...',
  'keyword_add_keywords': '➕ Adding keywords...',
  'ad_create_responsive_search_ad': '📝 Creating responsive search ad...',

  // Google Ads MCP — Modifying
  'campaign_update_campaign': '⚙️ Updating campaign...',
  'ad_group_update_ad_group': '⚙️ Updating ad group...',
  'keyword_update_keyword_bid': '💰 Updating keyword bid...',
  'keyword_remove_keyword': '🗑️ Removing keyword...',
  'campaign_criterion_add_negative_keyword_criteria': '🚫 Adding negative keywords...',
  'campaign_criterion_add_location_criteria': '📍 Setting location targeting...',
  'ad_update_ad_status': '⚙️ Updating ad status...',

  // Google Ads MCP — Advanced
  'keyword_plan_idea_generate_keyword_ideas_from_keywords': '💡 Researching keyword ideas...',
  'keyword_plan_idea_generate_keyword_ideas_from_url': '💡 Researching keywords from URL...',
  'recommendation_get_recommendations': '💡 Fetching Google recommendations...',
  'recommendation_apply_recommendation': '✅ Applying recommendation...',
  'geo_target_search_geo_targets': '🌍 Searching geo targets...',
  'conversion_create_conversion_action': '🎯 Creating conversion action...',
  'customer_list_accessible_customers': '👥 Listing accounts...',

  // Chrome MCP — Browser
  'new_page': '🌐 Opening new browser tab...',
  'navigate_page': '🌐 Navigating to page...',
  'take_screenshot': '📸 Taking screenshot...',
  'take_snapshot': '📄 Reading page DOM...',
  'click': '👆 Clicking element...',
  'fill': '✏️ Filling form field...',
  'type_text': '⌨️ Typing text...',
  'evaluate_script': '💻 Running JavaScript...',
  'list_network_requests': '🔍 Checking network requests...',
  'list_console_messages': '📋 Reading console logs...',
  'lighthouse_audit': '🔬 Running Lighthouse audit...',
  'wait_for': '⏳ Waiting for element...',
  'select_page': '🔄 Switching tab...',
  'hover': '👆 Hovering element...',

  // GTM MCP
  'list_containers': '🏷️ Listing GTM containers...',
  'list_tags': '🏷️ Loading GTM tags...',
  'list_triggers': '🏷️ Loading triggers...',
  'create_tag': '🏷️ Creating GTM tag...',
  'create_trigger': '🏷️ Creating trigger...',
  'publish_version': '🚀 Publishing GTM version...',

  // Clarity MCP
  'get_project_info': '📊 Fetching Clarity project info...',
  'get_heatmap_data': '🔥 Loading heatmap data...',
  'get_session_recordings': '🎥 Fetching session recordings...',
  'get_metrics_summary': '📊 Loading engagement metrics...',
};

/**
 * Get a human-readable description for a tool call.
 * Falls back to formatted tool name if no description exists.
 */
export function getToolDescription(toolName: string): string {
  // Try exact match
  if (TOOL_DESCRIPTIONS[toolName]) return TOOL_DESCRIPTIONS[toolName];

  // Try without prefix (e.g. "search_campaigns" from "google_ads_search_campaigns")
  const parts = toolName.split('_');
  if (parts.length > 2) {
    const short = parts.slice(1).join('_');
    if (TOOL_DESCRIPTIONS[short]) return TOOL_DESCRIPTIONS[short];
  }

  // Fallback: format the name
  const formatted = toolName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  return `⚙️ ${formatted}...`;
}

/**
 * Get the icon for a tool source.
 */
export function getSourceIcon(source: string): string {
  switch (source) {
    case 'google-ads-mcp': return '📊';
    case 'chrome': return '🌐';
    case 'gtm': return '🏷️';
    case 'clarity': return '🔥';
    default: return '⚙️';
  }
}
