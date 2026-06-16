"""
Unit tests for BoundedList (Phase 4D).
"""

import copy
import pickle
import operator

import pytest

from backend.graph.state import BoundedList


# ── construction ─────────────────────────────────────────────────────────────

class TestConstruction:
    def test_empty(self):
        bl = BoundedList[int](maxlen=5)
        assert bl.maxlen == 5
        assert list(bl) == []

    def test_with_initial_items(self):
        bl = BoundedList[int](maxlen=3, initlist=[1, 2])
        assert list(bl) == [1, 2]

    def test_initial_items_exceed_maxlen(self):
        bl = BoundedList[int](maxlen=3, initlist=[1, 2, 3, 4, 5])
        # Only the 3 most-recent items should be retained
        assert list(bl) == [3, 4, 5]

    def test_maxlen_less_than_one_raises(self):
        with pytest.raises(ValueError, match="maxlen must be >= 1"):
            BoundedList[int](maxlen=0)
        with pytest.raises(ValueError, match="maxlen must be >= 1"):
            BoundedList[int](maxlen=-1)


# ── append ───────────────────────────────────────────────────────────────────

class TestAppend:
    def test_append_within_limit(self):
        bl = BoundedList[int](maxlen=3)
        bl.append(1); bl.append(2)
        assert list(bl) == [1, 2]

    def test_append_exceeds_limit(self):
        bl = BoundedList[int](maxlen=3, initlist=[1, 2, 3])
        bl.append(4)
        assert list(bl) == [2, 3, 4]  # oldest (1) dropped

    def test_append_multiple_evictions(self):
        bl = BoundedList[int](maxlen=2)
        bl.append(1); bl.append(2); bl.append(3); bl.append(4)
        assert list(bl) == [3, 4]


# ── extend ───────────────────────────────────────────────────────────────────

class TestExtend:
    def test_extend_within_limit(self):
        bl = BoundedList[int](maxlen=5, initlist=[1, 2])
        bl.extend([3, 4])
        assert list(bl) == [1, 2, 3, 4]

    def test_extend_exceeds_limit(self):
        bl = BoundedList[int](maxlen=3, initlist=[1])
        bl.extend([2, 3, 4])
        assert list(bl) == [2, 3, 4]

    def test_extend_drops_oldest(self):
        bl = BoundedList[int](maxlen=3, initlist=[1, 2])
        bl.extend([3, 4, 5])
        assert list(bl) == [3, 4, 5]

    def test_extend_source_exceeds_maxlen(self):
        bl = BoundedList[int](maxlen=3)
        bl.extend([1, 2, 3, 4, 5])
        assert list(bl) == [3, 4, 5]


# ── operator.add semantics (LangGraph reducer) ─────────────────────────────

class TestOperatorAdd:
    def test_add_two_bounded_lists(self):
        a = BoundedList[int](maxlen=5, initlist=[1, 2])
        b = BoundedList[int](maxlen=5, initlist=[3, 4])
        c = a + b
        assert list(c) == [1, 2, 3, 4]
        # Original lists unchanged
        assert list(a) == [1, 2]
        assert list(b) == [3, 4]

    def test_add_exceeds_maxlen(self):
        a = BoundedList[int](maxlen=3, initlist=[1, 2])
        b = BoundedList[int](maxlen=3, initlist=[3, 4])
        c = a + b
        # Merged = [1,2,3,4]; truncate to maxlen=3 → [2,3,4]
        assert list(c) == [2, 3, 4]

    def test_add_with_plain_list(self):
        a = BoundedList[int](maxlen=4, initlist=[1, 2])
        c = a + [3, 4]
        assert list(c) == [1, 2, 3, 4]

    def test_radd_with_plain_list(self):
        a = BoundedList[int](maxlen=4, initlist=[3, 4])
        c = [1, 2] + a
        assert list(c) == [1, 2, 3, 4]

    def test_iadd(self):
        a = BoundedList[int](maxlen=4, initlist=[1, 2])
        a += [3, 4]
        assert list(a) == [1, 2, 3, 4]

    def test_iadd_exceeds_maxlen(self):
        a = BoundedList[int](maxlen=3, initlist=[1, 2])
        a += [3, 4, 5]
        assert list(a) == [3, 4, 5]

    def test_operator_add_direct(self):
        """Simulate LangGraph's Annotated[BoundedList, operator.add]."""
        bl = BoundedList[int](maxlen=3, initlist=[1])
        merged = operator.add(bl, BoundedList[int](maxlen=3, initlist=[2, 3, 4]))
        assert list(merged) == [2, 3, 4]


# ── serialization ────────────────────────────────────────────────────────────

