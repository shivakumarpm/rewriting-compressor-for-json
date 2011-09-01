"""
Copyright 2011 Google Inc. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""
Usage: 
	RCFJ.py [options] input.json

Options:
  -h, --help            show this help message and exit
  -a, --all             Enable all optimizations (x, s, b, z, r). (You have to
                        specify f yourself).
  -x, --hex, --hex-ints
                        Allow integers to be represented in hexadecimal when
                        it's shorter. (NON-COMPLIANT.)
  -s, --symbol-keys, --non-string-keys
                        Allow dictionary keys to be symbols rather than
                        strings, as in {x: 0} (on) versus {"x": 1} (off).
                        (NON-COMPLIANT.)
  -b, --bool-int, --booleans-are-numbers
                        Represent true & false as 1 & 0. (Compliant, but loss
                        of semantics.)
  -f SIGNIFICANTFIGURES, --sigfigs=SIGNIFICANTFIGURES, --significant-figures=SIGNIFICANTFIGURES
                        Round floating point numbers to have however many
                        significant figures. (Compliant, but information
                        sometimes lost.)
  -z, --symbolization   Enable symbolization of common literals. (NON-
                        COMPLIANT.)
  -r, --records         Shorten representation of objects with all property
                        names in common. (NON-COMPLIANT.)
"""

import json, re, decimal
import LiteralOptimizers, Errors

VARIABLE_START = u'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_$'
VARIABLE_MID = VARIABLE_START + '0123456789'

def VariableGenerator(length):
  """
  A variable generator of length L will iterate over all valid variable names
  of length L (avoiding keywords and reserved variable names).
  """
  # This list contains both keywords & variables that you shouldn't (and
  # sometimes can't) override.
  keywords = ['false', 'debugger', 'synchronized', 'int', 'abstract', 'float',
      'private', 'self', 'char', 'interface', 'boolean', 'export', 'in', 'null',
      'if', 'true', 'const', 'for', 'with', 'top', 'NaN', 'while', 'long',
      'throw', 'finally', 'protected', 'extends', 'implements', 'var', 'import',
      'native', 'final', 'location', 'function', 'do', 'return', 'goto', 'void',
      'enum', 'else', 'break', 'transient', 'window', 'new', 'catch',
      'instanceof', 'byte', 'super', 'class', 'volatile', 'case', 'short',
      'undefined', 'package', 'default', 'double', 'public', 'try', 'this',
      'switch', 'continue', 'typeof', 'static', 'throws', 'delete']
  keywords = [x for x in keywords if len(x) == length]
  state = [0]*length
  state[0] = -1
  while True:
    state[-1] += 1
    i = length - 1
    while i >= 0:
      maxsize = len(VARIABLE_MID)
      if i == 0:
        maxsize = len(VARIABLE_START)
      if state[i] >= maxsize and i != 0:
        state[i-1] += 1
        state[i] = 0
      elif state[i] >= maxsize and i == 0:
        return
      i -= 1
    s = []
    for i in xrange(length):
      if i == 0:
        s.append(VARIABLE_START[state[i]])
      else:
        s.append(VARIABLE_MID[state[i]])
    as_name = ''.join(s)
    if as_name not in keywords:
      yield as_name

class StructurePositionIdentifier:
  """
  Uniquely specifies a single instance of a literal value in JSON using its
  position in the structure. Supports rich comparison.
  """
  def __init__(self, path):
    self.path = tuple(path)
  def __eq__(self, other):
    return self.path == other.path
  def __lt__(self, other):
    if len(self.path) <= len(other.path):
      return False
    for i,e in enumerate(other.path):
      if e != self.path[i]:
        return False
    return True
  def __gt__(self, other):
    if len(self.path) >= len(other.path):
      return False
    for i,e in enumerate(self.path):
      if e != other.path[i]:
        return False
    return True
  def __le__(self, other):
    return not self.__gt__(other)
  def __ge__(self, other):
    return not self.__lt__(other)
  def __ne__(self, other):
    return not self.__eq__(other)
  def __call__(self, onObject):
    for next in self.path:
      onObject = onObject[next]
    return onObject

