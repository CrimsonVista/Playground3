'''

'''

from playground.common import CustomConstant as Constant
from playground.network.protocols.vsockets import VNICSocketControlProtocol
from playground.network.protocols.switching import PlaygroundSwitchTxProtocol
from playground.network.protocols.packets.switching_packets import WirePacket
from playground.network.common import PortKey
from playground.network.common import PlaygroundAddress, PlaygroundAddressBlock

from asyncio import Protocol
import io, logging

logger = logging.getLogger(__name__)
        
class ConnectionData: 
        
    def __init__(self, portKey, control):
        self.portKey = portKey
        self.writer = io.BytesIO()
        self.control = control
        
    def setProtocol(self, protocol):
        backlog = self.writer.getvalue()
        if len(backlog) > 0:
            protocol.transport.write(backlog)
        self.writer = protocol.transport
        
    def write(self, data):
        self.writer.write(data)
    
    def close(self):
        try:
            self.writer and self.writer.close()
        except:
            pass
        self.control.spawnedConnectionClosed(self.portKey)
            
class VNIC:
    _STARTING_SRC_PORT = 2000
    _MAX_PORT          = (2**16)-1

    def __init__(self, playgroundAddress):
        self._address = PlaygroundAddress.FromString(playgroundAddress)
        logger.info("{} just started up".format(self))
        
        # ports and connections are interrelated but slightly different
        # a port is just an integer key mapped to a control object.
        # a connection is tied to the port.
        self._ports = {}
        self._connections = {}
        self._dumps = set([])
        self._freePorts = self._freePortsGenerator()
        self._linkTx = None#PlaygroundSwitchTxProtocol(self, self.address())
        self._connectedToNetwork = False
        self._promiscuousMode = None
        
    def _freePortsGenerator(self):
        while True:
            for i in range(self._STARTING_SRC_PORT, self._MAX_PORT):
                if i in self._ports: continue
                yield i
                
    def promiscuousLevel(self):
        if self._promiscuousMode == None: return 0
        return self._promiscuousMode
        
    def setPromiscuousLevel(self, level):
        """
        Setting level to 0 or None turns promiscuous mode off.
        Otherwise, start listening for more addresses than just your own.
        
        Level 0: Address Only (off)
        Level 1: x.y.z.*
        Level 2: x.y.*.*
        Level 3: x.*.*.*
        Level 4: *.*.*.*
        """
        if level == None or level < 0: level = 0
        if level > 4: level = 4
        if level != self._promiscuousMode:
            self._promiscuousMode = level
            self._updateRegisteredAddress()
            
    def _updateRegisteredAddress(self):
        if not self.connected(): return
        level = self._promiscuousMode
        listeningBlock = PlaygroundAddressBlock(*self._address.toParts())
        for i in range(level):
            listeningBlock.getParentBlock()
        self._linkTx.changeRegisteredAddress(str(listeningBlock))
        
    def address(self):
        return self._address
        
    def connected(self):
        return self._connectedToNetwork
    
    def switchConnectionFactory(self):
        if self._linkTx and self._linkTx.transport:
            self._linkTx.transport.close()
        self._linkTx = PlaygroundSwitchTxProtocol(self, self.address())
        return self._linkTx
        
    def controlConnectionFactory(self):
        logger.debug("{} creating control protocol for new connection.".format(self))
        controlProtocol = VNICSocketControlProtocol(self)
        return controlProtocol
        
    ###
    # Switch Dmux routines
    ###
    
    def connectionMade(self):
        logger.info("{} connected to network".format(self))
        self._connectedToNetwork = True
        if self.promiscuousLevel():
            self._updateRegisteredAddress()
        
    def connectionLost(self):
        logging.info("{} lost connection network".format(self))
        self._connectedToNetwork = False
        self._linkTx = None
        
    def demux(self, source, sourcePort, destination, destinationPort, data):
        logger.debug("{} received {} bytes of data from {}:{} for {}:{}".format(self, len(data), source, sourcePort, destination, destinationPort))
        for dumper in self._dumps:
            dumpPacket = WirePacket(source=source, sourcePort=sourcePort,
                                    destination=destination, destinationPort=destinationPort,
                                    data=data)
            dumper.transport.write(dumpPacket.__serialize__())
                
        remotePortKey = PortKey(source, sourcePort, destination, destinationPort)
        
        # this portkey is backwards. The source is from the remote machine
        # but our ports have the remote machine being the destination. 
        # So, invert:
        
        localPortKey = remotePortKey.inverseKey()
        
        # Check if the full port key is already in connections. If so, we're all done
        if localPortKey in self._connections:
            self._connections[localPortKey].write(data)
            return
        
        # If there's no port key in connections, check for listening port.
        listeningPort = localPortKey.sourcePort
        if listeningPort in self._ports and self._ports[listeningPort].isListener():
            # We have a new connection. Spawn.
            # use a controlled port so that if the listening port is closed,
            # all of the spawned ports are closed.
            self._connections[localPortKey] = ConnectionData(localPortKey, self._ports[listeningPort])
            self._connections[localPortKey].write(data)
            self._ports[listeningPort].spawnConnection(localPortKey)
            
        else:
            pass # drop? Fail silently?
    
    ### End Dmux Methods ###
    
    def spawnConnection(self, portKey, protocol):
        self._connections[portKey].setProtocol(protocol)
        
    def createOutboundSocket(self, control, destination, destinationPort):
        port = next(self._freePorts)
        
        self._ports[port] = control
        
        portKey = PortKey(str(self._address), port, destination, destinationPort)
        self._connections[portKey] = ConnectionData(portKey, control)
        control.spawnConnection(portKey)
        
        return port
        
    def createInboundSocket(self, control, requestedPort):
        if requestedPort in self._ports:
            # port already in use
            return None
            
        self._ports[requestedPort] = control
        return requestedPort
        
    def closeConnection(self, portKey):
        if portKey in self._connections:
            connData = self._connections[portKey]
            del self._connections[portKey]
            
            connData.close()
            
    def closePort(self, port):
        if port in self._ports:
            control = self._ports[port]
            del self._ports[port]
            control.close()
            
    def controlClosed(self, control):
        portKeys = self._controlChannels.get(control.controlProtocol(),[])
        for pk in portKeys:
            self.closePort(pk)
            
    def write(self, portKey, data):
        if not self._linkTx or not self._linkTx.transport:
            return
        self._linkTx.write(portKey.source, portKey.sourcePort, portKey.destination, portKey.destinationPort, data)
        
    def startDump(self, protocol):
        self._dumps.add(protocol)
        
    def stopDump(self, protocol):
        if protocol in self._dumps:
            self._dumps.remove(protocol)
            
    def __repr__(self):
        return "VNIC ({})".format(self._address)
        
