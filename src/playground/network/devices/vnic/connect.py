
class PlaygroundConnector:
    def __init__(self, protocolStack, vnicService):
        self._stack = protocolStack
        self._vnicService = vnicService
        
    def create_playground_connection(self, protocolFactory, destination, destinationPort, vnicName="default", cbPort=0):
        if not vnicName in self._vnicService:
            raise Exception("VNIC '{}' is not currently available.".format(vnicName))
            
        
        
    def create_playground_server(self, protocolFactory, sourcePort, vnicName="default", cbPort=0):
        if not vnicName in self._vnicService:
            raise Exception("VNIC '{}' is not currently available.".format(vnicName))