from ..switch.Switch import Switch
from playground.network.common import PlaygroundAddressBlock

class HierarchyRouter(Switch):
    def __init__(self, prefix):
        super().__init__()
        self._prefix = prefix
        self._WAN = None
        
    def setWan(self, WAN):
        self._WAN = WAN
        
    def getOutboundLinks(self, source, sourcePort, destination, destinationPort):
        if not PlaygroundAddressBlock.IsValidAddressString(destination):
            return outboundLinks
        dstAddress = PlaygroundAddressBlock.FromString(destination)
        dstPrefix = dstAddress[0]
        
        # allow anyone connected to this router to receive messages
        # for aother prefix
        wanLinks = super().getOutboundLinks(source, sourcePort, destination, destinationPort)

        # but, if the dstPrefix is not the local prefix, get nexthop as an 
        # additional link
        if dstPrefix != self._prefix and self._WAN:
            nextHop = self._WAN.nextHop()
            if nextHop:
                destination = "{}.0.0.0".format(nextHop)
                for routeLink in super().getOutboundLinks(source, 0, destination, 0):
                    if routeLink not in wanLinks:
                        wanLinks.append(routeLink)
        return wanLinks
                
    def handleExtensionPacket(self, protocol, packet):
        if isinstance(packet, RouterMIB):
            pass