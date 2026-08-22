#!/usr/bin/env python3
"""Run deterministic Nova API smoke checks against an isolated deployment."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class HTTPResult:
    status: int
    body: Any


class SmokeError(RuntimeError):
    """Raised when a required Nova endpoint does not behave as expected."""


def request(base_url: str, method: str, path: str, token: str = "", payload: Any = None) -> HTTPResult:
    data = None
    headers = {"Accept": "application/json", "User-Agent": "nova-ci-smoke"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if method == "POST" and path == "/api/v1/keys":
        headers["Idempotency-Key"] = f"nova-ci-{uuid.uuid4().hex}"
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
    except (OSError, urllib.error.URLError) as exc:
        raise SmokeError(f"{method} {path} request failed: {exc}") from exc
    try:
        body = json.loads(raw) if raw else None
    except json.JSONDecodeError as exc:
        raise SmokeError(f"{method} {path} returned invalid JSON") from exc
    return HTTPResult(status, body)


def response_data(result: HTTPResult, path: str) -> Any:
    if not isinstance(result.body, dict) or "data" not in result.body:
        raise SmokeError(f"{path} returned an unexpected response envelope")
    return result.body["data"]


def require_2xx(result: HTTPResult, path: str) -> Any:
    if not 200 <= result.status < 300:
        raise SmokeError(f"{path} returned HTTP {result.status}: {result.body}")
    return response_data(result, path)


def require_gateway_200(result: HTTPResult, path: str) -> dict[str, Any]:
    if result.status != 200 or not isinstance(result.body, dict):
        raise SmokeError(f"{path} returned HTTP {result.status}: {result.body}")
    return result.body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("NOVA_BASE_URL", "http://127.0.0.1:18080"))
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL", ""))
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", ""))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.email or not args.password:
        raise SmokeError("ADMIN_EMAIL and ADMIN_PASSWORD are required")

    health = request(args.base_url, "GET", "/health")
    if health.status != 200 or health.body != {"status": "ok"}:
        raise SmokeError(f"/health returned HTTP {health.status}: {health.body}")

    login = request(
        args.base_url,
        "POST",
        "/api/v1/auth/login",
        payload={"email": args.email, "password": args.password},
    )
    login_data = require_2xx(login, "/api/v1/auth/login")
    if not isinstance(login_data, dict) or not isinstance(login_data.get("access_token"), str):
        raise SmokeError("login response did not contain data.access_token")
    token = login_data["access_token"]
    login_user = login_data.get("user")
    if not isinstance(login_user, dict) or not isinstance(login_user.get("id"), int):
        raise SmokeError("login response did not contain data.user.id")

    require_2xx(
        request(
            args.base_url,
            "POST",
            f"/api/v1/admin/users/{login_user['id']}/balance",
            token,
            {"balance": 1, "operation": "add", "notes": "isolated Nova CI smoke"},
        ),
        "/api/v1/admin/users/:id/balance",
    )

    compliance = require_2xx(
        request(args.base_url, "GET", "/api/v1/admin/compliance", token),
        "/api/v1/admin/compliance",
    )
    if not isinstance(compliance, dict):
        raise SmokeError("compliance response data must be an object")
    if compliance.get("required"):
        phrase = compliance.get("ack_phrase_en")
        if not isinstance(phrase, str) or not phrase:
            raise SmokeError("compliance response did not contain ack_phrase_en")
        accepted = require_2xx(
            request(
                args.base_url,
                "POST",
                "/api/v1/admin/compliance/accept",
                token,
                {"phrase": phrase, "language": "en"},
            ),
            "/api/v1/admin/compliance/accept",
        )
        if not isinstance(accepted, dict) or accepted.get("required"):
            raise SmokeError("admin compliance acknowledgement did not take effect")

    require_2xx(request(args.base_url, "GET", "/api/v1/admin/settings", token), "/api/v1/admin/settings")
    require_2xx(
        request(args.base_url, "GET", "/api/v1/admin/accounts?page=1&page_size=1", token),
        "/api/v1/admin/accounts",
    )

    suffix = uuid.uuid4().hex[:12]
    group_id: int | None = None
    key_id: int | None = None
    api_key = ""
    cleanup_errors: list[str] = []
    try:
        group = require_2xx(
            request(
                args.base_url,
                "POST",
                "/api/v1/admin/groups",
                token,
                {
                    "name": f"nova-ci-smoke-{suffix}",
                    "platform": "openai",
                    "rate_multiplier": 1,
                    "is_exclusive": False,
                    "subscription_type": "standard",
                },
            ),
            "/api/v1/admin/groups",
        )
        if not isinstance(group, dict) or not isinstance(group.get("id"), int):
            raise SmokeError("group creation response did not contain data.id")
        group_id = group["id"]

        key = require_2xx(
            request(
                args.base_url,
                "POST",
                "/api/v1/keys",
                token,
                {"name": f"nova-ci-smoke-{suffix}", "group_id": group_id},
            ),
            "/api/v1/keys",
        )
        if not isinstance(key, dict):
            raise SmokeError("API key creation response must be an object")
        key_id = key.get("id") if isinstance(key.get("id"), int) else None
        api_key = key.get("key", "") if isinstance(key.get("key"), str) else ""
        if key_id is None or not api_key:
            raise SmokeError("API key creation response did not contain id and key")

        models = require_gateway_200(
            request(args.base_url, "GET", "/v1/models", api_key),
            "/v1/models",
        )
        if models.get("object") != "list" or not isinstance(models.get("data"), list):
            raise SmokeError("/v1/models returned an invalid model list")

        billing = require_gateway_200(
            request(args.base_url, "GET", "/v1/sub2api/billing", api_key),
            "/v1/sub2api/billing",
        )
        if billing.get("object") != "sub2api.key_billing":
            raise SmokeError("controlled gateway request returned an unexpected object")
    finally:
        if key_id is not None:
            try:
                result = request(args.base_url, "DELETE", f"/api/v1/keys/{key_id}", token)
                if not 200 <= result.status < 300:
                    cleanup_errors.append(f"API key deletion returned HTTP {result.status}")
            except SmokeError as exc:
                cleanup_errors.append(str(exc))
        if group_id is not None:
            try:
                result = request(args.base_url, "DELETE", f"/api/v1/admin/groups/{group_id}", token)
                if not 200 <= result.status < 300:
                    cleanup_errors.append(f"group deletion returned HTTP {result.status}")
            except SmokeError as exc:
                cleanup_errors.append(str(exc))
        if cleanup_errors:
            print(f"Nova smoke cleanup failed: {'; '.join(cleanup_errors)}", file=sys.stderr)

    if cleanup_errors:
        raise SmokeError("temporary smoke resources were not fully removed")

    print("Nova smoke checks passed: login, compliance, settings, accounts, models, gateway")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as exc:
        print(f"Nova smoke checks failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
