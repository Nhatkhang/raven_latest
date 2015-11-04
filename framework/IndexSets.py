from __future__ import division, print_function, unicode_literals, absolute_import
import warnings
warnings.simplefilter('default',DeprecationWarning)

import numpy as np
import itertools
from operator import itemgetter
import sys
import operator

import MessageHandler
import Files

class IndexSet(MessageHandler.MessageUser):
  """In stochastic collocation for generalised polynomial chaos, the Index Set
     is a set of all combinations of polynomial orders needed to represent the
     original model to a "level" L (maxPolyOrder).
  """
  def __init__(self,messageHandler):
    self.type          = 'IndexSet' #type of index set (Tensor Product, Total Degree, Hyperbolic Cross)
    self.printTag      = 'IndexSet' #type of index set (Tensor Product, Total Degree, Hyperbolic Cross)
    self.maxOrds       = None #maximum requested polynomial order requested for each distribution
    self.points        = []   #array of polynomial order tuples
    self.maxPolyOrder  = None #integer, maximum order polynomial to use in any one dimension -> misleading! Relative order for anisotropic case
    self.polyOrderList = []   #array of lists containing all the polynomial orders needed for each dimension
    self.impWeights    = []   #array of scalars for assigning importance weights to each dimension
    self.messageHandler=messageHandler

  def __len__(self):
    """Returns number of entries in the index set.
    @ In , None  , None
    @ Out, int  , cardinality of index set
    """
    return len(self.points)

  def __getitem__(self,i=None):
    """Returns as if called on self.points.
    @ In , i     , string/int           , splice notation for array
    @ Out, array of tuples/tuple, requested points
    """
    if i==None: return np.array(self.points)
    else: return self.points[i]

  def __repr__(self):
    """Produces a more human-readable version of the index set.
    @ In, None, None
    @ Out, string, visual representation of index set
    """
    if len(self.points)<1: return "Index set is empty!"
    msg='IndexSet Printout:\n'
    if len(self.points[0])==2: #graphical block visualization
      left=0
      p=0
      while p<len(self.points):
        pt = self.points[p]
        if pt[0]==left:
          msg+='  '+str(pt)
          p+=1
        else:
          msg+='\n'
          left+=1
    else: #just list them
      for pt in self.points:
        msg+='  '+str(pt)+'\n'
    return msg

  def __eq__(self,other):
    """Checks equivalency of index set
    @ In , other, object , object to compare to
    @ Out, boolean, equivalency
    """
    return self.type == other.type and \
           self.points == other.points and \
           (self.impWeights == other.impWeights).all()

  def __ne__(self,other):
    """Checks non-equivalency of index set
    @ In , other  , object , object to compare to
    @ Out, boolean, non-equivalency
    """
    return not self.__eq__(other)

  def _xy(self):
    """Returns reordered data.  Originally,
       Points = [(a1,b1,...,z1),
                 (a2,b2,...,z2),
                 ...]
       Returns [(a1,a2,a3,...),
                (b1,b2,b3,...),
                ...,
                (z1,z2,z3,...)]
    @ In , None  , None
    @ Out, array of tuples, points by dimension
    """
    return zip(*self.points)

  def printOut(self):
    """
      Prints out the contents of the index set.
      @ In, None
      @ Out, None
    """
    self.raiseADebug('IndexSet Printout:')
    if len(self.points[0])==2: #graphical block visualization
      msg=''
      left=0
      p=0
      while p<len(self.points):
        pt = self.points[p]
        if pt[0]==left:
          msg+='  '+str(pt)
          p+=1
        else:
          self.raiseADebug(msg)
          msg=''
          left+=1
      self.raiseADebug(msg)
    else: #just list them
      for pt in self.points:
        self.raiseADebug('  '+str(pt))

  def order(self):
    """
      Orders the index set points in partially-increasing order.
      @ In, None
      @ Out, None
    """
    self.points.sort(key=operator.itemgetter(*range(len(self.points[0]))))

  def initialize(self,distrList,impList,maxPolyOrder):
    """Initialize everything index set needs
    @ In , distrList   , dictionary of {varName:Distribution}, distribution access
    @ In , impList     , dictionary of {varName:float}, weights by dimension
    @ In , maxPolyOrder, int, relative maximum polynomial order to be used for index set
    @ Out, None        , None
    """
    numDim = len(distrList)
    #set up and normalize weights
    #  this algorithm assures higher weight means more importance,
    #  and end product is normalized so smallest is 1
    self.impWeights = np.array(list(impList[v] for v in distrList.keys()))
    self.impWeights/= np.max(self.impWeights)
    self.impWeights = 1.0/self.impWeights
    #establish max orders
    self.maxOrder=maxPolyOrder
    self.polyOrderList=[]
    for distr in distrList.values():
      self.polyOrderList.append(range(self.maxOrder+1))

  def generateMultiIndex(self,N,rule,I=None,MI=None):
    """Recursive algorithm to build monotonically-increasing-order index set.
    @ In, N   , int            , dimension of the input space
    @ In, rule, function       , rule for type of index set (tensor product, total degree, etc)
    @ In, I   , array of scalar, single index point
    @ In, MI  , array of tuples, multiindex point collection
    @ Out, array of tuples, index set
    """
    L = self.maxOrder
    if I ==None: I =[]
    if MI==None: MI=[]
    if len(I)!=N:
      i=0
      while rule(I+[i]): #rule is defined by subclasses, limits number of index points by criteria
        MI = self.generateMultiIndex(N,rule,I+[i],MI)
        i+=1
    else:
      MI.append(tuple(I))
    return MI



