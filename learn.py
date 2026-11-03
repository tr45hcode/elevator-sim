"""Teach a dispatcher by trial and error: reinforcement learning by policy search.

    python learn.py                     # about 2 minutes on 4 cores, saves learned_weights.json
    python learn.py --iterations 10     # quicker, rougher
    python building.py --dispatch learned
    python compare.py                   # tests it on days it never practiced on

How it decides: for each car it adds up a weighted list of simple facts about the
car and the caller (FEATURES below) and gives the call to the car with the lowest
total. Every 5 ticks it re-scores every waiting call. A call may move to another
car at most 3 times, so calls can't bounce between cars forever.

How it learns (the cross-entropy method): nobody tells it the right weights.
Each iteration it tries `population` random variations of its current best guess
on the same practice days, keeps the best few, and moves its guess toward them.
It never looks inside the cars. It only sees how each day turned out.
"""
import argparse
import json
import os
import random
import statistics
from multiprocessing import Pool

from dataset import generate_requests
from requests import Requests
from elevator import Elevator
from building import Building, shared

WEIGHTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learned_weights.json")

FEATURES = [
    "distance",                # floors between the car and the caller
    "on_the_way",              # car is idle, or heading toward the caller in the caller's direction
    "heading_away",            # car is moving away from the caller
    "riders",                  # how full the car is
    "assigned_calls",          # waiting calls already given to this car
    "stops",                   # floors the car already has to stop at
    "stops_before_call",       # of those, how many come before it reaches the caller
    "already_stopping_there",  # the car is stopping on the caller's floor anyway
    "full",                    # the car is full right now
    "route_distance",          # floors it travels to reach the caller, including finishing its sweep
]

GAPS = [1.0, 3.0, 10.0]  # practice on rush, busy, and quiet days


def features(request, car, building):
    """Simple facts about giving this call to this car, each scaled to roughly 0-1."""
    n = building.num_floors
    floor = request["floor"]
    call_direction = 1 if request["destination"] > floor else -1
    calls = building.calls_for(car)
    riders = car.passengers
    stops = {p["destination"] for p in riders} | {r["floor"] for r in calls}

    offset = floor - car.current_floor
    idle = not riders and not calls
    toward = offset * car.direction >= 0
    ahead = [(s - car.current_floor) * car.direction for s in stops]  # > 0 means ahead of the car
    if idle or toward:
        before = sum(1 for a in ahead if 0 < a < abs(offset))
        route = abs(offset)
    else:
        farthest = max((a for a in ahead if a > 0), default=0)
        before = sum(1 for a in ahead if a > 0)
        route = 2 * farthest + abs(offset)  # out to its farthest stop, then back past here

    return [
        abs(offset) / n,
        float(idle or (toward and car.direction == call_direction)),
        float(not idle and not toward),
        len(riders) / car.capacity,
        len(calls) / 10,
        len(stops) / n,
        before / 10,
        float(floor in stops),
        float(len(riders) >= car.capacity),
        route / n,
    ]


class LearnedDispatcher:
    """Gives each call to the car with the lowest weighted score, and re-scores waiting calls."""

    name = "learned"

    def __init__(self, weights, recheck_every=5, max_moves=3):
        self.weights = list(weights)
        self.recheck_every = recheck_every
        self.max_moves = max_moves
        self.next_check = recheck_every or 0
        self.moves = {}  # passenger id -> times moved to a different car

    @classmethod
    def load(cls, path=WEIGHTS_FILE):
        if not os.path.exists(path):
            raise FileNotFoundError(f"No {os.path.basename(path)} yet. Train one first: python learn.py")
        with open(path) as f:
            saved = json.load(f)
        if saved["features"] != FEATURES:
            raise ValueError("Saved weights were trained on different features. Retrain: python learn.py")
        return cls(saved["weights"], saved["recheck_every"])

    def score(self, request, car, building):
        return sum(w * x for w, x in zip(self.weights, features(request, car, building)))

    def __call__(self, request, building):
        return min(building.cars, key=lambda car: self.score(request, car, building))

    def tick(self, building):
        """Called by the building after every step."""
        if not self.recheck_every or building.clock < self.next_check:
            return
        self.next_check = building.clock + self.recheck_every

        for request in sorted(building.requests.get_pending_requests(), key=lambda r: r.get("time", 0)):
            if self.moves.get(request["id"], 0) >= self.max_moves:
                continue
            old_car = building.assigned.pop(request["id"])
            building.dispatch(request)
            if building.assigned[request["id"]] is not old_car:
                self.moves[request["id"]] = self.moves.get(request["id"], 0) + 1


