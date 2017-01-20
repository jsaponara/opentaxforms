find . -name '*.pyc' -exec rm {} \;
find . -name '*.log' -exec rm {} \;
find . -name __pycache__ -exec rm -rf {} \; >& /dev/null
rm -rf script/{z,forms}
rm -rf test/forms_*  # but not forms-*
rm -f {script,test,.}/{*.log,*.prof,*.sqlite3,*.localstorage,failurls.*}
rm -f script/*.sqlite3
rm -rf ./forms ./tmp.*
