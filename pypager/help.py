import sys

import prompt_toolkit
from prompt_toolkit.formatted_text import HTML

import pypager

python_version = sys.version_info
ptk_version = prompt_toolkit.__version__
pypager_version = pypager.__version__


HELP = (
    HTML(
        """
            <title>SUMMARY OF COMMANDS</title>

 <keys> h  H             </keys> Display this help.
 <keys> q  Q  ZZ         </keys> Exit.

 <line>------------------------------------------------------</line>

  <subtitle> Moving </subtitle>

 <keys>e  ^E  j  ^N  CR  </keys> Forward one line.
 <keys>y  ^Y  k  ^K  ^P  </keys> Backward one line.
 <keys>f  ^F  ^V  SPACE  </keys> Forward one window.
 <keys>b  ^B  ESC-v      </keys> Backward one window.
 <keys>d  ^D             </keys> Forward one half-window.
 <keys>u  ^U             </keys> Backward one half-window.
 <keys>ESC-)  RightArrow </keys> Left one half screen width.
 <keys>ESC-(  LeftArrow  </keys> Right one half screen width.
 <keys>F                 </keys> Forward forever; like "tail -f"
 <keys>r  R  ^R  ^L      </keys> Repaint screen.

  <subtitle> SEARCHING </subtitle>

 <keys>/pattern          </keys> Search forward.
 <keys>?pattern          </keys> Search backward.
 <keys>n                 </keys> Repeat previous search.
 <keys>N                 </keys> Repeat previous search in reverse direction.
 <keys>ESC-u             </keys> Undo (toggle) search highlighting.

  <subtitle> JUMPING </subtitle>

 <keys> g  &lt;  ESC-&lt;</keys>       Go to the first line in file.
 <keys> G  &gt;  ESC-&gt;</keys>       Go to the last line in file.

 <keys>m&lt;letter&gt;   </keys>       Mark the current position with &lt;letter&gt;
 <keys>'&lt;letter&gt;   </keys>       Go to a previously marked position.
 <keys>^X^X              </keys> Same as <keys>'.</keys>

    A mark is any upper-case or lower-case letter.
    Certain marks are predefined.
        <keys>^</keys>  means  beginning of the file
        <keys>$</keys>  means  end of the file

  <subtitle> CHANGING FILES </subtitle>

  <keys>:e               </keys> Examine a new file.
  <keys>^E^V             </keys> Same as :e.
  <keys>:n               </keys> Examine the next file from the command line.
  <keys>:p               </keys> Examine the previous file from the command line.
  <keys>:d               </keys> Delete the current file from the command line list.
  <keys>=  ^G  :f        </keys> Print current file name.

  <subtitle> Extras </subtitle>

  <keys>w                </keys> Enable/disable <b>line wrapping</b>.

  <subtitle> About Pypager </subtitle>

  Pypager is a <u>prompt_toolkit</u> application.

  - Pypager version:        <version>%s</version>
  - Python version:         <version>%s.%s.%s</version>
  - prompt_toolkit version: <version>%s</version>

"""
    )
    % (
        pypager_version,
        python_version[0],
        python_version[1],
        python_version[2],
        ptk_version,
    )
)
