#! /usr/bin/env python

from opentaxforms import ut

class TestOtfBase(object):
    def setup_method(self, _):
        self.dbpath='sqlite:///'+ut.Resource('test','opentaxforms.sqlite3').path()
    def teardown_method(self, _):
        pass
class TestOtfSteps(TestOtfBase):
    '''
        these tests actually run the script
        they dont start with 'test_' because
        they each take several seconds to run
        '''
    def run_1040(self):
        from opentaxforms import opentaxforms as otf
        # skip cleanupFiles to allow comparison with target output
        returnval=otf.opentaxforms(
            dirName='forms',rootForms=['1040'],
            okToDownload=False,skip=['c'],
            # todo change dbpath to dburl
            dbpath=self.dbpath,
            )
        if returnval!=0:
            raise Exception('run failed, no output to compare against target')
        import filecmp
        shallow=False
        fileToCheck='f1040-p1.html'
        outdir,targetdir='forms/','forms-targetOutput/'
        filesMatch=filecmp.cmp(outdir+fileToCheck,targetdir+fileToCheck,shallow)
        def fmtmsg(result,verb):
            return '{}: output file "{}" in "{}" {} target in "{}"'.format(
                result,fileToCheck,outdir,verb,targetdir)
        if filesMatch:
            result,verb='PASS','matches'
            print fmtmsg(result,verb)
        else:
            result,verb='FAIL','does NOT match'
            raise Exception(fmtmsg(result,verb))

class TestOtfApiBase(object):
    def setup_method(self, _):
        from opentaxforms.serve import createApp
        dbpath='sqlite:///'+ut.Resource('test','opentaxforms.sqlite3').path()
        self.app=createApp(dbpath=dbpath)
        self.client=self.app.test_client()
    def teardown_method(self, _):
        pass
class TestOtfApi(TestOtfApiBase):
    def test_api_orgn(self):
        # get list of organizations (currently just IRS)
        response=self.client.get('/api/v1/orgn')
        assert '"code": "us_irs"' in response.data
        assert response.status_code==200
    def test_api_f1040(self):
        # get form 1040
        response=self.client.get('/api/v1/form?q={"filters":[{"name":"code","op":"eq","val":"1040"}]}')
        assert '"title": "Form 1040"' in response.data
        assert response.status_code==200
    def test_api_noresults(self):
        # request a nonexistent form
        response=self.client.get('/api/v1/form?q={"filters":[{"name":"code","op":"eq","val":"0000"}]}')
        assert '"num_results": 0' in response.data
        assert response.status_code==200
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
        assert '"num_results": 15' in response.data

def main(args):
    def usage():
        print 'usage: "%s -f" for fasttests or "%s -s" for slow tests'%(args[0],args[0])
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

            testRunner.run_1040()
        else:
            usage()

    else:
        usage()

if __name__=='__main__':
    import sys
    sys.exit(main(sys.argv))

