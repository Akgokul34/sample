import asyncio
import logging

logger = logging.getLogger(__name__)

class TCPServer:
    def __init__(self, host: str, port: int, protocol_handler):
        self.host = host
        self.port = port
        self.protocol_handler = protocol_handler
        self.server = None

    async def start(self):
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        addrs = ', '.join(str(sock.getsockname()) for sock in self.server.sockets)
        logger.info(f"Serving on {addrs}")
        async with self.server:
            await self.server.serve_forever()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        logger.info(f"Accepted connection from {addr}")
        
        try:
            await self.protocol_handler(reader, writer)
        except Exception as e:
            logger.error(f"Error handling connection from {addr}: {e}")
        finally:
            logger.info(f"Closing connection from {addr}")
            writer.close()
            await writer.wait_closed()
