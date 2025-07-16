class Requests:
    def __init__(self, initial_requests=None):
        self.pending_requests = initial_requests if initial_requests else []
        self.all_requests = {req["id"]: {"request": req, "completed": False} for req in initial_requests} if initial_requests else {}

    def add_request(self, request):
        self.pending_requests.append(request)
        self.all_requests[request["id"]] = {"request": request, "completed": False}

    def get_pending_requests(self):
        return self.pending_requests

    def remove_pending_request(self, request):
        self.pending_requests.remove(request)

    def mark_completed(self, passenger_id):
        if passenger_id in self.all_requests:
            self.all_requests[passenger_id]["completed"] = True

    def get_all_requests(self):
        return self.all_requests

    def is_empty(self):
        return len(self.pending_requests) == 0 and all(req["completed"] for req in self.all_requests.values())