"""Compare elevator setups on random days, with no screen, so it runs fast.

    python compare.py                       # 30 random days at each traffic level (~1 min)
    python compare.py --days 100            # steadier numbers, slower
    python compare.py --seed 42 --gap 2     # one particular day

All times are in ticks (1 tick = moving one floor).
ETA is much slower than the others: it simulates each car forward for every decision.
"""
import argparse
import os
import statistics

from dataset import generate_requests, get_requests
from requests import Requests
from elevator import Elevator
from elevator2 import NearestFirstElevator
from building import Building, DISPATCHERS
from learn import WEIGHTS_FILE

# name: (number of cars, what each car runs, dispatcher)
SETUPS = {
    "1 car  LOOK": (1, Elevator, "shared"),
    "1 car  nearest-first": (1, NearestFirstElevator, "shared"),
    "2 cars LOOK, shared": (2, Elevator, "shared"),
    "2 cars LOOK, zoned": (2, Elevator, "zoned"),
    "2 cars LOOK, nearest-car": (2, Elevator, "nearest-car"),
    "2 cars LOOK, eta": (2, Elevator, "eta"),
    "2 cars LOOK, learned": (2, Elevator, "learned"),
    "2 cars nearest-first, shared": (2, NearestFirstElevator, "shared"),
    "2 cars nearest-first, nearest-car": (2, NearestFirstElevator, "nearest-car"),
    "2 cars nearest-first, eta": (2, NearestFirstElevator, "eta"),
}

# Average ticks between calls. Lower = busier building.
TRAFFIC = {
    "Rush hour": 1.0,
    "Busy": 3.0,
    "Quiet": 10.0,
}


def run_day(setup, passengers):
    count, car_class, dispatcher = setup
    building = Building([car_class(num_floors=20) for _ in range(count)], DISPATCHERS[dispatcher]())
    requests = Requests([dict(p) for p in passengers])
    building.simulate(requests)
    return {**requests.stats(), "finish": building.clock}


def print_table(title, results):
    width = max(len(name) for name in results)
    print(f"\n{title}")
    print(f"  {'':<{width}} {'avg wait':>9} {'worst wait':>11} {'avg ride':>9} {'avg journey':>12} {'finished at':>12}")
    for name, r in results.items():
        print(f"  {name:<{width}} {r['avg_wait']:>9.1f} {r['max_wait']:>11.1f} {r['avg_ride']:>9.1f} "
              f"{r['avg_journey']:>12.1f} {r['finish']:>12.1f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=30, help="random days per traffic level (default 30)")
    parser.add_argument("--passengers", type=int, default=100, help="passengers per day (default 100)")
    parser.add_argument("--seed", type=int, help="run just this one day")
    parser.add_argument("--gap", type=float, default=3.0, help="average ticks between calls, for --seed (default 3)")
    args = parser.parse_args()

    if not os.path.exists(WEIGHTS_FILE):
        for name in [n for n, setup in SETUPS.items() if setup[2] == "learned"]:
            del SETUPS[name]
        print("(No learned dispatcher yet. Run python learn.py to add it to this table.)")

    if args.seed is not None:
        day = generate_requests(n=args.passengers, mean_gap=args.gap, seed=args.seed)
        print_table(f"Day {args.seed}: {args.passengers} passengers, a call every ~{args.gap:g} ticks",
                    {name: run_day(setup, day) for name, setup in SETUPS.items()})
        return

    print_table("Fixed dataset (dataset.py): everyone calls at tick 0",
                {name: run_day(setup, get_requests()) for name, setup in SETUPS.items()})

    for label, gap in TRAFFIC.items():
        days = {name: [] for name in SETUPS}
        for seed in range(args.days):
            day = generate_requests(n=args.passengers, mean_gap=gap, seed=seed)
            for name, setup in SETUPS.items():
                days[name].append(run_day(setup, day))
        averages = {name: {key: statistics.mean(d[key] for d in results) for key in results[0]}
                    for name, results in days.items()}
        print_table(f"{label}: a call every ~{gap:g} ticks "
                    f"(average over {args.days} days of {args.passengers} passengers)", averages)


if __name__ == "__main__":
    main()
