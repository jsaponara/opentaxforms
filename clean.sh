find . -name '*.pyc' -exec rm {} \;
find . -name '*.log' -exec rm {} \;
find . -name __pycache__ -exec rm -rf {} \; >& /dev/null
rm -rf script/{z,forms}
rm -f test/forms/*.{pickl,prof,txt,xml,html,svg} test/forms/static
rm -f {script,test}/{*.log,*.prof,failurls.*}
rm -f script/*.sqlite3
