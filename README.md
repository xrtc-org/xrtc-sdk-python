# XRTC API
[![xrtc](https://snyk.io/advisor/python/xrtc/badge.svg)](https://snyk.io/advisor/python/xrtc)

XRTC is the next generation ultra-low latency TCP streaming protocol. It is up to 30x faster than
LL HLS and RTMP, and it is on a par with WebRTC. Unlike UDP-based WebRTC, XRTC uses a pure
TCP/HTTP for ease of cross-firewall deployment and security.

This is an SDK for XRTC API in Python. The SDK implements the following convenience features:

- non-async context manager with requests package, error management
- async context manager with asyncio/aiohttp for handling parallel HTTP requests, error management
- login and connection configurations loading from .env file or from the environment
- configurations, serialized and deserialized request bodies and response data models and parser with Pydantic

To start using XRTC, please obtain your free API token at [XRTC web site](https://xrtc.org)

This project is sponsored by [Delta Cygni Labs Ltd](https://deltacygnilabs.com) with the headquarters in Tampere, Finland.

## Installation

Installation from Pypi:
```
pip install xrtc
```

Update from Pypi if you have already installed the package:
```
pip install xrtc --upgrade
```

Installation from source:
```
pip install .
```

Installation from source if you want the package to be editable:
```
pip install . -e
```

## Login credentials and connection URLs

Login credentials are taken from the environment or from a `.env` file
(e.g. `xrtc.env`) placed to the work directory. 

Example of `.env` file content:
```
# XRTC credentials
ACCOUNT_ID=AC0987654321012345
API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Usage examples

See more on [GitHub, examples directory](https://github.com/xrtc-org/xrtc-sdk-python).

Simple set and get:
```
import os

from xrtc import XRTC

# Connection credentials from environment variables
# Get your free account and API key from https://xrtc.org
os.environ["ACCOUNT_ID"] = "AC0987654321012345"
os.environ["API_KEY"] = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

with XRTC() as xrtc:
    # Upload item
    xrtc.set_item(items=[{"portalid": "exampleportal", "payload": "examplepayload"}])

    # Download items and iterate through them
    for item in xrtc.get_item(portals=[{"portalid": "exampleportal"}]):
        print(item.dict())
```

The same example with the async context manager:
```
import os

from xrtc import AXRTC


async def main():

    # Connection credentials from environment variables
    # Get your free account and API key from https://xrtc.org
    os.environ["ACCOUNT_ID"] = "AC0987654321012345"
    os.environ["API_KEY"] = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

    # Use async context manager
    async with AXRTC() as xrtc:
        # Upload an item
        await xrtc.set_item(items=[{"portalid": "exampleportal", "payload": "examplepayload"}])

        # Download items and iterate through them
        async for item in xrtc.get_item(portals=[{"portalid": "exampleportal"}]):
            print(item.dict())


AXRTC.run(main())
```

A more sophisticated example for continuous setting and getting with XRTC and async context manager.
Measures end-to-end latency in ms. Note different get item modes (watch, probe) as well as cutoff
parameter to discard the items from previous runs. Two set of credentials are used for setting
and getting: the `accountid` is the same, but the `apikey` are different (request them twice from
[XRTC web site](https://xrtc.org)), and the credentials are loaded from .env files.
```
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
```