class Proposal:
  """
  A proposal represents an option to replace a data structure (object, array,
  or basic literal) with something else. It handles creation of the foreword
  (something that needs to be assigned beforehand) and assesses the potential
  savings of the replacement in terms of the length of the variable it gets
  to use.
  """
  def __init__(self, savings_func, foreword):
    self.savings = savings_func
    self.foreword = foreword
    self.variable = None
  def assign(self, variable):
    self.variable = variable
  def get_foreword(self):
    return self.foreword % self.variable
  def compatible(self, otherProposal):
    return True
  def __repr__(self):
    return '<Proposal to save (%d,%d,%d) bytes with a (%d,%d,%d)-variable>' % (self.savings(1), self.savings(2), self.savings(3), 1, 2, 3)

class SymbolizedLiteralProposal(Proposal):
  """
  A proposal that replaces a literal (number or string) with a variable name,
  e.g. 3.14159 -> p
  """
  def __init__(self, save, foreword, value):
    self.value = value
    Proposal.__init__(self, save, foreword)
  def applies(self, struct):
    if struct == self.value:
      return True
  def apply(self, struct, proposals, options):
    return self.variable
  def __repr__(self):
    return '<Proposal to save (%d,%d,%d) bytes with a (%d,%d,%d)-variable (literal: %r)>' % (self.savings(1), self.savings(2), self.savings(3), 1, 2, 3, self.value)

class RecordProposal(Proposal):
  """
  A proposal that replaces an object with a function call to create the same.
  e.g. {value1: 4, value2: 5} ->
  function f(a,b){return {value1:a,value2:b};};
  f(4,5)
  (This becomes advantageous when you have many objects with the same key set).
  """
  def __init__(self, save, foreword, keys):
    self.keys = keys
    Proposal.__init__(self, save, foreword)
  def applies(self, struct):
    if isinstance(struct, dict):
      key = struct.keys()
      key.sort()
      if tuple(key) == self.keys:
        return True
  def apply(self, struct, proposals, options):
    args = []
    keys = struct.keys()
    keys.sort()
    for key in keys:
      args.append(writeJSON(struct[key], proposals, options=options))
    return self.variable + '(' + ','.join(args) + ')'

def generate_symbolized_literal_proposals(struct, options=None):
  """
  Generate a list of (not necessarily good) symbolization proposals
  (SymbolizedLiteralProposal).
  """
  if options == None:
    options = get_default_options()
  
  frequency = {}
  explore = [struct]
  while len(explore) > 0:
    node = explore.pop(0)
    if isinstance(node, list):
      for element in node:
        explore.append(element)
    elif isinstance(node, dict):
      for k in node:
        explore.append(node[k])
    else:
      frequency[node] = frequency.get(node,0) + 1
  
  def saved(literal_cost, occur, init_cost):
    def f(varlength):
      return (literal_cost*occur)-(varlength*occur+init_cost+varlength)
    return f
  
  proposals = []
  for k in frequency:
    best = LiteralOptimizers.optimal(k, options)
    #init_cost is semi-special here
    proposal = SymbolizedLiteralProposal(saved(len(best), frequency[k], 2+len(best)), '%%s=%s'%best, k)
    if proposal.savings(1) > 0:
      proposals.append(proposal)
  
  return proposals

