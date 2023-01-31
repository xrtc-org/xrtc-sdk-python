"""Example code for async set and get with XRTC."""
from xrtc import AXRTC


async def main():
    """Async function that enables the use of async context manager."""
    # Get your free account and API key from https://xrtc.org
    async with AXRTC(account_id="AC0987654321012345", api_key="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") as xrtc:

        # Upload an item
        await xrtc.set_item(items=[{"portalid": "exampleportal", "payload": "examplepayload"}])

        # Download items and iterate through them
        async for item in xrtc.get_item(portals=[{"portalid": "exampleportal"}]):
            print(item.dict())


AXRTC.run(main())