class TensorProduct(IndexSet):
  """This Index Set requires only that the max poly order in the index point i is less than maxPolyOrder ( max(i)<=L )."""
  def initialize(self,distrList,impList,maxPolyOrder):
    """Initialize everything index set needs
    @ In , distrList   , dictionary of {varName:Distribution}, distribution access
    @ In , impList     , dictionary of {varName:float}, weights by dimension
    @ In , maxPolyOrder, int, relative maximum polynomial order to be used for index set
    @ Out, None        , None
    """
    IndexSet.initialize(self,distrList,impList,maxPolyOrder)
    self.type='Tensor Product'
    self.printTag='TensorProductIndexSet'
    target = sum(self.impWeights)/float(len(self.impWeights))*self.maxOrder
    def rule(i):
      big=0
      for j,p in enumerate(i):
        big=max(big,p*self.impWeights[j])
      return big <= target
    self.points = self.generateMultiIndex(len(distrList),rule)



class TotalDegree(IndexSet):
  """This Index Set requires the sum of poly orders in the index point is less than maxPolyOrder ( sum(i)<=L )."""
  def initialize(self,distrList,impList,maxPolyOrder):
    """Initialize everything index set needs
    @ In , distrList   , dictionary of {varName:Distribution}, distribution access
    @ In , impList     , dictionary of {varName:float}, weights by dimension
    @ In , maxPolyOrder, int, relative maximum polynomial order to be used for index set
    @ Out, None        , None
    """
    IndexSet.initialize(self,distrList,impList,maxPolyOrder)
    self.type='Total Degree'
    self.printTag='TotalDegreeIndexSet'
    #TODO if user has set max poly orders (levels), make it so you never use more
    #  - right now is only limited by the maximum overall level (and importance weight)
    target = sum(self.impWeights)/float(len(self.impWeights))*self.maxOrder
    def rule(i):
      tot=0
      for j,p in enumerate(i):
        tot+=p*self.impWeights[j]
      return tot<=target
    self.points = self.generateMultiIndex(len(distrList),rule)



class HyperbolicCross(IndexSet):
  """This Index Set requires the product of poly orders in the index point is less than maxPolyOrder ( prod(i+1)<=L+1 )."""
  def initialize(self,distrList,impList,maxPolyOrder):
    """Initialize everything index set needs
    @ In , distrList   , dictionary of {varName:Distribution}, distribution access
    @ In , impList     , dictionary of {varName:float}, weights by dimension
    @ In , maxPolyOrder, int, relative maximum polynomial order to be used for index set
    @ Out, None        , None
    """
    IndexSet.initialize(self,distrList,impList,maxPolyOrder)
    self.type='Hyperbolic Cross'
    self.printTag='HyperbolicCrossIndexSet'
    #TODO if user has set max poly orders (levels), make it so you never use more
    #  - right now is only limited by the maximum overall level (and importance weight)
    target = (self.maxOrder+1)**(sum(self.impWeights)/max(1,float(len(self.impWeights))))
    def rule(i):
      tot=1;
      for e,val in enumerate(i):
        tot*=(val+1)**self.impWeights[e]
      return tot<=target
    self.points = self.generateMultiIndex(len(distrList),rule)



