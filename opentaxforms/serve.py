#!/usr/bin/env python

from version import appname,apiVersion
from flask import Flask

def createApi(**kw):
    import flask_restless
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import scoped_session, sessionmaker
    from db import connect,engine,metadata
    from flask_sqlalchemy import SQLAlchemy
    db=SQLAlchemy(app)
    conn,engine,metadata,md=connect(appname,**kw)
    Base=declarative_base()
    Session=sessionmaker(autocommit=False,autoflush=False,bind=engine)
    mysession=scoped_session(Session)
    apimanager=flask_restless.APIManager(app,session=mysession)
    counts={}
    for tabl in md:
        tablobj=md[tabl]
        counts[tabl]=tablobj.count().execute().fetchone()[0]
        attrs=dict(
            __table__=tablobj,
            __tablename__=str(tabl),  # todo should flask_restless need __tablename__?
            )
        attrs.update(dict(
            orgn=dict(
                form=db.relationship('Form'),
                ),
            form=dict(
                orgn=db.relationship('Orgn',back_populates='form'),
                slot=db.relationship('Slot',back_populates='form'),
                ),
            slot=dict(
                form=db.relationship('Form'),
                ),
            )[tabl])
        tablcls=type(str(tabl).capitalize(),(Base,),attrs)
        colsToAdd=dict(
            orgn=(),
            form=(
                'orgn','orgn.code',
                ),
            slot=(
                'form','form.code',
                ),
            )[tabl]
        colsToShow=[c.name for c in tablobj.columns]
        colsToShow.extend(colsToAdd)
        print tabl,colsToShow
        apimanager.create_api(tablcls,
            url_prefix='/api/v%s'%(apiVersion,),
            include_columns = colsToShow,
            )
    return counts

def parseCmdline():
    '''Load command line arguments'''
    from argparse import ArgumentParser
    parser=ArgumentParser(description='Automates tax forms and provides an API for new tax form interfaces')
    parser.add_argument('-P', '--postgres', help='use postgres database [default=sqlite]', action="store_true")
    return parser.parse_args()

def createApp(**kw):
    global app
    from ut import Bag
    cmdline=kw.get('cmdline')
    verbose=kw.get('verbose')
    if 'cmdline' in kw:
        del kw['cmdline']
    if 'verbose' in kw:
        del kw['verbose']
    args=parseCmdline() if cmdline else Bag(dict(postgres=False))
    app=Flask(appname)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False  # to suppress warning
    counts=createApi(postgres=args.postgres,**kw)
    if verbose:
        print 'serving {slot} slots in {form} forms from {orgn} orgns'.format(**counts)
    return app

def main(**kw):
    app=createApp(dbpath='sqlite:///opentaxforms.sqlite3',**kw)
    app.run()

if __name__=="__main__":
    main(cmdline=True,verbose=True)

