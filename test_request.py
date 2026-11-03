from requests import Requests

def test_starts_empty():
    r = Requests()
    assert r.is_empty()
    assert r.get_pending_requests() == []

def test_add_request_makes_it_pending():
    r = Requests()
    r.add_request({"id": "P1", "floor": 3, "destination": 7})
    assert len(r.get_pending_requests()) == 1
    assert not r.is_empty()

def test_not_empty_until_dropped_off():
    req = {"id": "P1", "floor": 3, "destination": 7}
    r = Requests([req])

    r.remove_pending_request(req)  # passenger picked up
    assert not r.is_empty()        # still riding

    r.mark_completed("P1")         # passenger dropped off
    assert r.is_empty()
