"""Asset service implementation using Google Ads SDK."""

from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastmcp import Context, FastMCP
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v23.common.types.asset_types import (
    CallAsset,
    CalloutAsset,
    ImageAsset,
    SitelinkAsset,
    StructuredSnippetAsset,
    TextAsset,
    YoutubeVideoAsset,
)
from google.ads.googleads.v23.enums.types.asset_type import AssetTypeEnum
from google.ads.googleads.v23.resources.types.asset import Asset
from google.ads.googleads.v23.services.services.asset_service import (
    AssetServiceClient,
)
from google.ads.googleads.v23.services.services.google_ads_service import (
    GoogleAdsServiceClient,
)
from google.ads.googleads.v23.services.types.asset_service import (
    AssetOperation,
    MutateAssetsRequest,
    MutateAssetsResponse,
)
from google.ads.googleads.v23.services.types.ad_group_asset_service import (
    AdGroupAssetOperation,
    MutateAdGroupAssetsRequest,
)
from google.ads.googleads.v23.services.types.campaign_asset_service import (
    CampaignAssetOperation,
    MutateCampaignAssetsRequest,
)
from google.ads.googleads.v23.services.types.customer_asset_service import (
    CustomerAssetOperation,
    MutateCustomerAssetsRequest,
)
from google.protobuf import field_mask_pb2

from google_ads.sdk_client import get_sdk_client
from google_ads.utils import format_customer_id, get_logger, serialize_proto_message

logger = get_logger(__name__)

# ── Per-type mutable-field map (encodes Google's asset immutability rules) ─────
# Only these typed fields may be edited in place per asset type. Anything else
# (notably IMAGE media bytes) is immutable — the operator must create a new
# asset instead. ``name`` is editable for EVERY type (it lives on the Asset
# resource) and is therefore not listed here.
ASSET_TYPE_MUTABLE_FIELDS: Dict[str, List[str]] = {
    "SITELINK": ["link_text", "description1", "description2", "final_urls"],
    "CALLOUT": ["callout_text"],
    "STRUCTURED_SNIPPET": ["header", "values"],
    "CALL": ["phone_number", "country_code"],
    "IMAGE": [],  # name ONLY — media bytes are immutable
}

# Map each typed field back to the asset type that owns it (for inference +
# cross-type mixing rejection when ``asset_type`` is not supplied explicitly).
_FIELD_TO_TYPE: Dict[str, str] = {
    field: asset_type
    for asset_type, fields in ASSET_TYPE_MUTABLE_FIELDS.items()
    for field in fields
}

# Char limits enforced BEFORE mutation (Google rejects over-limit text anyway,
# but a local check gives a clear message instead of an opaque API error).
_ASSET_CHAR_LIMITS: Dict[str, int] = {
    "link_text": 25,
    "description1": 35,
    "description2": 35,
    "callout_text": 25,
}
_SNIPPET_VALUE_MAX = 25

# The Google Ads "ad text symbol" ban applies to displayed text fields (not to
# phone numbers or URLs). Repeated/gimmicky symbols like these are disallowed.
_BANNED_TEXT_SYMBOLS = set("~|+")
# Displayed-text fields the symbol ban + (where applicable) char limit cover.
_TEXT_DISPLAY_FIELDS = {
    "name",
    "link_text",
    "description1",
    "description2",
    "callout_text",
    "header",
}


