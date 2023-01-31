from setuptools import setup

# Read the contents of your README file
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="xrtc",
    description="SDK for XRTC API - the next generation TCP streaming protocol",
    long_description_content_type="text/markdown",
    long_description=long_description,
    package_dir={"": "src"},
    version="0.1.5",
    author="Delta Cygni Labs Ltd",
    url="https://xrtc.org",
    download_url="https://github.com/xrtc-org/xrtc-sdk-python",
    license="Apache-2.0",
    python_requires=">=3.10",
    install_requires=[
        # Read .env files to environment
        "python-dotenv >= 0.21.1",
        # Load and parse settings from environment
        "pydantic >= 1.10.4",
        # HTTP requests
        "requests >= 2.28.2",
        # Async HTTP requests
        "aiohttp >= 3.8.3",
        # SSL root certificates (for aiohttp)
        "certifi >= 2022.12.7",
    ],
)
