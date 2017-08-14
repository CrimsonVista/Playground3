
from .PacketFieldType import PacketFieldType

class ComplexFieldType(PacketFieldType):
    def __init__(self, dataType, **attributes):
        super().__init__(**attributes)
        self._dataType = dataType
        
    def dataType(self):
        return self._dataType
        
    def initializeData(self):
        if not self._data:
            self._data = self._dataType()
        # TODO: Warnings, Errors, etc?
        
    def setData(self, data):
        if not isinstance(data, self._dataType):
            raise ValueError("Invalid data for ComplexFieldType. Must be of type {}.".format(self._dataType))
        super().setData(data)
        
    def createInstance(self):
        cls = self.__class__
        instance = cls(self._dataType, **self._attributes)
        return instance

