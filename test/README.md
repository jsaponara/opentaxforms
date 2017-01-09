
Here we test the three phases of OpenTaxForms operation.  All three types of testing
are merely manual and very preliminary. 

  - The otf.py script generates database entries and html files (in the [forms/](forms/)
    directory). 
    To test, we compare the generated html with the target output in
    [forms-targetOutput/](forms-targetOutput/).
    Currently we have a full run of the 1040 form and a faster-but-partial run; both are
    built into [test_opentaxforms.py](test_opentaxforms.py), but only the faster one is
    named "test_" so that pytest can find it.  Scripts [run_slowtests](run_slowtests.sh) and
    [run_fasttests](run_fasttests.sh) give manual access to both sets of tests.
  - The database (in opentaxforms.sqlite3) is served (by [serve.py](../opentaxforms/serve.py)/main)
    via a ReSTful API using [Flask-Restless](http://flask-restless.readthedocs.io/).
    The automated test compares the result of a few API calls over http with the
    expected values in [test_opentaxforms.py](test_opentaxforms.py).
    Manual scripts run_apiclient and run_apiserver perform similar tests with a local
    server running.
  - The html files contain javascript code to automate the tax arithmetic (mostly
    sums and differences among lines).  The [run_html5](run_html5.sh) script uses casperjs (built
    on phantomjs) for headless testing of the arithmetic.  These tests will be
    automated via pytest (ie run from [test_opentaxforms.py](test_opentaxforms.py)) when I have configured
    .travis.yml to make casperjs and phantomjs available.

Finally a [run_commandline](run_commandline.sh) script demonstrates the command line.

