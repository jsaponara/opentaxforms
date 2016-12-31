
import ut
from ut import jj,ddict
import irs
import re

def findLineAndUnit(s):
    '''
        >>> findLineAndUnit('Payments, Credits, and Tax. Line 7. Federal income tax withheld. Dollars.')
        ('line7', 'dollars')
        >>> findLineAndUnit('Line 7. Cents.')
        ('line7', 'cents')
        >>> findLineAndUnit('Personal identification number (P I N). 5 digits. ')
        (None, '')
        >>> findLineAndUnit('Page 2. Worksheet for Line 5, ...')
        (None, '')
        >>> 
        f2106ez/part1/line1: without the dots in units pttn, unit here would be cents
        >>> findLineAndUnit('Part 1. Figure Your Expenses. Line 1. Complete Part 2. Multiply line 8a by 55.5 cents (.555). Enter the result here. Dollars.')
        ('line1', 'dollars')
        >>> findLineAndUnit("Part 1. Persons ... (If ..., see the instructions.) Line 1. Item 1. (a) Care provider's name. Caution. If the care was provided in your home, you may owe employment taxes. If you do, you cannot file Form 1040A. For details, see the instructions for Form 1040, line 60a, or Form 1040N R, line 59a. 2 lines available for entry.")  # f2441
        ('line1', '')
        '''
    findLineNum1=re.search(r'(?:[\.\)]+\s*|^)(Line\s*\w+)\.(?:\s*\w\.)?',s) # Line 62. a. etc
    findLineNum2=re.search(r'(?:\.\s*)(\d+)\.(?:\s*\w\.)?',s) # Exemptions. 62. a. etc
    findLineNum3=re.search(r'^(\d+\w*)\.\s',s) # 16b. ... eg 990/page6/line16b
    units=re.findall(r'\.?\s*(Dollars|Cents)\.?',s,re.I)
    if findLineNum1:
        # linenum is eg 'line62a' for 'Line 62. a. etc' or even for 'Exemptions. 62. a. etc'
        linenum=findLineNum1.groups()[0]
    elif findLineNum2:
        linenum='line'+findLineNum2.groups()[0]
    elif findLineNum3:
        linenum='line'+findLineNum3.groups()[0]
    else:
        linenum=None
        if re.search(r'line\s+\d+',s,re.I):
            log.warn(jj('linenumNotFound: cannot find the linenum in:',s))
    if linenum:
        linenum=linenum.lower().replace(' ','').replace('.','')
    unit=units[-1].lower().strip(' .') if units else ''
    return linenum,unit

def linkfields(form):
    global cfg,log
    from config import cfg,log
    # link and classify fields: dollar and cent; by line; by name
    fields=form.fields
    def computeUniqname(f,fieldsSofarByName):
        # [0] becomes L0T cuz L,T look like square brackets to me
        pathsegs=f['path'].replace('[','L').replace(']','T').split('.')
        i=-1
        uniqname=name
        while uniqname in fieldsSofarByName:
            uniqname='_'. join(seg for seg in pathsegs[i:])
            i-=1
            if i<-len(pathsegs):
                msg='cannot generate unique key from path segments %s in keys %s'%(pathsegs,fieldsSofarByName.keys())
                log.error(msg)
                raise Exception(msg)
        return uniqname
    ypozByLinenum=ddict(set)
    fieldsByLinenumYpos=ddict(list)
    fieldsByName={}
    fieldsByLine=ddict(list)
    fieldsByRow=ddict(list)
    fprev=None
    for f in fields:
        name=f['name']
        uniqname=computeUniqname(f,fieldsByName)
        fieldsByName[uniqname]=f
        f['uniqname']=uniqname
        pg=f['npage']
        l,u=findLineAndUnit(f['speak'])
        # use page,linenum as key
        #   eg f3800 has line3 on both page1 and page3.  so p1/line6 deps on which line3?
        #   todo can fields w/ same linenum occur on same page?  eg f990/p12/line1?  track section numbers?
        fieldsByLine[(pg,l)].append(f)
        ypozByLinenum[(pg,l)].add(f['ypos'])
        fieldsByLinenumYpos[(pg,l,f['ypos'])].append(f)
        f['linenum']=l
        f['unit']=u.lower() if u else None
        if f['unit'] is not None:
            if any(typ in f['coltype'] for typ in irs.possibleColTypes):
                f['unit']=None#'dollars'
        if u=='cents':
            # todo should check abit more, eg approx dollars.ypos==cents.ypos and dollars.xpos+dollars.wdim==cents.xpos
            cc,dd=f,fprev
            if dd['unit']!='dollars':
                # occasionally dollars fields are not so labeled, eg 2015/f1040sse/line7 and 2015/f8814/line5 [hmm, both are pre-filled fields...; speak has the amt but not always with a "$"]
                log.warn('expectedDollars: expected field [%s] to have unit==dollars, instead got [%s] from previous speak: [%s]'%(dd['uniqname'],dd['unit'],dd['speak']))
                dd['unit']='dollars'
            dd['centfield']=cc
            cc['dollarfieldname']=dd['uniqname']
        fieldsByRow[(pg,str(f['ypos']))].append(f)
        fprev=f
    def byPageAndYpos(((pg,ypos),val)):
        '''
            >>> byPageAndYpos((1,'67.346 mm'),['et','cetera'])
            (1,67.346)
            '''
        return (pg,float(ypos.split(None,1)[0]))
    # force cells in each row to have same linenum as leftmost cell
    # todo give example [form/line] of where this is needed
    # todo consider adding tolerance, eg if y,y+ht overlap >=90% for two cells then theyre in the same row
    for row,fs in sorted(fieldsByRow.items(),key=byPageAndYpos):
        page,ht=row
        fs.sort(key=lambda f:f['xpos'])
        if fs[0].get('currTable'):
            ll0=fs[0]['linenum']
            for f in fs[1:]:
                if f['linenum']!=ll0:
                    f['linenum-orig']=f['linenum']
                    f['linenum']=ll0
                    log.warn(jj('leftmostCellOverride: p%d: changed'%(page),f['linenum-orig'],'in field',f['uniqname'],'to',ll0,'from leftmost field',fs[0]['uniqname']))
    # compute and assign unique linenumz
    for lnum,ypoz in ypozByLinenum.items():
        # using noncentFields to ensure just one field per ypos
        # eg dollar-and-cent pair usu at same ypos
        # newcode but wks for 1040,1040sb
        pg,linenumm=lnum
        noncentFields=[ff for ff in fieldsByLine[lnum] if ff['unit']!='cents']
        dupLinenumz=len(noncentFields)>1
        ypozz=[ff['ypos'] for ff in noncentFields]
        for iypos,ypos in enumerate(sorted(ypozz)):
            for ff in fieldsByLinenumYpos[(pg,linenumm,ypos)]:
                if linenumm is None:
                    uniqlinenum=None
                elif dupLinenumz:
                    # todo ensure the delimiter char ['_'] doesnt occur in any linenum
                    uniqlinenum=ff['linenum']+'_'+str(1+iypos)
                else:
                    uniqlinenum=ff['linenum']
                ff['uniqlinenum']=uniqlinenum
    form.fieldsByName=fieldsByName
    form.fieldsByLine=fieldsByLine

