import pytest

from dataset import generate_requests
from requests import Requests
from elevator import Elevator
from elevator2 import NearestFirstElevator

ALGORITHMS = [Elevator, NearestFirstElevator]


def test_same_seed_same_day():
    assert generate_requests(seed=42) == generate_requests(seed=42)
    assert generate_requests(seed=42) != generate_requests(seed=43)


def test_generated_days_are_valid():
    for seed in range(50):
        day = generate_requests(seed=seed)
        times = [p["time"] for p in day]
        assert times == sorted(times)
        for p in day:
            assert 1 <= p["floor"] <= 20, p
            assert 1 <= p["destination"] <= 20, p
            assert p["floor"] != p["destination"], p


def test_calls_stay_hidden_until_their_time():
    r = Requests([
        {"id": "A", "time": 0, "floor": 1, "destination": 5},
        {"id": "B", "time": 5, "floor": 3, "destination": 9},
    ])
    assert [p["id"] for p in r.get_pending_requests()] == ["A"]
    r.release(4)
    assert [p["id"] for p in r.get_pending_requests()] == ["A"]
    r.release(5)
    assert [p["id"] for p in r.get_pending_requests()] == ["A", "B"]
    assert not r.is_empty()


@pytest.mark.parametrize("elevator_class", ALGORITHMS)
def test_door_and_boarding_time(elevator_class):
    # One passenger, floor 1 -> 3, calling at tick 0:
    # board (2 door + 1 person) + 2 floors + alight (2 door + 1 person) = 8 ticks
    day = [{"id": "P1", "time": 0, "floor": 1, "destination": 3}]

    slow = elevator_class(num_floors=20)
    slow.simulate(Requests([dict(p) for p in day]))
    assert slow.clock == 8

    instant = elevator_class(num_floors=20, door_time=0, board_time=0)
    instant.simulate(Requests([dict(p) for p in day]))
    assert instant.clock == 2


@pytest.mark.parametrize("elevator_class", ALGORITHMS)
def test_waits_idle_for_a_late_caller(elevator_class):
    day = [{"id": "LATE", "time": 30, "floor": 1, "destination": 2}]
    elevator = elevator_class(num_floors=20)
    requests = elevator.simulate(Requests(day))
    entry = requests.get_all_requests()["LATE"]
    assert entry["picked_up_at"] == 30  # waited on floor 1 until they called
    assert entry["completed"]


@pytest.mark.parametrize("elevator_class", ALGORITHMS)
def test_random_days_follow_the_rules(elevator_class):
    for seed in range(30):
        day = generate_requests(n=60, mean_gap=2.0, seed=seed)
        elevator = elevator_class(num_floors=20)
        requests = Requests([dict(p) for p in day])

        while elevator.step(requests):
            assert len(elevator.passengers) <= elevator.capacity
            assert 1 <= elevator.current_floor <= 20
            assert elevator.clock < 100_000, "stuck"

        assert requests.stats()["delivered"] == len(day)
        for entry in requests.get_all_requests().values():
            assert entry["picked_up_at"] >= entry["request"]["time"], "picked up before calling"


def test_out_of_range_floor_is_rejected():
    elevator = Elevator(num_floors=20)
    with pytest.raises(ValueError, match="P9"):
        elevator.simulate(Requests([{"id": "P9", "floor": 25, "destination": 3}]))
