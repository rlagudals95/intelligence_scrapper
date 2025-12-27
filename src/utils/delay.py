"""
랜덤 딜레이 유틸리티
"""
import asyncio
import random
from ..utils.logger import get_logger

logger = get_logger()


async def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """랜덤 딜레이 (1~3초)"""
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f"딜레이: {delay:.2f}초")
    await asyncio.sleep(delay)


async def fixed_delay(seconds: float) -> None:
    """고정 딜레이"""
    logger.debug(f"딜레이: {seconds:.2f}초")
    await asyncio.sleep(seconds)

