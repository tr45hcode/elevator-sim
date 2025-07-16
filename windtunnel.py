import subprocess
import re
import time
import os
import sys

# Path to the fan RPM file
FAN_RPM_FILE = '/sys/class/hwmon/hwmon3/fan1_input'

def get_fan_rpm():
    """Reads the current fan RPM from the system file."""
    try:
        with open(FAN_RPM_FILE, 'r') as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return "N/A"
    except Exception:
        return "Error"

def restart_thinkfan_service():
    """Attempts to restart the thinkfan service by reloading the kernel module."""
    if os.geteuid() != 0:
        return "Error: This script must be run as root (using sudo) to restart the thinkfan service."

    print("\nAttempting to reload thinkpad_acpi module and restart thinkfan service...")
    try:
        # Unload the module
        print("Unloading thinkpad_acpi module...")
        subprocess.run(['modprobe', '-r', 'thinkpad_acpi'], check=True, capture_output=True, text=True)

        # Load the module again
        print("Loading thinkpad_acpi module...")
        subprocess.run(['modprobe', 'thinkpad_acpi'], check=True, capture_output=True, text=True)

        # Start the thinkfan service
        print("Starting thinkfan service...")
        subprocess.run(['systemctl', 'start', 'thinkfan.service'], check=True, capture_output=True, text=True)

        print("Successfully restarted thinkfan service.")
        return "Service restarted. Checking status on next poll."
    except subprocess.CalledProcessError as e:
        return f"Failed to restart thinkfan service.\nCommand: {' '.join(e.cmd)}\nStderr: {e.stderr}"
    except Exception as e:
        return f"An unexpected error occurred during service restart: {e}"


def get_fan_level():
    """Gets the fan level from the thinkfan service."""
    try:
        # Run the systemctl command to get the service status
        result = subprocess.run(['systemctl', 'status', 'thinkfan.service'], capture_output=True, text=True)
        output = result.stdout

        # Check if service is active
        if 'Active: active (running)' in output:
            # Search for the line containing "Fans: level"
            match = re.search(r'Fans: level (\d+)', output)
            if match:
                return match.group(1)
            else:
                return "N/A"
        else:
            # If service is not running, try to restart it
            print("\nThinkfan service is not running.")
            return restart_thinkfan_service()

    except FileNotFoundError:
        return "Error: 'systemctl' command not found."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

if __name__ == "__main__":
    print("Starting fan monitor. Press Ctrl+C to stop.")
    print("NOTE: If the thinkfan service fails, this script will attempt to restart it.")
    print("This requires the script to be run with sudo privileges.")
    try:
        while True:
            level = get_fan_level()
            rpm = get_fan_rpm()

            # Use carriage return to keep it on one line and flush the output
            sys.stdout.write(f"Fan Level: {level} | Fan RPM: {rpm}   \r")
            sys.stdout.flush()

            time.sleep(1) # Poll every 1 second
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
