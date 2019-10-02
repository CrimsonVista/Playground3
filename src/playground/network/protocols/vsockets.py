
from playground.network.protocols.packets.vsocket_packets import VNICSocketOpenPacket,              \
                                                                    VNICSocketOpenResponsePacket,   \
                                                                    VNICConnectionSpawnedPacket,    \
                                                                    VNICStartDumpPacket,            \
                                                                    VNICStopDumpPacket,             \
                                                                    VNICSocketControlPacket,        \
                                                                    VNICSocketClosePacket,          \
                                                                    VNICPromiscuousLevelPacket,     \
                                                                    PacketType
from playground.network.protocols.packets.switching_packets import WirePacket
from playground.network.common import StackingProtocol, StackingTransport
from playground.network.common import PortKey
from playground.common import CustomConstant as Constant


from asyncio import Protocol
import asyncio, logging, random
from asyncio.futures import Future
logger = logging.getLogger(__name__)

class SocketControl:
    SOCKET_TYPE_CONNECT = Constant(strValue="Outbound Connection Socket")
    SOCKET_TYPE_LISTEN  = Constant(strValue="Inbound Listening Socket")
    
    def __init__(self, connectionId, socketType, callbackAddr, callbackPort, controlProtocol):
        self._connectionId = connectionId
        self._type = socketType
        self._port = None
        self._callbackAddr = callbackAddr
        self._callbackPort = callbackPort
        self._controlProtocol = controlProtocol
        self._spawnedConnectionKeys = set([])
        self._closed = False
        
    def connectionId(self):
        return self._connectionId
        
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
            portKeys = self._spawnedConnectionKeys
            self._spawnedConnectionKeys = set([])
            for portKey in portKeys:
                logger.debug("Closing {} asking device to close connection to {}".format(self, portKey))
                self.device().closeConnection(portKey)
            (self._port != None) and self.device().closePort(self._port)
        
    def closeSpawnedConnection(self, portKey):
        """
        Only close a single spawned connection. However, if this is
        an outbound socket, will close everything.
        """
        logger.debug("{} ({}) closing port key {}".format(self, self._type, portKey))
        if self._type == self.SOCKET_TYPE_CONNECT:
            # outbound connections only have one connection per socket
            self.close()
        else:
            # inbound connections can have many. Just close this one.
            self.device().closeConnection(portKey)

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
        
        logger.debug("{} spwaning connection on portkey {}. Callback={}:{}".format(self.device(), portIndex, self._callbackAddr, self._callbackPort))
        # create the reverse connection to complete opening the socket
        loop = asyncio.get_event_loop()
        coro = loop.create_connection(lambda: ReverseOutboundSocketProtocol(self, portIndex), 
                                      self._callbackAddr, self._callbackPort)
        futureConnection = asyncio.get_event_loop().create_task(coro)
        futureConnection.add_done_callback(self._spawnFinished)
    
    def _spawnFinished(self, futureConnection):
        logger.debug("{} spawn completed. {}".format(self.device(), futureConnection))
        if futureConnection.exception() != None:
            # Opening the reverse connection failed. Shut down.
            # this might be a little harsh. It could close many other
            # connections.
            self.close()
        
        else:
            transport, protocol = futureConnection.result()
            
            self._spawnedConnectionKeys.add(protocol._portKey)
            self.device().spawnConnection(protocol._portKey, protocol)
            
            reverseConnectionLocalPort = transport.get_extra_info("sockname")[1]
            self._controlProtocol.sendConnectionSpawned(self._connectionId, 
                                                        reverseConnectionLocalPort, 
                                                        protocol._portKey)
        
class ReverseOutboundSocketProtocol(Protocol):
    def __init__(self, control, portKey):
        self._control = control
        self._portKey = portKey
        self.transport = None
    def connection_made(self, transport):
        logger.debug("Connection made for reverse")
        self.transport = transport
    def data_received(self, data):
        logger.debug("writing data from reverse to vnic")
        self._control.device().write(self._portKey, data)
    def connection_lost(self, reason=None):
        logger.debug("conneciton lost to reverse. reason={}".format(reason))
        self._control.closeSpawnedConnection(self._portKey)

