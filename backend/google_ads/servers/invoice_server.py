"""Invoice server using SDK implementation."""

from fastmcp import FastMCP

from google_ads.services.account.invoice_service import (
    register_invoice_tools,
)

# Create the invoice server
invoice_server = FastMCP(name="invoice-service")

# Register the tools
register_invoice_tools(invoice_server)
