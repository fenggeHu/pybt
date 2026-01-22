from collections import defaultdict, deque
from typing import Callable, Deque, Iterable, List, MutableMapping, Type, TypeVar

from .events import Event

EventHandler = Callable[[Event], None]
E = TypeVar("E", bound=Event)


class EventBus:
    """
    Simple synchronous event bus backed by a FIFO queue.

    Publishers enqueue events; subscribers register callbacks that will
    be invoked in order when :meth:`dispatch` is called. The bus keeps
    no background threads which simplifies reasoning and deterministic
    backtesting.
    """

    def __init__(self) -> None:
        self._subscribers: MutableMapping[Type[Event], List[EventHandler]] = defaultdict(list)
        self._queue: Deque[Event] = deque()
        self._dispatching: bool = False
        # Cache compiled handler lists per concrete event class.
        # This preserves the current "isinstance" semantics (subclass matches),
        # but avoids re-scanning subscriber types for every event.
        self._handler_cache: dict[type[Event], list[EventHandler]] = {}

    def subscribe(self, event_type: Type[E], handler: Callable[[E], None]) -> None:
        """
        Register a callback for a given event class.
        """

        self._subscribers[event_type].append(handler)  # type: ignore[arg-type]
        self._handler_cache.clear()

    def unsubscribe(self, event_type: Type[E], handler: Callable[[E], None]) -> None:
        """
        Remove a callback; ignores missing handlers to keep teardown simple.
        """

        handlers = self._subscribers.get(event_type)
        if not handlers:
            return
        try:
            handlers.remove(handler)  # type: ignore[arg-type]
        except ValueError:
            return
        self._handler_cache.clear()

    def publish(self, event: Event) -> None:
        """
        Enqueue an event for later dispatch.
        """

        self._queue.append(event)

    def dispatch(self) -> None:
        """
        Drain the queue and invoke subscribers.

        Re-entrant calls are ignored to guard against handlers triggering
        nested dispatches; the outermost call will flush the queue.
        """

        if self._dispatching:
            return

        self._dispatching = True
        try:
            while self._queue:
                event = self._queue.popleft()
                event_cls = type(event)
                compiled = self._handler_cache.get(event_cls)
                if compiled is None:
                    compiled = []
                    for event_type, handlers in self._subscribers.items():
                        if issubclass(event_cls, event_type):
                            compiled.extend(list(handlers))
                    self._handler_cache[event_cls] = compiled
                for handler in list(compiled):
                    handler(event)
        finally:
            self._dispatching = False

    def drain(self, events: Iterable[Event]) -> None:
        """
        Convenience helper for bulk publishing prior to a dispatch.
        """

        for event in events:
            self.publish(event)

    def clear(self) -> None:
        """
        Remove queued events and subscribers—useful for test isolation.
        """

        self._queue.clear()
        self._subscribers.clear()
        self._handler_cache.clear()

    @property
    def pending(self) -> int:
        """
        Return the number of events currently queued for dispatch.
        """

        return len(self._queue)