class VNICSocketControlProtocol(Protocol):
    
    ERROR_UNKNOWN = Constant(strValue="An Unknown Error", intValue=255)
    ERROR_BUSY    = Constant(strValue="Port is not available", intValue=1)
    
    def __init__(self, vnic):
        self._vnic = vnic
        self._deserializer = PacketType.Deserializer()
        self._control = {}
        self.transport = None
        self.dumping = False
        
    def controlLost(self, controlId):
        if controlId in self._control:
            control = self._control[controlId]
            control.close()
            del self._control[controlId]
        
    def device(self):
        return self._vnic
        
    def close(self):
        self.transport and self.transport.close()
        
    def connection_made(self, transport):
        logger.debug("VNIC socket control spawn {}".format(self))
        self.transport = transport
        
    def connection_lost(self, reason=None):
        logger.debug("VNIC connection_lost {} for reason {}".format(self, reason))
        if self._dumping:
            self._vnic.stopDump(self)
            self._dumping = False
        for controlId in self._control:
            control = self._control[controlId]
            try:
                control.close()
            except:
                pass
        self._control = {}
        self.transport = None
        
    def data_received(self, data):
        self._deserializer.update(data)
        for controlPacket in self._deserializer.nextPackets():
            if isinstance(controlPacket, VNICSocketOpenPacket):
                logger.info("{} received socket open operation.".format(self._vnic))
                self.socketOpenReceived(controlPacket)
            elif isinstance(controlPacket, VNICSocketClosePacket):
                logger.info("{} received socket close {} operation".format(self._vnic, controlPacket.ConnectionId))
                self.controlLost(controlPacket.ConnectionId)
            elif isinstance(controlPacket, VNICStartDumpPacket) and not self._dumping:
                logger.info("{} received start dump operation.".format(self._vnic))
                self._dumping = True
                self._vnic.startDump(self) 
            elif isinstance(controlPacket, VNICStopDumpPacket) and self._dumping:
                logger.info("{} received stop dump operation.".format(self._vnic))
                self._dumping = False
                self._vnic.stopDump(self) 
            elif isinstance(controlPacket, WirePacket):
                logger.debug("{} received raw wire for dump mode connection.".format(self._vnic))
                outboundKey = PortKey(controlPacket.source, controlPacket.sourcePort, 
                                        controlPacket.destination, controlPacket.destinationPort)
                self._vnic.write(outboundKey, controlPacket.data)
            elif isinstance(controlPacket, VNICPromiscuousLevelPacket):
                logger.info("{} received promiscuous control packet.".format(self._vnic))
                try:
                    logger.info("{} setting prom. mode to {}".format(self._vnic, controlPacket.set))
                    if controlPacket.set != controlPacket.UNSET:
                        self._vnic.setPromiscuousLevel(controlPacket.set)
                    controlPacket.set = controlPacket.UNSET
                    controlPacket.get = self._vnic.promiscuousLevel()
                    logger.info("{} returning level {}".format(self, controlPacket.get))
                    self.transport.write(controlPacket.__serialize__())
                except Exception as error:
                    logger.error("{} got error {}".format(self._vnic, error))
            #elif isinstance(controlPacket, VNICSocketStatusPacket):
            #    self.socketStatusReceived(controlPacket)
            #elif isinstance(controlPacket, VNICSocketClosePacket):
            #    self.socketCloseReceived(controlPacket)
            else:
                logger.info("{} received unknown packet {}".format(self._vnic, controlPacket))
               
    def socketOpenReceived(self, openSocketPacket):
        resp = VNICSocketOpenResponsePacket(ConnectionId=openSocketPacket.ConnectionId)
        
        if openSocketPacket.ConnectionId in self._control:
            resp.port = 0
            resp.errorCode = int(self.ERROR_BUSY)
            resp.errorMessage = "Connection ID Already in Use"
        
        elif openSocketPacket.isConnectType():
            control = SocketControl(openSocketPacket.ConnectionId, 
                                    SocketControl.SOCKET_TYPE_CONNECT,
                                    openSocketPacket.callbackAddress, openSocketPacket.callbackPort,
                                    self)
            self._control[openSocketPacket.ConnectionId] = control
            connectData = openSocketPacket.connectData
            port = self._vnic.createOutboundSocket(control, 
                                                    connectData.destination,
                                                    connectData.destinationPort)
            if port != None:
                resp.port      = port
                control.setPort(port)
            else:
                resp.port         = 0
                resp.errorCode    = int(self.ERROR_UNKNOWN)
                resp.errorMessage = str(self.ERROR_UNKNOWN)
                
        elif openSocketPacket.isListenType():
            control = SocketControl(openSocketPacket.ConnectionId, 
                                    SocketControl.SOCKET_TYPE_LISTEN, 
                                    openSocketPacket.callbackAddress, openSocketPacket.callbackPort,
                                    self)
            self._control[openSocketPacket.ConnectionId] = control
            listenData = openSocketPacket.listenData
            port = self._vnic.createInboundSocket(control, listenData.sourcePort)
            
            if port == listenData.sourcePort:
                resp.port = port
                control.setPort(port)
            else:
                resp.port         = 0
                resp.errorCode    = int(self.ERROR_BUSY)
                resp.errorMessage = str(self.ERROR_BUSY)
        else:
            pass # error
        self.transport.write(resp.__serialize__())

                                        
    def sendConnectionSpawned(self, connectionId, spawnTcpPort, portKey):
        #logger.info("Spawning new connection for listener with resvId %d for %s %d on local TCP port %d" % 
        #            (resvId, dstAddr, dstPort, connPort))
        eventPacket = VNICConnectionSpawnedPacket(ConnectionId=connectionId,
                                                    spawnTcpPort = spawnTcpPort, 
                                                    source = portKey.source,
                                                    sourcePort = portKey.sourcePort,
                                                    destination = portKey.destination,
                                                    destinationPort = portKey.destinationPort)

        self.transport.write(eventPacket.__serialize__())