def generate_record_proposals(struct, options=None):
  """
  Generate a list of (not necessarily good) record proposals (RecordProposal).
  """
  if options == None:
    options = get_default_options()
  
  #it's important that the savings for non-literal proposals are the savings from
  # *structure only*. The literal values are considered separately.
  
  frequency = {}
  explore = [struct]
  while len(explore) > 0:
    node = explore.pop(0)
    if isinstance(node, list):
      for element in node:
        explore.append(element)
    elif isinstance(node, dict):
      keylist = node.keys()
      keylist.sort()
      keylist = tuple(keylist)
      
      frequency[keylist] = frequency.get(keylist,0) + 1
      
      for k in node:
        explore.append(node[k])
  
  
  def saved(occur, keyset_size, keyset_len, foreword_len):
    def f(varlength):
      return occur*(2+keyset_size+2*keyset_len) - (foreword_len + varlength + occur*(2+varlength+keyset_len))
    return f
  
  proposals = []
  for k in frequency:
    arguments = []
    vlen = 1
    i = len(k)
    generator = VariableGenerator(vlen)
    while i > 0:
      for name in generator:
        arguments.append(name)
        i -= 1
        if i == 0:
          break
      vlen += 1
      generator = VariableGenerator(vlen)
    
    mappings = ['%s:%s' % (key,arg) for key,arg in zip(k,arguments)]
    
    foreword = 'function %%s(%s){return {%s};};' % (','.join(arguments), ','.join(mappings))

    proposal = RecordProposal(saved(frequency[k], sum([len(x) for x in k]), len(k), len(foreword)-2), foreword, k)
    if proposal.savings(1) > 0:
      proposals.append(proposal)
  
  return proposals


class JavascriptExpression:
  """
  If a JavascriptExpression shows up in a structure, writeJSON will output the
  expression given in the constructor as Javascript code. For example:
  
  # Shorter than "1.4142135623730951," but just as accurate.
  shorthand = JavascriptExpression('Math.sqrt(2)')
  writeJSON({'a': shorthand, 'b': 5} , [])
  
  -->
  
  {"a":Math.sqrt(2),"b":5}
  
  """
  def __init__(self, val):
    self.val = val
  def __str__(self):
    return self.val
  def __repr__(self):
    return '<Symbol %r>' % self.val

def get_default_options():
  """
  Default options for write-out. Compliant; essentially just strips whitespace.
  """
  return {'keysAreStrings': True, 'allowHex': False, 'allowBooleanNumbers': False, 'significantFigures': None}


def writeJSON(struct, proposals, options=None):
  """
  Translate struct to JSON, in a manner similar to json.dumps(). Proposals is a
  list of Proposal objects which will be .apply()d if they .applies(). Options
  is a dictionary with keys like those in get_default_options() (although
  perhaps with different values).
  """
  if options == None:
    options = get_default_options()
  for proposal in proposals:
    if proposal.applies(struct):
      return proposal.apply(struct, proposals, options)
  
  output = []
  if isinstance(struct, dict):
    output.append('{')
    temp = []
    for key in struct:
      if options['keysAreStrings']:
        temp.append('"' + key + '":' + writeJSON(struct[key],  proposals, options=options))
      else:
        temp.append(key + ':' + writeJSON(struct[key],  proposals, options=options))
    output.append(','.join(temp))
    output.append('}')
  elif isinstance(struct, list):
    output.append('[')
    temp = []
    for item in struct:
      temp.append(writeJSON(item,  proposals, options=options))
    output.append(','.join(temp))
    output.append(']')
  elif isinstance(struct, JavascriptExpression):
    output.append(str(struct))
  else:
    output.append(LiteralOptimizers.optimal(struct, options))
  return ''.join(output)


def assign_proposals_greedy(proposals):
  """
  Return a sorted list of the most advantageous proposals, after assigning them
  variables. This is a simple greedy algorithm which furthermore only tries up
  to variables of length 2.
  """
  assigned = []
  
  proposals.sort(key=lambda x:x.savings(1), reverse=True)
  
  # At the moment this only considers 1 and 2 length variables (very rarely
  # would 3 be useful).
  for i,proposal in enumerate(proposals[:len(VARIABLE_START)]):
    if proposal.savings(1) <= 0:
      break
    proposal.assign(VARIABLE_START[i])
    assigned.append(proposal)
  proposals = proposals[len(assigned):]
  
  g = VariableGenerator(2)
  
  proposals.sort(key=lambda x:x.savings(2), reverse=True)
  for i,proposal in enumerate(proposals):
    if proposal.savings(2) <= 0:
      break
    proposal.assign(g.next())
    assigned.append(proposal)
  
  
  return assigned

