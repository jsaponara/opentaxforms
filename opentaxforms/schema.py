#!/usr/bin/env python

'''
form=blank forms
orgn=organization that publishes the form
slot=fillable slot in a form
'''
from __future__ import print_function, absolute_import
from sqlalchemy import (
    Table, Column, Integer, SmallInteger, String,
    ForeignKey, Boolean, UniqueConstraint, CheckConstraint, CHAR)
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.schema import CreateSchema

from . import db
from .db import engine, metadata
from .ut import Bag, CharEnum
from .config import cfg, setup as appsetup
from .irs import computeTitle as computeFormTitle
from .version import appname

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
    except ProgrammingError as exc:
        if 'already exists' not in str(exc).lower():
            print(exc)
            exit()


def schema():
    # construct schema and create tables if they dont exist

    global tableInfo
    tableInfo = {}

    if cfg.postgres:
        try:
            engine.execute(CreateSchema('schema'))
        except ProgrammingError as e:
            if 'already exists' not in str(e):
                raise

    allowedInputTypes = ','.join("'%s'" % (i) for i in InputType.vals())
    allowedXmlTypes = ','.join("'%s'" % (i) for i in XmlType.vals())
    allowedUnitTypes = ','.join("'%s'" % (i) for i in Unit.vals())
    cols = dict(
        orgn=(  # organization eg US/IRS
            Column('id', Integer, primary_key=True),
            Column('code', String, nullable=False, unique=True),
            Column('title', String, nullable=False),
            ),
        form=(  # eg form 1040
            Column('id', Integer, primary_key=True),
            Column('code', String, nullable=False),  # eg 1040-e
            Column('year', String, nullable=False),
            Column('title', String, nullable=False),  # eg Form 1040 Schedule E
            Column('fname', String, nullable=False),  # filename eg f1040se
            Column('orgnId', Integer, ForeignKey('orgn.id')),
            Column('pageht', String, nullable=False),
            Column('pagewd', String, nullable=False),
            UniqueConstraint('code', 'year'),
            ),
        slot=(  # fillable field in a form
            # todo consider categorizing these to allow:
            #      slot=Table('slot',metadata,*chain(slot.columns,slot.constraints,slot.indexes))
            Column('id', Integer, primary_key=True),
            Column('formId', Integer, ForeignKey('form.id')),
            Column('page', SmallInteger, nullable=False),
            Column('uniqname', String, nullable=False),
            Column('uniqlinenum', String),  # some fields are not numbered,
                                            #  eg 1040 name and address fields
            Column('path', String, nullable=False),
            Column(
                'inptyp', CHAR, CheckConstraint(
                    'inptyp in (%s)' % (allowedInputTypes))),
            Column(
                'xmltyp', CHAR, CheckConstraint(
                    'xmltyp in (%s)' % (allowedXmlTypes,))),
            Column(
                'unit', CHAR, CheckConstraint(
                    'unit in (%s)' % (allowedUnitTypes))),
            Column('maxlen', SmallInteger),  # nullable for checkboxes
            Column('math', String),
            # Column('op', CHAR, CheckConstraint('op in
            #      (%s)'%(','.join("'%s'"%(i) for i in Op.vals())))),
            Column('xpos', String),  # x position
            Column('ypos', String),  # y position
            Column('wdim', String),  # width dimension
            Column('hdim', String),  # height dimension
            Column('vistxt', String),  # visible text eg draw/text
                                       #   and field/captionText
            Column('hidtxt', String),  # hidden text eg field/speak
            Column('code', String),  # for checkboxes
                                     #     eg MJ for married filing jointly
            Column('currtabl', String),  # table if any
            Column('coltitle', String),  # column title if in table
            Column('coltype', String),  # column type if in table
            Column('colinstrc', String),  # column instructions if any in table
            Column('isreadonly', Boolean),
            Column('ismultiline', Boolean),  # for textboxes
                                             # computable from hdim?
            UniqueConstraint('formId', 'path'),
            ),
        )
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
        conn, engine, metadata, md = db.connect(
            appname, dbpath=cfg.get('dbpath'))
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
        >>> from ut import Qnty
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
    title = computeFormTitle(prefix, form)
    orgn = 'us_irs'
    irs_id = dbc['orgn.' + orgn]
    page1 = pageinfo[1]
    formid = db.upsert(
        dbt.form,
        code=code,
        year=year,
        title=title,
        fname=prefix,
        orgnId=irs_id,
        pageht=str(page1.pageheight),
        pagewd=str(page1.pagewidth),
        )
    for f in fields:
        db.upsert(
            dbt.slot,
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
            unit=f.unit[0].lower() if f.unit else None,  # d or c
                                                         # (dollars or cents)
            math=repr(f.math.text if f.math.text else []),
            # op=f.op,
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
    appsetup(relaxRqmts=True, checkFileList=False)
    if cfg.doctests:
        import doctest
        doctest.testmod(verbose=cfg.verbose)
    else:
        setup(cfg)
