import time
import sys

ENERGY_FILE = '/sys/class/powercap/intel-rapl:0/energy_uj'

def read_energy():
    """Reads the current energy value from the system file."""
    try:
        with open(ENERGY_FILE, 'r') as f:
            return int(f.read())
    except FileNotFoundError:
        print(f"\nError: Could not find {ENERGY_FILE}")
        print("Please ensure you have an Intel CPU and the 'intel_rapl' kernel module is loaded.")
        return None
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        return None

def main():
    """Continuously calculates and displays CPU power until interrupted."""
    print("Starting live CPU power monitoring... Press Ctrl+C to exit.")
    
    try:
        last_energy = read_energy()
        if last_energy is None:
            return
        last_time = time.monotonic()
        max_power_watts = 0.0

        while True:
            time.sleep(1)  # Set the update interval to 1 second
            
            current_energy = read_energy()
            current_time = time.monotonic()

            if current_energy is None:
                break  # Exit if the energy file becomes unreadable

            time_delta = current_time - last_time
            energy_delta = current_energy - last_energy

            if time_delta > 0:
                # Power (W) = (Energy (uJ) / 1,000,000) / Time (s)
                power_watts = (energy_delta / 1_000_000) / time_delta
                
                # Update max power
                if power_watts > max_power_watts:
                    max_power_watts = power_watts

                # Use carriage return to overwrite the line
                sys.stdout.write(f"Current CPU Power: {power_watts:6.2f} W | Max: {max_power_watts:6.2f} W\r")
                sys.stdout.flush()

            # Update values for the next iteration
            last_energy = current_energy
            last_time = current_time

    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        sys.stdout.write("\n") # Move to a new line after stopping
        print("Monitoring stopped.")

if __name__ == "__main__":
    main()