class TestSerialization:
    def test_to_list(self):
        bl = BoundedList[str](maxlen=3, initlist=["a", "b"])
        assert bl.to_list() == ["a", "b"]

    def test_from_list(self):
        bl = BoundedList[str].from_list(["x", "y", "z", "w"], maxlen=2)
        assert list(bl) == ["z", "w"]
        assert bl.maxlen == 2

    def test_pickle_round_trip(self):
        bl = BoundedList[int](maxlen=5, initlist=[1, 2, 3])
        data = pickle.dumps(bl)
        restored = pickle.loads(data)
        assert list(restored) == [1, 2, 3]
        assert restored.maxlen == 5

    def test_pickle_after_append(self):
        bl = BoundedList[int](maxlen=3, initlist=[1, 2])
        bl.append(3); bl.append(4)  # drops 1
        data = pickle.dumps(bl)
        restored = pickle.loads(data)
        assert list(restored) == [2, 3, 4]
        assert restored.maxlen == 3


# ── copy ─────────────────────────────────────────────────────────────────────

class TestCopy:
    def test_shallow_copy(self):
        bl = BoundedList[int](maxlen=5, initlist=[1, 2, 3])
        c = bl.copy()
        assert list(c) == [1, 2, 3]
        assert c.maxlen == 5
        # Mutating copy does not affect original
        c.append(4)
        assert list(bl) == [1, 2, 3]

    def test_deepcopy(self):
        bl = BoundedList[list](maxlen=3, initlist=[[1], [2]])
        c = copy.deepcopy(bl)
        c.data[0].append(99)
        # Original unchanged
        assert bl.data[0] == [1]

    def test_copy_module_copy(self):
        import copy
        bl = BoundedList[int](maxlen=5, initlist=[1, 2])
        c = copy.copy(bl)
        assert list(c) == [1, 2]
        assert c.maxlen == 5


# ── edge cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_maxlen_one(self):
        bl = BoundedList[int](maxlen=1)
        bl.append(1); bl.append(2); bl.append(3)
        assert list(bl) == [3]

    def test_maxlen_one_via_extend(self):
        bl = BoundedList[int](maxlen=1)
        bl.extend([1, 2, 3])
        assert list(bl) == [3]

    def test_append_to_full_list(self):
        bl = BoundedList[int](maxlen=3, initlist=[1, 2, 3])
        bl.append(4)
        assert list(bl) == [2, 3, 4]

    def test_extend_empty(self):
        bl = BoundedList[int](maxlen=3, initlist=[1, 2])
        bl.extend([])
        assert list(bl) == [1, 2]

    def test_empty_extend(self):
        bl = BoundedList[int](maxlen=3)
        bl.extend([1, 2, 3, 4])
        assert list(bl) == [2, 3, 4]

    def test_bool(self):
        assert bool(BoundedList[int](maxlen=3)) is False
        assert bool(BoundedList[int](maxlen=3, initlist=[1])) is True

    def test_len(self):
        bl = BoundedList[int](maxlen=5, initlist=[1, 2, 3])
        assert len(bl) == 3

    def test_iteration(self):
        bl = BoundedList[int](maxlen=3, initlist=[10, 20, 30])
        assert list(iter(bl)) == [10, 20, 30]

    def test_index_access(self):
        bl = BoundedList[int](maxlen=3, initlist=[10, 20, 30])
        assert bl[0] == 10
        assert bl[-1] == 30

    def test_repr(self):
        bl = BoundedList[int](maxlen=3, initlist=[1, 2])
        r = repr(bl)
        assert "maxlen=3" in r
        assert "1, 2" in r


# ── integration: LangGraph-like reducer pattern ──────────────────────────

class TestReducerPattern:
    """Simulate how LangGraph applies updates via Annotated[Type, operator.add]."""

    def test_two_node_updates(self):
        """Simulate two nodes each returning chunks that get merged."""
        state = BoundedList[str](maxlen=5)
        # Node 1 returns some chunks
        node1_result = ["chunk_a", "chunk_b"]
        state = operator.add(state, BoundedList[str](maxlen=5, initlist=node1_result))
        # Node 2 returns more chunks
        node2_result = ["chunk_c"]
        state = operator.add(state, BoundedList[str](maxlen=5, initlist=node2_result))
        assert list(state) == ["chunk_a", "chunk_b", "chunk_c"]

    def test_reducer_with_overflow(self):
        """Simulate healing retries that keep adding error entries."""
        error_log = BoundedList[str](maxlen=5)
        for i in range(10):
            error_log = operator.add(error_log, BoundedList[str](maxlen=5, initlist=[f"error_{i}"]))
        # Only the last 5 errors remain
        assert list(error_log) == ["error_5", "error_6", "error_7", "error_8", "error_9"]

    def test_empty_add(self):
        """operator.add with empty list is a no-op."""
        bl = BoundedList[int](maxlen=3, initlist=[1, 2])
        result = operator.add(bl, BoundedList[int](maxlen=3))
        assert list(result) == [1, 2]