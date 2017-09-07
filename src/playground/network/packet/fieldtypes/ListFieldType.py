from .ComplexFieldType import ComplexFieldType, PacketFieldType

class ListFieldType(ComplexFieldType):
    def __init__(self, listDataType, attributes=None):
        super().__init__(listDataType, attributes)
        self._dataList = []
        
    def _setTypedData(self, data):
        if isinstance(data, ListFieldType):
            if data._data == self.UNSET:
                self._data = self.UNSET
                return
                
            # CREATES a shallow copy. The lists are independent, and fields that copy on .data()
            # are copied. But fields, like List itself, that do not copy on .data() are shared.
            if self != data:
                self._dataList = []
                for otherField in data._dataList:
                    self.append(otherField.data())        
        elif isinstance(data, list):
            self._dataList = []
            for dataElement in data:
                self.append(dataElement)
        else:
            raise ValueError("Cannot set a ListFieldType to {}".data)
        # The real data is stored in _dataList. But we use _data to determine
        # if we're "null" (UNSET). So set it to some non UNSET value.
        self._data = len(self._dataList)
            
    def data(self):
        if self._data == self.UNSET:
            return self.UNSET
        return self
        
    def initializeData(self):
        pass # no need. Done in constructor
        
    def append(self, data):
        # append initializes data.
        
        self._dataList.append(self.dataType()())
        self._dataList[-1].setData(data)
        self._data = len(self._dataList)
        
    def pop(self, index=-1):
        self._dataList.pop(index)
        
    def __call__(self, newAttributes=None):
        clonedList = super().__call__(newAttributes)
        clonedList.setData(self) # copy elements
        return clonedList
        
    def __contains__(self, data):
        for field in self._dataList:
            if field.data() == data: return True
        return False
        
    def __eq__(self, otherList):
        """
        Normally, the PacketFieldType's __eq__ is sufficient.
        But because we don't actually store data in _data, we
        need to do a different kind of comparison.
        """
        if isinstance(otherList, ListFieldType) or isinstance(otherList, list):
            if len(self) == len(otherList):
                for i in range(len(self)):
                    if self[i] != otherList[i]:
                        return False
                return True
        return False
        
    def __len__(self):
        return len(self._dataList)
        
    def __getrawitem__(self, index):
        return self._dataList[index]
        
    def __getitem__(self, index):
        if isinstance(index, slice):
            subList = self._dataList[index]
            return [field.data() for field in subList]
        return self._dataList[index].data()
        
    def __setitem__(self, index, value):
        self._dataList[index].setData(value)
        
    def __iter__(self):
        for field in self._dataList:
            yield field.data()