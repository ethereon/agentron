import inspect

from collections.abc import Awaitable

type MaybeAwaitable[T] = T | Awaitable[T]


async def maybe_await[T](value: MaybeAwaitable[T]) -> T:
    if inspect.isawaitable(value):
        return await value
    return value
