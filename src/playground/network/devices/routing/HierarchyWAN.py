
class HierarchyWAN:
    class DirectLinkTransport:
        def __init__(self, link):
            self._link = link
        def write(self, rawBytes):
            self._link.data_received(rawBytes)
        def close(self):
            self._link.connection_lost(None)
            
    def __init__(self):
        self._apsp = {}
        self._routers = {}
        
    def registerLANRouter(self, routerPrefix, router, directConnections):
        if self._apsp.get(routerPrefix, None) != None:
            raise Exception("Duplicate Router for prefix {}".format(routerPrefix))
        self._apsp[routerPrefix] = {}
        self._routers[routerPrefix] = router
        for dstPrefix in directConnections:
            # obviously, the next hop for the direct connection is the
            # direct connection.
            self._apsp[routerPrefix][dstPrefix] = [dstPrefix]
            self._apsp[dstPrefix][routerPrefix] = [routerPrefix]
        self.updateAllPairsShortestPaths()
        
    def createDirectLink(self, prefix1, prefix2):
        rxProtocol1 = self._routers[prefix1].ProtocolFactory()
        rxProtocol2 = self._routers[prefix2].ProtocolFactory()
        rxProtocol1.connection_made(self.DirectLinkTransport(rxProtocol2))
        rxProtocol2.connection_made(self.DirectLinkTransport(rxProtocol1))
        rxProtocol1.data_received(AnnounceLinkPacket(Address="{}.0.0.0"%prefix1))
        rxProtocol2.data_received(AnnounceLinkPacket(Address="{}.0.0.0"%prefix2))
    
    def unregisterLANRouter(self, routerPrefix)
        pass
        
    def updateAllPairsShortestPaths(self):
        allPrefixes = self._apsp.keys()
        
        for intPrefix in allPrefixes:
            for srcPrefix in allPrefixes:
                for dstPrefix in allPrefixes:
                    if intPrefix == srcPrefix or intPrefix == dstPrefix or srcPrefix == dstPrefix:
                        continue
                    curPath = self._apsp[srcPrefix].get(dstPrefix,None)
                    checkPath1 = self._apsp[srcPrefix].get(intPrefix, None)
                    checkPath2 = self._apsp[intPrefix].get(dstPrefix, None)
                    if checkPath1 and checkPoint2:
                        checkPath = checkPath1 + checkPath2
                        if curPath == None or len(curPath) > len(checkPath):
                            self._apsp[srcPrefix][dstPrefix] = checkPath
                            self._apsp[dstPrefix][srcPrefix] = checkPath[:]
                            self._apsp[dstPrefix][srcPrefix].reverse()
        
    def nextHop(self, srcPrefix, dstPrefix):
        curRoute = self._apsp.get(srcPrefix,{}).get(dstPrefix,None)
        if curRoute:
            nextHop = curRoute[0]
            return nextHop
        return None