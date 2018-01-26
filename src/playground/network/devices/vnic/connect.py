from playground import Configure
from playground.network.common import PlaygroundAddress, StackingProtocol
from playground.network.packet.PacketDefinitionRegistration import PacketDefinitionSilo
from playground.network.common.Protocol import ProtocolObservation
from playground.network.protocols.vsockets import VNICSocketControlClientProtocol, VNICCallbackProtocol
from playground.network.devices.pnms import NetworkManager
from playground.asyncio_lib import SimpleCondition
import playground
import asyncio, os, sys, importlib, traceback, logging, time
from concurrent.futures import TimeoutError

logger = logging.getLogger(__name__)

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
            await condition.awaitCondition(lambda: self.protocols[protocol] == "connected")
        
        # at this point, we're connected. clean up and return
        self.release(protocol)
        return
connectionMadeObserver = ConnectionMadeObserver()

class CallbackService:
    def __init__(self, callbackAddress, callbackPort, protocolStack):
        self._callbackAddress = callbackAddress
        self._callbackPort = callbackPort
        self._dataProtocols = {}     # Holds all of the data transfer protocols (callback protocols)
        self._connectionData = {}    # Holds connection data such as connection ID, etc
        self._connectionSpawn = {}   # Maps connection Ids to data protocols
        self._connectionBackptr = {} # Reverse of connectionSpawn
        self._protocolStack = protocolStack
        
        # asyncio condition
        self._conditionConnections = SimpleCondition()
        
    def location(self):
        return (self._callbackAddress, self._callbackPort)
    
    def tryToBuildStack(self, spawnTcpPort):
        if spawnTcpPort in self._connectionData and spawnTcpPort in self._dataProtocols:
            connectionType = self._connectionData[spawnTcpPort][1]
            if connectionType == "listen":
                stackFactory = self._protocolStack[1]
            else:
                stackFactory = self._protocolStack[0]
            self.buildStack(stackFactory, spawnTcpPort)
        
    def newDataConnection(self, spawnTcpPort, dataProtocol):
        logger.debug("Callback service new data connection on tcp port {}".format(spawnTcpPort))
        self._dataProtocols[spawnTcpPort] = dataProtocol
        self.tryToBuildStack(spawnTcpPort)
        
    def completeCallback(self, connectionId, connectionType, applicationProtocol, spawnTcpPort, source, sourcePort, destination, destinationPort):
        logger.debug("Callback service setting up callback for connectionID {}, spawn port {}".format(connectionId, spawnTcpPort))
        self._connectionData[spawnTcpPort] = (connectionId, connectionType, applicationProtocol, source, sourcePort, destination, destinationPort)
        self.tryToBuildStack(spawnTcpPort)
            
    def buildStack(self, stackFactory, spawnTcpPort):
        connectionId, connectionType, applicationProtocol, source, sourcePort, destination, destinationPort = self._connectionData[spawnTcpPort]
        
        connectionMadeObserver.watch(applicationProtocol)
        
        stackProtocol = stackFactory and stackFactory() or None
        stackString = "["+str(stackProtocol)
        s_p = stackProtocol and stackProtocol.higherProtocol()
        while s_p:
            stackString += ","+str(s_p)
            s_p = s_p.higherProtocol()
        stackString += "," + str(applicationProtocol) + "]"
        logger.debug("Connection made on spawned port {} for stack {} {}:{} -> {}:{}".format(spawnTcpPort, stackString, source, sourcePort, destination, destinationPort))
        self._dataProtocols[spawnTcpPort].setPlaygroundConnectionInfo(stackProtocol, applicationProtocol, 
                                                                      source, sourcePort, 
                                                                      destination, destinationPort)
        
        self._connectionSpawn[connectionId] = self._connectionSpawn.get(connectionId, []) + [self._dataProtocols[spawnTcpPort]]
        self._connectionBackptr[self._dataProtocols[spawnTcpPort]] = connectionId
        
        # done with these. Delete the data
        
        del self._dataProtocols[spawnTcpPort]
        del self._connectionData[spawnTcpPort]

        # notify that a new connection is received
        self._conditionConnections.notify()
        
    def dataConnectionClosed(self, dataProtocol, spawnTcpPort):
        logger.debug("Connection closed for spawned port {}".format(spawnTcpPort))

#        logger.debug("Connection closed on spawned port {} for source and destination {}:{} -> {}:{}".format(spawnTcpPort, source, sourcePort, destination, destinationPort))
        if spawnTcpPort in self._dataProtocols:
            del self._dataProtocols[spawnTcpPort]
        if spawnTcpPort in self._connectionData:
            del self._connectionData[spawnTcpPort]
        if dataProtocol in self._connectionBackptr:
            connectionId = self._connectionBackptr[dataProtocol]
            del self._connectionBackptr[dataProtocol]
            self._connectionSpawn[connectionId].remove(dataProtocol)

    async def waitForConnections(self, connectionId, n=1):
        # primarily used in awaiting the complete connection from an outbound connection
        if not connectionId in self._connectionSpawn:
            self._connectionSpawn[connectionId] = []
        
        # now wait for the list to be big enough
        predicate = lambda: len(self._connectionSpawn[connectionId]) >= n
        await self._conditionConnections.awaitCondition(predicate)
        return self._connectionSpawn[connectionId]
        
    def getConnections(self, connectionId):
        return self._connectionSpawn.get(connectionId, [])
        
