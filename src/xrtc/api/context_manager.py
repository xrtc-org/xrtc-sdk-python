"""Context manager (non-async) for XRTC: login and set/get API."""
from typing import Iterable
import logging

import requests
from pydantic import ValidationError


from xrtc import (
    LoginCredentials,
    ConnectionConfiguration,
    ReceivedError,
    GetItemRequest,
    SetItemRequest,
    LoginResponseData,
    ReceivedData,
    Item,
    XRTCException,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(asctime)s %(message)s")
logger = logging.getLogger()


class XRTC:
    """Context manager (non-async) for XRTC: login and set/get API."""

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

        # Session
        self._session = None
        self.login_time = 0

    def __enter__(self):
        """Open requests connection and login."""
        self._session = requests.Session()

        try:
            login_response = self._session.post(
                url=self._connection_configuration.login_url,
                data=self._login_credentials.json(),
                timeout=(
                    self._connection_configuration.requests_connect,
                    self._connection_configuration.requests_read,
                ),
            )

            if login_response.status_code != 200:
                if login_response.status_code in (400, 401):
                    error_message = ReceivedError.parse_raw(login_response.text).error.errormessage
                    self._session.close()
                    raise XRTCException(
                        message=error_message,
                        url=self._connection_configuration.login_url,
                    )

                self._session.close()
                raise XRTCException(
                    message=f"Code: {login_response.status_code}",
                    url=self._connection_configuration.login_url,
                )

            self.login_time = LoginResponseData.parse_raw(login_response.text).servertimestamp

        except Exception as ex:
            self._session.close()
            raise XRTCException(
                message=f"Login failed. Message: {str(ex)}",
                url=self._connection_configuration.login_url,
            ) from ex

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Close requests connection."""
        self._session.close()

    def set_item(self, items: list[dict]):
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
            set_item_response = self._session.post(
                url=self._connection_configuration.set_url,
                data=request_parameters,
                timeout=(
                    self._connection_configuration.requests_connect,
                    self._connection_configuration.requests_read,
                ),
            )

            if set_item_response.status_code != 200:
                if set_item_response.status_code in (400, 401):
                    error_message = ReceivedError.parse_raw(set_item_response.text).error.errormessage
                    raise XRTCException(
                        message=error_message,
                        url=self._connection_configuration.set_url,
                    )

                raise XRTCException(
                    message=f"Code: {set_item_response.status_code}",
                    url=self._connection_configuration.set_url,
                )

        except Exception as ex:
            self._session.close()
            raise XRTCException(
                message=f"Set item failed. Message: {str(ex)}",
                url=self._connection_configuration.set_url,
            ) from ex

    def get_item(
        self,
        portals: list[dict] = None,
        mode: str = "probe",
        schedule: str = "LIFO",
        cutoff: int = -1,
    ) -> Iterable[Item]:
        """Wrap get item endpoint.

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
            get_item_response = self._session.post(
                url=self._connection_configuration.get_url,
                data=request_parameters,
                timeout=(
                    self._connection_configuration.requests_connect,
                    self._connection_configuration.requests_read,
                ),
            )

            if get_item_response.status_code != 200:
                if get_item_response.status_code in (400, 401):
                    error_message = ReceivedError.parse_raw(get_item_response.text).error.errormessage
                    raise XRTCException(
                        message=f"Get item failed. {error_message}",
                        url=self._connection_configuration.get_url,
                    )

                raise XRTCException(
                    message=f"Get item failed. Code: {get_item_response.status_code}",
                    url=self._connection_configuration.get_url,
                )

            response_text = get_item_response.text

            if len(response_text) > self._connection_configuration.serialized_json_size_max:
                logger.warning("Get item failed. Serialized json response size exceeds API limit")
                return
            if len(response_text) == 0:
                logger.warning("Get item failed. Empty response")
                return

            received_data = ReceivedData.parse_raw(response_text)

            if received_data.items is not None:
                for item in received_data.items:
                    yield item

        except Exception as ex:
            self._session.close()
            raise XRTCException(
                message=f"Get item failed. Message: {str(ex)}",
                url=self._connection_configuration.get_url,
            ) from ex

        return
