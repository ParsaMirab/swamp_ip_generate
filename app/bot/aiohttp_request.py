from __future__ import annotations

from typing import Optional

import aiohttp
from telegram.request import BaseRequest, RequestData


class AiohttpRequest(BaseRequest):
    """Telegram request implementation using aiohttp instead of httpx."""

    def __init__(
        self,
        *,
        connection_pool_size: int = 8,
        read_timeout: float | None = 60.0,
        write_timeout: float | None = 30.0,
        connect_timeout: float | None = 30.0,
        pool_timeout: float | None = 30.0,
    ) -> None:
        super().__init__()

        self.connection_pool_size = connection_pool_size
        self.read_timeout = read_timeout
        self.write_timeout = write_timeout
        self.connect_timeout = connect_timeout
        self.pool_timeout = pool_timeout

        self._session: aiohttp.ClientSession | None = None

    async def initialize(self) -> None:
        if self._session is not None and not self._session.closed:
            return

        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=self.connect_timeout,
            sock_connect=self.connect_timeout,
            sock_read=self.read_timeout,
        )

        connector = aiohttp.TCPConnector(
            limit=self.connection_pool_size,
            family=2,
            ssl=True,
        )

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            trust_env=False,
        )

    async def shutdown(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

        self._session = None

    async def do_request(
        self,
        url: str,
        method: str,
        request_data: Optional[RequestData] = None,
        read_timeout: float | None = None,
        write_timeout: float | None = None,
        connect_timeout: float | None = None,
        pool_timeout: float | None = None,
    ) -> tuple[int, bytes]:
        if self._session is None or self._session.closed:
            await self.initialize()

        assert self._session is not None

        params = None
        data = None

        if request_data is not None:
            params = request_data.url_parameters

            if request_data.multipart_data:
                form = aiohttp.FormData()

                for key, value in request_data.multipart_data.items():
                    form.add_field(key, value)

                data = form

            elif request_data.json_parameters:
                data = request_data.json_parameters

        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=connect_timeout or self.connect_timeout,
            sock_connect=connect_timeout or self.connect_timeout,
            sock_read=read_timeout or self.read_timeout,
        )

        async with self._session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            timeout=timeout,
        ) as response:
            body = await response.read()

            return response.status, body