class Custom(IndexSet):
  """User-based index set point choices"""
  def initialize(self,distrList,impList,maxPolyOrder):
    """Initialize everything index set needs
    @ In , distrList   , dictionary of {varName:Distribution}, distribution access
    @ In , impList     , dictionary of {varName:float}, weights by dimension
    @ In , maxPolyOrder, int, relative maximum polynomial order to be used for index set
    @ Out, None        , None
    """
    IndexSet.initialize(self,distrList,impList,maxPolyOrder)
    self.type     = 'Custom'
    self.printTag = 'CustomIndexSet'
    self.N        = len(distrList)
    self.points   = []

  def setPoints(self,points):
    """
      Used to set the index set points manually.
      @ In, points, list of tuples to set points to
      @ Out, None
    """
    self.points=[]
    if len(points)>0:
      self.addPoints(points)
      self.order()

  def addPoints(self,points):
    """
      Adds points to existing index set. Reorders set on completion.
      @ In, points, either single tuple or list of tuples to add
      @ Out, None
    """
    if type(points)==list:
      for pt in points: self.points.append(pt)
    elif type(points)==tuple and len(points)==self.N:
      self.points.append(points)
    else: raiseAnError(ValueError,'Unexpected points to add to set:',points)
    self.order()



class AdaptiveSet(IndexSet):
  """Adaptive index set that can expand itself on call.  Used in conjunctoin with AdaptiveSparseGrid sampler."""
  def initialize(self,distrList,impList,maxPolyOrder):
    """Initialize everything index set needs
    @ In , distrList   , dictionary of {varName:Distribution}, distribution access
    @ In , impList     , dictionary of {varName:float}, weights by dimension
    @ In , maxPolyOrder, int, relative maximum polynomial order to be used for index set
    @ Out, None        , None
    """
    IndexSet.initialize(self,distrList,impList,maxPolyOrder)
    self.type     = 'Adaptive Index Set'
    self.printTag = self.type
    self.N        = len(distrList)
    self.points   = [] #retained points in the index set
    #need 0, first-order polynomial in each dimension to start predictions
    firstpoint    = [0]*self.N #mean point polynomial
    self.active   = [tuple(firstpoint)] #stores the polynomial indices being actively trained
    for i in range(self.N): #add first-order polynomial along each axis
      pt = firstpoint[:]
      pt[i]+=1
      self.active.append(tuple(pt))
    self.history  = [] #list of tuples, index set point and its impact parameter

  def accept(self,pt):
    """
    Indicates the provided point should be accepted from the active set to the use set
    @ In, pt, tuple(int), the polynomial index to accept
    @Out, None
    """
    if pt not in self.active:
      self.raiseAnError(KeyError,'Adaptive index set instructed to accept point',pt,'but point is not in active set!')
    self.active.remove(pt)
    self.points.append(pt)
    self.order()

  def reject(self,pt):
    """
    Indicates the provided point should be accepted from the active set to the use set
    @ In, pt, tuple(int), the polynomial index to accept
    @Out, None
    """
    if pt not in self.active.keys():
      self.raiseAnError(KeyError,'Adaptive index set instructed to reject point',pt,'but point is not in active set!')
    self.active.remove(pt)

  def forward(self,pt,maxPoly=None):
    """
      Searches for new active points based on the point given and the established set.
      @ In, pt, tuple of int, the point to move forward from
      @ In, maxPoly, integer, optional maximum value to have in any direction
      @ Out, None
    """
    #TODO generalize this not to refer to polys, if anything else ever wants to use these sets.
    #add one to each dimenssion, one at a time, as the potential candidates
    for i in range(self.N):
      newpt = list(pt)
      newpt[i]+=1
      if maxPoly != None:
        if newpt[i]>maxPoly:
          continue
      if tuple(newpt) in self.active:
        continue
      #remove the candidate if not all of its predecessors are accepted.
      found=True
      for j in range(self.N):
        checkpt = newpt[:]
        if checkpt[j]==0:continue
        checkpt[j] -= 1
        if tuple(checkpt) not in self.points:
          found=False
          break
      if found:
        self.active.append(tuple(newpt))

  def printOut(self):
    """
      Prints the accepted/established points and the current active set to screen.
      @ In, None
      @ Out, None
    """
    self.raiseADebug('    Accepted Points:')
    for p in self.points:
      self.raiseADebug('       ',p)
    self.raiseADebug('    Active Set')
    for a in self.active:
      self.raiseADebug('       ',a)


"""
Interface Dictionary (factory) (private)
"""
__base = 'IndexSet'
__interFaceDict = {}
__interFaceDict['TensorProduct'  ] = TensorProduct
__interFaceDict['TotalDegree'    ] = TotalDegree
__interFaceDict['HyperbolicCross'] = HyperbolicCross
__interFaceDict['Custom'         ] = Custom
__interFaceDict['AdaptiveSet'    ] = AdaptiveSet
__knownTypes = list(__interFaceDict.keys())

def knownTypes():
  return __knownTypes

def returnInstance(Type,caller):
  if Type in knownTypes(): return __interFaceDict[Type](caller.messageHandler)
  else: caller.raiseAnError(NameError,'not known '+__base+' type '+Type)
