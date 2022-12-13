"""Example code for simple set and get with XRTC."""
from xrtc import XRTC

# Get your free account and API key from https://xrtc.org
with XRTC(account_id="AC0987654321012345", api_key="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") as xrtc:
    # Upload an item
    xrtc.set_item(items=[{"portalid": "exampleportal", "payload": "examplepayload"}])

    # Download items and iterate through them
    for item in xrtc.get_item(portals=[{"portalid": "exampleportal"}]):
        print(item.dict())
