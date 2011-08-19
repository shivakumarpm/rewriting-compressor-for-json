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

import json, traceback, time, random, struct, math
import LiteralOptimizers

def float_fuzzer():
  f = struct.unpack('d', struct.pack('L', random.getrandbits(64)))[0]
  if math.isnan(f) or math.isinf(f):
    # These aren't part of the JSON spec.
    return True, None
  try:
    if float(LiteralOptimizers.optimal_float(f)) == f:
      return True, None
    else:
      return False, f
  except:
    return False, f

def int_fuzzer():
  i = random.randint(-(1 << 31), 1 << 31)
  if float(LiteralOptimizers.optimal_int(i)) == i:
    return True, None
  return False, i

def string_fuzzer():
  length = random.randint(0, 30)
  chrs = []
  for i in xrange(length):
    if random.random() < 0.8:
      chrs.append(unichr(random.randint(0,0x7f)))
    else:
      # Making random well-formed unicode strings is hard. This test aims to
      # at least stress ASCII + Control characters and some other Latin
      # characters.
      chrs.append(unichr(random.randint(0x100, 0x17f)))
  chrs = ''.join(chrs)
  try:
    if chrs != json.loads(LiteralOptimizers.optimal_string(chrs)):
      return False, chrs
  except:
    return False, chrs
  return True, None

def test_boolean():
  assert LiteralOptimizers.optimal_boolean(True, allowBooleanNumbers=False) == 'true'
  assert LiteralOptimizers.optimal_boolean(False, allowBooleanNumbers=False) == 'false'
  assert LiteralOptimizers.optimal_boolean(True, allowBooleanNumbers=True) == '1'
  assert LiteralOptimizers.optimal_boolean(False, allowBooleanNumbers=True) == '0'

def test_null():
  assert LiteralOptimizers.optimal_null(None) == 'null'
  assert LiteralOptimizers.optimal(None, None) == 'null'


tests = [test_boolean, test_null]
for test in tests:
  try:
    print('')
    test()
  except AssertionError as e:
    print('%s failed!: %r' % (test.__name__, e))
    traceback.print_exc()
  else:
    print('Test %s passed' % test.__name__)

fuzzers = [float_fuzzer, int_fuzzer, string_fuzzer]
FUZZER_TIME = 1.0

for fuzzer in fuzzers:
  start = time.clock()
  iterations = 0
  failures = []
  while time.clock() - start < FUZZER_TIME:
    try:
      worked, case = fuzzer()
      if not worked:
        failures.append(case)
    except AssertionError as e:
      pass
    iterations += 1
  print('')
  print('Ran {0} for {1:n} iterations ({2:.2f}s wall time)'.format(fuzzer.__name__, iterations, time.clock()-start))
  print('\t%d cases failed' % len(failures))
