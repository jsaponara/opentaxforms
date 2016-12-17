ver=`python -c 'from opentaxforms.version import appversion;print appversion'`
ls dist/*$ver* >& /dev/null
if [ $? = 0 ] ; then
	echo version $ver already distributed according to "ls dist/*$ver*"
else
	python setup.py sdist # test this: bdist
	#twine upload dist/opentaxforms-$ver.tar.gz
	twine upload dist/opentaxforms-$ver.*
fi

