find . -name '*.pyc' -exec rm {} \;
find . -name '*.log' -exec rm {} \;
find . -name __pycache__ -exec rm -rf {} \; >& /dev/null
rm -rf script/{z,forms}
rm -rf test/forms_*  # but not forms-*
rm -f {script,test,.}/{*.log,*.prof,failurls.*}
rm -f script/*.sqlite3
rm -rf ./forms
echo avoid sqlite3 timestamp diff: cp ../opentaxforms.sqlite3 test/
