
import io
from collections import namedtuple
from itertools import islice

from playground.common import CustomConstant

class UpdateableReaderMixin(object):
    def update(self, newData):
        raise NotImplemented("The 'update' method must be implemented in subclasses.")
        
    def peek(self, size=-1):
        raise NotImplemented("The 'update' method must be implemented in subclasses.")
        
    def available(self):
        raise NotImplemented("The 'peek' method must be implemented in subclasses.")
        
class UpdateableBytesIO(io.BytesIO, UpdateableReaderMixin):
    def update(self, newData):
        beforeWritePos = self.tell()
        self.seek(0, io.SEEK_END)
        self.write(newData)
        self.seek(beforeWritePos)
        
    def peek(self, size=-1):
        if not size or size < 0:
            size = self.available()
            
        return self.getbuffer()[self.tell():self.available()].tobytes()
        
    def available(self):
        cur = self.tell()
        end = self.seek(0, io.SEEK_END)
        self.seek(cur)
        return end-cur

class MinimumCopyingStreamIO(io.RawIOBase, UpdateableReaderMixin):
    
    """
    This class is designed to be very high performance
    when working with incoming streams of data. It will
    not copy except when absolutely necessary. It can
    be constructed seekable or non-seekable. In non-seekable
    mode, data is released when no longer used.
    
    Critically, client code must assume that buffers passed
    to MinimumCopyingStreamIO will use the passed-in buffer,
    and client code should not modify said buffer without
    expecting those changes to be visible in the stream.
    
    Note that this class supports all of the methods that BufferedReader. 
    But it does not inherit that class, because it does not wrap a raw object.
    It also not inherit BufferedWriter, nor is it "writeable". However,
    it does have an"update" method. The update method appends
    a new buffer at the end, representing new stream data.
    """
    
    
    def __init__(self, initialBuffer=None, seekable=False):
        if initialBuffer == None:
            self.__buffers = []
            self.__bufferPos = []
            self.__streamEnd = 0
        else:
            # We are explicitly NOT using a named buffer here. Named buffers had significantly worse performance
            self.__buffers = [initialBuffer]
            self.__bufferPos = [0]
            self.__streamEnd = len(initialBuffer)
        self.__streamPosition = 0
        
        self.__seekable = seekable
        self.__closed = False
        
    def __calculateBufferAndOffset(self, position):
        if not self.__buffers:
            return (-1, -1)
        if self.__bufferPos[0] > position:
            return (-1, -1)
        for bufferIndex in range(len(self.__buffers)):
            buffer = self.__buffers[bufferIndex]
            bufferPosition = self.__bufferPos[bufferIndex]
            if bufferPosition + len(buffer) > position:
                return bufferIndex, (position - bufferPosition)
        return (-1, -1)
        
    def update(self, newBuffer):
        self.__buffers.append(newBuffer)
        self.__bufferPos.append(self.__streamEnd)
        self.__streamEnd += len(newBuffer)
        
    def close(self):
        # release all buffers
        self.__buffers = []
        self.__bufferPos = []
        self.__closed = True
        
    def __raiseIfClosed(self):
        if self.__closed:
            raise ValueError("Invalid operation on already closed stream")
        
    @property
    def closed(self):
        return self.__closed
        
    def fileno(self):
        raise OSError
        
    def isatty(self):
        return False
        
    def readable(self):
        return True
        
    def peek(self, size=-1):
        bufStartIndex, bufStartOffset = self.__calculateBufferAndOffset(self.__streamPosition)
        if bufStartIndex == -1: return ''
        
        if size == -1:
            if bufStartOffset == 0:
                buffers = self.__buffers[bufStartIndex:]
            else:
                buffers = [self.__buffers[bufStartIndex][bufStartOffset:]] + self.__buffers[bufStartIndex+1:]
            if len(buffers) == 1:
                return buffers[0]
            return b"".join(buffers)
            #b1 = bytearray(self.available())
            #firstBuffer = self.__buffers[bufStartIndex][1]
            #pos = len(firstBuffer)-bufStartIndex
            #b1[0:pos] = firstBuffer[bufStartIndex:]
            #for bufStartPos, buf in self.__buffers[bufStartIndex+1:]:
            #    newPos = len(buf)
            #    b1[pos:newPos]
            #    pos = newPos
            #b1 = self.__buffers[bufStartIndex].buffer[bufStartOffset:]
            # get all remaining buffers
            #bufIndex = bufStartIndex + 1
            #while bufIndex < len(self.__buffers):
            #    b1 = b1 + self.__buffers[bufIndex].buffer
            #    bufIndex += 1
            
        else:
            size = size <= self.available() and size or self.available()
            buffers = [self.__buffers[bufStartIndex][bufStartOffset:bufStartOffset+size]]
            size = size - len(buffers[-1])
            for buffer in self.__buffers:
                if not size: break
                if len(buffer) < size: buffers.append(buffer)
                else: buffers.append(buffer[:size])
                size = size - len(buffers[-1])
            if len(buffers) == 1:
                return buffers[0]
            return b"".join(buffers)
            ## ALG 2
            #b1 = bytearray(size)
            #pos = 0
            #for bufStart, buf in self.__buffers[bufStartIndex:]:
            #    buf = buf[bufStartOffset:bufStartOffset+(size-pos)]
            #    b1[pos:pos+len(buf)] = buf
            #    pos += len(buf)
            #    if pos==size: break
            #    bufStartOffset = 0
            ## ALG 1
            #b1 = self.__buffers[bufStartIndex][1][bufStartOffset:(bufStartOffset+size)]
            #bufIndex = bufStartIndex + 1
            #while len(b1) < size:
            #    if bufIndex >= len(self.__buffers): break
            #    sizeLeft = size-len(b1)
            #    b1 = b1 + self.__buffers[bufIndex][1][:sizeLeft]
            #    bufIndex += 1
        #return b1
        
    def read(self, size=-1):
        readData = self.peek(size)
        self.__streamPosition += len(readData)
        if not self.__seekable:
            bufIndex, bufOffset = self.__calculateBufferAndOffset(self.__streamPosition)
            # release memory if not seekable
            if bufIndex == -1:
                self.__buffers = []
                self.__bufferPos = []
            else:
                self.__buffers = self.__buffers[bufIndex:]
                self.__bufferPos = self.__bufferPos[bufIndex:]
        return readData
                
    def read1(self, size=-1):
        return self.read(size)
        
    def available(self):
        return self.__streamEnd - self.__streamPosition
        
    def seek(self, offset, whence=io.SEEK_SET):
        self.__raiseIfClosed()
        if not self.__seekable:
            raise OSError("Seek not enabled for this stream")
        if whence == io.SEEK_SET:
            if offset < 0:
                raise ValueError("Cannot have a negative absolute seek")
            newStreamPosition = offset
        elif whence == io.SEEK_CUR:
            newStreamPosition = self.__streamPosition + whence
        elif whence == io.SEEK_END:
            if not self.__buffers:
                newStreamPosition = 0
            else:
                newStreamPosition = self.__streamEnd + offset
        self.__streamPosition = newStreamPosition
        
    def tell(self):
        if not self.__seekable:
            raise OSError("Tell not enabled for this stream")
        return self.__streamPosition
        
        
    def writable(self):
        return False
        
    def memsize(self):
        memsize = 0
        for bufferData in self.__buffers:
            memsize += len(bufferData[1])#.buffer)
        return memsize

