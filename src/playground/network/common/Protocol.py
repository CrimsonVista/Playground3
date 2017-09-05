'''
Created on August 19, 2017
Copied and adapted from Playground 2.0
Created on Oct 23, 2013

@author: sethjn
'''
from playground.common import CustomConstant as Constant
from asyncio import Protocol, Transport

class StackingProtocolFactory:
    """
    MyStackType() = StackingProtocolFactory.CreateFactoryType(Prot1Factory, Prot2Factory, Prot3Factory)
    myStack = MyStackType()
    bottomProtocol = myStack()
    """
    
    @classmethod
    def CreateFactoryType(cls, *factories):
        """
        Creates a new class (type) for creating a stacking factory.
        
        MyStackType() = StackingProtocolFactory.CreateFactoryType(Prot1Factory, Prot2Factory, Prot3Factory)
        myStack = MyStackType()
        bottomProtocol = myStack()
        """
        class ConcreteStackingProtocolFactory(cls):
            def __init__(self):
                super().__init__(*factories)
        return ConcreteStackingProtocolFactory
        
    def __init__(self, *factories):
        if len(factories) < 2:
            raise Exception("Stack requires at least two factories")
        self._stackFactories = factories
    
    def __call__(self):
        topProtocol = None
        for i in range(len(self._stackFactories)):
            protocol = self._stackFactories[-i](topProtocol)
            topProtocol = protocol
        return protocol
       
class StackingProtocol(Protocol):
    
    def __init__(self, higherProtocol=None):
        self._higherProtocol = higherProtocol
        self.transport = None
        
    def higherProtocol(self):
        return self._higherProtocol
        
    def setHigherProtocol(self, higherProtocol):
        self._higherProtocol = higherProtocol # error if already set?
    
class StackingTransport(Transport):
    
    def __init__(self, lowerTransport, extra=None):
        super().__init__(extra)
        self._lowerTransport = lowerTransport
        if self.get_extra_info("sockname", None) == None:
            self._extra["sockname"] = lowerTransport.get_extra_info("sockname", None)
        if self.get_extra_info("peername", None) == None:
            self._extra["peername"] = lowerTransport.get_extra_info("peername", None)
            
    def lowerTransport():
        return self._lowerTransport
    
    def close(self):
        return self._lowerTransport.close()
        
    def is_closing(self):
        return self._lowerTransport.is_closing()
        
    def abort(self):
        return self._lowerTransport.abort()
        
    def write(self, data):
        return self._lowerTransport.write(data)
        
    def writelines(self, iterable):
        for i in iterable:
            self.write(i)


