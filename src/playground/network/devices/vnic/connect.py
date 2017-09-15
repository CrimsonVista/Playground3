from playground.network.common import PlaygroundAddress, StackingProtocol
from playground.network.common.Protocol import ProtocolObservation
from playground.network.protocols.vsockets import VNICConnectProtocol, VNICListenProtocol, VNICCallbackProtocol
from playground.network.devices.pnms import NetworkManager
from playground.asyncio_lib import SimpleCondition
import playground
import asyncio

class ConnectionMadeObserver:
    """
    Observer protocols for connection made events. Provide
    an async waiter for a protocol to be connected.
    
    TODO: clean up ones that shut down badly.
    Not that big of a deal because this is per process. If
    it shuts down bad, whole process probably goes bad
    """
    def __init__(self):
        self.protocols = {}
        
    def watch(self, protocol):
        """
        For a given protocol, setup a condition to
        wait for connection made
        """
        ProtocolObservation.Listen(protocol, self)
        self.protocols[protocol] = SimpleCondition()
        
    def connected(self, protocol):
        return self.protocols[protocol] == "connected"
        
    def release(self, protocol):
        if not protocol in self.protocols: return
        ProtocolObservation.StopListening(protocol, self)
        del self.protocols[protocol]
        
    def __call__(self, protocol, event, *args):
        if protocol in self.protocols and event == ProtocolObservation.EVENT_CONNECTION_MADE:
            if self.protocols[protocol] == "connected":
                # we're already done.
                return
            condition = self.protocols[protocol]
            self.protocols[protocol] = "connected"
            condition.notify()
    async def awaitConnection(self, protocol):
        # if we don't have the protocol, or it's already done, don't wait.
        if self.protocols.get(protocol, None) != "connected":
            condition = self.protocols[protocol]
        
            # wait for the connection to be made
            await condition.waitForPredicate(lambda: self.protocols[protocol] == True)
        
        # at this point, we're connected. clean up and return
        self.release(protocol)
        return
connectionMadeObserver = ConnectionMadeObserver()

class CallbackService:
    def __init__(self, callbackAddress, callbackPort, protocolStack):
        self._callbackAddress = callbackAddress
        self._callbackPort = callbackPort
        self._dataProtocols = {}
        self._completionData = {}
        self._controlProtocols = {}
        self._connectionBackptr = {}
        self._protocolStack = protocolStack
        
        # asyncio condition
        self._conditionConnections = SimpleCondition()
        
    def location(self):
        return (self._callbackAddress, self._callbackPort)
        
    def buildDataProtocol(self):
        higherProtocol = self._protocolStack and self._protocolStack() or None
        return VNICCallbackProtocol(self, higherProtocol)
        
    def newDataConnection(self, spawnTcpPort, dataProtocol):
        self._dataProtocols[spawnTcpPort] = dataProtocol
        
        if spawnTcpPort in self._completionData and spawnTcpPort in self._dataProtocols:
            self.buildStack(spawnTcpPort)
        
    def dataConnectionClosed(self, dataProtocol, spawnTcpPort):
        if spawnTcpPort in self._dataProtocols:
            del self._dataProtocols[spawnTcpPort]
        if dataProtocol in self._connectionBackptr:
            controlProtocol = self._connectionBackptr[dataProtocol]
            self._controlProtocols[controlProtocol].remove(dataProtocol)
            del self._connectionBackptr[dataProtocol]
        
    def completeCallback(self, controlProtocol, applicationProtocol, spawnTcpPort, source, sourcePort, destination, destinationPort):
        self._completionData[spawnTcpPort] = (controlProtocol, applicationProtocol, source, sourcePort, destination, destinationPort)
        
        if spawnTcpPort in self._completionData and spawnTcpPort in self._dataProtocols:
            self.buildStack(spawnTcpPort)
        
            
    def buildStack(self, spawnTcpPort):
        controlProtocol, applicationProtocol, source, sourcePort, destination, destinationPort = self._completionData[spawnTcpPort]
        
        connectionMadeObserver.watch(applicationProtocol)
        
        self._dataProtocols[spawnTcpPort].setPlaygroundConnectionInfo(applicationProtocol, source, sourcePort, destination, destinationPort)
        
        self._controlProtocols[controlProtocol] = self._controlProtocols.get(controlProtocol, []) + [self._dataProtocols[spawnTcpPort]]
        self._connectionBackptr[self._dataProtocols[spawnTcpPort]] = controlProtocol
        del self._dataProtocols[spawnTcpPort]
        del self._completionData[spawnTcpPort]

        # notify that a new connection is received
        self._conditionConnections.notify()

    async def waitForConnections(self, controlProtocol, n=1):
        if not controlProtocol in self._controlProtocols:
            self._controlProtocols[controlProtocol] = []
        
        # now wait for the list to be big enough
        predicate = lambda: len(self._controlProtocols[controlProtocol]) >= n
        result = await self._conditionConnections.awaitCondition(predicate)
        return self._controlProtocols[controlProtocol]
        
    def getConnections(self, controlProtocol):
        if not controlProtocol in self._controlProtocols:
            self._controlProtocols[controlProtocol] = []
        return self._controlProtocols[controlProtocol]
        