# --- training ----------------------------------------------------------------

def _journey(dispatcher, day, max_ticks=20_000):
    building = Building([Elevator(num_floors=20), Elevator(num_floors=20)], dispatcher)
    requests = Requests([dict(p) for p in day])
    building.simulate(requests, max_ticks=max_ticks)
    return requests.stats()["avg_journey"]


def _practice_day(seed, gap):
    day = generate_requests(n=100, mean_gap=gap, seed=seed)
    return day, _journey(shared, day)


def _score(job):
    """Average journey compared with no dispatcher on the same days. 1.0 = no better, 0.9 = 10% shorter."""
    weights, days, recheck_every = job
    ratios = []
    for day, baseline in days:
        try:
            ratios.append(_journey(LearnedDispatcher(weights, recheck_every), day) / baseline)
        except RuntimeError:  # stuck: count it as a terrible day
            ratios.append(5.0)
    return statistics.mean(ratios)


def train(iterations=40, population=24, elite=6, days_per_round=12, recheck_every=5,
          workers=None, seed=0, log=print):
    """The cross-entropy method. Returns (best weights, their validation score)."""
    rng = random.Random(seed)
    k = len(FEATURES)
    mean, spread = [0.0] * k, [1.0] * k

    # Fixed days for tracking progress fairly. Practice days are fresh every round.
    validation = [_practice_day(900_000 + i, GAPS[i % 3]) for i in range(18)]
    best = (float("inf"), mean, 0)

    pool = Pool(workers) if workers != 1 else None
    try:
        for it in range(1, iterations + 1):
            days = [_practice_day(rng.randrange(1_000_000, 2_000_000), rng.choice(GAPS))
                    for _ in range(days_per_round)]
            candidates = [[rng.gauss(m, s) for m, s in zip(mean, spread)] for _ in range(population)]
            candidates.append(mean)  # keep the current guess in the running
            jobs = [(w, days, recheck_every) for w in candidates]
            scores = pool.map(_score, jobs) if pool else [_score(job) for job in jobs]

            ranked = sorted(range(len(candidates)), key=lambda i: scores[i])
            elites = [candidates[i] for i in ranked[:elite]]
            mean = [statistics.mean(column) for column in zip(*elites)]
            # A little extra spread early on, so it keeps exploring instead of settling too soon
            spread = [statistics.pstdev(column) + 0.05 * (1 - it / iterations) for column in zip(*elites)]

            score = _score((mean, validation, recheck_every))
            if score < best[0]:
                best = (score, mean, it)
            log(f"iteration {it:>2}: validation {score:.3f}   best so far {best[0]:.3f} (iteration {best[2]})")
    finally:
        if pool:
            pool.close()
            pool.join()
    return best[1], best[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--iterations", type=int, default=40, help="rounds of trial and error (default 40)")
    parser.add_argument("--population", type=int, default=24, help="variations tried per round (default 24)")
    parser.add_argument("--days", type=int, default=12, help="practice days per round (default 12)")
    parser.add_argument("--workers", type=int, default=os.cpu_count(), help="CPU cores to use (default: all)")
    parser.add_argument("--seed", type=int, default=0, help="same seed = same training run")
    args = parser.parse_args()

    print(f"Training: {args.iterations} rounds, {args.population + 1} variations x {args.days} practice days each.")
    print("Validation score = average journey vs. no dispatcher (1.000 = no better, lower is better).\n")
    weights, validation = train(iterations=args.iterations, population=args.population,
                                days_per_round=args.days, workers=args.workers, seed=args.seed)

    with open(WEIGHTS_FILE, "w") as f:
        json.dump({"features": FEATURES, "weights": weights, "recheck_every": 5,
                   "validation": validation, "seed": args.seed}, f, indent=2)
        f.write("\n")

    print("\nLearned weights (negative = makes a car more likely to get the call):")
    for name, w in sorted(zip(FEATURES, weights), key=lambda pair: pair[1]):
        print(f"  {name:<24} {w:+.2f}")
    print(f"\nSaved {os.path.basename(WEIGHTS_FILE)}. Next: python compare.py   or   python building.py --dispatch learned")


if __name__ == "__main__":
    main()
