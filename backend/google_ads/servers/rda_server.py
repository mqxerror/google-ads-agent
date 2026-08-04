"""Responsive Display Ad orchestrator server.

Wraps ``RdaOrchestrator`` (the recipe that batches budget + campaign + targeting
+ image assets + ad group + responsive display ad into one transactional flow)
as a FastMCP sub-server, mounted under the `core` group in mcp_main.py.
"""

from fastmcp import FastMCP

from google_ads.services.campaign.rda_orchestrator import register_rda_tools

rda_server = FastMCP(name="rda-orchestrator-service")

register_rda_tools(rda_server)
