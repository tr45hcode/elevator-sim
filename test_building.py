import pytest

from dataset import generate_requests
from requests import Requests
from elevator import Elevator
from elevator2 import NearestFirstElevator
from building import Building, DISPATCHERS, ETA, nearest_car, zoned, shared, predict

ALGORITHMS = [Elevator, NearestFirstElevator]


def fresh(day):
    return Requests([dict(p) for p in day])


@pytest.mark.parametrize("car_class", ALGORITHMS)
def test_one_car_building_matches_a_lone_elevator(car_class):
    for seed in range(20):
        day = generate_requests(n=60, seed=seed)
        lone = car_class(num_floors=20)
        lone_requests = lone.simulate(fresh(day))

        building = Building([car_class(num_floors=20)], shared)
        building_requests = building.simulate(fresh(day))

        assert building.clock == lone.clock
        assert building_requests.stats() == lone_requests.stats()


@pytest.mark.parametrize("car_class", ALGORITHMS)
@pytest.mark.parametrize("dispatcher", DISPATCHERS)
def test_two_cars_follow_the_rules(car_class, dispatcher):
    for seed in range(15):
        day = generate_requests(n=60, mean_gap=2.0, seed=seed)
        building = Building([car_class(num_floors=20), car_class(num_floors=20)], DISPATCHERS[dispatcher]())
        requests = fresh(day)

        building.start(requests)
        while building.step():
            for car in building.cars:
                assert len(car.passengers) <= car.capacity
                assert 1 <= car.current_floor <= 20
            assert building.clock < 100_000, "stuck"

        assert requests.stats()["delivered"] == len(day)
        for pid, entry in requests.get_all_requests().items():
            assert entry["picked_up_at"] >= entry["request"]["time"], "picked up before calling"
            if dispatcher != "shared":
                assert entry["car"] == building.assigned[pid].name, "picked up by the wrong car"


def test_zoned_splits_the_floors():
    building = Building([Elevator(num_floors=20), Elevator(num_floors=20)], zoned)
    a, b = building.cars
    for floor, car in [(1, a), (10, a), (11, b), (20, b)]:
        assert zoned({"id": "x", "floor": floor, "destination": 5}, building) is car


def test_nearest_car_sends_the_closer_idle_car():
    building = Building([Elevator(num_floors=20), Elevator(num_floors=20)], nearest_car)
    building.start(Requests())
    a, b = building.cars
    b.current_floor = 15
    assert nearest_car({"id": "x", "floor": 14, "destination": 2}, building) is b
    assert nearest_car({"id": "y", "floor": 3, "destination": 9}, building) is a


def test_a_second_car_cuts_waiting_on_busy_days():
    one_car, two_cars = [], []
    for seed in range(20):
        day = generate_requests(n=80, mean_gap=2.0, seed=seed)
        one_car.append(Building([Elevator(num_floors=20)], shared).simulate(fresh(day)).stats()["avg_wait"])
        pair = [Elevator(num_floors=20), Elevator(num_floors=20)]
        two_cars.append(Building(pair, nearest_car).simulate(fresh(day)).stats()["avg_wait"])
    assert sum(two_cars) < sum(one_car)


def test_predict_leaves_the_real_car_alone():
    car = Elevator(num_floors=20)
    requests = Requests(generate_requests(n=30, mean_gap=0.1, seed=3))
    requests.release(10)
    calls = list(requests.get_pending_requests())
    before = (car.clock, car.current_floor, car.direction, list(car.passengers), list(calls))

    predict(car, calls)

    assert (car.clock, car.current_floor, car.direction, list(car.passengers), list(calls)) == before
    assert requests.get_pending_requests() == calls
    assert all("picked_up_at" not in e for e in requests.get_all_requests().values())


@pytest.mark.parametrize("car_class", ALGORITHMS)
def test_predict_matches_what_actually_happens(car_class):
    # With no new calls arriving, the forecast should be exactly right.
    for seed in range(10):
        day = [{**p, "time": 0} for p in generate_requests(n=40, seed=seed)]
        requests = Requests(day)
        car = car_class(num_floors=20)

        forecast = predict(car, requests.get_pending_requests())
        car.simulate(requests)

        for pid, entry in requests.get_all_requests().items():
            assert forecast[pid] == (entry["picked_up_at"], entry["completed_at"]), pid


def test_eta_beats_shared_on_busy_days():
    eta, no_dispatcher = [], []
    for seed in range(10):
        day = generate_requests(n=80, mean_gap=3.0, seed=seed)
        for results, dispatcher in ((eta, ETA()), (no_dispatcher, shared)):
            building = Building([Elevator(num_floors=20), Elevator(num_floors=20)], dispatcher)
            results.append(building.simulate(fresh(day)).stats()["avg_journey"])
    assert sum(eta) < sum(no_dispatcher)
