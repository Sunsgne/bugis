"""Sync helpers for PySNMP 7.x asyncio HLAPI (Python 3.12+ compatible)."""
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


def _var_bind_index_and_value(var_bind: Any) -> tuple[str, str]:
    oid_val = var_bind[0]
    val = var_bind[1]
    return str(oid_val), str(val)


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
    )
    from pysnmp.hlapi.v3arch.asyncio import walk_cmd

    engine = SnmpEngine()
    out: dict[int, str] = {}
    try:
        transport = await UdpTransportTarget.create(
            (mgmt_ip, port),
            timeout=timeout,
            retries=retries,
        )
        async for err_ind, err_stat, _idx, var_binds in walk_cmd(
            engine,
            creds,
            transport,
            ctx or ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
            maxRepetitions=max_repetitions,
        ):
            if err_ind or err_stat:
                break
            for var_bind in var_binds:
                oid_val, val = _var_bind_index_and_value(var_bind)
                ifindex = int(oid_val.rsplit(".", 1)[-1])
                out[ifindex] = val
    finally:
        engine.close_dispatcher()
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
    )
    from pysnmp.hlapi.v3arch.asyncio import get_cmd

    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create(
            (mgmt_ip, port),
            timeout=timeout,
            retries=retries,
        )
        err_ind, err_stat, _idx, var_binds = await get_cmd(
            engine,
            creds,
            transport,
            ctx or ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        if err_ind or err_stat:
            return None
        for var_bind in var_binds:
            _oid, val = _var_bind_index_and_value(var_bind)
            return val
    finally:
        engine.close_dispatcher()
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
