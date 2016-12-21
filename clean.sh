find . -name '*.pyc' -exec rm {} \;
find . -name '*.log' -exec rm {} \;
find . -name __pycache__ -exec rm -rf {} \; >& /dev/null
rm -rf script/{z,forms}
rm -f test/forms/*[tlgc]
rm -f {script,test}/failurls.*
rm -f script/*.sqlite3
