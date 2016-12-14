
import ut
from sqlalchemy import MetaData, create_engine, select
from sqlalchemy.exc import ProgrammingError
from itertools import chain

engine,metadata,conn=None,None,None

def unicodify(dic):
    for k,v in dic.iteritems():
        if type(v)==str:
            dic[k]=unicode(v)
    return dic

def connect(appname,**kw):
    # default values
    user=pw='user'
    dbname=appname.lower()
    # optionally override defaults
    import os
    user=os.environ.get(appname.upper()+'_DBUSER',user)
    pw=os.environ.get(appname.upper()+'_DBPASS',pw)
    dbname=os.environ.get(appname.upper()+'_DBNAME',dbname)
    global conn
    conn,engine,metadata,md=connect_(user=user,pw=pw,db=dbname,**kw)
    return conn,engine,metadata,md

def connect_(**kw):
    # consumes keys from kw: user pw db
    global conn,engine,metadata
    from config import cfg
    usepostgres=kw.get('postgres',False) if cfg is None else cfg.postgres
    if usepostgres:
        kw.setdefault('user','postgres')
        kw.setdefault('pw',kw['user'])
        kw.setdefault('db','postgres')
        connstr='postgresql+psycopg2://%(user)s:%(pw)s@localhost/%(db)s'%kw
        kw.setdefault('echo',False)
    else:
        kw.setdefault('db','opentaxforms')
        connstr=kw['dbpath']
        if connstr is None:
            connstr='opentaxforms.sqlite3'
        sqlitePrefix='sqlite:///'
        if not connstr.lower().startswith(sqlitePrefix):
            connstr=sqlitePrefix+connstr
        del kw['dbpath']
    del kw['user']
    del kw['pw']
    del kw['db']
    if 'postgres' in kw: del kw['postgres']
    engine=create_engine(connstr,**kw)
    metadata=MetaData(engine)
    conn=engine.connect()
    metadata.reflect()
    return conn,engine,metadata,ut.Bag(metadata.tables)

def queryIdx(table):
    # nicer indexing for non-dict rows
    # eg row[idx['colname']] becomes row[idx.colname]
    # todo could be replaced by Bag?
    # todo return something like this for every query, not just straight table queries
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
    return ntuple('I'+table.name,[c.name for c in table.columns])(*range(len(table.columns)))

def deleteall():
    # ideally would compute graph of ForeignKey deps via table.foreign_keys
    # needed because metadata.drop_all() doesnt wk for tables w/ foreign keys but fails silently!
    # todo doesnt wk cuz didnt declare the cascade?  ForeignKey('parent.id',onupdate="CASCADE",ondelete="CASCADE" in http://docs.sqlalchemy.org/en/latest/core/constraints.html  [tho CASCADE not supported in sqlite before Cascading delete isn't supported by sqlite until version 3.6.19]
    for i in range(len(metadata.tables)):
        for tname,t in metadata.tables.iteritems():
            try:
                conn.execute(t.delete())
            except:
                pass
        metadata.clear()
        metadata.reflect()
    # should be empty by now, else there's a problem
    nonemptytables=[t for t in metadata.tables if conn.execute(t.count()).first()!=(0,)]
    if nonemptytables:
        raise Exception('failed to delete tables [%s]'%(nonemptytables,))
def dropall():
    # ideally would compute graph of ForeignKey deps via table.foreign_keys
    # needed because metadata.drop_all() doesnt wk for tables w/ foreign keys but fails silently!
    # todo doesnt wk cuz didnt declare the cascade?  ForeignKey('parent.id',onupdate="CASCADE",ondelete="CASCADE" in http://docs.sqlalchemy.org/en/latest/core/constraints.html  [tho CASCADE not supported in sqlite before Cascading delete isn't supported by sqlite until version 3.6.19]
    for i in range(len(metadata.tables)):
        for tname,t in metadata.tables.iteritems():
            try:
                t.drop()
            except:
                pass
        metadata.clear()
        metadata.reflect()
    # should be empty by now, else there's a problem
    if metadata.tables:
        raise Exception('cannot drop tables [%s]'%(metadata.tables.keys()))

