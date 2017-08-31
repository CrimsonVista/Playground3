

class PortKey:
    def __init__(self, source, sourcePort, destination, destinationPort):
        self.source = source
        self.sourcePort = sourcePort
        self.destination = destination
        self.destinationPort = destinationPort
        
    def inverseKey(self):
        return PortKey(self.destination, self.destinationPort, self.source, self.sourcePort)
        
    def sourceOnlyKey(self):
        return PortKey(self.source, self.sourcePort, None, None)
        
    def destinationOnlyKey(self):
        return PortKey(None, None, self.destination, self.destinationPort)
        
    def __eq__(self, cmp):
        if isinstance(cmp, PortKey):
            cmpSource, cmpSourcePort = cmp.source, cmp.sourcePort
            cmpDestination, cmpDestinationPort = cmp.destination, cmp.destinationPort
        elif hasattr(cmp, "__iter__"):
            cmpSource, cmpSourcePort, cmpDestination, cmpDestinationPort = cmp
        else:
            raise ValueError("Cannot compare {} and {}".format(self, cmp))
        return (self.source == cmpSource and self.sourcePort == cmpSourcePort and
                self.destination == cmpDestination and self.destinationPort == cmpDestinationPort)
                    
    def __hash__(self):
        return hash((self.source, self.sourcePort, self.destination, self.destinationPort))
        
    def __repr__(self):
        return "Port ({}:{}) <-> ({}:{})".format(self.source, self.sourcePort, self.destination, self.destinationPort)