#!/bin/bash
# automating https://cookiecutter-pypackage.readthedocs.io/en/latest/pypi_release_checklist.html
# UNTESTED!
# todo bumpversion 'patch' arg should be overridable
# todo format Changelog?
# todo register at pypi if needed

getver() { echo `python -c 'from opentaxforms.version import appversion;print appversion'` ; }
# ensure no pending changes...
if [ `git status --porcelain >& /dev/null` ] ; then
	echo there are uncommitted changes or extra files:
	git status --porcelain
	exit
else
	echo PASS no uncommitted changes.
fi
# ensure no pending features...or that a release .is. pending?
git branch | grep -q feature
if [ $? = 0 ] ; then
	echo features are pending.
	exit
else
	echo PASS no pending features.
fi
oldVersionTag=`getver`
git log --pretty=format:%s $oldVersionTag..HEAD >> changes-recent.log
bumpversion patch
newVersionTag=`getver`
if [ $oldVersionTag = $newVersionTag ] ; then
	echo oops bumpversion didnt change the version
	exit
else
	echo PASS moving from $oldVersionTag to $newVersionTag
fi
(echo $newVersionTag ; cat changes-recent.log) >> CHANGES.md
git commit -m "Changelog for upcoming release $newVersionTag"
exit
git flow release start $newVersionTag
python setup.py develop
tox  # or pytest or py.test
if [ $? = 0 ] ; then
	echo tests passed.
else
	echo tests FAILed.
	exit
fi
ls dist/*-$newVersionTag.* >& /dev/null
if [ $? = 0 ] ; then
	echo version $newVersionTag already distributed according to "ls dist/*$newVersionTag*"
else
	python setup.py sdist # test this: bdist
	#twine upload dist/opentaxforms-$newVersionTag.tar.gz
	twine upload dist/opentaxforms-$newVersionTag.*
fi
# rm -r changes-recent.log

