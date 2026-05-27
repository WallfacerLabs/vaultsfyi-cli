"""Low-level Vaults.fyi API command surface."""

from __future__ import annotations

import json
from typing import Any, Optional

import click
import typer

from agent.api.v2 import path_value
from agent.cli.context import CliContext
from agent.cli.output import OutputFormat, echo_error, echo_json, print_table


api_app = typer.Typer(help="Call Vaults.fyi V2 API endpoints")
vaults_app = typer.Typer(help="Vault listing endpoints")
assets_app = typer.Typer(help="Asset listing endpoints")
detailed_vaults_app = typer.Typer(help="Detailed vault analytics endpoints")
historical_app = typer.Typer(help="Historical time-series endpoints")
portfolio_app = typer.Typer(help="Portfolio and recommendation endpoints")
transactions_app = typer.Typer(help="Transaction payload endpoints")
rewards_app = typer.Typer(help="Reward transaction endpoints")
benchmarks_app = typer.Typer(help="Benchmark rate endpoints")
nrt_app = typer.Typer(help="Near-real-time vault endpoints")

api_app.add_typer(vaults_app, name="vaults")
api_app.add_typer(assets_app, name="assets")
api_app.add_typer(detailed_vaults_app, name="detailed-vaults")
api_app.add_typer(historical_app, name="historical")
api_app.add_typer(portfolio_app, name="portfolio")
api_app.add_typer(transactions_app, name="transactions")
transactions_app.add_typer(rewards_app, name="rewards")
api_app.add_typer(benchmarks_app, name="benchmarks")
api_app.add_typer(nrt_app, name="nrt")


def _ctx() -> CliContext:
    return click.get_current_context().obj


def _run(fn):
    ctx = _ctx()
    try:
        return fn(ctx)
    except typer.Abort:
        raise
    except typer.Exit:
        raise
    except Exception as exc:
        echo_error(exc, ctx.output)
        raise typer.Exit(1)


def _csv(values: Optional[list[str]]) -> list[str]:
    if not values:
        return []
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        result.extend(part.strip() for part in str(value).split(",") if part.strip())
    return result


def _query_pairs(values: Optional[list[str]]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for raw in values or []:
        if "=" not in raw:
            raise ValueError(f"query value must look like key=value: {raw}")
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"query key cannot be empty: {raw}")
        if key in params:
            current = params[key]
            if isinstance(current, list):
                current.append(value)
            else:
                params[key] = [current, value]
        else:
            params[key] = value
    return params


def _require_list(values: list[str], name: str) -> list[str]:
    if not values:
        raise ValueError(f"{name} is required")
    return values


def _page(page: Optional[int], per_page: Optional[int]) -> dict[str, Any]:
    return {"page": page, "perPage": per_page}


def _historical(
    page: Optional[int],
    per_page: Optional[int],
    granularity: Optional[str],
    from_timestamp: Optional[int],
    to_timestamp: Optional[int],
    apy_interval: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "page": page,
        "perPage": per_page,
        "apyInterval": apy_interval,
        "granularity": granularity,
        "fromTimestamp": from_timestamp,
        "toTimestamp": to_timestamp,
    }


def _detailed_filters(
    page: Optional[int],
    per_page: Optional[int],
    allowed_assets: Optional[list[str]],
    disallowed_assets: Optional[list[str]],
    allowed_protocols: Optional[list[str]],
    disallowed_protocols: Optional[list[str]],
    min_tvl: Optional[int],
    min_vault_score: Optional[float],
    only_transactional: Optional[bool],
    only_app_featured: Optional[bool],
    allow_corrupted: Optional[bool],
    allow_vaults_with_warnings: Optional[bool],
    allowed_networks: Optional[list[str]],
    disallowed_networks: Optional[list[str]],
    max_tvl: Optional[int],
    max_apy: Optional[float],
    min_apy: Optional[float],
    tags: Optional[list[str]],
    curators: Optional[list[str]],
    sort_order: Optional[str],
    sort_by: Optional[str],
) -> dict[str, Any]:
    return {
        "page": page,
        "perPage": per_page,
        "allowedAssets": _csv(allowed_assets),
        "disallowedAssets": _csv(disallowed_assets),
        "allowedProtocols": _csv(allowed_protocols),
        "disallowedProtocols": _csv(disallowed_protocols),
        "minTvl": min_tvl,
        "minVaultScore": min_vault_score,
        "onlyTransactional": only_transactional,
        "onlyAppFeatured": only_app_featured,
        "allowCorrupted": allow_corrupted,
        "allowVaultsWithWarnings": allow_vaults_with_warnings,
        "allowedNetworks": _csv(allowed_networks),
        "disallowedNetworks": _csv(disallowed_networks),
        "maxTvl": max_tvl,
        "maxApy": max_apy,
        "minApy": min_apy,
        "tags": _csv(tags),
        "curators": _csv(curators),
        "sortOrder": sort_order,
        "sortBy": sort_by,
    }


