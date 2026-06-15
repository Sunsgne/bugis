"""Sync helpers for PySNMP 6.x asyncio HLAPI (Python 3.12+ compatible)."""
from __future__ import annotations

import asyncio
from typing import Any


def run_snmp(coro: Any) -> Any:
    """Run an SNMP coroutine from synchronous FastAPI handlers."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Rare: already inside a loop — isolate in a fresh loop in a thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _walk_oid_async(
    mgmt_ip: str,
    port: int,
    timeout: float,
    retries: int,
    creds: Any,
    ctx: Any,
    oid: str,
    *,
    max_repetitions: int = 25,
) -> dict[int, str]:
    from pysnmp.hlapi.asyncio import (
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        walkCmd,
    )

    engine = SnmpEngine()
    out: dict[int, str] = {}
    try:
        async for err_ind, err_stat, _idx, var_binds in walkCmd(
            engine,
            creds,
            UdpTransportTarget((mgmt_ip, port), timeout=timeout, retries=retries),
            ctx or ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
            maxRepetitions=max_repetitions,
        ):
            if err_ind or err_stat:
                break
            for oid_val, val in var_binds:
                ifindex = int(str(oid_val).rsplit(".", 1)[-1])
                out[ifindex] = str(val)
    finally:
        engine.closeDispatcher()
    return out


async def _get_oid_async(
    mgmt_ip: str,
    port: int,
    timeout: float,
    retries: int,
    creds: Any,
    ctx: Any,
    oid: str,
) -> str | None:
    from pysnmp.hlapi.asyncio import (
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        getCmd,
    )

    engine = SnmpEngine()
    try:
        err_ind, err_stat, _idx, var_binds = await getCmd(
            engine,
            creds,
            UdpTransportTarget((mgmt_ip, port), timeout=timeout, retries=retries),
            ctx or ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        if err_ind or err_stat:
            return None
        for _oid, val in var_binds:
            return str(val)
    finally:
        engine.closeDispatcher()
    return None


def walk_oid(
    mgmt_ip: str,
    port: int,
    timeout: float,
    retries: int,
    creds: Any,
    ctx: Any,
    oid: str,
    *,
    max_repetitions: int = 25,
) -> dict[int, str]:
    return run_snmp(
        _walk_oid_async(
            mgmt_ip,
            port,
            timeout,
            retries,
            creds,
            ctx,
            oid,
            max_repetitions=max_repetitions,
        )
    )


def get_oid(
    mgmt_ip: str,
    port: int,
    timeout: float,
    retries: int,
    creds: Any,
    ctx: Any,
    oid: str,
) -> str | None:
    return run_snmp(
        _get_oid_async(mgmt_ip, port, timeout, retries, creds, ctx, oid)
    )
