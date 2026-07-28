"""Demand Gen orchestrator server.

Wraps `DemandGenOrchestrator` (the recipe that batches budget + campaign +
targeting + image assets + ad group with channel controls + multi-asset ad +
audience criteria into one transactional flow) as a FastMCP sub-server,
mounted under the `core` group in mcp_main.py.
"""

from fastmcp import FastMCP

from google_ads.services.campaign.demand_gen_orchestrator import (
    register_demand_gen_tools,
)

demand_gen_server = FastMCP(name="demand-gen-orchestrator-service")

register_demand_gen_tools(demand_gen_server)
