from __future__ import unicode_literals

HELP = """
SUMMARY OF COMMANDS
===================

 h  H          Display this help.
 q  Q  ZZ      Exit.

------------------------------------------------------

Moving
------

 e  ^E  j  ^N  CR   Forward one line.
 y  ^Y  k  ^K  ^P   Backward one line.
 f  ^F  ^V  SPACE   Forward one window.
 b  ^B  ESC-v       Backward one window.
 d  ^D              Forward one half-window.
 u  ^U              Backward one half-window.
 ESC-)  RightArrow  Left one half screen width.
 ESC-9  LeftArrow   Right one half screen width.
 F                  Forward forever; like "tail -f"
 r  R  ^R  ^L       Repaint screen.

SEARCHING
---------

 /pattern           Search forward.
 ?pattern           Search backward.
 n                  Repeat previous search.
 N                  Repeat previous search in reverse direction.
 ESC-u              Undo (toggle) search highlighting.

JUMPING
-------

 g  <  ESC-<        Go to the first line in file.
 G  >  ESC->        Go to the last line in file.

 m<letter>          Mark the current position with <letter>
 '<letter>          Go to a previously marked position.
 ^X^X               Same as '.

    A mark is any upper-case or lower-case letter.
    Certain marks are predefined.
        ^  means  beginning of the file
        $  means  end of the file

CHANGING FILES
--------------

  :e                Examine a new file.
  ^E^V              Same as :e.
  :n                Examine the next file from the command line.
  :p                Examine the previous file from the command line.
  :d                Delete the current file from the command line list.
  =  ^G  :f         Print current file name.
"""