def _portfolio_filters(
    allowed_assets: Optional[list[str]],
    disallowed_assets: Optional[list[str]],
    allowed_protocols: Optional[list[str]],
    disallowed_protocols: Optional[list[str]],
    min_tvl: Optional[int],
    min_vault_score: Optional[float],
    only_transactional: Optional[bool],
    only_app_featured: Optional[bool],
    allow_corrupted: Optional[bool],
    allow_vaults_with_warnings: Optional[bool],
    allowed_networks: Optional[list[str]],
    disallowed_networks: Optional[list[str]],
    apy_interval: Optional[str],
    min_apy: Optional[float],
    min_usd_asset_value_threshold: Optional[float],
) -> dict[str, Any]:
    return {
        "allowedAssets": _csv(allowed_assets),
        "disallowedAssets": _csv(disallowed_assets),
        "allowedProtocols": _csv(allowed_protocols),
        "disallowedProtocols": _csv(disallowed_protocols),
        "minTvl": min_tvl,
        "minVaultScore": min_vault_score,
        "onlyTransactional": only_transactional,
        "onlyAppFeatured": only_app_featured,
        "allowCorrupted": allow_corrupted,
        "allowVaultsWithWarnings": allow_vaults_with_warnings,
        "allowedNetworks": _csv(allowed_networks),
        "disallowedNetworks": _csv(disallowed_networks),
        "apyInterval": apy_interval,
        "minApy": min_apy,
        "minUsdAssetValueThreshold": min_usd_asset_value_threshold,
    }


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _apply_client_filters(
    data: Any,
    *,
    only_instant_deposit: Optional[bool] = None,
    only_instant_redeem: Optional[bool] = None,
    max_performance_fee: Optional[float] = None,
    max_management_fee: Optional[float] = None,
    max_withdrawal_fee: Optional[float] = None,
    max_deposit_fee: Optional[float] = None,
    min_remaining_capacity: Optional[float] = None,
    only_rewards_supported: Optional[bool] = None,
) -> Any:
    """Post-filter API response using client-side vault property filters."""
    has_filters = any(v is not None for v in (
        only_instant_deposit, only_instant_redeem,
        max_performance_fee, max_management_fee,
        max_withdrawal_fee, max_deposit_fee,
        min_remaining_capacity, only_rewards_supported,
    ))
    if not has_filters:
        return data
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return data

    def keep(vault: dict) -> bool:
        if only_instant_deposit and vault.get("depositStepsType") != "instant":
            return False
        if only_instant_redeem and vault.get("redeemStepsType") != "instant":
            return False
        if max_performance_fee is not None:
            v = _float_or_none(vault.get("performanceFee"))
            if v is not None and v > max_performance_fee:
                return False
        if max_management_fee is not None:
            v = _float_or_none(vault.get("managementFee"))
            if v is not None and v > max_management_fee:
                return False
        if max_withdrawal_fee is not None:
            v = _float_or_none(vault.get("withdrawalFee"))
            if v is not None and v > max_withdrawal_fee:
                return False
        if max_deposit_fee is not None:
            v = _float_or_none(vault.get("depositFee"))
            if v is not None and v > max_deposit_fee:
                return False
        if min_remaining_capacity is not None:
            v = _float_or_none(vault.get("remainingCapacity"))
            if v is not None and v < min_remaining_capacity:
                return False
        if only_rewards_supported and vault.get("rewardsSupported") is not True:
            return False
        return True

    return {**data, "data": [v for v in data["data"] if keep(v)]}


def _emit(data: Any, ctx: CliContext, rows: Optional[list[dict[str, Any]]] = None) -> None:
    if ctx.output == OutputFormat.json:
        echo_json(data)
    else:
        print_table(rows if rows is not None else _rows(data))


def _rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return [_flatten(item) for item in data["data"]]
    if isinstance(data, dict) and "claimable" in data and isinstance(data["claimable"], dict):
        return [
            {"network": network, "claimable": len(items)}
            for network, items in data["claimable"].items()
            if isinstance(items, list)
        ] or [_flatten(data)]
    if isinstance(data, dict) and "actions" in data and isinstance(data["actions"], list):
        return [_flatten(action) for action in data["actions"]]
    if isinstance(data, dict) and data and all(isinstance(value, dict) and "actions" in value for value in data.values()):
        return [
            {"network": network, "current_action_index": value.get("currentActionIndex"), "actions": len(value.get("actions", []))}
            for network, value in data.items()
        ]
    if isinstance(data, list):
        return [_flatten(item) if isinstance(item, dict) else {"value": item} for item in data]
    if isinstance(data, dict):
        return [_flatten(data)]
    return [{"value": data}]


