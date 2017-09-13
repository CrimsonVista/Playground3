from asyncio import Transport

class MockTransportBase(Transport):
    def __init__(self, myProtocol=None, extra=None):
        super().__init__(extra)
        self.writeCount = 0
        self.loop = None
        self.delay = None
        self.sink = None
        self.protocol = myProtocol
        self.closed = False
        
    def setMyProtocol(self, protocol):
        self.protocol = protocol
        
    def setWriteDelay(self, loop, delay=1):
        if loop == None and delay > 0:
            self.loop = None
            self.delay = None
        else:
            self.loop = loop
            self.delay = delay
            
    def _close(self, *args):
        if self.protocol: 
            self.protocol.connection_lost(None)
            self.protocol = None
        
    def _write(self, data):
        pass
        
    def write(self, data):
        if self.closed: return
        self.writeCount += 1
        if self.delay:
            self.loop.call_later(self.delay, self._write, data)
        else:
            self._write(data)
        
    def close(self, *args):
        if self.closed: return
        self.closed = True
        if self.delay:
            self.loop.call_later(self.delay, self._close, *args)
        else:
            self._close(*args)

class MockTransportToProtocol(MockTransportBase):
    @classmethod
    def CreateTransportPair(cls, protocol1=None, protocol2=None):
        t1 = cls(protocol1)
        t2 = cls(protocol2)
        t1.setRemoteTransport(t2)
        t2.setRemoteTransport(t1)
        return (t1, t2)
        
    def setRemoteTransport(self, remoteTransport):
        self.sink=remoteTransport

    def _write(self, data):
        if not self.sink:
            raise Exception("Write failed! No remote destination configured yet")
        elif self.sink.protocol:
            self.sink.protocol.data_received(data)
        else:
            raise Exception("Write failed! Remote protocol already appears closed")
            
    def _close(self, *args):
        self.sink and self.sink.close()
        super()._close()
        
class MockTransportToStorageStream(MockTransportBase):
    def __init__(self, sinkStream, myProtocol=None, extra=None):
        super().__init__(myProtocol, extra)
        self.sink = sinkStream

    def _write(self, data):
        self.sink.write(data)
