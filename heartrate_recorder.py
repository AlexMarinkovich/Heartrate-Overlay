import asyncio
import os
from bleak import BleakClient
from datetime import datetime

POLAR_ADDRESS = "24:AC:AC:0E:EB:0C"  # identified using device_finder.py
HR_CHAR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

# Ensure logs folder exists
os.makedirs("logs", exist_ok=True)

# Create a new text file with a timestamp in the filename
filename = f"logs/{datetime.now().strftime('%Y-%m-%d %H-%M-%S')}.csv"

async def main():
    async with BleakClient(POLAR_ADDRESS) as client:
        print("Connected to Polar H10")

        # Open file once, keep it open during the session
        with open(filename, "a") as f:
            # Write CSV header
            f.write("timestamp,heart_rate\n")
            f.flush()

            def handle_hr(sender, data):
                hr_value = data[1]  # heartrate value
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                line = f"{timestamp},{hr_value}\n"
                print(line.strip())
                
                f.write(line)
                f.flush()  # immediately write to disk

            await client.start_notify(HR_CHAR_UUID, handle_hr)
            print("Listening for heart rate... Press Ctrl+C to stop.")
            
            try:
                while True:
                    await asyncio.sleep(1)
            except:
                print("\nStopping...")
                await client.stop_notify(HR_CHAR_UUID)
                print(f"Heart rate data saved to {filename}")

asyncio.run(main())