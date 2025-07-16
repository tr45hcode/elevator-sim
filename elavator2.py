import time
import curses
from requests import Requests
from dataset import get_requests

class Elevator:
    def __init__(self, num_floors):
        self.current_floor = 1
        self.direction = 1  # 1 for up, -1 for down
        self.passengers = []
        self.num_floors = num_floors
        self.stdscr = None
    
    def move(self, requests):
        time.sleep(0.5)
        self.current_floor += self.direction
        self.draw(requests)
    
    def run(self, requests):
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        start_time = time.time()
        
        def pickup_passengers_at_current_floor():
            # Using list() to create a copy for safe iteration while modifying the original list
            for req in list(requests.get_pending_requests()):
                if req["floor"] == self.current_floor:
                    # Pick up passenger if they're going in the same direction OR if there are no other jobs
                    same_direction = (req["destination"] - self.current_floor) * self.direction > 0
                    no_other_jobs = (not self.passengers and 
                                   not any(r['floor'] != self.current_floor for r in requests.get_pending_requests()))
                    
                    if same_direction or no_other_jobs:
                        self.passengers.append(req)
                        requests.remove_pending_request(req)
        
        try:
            # Initial draw
            self.draw(requests)
            
            while not requests.is_empty() or self.passengers:
                # 1. Drop off passengers for the current floor
                dropped_off_passengers = []
                for p in self.passengers:
                    if p['destination'] == self.current_floor:
                        requests.mark_completed(p['id'])
                        dropped_off_passengers.append(p)
                self.passengers = [p for p in self.passengers if p not in dropped_off_passengers]
                
                # 2. Pick up passengers going in the current direction
                pickup_passengers_at_current_floor()
                
                # 3. Check if the simulation is over (after pickup/dropoff)
                if not self.passengers and requests.is_empty():
                    break
                
                # 4. Decide if the elevator needs to change direction
                # Going up
                if self.direction == 1:
                    has_upward_jobs = any(p['destination'] > self.current_floor for p in self.passengers) or any(r['floor'] > self.current_floor for r in requests.get_pending_requests())
                    has_upward_pickups = any(r['floor'] > self.current_floor and r['destination'] > r['floor'] for r in requests.get_pending_requests())
                    if not has_upward_jobs and not has_upward_pickups:
                        self.direction = -1
                        # After changing direction, check for pickups again at the same floor
                        pickup_passengers_at_current_floor()
                # Going down
                elif self.direction == -1:
                    has_downward_jobs = any(p['destination'] < self.current_floor for p in self.passengers) or any(r['floor'] < self.current_floor for r in requests.get_pending_requests())
                    has_downward_pickups = any(r['floor'] < self.current_floor and r['destination'] < r['floor'] for r in requests.get_pending_requests())
                    if not has_downward_jobs and not has_downward_pickups:
                        self.direction = 1
                        # After changing direction, check for pickups again at the same floor
                        pickup_passengers_at_current_floor()
                
                # 5. Check again if the simulation is over (after direction change and pickup)
                if not self.passengers and requests.is_empty():
                    break
                
                # 6. Prevent elevator from going out of bounds
                if (self.current_floor >= self.num_floors and self.direction == 1) or (self.current_floor <= 1 and self.direction == -1):
                    self.direction *= -1  # Reverse direction
                    pickup_passengers_at_current_floor()  # Check for pickups after direction change
                    
                # 7. Check one more time if simulation is over
                if not self.passengers and requests.is_empty():
                    break
                
                # 8. Move the elevator
                self.move(requests)
            
            end_time = time.time()
            if self.num_floors + 2 < self.stdscr.getmaxyx()[0]:
                self.stdscr.addstr(self.num_floors + 2, 0, f"Elevator finished in {end_time - start_time:.2f} seconds.")
                self.stdscr.refresh()
                time.sleep(3)
            
        except Exception as e:
            # Clean up curses even if an error occurs
            try:
                curses.endwin()
            except:
                pass  # Ignore errors during cleanup
            raise e
        finally:
            try:
                curses.endwin()
            except:
                pass  # Ignore errors during cleanup
    
    def draw(self, requests):
        try:
            self.stdscr.clear()
            max_y, max_x = self.stdscr.getmaxyx()
            
            # Draw elevator floors
            for i in range(self.num_floors, 0, -1):
                y_pos = self.num_floors - i
                if y_pos < max_y - 1:  # Leave space for bottom content
                    if i == self.current_floor:
                        self.stdscr.addstr(y_pos, 0, f"[{i:2d}] E")
                    else:
                        self.stdscr.addstr(y_pos, 0, f"[{i:2d}]  ")
            
            # Draw passenger info
            passenger_str = ", ".join([f"{p['id']}(->{p['destination']})" for p in self.passengers])
            passenger_line = f"Passengers: {passenger_str}"
            if len(passenger_line) > max_x - 1:
                passenger_line = passenger_line[:max_x - 4] + "..."
            
            if self.num_floors + 1 < max_y:
                self.stdscr.addstr(self.num_floors + 1, 0, passenger_line)
            
            # Show direction
            direction_str = "UP" if self.direction == 1 else "DOWN"
            if self.num_floors + 2 < max_y:
                self.stdscr.addstr(self.num_floors + 2, 0, f"Direction: {direction_str}")
            
            # Display requests status (limited to available space)
            y_offset = self.num_floors + 4
            if y_offset < max_y:
                pending_count = len(requests.get_pending_requests())
                self.stdscr.addstr(y_offset, 0, f"Pending Requests: {pending_count}")
                y_offset += 1
                
                if y_offset < max_y:
                    self.stdscr.addstr(y_offset, 0, "All Requests:")
                    y_offset += 1
                
                for req_id, req_data in requests.get_all_requests().items():
                    if y_offset >= max_y - 1:  # Stop if we're running out of space
                        break
                    status = "X" if req_data["completed"] else " "
                    req_line = f"  [{status}] {req_id}: {req_data['request']['floor']} -> {req_data['request']['destination']}"
                    if len(req_line) > max_x - 1:
                        req_line = req_line[:max_x - 4] + "..."
                    self.stdscr.addstr(y_offset, 0, req_line)
                    y_offset += 1
            
            self.stdscr.refresh()
        except curses.error:
            # If drawing fails, just continue - terminal might be too small
            pass

if __name__ == "__main__":
    requests_data = get_requests()
    requests = Requests(requests_data)
    elevator = Elevator(num_floors=20)
    elevator.run(requests)