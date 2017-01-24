0.4.19 (2017-01-24)

- add pylint config file.
- fix or silence all pylint errors.
- remove unused code from ut.py.
- use another project's pylintrc [pylint config file] as a starting point to reduce false positives.
- make linting more fine-grained [pylintrc-ut for ut.py, pylintrc for the rest of the code].
- integrate linting with tox.
- fail the build only for linting errors, not warnings.

0.4.18 (2017-01-19)

- test: separate read-only database file from the overwritten one in test/.
- test: add script to run just the api tests.
- test: make api tests print feedback.
- fixed all linting errors [according to vim/syntastic] [just errors, not warnings].
- ran pep8ify.
- mv opentaxforms.py -> main.py.
- main.py: remove sys.setdefaultencoding [and reload].
- remove pointless path from tox env.
- README.md fixes/updates. landscape.io suggestions.

0.4.17 (2017-01-17)

- move cmds.computeMath to Form.computeMath.
- refactoring cmds.computeMath to reduce function length:
-   move sentence-level (instruction-level) parsing into class Parser.
-   create class CommandParser.

0.4.16 (2017-01-13)

- linting via landscape.io, including shortening long lines, removing unused variables, and refactoring some long functions.
- fixed all broken doctests.
- both cross-module globals, log and cfg, are now importable.

0.4.15 (2017-01-09)

- bugfix: the ignoreCaches option now works.
- bugfix: skip forms setup if dirName is None.
- bugfix: ut.exists now insensitive to trailing slash.
- test: moved from relative to absolute paths so eg py.test works from outside of test/ dir.
- test: reorganize test/ dir: test_* subdirs are disposable, test-* arent.
- test/test_opentaxforms.py: command line options changed and expanded.
- test/test_opentaxforms.py: refactor TestOtfSteps, add test_run_1040_xfa, and finally add a script test to the [pytest] automated tests.
- test/forms/f1040.js,test/run_html5.sh: add casperjs script [to test f1040 html files] and shell script [for context].
- add test/README.md as guide to the test/ directory.
- probe access to phantomjs,casperjs in .travis.yml, hopefully for future integration of html5 tests.
- opentaxforms.py: in main, move form-summarizing code to try-else block.
- cache results of Form.pdfInfo for faster test run.
- add internal option to computeOverlap [for layout boxes; currently done inefficiently, thus costly].
- update 1040 target output file to fix broken test.
- cleanup opentaxforms.py/main.

0.4.14 (2016-12-31)

- mv math.py cmds.py: workaround for tox build failure [tox.Random imports py.math and gets our math.py instead].
- oops apparently gotta incl README for travis build to succeed.
- setup.cfg: git flow release already tags the release, so we dont want bumpversion to do so, otherwise git flow refuses to release.

0.4.13 (2016-12-30)

- gitignore release.sh temp files so they dont affect git status.
- move most of 1100-line main into four new files.
- add Form class.
- domain.py->irs.py.
- extractFillableFields.El derives from dict.
- combined rst format files into a single README file.
- noticed markdown readme is not rendered on pypi, fixing [part of fix is in release.sh].

0.4.12 (2016-12-23)
- bind arrow keys to next/prev page links [for demo video].
- [release.sh remains untracked while it is being tested.]

0.4.11 (2016-12-21)
- allow multiple 'rootForms' via call or commandline.
- output form statuses for external processing.
- clean up "import *".
- add cleanup script.
- merge the missing and spurious categories into the form status message.
- use bumpversion as cookiecutter does.

