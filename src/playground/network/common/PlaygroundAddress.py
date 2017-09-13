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
    def IsValidAddressString(cls, addressString, out_addressParts=None):
        """
        Checks if a string is a valid address. Can vary slightly from subclass
        to subclass because it relies on ConvertStringPart to check that each
        part can be successfully converted.
        
        But all addresses must be of the form a.b.c.d.
        
        The optional out_addressParts must be a list or support an append method.
        It takes converted parts created during the check. If the check returns
        false, this variable will still contain all the parts that were successfully
        converted.
        """
        if type(addressString) != str:
            return False
        parts = addressString.split(".")
        if len(parts) != 4:
            return False
        try:
            parts = [cls.ConvertStringPart(x) for x in parts]
            if out_addressParts != None:
                for part in parts:
                    out_addressParts.append(part)
            return True
        except:
            return False
    
    @classmethod
    def FromString(cls, addressString):
        addressParts = []
        if not cls.IsValidAddressString(addressString, out_addressParts=addressParts):
            raise InvalidPlaygroundAddress("Bad address {}. Must be of form a.b.c.d".format(addressString))
        
        return cls(*addressParts)
    
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
    def RootBlock(cls):
        return cls.FromString("*.*.*.*")
        
    @classmethod
    def ConvertStringPart(cls, part):
        return part == "*" and part or int(part)
    
    def __init__(self, zone="*", network="*", device="*", index="*"):
        super().__init__(zone, network, device, index)
        self.validate(raiseException=True)
        specifiedParts = []
        for part in self.toParts():
            if part == "*": break
            specifiedParts.append(str(part))
        self._prefixString = ".".join(specifiedParts)
        
    def prefixString(self):
        return self._prefixString
        
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
        
    def getParentBlock(self):
        blockParts = self.toParts()
        if "*" in blockParts:
            currentBlock = blockParts.index("*")
        else:
            currentBlock = len(blockParts)
        nextBlock = currentBlock - 1
        if nextBlock < 0:
            # We are already *.*.*.*. There is no parent block
            return None
        blockParts[nextBlock] = "*"
        return PlaygroundAddressBlock(*blockParts)       

class InvalidPlaygroundAddress(Exception): pass

