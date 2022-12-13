"""Example code for async set and get with XRTC."""
from xrtc import AXRTC

# To use async context manager, define an async function and run it
async def main():

    # Get your free account and API key from https://xrtc.org
    async with AXRTC(account_id="AC0987654321012345", api_key="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") as xrtc:
        # Upload an item
        await xrtc.set_item(items=[{"portalid": "exampleportal", "payload": "examplepayload"}])

        # Download items and iterate through them
        async for item in xrtc.get_item(portals=[{"portalid": "exampleportal"}]):
            print(item.dict())


AXRTC.run(main())
