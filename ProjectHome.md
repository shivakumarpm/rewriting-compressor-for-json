# The Rewriting Compressor for JSON #

The Rewriting Compressor For JSON (RCFJ) is a tool and library for representing data encoded in JSON format in a more compact way. In its current incarnation as a tool RCFJ is written in Python and supports the following optimizations:
  * Whitespace and non-string keys (JSON requires object properties to be strings, but Javascript is OK with identifiers)
  * Literal representation optimization (e.g. 10000 -> 1e4)
  * Symbolization of repeated literals
  * Extracting common object signatures into functions

Combined, these optimizations can dramatically reduce the size of your JSON (and it will even help when gzipped).

Another goal of this project is to make it easy to extend and use as a library to write new and custom optimizations. At the moment you can do the following things:
  * Call the internals of RCFJ in your Python code to write custom expression wrappers.
  * Use JavascriptExpression objects in Python structures you serialize to output Javascript raw into your JSON (which has utility beyond compression as well).

At the moment unless you want to get your hands dirty, it will be challenging to implement your own optimizations like symbolization or common-object functionization, but hopefully an optimizations framework is coming soon (it turns out to be a very tricky problem).

**If you have data in JSON format which you can contribute to testing, please do!**

### Example ###
**Input** (1136 bytes):
```
{
	"records": [{
		"user": 23742374,
		"action": "edit-append",
		"position": 234,
		"data": "Some string data!"
	},{
		"user": 23742374,
		"action": "edit-delete",
		"position": 434,
		"data": "\n\t\f\r\b"
	},{
		"user": 23742374,
		"action": "edit-append",
		"position": 79,
		"data": "\u00a1Unicode is awesome!"
	},{
		"user": 23742374,
		"action": "edit-append",
		"position": 1283,
		"data": "Some string data!"
	},{
		"user": 23742374,
		"action": "edit-delete",
		"position": 3127,
		"data": "Some string data!"
	},{
		"user": 3207243,
		"action": "edit-append",
		"position": 212,
		"data": "Some string data!"
	},{
		"user": 23742374,
		"action": "edit-append",
		"position": 11,
		"data": "Some string data!"
	},{
		"user": 23742374,
		"action": "edit-append",
		"position": 3872,
		"data": "Some string data!"
	},{
		"user": 23742374,
		"action": "edit-delete",
		"position": 298,
		"data": "Some string data!"
	},{
		"user": 3207243,
		"action": "edit-append",
		"position": 1211,
		"data": "Some string data!"
	},{
		"user": 23742374,
		"action": "edit-append",
		"position": 100000000,
		"data": "Some string data!"
	}]
}
```

**Output** (361 bytes):

`(function(){var b="Some string data!",c="edit-append",d=23742374,e="edit-delete",f=3207243;function a(a,b,c,d){return {action:a,data:b,position:c,user:d};};return {records:[a(c,b,234,d),a(e,"\n\t\f\r\b",434,d),a(c,"\u00a1Unicode is awesome!",79,d),a(c,b,1283,d),a(e,b,3127,d),a(c,b,212,f),a(c,b,11,d),a(c,b,3872,d),a(e,b,298,d),a(c,b,1211,f),a(c,b,1e8,d)]};})()`

### Questions ###
  * What about standards!?
By default, RCFJ doesn't break any standards. By turning on options you definitely can, as it takes advantage of the fact that Javascript can evaluate Javascript code (through eval()) to make the representation of your data smaller. If you choose to use these options it's a good idea to make an uncompressed version available as well, since no JSON library will be able to parse it.

  * Is this code ready to be used in <my web server stack>?
Probably not. In its current form RCFJ isn't optimized for speed, so it wouldn't be advisable to run it on all the JSON you write on the fly. Static content, however, is fair game. Speeding up the basic functionality of the code is a high priority.

  * Why doesn't RCFJ symbolize higher level structures?
Try this in a Javascript console:

`var x = {a:1, b:1};`

`var y = {f: x, g: x};`

This representation of `y` is undoubtedly more succinct than `{f: {a:1, b:1}, g: {a:1, b:1}}`, but observe:

`y.f.a = 5;`

`print(y.g.a)`

Whoa! Because both properties refer to the _same_ data in memory changing one will change the other. This isn't a problem if you only read your data (and there are other ways around this problem) but RCFJ doesn't support those yet.

### Tool Usage ###

<pre>
Usage:<br>
RCFJ.py [options] input.json<br>
<br>
Options:<br>
-h, --help            show this help message and exit<br>
-a, --all             Enable all optimizations (x, s, b, z, r). (You have to<br>
specify f yourself).<br>
-x, --hex, --hex-ints<br>
Allow integers to be represented in hexadecimal when<br>
it's shorter. (NON-COMPLIANT.)<br>
-s, --symbol-keys, --non-string-keys<br>
Allow dictionary keys to be identifiers rather than<br>
strings, as in {x: 0} (on) versus {"x": 1} (off).<br>
(NON-COMPLIANT.)<br>
-b, --bool-int, --booleans-are-numbers<br>
Represent true & false as 1 & 0. (Compliant, but loss<br>
of semantics.)<br>
-f SIGNIFICANTFIGURES, --sigfigs=SIGNIFICANTFIGURES, --significant-figures=SIGNIFICANTFIGURES<br>
Round floating point numbers to have however many<br>
significant figures. (Compliant, but information<br>
sometimes lost.)<br>
-z, --symbolization   Enable symbolization of common literals. (NON-<br>
COMPLIANT.)<br>
-r, --records         Shorten representation of objects with all property<br>
names in common. (NON-COMPLIANT.)<br>
</pre>

**Examples:**

Minimize size while staying standards-compliant:

`python RCFJ.py data.json > data.min.json`

Minimize the size of data.json and write it to data.min.js (as it's no longer JSON):

`python RCFJ.py -a data.json > data.min.js`

Minimize size and store only 2 significant digits for floating point numbers:

`python RCFJ.py -a -f 2 data.json > data.min.js`