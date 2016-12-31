#! /usr/bin/env python
# -*- coding: utf-8 -*-

# glossary
#   pos,poz=position,positions
#   trailing z pluralizes, eg chrz=characters

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import ut
from ut import jj,ddict,Bag,logg,stdout,Qnty
from config import setup,RecurseInfinitely
import irs
from decimal import Decimal as decim
import traceback
import re
from os import remove as removeFile
from extractFillableFields import extractFields
import link,schema,html,cmds,refs

failurls=ut.unpickle('failurls',set())

def cleanupFiles(form):
    prefix=form.prefix
    if 'c' in cfg.steps:
        rawXmlFname='{}/{}-text.xml'.format(cfg.dirName,prefix)
        fmtXmlFname='{}/{}-fmt.xml'.format(cfg.dirName,prefix)
        if ut.exists(rawXmlFname):
            removeFile(rawXmlFname)
        if ut.exists(fmtXmlFname):
            removeFile(fmtXmlFname)

def addFormsTodo(form,formsdone,formstodo,formsfail):
    from Form import Form
    recurselevel=form.recurselevel
    refs=form.refs
    if cfg.recurse and (cfg.maxrecurselevel==RecurseInfinitely or recurselevel<cfg.maxrecurselevel):
        newforms=set(refs.keys()) \
            .difference(formsdone) \
            .difference(set(form for form,reclevel in formstodo)) \
            .difference(set(formsfail))
        formstodo.extend(Form(f,1+recurselevel) for f in newforms)
        if ut.hasdups(formstodo,lambda form:form.name):
            raise Exception('formstodo hasdups')
    return formstodo

def mathStatus(computedFields):
    # computedFields are computed from other, dependent fields
    #   If a computed field has no dependencies, 
    #   either its dependencies are missing or the field isnt really computed [a bug either way].
    #   This is a coarse measure--even a perfect score could mask incorrect dependency lists.
    nComputedFieldsWithDeps=sum(1 for f in computedFields.values() if f['deps'])
    nComputedFieldsSansDeps=sum(1 for f in computedFields.values() if not f['deps'])
    return nComputedFieldsWithDeps,nComputedFieldsSansDeps

def layoutStatus(fields):
    def overlap(f1,f2):
        # where f1,f2 are fields
        bb1=ut.Bbox(
            int(f1['xpos'].magnitude),
            int(f1['ypos'].magnitude),
            int(f1['xpos'].magnitude)+int(f1.get('xdim',Qnty(0)).magnitude),
            int(f1['ypos'].magnitude)+int(f1.get('ydim',Qnty(0)).magnitude))
        bb2=ut.Bbox(
            int(f2['xpos'].magnitude),
            int(f2['ypos'].magnitude),
            int(f2['xpos'].magnitude)+int(f2.get('xdim',Qnty(0)).magnitude),
            int(f2['ypos'].magnitude)+int(f2.get('ydim',Qnty(0)).magnitude))
        return not(
            bb1.x1<=bb2.x0 or  # box1 is to the left of box2
            bb1.x0>=bb2.x1 or  # box1 is to the right of box2
            bb1.y0>=bb2.y1 or  # box1 is below box2
            bb1.y1<=bb2.y0)    # box1 is above box2
    def overlaps(field,fieldz):
        # returns true if field overlaps w/ any in fieldz
        for f in fieldz:
            if overlap(f,field):
                return True
        return False
    nOverlappingFields=sum(overlaps(f,fields[i:]) for i,f in enumerate(fields))
    nNonoverlappingFields=len(fields)-nOverlappingFields
    return nNonoverlappingFields,nOverlappingFields

statusmsgtmpl='layoutBoxes: {}found,{}overlapping,?missing,?spurious; refs: {}found,{}unrecognized,?missing,?spurious; computedFields: {}found,{}empty,?missing,?spurious'
def logFormStatus(form):
    z=Bag()
    z.lgood,z.lerrs=layoutStatus(form.fields)
    z.rgood,z.rerrs=form.refs.status() if form.refs else (0,0)
    z.mgood,z.merrs=mathStatus(form.computedFields)
    statusmsg='form {} status: '.format(form.name)+statusmsgtmpl.format(
        *z(*('lgood','lerrs','rgood','rerrs','mgood','merrs'))
        )
    logg(statusmsg,[log.warn,stdout])
    return z.__dict__

def logRunStatus(formsdone,formsfail,status):
    if len(formsdone)>1:
        print 'successfully processed {} forms'.format(len(formsdone))
        statusTotals=sum(status.values(),Bag())
        msg='status totals:'+statusmsgtmpl.format(*statusTotals(*'lgood lerrs rgood rerrs mgood merrs'.split()))
        logg(msg,[log.warn,stdout])
    if formsfail:
        msg='failed to process %d forms: %s'%(len(formsfail),[irs.computeFormId(f) for f in formsfail])
        logg(msg,[log.error,stdout])
        logg('logfilename is "{}"'.format(cfg.logfilename))
    import json
    status.update({'f'+irs.computeFormId(f).lower():None for f in formsfail})
    statusStr=json.dumps(status.__dict__)
    # status is partial because missing,spurious values are unknown and thus omitted
    log.warn('status partial data: %s'%(statusStr))

def indicateProgress(form):
    if cfg.indicateProgress:
        msg='--------'+jj(form.name,('recurselevel=%d'%(form.recurselevel) if cfg.recurse else ''))
        logg(msg,[stdout,log.warn])  # use warn level so that transition to new form is logged by default

def opentaxforms(**args):
    global cfg,log
    cfg,log=setup(**args)
    dirName=cfg.dirName
    
    formstodo,formsdone,formsfail=[],[],[]
    formstodo.extend(cfg.formsRequested)
    cfg.indicateProgress=cfg.recurse or len(formstodo)>1
    status=Bag()
    
    while formstodo:
        form=formstodo.pop(0)
        indicateProgress(form)
        try:
            form.getFile(failurls)
            form.readInfo()
            extractFields(form,dirName)
            form.fixBugs()
            link.linkfields(form)
            cmds.computeMath(form)
            refs.findRefs(form,dirName)
            schema.writeFormToDb(form,cfg.formyear)
            html.writeEmptyHtmlPages(form,dirName)
            cleanupFiles(form)
            formsdone.append(form)
            formstodo=addFormsTodo(form,formsdone,formstodo,formsfail)
            status[form.prefix]=logFormStatus(form)
        except irs.CrypticXml as e:
            # eg 1040 older than 2012 fails here
            log.error(jj('EEEError',e.__class__.__name__,str(e)))
            formsfail.append(form.name)
        except Exception as e:
            log.error(jj('EEEError',traceback.format_exc()))
            if cfg.debug: raise
            formsfail.append(form.name)
    logRunStatus(formsdone,formsfail,status)
    ut.pickle(failurls,'failurls')
    atLeastSomeFormsSucceeded=(len(formsdone)>0) ; Success=0 ; Failure=1
    return Success if atLeastSomeFormsSucceeded else Failure

if __name__=='__main__':
    from config import setup
    cfg,log=setup(readCmdlineArgs=True)
    if cfg.doctests:
        import doctest; doctest.testmod(verbose=cfg.verbose)
    else:
        sys.exit(opentaxforms())

