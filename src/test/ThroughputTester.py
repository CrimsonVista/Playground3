'''
Created on Oct 3, 2017

@author: seth_
'''

from playground.network.packet.PacketType import PacketType
from playground.network.packet.fieldtypes import BUFFER
import playground
import sys, asyncio, hashlib, os, time

def hash(data):
    return hashlib.sha1(data).hexdigest()

class TestMessagePacket(PacketType):
    DEFINITION_IDENTIFIER = "testpacket"
    DEFINITION_VERSION = "1.0"
    
    FIELDS = [("data",BUFFER)]

class TestConfig:
    def __init__(self, p1Tx, p2Tx, **options):
        self._pData = {
            "p1": ["peer1", p1Tx, p2Tx, 0, 0.0, 0.0],
            "p2": ["peer2", p2Tx, p1Tx, 0, 0.0, 0.0]
            }
        self.testRecord = []
        self._doneCount = 0
        self._closedCount = 0
        self._options = options
        self._lastSignal = 0
    
    def recordTxStart(self, p):
        self._pData[p][4] = time.time()
        if self._lastSignal == 0: # beginning
            asyncio.get_event_loop().call_later(1,self.waitClose)
        self._lastSignal = time.time()

    def waitClose(self):
        now = time.time()
        if now - self._lastSignal > 30.0:
            p1, p2 = self._pData.keys()
            p1.transport.close()
            p2.transport.close()

    def recordSignal(self, p):
        self._lastSignal = time.time()

    def recordRxFinish(self, p):
        self._pData[p][5] = time.time()
        self._doneCount += 1
        if self._doneCount == len(self._pData):
            p1, p2 = self._pData.keys()
            p1.transport.close()
            p2.transport.close()

    def getTestThroughput(self, p):
        bytesTotal = 0
        for t in self._pData[p][1]:
            bytesTotal += len(t)
        # bad. What if there were more than 2?
        p1, p2 = list(self._pData.keys())
        if p == p1: other = p2
        else: other = p1
        return bytesTotal, self._pData[other][5]-self._pData[p][4]
        
    def getTestingProtocols(self):
        return tuple(self._pData.keys())
        
    def getOption(self, key, default):
        return self._options.get(key, default)
        
    def getPeerName(self, p):
        return self._pData.get(p, ["unknown"])[0]
    
    def getTestResults(self, p):
        expectedRxCount = len(self._pData[p][2])
        correctRxCount = self._pData[p][3]
        return (correctRxCount, expectedRxCount)
    
    def setPeerSuccesssfulRx(self, p):
        self._pData[p][3] += 1
        
    def getTxTransmissions(self, p):
        return self._pData[p][1][:]
        
    def getExpectedRxTransmissions(self, p):
        return self._pData[p][2][:]
        
    def recordConnect(self, p):
        if "p1" in self._pData:
            self._pData[p] = self._pData["p1"]
            del self._pData["p1"]
        elif "p2" in self._pData:
            self._pData[p] = self._pData["p2"]
            del self._pData["p2"]
        self._pData[p][4] = time.time()
        self.testRecord.append("{} ({}) received connection from {}".format(self.getPeerName(p),
                                                                        p.transport.get_extra_info("hostname"),
                                                                        p.transport.get_extra_info("peername")))
        
    def recordTx(self, p, tx):
        self.testRecord.append("{} transmitting data with len {} and hash {}".format(self.getPeerName(p),
                                                                                     len(tx),
                                                                                     hash(tx)))
        
    def recordRx(self, p, actualRx, expectedRx):
        actualHash = hash(actualRx)
        expectedHash = hash(expectedRx)
        self.testRecord.append("{} received data with hash {}. Expected hash {}".format(self.getPeerName(p),
                                                                                        actualHash,
                                                                                        expectedHash))
        if actualHash == expectedHash:
            self.setPeerSuccesssfulRx(p)
            
    def recordClose(self, p, reason=None):
        self.testRecord.append("{} closing because {}.".format(self.getPeerName(p), reason))
        self._closedCount += 1
        if self._closedCount == 2:
            self.testRecord.append("Test Complete")
            asyncio.get_event_loop().call_later(1, asyncio.get_event_loop().stop)
            
class AutoDataTestConfig(TestConfig):
    def __init__(self, minSize=1, maxSize=100000, count=10, **options):
        txData = []
        step = int((maxSize-minSize)/count)
        for i in range(count):
            txSize = minSize + (i*step)
            txData.append(os.urandom(txSize))
        super().__init__(txData, txData, **options)