class VNICSocketControlClientProtocol(Protocol):
    def __init__(self, callbackService):
        self._connections = {}
        self._futures = {}
        self._callbackService = callbackService
        self._connectionId = 0
        self._deserializer = VNICSocketControlPacket.Deserializer()
        self.transport=None 
    
    def connect(self, destination, destinationPort, applicationProtocolFactory):
        self._connectionId += 1
        logger.debug("Requesting connect to {}:{} from vnic (connection ID {})".format(destination,
                                                                                       destinationPort,
                                                                                       self._connectionId))
        callbackAddr, callbackPort = self._callbackService.location()
        openSocketPacket = VNICSocketOpenPacket(ConnectionId = self._connectionId,
                                                callbackAddress=callbackAddr, 
                                                callbackPort=callbackPort)
        openSocketPacket.connectData = openSocketPacket.SocketConnectData(destination=destination, 
                                                                          destinationPort=destinationPort)
        packetBytes = openSocketPacket.__serialize__()
        self.transport.write(packetBytes)
        
        future = Future()
        self._connections[self._connectionId] = applicationProtocolFactory
        self._futures[self._connectionId] = ("connect", future) 
        return future
    
    def listen(self, listenPort, applicationProtocolFactory):
        self._connectionId += 1
        logger.debug("Requesting listenting socket on port {} from vnic (connection ID {})".format(listenPort,
                                                                                       self._connectionId))
        logger.info("Listen in {}. Has transport {}. For port {}".format(self, self.transport, listenPort))
        callbackAddr, callbackPort = self._callbackService.location()
        openSocketPacket = VNICSocketOpenPacket(ConnectionId=self._connectionId, 
                                                callbackAddress=callbackAddr, callbackPort=callbackPort)
        openSocketPacket.listenData = openSocketPacket.SocketListenData(sourcePort = listenPort)
        
        self.transport.write(openSocketPacket.__serialize__())
        future = Future()
        self._connections[self._connectionId] = applicationProtocolFactory
        self._futures[self._connectionId] = ("listen", future) 
        return future
    
    def close(self, connectionId):
        logger.debug("Closing connection {}".format(connectionId))
        self.transport.write(VNICSocketClosePacket(ConnectionId=connectionId).__serialize__())
    
    def connection_made(self, transport):
        logger.info("{} setting transport {}".format(self, transport))
        self.transport=transport
    
    def data_received(self, data):
        self._deserializer.update(data)
        for packet in self._deserializer.nextPackets():
            if isinstance(packet, VNICSocketOpenResponsePacket):
                logger.debug("Open callback for connection {}. Failure? {}".format(packet.ConnectionId, packet.isFailure()))
                if not packet.ConnectionId in self._futures:
                    logger.debug("No such connection ID {}. Ignoring.".format(packet.ConnectionId))
                    continue
                futureType, future = self._futures[packet.ConnectionId]
                if (futureType == "listen") or packet.isFailure():
                    # Listen packets are "complete" as soon as the VNIC says they're open.
                    # Connect packets aren't complete until the circuit is made
                    del self._futures[packet.ConnectionId]
                
                if packet.isFailure():
                    future.set_exception(Exception("Could not open socket. Error {} - {}".format(packet.errorCode, packet.errorMessage)))
                elif futureType == "listen":
                    # listening packet is done now. A connect packet waits for outbound to be setup.
                    future.set_result((packet.ConnectionId, packet.port))
                    
            elif isinstance(packet, VNICConnectionSpawnedPacket):
                if packet.ConnectionId in self._futures:
                    futureType, future = self._futures[packet.ConnectionId]
                else:
                    futureType = "listen"
                logger.info("Connect {} callback {}:{} -> {}:{}".format(packet.ConnectionId,
                                                                        packet.source, packet.sourcePort,
                                                                        packet.destination, packet.destinationPort))
                applicationProtocolFactory = self._connections[packet.ConnectionId]
                self._callbackService.completeCallback(packet.ConnectionId, futureType, 
                                                       applicationProtocolFactory(),
                                                        packet.spawnTcpPort, 
                                                        packet.source, packet.sourcePort, 
                                                        packet.destination, packet.destinationPort)
                if futureType == "connect":
                    # A connect is done after a spawn. The listening socket is not.
                    del self._futures[packet.ConnectionId]
                    future.set_result((packet.ConnectionId, packet.sourcePort))
        
    def connection_lost(self, reason=None):
        logger.info("Connection Lost - VNIC Connect Protocol. Reason = {}.".format(reason))
        
