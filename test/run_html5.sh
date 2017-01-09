# test javascript in generated html files
# todo generate a js test file for each form processed.
# todo integrate with pytest and travis-ci.org.

# one-time setup to run casperjs
# sudo apt install npm phantomjs
# init step avoids some warnings; see https://github.com/npm/npm/issues/9161
# npm init --yes
# npm install casperjs
# node_modules/casperjs/bin/casperjs selftest
# sudo ln -sf `pwd`/node_modules/casperjs/bin/casperjs /usr/local/bin/casperjs

# just a single manual test file for now
casperjs --local-storage-path=. test forms/f1040.js

