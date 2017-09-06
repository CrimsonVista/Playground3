from playground.network.common import PlaygroundAddress, StackingProtocol
from playground.network.protocols.vsockets import VNICConnectProtocol, VNICListenProtocol, VNICCallbackProtocol
from playground.network.devices.pnms import NetworkManager
import playground
import asyncio

class CallbackService:
    def __init__(self, callbackAddress, callbackPort, protocolStack):
        self._callbackAddress = callbackAddress
        self._callbackPort = callbackPort
        self._dataProtocols = {}
        self._completionData = {}
        self._controlProtocols = {}
        self._connectionBackptr = {}
        self._protocolStack = protocolStack
        
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
        self._dataProtocols[spawnTcpPort].setPlaygroundConnectionInfo(applicationProtocol, source, sourcePort, destination, destinationPort)
        
        self._controlProtocols[controlProtocol] = self._controlProtocols.get(controlProtocol, []) + [self._dataProtocols[spawnTcpPort]]
        self._connectionBackptr[self._dataProtocols[spawnTcpPort]] = controlProtocol
        del self._dataProtocols[spawnTcpPort]
        del self._completionData[spawnTcpPort]

    async def waitForConnections(self, controlProtocol, n=1, timeout=30):
        if not controlProtocol in self._controlProtocols:
            self._controlProtocols[controlProtocol] = []
        while len(self._controlProtocols[controlProtocol]) < n and timeout >= 0:
            await asyncio.sleep(.1)
            timeout = timeout-.1
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
    def __init__(self, vnicService, protocolStack=None, callbackAddress="127.0.0.1", callbackPort=0):
        self._stack = protocolStack
        self._vnicService = vnicService
        self._callbackService = CallbackService(callbackAddress, callbackPort, protocolStack)
        self._ready = False
        
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
        coro = self._callbackService.waitForConnections(protocol, timeout=timeout)
        connections = await coro
        if len(connections) != 1:
            raise Exception("VNIC Open Failed (Unexpected Error, connections={})!".format(len(connections)))
        playgroundProtocol = connections[0]
        while isinstance(playgroundProtocol, StackingProtocol) and playgroundProtocol.higherProtocol():
            playgroundProtocol = playgroundProtocol.higherProtocol()
        
        # this is the application protocol!
        # unlike twisted, asyncio does not require transport to be set at all.
        # consequently, there's no easy way to know if its connected
        while not playgroundProtocol.transport:
            await asyncio.sleep(.1)
            timeout = timeout-.1
        if not playgroundProtocol.transport:
            raise Exception("Timeout before application connection made")
            
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
        print("Connecting to {}:{}".format(vnicAddr, vnicPort))
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

g_PlaygroundNetworkConnectors = {"default":PlaygroundConnector(StandardVnicService())}        
def getConnector(connectorName="default"):
    return g_PlaygroundNetworkConnectors[connectorName]
def setConnector(connectorName, connector):
    g_PlaygroundNetworkConnectors[connectorName] = connector
playground.getConnector = getConnector
playground.setConnector = setConnector