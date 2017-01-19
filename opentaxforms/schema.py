#!/usr/bin/env python

'''
form=blank forms
orgn=organization that publishes the form
slot=fillable slot in a form
'''
#from sys import exit  # exit is builtin??
from ut import Bag, CharEnum, Qnty
from config import cfg
import db
from irs import computeTitle as computeFormTitle
from version import appname
from sqlalchemy import (
    Table, Column, Integer, SmallInteger, String,
    DateTime, Enum, ForeignKey, Boolean,
    UniqueConstraint, CheckConstraint, CHAR, func)
from sqlalchemy.exc import ProgrammingError

conn = None
tableInfo = None


class Unit(CharEnum):
    dollars = 'd'
    cents = 'c'


class XmlType(CharEnum):
    field = 'f'
    draw = 'd'


class InputType(CharEnum):
    text = 'x'
    check = 'k'


class Op(CharEnum):
    add = '+'
    sub = '-'
    mul = '*'
    div = '/'
    copy = '='
    unkn = '?'


def createdb(dbname):
    try:
        conn.execute('CREATE DATABASE %s' % (dbname))
    except ProgrammingError, exc:
        if 'already exists' not in str(exc).lower():
            print exc
            exit()


def dropTableCascade(table, connection):
    connection.execute('drop table "%s" cascade' % (table.name))


def dropAll(metadata, connection):
    for tablename, table in metadata.tables.iteritems():
        dropTableCascade(table, connection)


def schema():
    # construct schema and create tables if they dont exist

    global tableInfo
    tableInfo = {}
    # no sense in creating the database itself cuz cannot connect to a db that
    # doesnt exist try: conn.execute('CREATE DATABASE %s'%(dbname)) except
    # ProgrammingError,exc: if 'already exists' not in str(exc): print exc
    # exit() todo try connecting to db postgres and creating new db from there;
    # grant privs too

    from db import engine, metadata
    from config import cfg
    if cfg.postgres:
        try:
            from sqlalchemy.schema import CreateSchema
            engine.execute(CreateSchema('schema'))
        except ProgrammingError as e:
            if 'already exists' not in str(e):
                raise

    cols = dict(orgn=(Column('id', Integer, primary_key=True), Column('code',
        String, nullable=False, unique=True), Column('title', String,
        nullable=False),), form=(Column('id', Integer, primary_key=True),
        Column('code', String, nullable=False), Column('year', String,
        nullable=False), Column('title', String, nullable=False), Column(
        'fname', String, nullable=False), Column('orgnId', Integer, ForeignKey
        ('orgn.id')), Column('pageht', String, nullable=False), Column(
        'pagewd', String, nullable=False), UniqueConstraint('code', 'year'),),
        slot=(Column('id', Integer, primary_key=True), Column('formId',
        Integer, ForeignKey('form.id')), Column('page', SmallInteger,
        nullable=False), Column('uniqname', String, nullable=False), Column(
        'uniqlinenum', String), Column('path', String, nullable=False), Column
        ('inptyp', CHAR, CheckConstraint('inptyp in (%s)' % (','.join("'%s'" %
        (i) for i in InputType.vals())))), Column('xmltyp', CHAR,
        CheckConstraint('xmltyp in (%s)' % (','.join("'%s'" % (i) for i in
        XmlType.vals())))), Column('unit', CHAR, CheckConstraint(
        'unit in (%s)' % (','.join("'%s'" % (i) for i in Unit.vals())))),
        Column('maxlen', SmallInteger), Column('math', String), Column('xpos',
        String), Column('ypos', String), Column('wdim', String), Column(
        'hdim', String), Column('vistxt', String), Column('hidtxt', String),
        Column('code', String), Column('currtabl', String), Column('coltitle',
        String), Column('coltype', String), Column('colinstrc', String),
        Column('isreadonly', Boolean), Column('ismultiline', Boolean),
        UniqueConstraint('formId', 'path'),),)
        # organization eg US/IRS eg form 1040 eg 1040-e eg Form 1040 Schedule E
        # filename eg f1040se
        # e('slot',metadata,*chain(slot.columns,slot.constraints,slot.indexes))
        # some fields are not numbered, eg 1040 name and address fields
        # nullable cuz senseless for checkboxes (%s)'%(','.join("'%s'"%(i) for
        # i in Op.vals())))), x position y position width dimension height
        # dimension visible text eg draw/text and field/captionText hidden text
        # eg field/speak for checkboxes eg MJ for married filing jointly table
        # if any column title if in table column type if in table column
        # instructions if any if in table for textboxes--computable from hdim?

    for tabl in ('orgn', 'form', 'slot'):
        if tabl in metadata.tables:
            tablobj = metadata.tables[tabl]
        else:
            tablobj = Table(tabl, metadata, *cols[tabl])
        tableInfo[tabl] = tablobj

    createAll()
    md = Bag(metadata.tables)
    return md


