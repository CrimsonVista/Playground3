'''
Created on August 19, 2017
Copied and adapted from Playground 2.0
Original File Date: Nov 25, 2013

@author: sethjn
'''
import random

class PlaygroundAddressType:
    @classmethod
    def ConvertStringPart(cls, part):
        return part
    
    @classmethod
    def FromString(cls, addressString):
        if type(addressString) != str:
            raise InvalidPlaygroundAddress("Address string not of type string")
        
        parts = addressString.split(".")
        if len(parts) != 4:
            raise InvalidPlaygroundAddress("Address string not of form a.b.c.d")
        
        parts = list(map(cls.ConvertStringPart, parts))
        
        return cls(parts[0], parts[1], parts[2], parts[3])
    
    def __init__(self, zone, network, device, index):
        self._zone = zone
        self._network = network
        self._device = device
        self._index = index
        self._addressString = ".".join(str(p) for p in self.toParts())
        
    def zone(self): return self._zone
    def network(self): return self._network
    def device(self): return self._device
    def index(self): return self._index
    
    def toString(self):
        return self._addressString

    def toParts(self):
        return [self._zone, self._network, self._device, self._index]
    
    def __repr__(self):
        return self.toString()
    
    def __str__(self):
        return self.toString()
    
    def __eq__(self, other):
        if isinstance(other, PlaygroundAddressType):
            return (self._zone == other._zone and 
                    self._network == other._network and
                    self._device == other._device and
                    self._index == other._index)
        elif isinstance(other, str):
            return self._addressString == other
        return False
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __hash__(self):
        return self._addressString.__hash__()
    
    def __getitem__(self, i):
        if i < 0 or i > 3:
            raise IndexError("Playground Addresses have 4 parts")
        if i == 0: return self._zone
        if i == 1: return self._network
        if i == 2: return self._device
        if i == 3: return self._index

class PlaygroundAddress(PlaygroundAddressType):
    @classmethod
    def ConvertStringPart(cls, part):
        return int(part)
    
    def __init__(self, zone, network, device, index):
        super().__init__(zone, network, device, index)
        
        self.validate(raiseException=True)
        
    def validate(self, raiseException=False):
        for part in self.toParts():
            if not type(part) == int or part < 0:
                raise InvalidPlaygroundAddress("Address parts must be positive integers")
    
class PlaygroundAddressBlock(PlaygroundAddressType):
    @classmethod
    def ConvertStringPart(cls, part):
        return part == "*" and part or int(part)
    
    def __init__(self, zone="*", network="*", device="*", index="*"):
        super().__init__(zone, network, device, index)
        self.validate(raiseException=True)
        
    def validate(self, raiseException=False):
        for part in self.toParts():
            if not (part == "*" or (type(part) == int and part >=0)): 
                if raiseException:
                    raise InvalidPlaygroundAddress("Invalid part %s" % part)
                return False
        return True
            
    def spawnAddress(self, maxInt=((2**16)-1), addrType=PlaygroundAddress):
        addrParts = []
        for part in self.toParts():
            if part == "*":
                addrParts.append(random.randint(0, maxInt))
            else:
                addrParts.append(part)
        return addrType(*addrParts)
        
    def isParentBlock(self, address):
        blockParts = self.toParts()
        addrParts  = address.toParts()
        if len(addrParts) > len(blockParts):
            return False
        for i in range(len(blockParts)):
            if blockParts[i] != "*" and blockParts[i] != addrParts[i]:
                return False
        return True

class InvalidPlaygroundAddress(Exception): pass

