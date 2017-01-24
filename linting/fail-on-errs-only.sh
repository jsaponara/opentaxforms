#!/bin/bash

# fail the tox build if pylint returns fatal (1) | error (2)

pylint --rcfile=linting/pylintrc --ignore=ut.py opentaxforms test/test_opentaxforms.py
if [ $(($? & 3)) -ne 0 ]; then
    echo "FAIL general linting: errors occurred"
    exit 1
else
    echo "PASS general linting"
fi

pylint --rcfile=linting/pylintrc-ut opentaxforms/ut.py
if [ $(($? & 3)) -ne 0 ]; then
    echo "FAIL ut linting: errors occurred"
    exit 1
else
    echo "PASS ut linting"
fi

exit 0
