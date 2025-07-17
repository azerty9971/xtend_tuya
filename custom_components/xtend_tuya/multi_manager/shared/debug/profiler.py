from __future__ import annotations
try:
    import yappi
except Exception:
    pass
import cProfile
import re
from datetime import datetime
from typing import Coroutine


async def profile_async_method2(coroutine: Coroutine):
    profiler = cProfile.Profile()
    profiler.enable()

    try:
        return await coroutine
    finally:
        profiler.disable()
        profiler.dump_stats(
            re.sub(
                "[^a-z0-9._-]",
                ".",
                f"profile_async_{datetime.now()}_{coroutine}.prof",
                flags=re.IGNORECASE,
            )
        )


async def profile_async_method(coroutine: Coroutine):
    if "yappi" in globals() or "yappi" in locals():
        yappi.set_clock_type("WALL")  # type: ignore
        with yappi.run():  # type: ignore
            result = await coroutine
        info = yappi.get_func_stats()  # type: ignore
        info._save_as_PSTAT(
            re.sub(
                "[^a-z0-9._-]",
                ".",
                f"profile_async_{datetime.now()}_{coroutine}.pstat",
                flags=re.IGNORECASE,
            )
        )
    else:
        return await profile_async_method2(coroutine)
    return result