def basicUnitTest():
    from playground.network.testing import MockTransportToStorageStream as MockTransport
    from playground.asyncio_lib.testing import TestLoopEx
    from playground.network.protocols.packets.vsocket_packets import    VNICSocketOpenPacket,           \
                                                                        VNICSocketOpenResponsePacket,   \
                                                                        VNICStartDumpPacket,            \
                                                                        PacketType
    from playground.network.protocols.packets.switching_packets import WirePacket
    import io, asyncio
    
    vnic1 = VNIC("1.1.1.1")
    assert vnic1.address() == "1.1.1.1"

    linkTx = vnic1.switchConnectionFactory()
    linkTransport = MockTransport(io.BytesIO())
    linkTx.connection_made(linkTransport)
    
    control = vnic1.controlConnectionFactory()
    controlTransport = MockTransport(io.BytesIO())
    control.connection_made(controlTransport)
    
    class TransportFactory:
        def __init__(self):
            self.transports = {}
            self.txPort = 5000
        def __call__(self, protocol, addr, port):
            t = MockTransport(io.BytesIO(), extra={'sockname':('192.168.0.1',self.txPort),'peername':(addr, port)})
            t.protocol = protocol
            self.transports[(addr, port)] = t
            self.txPort+=1
            return t
    transportFactory = TransportFactory()
    
    loop = TestLoopEx()
    loop.setTransportFactory(transportFactory)
    asyncio.set_event_loop(loop)
    
    openPacket = VNICSocketOpenPacket(callbackAddress="192.168.0.2", callbackPort=9091)
    openPacket.connectData = openPacket.SocketConnectData(destination="2.2.2.2", destinationPort=100)
    control.data_received(openPacket.__serialize__())
    
    deserializer = PacketType.Deserializer()
    deserializer.update(controlTransport.sink.getvalue())
    responsePackets = list(deserializer.nextPackets())
    assert len(responsePackets) == 1
    assert isinstance(responsePackets[0], VNICSocketOpenResponsePacket)
    assert not responsePackets[0].isFailure()
    
    # Two advances might be necessary to create the reverse connection AND complete it.
    loop.advanceClock(1)
    loop.advanceClock(1)
    
    assert ("192.168.0.2",9091) in transportFactory.transports
    socketTransport = transportFactory.transports[("192.168.0.2",9091)]
    
    txPacket1 = WirePacket(source="2.2.2.2", sourcePort=100, destination="1.1.1.1", destinationPort=responsePackets[0].port,
                            data=b"This is a test message")
    linkTx.data_received(txPacket1.__serialize__())
    
    assert socketTransport.sink.getvalue()==txPacket1.data
    
    listenPacket = VNICSocketOpenPacket(callbackAddress="192.168.0.2", callbackPort=9092)
    listenPacket.listenData = listenPacket.SocketListenData(sourcePort=666)
    
    control2 = vnic1.controlConnectionFactory()
    control2Transport = MockTransport(io.BytesIO())
    control2.connection_made(control2Transport)
    control2.data_received(listenPacket.__serialize__())
    
    deserializer = PacketType.Deserializer()
    deserializer.update(control2Transport.sink.getvalue())
    responsePackets = list(deserializer.nextPackets())
    assert len(responsePackets) == 1
    assert isinstance(responsePackets[0], VNICSocketOpenResponsePacket)
    assert not responsePackets[0].isFailure()
    
    txPacket2 = WirePacket(source="2.2.2.2", sourcePort=100, destination="1.1.1.1", destinationPort=666,
                            data=b"This is a test message x2")
    linkTx.data_received(txPacket2.__serialize__())
    
    loop.advanceClock(1)
    loop.advanceClock(1)
    
    assert ("192.168.0.2",9092) in transportFactory.transports
    
    socket2Transport = transportFactory.transports[("192.168.0.2",9092)]
    assert socket2Transport.sink.getvalue()==txPacket2.data
    
    txPacket3 = WirePacket(source="1.1.1.1", sourcePort=666, destination="2.2.2.2", destinationPort=100, data=b"response1")
    socket2Transport.protocol.data_received(txPacket3.__serialize__())
    
    vnic1.setPromiscuousLevel(2)
    # TODO: Asert new announce packet set
    dumper = vnic1.controlConnectionFactory()
    dumperTransport = MockTransport(io.BytesIO())
    dumper.connection_made(dumperTransport)
    dumper.data_received(VNICStartDumpPacket().__serialize__())
    txPacket4 = WirePacket(source="2.2.2.2", sourcePort=666, destination="2.2.1.5", destinationPort=300, data=b"No Address")
    linkTx.data_received(txPacket4.__serialize__())
    
    deserializer.update(dumperTransport.sink.getvalue())
    
    dumpPackets = list(deserializer.nextPackets())
    assert len(dumpPackets) == 1
    assert dumpPackets[0].data == txPacket4.data
    
    # set "myProtocol" so that closing the transport closes
    # the protocol (connection_lost). Check that no further
    # messages are sent to the protocol
    dumperTransport.setMyProtocol(dumper)
    dumperTransport.close()
    dumperTransport.sink.truncate(0)
    
    txPacket5 = WirePacket(source="2.2.2.2", sourcePort=666, destination="2.2.1.5", destinationPort=300, data=b"No Address")
    linkTx.data_received(txPacket5.__serialize__())
    
    deserializer.update(dumperTransport.sink.getvalue())
    
    dumpPackets = list(deserializer.nextPackets())
    assert len(dumpPackets) == 0
    
if __name__=="__main__":
    basicUnitTest()
    print("Basic Unit Test Successful.")