class VNICCallbackProtocol(StackingProtocol):
    def __init__(self, callbackService):
        super().__init__(None)
        self.transport = None
        self._callbackService = callbackService
        self._spawnPort = None
        self._backlog = []
        self._higherConnectionMade = False
        
    def connection_made(self, transport):
        super().connection_made(transport)
        self.transport = transport
        self._spawnPort = transport.get_extra_info("peername")[1]
        self._callbackService.newDataConnection(self._spawnPort, self)
        
    def setPlaygroundConnectionInfo(self, stack, application, source, sourcePort, destination, destinationPort):
        self.setHigherProtocol(stack)
        nextTransport = StackingTransport(self.transport, {"sockname":(source, sourcePort),
                                                            "peername":(destination, destinationPort),
                                                            "spawnport":self._spawnPort})
        p = self
        while p.higherProtocol():
            p = p.higherProtocol()
        p.setHigherProtocol(application)
        logger.debug("Creating tranport for higher protocol {} with spawnport {}".format(self.higherProtocol(), self._spawnPort))
        self.higherProtocol().connection_made(nextTransport)
        self._higherConnectionMade = True
        while self._backlog:
            self.higherProtocol().data_received(self._backlog.pop(0))

    def connection_lost(self, reason=None):
        logger.debug("low level connection_lost for callback port {}, reason={}".format(self._spawnPort, reason))
        super().connection_lost(reason)
        #self.higherProtocol().transport.close()
        self.higherProtocol().connection_lost(reason)
        # Checking the log so that we can ensure _spawnPort is always set
        logger.debug("Connection Lost towards higher protocol for connection initiated through spawned port {}".format(self._spawnPort))
        if self._spawnPort:
            self._callbackService.dataConnectionClosed(self, self._spawnPort)
            
    def data_received(self, buf):
        if self._higherConnectionMade:
            logger.debug("Pushing data to application, data received on {}".format(self._spawnPort)) 
            if self.higherProtocol():
                try:
                    self.higherProtocol().data_received(buf)
                except Exception as e:
                    logger.debug("Could not push data to application because {}.".format(e))
        else:
            self._backlog.append(buf)
            
class VNICDumpProtocol(Protocol):
    def __init__(self):
        self.transport = None
        
    def connection_made(self, transport):
        self.transport = transport
        self.transport.write(VNICStartDumpPacket().__serialize__())
        
    def data_received(self, data):
        pass
        # subclasses can overwrite
        
    def write(self, source, sourceAddress, destination, destinationPort, data):
        pkt = WirePacket(source=source, sourceAddress=sourceAddress,
                            destination=destination, destinationPort=destinationPort,
                            data=data)
        self.transport.write(pkt.__serialize__())
        
class VNICPromiscuousControl(Protocol):
    def __init__(self, level=None):
        self.level = level
        self.currentVnicLevel = None
        self.deserializer = VNICPromiscuousLevelPacket.Deserializer()
    def connection_made(self, transport):
        self.transport=transport
        request = VNICPromiscuousLevelPacket()
        if self.level != None: request.set = self.level
        transport.write(request.__serialize__())
    def data_received(self, data):
        self.deserializer.update(data)
        for response in self.deserializer.nextPackets():
            if response.get != response.UNSET:
                self.currentVnicLevel = response.get
            self.transport.close()
            self.transport=None
            break
