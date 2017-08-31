'''
Created on August 28, 2017
Copied and adapted from Playground 2.0
Original File Created on Aug 20, 2013

@author: sethjn
'''

from playground.network.protocols.switching import PlaygroundSwitchRxProtocol
        
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
        self.unregisterLink(protocol)
            
        if not address in self._addressToLinks:
            self._addressToLinks[address] = set([protocol])
        else:
            self._addressToLinks[address].add(protocol)
            
        self._linkToAddress[protocol] = address

    def getOutboundLinks(self, source, sourcePort, destination, destinationPort):
        return self._addressToLinks.get(destination, set([]))
        
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
    s.registerLink("1.1.1.1", p1)
    assert len(s.getOutboundLinks(None, None, "1.1.1.1", None)) == 1
    assert p1 in s.getOutboundLinks(None, None, "1.1.1.1", None)
    s.unregisterLink(p1)
    assert len(s.getOutboundLinks(None, None, "1.1.1.1", None))== 0
    
if __name__=="__main__":
    basicUnitTest()
    print("Basic Unit Test completed successfully")