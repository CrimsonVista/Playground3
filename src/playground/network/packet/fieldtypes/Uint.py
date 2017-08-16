
from .PacketFieldType import PacketFieldType

class Uint(PacketFieldType):
    def _setTypedData(self, data):  
        try:
            self._data = int(data)
        except Exception as e:
            raise ValueError("{} is not a uint".format(data))
        if self._data < 0:
            raise ValueError("Uint's cannot be negative")