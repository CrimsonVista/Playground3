from ..switch import Switch
from .HierarchyRouter import HierarchyRouter
from ...protocols.switching import AnnounceLinkPacket
import random, logging

logger = logging.getLogger(__name__)

class HierarchyWAN:            
    class DirectLinkTransport:
        def __init__(self, WAN, link):
            self._link = link
            self._WAN = WAN
        def write(self, rawBytes):
            if random.random() < self._WAN.getRoutingLossRate():
                return
            self._link.data_received(rawBytes)
        def close(self):
            self._link.connection_lost(None)
            
    def __init__(self):
        self._apsp = {}
        self._switches = {}
        self._directLinks = {}
        self._connections = {}
        self._routingLossRate = 0.0001
        
    def getRoutingLossRate(self):
        return self._routingLossRate
        
    def setRoutingLossRate(self, rate):
        self._routingLossRate = rate
        
    def registerLANSwitch(self, routerPrefix, switch=None):
        if self._apsp.get(routerPrefix, None) != None:
            raise Exception("Duplicate Router for prefix {}".format(routerPrefix))
        if switch == None:
            switch = Switch()
            
        logger.debug("Adding new LAN at prefix {}".format(routerPrefix))
        
        self._switches[routerPrefix] = switch
        self._apsp[routerPrefix] = {}
        self._directLinks[routerPrefix] = {}
        
    def setDirectConnections(self, routerPrefix, directConnections):
        if routerPrefix not in self._apsp or routerPrefix not in self._switches:
            raise Exception("No switch located at prefix {}".format(routerPrefix))
        
        # clear all connections for sourcePrefix and any routes
        self._apsp[routerPrefix] = {}
        for prefix in self._apsp:
            # break any direct connection. Function has no effect
            # if there is no direct connection, so safe to call always
            self.destroyDirectLink(routerPrefix, prefix)
            
            # if routerPrefix is a destination, remove it
            if routerPrefix in self._apsp[prefix]:
                del self._apsp[prefix][routerPrefix]
            
            # remove any destination that uses routerPrefix to get there
            toRemove = []
            for dstPrefix in self._apsp[prefix]:
                if routerPrefix in self._apsp[prefix][dstPrefix]:
                    toRemove.append(dstPrefix)
            for dstPrefix in toRemove:
                del self._apsp[prefix][dstPrefix]
                
        for dstPrefix in directConnections:
            # obviously, the next hop for the direct connection is the
            # direct connection.
            
            if dstPrefix not in self._apsp or dstPrefix not in self._switches:
                raise Exception("No destination switch located at prefix {}".format(dstPrefix))
            
            self._apsp[routerPrefix][dstPrefix] = [dstPrefix]
            self._apsp[dstPrefix][routerPrefix] = [routerPrefix]
        self.updateAllPairsShortestPaths()
        
        for dstPrefix in self._apsp[routerPrefix]:
            if dstPrefix in self._switches:
                self.createDirectLink(routerPrefix, dstPrefix)
        
    def createDirectLink(self, prefix1, prefix2):
        rxProtocol1 = self._switches[prefix1].ProtocolFactory()
        rxProtocol2 = self._switches[prefix2].ProtocolFactory()
        rxProtocol1.connection_made(self.DirectLinkTransport(self, rxProtocol2))
        rxProtocol2.connection_made(self.DirectLinkTransport(self, rxProtocol1))
        rxProtocol1.transport.write(AnnounceLinkPacket(address="{}.0.0.0".format(prefix1)).__serialize__())
        rxProtocol2.transport.write(AnnounceLinkPacket(address="{}.0.0.0".format(prefix2)).__serialize__())
        self._directLinks[prefix1][prefix2] = rxProtocol1
        self._directLinks[prefix2][prefix1] = rxProtocol2
        
    def destroyDirectLink(self, prefix1, prefix2):
        if prefix2 in self._directLinks[prefix1]:
            rxProtocol1 = self._directLinks[prefix1][prefix2]
            rxProtocol1.transport and rxProtocol1.transport.close()
            del self._directLinks[prefix1][prefix2]
        if prefix1 in self._directLinks[prefix2]:
            rxProtocol2 = self._directLinks[prefix2][prefix1]
            rxProtocol2.transport and rxProtocol2.transport.close()
            del self._directLinks[prefix2][prefix1]
    
    def unregisterLANSwitch(self, prefix):
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
                    if checkPath1 and checkPath2:
                        checkPath = checkPath1 + checkPath2
                        if curPath == None or len(curPath) > len(checkPath):
                            self._apsp[srcPrefix][dstPrefix] = checkPath
                            #self._apsp[dstPrefix][srcPrefix] = checkPath[:]
                            #self._apsp[dstPrefix][srcPrefix].reverse()
        
        logger.debug("Done with APSP")
        if logger.getEffectiveLevel() > logging.DEBUG:
            logger.debug("NEW ALL PAIRS SHORTEST PATH COMPUTED")
            for srcPrefix in allPrefixes:
                for dstPrefix in self._apsp[srcPrefix]:
                    logger.debug("{}-{}: {}".format(srcPrefix, dstPrefix,
                                                    str(self._apsp[srcPrefix][dstPrefix])))
        logger.debug("Done debugging")
        
    def getPrefixes(self):
        return list(self._apsp.keys())
    
    def getRoute(self, srcPrefix, dstPrefix):
        return self._apsp.get(srcPrefix,{}).get(dstPrefix,[])
        
    def getRoutes(self, srcPrefix):
        return list(self._apsp.get(srcPrefix, {}).items())
    
    def nextHop(self, srcPrefix, dstPrefix):
        curRoute = self._apsp.get(srcPrefix,{}).get(dstPrefix,None)
        if curRoute:
            nextHop = curRoute[0]
            return nextHop
        return None
        
    def ProtocolFactory(self):
        routerAdapter = HierarchyRouter(self)
        protocol = routerAdapter.ProtocolFactory()
        self._connections[protocol] = routerAdapter
        return protocol
        
    def currentConnections(self):
        return list(self._connections.items())
        
    def setLocation(self, protocol, prefix):
        switch = self._switches.get(prefix, None)
        self._connections[protocol].setPrefix(prefix, switch)
        
    def removeConnection(self, protocol):
        if protocol in self._connections:
            del self._connections[protocol]