MINIMUM_COPYING_STRATEGY = CustomConstant(strvalue="Minimum Copying Strategy")
STANDARD_LIB_STRATEGY = CustomConstant(strvalue="Python Standard Library Strategy")
DEFAULT_STRATEGY = STANDARD_LIB_STRATEGY
        
def HighPerformanceStreamIO(initialBuffer=None, strategy=DEFAULT_STRATEGY):
    if strategy == MINIMUM_COPYING_STRATEGY:
        return MinimumCopyingStreamIO(initialBuffer, seekable=False)
    elif strategy == STANDARD_LIB_STRATEGY:
        return UpdateableBytesIO(initialBuffer)
    raise ValueError("Unknown strategy")
        
def BasicUnitTest():
    initialBuffer = b"some initial data"
    #stream = MinimumCopyingStreamIO(initialBuffer, seekable=False)
    stream = UpdateableBytesIO(initialBuffer)
    assert stream.available() == len(initialBuffer)
    assert stream.peek() == initialBuffer
    assert stream.available() == len(initialBuffer)
    assert stream.read() == initialBuffer
    assert stream.available() == 0
    buffer2 = b"this is buffer 2"
    stream.update(buffer2)
    assert stream.available() == len(buffer2)
    buffer3 = b"this is buffer 3"
    stream.update(buffer3)
    assert stream.available() == len(buffer2) + len(buffer3)
    
    halfOf2 = int(len(buffer2)/2)
    readTotal = halfOf2
    assert stream.read(halfOf2) == buffer2[:halfOf2]
    assert stream.available() == (len(buffer2) + len(buffer3) - readTotal)
    
    # Get the rest of buffer 2 and half of buffer 3
    restOf2 = len(buffer2)-halfOf2
    halfOf3 = int(len(buffer3)/2)
    overlapRead = restOf2 + halfOf3
    readTotal += overlapRead
    assert stream.read(overlapRead) == buffer2[halfOf2:] + buffer3[:halfOf3]
    #assert stream.memsize() == len(buffer3)
    assert stream.available() == (len(buffer2) + len(buffer3) - readTotal)
    stream.read()
    #assert stream.memsize() == 0
    
    
