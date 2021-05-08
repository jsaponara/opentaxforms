from __future__ import absolute_import
import os
import six
import sys
from itertools import chain
from sqlalchemy import (
    MetaData, create_engine, select, UniqueConstraint)
# from sqlalchemy.exc import ProgrammingError

from . import ut, config
from .ut import log
from .config import cfg

engine, metadata, conn = None, None, None


def unicodify(dic):
    for k, v in dic.items():
        if isinstance(v, six.binary_type):
            dic[k] = six.text_type(v.decode('utf-8'))
    return dic


def connect(appname, **kw):
    # default values
    user = pw = 'user'
    dbname = appname.lower()
    # optionally override defaults
    user = os.environ.get(appname.upper() + '_DBUSER', user)
    pw = os.environ.get(appname.upper() + '_DBPASS', pw)
    dbname = os.environ.get(appname.upper() + '_DBNAME', dbname)
    global conn
    conn, engine, metadata, md = connect_(user=user, pw=pw, db=dbname, **kw)
    return conn, engine, metadata, md


def connect_(**kw):
    # consumes keys from kw: user pw db
    global conn, engine, metadata
    config.setup(**kw)
    if 'dirName' in kw:
        del kw['dirName']
    if 'relaxRqmts' in kw:
        del kw['relaxRqmts']
    usepostgres = kw.get('postgres', False) if cfg is None else cfg.postgres
    if usepostgres:
        kw.setdefault('user', 'postgres')
        kw.setdefault('pw', kw['user'])
        kw.setdefault('db', 'postgres')
        connstr = 'postgresql+psycopg2://%(user)s:%(pw)s@localhost/%(db)s' % kw
        kw.setdefault('echo', False)
    else:
        kw.setdefault('db', 'opentaxforms')
        connstr = kw['dbpath']
        if connstr is None:
            connstr = 'opentaxforms.sqlite3'
        sqlitePrefix = 'sqlite:///'
        if not connstr.lower().startswith(sqlitePrefix):
            connstr = sqlitePrefix + connstr
        del kw['dbpath']
    del kw['user']
    del kw['pw']
    del kw['db']
    if 'postgres' in kw:
        del kw['postgres']
    engine = create_engine(connstr, **kw)
    metadata = MetaData(engine)
    conn = engine.connect()
    metadata.reflect()
    return conn, engine, metadata, ut.Bag(metadata.tables)


def queryIdx(table):
    # nicer indexing for non-dict rows eg row[idx['colname']] becomes
    # row[idx.colname] todo could be replaced by Bag? todo return something
    # like this for every query, not just straight table queries
    '''
        >>> from sqlalchemy import MetaData, Table, Column, Integer, String
        >>> metadata=MetaData()
        >>> test=Table('test', metadata, \
            Column('id', Integer, primary_key=True), \
            Column('name', String, nullable=False, unique=True), \
            Column('addr', String, nullable=False), \
            )
        >>> tq=queryIdx(test)
        >>> tq.id,tq.name,tq.addr
        (0, 1, 2)
        '''
    return ut.ntuple('I' + table.name,
                     [c.name for c in table.columns])(
                        *range(len(table.columns)))


def getUniqueConstraints(table):
    uniqconstraints = chain(
        (c for c in table.constraints if type(c) == UniqueConstraint),
        table.indexes,
        )
    return uniqconstraints


def firstCompleteConstraint(table, kw):
    # return first constraint all of whose fields are in kw, otherwise return
    # kw
    uniqconstraints = getUniqueConstraints(table)
    for ucon in uniqconstraints:
        uniqfields = [c.key for c in ucon.columns]
        if all([field in kw for field in uniqfields]):
            seekfields = [(getattr(table.c, field), kw[field])
                          for field in uniqfields]
            break
    else:
        # found no such constraint, so use all kw entries
        seekfields = [(getattr(table.c, k), v) for k, v in kw.items()]
    return seekfields


