
from .PacketFieldType import PacketFieldType
from .attributes import StandardDescriptors

class Uint(PacketFieldType):
    DEFAULT_SIZE = 4
    
    def setData(self, data):
        try:
            self._data = int(data)
        except Exception as e:
            raise ValueError("{} is not a uint".format(data))
        if self._data < 0:
            raise ValueError("Uint's cannot be negative")
        size = self.getAttribute(StandardDescriptors.Size, self.DEFAULT_SIZE)
        if self._data >= 2**(size*8):
            raise ValueError("{} exceeds Uint's {} byte size.".format(self._data, size) )