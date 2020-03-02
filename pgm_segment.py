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
        self.value = self.setValue()

    def setContainer(self, container):
        self.container = container
    
    def setValue(self):
        if not self.container:
            return -1
        return self.container.segMan.getVal(self.row, self.col)
    
    def getValue(self):
        return self.value

class Box:
    def __init__(self, topLeft=(-1,-1), botRight=(-1,-1)):
        self.topLeft = topLeft
        self.botRight = botRight

    def area(self):
        dimx = abs(self.botRight[0] - self.topLeft[0] + 1)
        dimy = abs(self.botRight[1] - self.topLeft[1] + 1)
        return dimx*dimy

class Box4(Box):
    def __init__(self, topLeft=(-1,-1), botLeft=(-1,-1), topRight=(-1,-1), botRight=(-1,-1)):
        self.topLeft = topLeft
        self.topRight = topRight
        self.botLeft = botLeft
        self.botRight = botRight

    
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

    #def setBounds4(self):
        #initialize each coordinate to it's polar opposite
    #    topLeft = [sys.maxsize, sys.maxsize]
    #    botLeft = [0, sys.maxsize]
    #    topRight = [sys.maxsize, 0]
    #    botRight = [0, 0]

    #    for cell in self.cells:
            
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
    """A singleton for managing the image. Has facilities for segmentation and other image modifications."""
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
    
    def inBounds(self, row, col):
        if row > self.max_row or col > self.max_col or row <0 or col < 0:
            return 0
        return 1

    def getVal(self, row, col):
        if not self.inBounds(row, col):
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
        """Scans through raster and grows segments on every occupied pixel."""
        row = 0
        for line in self.raster: # each row in the image
            col = 0 # reset column count each row
            for value in line: # each pixel left->right
                if value == self.occupied: #if pixel is occupied space
                    self.checkAndGrow(row,col)
                col = col + 1
            row = row + 1
    
    def prunePercentileSize(self, percentile):
        """Prunes segments that are below a percentile size thresholding."""
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

                    
def cropRaster(raster, cropval=205):
    right = bottom = 0
    top = left = sys.maxsize
    row = col = 0
    frow = fcol = 0
    for line in raster: #top-down, left-right scan
        col = 0
        frow_last = frow
        frow = 0 #flagged row (with data in it, for detecting tail end)
        for value in line:
            fcol_last = fcol
            fcol = 0
            if value != cropval: # real data
                frow = fcol = 1
                if top > row: #if top thresh is lower than current line
                    top = max(0, row)
                if left > col:
                    left = max(0, col)
            if (fcol_last) and not fcol and (right < col):
                right = col
            col = col+1
        if (frow_last) and not frow and (bottom < row):
            bottom = row
        row = row+1
    print("\nVertexes of crop:\n")
    print("Left:", left, " Right:", right)
    print("\nTop:", top, "Bottom:", bottom)
    crop1 = raster[top:bottom]
    crop2 = []
    for row in crop1:
        crop2.append(row[left:right])
    return crop2

def dilateRaster(raster, size=5, occupied=0):
    """Dilate the raster by convolution of size x size matrix of 1's
        size parameter should be an odd value."""
    i = int((size-1)/2)
    row = 0
    max_row = len(raster)-1
    max_col = len(raster[1])-1
    toDilate = []
    for line in raster: #collect pixels to dilate first
        col = 0
        for value in line:
            if value == occupied:
                for rowmod in range(-i, i+1):
                    for colmod in range(-i, i+1):
                        if row+rowmod > 0 and col+colmod > 0 and row+rowmod <= max_row and col+colmod <= max_col:
                            cVal = raster[row+rowmod][col+colmod]
                            if cVal != occupied:
                                toDilate.append((row+rowmod, col+colmod))
            col = col+1
        row = row+1
    for tup in toDilate: #iterate through collected pixel tuples to set values
        raster[tup[0]][tup[1]] = occupied
    return raster

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

def processFile(inputfile, outputfile, pgm, crop, dilate):
    if inputfile:
        with open(inputfile, 'rb') as f:
            raster = read_pgm(f) #raster list of rows
            if crop:
                print("Raster cropped.")
                raster = cropRaster(raster, 205)
            if dilate:
                print("Raster dilated.")
                raster = dilateRaster(raster, dilate)

            print("Raster size:", len(raster),"x",len(raster[1]))
            segMan = SegmentManager(raster)
            segMan.scanRaster()
            segMan.prunePercentileSize(80.0) #,0)
            segMan.printInfo()
            if outputfile:
                if pgm:
                    with open(outputfile, 'w+b') as o:
                        flat_raster = [item for sublist in raster for item in sublist]
                        height = len(raster)
                        width = len(raster[1])
                        o.write(bytes('P5' + '\n' + '# CREATOR: pgm_segment.py 0.01\n', encoding='utf8'))
                        o.write(bytes(str(width) + ' ' + str(height) + '\n' + str(255) + '\n', encoding='utf8'))
                        rasterbytes = bytes(flat_raster)
                        o.write(rasterbytes)
                else:
                    with open(outputfile, 'w+') as o:
                        for line in raster:
                            for val in line:
                                o.write(str(val) + ',')
                            o.write('\n')

def main(argv):
    inputfile = ''
    outputfile = ''
    pgm = 0
    crop = 0
    dilate = 0
    try:
        opts, args = getopt.getopt(argv,"hbcd:i:o:",["dilate=", "ifile=","ofile="])
    except getopt.GetoptError:
        print(str(getopt.err))
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print("pgm_segment.py -i <inputfile> -o <outputfile>")
            sys.ext()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
        elif opt == '-b':
            print("Outputting as PGM.")
            pgm = 1
        elif opt == '-c':
            print("Cropping margins.")
            crop = 1
        elif opt in ("-d", "--dilate"):
            print("Dilating raster prior to segmentation. Size of " + str(int(arg)))
            dilate = int(arg)

    print("Input file is", inputfile)
    print("Output file is", outputfile)
    processFile(inputfile, outputfile, pgm, crop, dilate)

if __name__ == "__main__":
    main(sys.argv[1:])