def upsert(table, **kw):
    '''
        >>> from sqlalchemy import MetaData, Table, Column, \
                                   Integer, String, select
        >>> from config import setup
        >>> ignoreReturnValue=setup(quiet=True,dirName=None)
        >>> conn,engine,metadata,md=connect('upsert-doctest',dbpath='blah')
        >>> if 'test' in metadata.tables:
        ...   metadata.drop_all(tables=[md.test])
        ...   metadata.remove(md.test)
        >>> test=Table('test', metadata, \
           Column('id', Integer, primary_key=True), \
           Column('name', String, nullable=False, unique=True), \
           Column('addr', String, nullable=False), \
           )
        >>> metadata.create_all()
        >>> upsert(test, name='name1', addr='addr1' )
        1
        >>> upsert(test, name='name1', addr='addr2' )
        1
        >>> conn.execute(select([test.c.addr])).first()
        (u'addr2',)
    '''
    seekfields = firstCompleteConstraint(table, kw)
    datafields = unicodify(kw)
    col, val = seekfields[0]
    where = (col == val)
    for col, val in seekfields[1:]:
        where &= (col == val)
    matches = conn.execute(table.update().where(where).values(**datafields))
    if matches.rowcount == 1:
        # this wasteful select is needed to return inserted_primary_key
        #   and thus be parallel with the insert [rowcount==0] branch
        matches = conn.execute(select([table.c.id], where))
        insertedpk, = matches.first()
    elif matches.rowcount == 0:
        insertedpk, = conn.execute(table.insert(), **kw).inserted_primary_key
    else:
        msg = 'too many rows [%d] in table [%s]' \
            ' match allegedly unique values [%s]' \
            % (matches.rowcount, table, seekfields)
        raise Exception(msg)
    return insertedpk


def selsert(table, **kw):
    '''
        >>> from sqlalchemy import MetaData, Table, Column, Integer, String
        >>> from config import setup
        >>> ignoreReturnValue=setup(quiet=True,dirName=None)
        >>> conn,engine,metadata,md=connect('selsert-doctest',dbpath='blah')
        >>> if 'test' in metadata.tables: metadata.remove(md.test)
        >>> test=Table('test', metadata, \
           Column('id', Integer, primary_key=True), \
           Column('name', String, nullable=False, unique=True), \
           Column('addr', String, nullable=False), \
           )
        >>> metadata.create_all()
        >>> selsert(test, name='name1', addr='addr1' )
        1
        >>> selsert(test, name='name1', addr='addr1' )
        1
    '''
    seekfields = firstCompleteConstraint(table, kw)
    col, val = seekfields[0]
    where = (col == val)
    for col, val in seekfields[1:]:
        where &= (col == val)
    matches = conn.execute(select([table.c.id], where))
    allmatches = matches.fetchall()
    if len(allmatches) == 0:
        insertedpk, = (conn.execute(table.insert(), **unicodify(kw)).
                       inserted_primary_key)
    elif len(allmatches) == 1:
        insertedpk, = allmatches[0]
    else:
        msg = 'too many [%d] rows in table [%s]' \
            ' match allegedly unique values [%s]' \
            % (len(allmatches), table, seekfields)
        raise Exception(msg)
    return insertedpk


# todo switch to a memoize decorator
mem = ut.ddict(dict)


def getbycode(table, mem=mem, **kw):
    def stripifstring(s):
        try:
            return s.strip("\" '")
        except Exception:
            return s
    kw = dict([(k, stripifstring(v)) for k, v in kw.items()])
    if kw['code'] in mem[table.name]:
        i = mem[table.name][kw['code']]
    else:
        whereclause = (table.c.code == kw['code'])
        matches = conn.execute(select([table.c.id], whereclause))
        if matches.returns_rows:
            i, = matches.first()
        else:
            log.debug(kw)
            i = conn.execute(table.insert(), **kw).inserted_primary_key[0]
        mem[table.name][kw['code']] = i
    return i


def getbyname(table, mem=mem, **kw):
    def stripifstring(s):
        try:
            return s.strip("\" '")
        except Exception:
            return s
    kw = dict([(k, stripifstring(v)) for k, v in kw.items()])
    if kw['name'] in mem[table.name]:
        i = mem[table.name][kw['name']]
    else:
        whereclause = (table.c.name == kw['name'])
        matches = conn.execute(select([table.c.id], whereclause))
        if matches.returns_rows:
            i, = matches.first()
        else:
            i = conn.execute(table.insert(), **kw).inserted_primary_key[0]
        mem[table.name][kw['name']] = i
    return i


if __name__ == "__main__":
    args = sys.argv
    if any([arg in args for arg in '-t --testing'.split()]):
        import doctest
        doctest.testmod()
