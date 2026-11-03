from elevator import Elevator, main


class NearestFirstElevator(Elevator):
    """Nearest-request-first elevator (SSTF: shortest seek time first).

    This is a greedy algorithm. elevator.py uses LOOK: sweep one way, only pick
    up passengers heading the same way, reverse when nothing is left ahead.

    This one has no sweep. At every floor it heads for the closest job, which is
    either a rider's destination or a waiting passenger's floor (only if there
    is room). It picks up anyone on its floor, whichever way they are going, up
    to capacity. Capacity, the clock, door time, and drawing all come from
    elevator.py.
    """

    def _service_floor(self, requests):
        people = self._drop_off(requests)
        people += self._pick_up(requests)
        people += self._drop_off(requests)  # zero-length trips (floor == destination)
        return people

    def _choose_direction(self, requests):
        target = self._nearest_target(requests)
        if target is None:
            return 0
        return 1 if target > self.current_floor else -1

    def _pick_up(self, requests):
        boarded = 0
        for req in list(requests.get_pending_requests()):
            if len(self.passengers) >= self.capacity:
                break
            if req["floor"] == self.current_floor:
                self.passengers.append(req)
                requests.remove_pending_request(req, self.clock)
                boarded += 1
        return boarded

    def _nearest_target(self, requests):
        targets = [p["destination"] for p in self.passengers]
        if len(self.passengers) < self.capacity:
            targets += [r["floor"] for r in requests.get_pending_requests()]
        if not targets:
            return None

        # Closest floor wins. On a tie, keep going the way we're already heading.
        def cost(floor):
            distance = abs(floor - self.current_floor)
            turns_around = (floor - self.current_floor) * self.direction < 0
            return (distance, turns_around)

        return min(targets, key=cost)


if __name__ == "__main__":
    main(NearestFirstElevator)
