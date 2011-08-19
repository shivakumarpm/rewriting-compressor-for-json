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

import json, struct, math, decimal, Errors

def optimal_int(i, allowHex=False):
  """
  Return i in a form as short as possible. If allowHex is true, i will be
  converted to hexadecimal if it's shorter to do so (hexadecimal numbers aren't
  included in the JSON specification).
  """
  normal = '%d' % i
  power = 1000
  if i % power == 0 and i != 0:
    while i % power == 0:
      power *= 10
    power /= 10
    normal = '%de%d' % (i/power, int(math.log10(power)))
  if allowHex and len(hex(i)) < len(normal):
    return hex(i)
  return normal

def optimal_float(f, sigdigits=None, allowHex=False):
  """
  Return f in a form as short as possible. If allowHex is true, f can be
  written as an integer[1] and that integer is shorter in hexadecimal then it
  is (hexadecimal numbers aren't included in the JSON specification). If
  sigdigits is not None, only that many significant digits will be included.
  
  [1] Note that ECMAScript specifies that the number type is a 64 bit IEEE 754
  floating point (a double). As such, there's no difference between a number
  written as an integer and one written as a float.
  """
  
  if sigdigits == None:
    # Python's repr() function automatically chooses the shortest representation
    # which represents the corresponding IEEE-754 float.
    # Note that sometimes this uses E notation, which for some reason uses
    # a two character default (i.e. 1e06 rather than 1e6).
    # The conditions under which is switches to exponent notation are also
    # suboptimal for space considerations (1000000 vs. 1e6). (TODO -- although
    # will it ever matter? Since optimal_int takes this into account.)
    if isinstance(f, decimal.Decimal):
      floatversion = str(abs(f)).lstrip('0')
    else:
      floatversion = repr(abs(f)).lstrip('0')
    if f < 0:
      floatversion = '-%s' % floatversion
    if floatversion.find('e') != -1:
      digits, exponent = floatversion.split('e', 1)
      floatversion = '%sE%s' % (digits, optimal_int(int(exponent), allowHex=False))
  else:
    d = decimal.Decimal(f)
    prior = decimal.getcontext().prec
    decimal.getcontext().prec = sigdigits
    d += 0
    decimal.getcontext().prec = prior
    return optimal_float(d, sigdigits=None, allowHex=allowHex)
  
  integerversion = optimal_int(int(math.floor(f)), allowHex=allowHex)
  if int(f) == f and len(integerversion) <= len(floatversion):
    return integerversion
  return floatversion

def optimal_boolean(b, allowBooleanNumbers=False):
  """
  Return b as the shortest representation of itself as a boolean. This is simply
  true/false unless allowBooleanNumbers is True. In that case True/False are
  represented as 1 and 0 respectively.
  """
  if allowBooleanNumbers:
    if b:
      return '1'
    else:
      return '0'
  if b:
    return 'true'
  else:
    return 'false'

def optimal_null(s):
  """
  Returns the shortest representation of s as a null value. This is always null.
  """
  return 'null'

def optimal_string(s):
  """
  Return the shortest representation of s as a string literal. Currently this
  is outsourced to Python's json library, which handles all sorts of escaping
  complexities.
  """
  return json.dumps(s)

def optimal(struct, options):
  """
  Return the shortest string representation of struct, a literal (Python bool,
  float, int, unicode, str, or None) or else raise
  IncontrovertiblyInconvertible.
  """
  if isinstance(struct, bool):
    # It's important that this comes before int, because isinstance(True, int)==True
    return optimal_boolean(struct, allowBooleanNumbers=options['allowBooleanNumbers'])
  elif isinstance(struct, float) or isinstance(struct, decimal.Decimal):
    return optimal_float(struct, allowHex=options['allowHex'], sigdigits=options['significantFigures'])
  elif isinstance(struct, int):
    return optimal_int(struct, allowHex=options['allowHex'])
  elif isinstance(struct, unicode) or isinstance(struct, str):
    return optimal_string(struct)
  elif struct == None:
    return optimal_null(struct)
  else:
    raise Errors.IncontrovertiblyInconvertible('LiteralOptimizers.optimal didn\'t recognize the datatype, and doesn\'t know what to do with it.')