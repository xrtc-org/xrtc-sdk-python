"""Async context manager for XRTC: login and set/get API."""
from contextlib import AsyncContextDecorator
from typing import AsyncIterable
import ssl
import asyncio

import aiohttp
import certifi
from pydantic import ValidationError

from xrtc import (
    LoginCredentials,
    ConnectionConfiguration,
    ReceivedError,
    GetItemRequest,
    SetItemRequest,
    ReceivedData,
    Item,
    LoginResponseData,
    XRTCException,
)


class AXRTC(AsyncContextDecorator):
    """Async context manager for XRTC: login and set/get API."""

    def __init__(self, env_file_credentials: str = None, env_file_connection: str = None):
        """
        Initialize connection and credentials.

        Connection credentials and URLs can be specified in .env files. If the file name does not contain the full path,
        then the work directory is assumed. If the file names are not specified, then "xrtc.env" is used by default.
        The values in the files are overridden by environmental variables.

        Parameters:
            env_file_credentials (str): .env file with connection credentials (account id, API key).
            env_file_connection (str): .env file with connection URLs (login, set and get item).
        """
        # Get credentials from .env file
        try:
            if env_file_credentials is not None:
                self._login_credentials = LoginCredentials(_env_file=env_file_credentials)
            else:
                self._login_credentials = LoginCredentials()

            # Set connection configuration
            if env_file_connection is not None:
                self._connection_configuration = ConnectionConfiguration(
                    _env_file=env_file_connection
                )
            else:
                self._connection_configuration = ConnectionConfiguration()
        except ValidationError as ex:
            raise XRTCException from ex

        # Import root certificates
        self._sslcontext = ssl.create_default_context(cafile=certifi.where())

        # Set default timeouts, connection parameters
        self._client_timeout = aiohttp.ClientTimeout(
            total=self._connection_configuration.aiohttp_timeout_total,
            connect=self._connection_configuration.aiohttp_timeout_connect,
            sock_connect=self._connection_configuration.aiohttp_timeout_sock_connect,
            sock_read=self._connection_configuration.aiohttp_timeout_sock_read,
        )
        self._tcp_connector = aiohttp.TCPConnector(
            limit=self._connection_configuration.aiohttp_limit_connections,
            ttl_dns_cache=self._connection_configuration.aiohttp_timeout_dns_cache,
        )

        # Semaphore for client-side concurrent requests limit
        self._requests_semaphore = asyncio.Semaphore(
            self._connection_configuration.aiohttp_limit_concurrent_requests
        )

        # Session
        self._session = None
        self.login_time = 0

    async def __aenter__(self):
        """Open requests connection and login."""
        self._session = aiohttp.ClientSession(
            timeout=self._client_timeout, connector=self._tcp_connector
        )

        async with self._session.post(
            url=self._connection_configuration.login_url,
            data=self._login_credentials.json(),
            ssl=self._sslcontext,
        ) as login_response:
            if login_response.status != 200:
                if login_response.status in (400, 401):
                    error_message = ReceivedError.parse_raw(
                        await login_response.text()
                    ).error.errormessage
                    await self._session.close()
                    raise XRTCException(
                        message=f"Login failed. {error_message}",
                        url=self._connection_configuration.login_url,
                    )

                await self._session.close()
                raise XRTCException(
                    message=f"Login failed. Code: {login_response.status}",
                    url=self._connection_configuration.login_url,
                )

            self.login_time = LoginResponseData.parse_raw(
                await login_response.text()
            ).servertimestamp

        return self

    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        """Close requests connection."""
        await self._session.close()

    @staticmethod
    def run(*args, **kwargs):
        """Wrap asyncio run for simpler code examples."""
        asyncio.run(*args, **kwargs)

    async def set_item(self, items: list[dict]):
        """Wrap for set item endpoint.

        Parameters:
            items (list[dict]): list of items to set, e.g. [{"portalid": "exampleportal", "payload": "examplepayload"}]
        """
        # Parse request parameters
        request_parameters = SetItemRequest(items=items).json(exclude_defaults=True)

        if len(request_parameters) > self._connection_configuration.serialized_json_size_max:
            raise XRTCException(
                message="Set item failed. Serialized json request size exceeds API limit",
                url=self._connection_configuration.set_url,
            )

        # Make request
        async with self._requests_semaphore:
            async with self._session.post(
                url=self._connection_configuration.set_url,
                data=request_parameters,
                ssl=self._sslcontext,
            ) as set_item_response:
                if set_item_response.status != 200:
                    if set_item_response.status in (400, 401):
                        error_message = ReceivedError.parse_raw(
                            await set_item_response.text()
                        ).error.errormessage
                        raise XRTCException(
                            message=f"Set item failed. {error_message}",
                            url=self._connection_configuration.set_url,
                        )

                    raise XRTCException(
                        message=f"Set item failed. Code: {set_item_response.status}",
                        url=self._connection_configuration.set_url,
                    )

    async def get_item(
        self,
        portals: list[dict] = None,
        mode: str = "probe",
        schedule: str = "LIFO",
        cutoff: int = -1,
    ) -> AsyncIterable[Item]:
        """Wrap get item endpoint in an async generator.

        Parameters:
            portals (list[dict]): list of portals to get items from, e.g. [{"portalid": "exampleportal"}]
            mode (str): "probe" (default) - check & return, "watch" - await new & return, "stream" - stream continuously
            schedule (str): "LIFO" (default) - new item first, can omit old items, "FIFO" - strive to deliver all items
            cutoff (int): time in ms to define the maximum relative age of the items, default -1 (no effect)

        Returns:
            Item (iterable), e.g. [{"portalid": "exampleportal", "payload": "examplepayload", "servertimestamp": 123456789}]
        """
        # Parse request parameters
        request_parameters = GetItemRequest(
            portals=portals, mode=mode, schedule=schedule, cutoff=cutoff
        ).json(exclude_defaults=True)

        if len(request_parameters) > self._connection_configuration.serialized_json_size_max:
            raise XRTCException(
                message="Get item failed. Serialized json request size exceeds API limit",
                url=self._connection_configuration.get_url,
            )

        # Make request
        async with self._requests_semaphore:
            async with self._session.post(
                url=self._connection_configuration.get_url,
                data=request_parameters,
                ssl=self._sslcontext,
            ) as get_item_response:
                if get_item_response.status != 200:
                    if get_item_response.status in (400, 401):
                        error_message = ReceivedError.parse_raw(
                            await get_item_response.text()
                        ).error.errormessage
                        raise XRTCException(
                            message=f"Get item failed. {error_message}",
                            url=self._connection_configuration.get_url,
                        )

                    raise XRTCException(
                        message=f"Get item failed. Code: {get_item_response.status}",
                        url=self._connection_configuration.get_url,
                    )

                async for line in get_item_response.content:

                    if len(line) > self._connection_configuration.serialized_json_size_max:
                        raise XRTCException(
                            message="Get item failed. Serialized json response size exceeds API limit",
                            url=self._connection_configuration.get_url,
                        )
                    elif len(line) == 0:
                        raise XRTCException(
                            message="Get item failed. Empty response.",
                            url=self._connection_configuration.get_url,
                        )

                    received_data = ReceivedData.parse_raw(line)

                    if received_data.items is not None:
                        for item in received_data.items:
                            yield item
                            await asyncio.sleep(0)

                return
