from asyncio import Transport

class MockTransportToProtocol(Transport):
    def __init__(self, sinkProtocol, extra=None):
        super().__init__(extra)
        self.sink = sinkProtocol
        self.writeCount = 0
        self.closed = False
    def write(self, data):
        self.writeCount+=1
        self.sink.data_received(data)
    def close(self, *args):
        self.closed = True
        self.sink and self.sink.connection_lost(None)
        
class MockTransportToStorageStream(Transport):
    def __init__(self, sinkStream, extra=None):
        super().__init__(extra)
        self.sink = sinkStream
        self.writeCount = 0
        self.closed = False
    def write(self, data):
        self.writeCount+=1
        self.sink.write(data)
    def close(self, *args):
        self.closed = True