if __name__ == '__main__':
  import sys, os, optparse
  
  parser = optparse.OptionParser(usage='\n\t%prog [options] input.json')
  parser.add_option('-a', '--all', dest="all", help='Enable all optimizations (x, s, b, z, r). (You have to specify f yourself).', default=False, action="store_true")
  # Literal representation options
  parser.add_option('-x', '--hex', '--hex-ints', dest="allowHex", help='Allow integers to be represented in hexadecimal when it\'s shorter. (NON-COMPLIANT.)', default=False, action="store_true")
  parser.add_option('-s', '--symbol-keys', '--non-string-keys', dest="keysAreStrings", help='Allow dictionary keys to be identifiers rather than strings, as in {x: 0} (on) versus {"x": 1} (off). (NON-COMPLIANT.)', default=True, action="store_false")
  parser.add_option('-b', '--bool-int', '--booleans-are-numbers', dest="allowBooleanNumbers", help='Represent true & false as 1 & 0. (Compliant, but loss of semantics.)', default=False, action="store_true")
  parser.add_option('-f', '--sigfigs', '--significant-figures', dest="significantFigures", help='Round floating point numbers to have however many significant figures. (Compliant, but information sometimes lost.)', default=None, type='int')
  # Optimizations
  parser.add_option('-z', '--symbolization', dest="optimization_symbolization", help='Enable symbolization of common literals. (NON-COMPLIANT.)', default=False, action="store_true")
  parser.add_option('-r', '--records', dest="optimization_records", help='Shorten representation of objects with all property names in common. (NON-COMPLIANT.)', default=False, action="store_true")
  
  (options, args) = parser.parse_args()
  
  if len(args) != 1:
    parser.print_help()
    sys.exit(1)
  
  input = args[0]
  if not os.path.isfile(input):
    print 'Input isn\'t a file.'
    sys.exit(1)
  try:
    structure = json.load(open(input, 'rb'), parse_float=decimal.Decimal)
  except Exception as e:
    print 'Not able to parse input JSON: %r' % e
    sys.exit(1)
  
  writer_options = get_default_options()
  for option_key in writer_options:
    if hasattr(options, option_key):
      writer_options[option_key] = getattr(options,option_key)
  if options.all:
    writer_options['allowHex'] = True
    writer_options['keysAreStrings'] = False
    writer_options['allowBooleanNumbers'] = True
    options.optimization_symbolization = True
    options.optimization_records = True
  
  foreword_symbolizations = ''
  foreword_functions = ''
  proposals = []
  if options.optimization_symbolization:
    proposals += generate_symbolized_literal_proposals(structure, writer_options)
  if options.optimization_records:
    proposals += generate_record_proposals(structure, writer_options)
  proposals = assign_proposals_greedy(proposals)
  
  if options.optimization_symbolization:
    foreword_symbolizations = 'var ' + ','.join([x.get_foreword() for x in proposals if isinstance(x,SymbolizedLiteralProposal)]) + ';'
  if options.optimization_records:
    foreword_functions = ''.join([x.get_foreword() for x in proposals if isinstance(x,RecordProposal)])
  
  if len(proposals) > 0:
    result = '(function(){%sreturn %s;})()' % (foreword_symbolizations+foreword_functions, writeJSON(structure, proposals, options=writer_options))
  else:
    result = writeJSON(structure, proposals, options=writer_options)
  sys.stdout.write(result.encode('utf-8'))