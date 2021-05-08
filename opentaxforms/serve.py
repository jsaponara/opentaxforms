#!/usr/bin/env python
from __future__ import print_function, absolute_import
import flask_restless
from argparse import ArgumentParser
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import func, select

from .db import connect
from .version import appname, apiVersion
from .ut import Bag

def createApi(app,**kw):
    conn, engine, metadata, md = connect(appname, **kw)
    print(engine.url)
    app.config['SQLALCHEMY_DATABASE_URI'] = engine.url
    app.config['DEBUG'] = True
    db = SQLAlchemy(app)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    mysession = scoped_session(Session)
    Base = declarative_base()
    Base.metadata.bind = engine
    apimanager = flask_restless.APIManager(app, session=mysession)
    counts = {}
    tableClasses = {}
    for tabl in md:
        tablobj = md[tabl]
        stmt = select([func.count()]).select_from(tablobj)
        counts[tabl] = stmt.execute().fetchone()[0]
        attrs = dict(
            __table__=tablobj,
            # todo should flask_restless need __tablename__?
            __tablename__=str(tabl),
            )
        tableClasses[tabl] = tablobj, type(str(tabl).capitalize(), (Base, ), attrs)
    attrs_by_table = dict(
        orgn=dict(
            form=lambda cls: db.relationship(cls),
        ),
        form=dict(
            orgn=lambda cls: db.relationship(cls, back_populates='form'),
            slot=lambda cls: db.relationship(cls, back_populates='form'),
        ),
        slot=dict(
            form=lambda cls: db.relationship(cls),
        ),
    )
    for tabl, (tablobj, tableClass) in tableClasses.items():
        attrs = attrs_by_table[tabl]
        for linkTabl, linker in attrs.items():
            _, linkTableClass = tableClasses[linkTabl]
            setattr(tableClass, linkTabl, linker(linkTableClass))
    for tabl, (tablobj, tableClass) in tableClasses.items():
        colsToAdd = dict(
            orgn=(),
            form=(
                'orgn', 'orgn.code',
                ),
            slot=(
                'form', 'form.code',
                ),
            )[tabl]
        colsToShow = [c.name for c in tablobj.columns]
        colsToShow.extend(colsToAdd)
        apimanager.create_api(
            tableClass,
            url_prefix='/api/v%s' % (apiVersion, ),
            #include_columns=colsToShow,
            includes=colsToShow,
            )
    return counts


def parseCmdline():
    '''Load command line arguments'''
    parser = ArgumentParser(
        description='Automates tax forms'
                    ' and provides an API for new tax form interfaces'
        )
    parser.add_argument(
        '-P', '--postgres',
        help='use postgres database [default=sqlite]', action="store_true")
    return parser.parse_args()


def createApp(**kw):
    cmdline = kw.get('cmdline')
    verbose = kw.get('verbose')
    if 'cmdline' in kw:
        del kw['cmdline']
    if 'verbose' in kw:
        del kw['verbose']
    args = parseCmdline() if cmdline else Bag(dict(postgres=False))
    app = Flask(appname)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # to suppress warning
    counts = createApi(app,postgres=args.postgres, **kw)
    if verbose:
        print('serving {slot} slots in {form} forms from {orgn} orgns'.format(
              **counts))
    return app


def main(**kw):
    app = createApp(dbpath='sqlite:///opentaxforms.sqlite3', **kw)
    app.run()


if __name__ == "__main__":
    main(cmdline=True, verbose=True)
