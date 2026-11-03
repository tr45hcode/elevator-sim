"""Several elevator cars in one building, with a dispatcher deciding which car takes each call.

    python building.py                 # 2 LOOK cars, ETA dispatch, random day
    python building.py 42              # replay day 42
    python building.py 42 --dispatch zoned --cars 3 --algorithm nearest-first

Each car runs its own algorithm (elevator.py or elevator2.py) but only sees the
calls the dispatcher gave it. Dispatchers:
    eta          simulate each car forward and give the call to the one it slows down least
    learned      a scoring rule learned by trial and error (train it with: python learn.py)
    nearest-car  give each call to the most suitable car, the moment it's made
    zoned        split the floors into one band per car
    shared       no dispatcher: every car sees every call, first one there wins
"""
import argparse
import copy
import curses
import random
import time

from dataset import generate_requests
from requests import Requests
from elevator import Elevator
from elevator2 import NearestFirstElevator


# --- dispatchers: given a new call, choose the car that serves it ------------

def shared(request, building):
    """No dispatcher. Every car sees the call, and the first one there takes it."""
    return None


def zoned(request, building):
    """One band of floors per car, by the floor the call comes from."""
    cars = building.cars
    return cars[(request["floor"] - 1) * len(cars) // building.num_floors]


def nearest_car(request, building):
    """The classic nearest-car rule. Score each car and pick the best:

        heading toward the call, same way the caller wants to go:  N + 2 - distance
        heading toward the call, but the caller wants the other way: N + 1 - distance
        heading away from the call:                                  1

    where N = floors - 1. An idle car counts as heading toward the call.
    On a tie, the car with less already on its plate wins.
    """
    floor = request["floor"]
    call_direction = 1 if request["destination"] > floor else -1
    n = building.num_floors - 1

    def score(car):
        distance = abs(floor - car.current_floor)
        load = len(car.passengers) + len(building.calls_for(car))
        toward = (floor - car.current_floor) * car.direction >= 0
        if load == 0 or (toward and car.direction == call_direction):
            suitability = n + 2 - distance
        elif toward:
            suitability = n + 1 - distance
        else:
            suitability = 1
        return (suitability, -load)

    return max(building.cars, key=score)


def predict(car, calls, max_steps=100_000):
    """What would this car do with these calls, if nobody else called?

    Runs a copy of the car forward with its own algorithm, its current riders,
    and the given calls, until it's done. The real car and the real requests
    are not touched. Returns {passenger id: (pickup tick, arrival tick)} for
    the calls and the riders (riders' pickup is None, since they're already on).
    """
    clone = copy.copy(car)
    clone.passengers = list(car.passengers)
    forecast = Requests(calls)
    for p in clone.passengers:
        forecast.all_requests[p["id"]] = {"request": p, "completed": False, "picked_up_at": None}

    steps = 0
    while clone.step(forecast):
        steps += 1
        if steps > max_steps:
            raise RuntimeError("Prediction never finished. Stuck?")
    return {pid: (e["picked_up_at"], e["completed_at"]) for pid, e in forecast.all_requests.items()}


class ETA:
    """Estimated-time-of-arrival dispatch: the cost-function approach.

    To decide which car gets a new call, it asks each car "what would you do?"
    by running predict() twice: once without the new call and once with it.
    The call goes to the car whose passengers' total arrival time goes up the
    least. That counts the new caller's own wait and ride, plus how much the
    extra stop delays everyone that car is already carrying or collecting.

    It also remembers when it promised to pick each caller up. Every
    `recheck_every` ticks, any call whose car is now running late for it gets
    dispatched again, and may move to another car. Set it to None to never
    re-check.
    """

    name = "eta"

    def __init__(self, recheck_every=5):
        self.recheck_every = recheck_every
        self.next_check = recheck_every or 0
        self.promised = {}  # passenger id -> predicted pickup tick

    def __call__(self, request, building):
        best = None
        for car in building.cars:
            calls = building.calls_for(car)
            without = predict(car, calls)
            with_call = predict(car, calls + [request])
            cost = total_arrival(with_call) - total_arrival(without)
            if best is None or cost < best[0]:
                best = (cost, car, with_call[request["id"]][0])

        _, car, pickup = best
        self.promised[request["id"]] = pickup
        return car

    def tick(self, building):
        """Called by the building after every step."""
        if not self.recheck_every or building.clock < self.next_check:
            return
        self.next_check = building.clock + self.recheck_every

        late = []
        for car in building.cars:
            calls = building.calls_for(car)
            if calls:
                forecast = predict(car, calls)
                late += [r for r in calls if forecast[r["id"]][0] > self.promised[r["id"]]]

        for request in sorted(late, key=lambda r: r.get("time", 0)):
            del building.assigned[request["id"]]
            building.dispatch(request)


def total_arrival(forecast):
    return sum(arrival for _, arrival in forecast.values())


# --- the building ------------------------------------------------------------

class CarView:
    """One car's view of the building's calls: only the ones it's allowed to serve.

    It looks just like a Requests object, so the elevator algorithms work in a
    building with other cars without any changes.
    """

    def __init__(self, building, car):
        self.building = building
        self.car = car

    def release(self, now):
        self.building.release(now)

    def get_pending_requests(self):
        assigned = self.building.assigned
        return [r for r in self.building.requests.get_pending_requests()
                if assigned.get(r["id"]) in (None, self.car)]

    def remove_pending_request(self, request, now=None):
        self.building.requests.remove_pending_request(request, now)
        self.building.requests.get_all_requests()[request["id"]]["car"] = self.car.name

    def mark_completed(self, passenger_id, now=None):
        self.building.requests.mark_completed(passenger_id, now)

    def get_all_requests(self):
        return self.building.requests.get_all_requests()

    def is_empty(self):
        return self.building.requests.is_empty()


class Building:
    TICK_SECONDS = Elevator.TICK_SECONDS

    def __init__(self, cars, dispatcher=nearest_car):
        self.cars = cars
        for i, car in enumerate(cars):
            car.name = chr(ord("A") + i)
        self.dispatcher = dispatcher
        self.num_floors = cars[0].num_floors
        self.views = {car: CarView(self, car) for car in cars}
        self.requests = None
        self.assigned = {}  # passenger id -> car
        self.finished = set()
        self.stdscr = None

    # --- simulation (no screen) -----------------------------------------

    def start(self, requests):
        self.cars[0]._check_floors(requests)
        self.requests = requests
        for request in list(requests.get_pending_requests()):  # calls made at tick 0
            self.dispatch(request)

    def release(self, now):
        for request in self.requests.release(now):
            self.dispatch(request)

    def dispatch(self, request):
        car = self.dispatcher(request, self)
        if car is not None:
            self.assigned[request["id"]] = car

    def calls_for(self, car):
        """Waiting calls the dispatcher has given to this car."""
        return [r for r in self.requests.get_pending_requests() if self.assigned.get(r["id"]) is car]

    def step(self):
        """Advance whichever car is furthest behind in time. Returns False when the day is over.

        Cars' clocks drift apart (a stop takes several ticks, a move takes one).
        Always moving the car that's furthest behind means no car ever sees a
        call from its own future.
        """
        active = [car for car in self.cars if car not in self.finished]
        if not active:
            return False
        car = min(active, key=lambda c: c.clock)
        if not car.step(self.views[car]):
            self.finished.add(car)

        tick = getattr(self.dispatcher, "tick", None)  # dispatchers that re-check, like ETA
        if tick:
            tick(self)
        return True

    @property
    def clock(self):
        active = [car.clock for car in self.cars if car not in self.finished]
        return min(active) if active else max(car.clock for car in self.cars)

    def simulate(self, requests, max_ticks=1_000_000):
        """Run a whole day with no screen and no sleeping."""
        self.start(requests)
        while self.step():
            if self.clock > max_ticks:
                raise RuntimeError(f"Still running after {max_ticks} ticks. Stuck?")
        return requests

    # --- terminal view --------------------------------------------------

    def run(self, requests):
        """Watch the simulation in the terminal."""
        self.start(requests)
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()

        try:
            shown = self.clock
            self.draw()
            while self.step():
                if self.clock > shown:
                    self.draw()
                    time.sleep((self.clock - shown) * self.TICK_SECONDS)
                    shown = self.clock

            self.draw()
            y = self.num_floors + len(self.cars) + 1
            if y < self.stdscr.getmaxyx()[0]:
                self.stdscr.addstr(y, 0, f"Finished at tick {self.clock}.")
                self.stdscr.clrtoeol()
                self.stdscr.refresh()
                time.sleep(3)
        finally:
            try:
                curses.endwin()
            except curses.error:
                pass

    def draw(self):
        try:
            scr = self.stdscr
            scr.clear()
            max_y, max_x = scr.getmaxyx()

            def put(y, text):
                if y < max_y:
                    scr.addstr(y, 0, text[:max_x - 1])  # never the last column, so the last row is safe

            pending = self.requests.get_pending_requests()
            waiting = {}
            for r in pending:
                waiting[r["floor"]] = waiting.get(r["floor"], 0) + 1

            # One shaft per car
            for i in range(self.num_floors, 0, -1):
                shafts = " ".join(car.name if car.current_floor == i else "|" for car in self.cars)
                queue = f"  waiting: {waiting[i]}" if i in waiting else ""
                put(self.num_floors - i, f"[{i:2d}] {shafts}{queue}")

            # One line per car
            y = self.num_floors + 1
            for car in self.cars:
                direction = "UP" if car.direction == 1 else "DOWN"
                riders = ", ".join(f"{p['id']}(->{p['destination']})" for p in car.passengers)
                put(y, f"{car.name}  {direction:<4} {len(car.passengers):>2}/{car.capacity}  {riders}")
                y += 1

            dispatch = getattr(self.dispatcher, "name", None) or self.dispatcher.__name__.replace("_", "-")
            put(y, f"Tick: {self.clock}   Waiting: {len(pending)}   Dispatch: {dispatch}")
            y += 2

            put(y, "All Requests (X = done, . = hasn't called yet, letter = car):")
            y += 1
            for req_id, entry in self.requests.get_all_requests().items():
                if y >= max_y:
                    break
                req = entry["request"]
                if entry["completed"]:
                    status = "X"
                elif req.get("time", 0) > self.clock:
                    status = "."
                else:
                    status = " "
                car = entry.get("car") or getattr(self.assigned.get(req_id), "name", "")
                put(y, f"  [{status}] {req_id} t={req.get('time', 0)}: {req['floor']} -> {req['destination']}  {car}")
                y += 1

            scr.refresh()
        except curses.error:
            # If drawing fails, just continue - terminal might be too small
            pass


ALGORITHMS = {"look": Elevator, "nearest-first": NearestFirstElevator}

def _learned():
    from learn import LearnedDispatcher  # imported here because learn.py itself uses Building
    return LearnedDispatcher.load()


# Each entry makes a fresh dispatcher, because ETA and learned remember things between calls.
DISPATCHERS = {
    "eta": ETA,
    "learned": _learned,
    "nearest-car": lambda: nearest_car,
    "zoned": lambda: zoned,
    "shared": lambda: shared,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("seed", type=int, nargs="?", help="replay this day (default: a random one)")
    parser.add_argument("--cars", type=int, default=2, help="number of cars (default 2)")
    parser.add_argument("--dispatch", choices=DISPATCHERS, default="eta")
    parser.add_argument("--algorithm", choices=ALGORITHMS, default="look", help="what each car runs")
    parser.add_argument("--passengers", type=int, default=50, help="passengers in the day (default 50)")
    parser.add_argument("--gap", type=float, default=2.0, help="average ticks between calls (default 2)")
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(10_000)
    requests = Requests(generate_requests(n=args.passengers, mean_gap=args.gap, seed=seed))
    cars = [ALGORITHMS[args.algorithm](num_floors=20) for _ in range(args.cars)]
    building = Building(cars, DISPATCHERS[args.dispatch]())
    building.run(requests)

    s = requests.stats()
    served = {car.name: 0 for car in cars}
    for entry in requests.get_all_requests().values():
        served[entry["car"]] += 1
    print(f"{args.cars} x {args.algorithm}, {args.dispatch} dispatch, day {seed}: finished at tick {building.clock}")
    print(f"  wait     avg {s['avg_wait']:.1f}, worst {s['max_wait']} ticks")
    print(f"  journey  avg {s['avg_journey']:.1f} ticks (call to arrival)")
    print("  served   " + ", ".join(f"{name}: {count}" for name, count in served.items()))
    print(f"Same day with one car: python elevator.py {seed}")


if __name__ == "__main__":
    main()
