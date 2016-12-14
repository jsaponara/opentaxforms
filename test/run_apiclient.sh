
# for more details:  https://flask-restless.readthedocs.io/en/stable/index.html
pip install httpie

# all organizations
http 'http://127.0.0.1:5000/api/v1/orgn'

# form 1040
http 'http://127.0.0.1:5000/api/v1/form?q={"filters":[{"name":"code","op":"eq","val":"1040"}]}'

# a nonexistent form
http 'http://127.0.0.1:5000/api/v1/form?q={"filters":[{"name":"code","op":"eq","val":"0000"}]}'

# slots for form 1040 [gives page 1 of 26]
http 'http://127.0.0.1:5000/api/v1/slot?q={"filters":[{"name":"form","op":"has","val":{"name":"code","op":"eq","val":"1040"}}]}'

# page 2 of the slots for form 1040
http 'http://127.0.0.1:5000/api/v1/slot?page=2&q={"filters":[{"name":"form","op":"has","val":{"name":"code","op":"eq","val":"1040"}}]}'

