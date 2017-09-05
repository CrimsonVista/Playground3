'''
Created on Aug 20, 2013

@author: sethjn
'''

import random
from .packets.switching_packets import AnnounceLinkPacket, WirePacket, PacketType
from playground.common import Timer, Minutes, Seconds

from asyncio import Protocol
import io

class PlaygroundSwitchRxProtocol(Protocol):
    def __init__(self, switch):
        '''
        Creates an instance of the ChaerponeProtocol class with the
        server as the argument.
        '''
        self._switch = switch
        self._deserializer = PacketType.Deserializer()
        self.transport = None
        
    def connection_lost(self, reason=None):
        self._switch.unregisterLink(self)
        
    def connection_made(self, transport):
        self.transport = transport
        
    def data_received(self, buf):
        self._deserializer.update(buf)
        for packet in self._deserializer.nextPackets():
            if isinstance(packet, AnnounceLinkPacket):
                self._switch.registerLink(packet.address, self)
            elif isinstance(packet, WirePacket):
                destinations = self._switch.getOutboundLinks(packet.source, packet.sourcePort,
                                                                packet.destination, packet.destinationPort)
                for destinationProtocol in destinations:
                    # The Switching Protocol supports higher-layer processing.
                    # So, if there's a higher protocol, pass the un-modified packet
                    # Otherwise, serialize for transport
                    packetBytes = packet.__serialize__()
                    destinationProtocol.transport.write(packetBytes)
            else:
                self._switch.handleExtensionPacket(protocol, packet)
            #errReporter.error("Unexpected message received", exception=NetworkError.UnexpectedPacket(packet))
            
class PlaygroundSwitchTxProtocol(Protocol):
    MAX_MSG_SIZE = 2**16
    
    class FragStorage:
        def __init__(self, fragId, totalSize, parentContainer):
            self._fragId = fragId
            self._totalSize = totalSize
            self._parentContainer = parentContainer
            self._received = 0
            self._bufferStream = io.BytesIO()
            self._offsetsReceived = set([])
            self._cleanUpTimer = Timer(Minutes(5), self._removeFromParentContainer)
            self._cleanUpTimer.start()
            
        def _removeFromParentContainer(self):
            if self._fragId in self._parentContainer:
                del self._parentContainer[self._fragId]
            
        def insert(self, fragOffset, fragData):
            if fragOffset in self._offsetsReceived: return
            self._offsetsReceived.add(fragOffset)
            self._bufferStream.seek(fragOffset)
            self._bufferStream.write(fragData)
            self._received += len(fragData)
            self._cleanUpTimer.extend(Minutes(5))
            
        def isComplete(self):
            return self._received == self._totalSize
            
        def getData(self):
            return self._bufferStream.getvalue()
            
        def cleanup(self):
            self._cleanUpTimer.expire()
            return self.getData()
    
    def __init__(self, demuxer, address):
        self._demuxer = demuxer
        self._address = address
        self._deserializer = WirePacket.Deserializer()
        self._fragStorage = {}
        self.transport = None
        
    def connection_made(self, transport):
        self.transport = transport
        announceLinkPacket = AnnounceLinkPacket(address=self._address)
        self.transport.write(announceLinkPacket.__serialize__())
        self._demuxer.connected()
        
    def write(self, source, sourcePort, destination, destinationPort, data):
        wirePacket = WirePacket(source          = source,
                                sourcePort      = sourcePort,
                                destination     = destination,
                                destinationPort = destinationPort)
        
        if len(data) <= self.MAX_MSG_SIZE:
            wirePacket.data = data
            self.transport.write(wirePacket.__serialize__())
            return
        
        fragData = WirePacket.FragmentData()
        fragData.fragId = random.getrandbits(32)
        fragData.totalSize = len(data)
        offset = 0
        
        while data:
            fragData.offset = offset
            wirePacket.fragData = fragData
            wirePacket.data = data[:self.MAX_MSG_SIZE]
            
            data = data[self.MAX_MSG_SIZE:]
            offset += len(wirePacket.data)
            
            # transmit packet
            self.transport.write(wirePacket.__serialize__())
        
    def data_received(self, data):
        self._deserializer.update(data)
        demuxData = None
        for wirePacket in self._deserializer.nextPackets():
            if wirePacket.isFragment():
                fragData = wirePacket.fragData
                if not fragData.fragId in self._fragStorage:
                    self._fragStorage[fragData.fragId] = self.FragStorage(fragData.fragId, fragData.totalSize, self._fragStorage)
                self._fragStorage[fragData.fragId].insert(fragData.offset, wirePacket.data)
                if self._fragStorage[fragData.fragId].isComplete():
                    demuxData = self._fragStorage[fragData.fragId].cleanup()
            else:
                demuxData = wirePacket.data
                
            if demuxData != None:
                self._demuxer.demux(wirePacket.source, wirePacket.sourcePort, 
                                    wirePacket.destination, wirePacket.destinationPort,
                                    demuxData)
                                    
    def connection_lost(self, reason=None):
        self._demuxer.disconnected()
                                    

