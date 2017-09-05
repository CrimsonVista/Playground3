from asyncio.test_utils import TestLoop
import asyncio

class TestLoopEx(TestLoop):

    def __init__(self):
        self._running = True
        super().__init__(self._gen)
        self._transportFactory = None
        
    def _gen(self):
        while self._running:
            when = yield
            if self._running: yield 0
            
    def close(self):
        self._running=False
        self._run_once()
        super().close()
        
    def advanceClock(self, seconds):
        self.advance_time(seconds)
        self._run_once()
        
    def setTransportFactory(self, f):
        self._transportFactory = f
        
    async def create_connection(self, factory, addr, port):
        if not self._transportFactory:
            raise Exception("Not Ready. Requires a transport factory")
        protocol = factory()
        transport = self._transportFactory(protocol, addr, port)
        protocol.connection_made(transport)
        return (transport, protocol)