class PlaygroundServer:
    class FakePlaygroundSocket:
        def __init__(self, explicitName=None):
            self.explicitName = explicitName
            self.close = lambda *args: None
            self.connect = lambda *args: None
            self.recv = lambda *args: None
            self.send = lambda *args: None
        def getpeername(self):
            return ("",0)
        def gethostname(self): 
            if self.explicitName: return self.explicitName
            return ("<Unnamed Server Socket>",0)
        
    def __init__(self, connectionId, address, port, getConnections, closeServer):
        self._connectionId = connectionId
        self._controlSocket = self.FakePlaygroundSocket(explicitName=(address, port))
        self._closed = False
        self._getConnections = getConnections
        self._closeServer = closeServer
        # Doesn't do anything yet or support any sockets
        
    def close(self):
        if self._closed: return
        logger.debug("Playground server for connection {} calling close".format(self._connectionId))
        self._closed = True
        self._closeServer(self._connectionId)
        connections = self._getConnections(self._connectionId)
        logger.debug("Closing {} connections for server with id {}".format(len(connections), self._connectionId))
        for conn in connections:
            if conn.transport: conn.transport.close()
        
    def __getattribute__(self, attr):
        if attr == "sockets":
            sockets = [self._controlSocket]
            connections = self._getConnections(self._connectionId)
            for connection in connections:
                sockets.append(self.FakePlaygroundSocket(connection))
            return sockets
        return super().__getattribute__(attr)
        
class PlaygroundConnector:
    def __init__(self, vnicService=None, protocolStack=None, callbackAddress="127.0.0.1", callbackPort=0):
        if isinstance(protocolStack, tuple):
            if len(protocolStack) != 2: 
                raise Exception("Protocol Stack is a factory or a factory pair")
            self._stack = protocolStack
        else:
            self._stack = protocolStack, protocolStack
        self._vnicService = vnicService
        self._callbackService = CallbackService(callbackAddress, callbackPort, self._stack)
        self._vnicConnections = {}
        self._ready = False
        self._trace = traceback.extract_stack()
        self._module = self._trace[-2].filename
        
        if not vnicService:
            self._vnicService = StandardVnicService()
            
        self._protocolReadyCondition = SimpleCondition()
        
    def getClientStackFactory(self):
        return self._stack[0]
    
    def getServerStackFactory(self):
        return self._stack[1]
    
    def getModule(self):
        return self._module
        
    async def create_callback_service(self, factory):
        callbackAddress, callbackPort = self._callbackService.location()
        coro = asyncio.get_event_loop().create_server(factory, host=callbackAddress, port=callbackPort)
        server = await coro
        servingPort = server.sockets[0].getsockname()[1]
        self._callbackService._callbackPort = servingPort
        self._ready = True
        
    async def create_playground_connection(self, protocolFactory, destination, destinationPort, vnicName="default", cbPort=0, timeout=60):
        startTime = time.time()
        
        logger.info("Create playground connection to {}:{}".format(destination, destinationPort))
        if not self._ready:
            await self.create_callback_service(lambda: VNICCallbackProtocol(self._callbackService))#.buildConnectDataProtocol)
        if destination == "localhost":
            destination = self._vnicService.getVnicPlaygroundAddress(self._vnicService.getDefaultVnic())
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
        if not location in self._vnicConnections:
            logger.debug("No control conenction to VNIC {} yet. Connecting".format(location))
            self._vnicConnections[location] = VNICSocketControlClientProtocol(self._callbackService)
            coro = asyncio.get_event_loop().create_connection(lambda: self._vnicConnections[location], vnicAddr, vnicPort)
            await coro
            logger.debug("Control protocol connected.")

        controlTime = time.time()
        controlProtocol = self._vnicConnections[location]
        future = controlProtocol.connect(destination, destinationPort, protocolFactory)
        logger.debug("Awaiting outbound connection to complete")
        try:
            connectionId, port = await asyncio.wait_for(future, timeout)
            logger.debug("Connection complete. Outbound port is {} for connection {}".format(port, connectionId))
        except TimeoutError:
            raise Exception("Could not connect to {}:{} in {} seconds.".format(destination, destinationPort, timeout))
        callbackTime = time.time()
        logger.debug("Complete playground connection. Total Time: {} (Control {}, callback {})".format(callbackTime-startTime,
                                                                                                       controlTime-startTime, 
                                                                                                       callbackTime-controlTime))
        connections = await self._callbackService.waitForConnections(connectionId, n=1)
        if len(connections) != 1:
            raise Exception("VNIC Unexpected Error connecting to {}:{} (ID {}). Should be one connection, but got {})!".format(destination, 
                                                                                                                               destinationPort,
                                                                                                                               connectionId, 
                                                                                                                               len(connections)))
            
        playgroundProtocol = connections[0]
        while isinstance(playgroundProtocol, StackingProtocol) and playgroundProtocol.higherProtocol():
            playgroundProtocol = playgroundProtocol.higherProtocol()
        
        connectionMadeCoro = connectionMadeObserver.awaitConnection(playgroundProtocol)
        await asyncio.wait_for(connectionMadeCoro, timeout)
            
        return playgroundProtocol.transport, playgroundProtocol
        
    async def create_playground_server(self, protocolFactory, port, host="default", vnicName="default", cbPort=0):
        if not self._ready:
            await self.create_callback_service(lambda: VNICCallbackProtocol(self._callbackService))
            #await self.create_callback_service(self._callbackService.buildListenDataProtocol)
            
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
        
        if not vnicAddr or not vnicPort:
            raise Exception("Invalid VNIC address and/or port")
        
        if not location in self._vnicConnections:
            logger.debug("No control conenction to VNIC {} yet. Connecting".format(location))
            self._vnicConnections[location] = VNICSocketControlClientProtocol(self._callbackService)
            coro = asyncio.get_event_loop().create_connection(lambda: self._vnicConnections[location], vnicAddr, vnicPort)
            await coro
            logger.debug("Control protocol connected.")
        
        controlProtocol = self._vnicConnections[location]
        future = controlProtocol.listen(port, protocolFactory)
        logger.debug("Awaiting listening to port {} to complete".format(port))
        try:
            connectionId, port = await asyncio.wait_for(future, 30.0)
            logger.debug("Connection complete. Listening port is {}".format(port))
        except TimeoutError:
            raise Exception("Could not open listening port {} in {} seconds.".format(port, 30.0))
        
        server = PlaygroundServer(connectionId, host, port, self._callbackService.getConnections, controlProtocol.close)
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

