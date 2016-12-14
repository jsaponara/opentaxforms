-- invoke as: . db.sh
-- otf=opentaxforms
create role otfuser with login;
\password otfuser
create database otfdb;
grant all on database otfdb to otfuser;
