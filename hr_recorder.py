import asyncio
import os
from bleak import BleakClient
from datetime import datetime

HR_CHAR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


async def record_heartrate(polar_address: str, stop_event: asyncio.Event, log_callback=print):
    filename = f"heartrate_overlay/logs/{datetime.now().strftime('%Y-%m-%d %H-%M-%S')}.csv"
    os.makedirs("heartrate_overlay/logs", exist_ok=True)

    try:
        async with BleakClient(polar_address) as client:
            log_callback("Connected to Polar H10")

            with open(filename, "a") as f:
                f.write("timestamp,heart_rate\n")
                f.flush()

                def handle_hr(sender, data):
                    hr_value = data[1]
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    line = f"{timestamp},{hr_value}"
                    log_callback(f"BPM: {hr_value}")

                    f.write(line + "\n")
                    f.flush()

                await client.start_notify(HR_CHAR_UUID, handle_hr)

                # Run until stop is requested
                while not stop_event.is_set():
                    await asyncio.sleep(0.5)

                await client.stop_notify(HR_CHAR_UUID)
                log_callback(f"Saved to {filename}")

    except Exception as e:
        log_callback(f"❌ BLE error: {e}")