class AssetService:
    """Asset service for managing Google Ads assets (images, videos, text)."""

    def __init__(self) -> None:
        """Initialize the asset service."""
        self._client: Optional[AssetServiceClient] = None

    @property
    def client(self) -> AssetServiceClient:
        """Get the asset service client."""
        if self._client is None:
            sdk_client = get_sdk_client()
            self._client = sdk_client.client.get_service("AssetService")
        assert self._client is not None
        return self._client

    async def create_text_asset(
        self,
        ctx: Context,
        customer_id: str,
        text: str,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a text asset.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            text: The text content
            name: Optional name for the asset

        Returns:
            Created asset details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Create asset
            asset = Asset()
            asset.type_ = AssetTypeEnum.AssetType.TEXT

            # Set name if provided
            if name:
                asset.name = name
            else:
                asset.name = f"Text: {text[:50]}"  # Use first 50 chars as name

            # Create text asset
            text_asset = TextAsset()
            text_asset.text = text
            asset.text_asset = text_asset

            # Create operation
            operation = AssetOperation()
            operation.create = asset

            # Create request
            request = MutateAssetsRequest()
            request.customer_id = customer_id
            request.operations = [operation]

            # Make the API call
            response: MutateAssetsResponse = self.client.mutate_assets(request=request)
            return serialize_proto_message(response)

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to create text asset: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def create_image_asset(
        self,
        ctx: Context,
        customer_id: str,
        image_data: bytes,
        name: str,
        mime_type: str = "image/jpeg",
    ) -> Dict[str, Any]:
        """Create an image asset.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            image_data: The image data as bytes
            name: Name for the asset
            mime_type: MIME type (image/jpeg, image/png, etc.)

        Returns:
            Created asset details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Create asset
            asset = Asset()
            asset.type_ = AssetTypeEnum.AssetType.IMAGE
            asset.name = name

            # Create image asset
            image_asset = ImageAsset()
            image_asset.data = image_data
            image_asset.mime_type = self.get_mime_type_enum(mime_type)
            asset.image_asset = image_asset

            # Create operation
            operation = AssetOperation()
            operation.create = asset

            # Create request
            request = MutateAssetsRequest()
            request.customer_id = customer_id
            request.operations = [operation]

            # Make the API call
            response: MutateAssetsResponse = self.client.mutate_assets(request=request)

            return serialize_proto_message(response)

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to create image asset: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def create_youtube_video_asset(
        self,
        ctx: Context,
        customer_id: str,
        youtube_video_id: str,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a YouTube video asset.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            youtube_video_id: The YouTube video ID
            name: Optional name for the asset

        Returns:
            Created asset details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Create asset
            asset = Asset()
            asset.type_ = AssetTypeEnum.AssetType.YOUTUBE_VIDEO

            # Set name
            if name:
                asset.name = name
            else:
                asset.name = f"YouTube: {youtube_video_id}"

            # Create YouTube video asset
            youtube_video = YoutubeVideoAsset()
            youtube_video.youtube_video_id = youtube_video_id
            asset.youtube_video_asset = youtube_video

            # Create operation
            operation = AssetOperation()
            operation.create = asset

            # Create request
            request = MutateAssetsRequest()
            request.customer_id = customer_id
            request.operations = [operation]

            # Make the API call
            response: MutateAssetsResponse = self.client.mutate_assets(request=request)
            return serialize_proto_message(response)

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to create YouTube video asset: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def create_sitelink_asset(
        self,
        ctx: Context,
        customer_id: str,
        link_text: str,
        description1: str = "",
        description2: str = "",
        final_urls: Optional[List[str]] = None,
        name: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict[str, Any]:
        """Create a sitelink asset (sitelink ad extension).

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            link_text: The displayed sitelink text (max 25 chars)
            description1: Optional first description line (max 35 chars)
            description2: Optional second description line (max 35 chars)
            final_urls: Landing page URL(s) the sitelink points to
            name: Optional name for the asset
            validate_only: If true, the request is validated but not executed.

        Returns:
            Created asset details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Create asset
            asset = Asset()
            asset.type_ = AssetTypeEnum.AssetType.SITELINK

            # Set name if provided
            if name:
                asset.name = name
            else:
                asset.name = f"Sitelink: {link_text[:50]}"

            # Create sitelink asset
            sitelink_asset = SitelinkAsset()
            sitelink_asset.link_text = link_text
            if description1:
                sitelink_asset.description1 = description1
            if description2:
                sitelink_asset.description2 = description2
            asset.sitelink_asset = sitelink_asset

            # final_urls live on the Asset message, not the SitelinkAsset
            if final_urls:
                asset.final_urls.extend(final_urls)

            # Create operation
            operation = AssetOperation()
            operation.create = asset

            # Create request
            request = MutateAssetsRequest()
            request.customer_id = customer_id
            request.operations = [operation]
            request.validate_only = validate_only

            # Make the API call
            response: MutateAssetsResponse = self.client.mutate_assets(request=request)
            return serialize_proto_message(response)

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to create sitelink asset: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def create_callout_asset(
        self,
        ctx: Context,
        customer_id: str,
        callout_text: str,
        name: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict[str, Any]:
        """Create a callout asset (callout ad extension).

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            callout_text: The callout text (max 25 chars)
            name: Optional name for the asset
            validate_only: If true, the request is validated but not executed.

        Returns:
            Created asset details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Create asset
            asset = Asset()
            asset.type_ = AssetTypeEnum.AssetType.CALLOUT

            # Set name if provided
            if name:
                asset.name = name
            else:
                asset.name = f"Callout: {callout_text[:50]}"

            # Create callout asset
            callout_asset = CalloutAsset()
            callout_asset.callout_text = callout_text
            asset.callout_asset = callout_asset

            # Create operation
            operation = AssetOperation()
            operation.create = asset

            # Create request
            request = MutateAssetsRequest()
            request.customer_id = customer_id
            request.operations = [operation]
            request.validate_only = validate_only

            # Make the API call
            response: MutateAssetsResponse = self.client.mutate_assets(request=request)
            return serialize_proto_message(response)

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to create callout asset: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def create_structured_snippet_asset(
        self,
        ctx: Context,
        customer_id: str,
        header: str,
        values: Optional[List[str]] = None,
        name: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict[str, Any]:
        """Create a structured snippet asset (structured snippet ad extension).

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            header: A predefined snippet header (e.g. "Services", "Brands",
                "Destinations"). Passed through — the API validates it.
            values: The snippet values displayed under the header (up to 10)
            name: Optional name for the asset
            validate_only: If true, the request is validated but not executed.

        Returns:
            Created asset details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Create asset
            asset = Asset()
            asset.type_ = AssetTypeEnum.AssetType.STRUCTURED_SNIPPET

            # Set name if provided
            if name:
                asset.name = name
            else:
                asset.name = f"Structured Snippet: {header[:50]}"

            # Create structured snippet asset
            structured_snippet_asset = StructuredSnippetAsset()
            structured_snippet_asset.header = header
            if values:
                structured_snippet_asset.values.extend(values)
            asset.structured_snippet_asset = structured_snippet_asset

            # Create operation
            operation = AssetOperation()
            operation.create = asset

            # Create request
            request = MutateAssetsRequest()
            request.customer_id = customer_id
            request.operations = [operation]
            request.validate_only = validate_only

            # Make the API call
            response: MutateAssetsResponse = self.client.mutate_assets(request=request)
            return serialize_proto_message(response)

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to create structured snippet asset: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def create_call_asset(
        self,
        ctx: Context,
        customer_id: str,
        phone_number: str,
        country_code: str,
        name: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict[str, Any]:
        """Create a call asset (call ad extension).

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            phone_number: The raw phone number (e.g. "+1 800 555 0100")
            country_code: The 2-letter uppercase country code (e.g. "US")
            name: Optional name for the asset
            validate_only: If true, the request is validated but not executed.

        Returns:
            Created asset details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Create asset
            asset = Asset()
            asset.type_ = AssetTypeEnum.AssetType.CALL

            # Set name if provided
            if name:
                asset.name = name
            else:
                asset.name = f"Call: {phone_number[:50]}"

            # Create call asset
            call_asset = CallAsset()
            call_asset.phone_number = phone_number
            call_asset.country_code = country_code
            asset.call_asset = call_asset

            # Create operation
            operation = AssetOperation()
            operation.create = asset

            # Create request
            request = MutateAssetsRequest()
            request.customer_id = customer_id
            request.operations = [operation]
            request.validate_only = validate_only

            # Make the API call
            response: MutateAssetsResponse = self.client.mutate_assets(request=request)
            return serialize_proto_message(response)

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to create call asset: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def update_asset(
        self,
        ctx: Context,
        customer_id: str,
        asset_id: Optional[str] = None,
        asset_resource_name: Optional[str] = None,
        asset_type: Optional[str] = None,
        name: Optional[str] = None,
        link_text: Optional[str] = None,
        description1: Optional[str] = None,
        description2: Optional[str] = None,
        final_urls: Optional[List[str]] = None,
        callout_text: Optional[str] = None,
        header: Optional[str] = None,
        values: Optional[List[str]] = None,
        phone_number: Optional[str] = None,
        country_code: Optional[str] = None,
        image_data: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Edit an existing asset in place via an update_mask mutate.

        Mirrors the field-mask idiom shipped for ads (update_ad_final_urls) and
        conversion actions (primary_for_goal): ONLY the fields explicitly
        provided enter the mask; ``None`` means untouched. Encodes Google's
        per-type immutability rules (see ASSET_TYPE_MUTABLE_FIELDS): IMAGE media
        bytes are immutable — passing ``image_data`` is rejected.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            asset_id: The asset ID (with customer_id → resource name) OR pass
                ``asset_resource_name`` directly
            asset_resource_name: Full asset resource name; overrides asset_id
            asset_type: Optional explicit type (SITELINK/CALLOUT/
                STRUCTURED_SNIPPET/CALL/IMAGE). When omitted the type is inferred
                from the provided typed fields; supplying it enables strict
                per-type field validation (e.g. IMAGE → name only).
            name: New asset name (editable for every asset type)
            link_text/description1/description2/final_urls: SITELINK fields
            callout_text: CALLOUT field
            header/values: STRUCTURED_SNIPPET fields
            phone_number/country_code: CALL fields
            image_data: REJECTED — image bytes are immutable

        Returns:
            Updated asset details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # ── Reject immutable image media up front ────────────────
            if image_data is not None:
                raise ValueError(
                    "Image asset media bytes are immutable in Google Ads. "
                    "Create a new image asset instead (create_image_asset); "
                    "only an image asset's name can be edited."
                )

            # ── Resolve the asset resource name ──────────────────────
            if asset_resource_name:
                resource_name = asset_resource_name
            elif asset_id:
                resource_name = f"customers/{customer_id}/assets/{asset_id}"
            else:
                raise ValueError(
                    "Provide either asset_resource_name or asset_id"
                )

            # ── Gather provided typed fields ─────────────────────────
            typed_values: Dict[str, Any] = {
                "link_text": link_text,
                "description1": description1,
                "description2": description2,
                "final_urls": final_urls,
                "callout_text": callout_text,
                "header": header,
                "values": values,
                "phone_number": phone_number,
                "country_code": country_code,
            }
            provided = {k: v for k, v in typed_values.items() if v is not None}

            # ── Determine / validate the asset type ──────────────────
            if asset_type is not None:
                asset_type = asset_type.upper()
                if asset_type not in ASSET_TYPE_MUTABLE_FIELDS:
                    raise ValueError(
                        f"Unsupported asset_type {asset_type!r}; editable types: "
                        f"{', '.join(ASSET_TYPE_MUTABLE_FIELDS)}"
                    )
                allowed = set(ASSET_TYPE_MUTABLE_FIELDS[asset_type])
                bad = [f for f in provided if f not in allowed]
                if bad:
                    if asset_type == "IMAGE":
                        raise ValueError(
                            "IMAGE assets: only 'name' is editable "
                            "(media bytes are immutable). Rejected fields: "
                            f"{', '.join(bad)}"
                        )
                    raise ValueError(
                        f"Fields {', '.join(bad)} are not valid for a "
                        f"{asset_type} asset (valid: {', '.join(sorted(allowed)) or 'name only'})"
                    )
            else:
                inferred = {_FIELD_TO_TYPE[f] for f in provided}
                if len(inferred) > 1:
                    raise ValueError(
                        "Cannot mix fields from different asset types in one "
                        f"update: {', '.join(sorted(inferred))}. Update one "
                        "asset (one type) at a time."
                    )
                asset_type = next(iter(inferred), None)

            if not provided and name is None:
                raise ValueError(
                    "No updatable fields provided — supply at least one of "
                    "name or a typed field."
                )

            # ── Validate char limits + the ad-text symbol ban ────────
            self._validate_asset_text(name=name, provided=provided)

            # ── Validate final_urls (http/https) ─────────────────────
            cleaned_urls: Optional[List[str]] = None
            if final_urls is not None:
                cleaned_urls = []
                for url in final_urls:
                    if not isinstance(url, str) or not url.strip():
                        raise ValueError("Each final URL must be a non-empty string")
                    stripped = url.strip()
                    if not (
                        stripped.startswith("http://")
                        or stripped.startswith("https://")
                    ):
                        raise ValueError(
                            f"Final URL must start with http:// or https://: {url!r}"
                        )
                    cleaned_urls.append(stripped)

            # ── Build the in-place update + field mask ───────────────
            asset = Asset()
            asset.resource_name = resource_name
            mask_paths: List[str] = []

            if name is not None:
                asset.name = name
                mask_paths.append("name")

            if link_text is not None:
                asset.sitelink_asset.link_text = link_text
                mask_paths.append("sitelink_asset.link_text")
            if description1 is not None:
                asset.sitelink_asset.description1 = description1
                mask_paths.append("sitelink_asset.description1")
            if description2 is not None:
                asset.sitelink_asset.description2 = description2
                mask_paths.append("sitelink_asset.description2")
            if cleaned_urls is not None:
                asset.final_urls.extend(cleaned_urls)
                mask_paths.append("final_urls")

            if callout_text is not None:
                asset.callout_asset.callout_text = callout_text
                mask_paths.append("callout_asset.callout_text")

            if header is not None:
                asset.structured_snippet_asset.header = header
                mask_paths.append("structured_snippet_asset.header")
            if values is not None:
                asset.structured_snippet_asset.values.extend(values)
                mask_paths.append("structured_snippet_asset.values")

            if phone_number is not None:
                asset.call_asset.phone_number = phone_number
                mask_paths.append("call_asset.phone_number")
            if country_code is not None:
                asset.call_asset.country_code = country_code
                mask_paths.append("call_asset.country_code")

            operation = AssetOperation()
            operation.update = asset
            operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=mask_paths))

            request = MutateAssetsRequest()
            request.customer_id = customer_id
            request.operations = [operation]

            response: MutateAssetsResponse = self.client.mutate_assets(request=request)

            await ctx.log(
                level="info",
                message=(
                    f"Updated asset {resource_name} "
                    f"(fields: {', '.join(mask_paths)})"
                ),
            )

            return serialize_proto_message(response)

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to update asset: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    def _validate_asset_text(
        self, *, name: Optional[str], provided: Dict[str, Any]
    ) -> None:
        """Enforce char limits + the ad-text symbol ban on displayed text.

        Applies to name and the SITELINK/CALLOUT/STRUCTURED_SNIPPET text fields
        — NOT to phone numbers or URLs. Raises ValueError on the first breach.
        """

        def _check_symbols(field: str, text: str) -> None:
            bad = sorted({c for c in text if c in _BANNED_TEXT_SYMBOLS})
            if bad:
                raise ValueError(
                    f"{field} contains disallowed ad-text symbol(s) "
                    f"{' '.join(bad)} — remove them"
                )

        # name + single-string display fields
        for field in _TEXT_DISPLAY_FIELDS:
            text = name if field == "name" else provided.get(field)
            if text is None:
                continue
            if not isinstance(text, str):
                raise ValueError(f"{field} must be a string")
            limit = _ASSET_CHAR_LIMITS.get(field)
            if limit is not None and len(text) > limit:
                raise ValueError(
                    f"{field} is {len(text)} chars (max {limit})"
                )
            _check_symbols(field, text)

        # structured-snippet values (each ≤ 25, symbol-banned)
        if "values" in provided:
            for i, val in enumerate(provided["values"]):
                if not isinstance(val, str):
                    raise ValueError(f"values[{i}] must be a string")
                if len(val) > _SNIPPET_VALUE_MAX:
                    raise ValueError(
                        f"values[{i}] is {len(val)} chars (max {_SNIPPET_VALUE_MAX})"
                    )
                _check_symbols(f"values[{i}]", val)

    def _inventory_asset_linkages(
        self, customer_id: str, asset_resource_name: str
    ) -> List[Dict[str, Any]]:
        """Return every LIVE (status != REMOVED) link for an asset across the
        campaign / ad_group / customer levels. Each entry carries the LINK's
        own resource_name so removal can detach it directly. Cheap GAQL reads —
        no mutation. This is the blast-radius the remove guard surfaces."""
        google_ads_service: GoogleAdsServiceClient = (
            get_sdk_client().client.get_service("GoogleAdsService")
        )
        linkages: List[Dict[str, Any]] = []

        level_queries = [
            (
                "campaign",
                "campaign_asset",
                f"""
                SELECT campaign_asset.resource_name, campaign_asset.field_type,
                       campaign.id
                FROM campaign_asset
                WHERE campaign_asset.asset = '{asset_resource_name}'
                  AND campaign_asset.status != 'REMOVED'
                """,
            ),
            (
                "ad_group",
                "ad_group_asset",
                f"""
                SELECT ad_group_asset.resource_name, ad_group_asset.field_type,
                       ad_group.id
                FROM ad_group_asset
                WHERE ad_group_asset.asset = '{asset_resource_name}'
                  AND ad_group_asset.status != 'REMOVED'
                """,
            ),
            (
                "customer",
                "customer_asset",
                f"""
                SELECT customer_asset.resource_name, customer_asset.field_type
                FROM customer_asset
                WHERE customer_asset.asset = '{asset_resource_name}'
                  AND customer_asset.status != 'REMOVED'
                """,
            ),
        ]

        for level, row_attr, query in level_queries:
            response = google_ads_service.search(
                customer_id=customer_id, query=query
            )
            for row in response:
                link = getattr(row, row_attr)
                entry: Dict[str, Any] = {
                    "level": level,
                    "resource_name": link.resource_name,
                    "field_type": link.field_type.name
                    if link.field_type
                    else "UNKNOWN",
                }
                if level == "campaign":
                    entry["campaign_id"] = str(row.campaign.id)
                elif level == "ad_group":
                    entry["ad_group_id"] = str(row.ad_group.id)
                linkages.append(entry)

        return linkages

    async def remove_asset(
        self,
        ctx: Context,
        customer_id: str,
        asset_id: Optional[str] = None,
        asset_resource_name: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Remove (detach) an asset.

        IMPORTANT API REALITY: Google Ads assets CANNOT be hard-deleted —
        ``AssetOperation`` has no ``remove``. "Removing" an asset therefore means
        DETACHING it everywhere it is used (campaign_asset + ad_group_asset +
        customer_asset). An orphaned asset is harmless and simply ignored.

        Guard: this detaches the asset from EVERY live link, so first inventory
        the live linkages. If any exist and ``force`` is not set, return the
        linkage list (the blast radius) and refuse — the operator must
        acknowledge that removal detaches it everywhere. ``force=True`` proceeds.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            asset_id: The asset ID OR pass ``asset_resource_name``
            asset_resource_name: Full asset resource name; overrides asset_id
            force: Detach from all live links even when linkages exist

        Returns:
            When blocked: ``{"status": "blocked", "force_required": True,
            "linkages": [...]}``. When removed: the per-link detach results.
        """
        try:
            customer_id = format_customer_id(customer_id)

            if asset_resource_name:
                resource_name = asset_resource_name
            elif asset_id:
                resource_name = f"customers/{customer_id}/assets/{asset_id}"
            else:
                raise ValueError(
                    "Provide either asset_resource_name or asset_id"
                )

            linkages = self._inventory_asset_linkages(customer_id, resource_name)

            if linkages and not force:
                await ctx.log(
                    level="info",
                    message=(
                        f"Refusing to remove asset {resource_name}: "
                        f"{len(linkages)} live link(s). Pass force=true to detach."
                    ),
                )
                return {
                    "status": "blocked",
                    "force_required": True,
                    "asset_resource_name": resource_name,
                    "linkage_count": len(linkages),
                    "linkages": linkages,
                    "message": (
                        "Removing this asset detaches it from every campaign / "
                        "ad group / account link listed. Re-run with force=true "
                        "to proceed. (Google Ads assets are never hard-deleted; "
                        "removal = detach everywhere.)"
                    ),
                }

            if not linkages:
                await ctx.log(
                    level="info",
                    message=(
                        f"Asset {resource_name} has no live links — already "
                        "orphaned (nothing to detach; assets can't be hard-deleted)."
                    ),
                )
                return {
                    "status": "no_op",
                    "asset_resource_name": resource_name,
                    "detached": [],
                    "message": (
                        "Asset has no live links; nothing to remove. Google Ads "
                        "assets cannot be hard-deleted — an unlinked asset is "
                        "simply inert."
                    ),
                }

            # ── Detach every live link at its own level ──────────────
            sdk = get_sdk_client()
            campaign_client = sdk.client.get_service("CampaignAssetService")
            ad_group_client = sdk.client.get_service("AdGroupAssetService")
            customer_client = sdk.client.get_service("CustomerAssetService")

            detached: List[Dict[str, Any]] = []
            for link in linkages:
                rn = link["resource_name"]
                level = link["level"]
                if level == "campaign":
                    op = CampaignAssetOperation()
                    op.remove = rn
                    req = MutateCampaignAssetsRequest()
                    req.customer_id = customer_id
                    req.operations = [op]
                    campaign_client.mutate_campaign_assets(request=req)
                elif level == "ad_group":
                    op = AdGroupAssetOperation()
                    op.remove = rn
                    req = MutateAdGroupAssetsRequest()
                    req.customer_id = customer_id
                    req.operations = [op]
                    ad_group_client.mutate_ad_group_assets(request=req)
                else:  # customer
                    op = CustomerAssetOperation()
                    op.remove = rn
                    req = MutateCustomerAssetsRequest()
                    req.customer_id = customer_id
                    req.operations = [op]
                    customer_client.mutate_customer_assets(request=req)
                detached.append(link)

            await ctx.log(
                level="info",
                message=(
                    f"Removed asset {resource_name}: detached "
                    f"{len(detached)} link(s)."
                ),
            )

            return {
                "status": "removed",
                "asset_resource_name": resource_name,
                "detached_count": len(detached),
                "detached": detached,
            }

        except GoogleAdsException as e:
            error_msg = f"Google Ads API error: {e.failure}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to remove asset: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def search_assets(
        self,
        ctx: Context,
        customer_id: str,
        asset_types: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search for assets in the account.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            asset_types: Optional list of asset types to filter by
            limit: Maximum number of results

        Returns:
            List of asset details
        """
        try:
            customer_id = format_customer_id(customer_id)

            # Use GoogleAdsService for search
            sdk_client = get_sdk_client()
            google_ads_service: GoogleAdsServiceClient = sdk_client.client.get_service(
                "GoogleAdsService"
            )

            # Build query
            query = """
                SELECT
                    asset.id,
                    asset.name,
                    asset.type,
                    asset.resource_name,
                    asset.text_asset.text,
                    asset.image_asset.file_size,
                    asset.youtube_video_asset.youtube_video_id
                FROM asset
            """

            if asset_types:
                type_conditions = [f"asset.type = '{t}'" for t in asset_types]
                query += " WHERE " + " OR ".join(type_conditions)

            query += f" ORDER BY asset.id DESC LIMIT {limit}"

            # Execute search
            response = google_ads_service.search(customer_id=customer_id, query=query)

            # Process results
            assets = []
            for row in response:
                asset = row.asset
                asset_dict = {
                    "asset_id": str(asset.id),
                    "name": asset.name,
                    "type": asset.type_.name,
                    "resource_name": asset.resource_name,
                }

                # Add type-specific fields
                if asset.type_ == AssetTypeEnum.AssetType.TEXT:
                    asset_dict["text"] = asset.text_asset.text
                elif asset.type_ == AssetTypeEnum.AssetType.IMAGE:
                    asset_dict["file_size"] = str(asset.image_asset.file_size)
                elif asset.type_ == AssetTypeEnum.AssetType.YOUTUBE_VIDEO:
                    asset_dict["youtube_video_id"] = (
                        asset.youtube_video_asset.youtube_video_id
                    )

                assets.append(asset_dict)

            await ctx.log(
                level="info",
                message=f"Found {len(assets)} assets",
            )

            return assets

        except Exception as e:
            error_msg = f"Failed to search assets: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    def get_mime_type_enum(self, mime_type: str):
        """Convert MIME type string to enum value."""
        from google.ads.googleads.v23.enums.types.mime_type import MimeTypeEnum

        mime_type_map = {
            "image/jpeg": MimeTypeEnum.MimeType.IMAGE_JPEG,
            "image/png": MimeTypeEnum.MimeType.IMAGE_PNG,
            "image/gif": MimeTypeEnum.MimeType.IMAGE_GIF,
        }

        return mime_type_map.get(
            mime_type.lower(),
            MimeTypeEnum.MimeType.IMAGE_JPEG,  # Default
        )


def create_asset_tools(service: AssetService) -> List[Callable[..., Awaitable[Any]]]:
    """Create tool functions for the asset service.

    This returns a list of tool functions that can be registered with FastMCP.
    This approach makes the tools testable by allowing service injection.
    """
    tools = []

    async def create_text_asset(
        ctx: Context,
        customer_id: str,
        text: str,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a text asset.

        Args:
            customer_id: The customer ID
            text: The text content
            name: Optional name for the asset

        Returns:
            Created asset details including resource_name and asset_id
        """
        return await service.create_text_asset(
            ctx=ctx,
            customer_id=customer_id,
            text=text,
            name=name,
        )

    async def create_image_asset(
        ctx: Context,
        customer_id: str,
        image_data: bytes,
        name: str,
        mime_type: str = "image/jpeg",
    ) -> Dict[str, Any]:
        """Create an image asset.

        Args:
            customer_id: The customer ID
            image_data: The image data as bytes
            name: Name for the asset
            mime_type: MIME type (image/jpeg, image/png, image/gif)

        Returns:
            Created asset details including resource_name and asset_id
        """
        return await service.create_image_asset(
            ctx=ctx,
            customer_id=customer_id,
            image_data=image_data,
            name=name,
            mime_type=mime_type,
        )

    async def create_youtube_video_asset(
        ctx: Context,
        customer_id: str,
        youtube_video_id: str,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a YouTube video asset.

        Args:
            customer_id: The customer ID
            youtube_video_id: The YouTube video ID (e.g., "dQw4w9WgXcQ")
            name: Optional name for the asset

        Returns:
            Created asset details including resource_name and asset_id
        """
        return await service.create_youtube_video_asset(
            ctx=ctx,
            customer_id=customer_id,
            youtube_video_id=youtube_video_id,
            name=name,
        )

    async def create_sitelink_asset(
        ctx: Context,
        customer_id: str,
        link_text: str,
        description1: str = "",
        description2: str = "",
        final_urls: Optional[List[str]] = None,
        name: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict[str, Any]:
        """Create a sitelink asset (sitelink ad extension).

        Create the asset here, then link it to a campaign/ad group with the
        campaign_asset / ad_group_asset tools using field_type SITELINK.

        Args:
            customer_id: The customer ID
            link_text: The displayed sitelink text (max 25 chars)
            description1: Optional first description line (max 35 chars)
            description2: Optional second description line (max 35 chars)
            final_urls: Landing page URL(s) the sitelink points to
            name: Optional name for the asset
            validate_only: If true, the request is validated but not executed.

        Returns:
            Created asset details including resource_name and asset_id
        """
        return await service.create_sitelink_asset(
            ctx=ctx,
            customer_id=customer_id,
            link_text=link_text,
            description1=description1,
            description2=description2,
            final_urls=final_urls,
            name=name,
            validate_only=validate_only,
        )

    async def create_callout_asset(
        ctx: Context,
        customer_id: str,
        callout_text: str,
        name: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict[str, Any]:
        """Create a callout asset (callout ad extension).

        Create the asset here, then link it to a campaign/ad group with the
        campaign_asset / ad_group_asset tools using field_type CALLOUT.

        Args:
            customer_id: The customer ID
            callout_text: The callout text (max 25 chars)
            name: Optional name for the asset
            validate_only: If true, the request is validated but not executed.

        Returns:
            Created asset details including resource_name and asset_id
        """
        return await service.create_callout_asset(
            ctx=ctx,
            customer_id=customer_id,
            callout_text=callout_text,
            name=name,
            validate_only=validate_only,
        )

    async def create_structured_snippet_asset(
        ctx: Context,
        customer_id: str,
        header: str,
        values: Optional[List[str]] = None,
        name: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict[str, Any]:
        """Create a structured snippet asset (structured snippet ad extension).

        Create the asset here, then link it to a campaign/ad group with the
        campaign_asset / ad_group_asset tools using field_type STRUCTURED_SNIPPET.

        Args:
            customer_id: The customer ID
            header: A predefined snippet header (e.g. "Services", "Brands",
                "Destinations"). The API validates the header.
            values: The snippet values displayed under the header (up to 10)
            name: Optional name for the asset
            validate_only: If true, the request is validated but not executed.

        Returns:
            Created asset details including resource_name and asset_id
        """
        return await service.create_structured_snippet_asset(
            ctx=ctx,
            customer_id=customer_id,
            header=header,
            values=values,
            name=name,
            validate_only=validate_only,
        )

    async def create_call_asset(
        ctx: Context,
        customer_id: str,
        phone_number: str,
        country_code: str,
        name: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict[str, Any]:
        """Create a call asset (call ad extension).

        Create the asset here, then link it to a campaign/ad group with the
        campaign_asset / ad_group_asset tools using field_type CALL.

        Args:
            customer_id: The customer ID
            phone_number: The raw phone number (e.g. "+1 800 555 0100")
            country_code: The 2-letter uppercase country code (e.g. "US")
            name: Optional name for the asset
            validate_only: If true, the request is validated but not executed.

        Returns:
            Created asset details including resource_name and asset_id
        """
        return await service.create_call_asset(
            ctx=ctx,
            customer_id=customer_id,
            phone_number=phone_number,
            country_code=country_code,
            name=name,
            validate_only=validate_only,
        )

    async def update_asset(
        ctx: Context,
        customer_id: str,
        asset_id: Optional[str] = None,
        asset_resource_name: Optional[str] = None,
        asset_type: Optional[str] = None,
        name: Optional[str] = None,
        link_text: Optional[str] = None,
        description1: Optional[str] = None,
        description2: Optional[str] = None,
        final_urls: Optional[List[str]] = None,
        callout_text: Optional[str] = None,
        header: Optional[str] = None,
        values: Optional[List[str]] = None,
        phone_number: Optional[str] = None,
        country_code: Optional[str] = None,
        image_data: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Edit an existing asset in place (update_mask mutate).

        Changes a sitelink / callout / structured-snippet / call asset (or any
        asset's name) WITHOUT deleting and recreating it, so the asset ID and
        its links survive. Only the fields you pass are changed. Provide either
        ``asset_id`` or ``asset_resource_name``.

        Editable fields per type:
            - SITELINK: link_text (≤25), description1/2 (≤35 each), final_urls
            - CALLOUT: callout_text (≤25)
            - STRUCTURED_SNIPPET: header, values (each ≤25)
            - CALL: phone_number, country_code
            - IMAGE: name ONLY (media bytes are immutable — passing image_data
              is rejected; create a new image asset instead)
        Text fields reject the banned ad symbols ~ | +.

        Args:
            customer_id: The customer ID
            asset_id: The asset ID (or pass asset_resource_name)
            asset_resource_name: Full asset resource name; overrides asset_id
            asset_type: Optional explicit type for strict per-type validation
            name: New asset name (any type)
            link_text/description1/description2/final_urls: SITELINK fields
            callout_text: CALLOUT field
            header/values: STRUCTURED_SNIPPET fields
            phone_number/country_code: CALL fields
            image_data: REJECTED (image bytes immutable)

        Returns:
            Updated asset details
        """
        return await service.update_asset(
            ctx=ctx,
            customer_id=customer_id,
            asset_id=asset_id,
            asset_resource_name=asset_resource_name,
            asset_type=asset_type,
            name=name,
            link_text=link_text,
            description1=description1,
            description2=description2,
            final_urls=final_urls,
            callout_text=callout_text,
            header=header,
            values=values,
            phone_number=phone_number,
            country_code=country_code,
            image_data=image_data,
        )

    async def remove_asset(
        ctx: Context,
        customer_id: str,
        asset_id: Optional[str] = None,
        asset_resource_name: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Remove (detach) an asset from everywhere it is used.

        Google Ads assets can't be hard-deleted, so "remove" means DETACHING the
        asset from every campaign / ad group / account link. Because that is
        account-wide, the tool first inventories the live links: if any exist and
        ``force`` is not set it returns the linkage list (the blast radius) and
        refuses. Re-run with ``force=true`` to detach everywhere. An asset with
        no live links is already inert (no-op).

        Args:
            customer_id: The customer ID
            asset_id: The asset ID (or pass asset_resource_name)
            asset_resource_name: Full asset resource name; overrides asset_id
            force: Detach from all live links even when linkages exist

        Returns:
            Blocked linkage report, a no-op notice, or the detach results
        """
        return await service.remove_asset(
            ctx=ctx,
            customer_id=customer_id,
            asset_id=asset_id,
            asset_resource_name=asset_resource_name,
            force=force,
        )

    async def search_assets(
        ctx: Context,
        customer_id: str,
        asset_types: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search for assets in the account.

        Args:
            customer_id: The customer ID
            asset_types: Optional list of asset types to filter by (TEXT, IMAGE, YOUTUBE_VIDEO)
            limit: Maximum number of results

        Returns:
            List of asset details
        """
        return await service.search_assets(
            ctx=ctx,
            customer_id=customer_id,
            asset_types=asset_types,
            limit=limit,
        )

    tools.extend(
        [
            create_text_asset,
            create_image_asset,
            create_youtube_video_asset,
            create_sitelink_asset,
            create_callout_asset,
            create_structured_snippet_asset,
            create_call_asset,
            update_asset,
            remove_asset,
            search_assets,
        ]
    )
    return tools


def register_asset_tools(mcp: FastMCP[Any]) -> AssetService:
    """Register asset tools with the MCP server.

    Returns the AssetService instance for testing purposes.
    """
    service = AssetService()
    tools = create_asset_tools(service)

    # Register each tool
    for tool in tools:
        mcp.tool(tool)

    return service
