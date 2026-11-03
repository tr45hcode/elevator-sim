class Requests:
    """Every passenger in the simulation, and where each one is up to.

    A passenger's "time" is the tick when they press the call button. Until
    then they wait in `future`, invisible to the elevator, so an algorithm can
    only react to calls that have actually happened. Passengers without a
    "time" call at tick 0.
    """

    def __init__(self, initial_requests=None):
        initial = list(initial_requests) if initial_requests else []
        self.future = sorted(initial, key=lambda req: req.get("time", 0))
        self.pending_requests = []
        self.all_requests = {req["id"]: {"request": req, "completed": False} for req in initial}
        self.release(0)

    def release(self, now):
        """Move everyone whose call time has come into the pending list.
        Returns the newly released calls."""
        released = []
        while self.future and self.future[0].get("time", 0) <= now:
            released.append(self.future.pop(0))
        self.pending_requests.extend(released)
        return released

    def add_request(self, request):
        self.pending_requests.append(request)
        self.all_requests[request["id"]] = {"request": request, "completed": False}

    def get_pending_requests(self):
        return self.pending_requests

    def remove_pending_request(self, request, now=None):
        self.pending_requests.remove(request)
        self.all_requests[request["id"]]["picked_up_at"] = now

    def mark_completed(self, passenger_id, now=None):
        if passenger_id in self.all_requests:
            self.all_requests[passenger_id]["completed"] = True
            self.all_requests[passenger_id]["completed_at"] = now

    def get_all_requests(self):
        return self.all_requests

    def is_empty(self):
        return (not self.future and not self.pending_requests
                and all(req["completed"] for req in self.all_requests.values()))

    def stats(self):
        """Wait, ride and journey times in ticks, for everyone delivered.

        wait    = call -> doors open for them
        ride    = doors open for them -> doors open at their floor
        journey = wait + ride
        """
        done = [e for e in self.all_requests.values() if e.get("completed_at") is not None]
        if not done:
            return {"delivered": 0}
        waits = [e["picked_up_at"] - e["request"].get("time", 0) for e in done]
        rides = [e["completed_at"] - e["picked_up_at"] for e in done]
        return {
            "delivered": len(done),
            "avg_wait": sum(waits) / len(done),
            "max_wait": max(waits),
            "avg_ride": sum(rides) / len(done),
            "avg_journey": (sum(waits) + sum(rides)) / len(done),
        }
