# basic postgres setup
# note: this is optional--opentaxforms defaults to sqlite database built into python
sudo -u postgres psql -v ON_ERROR_STOP=1 -f $PWD/db.sql postgres
