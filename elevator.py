import random
import sys
import time
import curses
from requests import Requests
from dataset import generate_requests


class Elevator:
    """LOOK elevator: sweep one way, only pick up passengers heading the same
    way, and reverse when there's nothing left ahead.

    Time runs on a simulated clock counted in ticks:
      - moving one floor takes 1 tick
      - a stop costs door_time ticks, plus board_time per person getting on or off
      - with nothing to do, the elevator waits where it is for 1 tick
    Passengers call at their "time" tick, and the elevator can't see a call
    before it happens.
    """

    TICK_SECONDS = 0.25  # animation speed in the terminal view

    def __init__(self, num_floors, capacity=10, door_time=2, board_time=1, name="E"):
        self.name = name
        self.current_floor = 1
        self.direction = 1  # 1 for up, -1 for down
        self.passengers = []
        self.num_floors = num_floors
        self.capacity = capacity
        self.door_time = door_time
        self.board_time = board_time
        self.clock = 0
        self.stdscr = None

    # --- simulation (no screen) -------------------------------------------

    def step(self, requests):
        """Advance by one action. Returns False once everyone is delivered."""
        requests.release(self.clock)
        if requests.is_empty() and not self.passengers:
            return False

        people = self._service_floor(requests)
        if people:
            # Doors opened. Look again before leaving, in case someone on
            # this floor called while the doors were open.
            self.clock += self.door_time + self.board_time * people
            return True

        direction = self._choose_direction(requests)
        if direction:
            self.direction = direction
            self.current_floor += direction
        self.clock += 1  # one floor moved, or one tick spent waiting
        return True

    def simulate(self, requests, max_ticks=1_000_000):
        """Run a whole day with no screen and no sleeping."""
        self._check_floors(requests)
        while self.step(requests):
            if self.clock > max_ticks:
                raise RuntimeError(f"Still running after {max_ticks} ticks. Stuck?")
        return requests

    # --- LOOK decisions (elevator2.py overrides these) --------------------

    def _service_floor(self, requests):
        """Let people off and on at this floor. Returns how many moved."""
        people = self._drop_off(requests)
        people += self._pick_up(requests)
        if self._has_work(requests) and not self._work_ahead(requests):
            self.direction *= -1
            people += self._pick_up(requests)  # people here going the new way
        return people

    def _choose_direction(self, requests):
        """1 = up, -1 = down, 0 = wait here."""
        return self.direction if self._has_work(requests) else 0

    def _pick_up(self, requests):
        boarded = 0
        for req in list(requests.get_pending_requests()):
            going_our_way = (req["destination"] - self.current_floor) * self.direction > 0
            if req["floor"] == self.current_floor and going_our_way and len(self.passengers) < self.capacity:
                self.passengers.append(req)
                requests.remove_pending_request(req, self.clock)
                boarded += 1
        return boarded

    def _work_ahead(self, requests):
        def ahead(floor):
            return (floor - self.current_floor) * self.direction > 0
        return (any(ahead(p["destination"]) for p in self.passengers)
                or any(ahead(r["floor"]) for r in requests.get_pending_requests()))

    # --- shared by every algorithm ----------------------------------------

    def _has_work(self, requests):
        return bool(self.passengers or requests.get_pending_requests())

    def _drop_off(self, requests):
        arrived = [p for p in self.passengers if p["destination"] == self.current_floor]
        for p in arrived:
            requests.mark_completed(p["id"], self.clock)
        self.passengers = [p for p in self.passengers if p not in arrived]
        return len(arrived)

    def _check_floors(self, requests):
        # A floor outside the building makes LOOK bounce at the top forever and
        # nearest-first drive straight past it. Fail loudly instead.
        for entry in requests.get_all_requests().values():
            req = entry["request"]
            for floor in (req["floor"], req["destination"]):
                if not 1 <= floor <= self.num_floors:
                    raise ValueError(f"{req['id']} uses floor {floor}, outside 1-{self.num_floors}")

    # --- terminal view ----------------------------------------------------

    def run(self, requests):
        """Watch the simulation in the terminal."""
        self._check_floors(requests)
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()

        try:
            self.draw(requests)
            while True:
                before = self.clock
                if not self.step(requests):
                    break
                self.draw(requests)
                time.sleep((self.clock - before) * self.TICK_SECONDS)

            if self.num_floors + 2 < self.stdscr.getmaxyx()[0]:
                self.stdscr.addstr(self.num_floors + 2, 0, f"Finished at tick {self.clock}.")
                self.stdscr.clrtoeol()
                self.stdscr.refresh()
                time.sleep(3)
        finally:
            try:
                curses.endwin()
            except curses.error:
                pass

    def draw(self, requests):
        try:
            self.stdscr.clear()
            max_y, max_x = self.stdscr.getmaxyx()

            waiting = {}
            for r in requests.get_pending_requests():
                waiting[r["floor"]] = waiting.get(r["floor"], 0) + 1

            # Draw elevator floors, with how many people are waiting on each
            for i in range(self.num_floors, 0, -1):
                y_pos = self.num_floors - i
                if y_pos < max_y - 1:  # Leave space for bottom content
                    car = self.name if i == self.current_floor else " "
                    queue = f"  waiting: {waiting[i]}" if i in waiting else ""
                    self.stdscr.addstr(y_pos, 0, f"[{i:2d}] {car}{queue}"[:max_x - 1])

            # Draw passenger info
            passenger_str = ", ".join([f"{p['id']}(->{p['destination']})" for p in self.passengers])
            passenger_line = f"Passengers: {passenger_str}"
            if len(passenger_line) > max_x - 1:
                passenger_line = passenger_line[:max_x - 4] + "..."

            if self.num_floors + 1 < max_y:
                self.stdscr.addstr(self.num_floors + 1, 0, passenger_line)

            # Show direction and the clock
            direction_str = "UP" if self.direction == 1 else "DOWN"
            if self.num_floors + 2 < max_y:
                self.stdscr.addstr(self.num_floors + 2, 0, f"Direction: {direction_str}   Tick: {self.clock}")

            # Display requests status (limited to available space)
            y_offset = self.num_floors + 4
            if y_offset < max_y:
                pending_count = len(requests.get_pending_requests())
                self.stdscr.addstr(y_offset, 0, f"Pending Requests: {pending_count}")
                y_offset += 1

                if y_offset < max_y:
                    self.stdscr.addstr(y_offset, 0, "All Requests (X = done, . = hasn't called yet):")
                    y_offset += 1

                for req_id, req_data in requests.get_all_requests().items():
                    if y_offset >= max_y - 1:  # Stop if we're running out of space
                        break
                    req = req_data["request"]
                    if req_data["completed"]:
                        status = "X"
                    elif req.get("time", 0) > self.clock:
                        status = "."
                    else:
                        status = " "
                    req_line = f"  [{status}] {req_id} t={req.get('time', 0)}: {req['floor']} -> {req['destination']}"
                    if len(req_line) > max_x - 1:
                        req_line = req_line[:max_x - 4] + "..."
                    self.stdscr.addstr(y_offset, 0, req_line)
                    y_offset += 1

            self.stdscr.refresh()
        except curses.error:
            # If drawing fails, just continue - terminal might be too small
            pass


def main(elevator_class):
    """Watch one random day. Pass a seed to replay a day: python elevator.py 42"""
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else random.randrange(10_000)
    requests = Requests(generate_requests(seed=seed))
    elevator = elevator_class(num_floors=20)
    elevator.run(requests)

    s = requests.stats()
    print(f"{elevator_class.__name__} on day {seed}: finished at tick {elevator.clock}")
    print(f"  wait     avg {s['avg_wait']:.1f}, worst {s['max_wait']} ticks")
    print(f"  journey  avg {s['avg_journey']:.1f} ticks (call to arrival)")
    print(f"Same day again: python elevator.py {seed}   or   python elevator2.py {seed}")


if __name__ == "__main__":
    main(Elevator)