"""        
class ProtocolEvents(object):
    PROTOCOL_LISTENERS = {}
    EVENT_CONNECTION_MADE = 0
    EVENT_CONNECTION_LOST = 1
    EVENT_DATA_RECEIVED   = 2
    EVENT_DATA_SENT       = 3
    
    class ProtocolData(object):
        def __init__(self, protocol):
            self.originalConnectionMade = protocol.connectionMade
            self.originalConnectionLost = protocol.connectionLost
            self.originalDataReceived   = protocol.dataReceived
            self.transport              = None
            self.originalTransportWrite = None
            self.listeners = []
            
        def transportData(self, protocol):
            self.transport = protocol.transport
            self.originalTransportWrite = protocol.transport.write
            protocol.transport.write = lambda *args, **kargs: ProtocolEvents.protocolEvent(protocol, 
                                                                     self.originalTransportWrite,
                                                                     ProtocolEvents.EVENT_DATA_SENT,
                                                                     *args, **kargs)
            
        def restoreProtocol(self, protocol):
            protocol.connectionMade = self.originalConnectionMade
            protocol.connectionLost = self.originalConnectionLost
            protocol.dataReceived   = self.originalDataReceived
            if self.transport and self.originalTransportWrite:
                self.transport.write = self.originalTransportWrite
                self.transport = None
            self.originalTransportWrite = None
            self.originalConnectionLost = None
            self.originalConnectionMade = None
            self.originalDataReceived   = None
    
    @classmethod
    def protocolEvent(cls, protocol, protocolMethod, event, *args, **kargs):
        r = protocolMethod(*args, **kargs)
        protocolData = cls.PROTOCOL_LISTENERS.get(protocol, None)
        if not protocolData:
            return r
        
        for l in protocolData.listeners:
            l(protocol, event, args, kargs, r)
        if event == cls.EVENT_CONNECTION_MADE and protocol.transport:
            protocolData.transportData(protocol)
        if event == cls.EVENT_CONNECTION_LOST:
            protocolData.restoreProtocol(protocol)
            del cls.PROTOCOL_LISTENERS[protocol]
        return r
    
    @classmethod
    def EnableProtocol(cls, protocol):
        if not cls.PROTOCOL_LISTENERS.has_key(protocol):
            protocolData = cls.ProtocolData(protocol)
            cls.PROTOCOL_LISTENERS[protocol] = protocolData
            protocol.connectionMade = lambda *args, **kargs: cls.protocolEvent(protocol, 
                                                                               protocolData.originalConnectionMade, 
                                                                               cls.EVENT_CONNECTION_MADE, 
                                                                               *args, **kargs)
            protocol.connectionLost = lambda *args, **kargs: cls.protocolEvent(protocol, 
                                                                               protocolData.originalConnectionLost, 
                                                                               cls.EVENT_CONNECTION_LOST,
                                                                               *args, **kargs)
            protocol.dataReceived   = lambda *args, **kargs: cls.protocolEvent(protocol, protocolData.originalDataReceived,  
                                                                               cls.EVENT_DATA_RECEIVED,
                                                                               *args, **kargs)
        return protocol
    
    @classmethod
    def Listen(cls, protocol, listener):
        cls.EnableProtocol(protocol)
        cls.PROTOCOL_LISTENERS[protocol].listeners.append(listener)
    
    @classmethod
    def EnableProtocolClass(cls, protocolClass):
        raise Exception("Not yet implemented")    
        

class ProtocolLoggerAdapter(object):
    ""
    These class-level operations: prevent memory leaks.
    
    Consider. If we created an adapter for each protocol with a pointer
    to the protocol and then had the protocol have a pointer to the adapter
    we'd have a circular dependency and a memory leak.
    
    so, instead, we have to custom adapt the protocol so that 
    connectionLost clears us. We have to keep track
    of the adapters in case a protocol calls us twice.
    ""
    
    def __init__(self, protocol):
        self.protocolClass, self.protocolId = protocol.__class__, id(protocol)
        self.transport = None
        ProtocolEvents.Listen(protocol, self.protocolEventListener)
        
    def protocolEventListener(self, protocol, protocolMethod, args, kargs, rValue):
        if protocolMethod == protocol.connectionMade:
            self.transport = protocol.transport
        elif protocolMethod == protocol.connectionLost:
            self.transport = None
    
    def process(self, msg, kwargs):
        pmsg = "[%s (%d) connected to " % (self.protocolClass, self.protocolId)
        if self.transport:
            pmsg += str(self.transport.getPeer())
        else: pmsg += "<UNCONNECTED>"
        pmsg += "] "
        return pmsg + msg, kwargs
    
class ENABLE_PACKET_TRACING(object):
    TAG = "packettrace"
    DATA_STORAGE = {}
    
    @classmethod
    def FormatPacketData(cls, dataObj):
        protocol, data, direction = dataObj
        if not cls.DATA_STORAGE.has_key(protocol):
            return "<LOST PACKET DATA : No Protocol>"
        cls.DATA_STORAGE[protocol].update(data)
        msgString = ""
        for packet in cls.DATA_STORAGE[protocol].iterateMessages():
            msgType, msgVersion = packet.__class__.PLAYGROUND_IDENTIFIER, packet.__class__.MESSAGE_VERSION
            msgString = "<<PACKET %s by Protocol %s>> [" % (direction, protocol)
            msgString += msgType + " v"
            msgString += msgVersion + " ID:"
            msgString += str(packet.playground_msgID) +"] "
            msgString += "\n\t"
        if not msgString:
            msgString = "<<DATA RECEIVED BUT NOT PACKETS>>"
        return msgString
    
    def __init__(self, protocol, logLevel=logging.DEBUG, wireProtocol=False):
        ProtocolEvents.Listen(protocol, self)
        
        self.logLevel = logLevel
        self.packetTracingLoggerName = TaggedLogger.GetTaggedLoggerNameForObject(protocol, self.TAG)
        self.traceLogger = logging.getLogger(self.packetTracingLoggerName)
        ENABLE_PACKET_TRACING.DATA_STORAGE[protocol] = wireProtocol and PacketStorage() or MessageStorage()
        
    def __call__(self, protocol, eventType, args, kargs, r):
        if eventType == ProtocolEvents.EVENT_DATA_RECEIVED:
            direction = 'DATA RECEIVED'
        elif eventType == ProtocolEvents.EVENT_DATA_SENT:
            direction = 'TRANSPORT WRITE'
        elif eventType == ProtocolEvents.EVENT_CONNECTION_LOST:
            if ENABLE_PACKET_TRACING.DATA_STORAGE.has_key(protocol):
                del ENABLE_PACKET_TRACING.DATA_STORAGE[protocol]
                return 
        else:
            return
        
        data = args[0]
        specialData = {"packet_trace":(protocol, data, direction)}
        r = self.traceLogger.makeRecord(self.packetTracingLoggerName, 
                                    self.logLevel, "%s.dataReceived"%protocol, 0, 
                                    "%(packet_trace)s", [],
                                    None)
        r.__playground_special__ = specialData
        self.traceLogger.handle(r)
playgroundlog.PlaygroundLoggingFormatter.SPECIAL_CONVERTERS["packet_trace"] = ENABLE_PACKET_TRACING.FormatPacketData
"""