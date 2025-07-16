
import time

ENERGY_FILE = '/sys/class/powercap/intel-rapl:0/energy_uj'

def read_energy():
    """Reads the current energy value from the system file."""
    try:
        with open(ENERGY_FILE, 'r') as f:
            return int(f.read())
    except FileNotFoundError:
        print(f"Error: Could not find {ENERGY_FILE}")
        print("Please ensure you have an Intel CPU and the 'intel_rapl' kernel module is loaded.")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def main():
    """Calculates and prints the average CPU power consumption over a short interval."""
    energy1 = read_energy()
    if energy1 is None:
        return

    time.sleep(1)  # Wait for 1 second

    energy2 = read_energy()
    if energy2 is None:
        return

    # Calculate the power in watts
    # The energy is in microjoules (uJ), and we measured over 1 second.
    # Power (W) = Energy (J) / Time (s)
    # Power (W) = (Energy (uJ) / 1,000,000) / 1 (s)
    power_watts = (energy2 - energy1) / 1_000_000

    print(f"Current CPU Power Usage: {power_watts:.2f} Watts")

if __name__ == "__main__":
    main()
