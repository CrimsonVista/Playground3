'''

'''

from playground.common import CustomConstant as Constant
from playground.network.protocols.vsockets import VNICSocketControlProtocol
from playground.network.protocols.switching import PlaygroundSwitchTxProtocol
from playground.network.common import PortKey

from asyncio import Protocol
import io
        
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
        self._address = playgroundAddress
        
        # ports and connections are interrelated but slightly different
        # a port is just an integer key mapped to a control object.
        # a connection is tied to the port.
        self._ports = {}
        self._connections = {}
        self._freePorts = self._freePortsGenerator()
        self._linkTx = None#PlaygroundSwitchTxProtocol(self, self.address())
        self._connectedToNetwork = False
        
    def _freePortsGenerator(self):
        while True:
            for i in range(self._STARTING_SRC_PORT, self._MAX_PORT):
                if i in self._ports: continue
                yield i
        
    def address(self):
        return self._address
        
    def connectedToNetwork(self):
        return self._connectedToNetwork
    
    def switchConnectionFactory(self):
        if self._linkTx and self._linkTx.transport:
            self._linkTx.transport.close()
        self._linkTx = PlaygroundSwitchTxProtocol(self, self.address())
        return self._linkTx
        
    def controlConnectionFactory(self):
        controlProtocol = VNICSocketControlProtocol(self)
        return controlProtocol
        
    ###
    # Switch Dmux routines
    ###
    
    def connected(self):
        # TODO: log connected to the switch
        self._connectedToNetwork = True
        
    def disconnected(self):
        self._connectedToNetwork = False
        self._linkTx = None
        
    def demux(self, source, sourcePort, destination, destinationPort, data):
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
        
        portKey = PortKey(self._address, port, destination, destinationPort)
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
        
def basicUnitTest():
    from playground.network.testing import MockTransportToStorageStream as MockTransport
    from playground.asyncio_lib.testing import TestLoopEx
    from playground.network.protocols.packets.vsocket_packets import VNICSocketOpenPacket, VNICSocketOpenResponsePacket, PacketType
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
    
    print(linkTransport.sink.getvalue())
    
if __name__=="__main__":
    basicUnitTest()
    print("Basic Unit Test Successful.")
