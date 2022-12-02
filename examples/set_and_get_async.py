"""Example code for async set and get with XRTC."""
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
