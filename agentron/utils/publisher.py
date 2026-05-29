from __future__ import annotations
from typing import Callable

type Subscriber[T] = Callable[[T], None]

type Subscription = Callable[[], None]


class Entry[T]:
    __slots__ = ('callback', 'index', 'active')

    def __init__(self, callback: Subscriber[T], index: int):
        self.callback = callback
        self.index = index
        self.active = True


class Publisher[T]:
    def __init__(self):
        self._entries: list[Entry[T]] = []
        self._publishing = 0
        self._needs_compact = False

    def subscribe(self, callback: Subscriber[T]) -> Subscription:
        entry = Entry(callback, len(self._entries))
        self._entries.append(entry)
        return lambda: self._unsubscribe(entry)

    def publish(self, value: T):
        """
        Publish a value to all active subscribers.

        It is safe to both subscribe and unsubscribe from within a subscriber callback.
        However, subscriptions added during publishing won't be called until the next publish.
        """
        self._publishing += 1
        end = len(self._entries)

        try:
            # Removals are deferred until after publishing finishes to avoid
            # mutating the list while iterating.
            # New subscriptions during publishing are safe (added past iteration end)
            # but won't be called until the next publish.
            for i in range(end):
                entry = self._entries[i]
                if entry.active:
                    entry.callback(value)
        finally:
            self._publishing -= 1

            if self._publishing == 0 and self._needs_compact:
                self._compact()
                self._needs_compact = False

    def clear(self):
        for entry in self._entries:
            entry.active = False

        if self._publishing:
            self._needs_compact = True
        else:
            self._entries.clear()

    @classmethod
    def clear_all(cls, *publishers: Publisher):
        for publisher in publishers:
            publisher.clear()

    def _unsubscribe(self, entry: Entry[T]):
        if not entry.active:
            # Will be pruned during deferred compaction.
            return

        entry.active = False

        if self._publishing:
            # Defer removal until after publishing finishes to avoid mutating the list while iterating.
            self._needs_compact = True
        else:
            # Safe to eagerly remove.
            self._remove(entry)

    def _remove(self, entry: Entry[T]):
        last = self._entries[-1]

        if entry is last:
            self._entries.pop()
            return

        # Swap with the last entry + pop for efficient removal.
        self._entries[entry.index] = last
        last.index = entry.index
        self._entries.pop()

    def _compact(self):
        entries: list[Entry[T]] = []

        for entry in self._entries:
            if entry.active:
                entry.index = len(entries)
                entries.append(entry)

        self._entries = entries


class SubscriptionStore:
    def __init__(self, *subs: Subscription):
        self.subscriptions = subs

    def add(self, *subs: Subscription):
        self.subscriptions += subs

    def clear(self):
        subs, self.subscriptions = self.subscriptions, ()
        for sub in subs:
            sub()
