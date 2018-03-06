#! /usr/bin/env python

# 'Otf' below [eg TestOtfSteps]  is 'OpenTaxForms'

from __future__ import print_function
import os
import os.path as osp
import shutil
from subprocess import check_output
from opentaxforms import ut

def checkDependencies():
    # todo read dependencies from a central location
    dependencies = ['pdf2svg']
    missingDeps = []
    for dep in dependencies:
        try:
            check_output(dep)
        except OSError:
            missingDeps.append(dep)
        except:
            pass
    if missingDeps:
        raise Exception('missing dependencies: ' + str(missingDeps) + '; see README.')

class TestOtfBase(object):
    def setup_method(self, _):
        dirName = 'forms'
        theForm = 'f1040.pdf'
        dbpath='sqlite:///'+ut.Resource('test','opentaxforms.sqlite3').path()
        if not osp.exists(dirName):
            os.makedir(dirName)
        formpath = osp.join(dirName, theForm)
        if not osp.exists(formpath):
            formResourcePath = ut.Resource('test', osp.join('forms-common', theForm)).path()
            shutil.copy(formResourcePath, formpath)
        filesToCleanup = 'failurls.pickl'.split()
        for f in filesToCleanup:
            if osp.exists(f):
                os.remove(f)
        self.defaultArgs=dict(
            # skip cleanupFiles to allow comparison with target output
            #skip=['c'],
            dirName = dirName,
            # todo change dbpath to dburl
            dbpath=dbpath,
            )
    def teardown_method(self, _):
        pass
    def run(self,**kw):
        checkDependencies()
        #rootForms=kw.get('rootForms') or ['1040']
        rootForms=kw.get('rootForms') or '1040'
        filesToCheck=kw.get('filesToCheck') or ['f%s-p1.html'%(form,) for form in rootForms]
        kw.update(self.defaultArgs)
        from opentaxforms import main as otf
        returnval=otf.opentaxforms(
            okToDownload=False,
            **kw)
        if returnval!=0:
            raise Exception('run failed, no output to compare against target')
        import filecmp
        shallow=False
        outdir = 'forms'
        targetdir= ut.Resource('test', 'forms-targetOutput').path()
        def fmtmsg(result,verb):
            return '{}: output file "{}" in "{}" {} target in "{}"'.format(
                result,fileToCheck,outdir,verb,targetdir)
        for fileToCheck in filesToCheck:
            filesMatch=filecmp.cmp(
                osp.join(outdir, fileToCheck),
                osp.join(targetdir, fileToCheck),
                shallow)
            if filesMatch:
                result,verb='PASS','matches'
                print(fmtmsg(result,verb))
            else:
                result,verb='FAIL','does NOT match'
                raise Exception(fmtmsg(result,verb))
class TestOtfSteps(TestOtfBase):
    '''
        These 'steps' tests actually run the script.
        run_1040_full runs 'all steps' and thus doesnt
        start with 'test_' because it runs for several seconds
        '''
    # todo use a less complex form than 1040 to speed testing
    def run_1040_full(self):
        self.run(
            #rootForms=['1040'],
            rootForms='1040',
            filesToCheck=['f1040-p1.html'],
            )
    def test_run_1040_xfa(self):
        self.run(
            #rootForms=['1040'],
            rootForms='1040',
            filesToCheck=['f1040-fmt.xml'],
            steps=['x'],
            # speeds testing
            computeOverlap=False,
            )
    # todo add tests of further steps,
    # todo   made fast via pickled results of previous step

class TestOtfApiBase(object):
    def setup_method(self, _):
        from opentaxforms.serve import createApp
        dbResourcePath = ut.Resource('test',
            osp.join('forms-common', 'f1040.sqlite3')).path()
        dbFilePath = osp.join('test', 'opentaxforms.sqlite3')
        shutil.copy(dbResourcePath, dbFilePath)
        dbpath='sqlite:///' + dbFilePath
        self.app=createApp(dbpath=dbpath)
        self.client=self.app.test_client()
    def teardown_method(self, _):
        pass
class TestOtfApi(TestOtfApiBase):
    def test_api_orgn(self):
        # get list of organizations (currently just IRS)
        response=self.client.get('/api/v1/orgn')
        assert response.status_code == 200
        assert b'"code": "us_irs"' in response.data
    def test_api_f1040(self):
        # get form 1040
        response=self.client.get('/api/v1/form?q={"filters":[{"name":"code","op":"eq","val":"1040"}]}')
        assert response.status_code == 200
        assert b'"title": "Form 1040"' in response.data
    def test_api_noresults(self):
        # request a nonexistent form
        response=self.client.get('/api/v1/form?q={"filters":[{"name":"code","op":"eq","val":"0000"}]}')
        assert response.status_code == 200
        assert b'"num_results": 0' in response.data
    def test_api_filterslots(self):
        # get all checkbox fields on page 1 of form 1040
        import json
        url = '/api/v1/slot?q=%s'
        filters = [
            dict(name='inptyp', op='eq', val='k'),  # inputtype is k for checkbox [vs x for textbox]
            dict(name='page'  , op='eq', val=1),    # on page 1
            dict(name='form', op='has', val=dict(name='code',op='eq',val='1040')),    # of form 1040
            ]
        paramstring = json.dumps(dict(filters=filters))
        response = self.client.get(url%(paramstring,))
        assert response.status_code == 200
        assert b'"num_results": 15' in response.data

def main(args):
    def usage():
        print('usage: "%s -f" for fasttests or "%s -s" for slow tests'%(args[0],args[0]))
    if len(args)==2:
        if args[1]=='-f':
            testRunner=TestOtfApi()
            testRunner.setup_method(0)

            testRunner.test_api_orgn()
            testRunner.test_api_f1040()
            testRunner.test_api_noresults()
            testRunner.test_api_filterslots()

        elif args[1]=='-s': # run slow tests
            testRunner=TestOtfSteps()
            testRunner.setup_method(0)

            testRunner.run_1040_full()
        else:
            usage()

    else:
        usage()

if __name__=='__main__':
    import sys
    sys.exit(main(sys.argv))