def BasicPerformanceTest():
    # As of 2017-08-03, this performance test shows that 
    # the minimum copying class only outperforms the updateable bytes
    # class when dealing with hundreds of 1000000 size'd buffers.
    bufferSizes = [10, 1000, 10000, 1000000]
    bufferCounts = [1, 5, 10, 100]

    
    def streamTest(stream, buffers, readCounts):
        i = 0
        for buffer in buffers:
            stream.update(buffer)
            if stream.available() >= readCounts[i]:
                stream.read(readCounts[i])
                i+=1
        stream.read()
    
    import time
    results = {}
    mcStream = MinimumCopyingStreamIO()
    ubiStream = UpdateableBytesIO()
    for bufferCount in bufferCounts:
        for bufferSize in bufferSizes:
            b0 = b"x"*bufferSize
            buffers = [b0] * bufferCount
            totalRead = bufferSize*bufferCount
            reads = []
            while totalRead > 0:
                reads.append(int(len(b0)/2))
                totalRead = totalRead - reads[-1]
                reads.append(len(b0))
                totalRead = totalRead - reads[-1]
                reads.append(len(b0)+int(len(b0)/2))
                totalRead = totalRead - reads[-1]
            hpReads = reads[:]
            
            startTime = time.time()
            for i in range(20):
                streamTest(ubiStream, buffers, reads)
            endTime = time.time()
            brTime = endTime-startTime
            
            startTime = time.time()
            for i in range(20):
                streamTest(mcStream, buffers, hpReads)
            endTime = time.time()
            hpTime = endTime-startTime
            
            results[(bufferCount, bufferSize)] = (hpTime, brTime)
    for count in bufferCounts:
        for size in bufferSizes:
            hpTime, brTime = results[(count,size)]
            print("buffer count={}, bufferSize={}, mcTime={:f}, ubTime={:f}, improvement={:f}".format(count, size, hpTime, brTime, brTime/hpTime))
    
if __name__=="__main__":
    #BasicPerformanceTest()
    BasicUnitTest()