def createAll():
    from db import engine, metadata
    metadata.create_all(engine)   # checks for existence before creating


def ensureCodes():
    # make sure the needed codes/constants are in the db
    dbcodes = {}
    for tabl, col, seekval, insertvals in [
            ('orgn', 'code', 'us_irs', dict(title='Internal Revenue Service')),
            ]:
        tablobj = db.metadata.tables[tabl]
        insertvals[col] = seekval
        pk = db.selsert(tablobj, **insertvals)
        dbcodes[tabl + '.' + seekval] = pk
    return dbcodes


def setup(cfg):
    global conn, engine, metadata, md
    if conn is None:
        conn, engine, metadata, md = db.connect(appname, dbpath=cfg.get(
            'dbpath'))
    md = schema()
    dbc = ensureCodes()
    return conn, engine, metadata, md, dbc


def generateFormCode(formName):
    try:
        form, sched = formName
        code = form + '-' + sched
    except ValueError:
        code = formName
    return code


def qntyToStr(q):
    '''
        >>> qnty=Qnty.fromstring('3mm')
        >>> qntyToStr(qnty)
        '3millimeter'
        '''
    return str(q.magnitude) + str(q.units)


def writeFormToDb(form, year=None):
    # write form data to db tables form and slot
    # todo maybe write form.refs data as well [to a new table]
    # todo generate both code and title from form.name [no need for prefix arg]
    if 'd' not in cfg.steps:
        return
    if year is None:
        year = cfg.formyear
    prefix = form.prefix
    fields = form.bfields
    pageinfo = form.pageinfo
    conn, engine, metadata, dbt, dbc = setup(cfg)
    code = generateFormCode(form.name)
    title = computeFormTitle(prefix)
    orgn = 'us_irs'
    irs_id = dbc['orgn.' + orgn]
    page1 = pageinfo[1]
    formid = db.upsert(dbt.form,
        code=code,
        year=year,
        title=title,
        fname=prefix,
        orgnId=irs_id,
        pageht=str(page1.pageheight),
        pagewd=str(page1.pagewidth),
        )
    for i, f in enumerate(fields):
        db.upsert(dbt.slot,
            formId=formid,
            page=f.npage,
            uniqname=f.uniqname,
            uniqlinenum=f.get('uniqlinenum', ''),
            path=f.path,
            inptyp=dict(
                text='x',
                checkbox='k',
                )[f.typ],
            xmltyp='f',  # f=field
            maxlen=f.maxchars,
            unit=f.unit[0].lower() if f.unit else None,  # d or c (dollars or cents)
            math=repr(f.math.text if f.math.text else []),
            #op=f.op,
            xpos=qntyToStr(f.xpos),
            ypos=qntyToStr(f.ypos),
            wdim=qntyToStr(f.wdim),
            hdim=qntyToStr(f.hdim),
            vistxt=f.text,
            hidtxt=f.speak,
            code=f.code,
            currtabl=f.currTable,
            coltitle=f.coltitle,
            coltype=f.coltype,
            colinstrc=f.colinstruction,
            isreadonly=f.isReadonly,
            ismultiline=bool(f.multiline),
            )

if __name__ == "__main__":
    from config import setup as appsetup
    appsetup(relaxRqmts=True, checkFileList=False)
    if cfg.doctests:
        import doctest
        doctest.testmod(verbose=cfg.verbose)
    elif cfg.dropall:
        response = raw_input(
            'are you sure you want to drop all tables?  if so enter "yes": ')
        if response == 'yes':
            conn, engine, metadata, md = db.connect(appname)
            dropAll(metadata, conn)
            print "dropall done"
        else:
            print 'dropall NOT done, quitting'
    else:
        setup(cfg)
