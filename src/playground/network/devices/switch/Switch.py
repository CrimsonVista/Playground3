'''
Created on August 28, 2017
Copied and adapted from Playground 2.0
Original File Created on Aug 20, 2013

@author: sethjn
'''

from playground.network.protocols.switching import PlaygroundSwitchRxProtocol
from playground.network.common import PlaygroundAddressBlock
        
class Switch:        
    def __init__(self):
        # addressToLinks is one to many. One address may map to many links
        self._addressToLinks = {}
        
        # linkToAddress is one to one. A single link may only map to one address.
        self._linkToAddress = {}
        
    def unregisterLink(self, protocol):
        if protocol in self._linkToAddress:
            oldAddress = self._linkToAddress[protocol]
            self._addressToLinks[oldAddress].remove(protocol)
            
            del self._linkToAddress[protocol]
        
    def registerLink(self, address, protocol):
        if not PlaygroundAddressBlock.IsValidAddressString(address):
            # drop bad addresses silently.
            return
        self.unregisterLink(protocol)
            
        if not address in self._addressToLinks:
            self._addressToLinks[address] = set([protocol])
        else:
            self._addressToLinks[address].add(protocol)
            
        self._linkToAddress[protocol] = address

    def getOutboundLinks(self, source, sourcePort, destination, destinationPort):
        outboundLinks = set([])
        if not PlaygroundAddressBlock.IsValidAddressString(destination):
            return outboundLinks
        pAddress = PlaygroundAddressBlock.FromString(destination)
        while pAddress:
            outboundLinks.update(self._addressToLinks.get(str(pAddress), set([])))
            pAddress = pAddress.getParentBlock()
        return outboundLinks
        
    def handleExtensionPacket(self, protocol, packet):
        """
        Should be overwritten by subclasses
        """
        pass
        
    def ProtocolFactory(self):
        return PlaygroundSwitchRxProtocol(self)
        
    
def basicUnitTest():
    s = Switch()
    p1 = s.ProtocolFactory()
    p2 = s.ProtocolFactory()
    p3 = s.ProtocolFactory()
    s.registerLink("1.1.1.1", p1)
    s.registerLink("2.2.2.2", p2)
    s.registerLink("2.2.*.*", p3)
    assert len(s.getOutboundLinks(None, None, "1.1.1.1", None)) == 1
    assert p1 in s.getOutboundLinks(None, None, "1.1.1.1", None)
    s.unregisterLink(p1)
    assert len(s.getOutboundLinks(None, None, "1.1.1.1", None))== 0
    
    assert len(s.getOutboundLinks(None, None, "2.2.2.2", None)) == 2
    assert len(s.getOutboundLinks(None, None, "2.2.3.4", None)) == 1
    
if __name__=="__main__":
    basicUnitTest()
    print("Basic Unit Test completed successfully")