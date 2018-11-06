from ..switch.Switch import Switch
from playground.network.common import PlaygroundAddressBlock

import logging
logger = logging.getLogger(__name__)

class HierarchyRouter(Switch):
    """
    A HierarchyRouter is just a wrapper/adapter around a non-routing switch.
    Within the WAN, there is a single switch for each "location" (prefix),
    but there is i HierarchyRouter wrapper/adapter for **each** incoming
    connection. This serves two purposes
    
    1. It enables messages to be routed to other routers/switches.
    For this, it checks the WAN for next hop for different prefixes.
    
    2. It also serves as a "floating" hub for the device moving
    about the WAN. When the device connects, it gets a connection to
    the router, which may or may not be connected to any prefix/switch.
    Again, there is only one HierarchyRouter per connection, so this
    adapter is specific to the connecting device. As the device "moves",
    its HierarchyRouter is attached to different switches, enabling
    communication within different prefix areas.
    """
    def __init__(self, WAN):
        super().__init__()
        self._prefix = None
        self._switch = None
        self._WAN = WAN
        self._hack_dontReleaseConnection = False
        
    def setPrefix(self, prefix, switch):
        if self._switch:
            # remove this address from the current switch
            for protocol in self._linkToAddress:
                self._switch.unregisterLink(protocol)
                
        self._switch = switch
        self._prefix = prefix
        
        if self._switch:
            # add this address to the new switch
            for protocol, address in self._linkToAddress.items():
                self._switch.registerLink(address, protocol)
                
    def unregisterLink(self, protocol):
        # We have to over-write this. Unlike normal switches,
        # there is a 1-to-1 link between the Router and the Connection
        # Usually, there will only be one connection. When it is
        # unregistered, the router is probably done.
        # However, all we need to do is unregister from any current
        # switches and unregister from the WAN
        self.setPrefix(None, None)
        print("Unregistering link from",protocol, protocol.transport)
        
        # if we're just re-registering, don't remove
        if not self._hack_dontReleaseConnection:
            self._WAN.removeConnection(protocol)
        
        # but, just to be clean, call super, to remove from our
        # local tables
        super().unregisterLink(protocol)
        
    def registerLink(self, address, protocol):
        # Unfortunately, the registerLink calls unregisterLink
        # first. This removes the connection from the WAN. We
        # have to re-add it.
        self._hack_dontReleaseConnection = True
        try:
            super().registerLink(address, protocol)
        except Exception as e:
            self._hack_dontReleaseConnection = False
            raise e
        self._hack_dontReleaseConnection = False
        
        
    def currentPrefix(self):
        return self._prefix
        
    def getOutboundLinks(self, source, sourcePort, destination, destinationPort):
        outboundLinks = set([])
        if not PlaygroundAddressBlock.IsValidAddressString(destination):
            return outboundLinks
        if not self._switch:
            # there is no service in this location.
            return outboundLinks
            
        dstAddress = PlaygroundAddressBlock.FromString(destination)
        dstPrefix = dstAddress[0]
        
        # allow anyone connected to this router to receive messages
        # for aother prefix
        outboundLinks = self._switch.getOutboundLinks(source, sourcePort, destination, destinationPort)

        # but, if the dstPrefix is not the local prefix, get nexthop as an 
        # additional link
        if dstPrefix != self._prefix and self._WAN:
            logger.debug("Received message for prefix {}. My prefix is {}. Routing".format(dstPrefix, self._prefix))
            nextHop = self._WAN.nextHop(self._prefix, dstPrefix)
            logger.debug("Next hop is {}".format(nextHop))
            if nextHop:
                destination = "{}.0.0.0".format(nextHop)
                logger.debug("Adding routing links {}".format(self._switch.getOutboundLinks(source, 0, destination, 0)))
                outboundLinks.update(self._switch.getOutboundLinks(source, 0, destination, 0))
        return outboundLinks
                
    def handleExtensionPacket(self, protocol, packet):
        if isinstance(packet, RouterMIB):
            pass