import asyncio

class TestLoopEx(asyncio.AbstractEventLoop):

    def __init__(self):
        self._running = True
        self._transportFactory = None
        self._schedule = []
        self._clock_time = 0.0
        
    def _test_set_clock(self, absolute_time):
        self._clock_time = absolute_time
        
    def _test_advance_time(self, seconds):
        self._clock_time += seconds
        self._test_run_once()
        
    def _test_run_once(self):
        while self._schedule and self._schedule[0][0] <= self._clock_time:
            event_time, event_task = self._schedule.pop(0)
            event_task()
            
    def _test_set_transport_factory(self, f):
        self._transportFactory = f
    
    def stop(self):
        self._running=False
        
    def is_running(self):
        return self._running
        
    def is_closed(self):
        return not self._running
        
    def call_soon(self, f, args=None):
        self.call_later(0.0, f, args)
        
    def call_later(self, delay, f, args=None):
        if args == None:
            args = ()
        self._schedule.append(((self._clock_time + delay), lambda: f(*args)))
        self._schedule.sort(key=lambda schedule_element: schedule_element[0])
        
    def time(self):
        return self._clock_time
        
    async def create_connection(self, factory, addr, port):
        if not self._transportFactory:
            raise Exception("Not Ready. Requires a transport factory")
        protocol = factory()
        transport = self._transportFactory(protocol, addr, port)
        protocol.connection_made(transport)
        return (transport, protocol)

    