import random

from dataset import generate_requests
from requests import Requests
from elevator import Elevator
from building import Building, DISPATCHERS
from learn import FEATURES, LearnedDispatcher, features, train


def two_cars(dispatcher):
    return Building([Elevator(num_floors=20), Elevator(num_floors=20)], dispatcher)


def test_features_of_an_idle_car_on_the_callers_floor():
    building = two_cars(LearnedDispatcher([0.0] * len(FEATURES)))
    building.start(Requests())
    car = building.cars[0]
    facts = dict(zip(FEATURES, features({"id": "x", "floor": 1, "destination": 9}, car, building)))
    assert facts["distance"] == 0
    assert facts["on_the_way"] == 1
    assert facts["heading_away"] == 0
    assert facts["route_distance"] == 0


def test_random_weights_never_get_stuck():
    # Re-scoring could bounce a call between cars forever. The move limit prevents it.
    rng = random.Random(1)
    for trial in range(15):
        weights = [rng.gauss(0, 2) for _ in FEATURES]
        day = generate_requests(n=60, mean_gap=1.5, seed=trial)
        requests = two_cars(LearnedDispatcher(weights)).simulate(Requests(day), max_ticks=20_000)
        assert requests.stats()["delivered"] == len(day)


def test_training_runs_and_is_repeatable():
    def tiny():
        return train(iterations=2, population=4, elite=2, days_per_round=1, workers=1, log=lambda *_: None)
    weights, score = tiny()
    assert len(weights) == len(FEATURES)
    assert (weights, score) == tiny()


def test_saved_weights_load():
    dispatcher = DISPATCHERS["learned"]()
    assert len(dispatcher.weights) == len(FEATURES)
