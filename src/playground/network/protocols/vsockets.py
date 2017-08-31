
from playground.network.protocols.packets.vsocket_packets import VNICSocketOpenPacket,              \
                                                                    VNICSocketOpenResponsePacket,   \
                                                                    VNICConnectionSpawnedPacket
from playground.common import CustomConstant as Constant

from asyncio import Protocol
import asyncio

class SocketControl:
    SOCKET_TYPE_CONNECT = Constant(strValue="Outbound Connection Socket")
    SOCKET_TYPE_LISTEN  = Constant(strValue="Inbound Listening Socket")
    
    def __init__(self, socketType, callbackAddr, callbackPort, controlProtocol):
        self._type = socketType
        self._port = None
        self._callbackAddr = callbackAddr
        self._callbackPort = callbackPort
        self._controlProtocol = controlProtocol
        self._spawnedConnectionKeys = set([])
        self._closed = False
        
    def setPort(self, port):
        self._port = port
        
    def closed(self):
        return self._closed
        
    def close(self):
        """
        Close down the whole socket including all spawned connections.
        """
        if not self._closed:
            self._closed = True
            for portKey in self._spawnedConnectionKeys():
                self._vnic.closeConnection(portKey)
            self._spawnedConnectionKeys = set([])
            self._port != None and self._vnic.close(self._port)
            self._controlProtocol.transport.close()
        
    def closeSpawnedConnection(self, portKey):
        """
        Only close a single spawned connection. However, if this is
        an outbound socket, will close everything.
        """
        if self._type == self.SOCKET_TYPE_CONNECT:
            # outbound connections only have one connection per socket
            self.close()
        else:
            # inbound connections can have many. Just close this one.
            self._vnic.closeConnection(portKey)

    def spawnedConnectionClosed(self, portKey):
        """
        This is a callback if the spawned connection closes.
        This can be circular (we close a connection that then
        calls us back) so it is important to check
        """
        if portKey in self._spawnedConnectionKeys:
            self._spawnedConnectionKeys.remove(portKey)
        if not self._closed and self._type == self.SOCKET_TYPE_CONNECT:
            # outbound connections only have one connection per socket
            self.close()
        
    def device(self):
        return self._controlProtocol.device()
        
    def controlProtocol(self):
        return self._controlProtocol
        
    def isListener(self):
        return self._type == self.SOCKET_TYPE_LISTEN
        
    def spawnConnection(self, portIndex):
        if self._type == self.SOCKET_TYPE_CONNECT and len(self._spawnedConnectionKeys) != 0:
            raise Exception("Duplicate Connection on Outbound Connect!")
            
        # create the reverse connection to complete opening the socket
        loop = asyncio.get_event_loop()
        coro = loop.create_connection(lambda: ReverseOutboundSocketProtocol(self, portIndex), 
                                      self._callbackAddr, self._callbackPort)
        futureConnection = asyncio.get_event_loop().create_task(coro)
        futureConnection.add_done_callback(self._spawnFinished)
    
    def _spawnFinished(self, futureConnection):
        if futureConnection.exception() != None:
            # Opening the reverse connection failed. Shut down.
            # this might be a little harsh. It could close many other
            # connections.
            self.close()
        
        else:
            protocol, transport = futureConnection.result()
            
            self._spawnedConnectionKeys.add(protocol._portKey)
            self.device().spawnConnection(protocol._portKey, protocol)
            
            reverseConnectionLocalPort = transport.get_extra_info("sockname")[1]
            self._controlProtocol.sendConnectionSpawned(reverseConnectionLocalPort, protocol._portKey)
        
class ReverseOutboundSocketProtocol(Protocol):
    def __init__(self, control, portKey):
        self._control = control
        self._portKey = portKey
        self.transport = None
    def connection_made(self, transport):
        self.transport = transport
    def dataReceived(self, data):
        self._control.device().write(self._portKey, data)
    def connection_lost(self):
        self._control.close(self._portKey)

class VNICSocketControlProtocol(Protocol):

    MODE_OPENING    = Constant(strValue="Socket Opening")
    MODE_CONNECTED  = Constant(strValue="Outbound Socket Connected")
    MODE_LISTENING  = Constant(strValue="Outbound Socket Listening")
    MODE_CLOSING    = Constant(strValue="Socket Closing")
    
    ERROR_UNKNOWN = Constant(strValue="An Unknown Error", intValue=255)
    ERROR_BUSY    = Constant(strValue="Port is not available", intValue=1)
    
    def __init__(self, vnic):
        self._vnic = vnic
        self._state = self.MODE_OPENING 
        self._deserializer = VNICSocketOpenPacket.Deserializer()
        self._control = None
        self.transport = None
        
    def device(self):
        return self._vnic
        
    def close(self):
        self.transport and self.transport.close()
        
    def connection_made(self, transport):
        self.transport = transport
        
    def connection_lost(self, reason=None):
        self._control and self._control.close()
        
    def dataReceived(self, data):
        self._deserializer.update(data)
        for controlPacket in self._deserializer.nextPackets():
            if isinstance(controlPacket, VNICSocketOpenPacket):
                self.socketOpenReceived(controlPacket)
            #elif isinstance(controlPacket, VNICSocketStatusPacket):
            #    self.socketStatusReceived(controlPacket)
            #elif isinstance(controlPacket, VNICSocketClosePacket):
            #    self.socketCloseReceived(controlPacket)
            #else:
            #    self.unknownPacketReceived(controlPacket)
               
    def socketOpenReceived(self, openSocketPacket):
        resp = VNICSocketOpenResponsePacket()
        
        if self._state != self.MODE_OPENING:
            resp.errorCode = resp.GENERAL_ERROR
            resp.errorMessage = "Socket Already Open"
        
        elif openSocketPacket.isConnectType():
            self._control = SocketControl(SocketControl.SOCKET_TYPE_CONNECT,
                                            openSocketPacket.callbackAddress, openSocketPacket.callbackPort,
                                            self)
            connectData = openSocketPacket.connectData
            port = self._vnic.createOutboundSocket(self._control, 
                                                                connectData.destination,
                                                                connectData.destinationPort)
            if port != None:
                resp.port      = port
                self._control.setPort(port)
            else:
                resp.port         = 0
                resp.errorCode    = int(self.ERROR_UNKNOWN)
                resp.errorMessage = str(self.ERROR_UNKNOWN)
                
        elif openSocketPacket.isListenType():
            self._control = SocketControl(SocketControl.SOCKET_TYPE_LISTEN, 
                                            openSocketPacket.callbackAddress, openSocketPacket.callbackPort,
                                            self)
            listenData = openSocketPacket.listenData
            port = self._vnic.createInboundSocket(self._control, listenData.sourcePort)
            
            if port == listenData.sourcePort:
                resp.port = port
                self._control.setPort(port)
            else:
                resp.port         = 0
                resp.errorCode    = int(ERROR_BUSY)
                resp.errorMessage = str(ERROR_BUSY)
        else:
            pass # error
        self.transport.write(resp.__serialize__())

                                        
    def sendConnectionSpawned(self, spawnTcpPort, portKey):
        #logger.info("Spawning new connection for listener with resvId %d for %s %d on local TCP port %d" % 
        #            (resvId, dstAddr, dstPort, connPort))
        eventPacket = VNICConnectionSpawnedPacket(spawnTcpPort = spawnTcpPort, 
                                                    source = portKey.source,
                                                    sourcePort = portKey.sourcePort,
                                                    destination = portKey.destination,
                                                    destinationPort = portKey.destinationPort)

        self.transport.write(eventPacket.__serialize__())