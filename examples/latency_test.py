"""
Latency test.

Example code for continuous setting and getting with XRTC and async context manager.
Measures end-to-end latency in ms.
"""
import asyncio
from time import time
import json

from xrtc import AXRTC


class LatencyTest:
    def __init__(self):
        self.test_running = True

    async def setting(self):
        """Set time co-routine."""
        async with AXRTC(env_file_credentials="xrtc_set.env") as xrtc:
            # Keep uploading items
            for counter in range(0, 100):
                payload = json.dumps({"time": str(time())})
                await xrtc.set_item(items=[{"portalid": "latency", "payload": payload}])
                await asyncio.sleep(0.1)

        # Uploading finished, sleep to let all items arrive
        await asyncio.sleep(1)
        self.test_running = False

    async def getting(self):
        """Get time co-routine."""
        mean = 0
        iteration = 0
        async with AXRTC(env_file_credentials="xrtc_get.env") as xrtc:
            # Keep polling for items
            while self.test_running:
                # mode="watch" means wait until there is fresh item. Compare to mode="probe"
                # cutoff=500 discards the items older than 500ms, e.g. from the previous run
                # iterate through the items (a single request may bring several items)
                async for item in xrtc.get_item(
                    portals=[{"portalid": "latency"}], mode="stream", cutoff=500
                ):
                    received_time = json.loads(item.payload)["time"]
                    latency = round((time() - float(received_time)) * 1000, 1)

                    # Recurring sample mean
                    mean = round(1 / (iteration + 1) * (mean * iteration + latency), 1)
                    iteration += 1

                    print(f"{iteration = }: {latency = } ms, {mean = } ms")

    async def execute(self):
        """Launch parallel setting and getting tasks."""
        await asyncio.gather(self.setting(), self.getting())


latency_test = LatencyTest()
asyncio.run(latency_test.execute())