def basicUnitTest():
    from playground.network.testing import MockTransportToProtocol as MockTransport
    class MockSwitch:
        def __init__(self):
            self.addresses = {}
            self.extensionPackets = []
        def registerLink(self, address, protocol):
            self.addresses[address] = self.addresses.get(address,[])+[protocol]
        def unregisterLink(self, protocol):
            # this is slow, but fine for testing:
            rem = None
            for address in self.addresses:
                if not protocol in self.addresses[address]: continue
                self.addresses[address].remove(protocol)
                if len(self.addresses[address]) == 0: rem = address
            if rem: del self.addresses[rem]
        def getOutboundLinks(self, source, sourcePort, destination, destinationPort):
            return self.addresses[destination]
        def handleExtensionPacket(self, ep):
            self.extensionPackets.append(ep)
        def connected(self):
            pass
        def disconnected(self):
            pass
    class MockClient:
        def __init__(self):
            self.results = []
        def demux(self, source, sourcePort, destination, destinationPort, data):
            self.results.append((source, sourcePort, destination, destinationPort, data))
    
            
    switch = MockSwitch()
    rx1 = PlaygroundSwitchRxProtocol(switch)
    rx2 = PlaygroundSwitchRxProtocol(switch)
    rx3 = PlaygroundSwitchRxProtocol(switch)
    
    client1, client2, client3 = MockClient(), MockClient(), MockClient()
    c1Tx = PlaygroundSwitchTxProtocol(client1, "1.1.1.1")
    c2Tx = PlaygroundSwitchTxProtocol(client2, "2.2.2.2")
    c3Tx = PlaygroundSwitchTxProtocol(client3, "2.2.2.2")
    
    # Client transports send data to rx)
    c1Transport = MockTransport(rx1) 
    c2Transport = MockTransport(rx2)
    c3Transport = MockTransport(rx3)
    
    # Switch transports send back to clients
    rx1Transport = MockTransport(c1Tx)
    rx2Transport = MockTransport(c2Tx)
    rx3Transport = MockTransport(c3Tx)
    
    # Make the switch-side connections first
    rx1.connection_made(rx1Transport)
    rx2.connection_made(rx2Transport)
    rx3.connection_made(rx3Transport)
    
    # Connecting the client protocols should cause an announce packet sent
    assert len(switch.addresses) == 0
    
    c1Tx.connection_made(c1Transport)
    assert len(switch.addresses) == 1
    
    c2Tx.connection_made(c2Transport)
    assert len(switch.addresses) == 2
    
    # Client 3 has the same address as client 2
    c3Tx.connection_made(c3Transport)
    assert len(switch.addresses) == 2
    
    # Send some small hello messages.
    c1Tx.write("1.1.1.1", 80, "2.2.2.2", 1000, b"Test1")
    assert len(client2.results) == 1
    assert client2.results[0] == ("1.1.1.1", 80, "2.2.2.2", 1000, b"Test1")
    assert len(client3.results) == 1
    assert client3.results[0] == client2.results[0]
    
    c2Tx.write("2.2.2.2", 1000, "1.1.1.1", 80, b"Response")
    assert client1.results[0] == ("2.2.2.2", 1000, "1.1.1.1", 80, b"Response")
    
    # Send a large packet to test fragmentation/re-assembly
    repeatingKey = b"REPEATINGKEY"
    largeData = b""
    while len(largeData) < (PlaygroundSwitchTxProtocol.MAX_MSG_SIZE + 100):
        largeData += repeatingKey
    
    curWriteCount = c3Transport.writeCount
    c3Tx.write("2.2.2.2", 1000, "1.1.1.1", 80, largeData)
    # should have written twice (two fragments)
    assert c3Transport.writeCount == (curWriteCount + 2)
    
    print("client 1 results count {}, len data {}, original len{}.".format(len(client1.results), len(client1.results[1][-1]), len(largeData)))
    assert client1.results[1][-1] == largeData
    
if __name__=="__main__":
    basicUnitTest()
    print("Basic Unit Test completed successfully")
    
    