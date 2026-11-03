import random


def generate_requests(n=50, num_floors=20, mean_gap=2.0, seed=None):
    """A random day: n passengers calling the lift at random times.

    Gaps between calls follow an exponential distribution (a Poisson
    process): mostly short gaps with the odd long lull, like people turning
    up independently. mean_gap is the average gap in ticks, so lower means
    a busier building. The same seed always gives the same day.
    """
    rng = random.Random(seed)
    t = 0.0
    passengers = []
    for i in range(1, n + 1):
        t += rng.expovariate(1 / mean_gap)
        floor = rng.randint(1, num_floors)
        destination = rng.choice([f for f in range(1, num_floors + 1) if f != floor])
        passengers.append({"id": f"P{i}", "time": round(t), "floor": floor, "destination": destination})
    return passengers


def get_requests():
    """The fixed dataset: everyone calls at tick 0."""
    return [
        {'id': 'P1', 'floor': 17, 'destination': 1},
        {'id': 'P2', 'floor': 12, 'destination': 5},
        {'id': 'P3', 'floor': 3, 'destination': 18},
        {'id': 'P4', 'floor': 1, 'destination': 15},
        {'id': 'P5', 'floor': 19, 'destination': 2},
        {'id': 'P6', 'floor': 6, 'destination': 18},
        {'id': 'P7', 'floor': 11, 'destination': 4},
        {'id': 'P8', 'floor': 8, 'destination': 16},
        {'id': 'P9', 'floor': 14, 'destination': 7},
        {'id': 'P10', 'floor': 5, 'destination': 13},
        {'id': 'P11', 'floor': 2, 'destination': 18},
        {'id': 'P12', 'floor': 18, 'destination': 3},
        {'id': 'P13', 'floor': 7, 'destination': 17},
        {'id': 'P14', 'floor': 16, 'destination': 6},
        {'id': 'P15', 'floor': 13, 'destination': 9},
        {'id': 'P16', 'floor': 4, 'destination': 11},
        {'id': 'P17', 'floor': 20, 'destination': 8},
        {'id': 'P18', 'floor': 9, 'destination': 14},
        {'id': 'P19', 'floor': 15, 'destination': 10},
        {'id': 'P20', 'floor': 10, 'destination': 12},
        {'id': 'P21', 'floor': 1, 'destination': 18},
        {'id': 'P22', 'floor': 20, 'destination': 1},
        {'id': 'P23', 'floor': 2, 'destination': 18},
        {'id': 'P24', 'floor': 18, 'destination': 2},
        {'id': 'P25', 'floor': 3, 'destination': 17},
        {'id': 'P26', 'floor': 17, 'destination': 3},
        {'id': 'P27', 'floor': 4, 'destination': 16},
        {'id': 'P28', 'floor': 16, 'destination': 4},
        {'id': 'P29', 'floor': 5, 'destination': 15},
        {'id': 'P30', 'floor': 15, 'destination': 5},
        {'id': 'P31', 'floor': 6, 'destination': 14},
        {'id': 'P32', 'floor': 14, 'destination': 6},
        {'id': 'P33', 'floor': 7, 'destination': 13},
        {'id': 'P34', 'floor': 13, 'destination': 7},
        {'id': 'P35', 'floor': 8, 'destination': 12},
        {'id': 'P36', 'floor': 12, 'destination': 8},
        {'id': 'P37', 'floor': 9, 'destination': 11},
        {'id': 'P38', 'floor': 11, 'destination': 9},
        {'id': 'P39', 'floor': 10, 'destination': 11},
        {'id': 'P40', 'floor': 1, 'destination': 10},
        {'id': 'P41', 'floor': 10, 'destination': 1},
        {'id': 'P42', 'floor': 2, 'destination': 9},
        {'id': 'P43', 'floor': 9, 'destination': 2},
        {'id': 'P44', 'floor': 3, 'destination': 8},
        {'id': 'P45', 'floor': 8, 'destination': 3},
        {'id': 'P46', 'floor': 4, 'destination': 7},
        {'id': 'P47', 'floor': 7, 'destination': 4},
        {'id': 'P48', 'floor': 5, 'destination': 6},
        {'id': 'P49', 'floor': 6, 'destination': 5},
        {'id': 'P50', 'floor': 1, 'destination': 2},
        {'id': 'P51', 'floor':20, 'destination': 3}
    ]