class NoSuchPlaygroundConnector(Exception):
    def __init__(self, connectorName):
        super().__init__("No such playground connector {}".format(connectorName))

class PlaygroundConnectorService:
    
    @classmethod
    def InitializeConfigModule(cls, location, overwrite=False):
        connectorLocation = os.path.join(location, "connectors")
        if not os.path.exists(connectorLocation):
            os.mkdir(connectorLocation)
            
    def __init__(self):
        self._connectors = {"default":PlaygroundConnector()}
        self._loaded = False
    
    def reloadConnectors(self, force=False):
        if self._loaded and not force: return
        
        configPath = Configure.CurrentPath()
        connectorsLocation = os.path.join(configPath, "connectors")
        connectorsInitPath = os.path.join(connectorsLocation, "__init__.py")
        
        oldPath = sys.path
        if configPath not in sys.path:
            sys.path.insert(0, configPath)
        if not os.path.exists(connectorsInitPath):
            with open(connectorsInitPath, "w+") as f:
                f.write("#dummy init for connectors module")
                
        for pathName in os.listdir(connectorsLocation):
            pathName = os.path.join(connectorsLocation, pathName)
            moduleName = os.path.basename(pathName)
            if os.path.exists(os.path.join(pathName, "__init__.py")):
                dottedName = "connectors.{}".format(moduleName)
                with PacketDefinitionSilo():
                    if dottedName in sys.modules:
                        #TODO: Test if this even works.
                        importlib.reload(sys.modules[dottedName])
                    else:
                        importlib.import_module(dottedName)
        sys.path = oldPath
        self._loaded = True
        #    print("Loading module {}".format(pathName))
        #    self._loadConnectorModule(os.path.join(connectorLocation, pathName))
    
    def getConnector(self, connectorName="default"):
        self.reloadConnectors()
        if connectorName not in self._connectors:
            raise NoSuchPlaygroundConnector(connectorName)
        return self._connectors[connectorName]
    
    def setConnector(self, connectorName, connector):
        self._connectors[connectorName] = connector
ConnectorService = PlaygroundConnectorService()


#Asyncio Like Adapter Interface
def create_server(protocol_factory, host=None, port=None, family=None, *args, **kargs):
    if host == None: host = "default"
    if port == None: raise Exception("Playground create_server cannot have a None port")
    if args or kargs:
        raise Exception("Playground's create_server does not support any arguments other than host, port, and family")
    if family == None and host is not None and "://" in host:
        family, host = host.split("://")
    elif family == None:
        family = "default"
    return playground.getConnector(family).create_playground_server(protocol_factory, host=host, port=port)
    
def create_connection(protocol_factory, host, port, family=None, *args, **kargs):
    if args or kargs:
        raise Exception("Playground's create_connection does not support any arguments other than host, port, and family")
    if family == None and host is not None and "://" in host:
        family, host = host.split("://")
    elif family == None:
        family = "default"
    return playground.getConnector(family).create_playground_connection(protocol_factory, host, port)