"""PMax orchestrator server.

Wraps `PMaxOrchestrator` (the recipe that batches budget + campaign +
assets + asset_group + asset_group_assets into one transactional flow)
as a FastMCP sub-server, mounted under the `core` group in mcp_main.py.
"""

from fastmcp import FastMCP

from google_ads.services.campaign.pmax_orchestrator import register_pmax_tools

pmax_server = FastMCP(name="pmax-orchestrator-service")

register_pmax_tools(pmax_server)
