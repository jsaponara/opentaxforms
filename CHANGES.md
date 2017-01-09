0.4.15 (2017-01-09)

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

