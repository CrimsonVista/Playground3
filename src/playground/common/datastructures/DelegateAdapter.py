
class DelegateAdapter:
    """
    The purpose of this class is to allow simple a simple
    adapter class that defers almost all operations to a
    delegate. Only attributes (functions and variables)
    specifically identified as provided by the adapter class.
    
    NOTE that methods like __getitem__ may not work correctly
    because of how python optimizes them.
    """
    
    ADAPTED_ATTRIBUTES = []
    REQUIRED_ATTRIBUTES = ["_delegate", "__class__"]
    
    def __init__(self, delegate):
        self._delegate = delegate
    
    def __getattribute__(self, attr):
        if attr in DelegateAdapter.REQUIRED_ATTRIBUTES:
            return super().__getattribute__(attr)
        elif attr in self.__class__.ADAPTED_ATTRIBUTES:
            return super().__getattribute__(attr)
        else:
            return self._delegate.__getattribute__(attr)
            
def basicUnitTest():
    class TestClass:
        def __init__(self):
            self._var1 = "var1"
            self._var2 = "var2"
            
        def operation1(self):
            return "operation1"
            
        def operation2(self):
            return "operation2"
            
    class TestClassAdapter(DelegateAdapter):
        ADAPTED_ATTRIBUTES = ["_aVar1", "aOperation1", "operation2"]
        def __init__(self, delegate):
            super().__init__(delegate)
            self._aVar1 = "aVar1"
            
        def aOperation1(self):
            return "aOperation1"
            
        def operation2(self):
            return "replaced_operation2"
    
    testInstance = TestClass()
    adapted = TestClassAdapter(testInstance)
    
    assert adapted._var1 == testInstance._var1
    assert adapted._var2 == testInstance._var2
    assert adapted.operation1 == testInstance.operation1
    assert adapted.operation2 != testInstance.operation2
    assert adapted._aVar1 == "aVar1"
    assert adapted.aOperation1() == "aOperation1"
    assert adapted.operation2() == "replaced_operation2"
    
    
if __name__=="__main__":
    basicUnitTest()