def upsert(table,**kw):
    '''
        >>> from sqlalchemy import MetaData, Table, Column, \
                                   Integer, String, select
        >>> conn,engine,metadata,md=connect()
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
    from sqlalchemy import UniqueConstraint
    uniqconstraints=chain(
        (c for c in table.constraints if type(c)==UniqueConstraint),
        table.indexes,
        )
    # use first constraint all of whose fields are in kw 
    for ucon in uniqconstraints:
        uniqfields=[c.key for c in ucon.columns]
        if all([field in kw for field in uniqfields]):
            seekfields=[(getattr(table.c,field),kw[field]) for field in uniqfields]
            break
    else:
        # found no such constraint, so use all kw entries
        seekfields=[(getattr(table.c,k),v) for k,v in kw.iteritems()]
    datafields=unicodify(kw)
    col,val=seekfields[0]
    where=(col==val)
    for col,val in seekfields[1:]:
        where&=(col==val)
    matches=conn.execute(table.update().where(where).values(**datafields))
    if matches.rowcount==1:
        # this wasteful select is needed to return inserted_primary_key
        #   and thus be parallel with the insert [rowcount==0] branch
        matches=conn.execute(select([table.c.id],where))
        insertedpk,=matches.first()
    elif matches.rowcount==0:
        insertedpk,=conn.execute(table.insert(),**kw).inserted_primary_key
    else:
        msg='too many rows [%d] in table [%s]' \
            ' match allegedly unique values [%s]' \
            %(matches.rowcount,table,seekfields)
        raise Exception()
    return insertedpk

def selsert(table,**kw):
    '''
        >>> from sqlalchemy import MetaData, Table, Column, Integer, String
        >>> conn,engine,metadata,md=connect()
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
    from sqlalchemy import UniqueConstraint
    uniqconstraints=chain(
        (c for c in table.constraints if type(c)==UniqueConstraint),
        table.indexes,
        )
    # use first constraint all of whose fields are in kw 
    for ucon in uniqconstraints:
        uniqfields=[c.key for c in ucon.columns]
        if all([field in kw for field in uniqfields]):
            seekfields=[(getattr(table.c,field),kw[field]) for field in uniqfields]
            break
    else:
        # found no such constraint, so use all kw entries
        seekfields=[(getattr(table.c,k),v) for k,v in kw.iteritems()]
    col,val=seekfields[0]
    where=(col==val)
    for col,val in seekfields[1:]:
        where&=(col==val)
    matches=conn.execute(select([table.c.id],where))
    allmatches=matches.fetchall()
    if len(allmatches)==0:
        insertedpk,=conn.execute(table.insert(),**unicodify(kw)).inserted_primary_key
    elif len(allmatches)==1:
        insertedpk,=allmatches[0]
    else:
        msg='too many [%d] rows in table [%s]' \
            ' match allegedly unique values [%s]' \
            %(len(allmatches),table,seekfields)
        raise Exception(msg)
    return insertedpk

# todo switch to a memoize decorator
mem=ut.ddict(dict)

def getbycode(table,mem=mem,**kw):
    def stripifstring(s):
        try:
            return s.strip("\" '")
        except:
            return s
    kw=dict([(k,stripifstring(v)) for k,v in kw.iteritems()])
    if kw['code'] in mem[table.name]:
        i=mem[table.name][kw['code']]
    else:
        whereclause=(table.c.code==kw['code'])
        matches=conn.execute(select([table.c.id],whereclause))
        if matches.returns_rows:
            i,=matches.first()
        else:
            ppr(kw)
            i=conn.execute(table.insert(),**kw).inserted_primary_key[0]
        mem[table.name][kw['code']]=i
    return i
def getbyname(table,mem=mem,**kw):
    def stripifstring(s):
        try:
            return s.strip("\" '")
        except:
            return s
    kw=dict([(k,stripifstring(v)) for k,v in kw.iteritems()])
    if kw['name'] in mem[table.name]:
        i=mem[table.name][kw['name']]
    else:
        whereclause=(table.c.name==kw['name'])
        matches=conn.execute(select([table.c.id],whereclause))
        if matches.returns_rows:
            i,=matches.first()
        else:
            i=conn.execute(table.insert(),**kw).inserted_primary_key[0]
        mem[table.name][kw['name']]=i
    return i


if __name__=="__main__":
    import sys
    args=sys.argv
    if any([arg in args for arg in '-t --testing'.split()]):
        import doctest; doctest.testmod()

