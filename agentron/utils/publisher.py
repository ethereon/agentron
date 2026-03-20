from __future__ import annotations
from typing import Callable

type Subscriber[T] = Callable[[T], None]

type Subscription = Callable[[], None]


class Publisher[T]:
    def __init__(self):
        self.subscribers: set[Subscriber[T]] = set()

    def subscribe(self, callback: Subscriber[T]) -> Subscription:
        self.subscribers.add(callback)
        return lambda: self.unsubscribe(callback)

    def unsubscribe(self, callback: Subscriber[T]):
        self.subscribers.discard(callback)

    def publish(self, value: T):
        for callback in self.subscribers:
            callback(value)

    def clear(self):
        self.subscribers.clear()

    @classmethod
    def clear_all(cls, *publishers: Publisher):
        for publisher in publishers:
            publisher.clear()


class SubscriptionStore:
    def __init__(self, *subs: Subscription):
        self.subscriptions = subs

    def add(self, *subs: Subscription):
        self.subscriptions += subs

    def clear(self):
        subs, self.subscriptions = self.subscriptions, ()
        for sub in subs:
            sub()