class PlaygroundServer:
    class FakePlaygroundSocket:
        def __init__(self, protocol, explicitName=None):
            self.protocol = protocol
            self.explicitName = explicitName
            self.close = lambda *args: None
            self.connect = lambda *args: None
            self.recv = lambda *args: None
            self.send = lambda *args: None
        def getpeername(self):
            if self.protocol.transport:
                return self.protocol.transport.get_extra_info("peername")
            return ("None",0)
        def gethostname(self): 
            if self.explicitName: return self.explicitName
            if self.protocol.transport:
                return self.protocol.transport.get_extra_info("sockname")
            return ("None",0)
        
    def __init__(self, controlProtocol, address, port, connections):
        self._controlSocket = self.FakePlaygroundSocket(controlProtocol, (address, port))
        self._connections = []
        self._closed = True
        # Doesn't do anything yet or support any sockets
        
    def close(self):
        if self._closed: return
        self._closed = True
        for conn in self._connections:
            if conn.transport: conn.transport.close()
        
    def __getattribute__(self, attr):
        if attr == "sockets":
            sockets = [self._controlSocket]
            for connection in self._connections:
                sockets.append(self.FakePlaygroundSocket(connection))
            return sockets
        return super().__getattribute__(attr)
        
class PlaygroundConnector:
    def __init__(self, vnicService=None, protocolStack=None, callbackAddress="127.0.0.1", callbackPort=0):
        self._stack = protocolStack
        self._vnicService = vnicService
        self._callbackService = CallbackService(callbackAddress, callbackPort, protocolStack)
        self._ready = False
        
        if not vnicService:
            self._vnicService = StandardVnicService()
            
        self._protocolReadyCondition = SimpleCondition()
        
    async def create_callback_service(self):
        callbackAddress, callbackPort = self._callbackService.location()
        coro = asyncio.get_event_loop().create_server(self._callbackService.buildDataProtocol, host=callbackAddress, port=callbackPort)
        server = await coro
        servingPort = server.sockets[0].getsockname()[1]
        self._callbackService._callbackPort = servingPort
        self._ready = True
        
    async def create_playground_connection(self, protocolFactory, destination, destinationPort, vnicName="default", cbPort=0, timeout=60):
        if not self._ready:
            await self.create_callback_service()
        if not isinstance(destination, PlaygroundAddress):
            destination = PlaygroundAddress.FromString(destination)
            
        if vnicName == "default":
            vnicName = self._vnicService.getVnicByDestination(destination, destinationPort)
        if not vnicName:
            raise Exception("Could not find a valid vnic four outbound connection {}:{}".format(destination, destinationPort))
        location = self._vnicService.getVnicTcpLocation(vnicName)
        if not location:
            raise Exception("Playground network not ready. Could not find interface to connect to {}:{}".format(destination, destinationPort))
        vnicAddr, vnicPort = location
        connectProtocol = VNICConnectProtocol(destination, destinationPort, self._callbackService, protocolFactory)
        coro = asyncio.get_event_loop().create_connection(lambda: connectProtocol, vnicAddr, vnicPort)
        transport, protocol  = await coro
        # now we have to wait for protocol to make it's callback.
        coro = self._callbackService.waitForConnections(protocol)
        connections = await asyncio.wait_for(coro, timeout)
        if len(connections) != 1:
            raise Exception("VNIC Open Failed (Unexpected Error, connections={})!".format(len(connections)))
            
        playgroundProtocol = connections[0]
        while isinstance(playgroundProtocol, StackingProtocol) and playgroundProtocol.higherProtocol():
            playgroundProtocol = playgroundProtocol.higherProtocol()
        
        connectionMadeCoro = connectionMadeObserver.awaitConnection(playgroundProtocol)
        await asyncio.wait_for(connectionMadeCoro, timeout)
            
        return playgroundProtocol.transport, playgroundProtocol
        
    async def create_playground_server(self, protocolFactory, sourcePort, host="default", vnicName="default", cbPort=0):
        if not self._ready:
            await self.create_callback_service()
            
        # find the address to host on.
        if host == "default":
            vnic = self._vnicService.getDefaultVnic()
        else:
            vnic = self._vnicService.getVnicByLocalAddress(host) 
        if not vnic:
            raise Exception("Could not find a valid VNIC.")
            
        address = self._vnicService.getVnicPlaygroundAddress(vnic)
        location = self._vnicService.getVnicTcpLocation(vnic)
        
        if not location:
            raise Exception("Could not find an active VNIC.")
        
        vnicAddr, vnicPort = location
        listenProtocol = VNICListenProtocol(sourcePort, self._callbackService, protocolFactory)
        coro = asyncio.get_event_loop().create_connection(lambda: listenProtocol, vnicAddr, vnicPort)
        transport, protocol  = await coro
        
        server = PlaygroundServer(protocol, host, sourcePort, self._callbackService.getConnections(protocol))
        return server


