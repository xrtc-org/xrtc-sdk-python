"""Example code for simple set and get with XRTC."""
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