class TestProtocol(asyncio.Protocol):
    """
    This can be both a client and server. Both behave identically
    """
    def __init__(self, testConfig):
        self._config = testConfig
        self._deserializer = TestMessagePacket.Deserializer()
        self._noProgressCount = 0
        self._tx = []
        self._rx = []

    def waitClose(self, lastRxCount):
        if not self._rx or self._noProgressCount == 30:
            self.transport.close()
            return
        
        if self._rx:
            if len(self._rx) == lastRxCount:
                self._noProgressCount += 1
                if self._noProgressCount == 30:
                    self.transport.close()
                    return
            else:
                self._noProgressCount = 0
        asyncio.get_event_loop().call_later(2,self.waitClose, len(self._rx))
        
    def transmit(self):
        if not self._tx:
        #    asyncio.get_event_loop().call_later(1,self.waitClose, len(self._rx))
            return
        self._config.recordTx(self, self._tx[0])
        testPacket = TestMessagePacket(data=self._tx.pop(0))
        self.transport.write(testPacket.__serialize__())
        txDelay = self._config.getOption("txdelay",0)
        asyncio.get_event_loop().call_later(txDelay, self.transmit)
        
    def connection_made(self, transport):
        self.transport=transport
        self._config.recordConnect(self)
        
        # We're not registered until we connect. So don't try to get these in
        # constructor
        self._tx = testConfig.getTxTransmissions(self)
        self._rx = testConfig.getExpectedRxTransmissions(self)
        self._config.recordTxStart(self)
        self.transmit()
        
    def data_received(self, data):
        self._deserializer.update(data)
        self._config.recordSignal(self)
        for packet in self._deserializer.nextPackets():
            print(self,"GOT TEST PACKET")
            if self._rx:
                expectedRx = self._rx.pop(0)
            else:
                expectedRx = b"<NO TRANSMISSION EXPECTED>"
                asyncio.get_event_loop().stop()
            
            self._config.recordRx(self, packet.data, expectedRx)
            if not self._rx:
                self._config.recordRxFinish(self)
        
    def connection_lost(self, reason):
        print("connection lost", reason)
        self.transport = None
        self._config.recordClose(self, reason)
        
        asyncio.get_event_loop().call_later(1, asyncio.get_event_loop().stop)


if __name__=="__main__":
    """
    Network Modes:
      localhost (default): Uses a virtual switch
      Dummy: Uses no network  connections at all
      
    Test Modes:
      Client - client is testing stack
      Server - server is testing stack
    """
    echoArgs = {"--testing-stack": "lab1",
                "--reference-stack": "instructor_lab1",
                "--network": "localhost"}
    
    args= sys.argv[1:]
    i = 0
    for arg in args:
        if arg.startswith("-"):
            if "=" in arg:
                k,v = arg.split("=")
                echoArgs[k]=v
            elif arg in echoArgs:
                echoArgs[arg] = True
        else:
            echoArgs[i] = arg
            i+=1
    
    #if not 0 in echoArgs:
    #    sys.exit(USAGE)

    mode = echoArgs[0]
    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=True)
    
    from playground.common.logging import EnablePresetLogging, PRESET_DEBUG
    EnablePresetLogging(PRESET_DEBUG)
    
    if mode == "client":
        print("get testing stack")
        clientConnector = playground.getConnector(echoArgs["--testing-stack"])
        print("get ref stack")
        serverConnector = playground.getConnector(echoArgs["--reference-stack"])
    elif mode == "server":
        serverConnector = playground.getConnector(echoArgs["--testing-stack"])
        clientConnector = playground.getConnector(echoArgs["--reference-stack"])

    
    testConfig = AutoDataTestConfig()
        
    coro = serverConnector.create_playground_server(lambda: TestProtocol(testConfig), 202)
    server = loop.run_until_complete(coro)
    print("Throughput Server Started at {}".format(server.sockets[0].gethostname()))
    
    coro = clientConnector.create_playground_connection(lambda: TestProtocol(testConfig), "localhost", 202)
    asyncio.ensure_future(coro)
    asyncio.get_event_loop().run_forever()
    asyncio.get_event_loop().close()
    print("Test finished. Results :")
    # testing protocols are p1 and p2. But p1 should always connect first...
    # ... we hope?
    client, server = testConfig.getTestingProtocols()
    print(client)
    print("\tClient correctly handled {} transmissions".format(testConfig.getTestResults(client)))
    print("\tServer correctly handled {} transmissions".format(testConfig.getTestResults(server)))
    print("\tDETAILS:")
    for data in testConfig.testRecord:
        print("\t\t",data)
    clientBytes, clientTime = testConfig.getTestThroughput(client)
    serverBytes, serverTime = testConfig.getTestThroughput(server)
    print("\tClient Throughput {} B/{} s = {} B/s".format(clientBytes, clientTime, clientBytes/clientTime))
    print("\tServer Throughput {} B/{} s = {} B/s".format(serverBytes, serverTime, serverBytes/serverTime))
        
    #transport, protocol = loop.run_until_complete(coro)
    #    print("Echo Client Connected. Starting UI t:{}. p:{}".format(transport, protocol))
    #control.connect(protocol)
    