def _flatten(item: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, value in item.items():
        if isinstance(value, dict):
            row[key] = _summarize_dict(value)
        elif isinstance(value, list):
            row[key] = _summarize_list(value)
        else:
            row[key] = value
    return row


def _summarize_dict(value: dict[str, Any]) -> Any:
    for key in ("name", "symbol", "address", "vaultId", "networkCaip", "suffix"):
        if key in value:
            return value[key]
    return json.dumps(value, default=str)


def _summarize_list(value: list[Any]) -> Any:
    if not value:
        return ""
    if all(not isinstance(item, (dict, list)) for item in value):
        text = ", ".join(str(item) for item in value)
        return text if len(text) <= 120 else text[:117] + "..."
    return f"{len(value)} item(s)"


@api_app.command("request")
def request(
    path: str = typer.Argument(..., help="API path, e.g. /v2/vaults"),
    query: Optional[list[str]] = typer.Option(None, "--query", "-q", help="Query pair key=value. Repeat for arrays."),
):
    """Call an arbitrary GET endpoint."""

    def inner(ctx: CliContext):
        endpoint = path if path.startswith("/") else f"/{path}"
        data = ctx.api_client().request(endpoint, params=_query_pairs(query))
        _emit(data, ctx)

    _run(inner)


@api_app.command("health")
def health():
    """Check API health."""

    def inner(ctx: CliContext):
        data = ctx.api_client().request("/v2/health")
        _emit(data, ctx)

    _run(inner)


@vaults_app.command("list")
def list_vaults(
    page: Optional[int] = typer.Option(None, "--page", help="Page number starting at 0"),
    per_page: Optional[int] = typer.Option(None, "--per-page", help="Items per page"),
    network: Optional[str] = typer.Option(None, "--network", help="Network name or CAIP-2 id"),
    asset_symbol: Optional[str] = typer.Option(None, "--asset-symbol", help="Asset symbol"),
    only_transactional: Optional[bool] = typer.Option(None, "--only-transactional/--include-non-transactional"),
    only_app_featured: Optional[bool] = typer.Option(None, "--only-app-featured/--include-non-app-featured"),
    allow_corrupted: Optional[bool] = typer.Option(None, "--allow-corrupted/--exclude-corrupted"),
):
    """List basic vaults."""

    def inner(ctx: CliContext):
        params = _page(page, per_page) | {
            "network": network,
            "assetSymbol": asset_symbol,
            "onlyTransactional": only_transactional,
            "onlyAppFeatured": only_app_featured,
            "allowCorrupted": allow_corrupted,
        }
        data = ctx.api_client().request("/v2/vaults", params=params)
        _emit(data, ctx)

    _run(inner)


@assets_app.command("list")
def list_assets(
    page: Optional[int] = typer.Option(None, "--page", help="Page number starting at 0"),
    per_page: Optional[int] = typer.Option(None, "--per-page", help="Items per page"),
    network: Optional[str] = typer.Option(None, "--network", help="Network name or CAIP-2 id"),
):
    """List supported assets."""

    def inner(ctx: CliContext):
        data = ctx.api_client().request("/v2/assets", params=_page(page, per_page) | {"network": network})
        _emit(data, ctx)

    _run(inner)


@api_app.command("tags")
def list_tags():
    """List vault tags."""

    def inner(ctx: CliContext):
        data = ctx.api_client().request("/v2/tags")
        _emit(data, ctx)

    _run(inner)


@api_app.command("networks")
def list_networks():
    """List supported networks."""

    def inner(ctx: CliContext):
        data = ctx.api_client().request("/v2/networks")
        _emit(data, ctx)

    _run(inner)


@api_app.command("curators")
def list_curators():
    """List vault curators."""

    def inner(ctx: CliContext):
        data = ctx.api_client().request("/v2/curators")
        _emit(data, ctx)

    _run(inner)


@api_app.command("protocols")
def list_protocols():
    """List protocols."""

    def inner(ctx: CliContext):
        data = ctx.api_client().request("/v2/protocols")
        _emit(data, ctx)

    _run(inner)


@detailed_vaults_app.command("list")
def list_detailed_vaults(
    page: Optional[int] = typer.Option(None, "--page"),
    per_page: Optional[int] = typer.Option(None, "--per-page"),
    allowed_assets: Optional[list[str]] = typer.Option(None, "--allowed-asset", "--allowed-assets"),
    disallowed_assets: Optional[list[str]] = typer.Option(None, "--disallowed-asset", "--disallowed-assets"),
    allowed_protocols: Optional[list[str]] = typer.Option(None, "--allowed-protocol", "--allowed-protocols"),
    disallowed_protocols: Optional[list[str]] = typer.Option(None, "--disallowed-protocol", "--disallowed-protocols"),
    min_tvl: Optional[int] = typer.Option(None, "--min-tvl"),
    min_vault_score: Optional[float] = typer.Option(None, "--min-vault-score"),
    only_transactional: Optional[bool] = typer.Option(None, "--only-transactional/--include-non-transactional"),
    only_app_featured: Optional[bool] = typer.Option(None, "--only-app-featured/--include-non-app-featured"),
    allow_corrupted: Optional[bool] = typer.Option(None, "--allow-corrupted/--exclude-corrupted"),
    allow_vaults_with_warnings: Optional[bool] = typer.Option(None, "--allow-vaults-with-warnings/--exclude-vaults-with-warnings"),
    allowed_networks: Optional[list[str]] = typer.Option(None, "--allowed-network", "--allowed-networks"),
    disallowed_networks: Optional[list[str]] = typer.Option(None, "--disallowed-network", "--disallowed-networks"),
    max_tvl: Optional[int] = typer.Option(None, "--max-tvl"),
    max_apy: Optional[float] = typer.Option(None, "--max-apy"),
    min_apy: Optional[float] = typer.Option(None, "--min-apy"),
    tags: Optional[list[str]] = typer.Option(None, "--tag", "--tags"),
    curators: Optional[list[str]] = typer.Option(None, "--curator", "--curators"),
    sort_order: Optional[str] = typer.Option(None, "--sort-order"),
    sort_by: Optional[str] = typer.Option(None, "--sort-by"),
    only_instant_deposit: Optional[bool] = typer.Option(None, "--only-instant-deposit/--include-non-instant-deposit"),
    only_instant_redeem: Optional[bool] = typer.Option(None, "--only-instant-redeem/--include-non-instant-redeem"),
    max_performance_fee: Optional[float] = typer.Option(None, "--max-performance-fee"),
    max_management_fee: Optional[float] = typer.Option(None, "--max-management-fee"),
    max_withdrawal_fee: Optional[float] = typer.Option(None, "--max-withdrawal-fee"),
    max_deposit_fee: Optional[float] = typer.Option(None, "--max-deposit-fee"),
    min_remaining_capacity: Optional[float] = typer.Option(None, "--min-remaining-capacity"),
    only_rewards_supported: Optional[bool] = typer.Option(None, "--only-rewards-supported/--include-non-rewards-supported"),
):
    """List detailed vaults with analytics and filters."""

    def inner(ctx: CliContext):
        params = _detailed_filters(
            page,
            per_page,
            allowed_assets,
            disallowed_assets,
            allowed_protocols,
            disallowed_protocols,
            min_tvl,
            min_vault_score,
            only_transactional,
            only_app_featured,
            allow_corrupted,
            allow_vaults_with_warnings,
            allowed_networks,
            disallowed_networks,
            max_tvl,
            max_apy,
            min_apy,
            tags,
            curators,
            sort_order,
            sort_by,
        )
        data = ctx.api_client().request("/v2/detailed-vaults", params=params)
        data = _apply_client_filters(
            data,
            only_instant_deposit=only_instant_deposit,
            only_instant_redeem=only_instant_redeem,
            max_performance_fee=max_performance_fee,
            max_management_fee=max_management_fee,
            max_withdrawal_fee=max_withdrawal_fee,
            max_deposit_fee=max_deposit_fee,
            min_remaining_capacity=min_remaining_capacity,
            only_rewards_supported=only_rewards_supported,
        )
        _emit(data, ctx)

    _run(inner)


@detailed_vaults_app.command("get")
def get_detailed_vault(network: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """Get one detailed vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/detailed-vaults/{path_value(network)}/{path_value(vault_id)}"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@detailed_vaults_app.command("apy")
def get_vault_apy(network: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """Get current vault APY breakdown."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/detailed-vaults/{path_value(network)}/{path_value(vault_id)}/apy"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@detailed_vaults_app.command("tvl")
def get_vault_tvl(network: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """Get current vault TVL breakdown."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/detailed-vaults/{path_value(network)}/{path_value(vault_id)}/tvl"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@historical_app.command("vault")
def get_historical_data(
    network: str,
    vault_id: str = typer.Argument(..., help="Vault id"),
    page: Optional[int] = typer.Option(None, "--page"),
    per_page: Optional[int] = typer.Option(None, "--per-page"),
    apy_interval: Optional[str] = typer.Option(None, "--apy-interval"),
    granularity: Optional[str] = typer.Option(None, "--granularity"),
    from_timestamp: Optional[int] = typer.Option(None, "--from-timestamp"),
    to_timestamp: Optional[int] = typer.Option(None, "--to-timestamp"),
):
    """Get historical APY, TVL, and share price for a vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/historical/{path_value(network)}/{path_value(vault_id)}"
        data = ctx.api_client().request(endpoint, params=_historical(page, per_page, granularity, from_timestamp, to_timestamp, apy_interval))
        _emit(data, ctx)

    _run(inner)


@historical_app.command("apy")
def get_historical_apy(
    network: str,
    vault_id: str = typer.Argument(..., help="Vault id"),
    page: Optional[int] = typer.Option(None, "--page"),
    per_page: Optional[int] = typer.Option(None, "--per-page"),
    apy_interval: Optional[str] = typer.Option(None, "--apy-interval"),
    granularity: Optional[str] = typer.Option(None, "--granularity"),
    from_timestamp: Optional[int] = typer.Option(None, "--from-timestamp"),
    to_timestamp: Optional[int] = typer.Option(None, "--to-timestamp"),
):
    """Get historical APY for a vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/historical/{path_value(network)}/{path_value(vault_id)}/apy"
        data = ctx.api_client().request(endpoint, params=_historical(page, per_page, granularity, from_timestamp, to_timestamp, apy_interval))
        _emit(data, ctx)

    _run(inner)


@historical_app.command("tvl")
def get_historical_tvl(
    network: str,
    vault_id: str = typer.Argument(..., help="Vault id"),
    page: Optional[int] = typer.Option(None, "--page"),
    per_page: Optional[int] = typer.Option(None, "--per-page"),
    apy_interval: Optional[str] = typer.Option(None, "--apy-interval"),
    granularity: Optional[str] = typer.Option(None, "--granularity"),
    from_timestamp: Optional[int] = typer.Option(None, "--from-timestamp"),
    to_timestamp: Optional[int] = typer.Option(None, "--to-timestamp"),
):
    """Get historical TVL for a vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/historical/{path_value(network)}/{path_value(vault_id)}/tvl"
        data = ctx.api_client().request(endpoint, params=_historical(page, per_page, granularity, from_timestamp, to_timestamp, apy_interval))
        _emit(data, ctx)

    _run(inner)


@historical_app.command("share-price")
def get_historical_share_price(
    network: str,
    vault_id: str = typer.Argument(..., help="Vault id"),
    page: Optional[int] = typer.Option(None, "--page"),
    per_page: Optional[int] = typer.Option(None, "--per-page"),
    apy_interval: Optional[str] = typer.Option(None, "--apy-interval"),
    granularity: Optional[str] = typer.Option(None, "--granularity"),
    from_timestamp: Optional[int] = typer.Option(None, "--from-timestamp"),
    to_timestamp: Optional[int] = typer.Option(None, "--to-timestamp"),
):
    """Get historical share price for a vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/historical/{path_value(network)}/{path_value(vault_id)}/sharePrice"
        data = ctx.api_client().request(endpoint, params=_historical(page, per_page, granularity, from_timestamp, to_timestamp, apy_interval))
        _emit(data, ctx)

    _run(inner)


@historical_app.command("asset-prices")
def get_historical_asset_prices(
    network: str,
    asset_address: str = typer.Argument(..., help="Asset address"),
    page: Optional[int] = typer.Option(None, "--page"),
    per_page: Optional[int] = typer.Option(None, "--per-page"),
    granularity: Optional[str] = typer.Option(None, "--granularity"),
    from_timestamp: Optional[int] = typer.Option(None, "--from-timestamp"),
    to_timestamp: Optional[int] = typer.Option(None, "--to-timestamp"),
):
    """Get historical USD prices for an asset."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/historical/asset-prices/{path_value(network)}/{path_value(asset_address)}"
        data = ctx.api_client().request(endpoint, params=_historical(page, per_page, granularity, from_timestamp, to_timestamp))
        _emit(data, ctx)

    _run(inner)


@portfolio_app.command("best-vault")
def get_best_vault(
    user_address: str,
    allowed_assets: Optional[list[str]] = typer.Option(None, "--allowed-asset", "--allowed-assets"),
    disallowed_assets: Optional[list[str]] = typer.Option(None, "--disallowed-asset", "--disallowed-assets"),
    allowed_protocols: Optional[list[str]] = typer.Option(None, "--allowed-protocol", "--allowed-protocols"),
    disallowed_protocols: Optional[list[str]] = typer.Option(None, "--disallowed-protocol", "--disallowed-protocols"),
    min_tvl: Optional[int] = typer.Option(None, "--min-tvl"),
    min_vault_score: Optional[float] = typer.Option(None, "--min-vault-score"),
    only_transactional: Optional[bool] = typer.Option(None, "--only-transactional/--include-non-transactional"),
    only_app_featured: Optional[bool] = typer.Option(None, "--only-app-featured/--include-non-app-featured"),
    allow_corrupted: Optional[bool] = typer.Option(None, "--allow-corrupted/--exclude-corrupted"),
    allow_vaults_with_warnings: Optional[bool] = typer.Option(None, "--allow-vaults-with-warnings/--exclude-vaults-with-warnings"),
    allowed_networks: Optional[list[str]] = typer.Option(None, "--allowed-network", "--allowed-networks"),
    disallowed_networks: Optional[list[str]] = typer.Option(None, "--disallowed-network", "--disallowed-networks"),
    apy_interval: Optional[str] = typer.Option(None, "--apy-interval"),
    min_apy: Optional[float] = typer.Option(None, "--min-apy"),
    min_usd_asset_value_threshold: Optional[float] = typer.Option(None, "--min-usd-asset-value-threshold"),
):
    """Get the best vault opportunity for a user."""

    def inner(ctx: CliContext):
        params = _portfolio_filters(
            allowed_assets,
            disallowed_assets,
            allowed_protocols,
            disallowed_protocols,
            min_tvl,
            min_vault_score,
            only_transactional,
            only_app_featured,
            allow_corrupted,
            allow_vaults_with_warnings,
            allowed_networks,
            disallowed_networks,
            apy_interval,
            min_apy,
            min_usd_asset_value_threshold,
        )
        endpoint = f"/v2/portfolio/best-vault/{path_value(user_address)}"
        data = ctx.api_client().request(endpoint, params=params)
        _emit(data, ctx)

    _run(inner)


@portfolio_app.command("positions")
def list_portfolio_positions(
    user_address: str,
    allowed_assets: Optional[list[str]] = typer.Option(None, "--allowed-asset", "--allowed-assets"),
    disallowed_assets: Optional[list[str]] = typer.Option(None, "--disallowed-asset", "--disallowed-assets"),
    allowed_protocols: Optional[list[str]] = typer.Option(None, "--allowed-protocol", "--allowed-protocols"),
    disallowed_protocols: Optional[list[str]] = typer.Option(None, "--disallowed-protocol", "--disallowed-protocols"),
    min_tvl: Optional[int] = typer.Option(None, "--min-tvl"),
    min_vault_score: Optional[float] = typer.Option(None, "--min-vault-score"),
    only_transactional: Optional[bool] = typer.Option(None, "--only-transactional/--include-non-transactional"),
    only_app_featured: Optional[bool] = typer.Option(None, "--only-app-featured/--include-non-app-featured"),
    allow_corrupted: Optional[bool] = typer.Option(None, "--allow-corrupted/--exclude-corrupted"),
    allow_vaults_with_warnings: Optional[bool] = typer.Option(None, "--allow-vaults-with-warnings/--exclude-vaults-with-warnings"),
    allowed_networks: Optional[list[str]] = typer.Option(None, "--allowed-network", "--allowed-networks"),
    disallowed_networks: Optional[list[str]] = typer.Option(None, "--disallowed-network", "--disallowed-networks"),
    max_tvl: Optional[int] = typer.Option(None, "--max-tvl"),
    max_apy: Optional[float] = typer.Option(None, "--max-apy"),
    min_apy: Optional[float] = typer.Option(None, "--min-apy"),
    tags: Optional[list[str]] = typer.Option(None, "--tag", "--tags"),
    curators: Optional[list[str]] = typer.Option(None, "--curator", "--curators"),
    sort_order: Optional[str] = typer.Option(None, "--sort-order"),
    sort_by: Optional[str] = typer.Option(None, "--sort-by"),
    apy_interval: Optional[str] = typer.Option(None, "--apy-interval"),
    min_usd_asset_value_threshold: Optional[float] = typer.Option(None, "--min-usd-asset-value-threshold"),
):
    """List all vault positions for a user."""

    def inner(ctx: CliContext):
        params = _detailed_filters(
            None,
            None,
            allowed_assets,
            disallowed_assets,
            allowed_protocols,
            disallowed_protocols,
            min_tvl,
            min_vault_score,
            only_transactional,
            only_app_featured,
            allow_corrupted,
            allow_vaults_with_warnings,
            allowed_networks,
            disallowed_networks,
            max_tvl,
            max_apy,
            min_apy,
            tags,
            curators,
            sort_order,
            sort_by,
        ) | {"apyInterval": apy_interval, "minUsdAssetValueThreshold": min_usd_asset_value_threshold}
        endpoint = f"/v2/portfolio/positions/{path_value(user_address)}"
        data = ctx.api_client().request(endpoint, params=params)
        _emit(data, ctx)

    _run(inner)


@portfolio_app.command("position")
def get_portfolio_position(
    user_address: str,
    network: str,
    vault_id: str = typer.Argument(..., help="Vault id"),
    apy_interval: Optional[str] = typer.Option(None, "--apy-interval"),
):
    """Get one vault position for a user."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/portfolio/positions/{path_value(user_address)}/{path_value(network)}/{path_value(vault_id)}"
        data = ctx.api_client().request(endpoint, params={"apyInterval": apy_interval})
        _emit(data, ctx)

    _run(inner)


@portfolio_app.command("best-deposit-options")
def get_best_deposit_options(
    user_address: str,
    allowed_assets: Optional[list[str]] = typer.Option(None, "--allowed-asset", "--allowed-assets"),
    disallowed_assets: Optional[list[str]] = typer.Option(None, "--disallowed-asset", "--disallowed-assets"),
    allowed_protocols: Optional[list[str]] = typer.Option(None, "--allowed-protocol", "--allowed-protocols"),
    disallowed_protocols: Optional[list[str]] = typer.Option(None, "--disallowed-protocol", "--disallowed-protocols"),
    min_tvl: Optional[int] = typer.Option(None, "--min-tvl"),
    min_vault_score: Optional[float] = typer.Option(None, "--min-vault-score"),
    only_transactional: Optional[bool] = typer.Option(None, "--only-transactional/--include-non-transactional"),
    only_app_featured: Optional[bool] = typer.Option(None, "--only-app-featured/--include-non-app-featured"),
    allow_corrupted: Optional[bool] = typer.Option(None, "--allow-corrupted/--exclude-corrupted"),
    allow_vaults_with_warnings: Optional[bool] = typer.Option(None, "--allow-vaults-with-warnings/--exclude-vaults-with-warnings"),
    allowed_networks: Optional[list[str]] = typer.Option(None, "--allowed-network", "--allowed-networks"),
    disallowed_networks: Optional[list[str]] = typer.Option(None, "--disallowed-network", "--disallowed-networks"),
    apy_interval: Optional[str] = typer.Option(None, "--apy-interval"),
    min_apy: Optional[float] = typer.Option(None, "--min-apy"),
    min_usd_asset_value_threshold: Optional[float] = typer.Option(None, "--min-usd-asset-value-threshold"),
    always_return_assets: Optional[list[str]] = typer.Option(None, "--always-return-asset", "--always-return-assets"),
    max_vaults_per_asset: Optional[int] = typer.Option(None, "--max-vaults-per-asset"),
):
    """Get best deposit options for a user's idle balances."""

    def inner(ctx: CliContext):
        params = _portfolio_filters(
            allowed_assets,
            disallowed_assets,
            allowed_protocols,
            disallowed_protocols,
            min_tvl,
            min_vault_score,
            only_transactional,
            only_app_featured,
            allow_corrupted,
            allow_vaults_with_warnings,
            allowed_networks,
            disallowed_networks,
            apy_interval,
            min_apy,
            min_usd_asset_value_threshold,
        ) | {"alwaysReturnAssets": _csv(always_return_assets), "maxVaultsPerAsset": max_vaults_per_asset}
        endpoint = f"/v2/portfolio/best-deposit-options/{path_value(user_address)}"
        data = ctx.api_client().request(endpoint, params=params)
        _emit(data, ctx)

    _run(inner)


@portfolio_app.command("idle-assets")
def list_idle_assets(
    user_address: str,
    allowed_assets: Optional[list[str]] = typer.Option(None, "--allowed-asset", "--allowed-assets"),
    disallowed_assets: Optional[list[str]] = typer.Option(None, "--disallowed-asset", "--disallowed-assets"),
    min_usd_asset_value_threshold: Optional[float] = typer.Option(None, "--min-usd-asset-value-threshold"),
    sort_by: Optional[str] = typer.Option(None, "--sort-by"),
    sort_direction: Optional[str] = typer.Option(None, "--sort-direction"),
    allowed_networks: Optional[list[str]] = typer.Option(None, "--allowed-network", "--allowed-networks"),
    disallowed_networks: Optional[list[str]] = typer.Option(None, "--disallowed-network", "--disallowed-networks"),
):
    """List idle assets for a user."""

    def inner(ctx: CliContext):
        params = {
            "allowedAssets": _csv(allowed_assets),
            "disallowedAssets": _csv(disallowed_assets),
            "minUsdAssetValueThreshold": min_usd_asset_value_threshold,
            "sortBy": sort_by,
            "sortDirection": sort_direction,
            "allowedNetworks": _csv(allowed_networks),
            "disallowedNetworks": _csv(disallowed_networks),
        }
        endpoint = f"/v2/portfolio/idle-assets/{path_value(user_address)}"
        data = ctx.api_client().request(endpoint, params=params)
        _emit(data, ctx)

    _run(inner)


@portfolio_app.command("total-returns")
def get_total_returns(user_address: str, network: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """Get total returns for one user position."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/portfolio/total-returns/{path_value(user_address)}/{path_value(network)}/{path_value(vault_id)}"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@portfolio_app.command("events")
def list_portfolio_events(user_address: str, network: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """List position deposit and withdrawal events."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/portfolio/events/{path_value(user_address)}/{path_value(network)}/{path_value(vault_id)}"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@transactions_app.command("context")
def get_transaction_context(user_address: str, network: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """Get transactional context for a user and vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/transactions/context/{path_value(user_address)}/{path_value(network)}/{path_value(vault_id)}"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@transactions_app.command("suffix")
def get_transaction_suffix(user_address: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """Get raw calldata suffix for a user and vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/transactions/suffix/{path_value(user_address)}/{path_value(vault_id)}"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@transactions_app.command("payload")
def get_transaction_payload(
    action: str,
    user_address: str,
    network: str,
    vault_id: str = typer.Argument(..., help="Vault id"),
    asset_address: str = typer.Option(..., "--asset-address", help="Asset address"),
    amount: Optional[str] = typer.Option(None, "--amount", help="Native amount for deposit/redeem/request actions"),
    redeem_all_assets: Optional[bool] = typer.Option(None, "--all/--not-all", help="Redeem all assets"),
    simulate: Optional[bool] = typer.Option(None, "--simulate/--no-simulate", help="Deprecated by API"),
):
    """Get executable transaction payloads for a vault action."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/transactions/{path_value(action)}/{path_value(user_address)}/{path_value(network)}/{path_value(vault_id)}"
        params = {
            "simulate": simulate,
            "assetAddress": asset_address,
            "amount": amount,
            "all": redeem_all_assets,
        }
        data = ctx.api_client().request(endpoint, params=params)
        _emit(data, ctx)

    _run(inner)


@rewards_app.command("context")
def get_rewards_context(user_address: str):
    """Get claimable rewards context for a user."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/transactions/rewards/context/{path_value(user_address)}"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@rewards_app.command("claim")
def claim_rewards(
    user_address: str,
    claim_ids: Optional[list[str]] = typer.Option(None, "--claim-id", "--claim-ids", help="Claim id. Repeat or comma-separate."),
    simulate: Optional[bool] = typer.Option(None, "--simulate/--no-simulate", help="Deprecated by API"),
):
    """Get reward claim transaction payloads."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/transactions/rewards/claim/{path_value(user_address)}"
        params = {"simulate": simulate, "claimIds": _require_list(_csv(claim_ids), "--claim-id")}
        data = ctx.api_client().request(endpoint, params=params)
        _emit(data, ctx)

    _run(inner)


@benchmarks_app.command("get")
def get_benchmark(network: str, code: str = typer.Option(..., "--code", help="Benchmark code: usd or eth")):
    """Get latest benchmark APY for a network."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/benchmarks/{path_value(network)}"
        data = ctx.api_client().request(endpoint, params={"code": code})
        _emit(data, ctx)

    _run(inner)


@benchmarks_app.command("history")
def get_historical_benchmarks(
    network: str,
    code: str = typer.Option(..., "--code", help="Benchmark code: usd or eth"),
    page: Optional[int] = typer.Option(None, "--page"),
    per_page: Optional[int] = typer.Option(None, "--per-page"),
    from_timestamp: Optional[int] = typer.Option(None, "--from-timestamp"),
    to_timestamp: Optional[int] = typer.Option(None, "--to-timestamp"),
):
    """Get historical benchmark APY for a network."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/historical-benchmarks/{path_value(network)}"
        params = _page(page, per_page) | {"code": code, "fromTimestamp": from_timestamp, "toTimestamp": to_timestamp}
        data = ctx.api_client().request(endpoint, params=params)
        _emit(data, ctx)

    _run(inner)


@nrt_app.command("vault")
def get_vault_nrt(network: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """Get all NRT metrics for a vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/nrt/vault/{path_value(network)}/{path_value(vault_id)}"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@nrt_app.command("share-price")
def get_vault_nrt_share_price(network: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """Get NRT share price for a vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/nrt/vault/{path_value(network)}/{path_value(vault_id)}/sharePrice"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@nrt_app.command("total-supply")
def get_vault_nrt_total_supply(network: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """Get NRT total supply for a vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/nrt/vault/{path_value(network)}/{path_value(vault_id)}/totalSupply"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@nrt_app.command("total-assets")
def get_vault_nrt_total_assets(network: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """Get NRT total assets for a vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/nrt/vault/{path_value(network)}/{path_value(vault_id)}/totalAssets"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)


@nrt_app.command("underlying-asset-price")
def get_vault_nrt_underlying_asset_price(network: str, vault_id: str = typer.Argument(..., help="Vault id")):
    """Get NRT underlying asset price for a vault."""

    def inner(ctx: CliContext):
        endpoint = f"/v2/nrt/vault/{path_value(network)}/{path_value(vault_id)}/underlyingAssetPrice"
        data = ctx.api_client().request(endpoint)
        _emit(data, ctx)

    _run(inner)
