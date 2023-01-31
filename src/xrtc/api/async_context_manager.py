"""Async context manager for XRTC: login and set/get API."""
from contextlib import AsyncContextDecorator
from typing import AsyncIterable
import ssl
import asyncio
import logging

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

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(asctime)s %(message)s")
logger = logging.getLogger()


class AXRTC(AsyncContextDecorator):
    """Async context manager for XRTC: login and set/get API."""

    def __init__(
        self,
        account_id: str = None,
        api_key: str = None,
        env_file_credentials: str = None,
        env_file_connection: str = None,
    ):
        """
        Initialize connection and credentials.

        Connection credentials and URLs can be specified in .env files. If the file name does not contain the full path,
        then the work directory is assumed. If the file names are not specified, then "xrtc.env" is used by default
        for either of the files. Account id and API key can be provided directly, overriding credentials .env file.
        Environmental variables override any other values.

        Parameters:
            env_file_credentials (str): .env file with connection credentials (account id, API key).
            env_file_connection (str): .env file with connection URLs (login, set and get item).
            account_id (str): Account id for connection, overrides .env
            api_key (str): API key for connection, overrides .env
        """
        try:
            if account_id is not None and api_key is not None:
                # Use explicit credentials if provided
                self._login_credentials = LoginCredentials(_env_file=None, accountid=account_id, apikey=api_key)
                if env_file_credentials is not None:
                    logger.warning("When using explicit credentials, env_file_credentials is ignored")
            else:
                # Otherwise get credentials from .env file
                if env_file_credentials is not None:
                    self._login_credentials = LoginCredentials(_env_file=env_file_credentials)
                else:
                    self._login_credentials = LoginCredentials()

            # Set connection configuration
            if env_file_connection is not None:
                self._connection_configuration = ConnectionConfiguration(_env_file=env_file_connection)
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
            keepalive_timeout=self._connection_configuration.aiohttp_keepalive_timeout,
            limit=self._connection_configuration.aiohttp_limit_connections,
            ttl_dns_cache=self._connection_configuration.aiohttp_timeout_dns_cache,
        )

        # Semaphore for client-side concurrent requests limit
        self._requests_semaphore = asyncio.Semaphore(self._connection_configuration.aiohttp_limit_concurrent_requests)

        # Session
        self._session = None
        self.login_time = 0

    async def __aenter__(self):
        """Open requests connection and login."""
        self._session = aiohttp.ClientSession(timeout=self._client_timeout, connector=self._tcp_connector)

        try:
            async with self._session.post(
                url=self._connection_configuration.login_url,
                data=self._login_credentials.json(),
                ssl=self._sslcontext,
            ) as login_response:
                if login_response.status != 200:
                    if login_response.status in (400, 401):
                        error_message = ReceivedError.parse_raw(await login_response.text()).error.errormessage
                        await self._session.close()
                        raise XRTCException(
                            message=error_message,
                            url=self._connection_configuration.login_url,
                        )

                    await self._session.close()
                    raise XRTCException(
                        message=f"Code: {login_response.status}",
                        url=self._connection_configuration.login_url,
                    )

                self.login_time = LoginResponseData.parse_raw(await login_response.text()).servertimestamp
        except Exception as ex:
            await self._session.close()
            raise XRTCException(
                message=f"Login failed. Message: {str(ex)}",
                url=self._connection_configuration.login_url,
            ) from ex

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
        try:
            request_parameters = SetItemRequest(items=items).json(exclude_defaults=True)
        except Exception as ex:
            logger.warning("Set item failed. Request conversion to json: %s", str(ex))
            return

        if len(request_parameters) > self._connection_configuration.serialized_json_size_max:
            logger.warning("Set item failed. Serialized json request size exceeds API limit")
            return

        # Make request
        try:
            async with self._requests_semaphore:
                async with self._session.post(
                    url=self._connection_configuration.set_url,
                    data=request_parameters,
                    ssl=self._sslcontext,
                ) as set_item_response:
                    if set_item_response.status != 200:
                        if set_item_response.status in (400, 401):
                            error_message = ReceivedError.parse_raw(await set_item_response.text()).error.errormessage
                            raise XRTCException(
                                message=error_message,
                                url=self._connection_configuration.set_url,
                            )

                        raise XRTCException(
                            message=f"Code: {set_item_response.status}",
                            url=self._connection_configuration.set_url,
                        )

        except Exception as ex:
            await self._session.close()
            raise XRTCException(
                message=f"Set item failed. Message: {str(ex)}",
                url=self._connection_configuration.set_url,
            ) from ex

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
            Item (iterable), e.g. [{"portalid":"exampleportal", "payload":"examplepayload", "servertimestamp":12345}]
        """
        # Parse request parameters
        try:
            request_parameters = GetItemRequest(portals=portals, mode=mode, schedule=schedule, cutoff=cutoff).json(
                exclude_defaults=True
            )
        except Exception as ex:
            logger.warning("Get item failed. Request conversion to json: %s", str(ex))
            return

        if len(request_parameters) > self._connection_configuration.serialized_json_size_max:
            logger.warning("Get item failed. Serialized json request size exceeds API limit")
            return

        # Make request
        try:
            async with self._requests_semaphore:
                async with self._session.post(
                    url=self._connection_configuration.get_url,
                    data=request_parameters,
                    ssl=self._sslcontext,
                ) as get_item_response:
                    if get_item_response.status != 200:
                        if get_item_response.status in (400, 401):
                            error_message = ReceivedError.parse_raw(await get_item_response.text()).error.errormessage
                            raise XRTCException(
                                message=error_message,
                                url=self._connection_configuration.get_url,
                            )

                        raise XRTCException(
                            message=f"Code: {get_item_response.status}",
                            url=self._connection_configuration.get_url,
                        )

                    async for line in get_item_response.content:

                        if len(line) > self._connection_configuration.serialized_json_size_max:
                            logger.warning("Get item failed. Serialized json response size exceeds API limit")
                            continue
                        if len(line) == 0:
                            logger.warning("Get item failed. Empty response")
                            continue

                        received_data = ReceivedData.parse_raw(line)

                        if received_data.items is not None:
                            for item in received_data.items:
                                yield item
                                await asyncio.sleep(0)

        except Exception as ex:
            await self._session.close()
            raise XRTCException(
                message=f"Get item failed. Message: {str(ex)}",
                url=self._connection_configuration.get_url,
            ) from ex

        return