class StandardVnicService:
    """
    The standard service is a thin layer around the Playground Network Management
    System (PNMS).
    """
    def __init__(self):
        try:
            self.deviceManager = NetworkManager()
            self.deviceManager.loadConfiguration()
        except:
            # todo. Check that this is a can't find config exception
            self.deviceManaer = None
        
    def getDefaultVnic(self):
        if not self.deviceManager:
            return None
        return self.deviceManager.routing().getDefaultRoute()
        
    def getVnicByDestination(self, destination, destinationPort):
        if not self.deviceManager:
            return None
        return self.deviceManager.routing().getRoutingDevice(destination)
        
    def getVnicByLocalAddress(self, vnicAddress):
        if not self.deviceManager:
            return None
        for deviceName in self.deviceManager.deviceInfo().devices():
            deviceType = self.deviceManager.deviceInfo().lookupDeviceType(deviceName)
            if deviceType == "vnic":
                device = self.deviceManager.getDevice(deviceName)
                if device.address() == vnicAddress:
                    return deviceName
        return None
        
    def getVnicPlaygroundAddress(self, vnicName):
        if not vnicName: return None
        device = self.deviceManager.getDevice(vnicName)
        if device: 
            address = device.address()
            return PlaygroundAddress.FromString(address)
        return None
        
    def getVnicTcpLocation(self, vnicName):
        if not vnicName: return None
        device = self.deviceManager.getDevice(vnicName)
        if device: return device.tcpLocation()
        return None

g_PlaygroundNetworkConnectors = {"default":PlaygroundConnector()}
def getConnector(connectorName="default"):
    return g_PlaygroundNetworkConnectors[connectorName]
def setConnector(connectorName, connector):
    g_PlaygroundNetworkConnectors[connectorName] = connector