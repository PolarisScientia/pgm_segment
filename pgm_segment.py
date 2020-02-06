#!/usr/bin/python3

#205 = Unknown
#254 = Free Space
#0 = Occupied Space

#TODO: make constant time access to a given Cell from a set of coordinates (using hash) if existant
#TODO: Change from recursive growth algorithm to an iterative approach because python doesn't have
# tail recursion optimization, therefore stack overflow...
import sys, getopt
import numpy as np

sys.setrecursionlimit(10**6) #bad bandaid for now

#raster = [[]]

class Cell:
    """A data structure with utilities for working with individual pixel cells."""
    def __init__(self, row=-1, col=-1, container=None):
        self.row = row
        self.col = col
        self.container = container

    def setContainer(self, container):
        self.container = container

class Box:
    def __init__(self, topLeft=(-1,-1), botRight=(-1,-1)):
        self.topLeft = topLeft
        self.botRight = botRight

    def area(self):
        dimx = abs(self.botRight[0] - self.topLeft[0] + 1)
        dimy = abs(self.botRight[1] - self.topLeft[1] + 1)
        return dimx*dimy

class Segment:
    """A segmented area from the image file."""
    def __init__(self, segMan, cells=[]):
        self.segMan = segMan
        self.cells = cells
        self.inheritCell(cells)
        self.boundingBox = None
        #print("New Segment,", len(cells))
    
    def setBounds(self):
        bot = right = 0
        top = left = sys.maxsize
        for cell in self.cells:
            top = min(top, cell.row)
            left = min(left, cell.col)
            bot = max(bot, cell.row)
            right = max(right, cell.col)
        self.boundingBox = Box((left, top), (right, bot))

    def size(self, update=1):
        """Returns the square area of a bounding box containing all Cells within the Segment object."""
        if update:
            self.setBounds()
        if not self.boundingBox:
            return 0
        return self.boundingBox.area()

    def inheritCell(self, cells):
        """Make sure the container property of each Cell is set to this Segment object."""
        if type(cells) is Cell:
            cells.setContainer(self)
        elif type(cells) is list:
            for cell in cells:
                if type(cell) is Cell:
                    cell.setContainer(self)

    def addCells(self, cells):
        if type(cells) is Cell:
            self.cells.append(cells)
            #print("Adding cell:", str(cells.row), ",", str(cells.col))
        elif type(cells) is list:
            for cell in cells:
                if type(cell) is Cell:
                    self.cells.append(cell)

    def isContained(self, row, col):
        """Check if the given coordinates lie within the segment."""
        for cell in self.cells: #most naive way possible
            if cell.row == row and cell.col == col:
                return 1
        return 0
    
    def grow(self, origin):
        """Grow a segment recursively by checking like neighbors (Top-Left->Bottom-Right order)."""
        origVal = self.segMan.getVal(origin.row, origin.col)
        for rowmod in range(-1, 2): #-1, 0, 1
            for colmod in range(-1, 2): #-1, 0, 1
                val = self.segMan.getVal(origin.row+rowmod, origin.col+colmod)
                if val == origVal: #matching
                    #check if contained in segment,
                    #we shouldn't have to check other segments because of GIL.
                    if not self.isContained(origin.row+rowmod, origin.col+colmod):
                        #now we should absorb and grow this cell
                        #we can also assume there's no Cell that refers here too.
                        #print("Growth event: ", origin.row+rowmod,",", origin.col+colmod)
                        nCell = Cell(origin.row+rowmod, origin.col+colmod, self)
                        self.addCells(nCell)
                        self.grow(nCell)


class SegmentManager:
    """A manager for individual segments."""
    def __init__(self, raster, segments=[], unknown=205, free=254, occupied=0):
        self.raster = raster
        self.segments = segments
        self.max_row = len(raster)-1
        self.max_col = len(raster[1])-1
        self.unknown = unknown
        self.free = free
        self.occupied = occupied
        self.prunedSegments = []
    
    def printInfo(self):
        i = 1
        for segment in self.segments:
            print("Segment #{}:".format(i),segment.size(),"({},{}) [{}]".format(segment.boundingBox.topLeft, segment.boundingBox.botRight, len(segment.cells)))
            i = i+1
        i = 1
        print("--------------------------")
        for segment in self.prunedSegments:
            print("Pruned Segment #{}:".format(i),segment.size(),"({},{}) [{}]".format(segment.boundingBox.topLeft, segment.boundingBox.botRight, len(segment.cells)))
            i = i+1
    
    def getVal(self, row, col):
        if row > self.max_row or col > self.max_col or row < 0 or col < 0:
            return -1 # should protect against out of range access
        return self.raster[row][col]

    def checkAndGrow(self, row, col):
        """Checks if a given cell is already accounted for, otherwise grows a new segment about it."""
        for seg in self.segments:
            if seg.isContained(row, col):
                return 1
        #print("Seeding: ", str(row),",", str(col))
        nCell = Cell(row, col)
        nSeg = Segment(self, [nCell])
        self.addSegment(nSeg)
        nSeg.grow(nCell)
        return 0
    
    def check(self, row, col):
        for seg in self.segments:
            if seg.isContained(row, col):
                return 1
        return 0
    
    def addSegment(self, segment):
        self.segments.append(segment)

    def scanRaster(self):
        row = 0
        for line in self.raster: # each row in the image
            col = 0 # reset column count each row
            for value in line: # each pixel left->right
                if value == self.occupied: #if pixel is occupied space
                    self.checkAndGrow(row,col)
                col = col + 1
            row = row + 1
    
    def prunePercentileSize(self, percentile):
        #TODO: Add overwriting capability (aka thresholding smaller segments out of the image)
        size = []
        for segment in self.segments:
            size.append(segment.size())
        cutoff = np.percentile(size, percentile)
        print("Minimum Size Threshold:", cutoff)
        print("Number of segments processed:", len(size))
        toPrune = []
        for segment in self.segments:
            x = segment.size()
            if cutoff > x:
                #prune this index
                toPrune.append(segment)
        for segment in toPrune:
            self.prune(segment)
    
    def prune(self, segment):
        #print("Prune event, size:", len(segment.cells))
        self.prunedSegments.append(segment)
        self.segments.remove(segment)

def read_pgm(pgmf):
    """Return a raster of integers from a PGM as a list of lists."""
    assert pgmf.readline() == b'P5\n'
    try:
        (width, height) = [int(i) for i in pgmf.readline().split()]
    except:
        #pgmf.readline() #just some trash.
        (width, height) = [int(i) for i in pgmf.readline().split()]
    depth = int(pgmf.readline())
    assert depth <= 255

    raster = []
    for y in range(height):
        row = []
        for y in range(width):
            row.append(ord(pgmf.read(1)))
        raster.append(row)
    return raster

def processFile(inputfile):
    with open(inputfile, 'rb') as f:
        raster = read_pgm(f) #raster list of rows
        print("Raster size:", len(raster),"x",len(raster[1]))
        segMan = SegmentManager(raster)
        segMan.scanRaster()
        segMan.prunePercentileSize(80.0) #,0)
        segMan.printInfo()
        #all data is deleted at the end of this function!!!

def main(argv):
    inputfile = ''
    outputfile = ''
    try:
        opts, args = getopt.getopt(argv,"i:o:",["ifile=","ofile="])
    except getopt.GetoptError:
        print(str(err))
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print("pgm_segment.py -i <inputfile> -o <outputfile>")
            sys.ext()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
    print("Input file is", inputfile)
    print("Output file is", outputfile)
    processFile(inputfile)

if __name__ == "__main__":
    main(sys.argv[1:])
