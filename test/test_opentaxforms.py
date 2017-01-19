#! /usr/bin/env python
'''
    The tests.
'''

from os.path import join as pathjoin
from shutil import copy
from opentaxforms import ut


class TestBase(object):
    '''setup/teardown'''
    def setup_method(self, _):
        '''setup'''
        self.testdir = ut.Resource('test', '').path()
        dbpath = 'sqlite:///' + self.testdir + '/opentaxforms.sqlite3'
        self.default_args = dict(
            # skip cleanupFiles to allow comparison with target output
            # skip=['c'],
            # todo change dbpath to dburl
            dbpath=dbpath,
            )

    def teardown_method(self, _):
        '''post-tests teardown'''
        pass

    def run(self, **kw):
        '''
        run test in child class

        note debug=True in kw will cause output mismatch
             because html pages get debug output
        '''
        kw.update(self.default_args)
        self.dir_name = kw['dirName']
        inputpdf = pathjoin(self.testdir, 'forms-common', 'f1040.pdf')
        self.outdir = pathjoin(self.testdir, self.dir_name, '')
        ut.ensure_dir(self.outdir)
        copy(inputpdf, self.outdir)
        from opentaxforms import main as otfmain
        returnval = otfmain.opentaxforms(
            okToDownload=False,
            **kw)
        if returnval != 0:
            raise Exception('run failed, no output to compare against target')
        self.check_output(**kw)

    def check_output(self, **kw):
        '''compare run output to target output'''
        root_forms = kw.get('rootForms') or ['1040']
        shallow = False
        targetdir = pathjoin(self.testdir, 'forms-targetOutput', '')
        files_to_check = kw.get('filesToCheck') or \
            ['f%s-p1.html' % (form, ) for form in root_forms]

        def fmtmsg(result, verb, file_to_check, outdir, targetdir):
            '''format message'''
            return '{}: output file "{}" in "{}" {} target in "{}"'.format(
                result, file_to_check, outdir, verb, targetdir)
        import filecmp
        for file_to_check in files_to_check:
            files_match = filecmp.cmp(
                pathjoin(self.outdir, file_to_check),
                pathjoin(targetdir, file_to_check),
                shallow)
            if files_match:
                result, verb = 'PASS', 'matches'
                print fmtmsg(result, verb, file_to_check,
                             self.outdir, targetdir)
            else:
                result, verb = 'FAIL', 'does NOT match'
                raise Exception(
                    fmtmsg(result, verb, file_to_check,
                           self.outdir, targetdir))


class TestSteps(TestBase):
    '''
        These 'steps' tests actually run the script.
        run_1040_full runs 'all steps' and thus doesnt
        start with 'test_' because it runs for several seconds
        '''

    # todo use a less complex form than 1040 to speed testing
    def run_1040_full(self, **kw):
        '''full run of form 1040'''
        self.run(
            rootForms=['1040'],
            filesToCheck=['f1040-p1.html'],
            dirName='forms_1040_full',
            ignoreCaches=True,
            **kw
            )

    def test_run_1040_xfa(self, **kw):
        '''xfa-only run of form 1040'''
        dir_name = pathjoin(self.testdir, 'forms_1040_xfa')
        ut.ensure_dir(dir_name)
        # use cached pdf info to speed the run
        pdfinfo = pathjoin(self.testdir, 'forms-common', 'f1040-pdfinfo.pickl')
        copy(pdfinfo, dir_name)
        self.run(
            rootForms=['1040'],
            filesToCheck=['f1040-fmt.xml'],
            dirName=dir_name,
            steps=['x'],
            computeOverlap=False,  # speeds testing
            **kw
            )

    # todo add tests of further steps,
    #      made fast via pickled results of previous step


class TestApiBase(object):
    '''setup/teardown'''
    def setup_method(self, _):
        '''pre-test setup'''
        from opentaxforms.serve import createApp
        # we just read from this db
        dbpath = 'sqlite:///' + ut.Resource(
            'test', 'forms-common/f1040.sqlite3').path()
        # dirName=None means dont look for a forms/ directory
        self.app = createApp(dbpath=dbpath, dirName=None)
        self.client = self.app.test_client()

    def teardown_method(self, _):
        '''post-test teardown'''
        pass


class TestApi(TestApiBase):
    '''test the api'''
    def test_api_orgn(self):
        '''get list of organizations (currently just IRS)'''
        request = '/api/v1/orgn'
        response = self.client.get(request)
        print request, '->', response.data
        assert '"code": "us_irs"' in response.data
        assert response.status_code == 200

    def test_api_f1040(self):
        '''get form 1040'''
        request = (
            '/api/v1/form?q='
            '{"filters":[{"name":"code","op":"eq","val":"1040"}]}')
        response = self.client.get(request)
        print request, '->', response.data
        assert '"title": "Form 1040"' in response.data
        assert response.status_code == 200

    def test_api_noresults(self):
        '''request a nonexistent form'''
        request = (
            '/api/v1/form?q='
            '{"filters":[{"name":"code","op":"eq","val":"0000"}]}')
        response = self.client.get(request)
        print request, '->', response.data
        assert '"num_results": 0' in response.data
        assert response.status_code == 200

    def test_api_filterslots(self):
        '''demo of how to filter
            get all checkbox fields on page 1 of form 1040
        '''
        import json
        url = '/api/v1/slot?q=%s'
        filters = [
            dict(name='inptyp', op='eq', val='k'),  # k=checkbox [vs x=textbox]
            dict(name='page', op='eq', val=1),  # on page 1
            dict(name='form', op='has',
                 val=dict(name='code', op='eq', val='1040')),  # of form 1040
            ]
        paramstring = json.dumps(dict(filters=filters))
        request = url % (paramstring, )
        response = self.client.get(request)
        print request, '->', response.data
        assert response.status_code == 200
        assert '"num_results": 15' in response.data


def main(args):
    ''' for commandline invocation '''
    def usage():
        ''' print usage note '''
        print 'usage: "%s [-q|-s|-f|-x|-a]"\n' \
              '-q=quick script tests\n' \
              '-s=slow script tests\n' \
              '-f=full 1040\n' \
              '-x=xfa-only 1040\n' \
              '-a=api tests' % (args[0], )
    if len(args) >= 2:
        if any(arg in args for arg in ('-q', '-s', '-f', '-x')):
            step_test_runner = TestSteps()
            step_test_runner.setup_method(0)
            if '-q' in args:
                step_test_runner.test_run_1040_xfa()
            elif '-s' in args:
                step_test_runner.run_1040_full()
            elif '-x' in args:
                step_test_runner.test_run_1040_xfa()
            elif '-f' in args:
                step_test_runner.run_1040_full()
        elif '-a' in args:  # run api tests
            api_test_runner = TestApi()
            api_test_runner.setup_method(0)

            api_test_runner.test_api_orgn()
            api_test_runner.test_api_f1040()
            api_test_runner.test_api_noresults()
            api_test_runner.test_api_filterslots()

        else:
            usage()

    else:
        usage()


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
