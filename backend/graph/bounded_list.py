"""
Phase 4D — BoundedList

A list-like container with a configurable maximum length (``maxlen``).
When the list would exceed *maxlen* the oldest items are discarded to make
room for new ones.  This prevents unbounded state growth in long-running
workflows.

Supports ``operator.add`` semantics, making it a drop-in replacement for
``Annotated[list, operator.add]`` in LangGraph state reducers.

Serialization
-------------
* ``to_list()`` / ``from_list(items, maxlen)``  — round-trip through plain
  Python lists (Pydantic-friendly).
* ``__getstate__`` / ``__setstate__`` — pickle support (e.g. for cross-process
  message passing).
"""

from __future__ import annotations

import copy
from collections import UserList
from typing import (
    Any,
    Generic,
    Iterator,
    List,
    Optional,
    overload,
    TypeVar,
    Union,
)

_T = TypeVar("_T")


class BoundedList(UserList[_T], Generic[_T]):
    """A list that never exceeds *maxlen* items.

    Parameters
    ----------
    maxlen : int
        Maximum number of items.  When ``append`` or ``extend`` would cause
        the list to hold more than *maxlen* items the **oldest** items are
        dropped.
    initlist : iterable, optional
        Initial items.  If the iterable yields more than *maxlen* items only
        the *maxlen* most-recent items are retained.
    """

    def __init__(
        self,
        maxlen: int,
        initlist: Optional[Union[List[_T], "BoundedList[_T]"]] = None,
    ):
        if maxlen < 1:
            raise ValueError("maxlen must be >= 1")
        self.maxlen: int = maxlen
        # UserList.__init__ calls self.data = list(initlist) which may
        # produce more items than maxlen – trim afterwards.
        super().__init__(initlist or [])
        self._truncate()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _truncate(self) -> None:
        """Drop oldest items when **self.data** exceeds *maxlen*."""
        if len(self.data) > self.maxlen:
            self.data[: len(self.data) - self.maxlen] = []

    # ── mutation ─────────────────────────────────────────────────────────────

    def append(self, item: _T) -> None:
        """Append *item*.  If the list is already at *maxlen* the oldest item
        is discarded first."""
        if len(self.data) >= self.maxlen:
            self.data.pop(0)
        self.data.append(item)

    def extend(self, other: Union[List[_T], "BoundedList[_T]"]) -> None:
        """Extend by *other*, discarding oldest items as necessary."""
        # Fast path: pop as many as needed, then extend.
        items: List[_T] = list(other)
        overflow = len(self.data) + len(items) - self.maxlen
        if overflow > 0:
            del self.data[:overflow]
        self.data.extend(items)
        # In case other itself had > maxlen items, trim once more.
        self._truncate()

    def __iadd__(self, other: Union[List[_T], "BoundedList[_T]"]) -> "BoundedList[_T]":
        self.extend(other)
        return self

    def __add__(self, other: Union[List[_T], "BoundedList[_T]"]) -> "BoundedList[_T]":
        """Return a **new** ``BoundedList`` whose contents are the merged
        items of ``self`` and *other*, truncated to *self.maxlen*.

        This enables ``Annotated[BoundedList, operator.add]`` reducer
        semantics in LangGraph state."""
        new = self.copy()
        new.extend(other)
        return new

    def __radd__(self, other: Union[List[_T], "BoundedList[_T]"]) -> "BoundedList[_T]":
        """Support ``list + BoundedList``."""
        if isinstance(other, list):
            merged = BoundedList[_T](maxlen=self.maxlen, initlist=other)
            merged.extend(self)
            return merged
        return self.__add__(other)

    # ── copy ─────────────────────────────────────────────────────────────────

    def copy(self) -> "BoundedList[_T]":
        return BoundedList[_T](maxlen=self.maxlen, initlist=list(self.data))

    def __copy__(self) -> "BoundedList[_T]":
        return self.copy()

    def __deepcopy__(self, memo: dict) -> "BoundedList[_T]":
        return BoundedList[_T](
            maxlen=self.maxlen,
            initlist=copy.deepcopy(self.data, memo),
        )

    # ── serialization ───────────────────────────────────────────────────────

    def to_list(self) -> List[_T]:
        """Return the current items as a plain Python list."""
        return list(self.data)

    @classmethod
    def from_list(
        cls,
        items: List[_T],
        maxlen: int,
    ) -> "BoundedList[_T]":
        """Construct a ``BoundedList`` from a plain list, retaining at most
        *maxlen* items."""
        return cls(maxlen=maxlen, initlist=items)

    # Pickle support
    def __getstate__(self) -> dict:
        return {"maxlen": self.maxlen, "data": self.data}

    def __setstate__(self, state: dict) -> None:
        self.maxlen = state["maxlen"]
        self.data = state["data"]

    # ── display / repr ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"BoundedList(maxlen={self.maxlen}, items={list(self.data)})"

    def __str__(self) -> str:
        return repr(self)