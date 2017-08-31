from asyncio import Transport

class MockTransportToProtocol(Transport):
    def __init__(self, sinkProtocol, extra=None):
        super().__init__(extra)
        self.sink = sinkProtocol
        self.writeCount = 0
    def write(self, data):
        self.writeCount+=1
        self.sink.dataReceived(data)
        
class MockTransportToStorageStream(Transport):
    def __init__(self, sinkStream, extra=None):
        super().__init__(extra)
        self.sink = sinkStream
        self.writeCount = 0
    def write(self, data):
        self.writeCount+=1
        self.sink.write(data)