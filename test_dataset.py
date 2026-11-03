from dataset import get_requests

NUM_FLOORS = 20


def test_ids_are_unique():
    ids = [r["id"] for r in get_requests()]
    assert len(ids) == len(set(ids))


def test_floors_are_in_the_building():
    for r in get_requests():
        assert 1 <= r["floor"] <= NUM_FLOORS, r["id"]
        assert 1 <= r["destination"] <= NUM_FLOORS, r["id"]


def test_no_zero_length_trips():
    for r in get_requests():
        assert r["floor"] != r["destination"], r["id"]
