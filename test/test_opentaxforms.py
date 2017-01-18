#! /usr/bin/env python

# 'Otf' below [eg TestOtfSteps]  is 'OpenTaxForms'

import os
from os.path import join as pathjoin
from shutil import copy
from opentaxforms import ut


class TestOtfBase(object):
    def setup_method(self, _):
        self.testdir = ut.Resource('test', '').path()
        dbpath = 'sqlite:///' + self.testdir + '/opentaxforms.sqlite3'
        self.defaultArgs = dict(
            # skip cleanupFiles to allow comparison with target output
            #skip=['c'],
            # todo change dbpath to dburl
            dbpath=dbpath,
            )

    def teardown_method(self, _):
        pass

    def ensureDir(self, folder):
        if not ut.exists(folder):
            os.makedirs(folder)

    def run(self, **kw):
        # note debug=True in kw will cause output mismatch because html pages get debug output
        rootForms = kw.get('rootForms') or ['1040']
        filesToCheck = kw.get('filesToCheck') or ['f%s-p1.html' % (form, ) for form in rootForms]
        kw.update(self.defaultArgs)
        self.dirName = kw['dirName']
        inputpdf = pathjoin(self.testdir, 'forms-common', 'f1040.pdf')
        outdir = pathjoin(self.testdir, self.dirName, '')
        self.ensureDir(outdir)
        copy(inputpdf, outdir)
        from opentaxforms import opentaxforms as otf
        returnval = otf.opentaxforms(
            okToDownload=False,
            **kw)
        if returnval != 0:
            raise Exception('run failed, no output to compare against target')
        import filecmp
        shallow = False
        targetdir = pathjoin(self.testdir, 'forms-targetOutput', '')

        def fmtmsg(result, verb):
            return '{}: output file "{}" in "{}" {} target in "{}"'.format(
                result, fileToCheck, outdir, verb, targetdir)
        for fileToCheck in filesToCheck:
            filesMatch = filecmp.cmp(
                pathjoin(outdir, fileToCheck),
                pathjoin(targetdir, fileToCheck),
                shallow)
            if filesMatch:
                result, verb = 'PASS', 'matches'
                print fmtmsg(result, verb)
            else:
                result, verb = 'FAIL', 'does NOT match'
                raise Exception(fmtmsg(result, verb))


class TestOtfSteps(TestOtfBase):
    '''
        These 'steps' tests actually run the script.
        run_1040_full runs 'all steps' and thus doesnt
        start with 'test_' because it runs for several seconds
        '''

    # todo use a less complex form than 1040 to speed testing
    def run_1040_full(self, **kw):
        self.run(
            rootForms=['1040'],
            filesToCheck=['f1040-p1.html'],
            dirName='forms_1040_full',
            ignoreCaches=True,
            **kw
            )

    def test_run_1040_xfa(self, **kw):
        dirName = pathjoin(self.testdir, 'forms_1040_xfa')
        self.ensureDir(dirName)
        # use cached pdf info to speed the run
        pdfinfo = pathjoin(self.testdir, 'forms-common', 'f1040-pdfinfo.pickl')
        copy(pdfinfo, dirName)
        self.run(
            rootForms=['1040'],
            filesToCheck=['f1040-fmt.xml'],
            dirName=dirName,
            steps=['x'],
            computeOverlap=False,  # speeds testing
            **kw
            )

    # todo add tests of further steps, made fast via pickled results of previous step

class TestOtfApiBase(object):
    def setup_method(self, _):
        from opentaxforms.serve import createApp
        dbpath = 'sqlite:///' + ut.Resource('test', 'opentaxforms.sqlite3').path()
        # dirName=None means dont look for a forms/ directory
        self.app = createApp(dbpath=dbpath, dirName=None)
        self.client = self.app.test_client()

    def teardown_method(self, _):
        pass


class TestOtfApi(TestOtfApiBase):
    def test_api_orgn(self):
        # get list of organizations (currently just IRS)
        response = self.client.get('/api/v1/orgn')
        assert '"code": "us_irs"' in response.data
        assert response.status_code == 200

    def test_api_f1040(self):
        # get form 1040
        response = self.client.get('/api/v1/form?q={"filters":[{"name":"code","op":"eq","val":"1040"}]}')
        assert '"title": "Form 1040"' in response.data
        assert response.status_code == 200

    def test_api_noresults(self):
        # request a nonexistent form
        response = self.client.get('/api/v1/form?q={"filters":[{"name":"code","op":"eq","val":"0000"}]}')
        assert '"num_results": 0' in response.data
        assert response.status_code == 200

    def test_api_filterslots(self):
        # get all checkbox fields on page 1 of form 1040
        import json
        url = '/api/v1/slot?q=%s'
        filters = [
            dict(name='inptyp', op='eq', val='k'),  # inputtype is k for checkbox [vs x for textbox]
            dict(name='page', op='eq', val=1),  # on page 1
            dict(name='form', op='has', val=dict(name='code', op='eq', val='1040')),  # of form 1040
            ]
        paramstring = json.dumps(dict(filters=filters))
        response = self.client.get(url % (paramstring, ))
        assert response.status_code == 200
        assert '"num_results": 15' in response.data


def main(args):
    def usage():
        print 'usage: "%s [-q|-s|-f|-x|-a]"\n-q=quick script tests\n-s=slow script tests\n-f=full 1040\n-x=xfa-only 1040\n-a=api tests' % (args[0], )
    if len(args) >= 2:
        if any(arg in args for arg in ('-q', '-s', '-f', '-x')):
            testRunner = TestOtfSteps()
            testRunner.setup_method(0)
            if '-q' in args:
                testRunner.test_run_1040_xfa()
            elif '-s' in args:
                testRunner.run_1040_full()
            elif '-x' in args:
                testRunner.test_run_1040_xfa()
            elif '-f' in args:
                testRunner.run_1040_full()
        elif '-a' in args:  # run api tests
            testRunner = TestOtfApi()
            testRunner.setup_method(0)

            testRunner.test_api_orgn()
            testRunner.test_api_f1040()
            testRunner.test_api_noresults()
            testRunner.test_api_filterslots()

        else:
            usage()

    else:
        usage()

if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
