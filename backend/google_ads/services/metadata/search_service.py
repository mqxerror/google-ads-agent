"""Search service implementation using Google Ads SDK."""

from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastmcp import Context, FastMCP
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v23.enums.types.keyword_plan_network import (
    KeywordPlanNetworkEnum,
)
from google.ads.googleads.v23.services.services.google_ads_service import (
    GoogleAdsServiceClient,
)
from google.ads.googleads.v23.services.types.google_ads_service import (
    GoogleAdsRow,
    SearchGoogleAdsRequest,
)
from google.ads.googleads.v23.services.types.keyword_plan_idea_service import (
    GenerateKeywordIdeasRequest,
    KeywordAndUrlSeed,
    KeywordSeed,
    UrlSeed,
)

from google_ads.sdk_client import get_sdk_client
from google_ads.utils import format_customer_id, get_logger, serialize_proto_message

logger = get_logger(__name__)


class SearchService:
    """Search service for querying Google Ads data."""

    def __init__(self) -> None:
        """Initialize the search service."""
        self._client: Optional[GoogleAdsServiceClient] = None

    @property
    def client(self) -> GoogleAdsServiceClient:
        """Get the Google Ads service client."""
        if self._client is None:
            sdk_client = get_sdk_client()
            self._client = sdk_client.client.get_service("GoogleAdsService")
        assert self._client is not None
        return self._client

    async def search_campaigns(
        self,
        ctx: Context,
        customer_id: str,
        include_removed: bool = False,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Search for campaigns in a customer account.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            include_removed: Whether to include removed campaigns
            limit: Maximum number of results to return

        Returns:
            List of campaign details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Build query
            query = """
                SELECT
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    campaign.advertising_channel_type,
                    campaign.campaign_budget,
                    campaign_budget.amount_micros,
                    campaign.start_date,
                    campaign.end_date
                FROM campaign
            """

            if not include_removed:
                query += " WHERE campaign.status != 'REMOVED'"

            query += f" ORDER BY campaign.id LIMIT {limit}"

            # Create request
            request = SearchGoogleAdsRequest()
            request.customer_id = customer_id
            request.query = query

            # Execute search
            response = self.client.search(request=request)

            # Process results
            results: List[Dict[str, Any]] = []
            row: GoogleAdsRow
            for row in response:
                results.append(serialize_proto_message(row))

            await ctx.log(
                level="info",
                message=f"Found {len(results)} campaigns for customer {customer_id}",
            )

            return results

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to search campaigns: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def search_ad_groups(
        self,
        ctx: Context,
        customer_id: str,
        campaign_id: Optional[str] = None,
        include_removed: bool = False,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Search for ad groups.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            campaign_id: Optional campaign ID to filter by
            include_removed: Whether to include removed ad groups
            limit: Maximum number of results to return

        Returns:
            List of ad group details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Build query
            query = """
                SELECT
                    ad_group.id,
                    ad_group.name,
                    ad_group.status,
                    ad_group.campaign,
                    ad_group.type,
                    ad_group.cpc_bid_micros,
                    ad_group.cpm_bid_micros,
                    campaign.id,
                    campaign.name
                FROM ad_group
            """

            conditions: List[str] = []
            if not include_removed:
                conditions.append("ad_group.status != 'REMOVED'")

            if campaign_id:
                conditions.append(f"campaign.id = {campaign_id}")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += f" ORDER BY ad_group.id LIMIT {limit}"

            # Create request
            request = SearchGoogleAdsRequest()
            request.customer_id = customer_id
            request.query = query

            # Execute search
            response = self.client.search(request=request)

            # Process results
            results: List[Dict[str, Any]] = []
            row: GoogleAdsRow
            for row in response:
                results.append(serialize_proto_message(row))

            await ctx.log(
                level="info",
                message=f"Found {len(results)} ad groups",
            )

            return results

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to search ad groups: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def search_keywords(
        self,
        ctx: Context,
        customer_id: str,
        ad_group_id: Optional[str] = None,
        include_negative: bool = False,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Search for keywords.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            ad_group_id: Optional ad group ID to filter by
            include_negative: Whether to include negative keywords
            limit: Maximum number of results to return

        Returns:
            List of keyword details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Build query
            query = """
                SELECT
                    ad_group_criterion.criterion_id,
                    ad_group_criterion.keyword.text,
                    ad_group_criterion.keyword.match_type,
                    ad_group_criterion.status,
                    ad_group_criterion.negative,
                    ad_group_criterion.cpc_bid_micros,
                    ad_group.id,
                    ad_group.name,
                    campaign.id,
                    campaign.name
                FROM ad_group_criterion
                WHERE ad_group_criterion.type = 'KEYWORD'
            """

            if not include_negative:
                query += " AND ad_group_criterion.negative = false"

            if ad_group_id:
                query += f" AND ad_group.id = {ad_group_id}"

            query += f" ORDER BY ad_group_criterion.criterion_id LIMIT {limit}"

            # Create request
            request = SearchGoogleAdsRequest()
            request.customer_id = customer_id
            request.query = query

            # Execute search
            response = self.client.search(request=request)

            # Process results
            results: List[Dict[str, Any]] = []
            row: GoogleAdsRow
            for row in response:
                results.append(serialize_proto_message(row))

            await ctx.log(
                level="info",
                message=f"Found {len(results)} keywords",
            )

            return results

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to search keywords: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def execute_query(
        self,
        ctx: Context,
        customer_id: str,
        query: str,
        page_size: int = 0,
    ) -> List[Dict[str, Any]]:
        """Execute a custom GAQL query.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            query: The GAQL (Google Ads Query Language) query
            page_size: DEPRECATED / ignored. The Google Ads API no longer supports
                a client-set page size on Search and rejects any non-zero value with
                PAGE_SIZE_NOT_SUPPORTED (fixed server-side page size of 10000). The
                param is retained for backward compatibility but is never applied;
                the SDK response iterator auto-paginates across all rows.

        Returns:
            List of query results as dictionaries
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Create request. NOTE: request.page_size is intentionally NOT set —
            # the Google Ads API raises PAGE_SIZE_NOT_SUPPORTED for any client-set
            # value; the search() iterator paginates automatically.
            request = SearchGoogleAdsRequest()
            request.customer_id = customer_id
            request.query = query

            # Execute search
            response = self.client.search(request=request)

            # Process results
            results: List[Dict[str, Any]] = []
            row: GoogleAdsRow
            for row in response:
                # Serialize the entire row using proto-plus serialization
                try:
                    row_dict = serialize_proto_message(row)
                    results.append(row_dict)
                except Exception as e:
                    # Fallback to manual extraction if serialization fails
                    await ctx.log(
                        level="warning",
                        message=f"Could not serialize row, using fallback: {str(e)}",
                    )
                    # Convert GoogleAdsRow to dictionary manually
                    row_dict: Dict[str, Any] = {}

                    # Common fields that might be in the query
                    field_names = [
                        "campaign",
                        "ad_group",
                        "ad_group_criterion",
                        "keyword_view",
                        "metrics",
                        "segments",
                        "customer",
                        "campaign_budget",
                        "bidding_strategy",
                        "ad",
                        "asset",
                        "user_list",
                    ]

                    for field_name in field_names:
                        if hasattr(row, field_name):
                            field_value = getattr(row, field_name)
                            if field_value is not None:
                                try:
                                    # Try to serialize the field
                                    row_dict[field_name] = serialize_proto_message(
                                        field_value
                                    )
                                except Exception:
                                    # If serialization fails, skip this field
                                    pass

                    if row_dict:
                        results.append(row_dict)

            await ctx.log(
                level="info",
                message=f"Query returned {len(results)} rows",
            )

            return results

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to execute query: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def list_accessible_customers(
        self,
        ctx: Context,
    ) -> Dict[str, Any]:
        """List accounts accessible to the authenticated OAuth identity.

        Read-only. Calls CustomerService.ListAccessibleCustomers, which uses only
        the developer token + OAuth refresh token (no customer_id / login_customer_id
        required) — the credential-free account-discovery bootstrap.

        Returns:
            {"resource_names": [...], "customer_ids": [...]}
        """
        try:
            sdk_client = get_sdk_client()
            customer_service = sdk_client.client.get_service("CustomerService")
            response = customer_service.list_accessible_customers()

            resource_names: List[str] = list(response.resource_names)
            customer_ids = [rn.split("/")[-1] for rn in resource_names]

            await ctx.log(
                level="info",
                message=f"Found {len(resource_names)} accessible customer(s)",
            )

            return {
                "resource_names": resource_names,
                "customer_ids": customer_ids,
            }

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to list accessible customers: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def generate_keyword_ideas(
        self,
        ctx: Context,
        customer_id: str,
        keywords: Optional[List[str]] = None,
        page_url: Optional[str] = None,
        geo_target: str = "2124",
        language: str = "1000",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Research keyword ideas via KeywordPlanIdeaService.GenerateKeywordIdeas.

        Read-only demand research: given seed keywords and/or a landing-page URL,
        returns related keyword ideas with search volume, competition, and
        top-of-page bid estimates. GenerateKeywordIdeas MUTATES NOTHING — no
        keyword plan is created, no campaign / criterion is touched — so this is
        safe on the read surface (the CMO's keyword-research tool).

        Args:
            ctx: FastMCP context
            customer_id: Account the research is billed to. Must be a NON-manager
                account (the API rejects MCC ids); the login_customer_id / MCC
                header is supplied by the SDK client config, not here.
            keywords: Optional list of seed keywords to expand.
            page_url: Optional landing-page URL to derive ideas from. At least one
                of `keywords` or `page_url` must be given.
            geo_target: Geo target constant id (bare numeric; expanded to
                geoTargetConstants/<id>). Default "2124" = Canada ("2840" = US).
            language: Language constant id (bare numeric; expanded to
                languageConstants/<id>). Default "1000" = English.
            limit: Max number of ideas to return (API page size, max 10000).

        Returns:
            List of rows: {text, avg_monthly_searches, competition,
            low_top_of_page_bid_micros, high_top_of_page_bid_micros}.
        """
        if not keywords and not page_url:
            raise Exception(
                "generate_keyword_ideas requires at least one of `keywords` or "
                "`page_url` as a seed."
            )
        try:
            customer_id = format_customer_id(customer_id)

            # Build request. Ids arrive bare (e.g. "2124") and are expanded to the
            # resource-name form the API expects.
            request = GenerateKeywordIdeasRequest()
            request.customer_id = customer_id
            request.language = f"languageConstants/{language}"
            request.geo_target_constants.append(f"geoTargetConstants/{geo_target}")
            request.keyword_plan_network = (
                KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH_AND_PARTNERS
            )
            request.page_size = limit

            # Pick the seed by what was provided (keywords + url / keywords / url).
            if keywords and page_url:
                keyword_and_url_seed = KeywordAndUrlSeed()
                keyword_and_url_seed.keywords.extend(keywords)
                keyword_and_url_seed.url = page_url
                request.keyword_and_url_seed = keyword_and_url_seed
            elif keywords:
                keyword_seed = KeywordSeed()
                keyword_seed.keywords.extend(keywords)
                request.keyword_seed = keyword_seed
            else:
                url_seed = UrlSeed()
                url_seed.url = page_url
                request.url_seed = url_seed

            # KeywordPlanIdeaService is a distinct service from GoogleAdsService.
            sdk_client = get_sdk_client()
            kp_idea_client = sdk_client.client.get_service("KeywordPlanIdeaService")
            response = kp_idea_client.generate_keyword_ideas(request=request)

            # The response iterator auto-paginates, so cap total rows at `limit`.
            results: List[Dict[str, Any]] = []
            for idea in response:
                if len(results) >= limit:
                    break
                metrics = idea.keyword_idea_metrics
                results.append(
                    {
                        "text": idea.text,
                        "avg_monthly_searches": metrics.avg_monthly_searches
                        if metrics
                        else None,
                        "competition": metrics.competition.name
                        if metrics and metrics.competition
                        else None,
                        "low_top_of_page_bid_micros": metrics.low_top_of_page_bid_micros
                        if metrics
                        else None,
                        "high_top_of_page_bid_micros": (
                            metrics.high_top_of_page_bid_micros if metrics else None
                        ),
                    }
                )

            await ctx.log(
                level="info",
                message=(
                    f"Generated {len(results)} keyword ideas for customer "
                    f"{customer_id}"
                ),
            )

            return results

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to generate keyword ideas: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e


def create_search_tools(service: SearchService) -> List[Callable[..., Awaitable[Any]]]:
    """Create tool functions for the search service.

    This returns a list of tool functions that can be registered with FastMCP.
    This approach makes the tools testable by allowing service injection.
    """
    tools: List[Callable[..., Awaitable[Any]]] = []

    async def search_campaigns(
        ctx: Context,
        customer_id: str,
        include_removed: bool = False,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Search for campaigns in a customer account.

        Args:
            customer_id: The customer ID
            include_removed: Whether to include removed campaigns
            limit: Maximum number of results to return

        Returns:
            List of campaign details with id, name, status, budget, etc.
        """
        return await service.search_campaigns(
            ctx=ctx,
            customer_id=customer_id,
            include_removed=include_removed,
            limit=limit,
        )

    async def search_ad_groups(
        ctx: Context,
        customer_id: str,
        campaign_id: Optional[str] = None,
        include_removed: bool = False,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Search for ad groups.

        Args:
            customer_id: The customer ID
            campaign_id: Optional campaign ID to filter by
            include_removed: Whether to include removed ad groups
            limit: Maximum number of results to return

        Returns:
            List of ad group details with id, name, status, bids, etc.
        """
        return await service.search_ad_groups(
            ctx=ctx,
            customer_id=customer_id,
            campaign_id=campaign_id,
            include_removed=include_removed,
            limit=limit,
        )

    async def search_keywords(
        ctx: Context,
        customer_id: str,
        ad_group_id: Optional[str] = None,
        include_negative: bool = False,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Search for keywords.

        Args:
            customer_id: The customer ID
            ad_group_id: Optional ad group ID to filter by
            include_negative: Whether to include negative keywords
            limit: Maximum number of results to return

        Returns:
            List of keyword details with text, match type, bid, etc.
        """
        return await service.search_keywords(
            ctx=ctx,
            customer_id=customer_id,
            ad_group_id=ad_group_id,
            include_negative=include_negative,
            limit=limit,
        )

    async def execute_query(
        ctx: Context,
        customer_id: str,
        query: str,
        page_size: int = 0,
    ) -> List[Dict[str, Any]]:
        """Execute a custom GAQL (Google Ads Query Language) query.

        Args:
            customer_id: The customer ID
            query: The GAQL query to execute
            page_size: DEPRECATED / ignored (the Google Ads API fixes page size at
                10000 and rejects any client-set value; the SDK auto-paginates).

        Returns:
            List of query results as dictionaries

        Example queries:
            - "SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status = 'ENABLED'"
            - "SELECT metrics.clicks, metrics.impressions FROM campaign WHERE segments.date DURING LAST_7_DAYS"
        """
        return await service.execute_query(
            ctx=ctx,
            customer_id=customer_id,
            query=query,
            page_size=page_size,
        )

    async def list_accessible_customers(
        ctx: Context,
    ) -> Dict[str, Any]:
        """List the Google Ads accounts the authenticated OAuth identity can access.

        Read-only account-discovery bootstrap that needs NO customer_id: it calls
        CustomerService.ListAccessibleCustomers using only the developer token +
        OAuth refresh token. Returns the accessible customer resource names and
        their bare 10-digit ids (typically the manager/MCC), which callers then
        expand into the full account tree via
        `execute_query(customer_id=<mcc>, query="... FROM customer_client")`.

        Returns:
            {"resource_names": ["customers/1234567890", ...],
             "customer_ids": ["1234567890", ...]}
        """
        return await service.list_accessible_customers(ctx=ctx)

    async def generate_keyword_ideas(
        ctx: Context,
        customer_id: str,
        keywords: Optional[List[str]] = None,
        page_url: Optional[str] = None,
        geo_target: str = "2124",
        language: str = "1000",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Research keyword ideas (search volume + competition + bid estimates).

        Read-only keyword research via KeywordPlanIdeaService.GenerateKeywordIdeas,
        which mutates nothing (no keyword plan, campaign, or criterion is created).
        Seed with `keywords`, a `page_url`, or both — at least one is required.

        Args:
            customer_id: A NON-manager account id the research is billed to (the
                API rejects MCC ids; the login_customer_id header comes from the
                SDK config, not this arg).
            keywords: Optional seed keywords to expand (e.g.
                ["golden visa portugal"]).
            page_url: Optional landing-page URL to derive ideas from.
            geo_target: Geo target constant id, bare numeric (default "2124" =
                Canada; "2840" = US).
            language: Language constant id, bare numeric (default "1000" = English).
            limit: Max ideas to return (default 50).

        Returns:
            List of {text, avg_monthly_searches, competition,
            low_top_of_page_bid_micros, high_top_of_page_bid_micros}.
        """
        return await service.generate_keyword_ideas(
            ctx=ctx,
            customer_id=customer_id,
            keywords=keywords,
            page_url=page_url,
            geo_target=geo_target,
            language=language,
            limit=limit,
        )

    tools.extend(
        [
            search_campaigns,
            search_ad_groups,
            search_keywords,
            execute_query,
            list_accessible_customers,
            generate_keyword_ideas,
        ]
    )
    return tools


def register_search_tools(mcp: FastMCP[Any]) -> SearchService:
    """Register search tools with the MCP server.

    Returns the SearchService instance for testing purposes.
    """
    service = SearchService()
    tools = create_search_tools(service)

    # Register each tool
    for tool in tools:
        mcp.tool(tool)

    return service
