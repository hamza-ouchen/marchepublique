from __future__ import annotations

import aiohttp
from aiohttp import web

ROUTES = {
    "base-donnees": 8201,
    "portail-marches": 8202,
    "base-connaissances": 8203,
    "canaux": 8204,
}

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


async def proxy(request: web.Request) -> web.StreamResponse:
    name = request.path.strip("/").split("/", 1)[0]
    if name not in ROUTES:
        return web.Response(status=404, text="Unknown MCP route: " + name)

    target = "http://127.0.0.1:" + str(ROUTES[name]) + "/mcp"
    if request.query_string:
        target += "?" + request.query_string

    body = await request.read()
    headers = {
        key: value for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP and key.lower() != "host"
    }

    timeout = aiohttp.ClientTimeout(total=None, sock_read=None)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.request(
            request.method, target, data=body, headers=headers
        ) as upstream:
            response = web.StreamResponse(status=upstream.status)
            for key, value in upstream.headers.items():
                if key.lower() not in HOP_BY_HOP and key.lower() != "content-length":
                    response.headers[key] = value
            await response.prepare(request)
            async for chunk in upstream.content.iter_chunked(8192):
                await response.write(chunk)
            await response.write_eof()
            return response


app = web.Application()
app.router.add_route("*", "/{tail:.*}", proxy)

if __name__ == "__main__":
    web.run_app(app, host="127.0.0.1", port=8299)
