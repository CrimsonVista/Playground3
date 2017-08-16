

class PacketFields:
    FIELDS = []
    
    def __init__(self, **fieldInitialization):
        self._fields = {}
        for fieldName, fieldType in self.FIELDS:
            self._fields[fieldName] = fieldType.CreateInstance(fieldType)
            if fieldName in fieldInitialization:
                self._fields[fieldName].setData(fieldInitialization[fieldName])
                
    def __getrawfield__(self, field):
        return self._fields[field]
                
    def __getattribute__(self, field):
        if not field.startswith("_") and field in self._fields:
            return self._fields[field].data()
        return object.__getattribute__(self, field)

    def __setattr__(self, field, value):
        if not field.startswith("_") and field in self._fields:
            self._fields[field].setData(value)
        else: object.__setattr__(self, field, value)