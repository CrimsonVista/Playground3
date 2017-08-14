from . import CustomConstant

class ReturnOrientedGenerator(object):
    GENERATOR_RUNNING = CustomConstant(strValue="Generator still running", boolValue=False)
    def __init__(self, generator):
        self._generator = generator
        self._result = self.GENERATOR_RUNNING
        
    def __iter__(self):
        self._result = yield from self._generator
        
    def result(self):
        return self._result