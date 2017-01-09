# similar tests are run automatically in test_opentaxforms.py / TestOtfApi without needing to run_apiserver.sh

# for more details about the restless interface:  https://flask-restless.readthedocs.io/en/stable/index.html

# one time setup
pip install -U httpie  # provides the 'http' executable--see https://httpie.org/

# request all organizations
http 'http://127.0.0.1:5000/api/v1/orgn'

# request form 1040
http 'http://127.0.0.1:5000/api/v1/form?q={"filters":[{"name":"code","op":"eq","val":"1040"}]}'

# request a nonexistent form
http 'http://127.0.0.1:5000/api/v1/form?q={"filters":[{"name":"code","op":"eq","val":"0000"}]}'

# request slots for form 1040 [gives page 1 of 26]
http 'http://127.0.0.1:5000/api/v1/slot?q={"filters":[{"name":"form","op":"has","val":{"name":"code","op":"eq","val":"1040"}}]}'

# request page 2 of the slots for form 1040
http 'http://127.0.0.1:5000/api/v1/slot?page=2&q={"filters":[{"name":"form","op":"has","val":{"name":"code","op":"eq","val":"1040"}}]}'

