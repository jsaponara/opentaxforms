#! /usr/bin/env python
# -*- coding: utf-8 -*-

# todo eliminate guesswork in setup()/allpdfnames and possibleFilePrefixes by
#      reading document metadata as in pdfInfo() and mapping formName<->filename.

# glossary
#   pos,poz=position,positions
#   trailing z pluralizes, eg chrz=characters

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import ut
from ut import jj,ntuple,ddict,Bag,logg,stdout,Qnty,numerify,NL
from config import setup,RecurseInfinitely
import domain
from decimal import Decimal as decim
import traceback
import re
from os import remove as removeFile
from extractFillableFields import extractFields
import schema,html

# irs Prior Year Products  https://apps.irs.gov/app/picklist/list/priorFormPublication.html
# 2014
#   prevurltmpl='http://www.irs.gov/pub/irs-pdf/%s'%(fname,)
#   currurltmpl='http://www.irs.gov/file_source/pub/irs-pdf/%s'%(fname,)
# 2015
prevurltmpl='http://www.irs.gov/pub/irs-prior/%s'
currurltmpl='http://www.irs.gov/pub/irs-pdf/%s'

failurls=ut.unpickle('failurls',set())

Bbox=ntuple('Bbox','x0 y0 x1 y1')
def merge(bb1,bb2):
    return Bbox(min(bb1.x0,bb2.x0),min(bb1.y0,bb2.y0),max(bb1.x1,bb2.x1),max(bb1.y1,bb2.y1))

def possibleFilePrefixes(formName):
    '''
        the filename for form 1040 sched 8812 is f1040s8.pdf, whereas the typical pattern is f1040s8812.pdf.
        todo eliminate this guesswork by reading document metadata in the setup()/allpdfnames step as done in pdfInfo()
        >>> possibleFilePrefixes(('1040','8812'))
        ['f1040s8812', 'f1040s881', 'f1040s88', 'f1040s8']
        '''
    prefixes=[]
    try:
        fform,fsched=formName
        if fsched is None:
            formName=fform
            raise
        ntrim=len(fsched)
        tmpl={
            ('990','b'):'%sez%s',  # a glaring inconsistency--in 2015 only??
            ('1120','utp'):'%s%s', # no delimiter at all--how common is this?
            }.get((fform,fsched),'%ss%s') # the typical pattern
        formName=(tmpl%formName).lower()  # formName may be eg ('f1040','A')
    except:
        def trailingLetters(s):
            i=-1
            if not s or not s[i].isalpha():
                return ''
            while len(s)>=abs(i) and s[i].isalpha():
                i-=1
            return s[i+1:] 
        # cuz 1120reit->f1120rei
        ntrim=max(0,len(trailingLetters(formName))-1)
    # remove '-' but protect '--'
    formName='f'+formName.lower().replace('--','<>').replace('-','').replace('<>','--')
    prefixes.append(formName)
    if any(formName.endswith(suffix) for suffix in ('ez','eic')):
        prefixes.append(formName[:-1])  # remove last char
    else:
        for i in range(1,ntrim):
            prefixes.append(formName[:-i])  # remove last chars
    return prefixes
def dlform(formName,year,dirName='forms'):
    # download form from irs.gov into {dirName}
    year=int(year)
    from urllib2 import urlopen,URLError,HTTPError
    formNamesToTry=possibleFilePrefixes(formName)
    msgs=[]
    foundfile=False
    url=''
    if year<cfg.latestTaxYear:
        fnametmpl='%(formName)s--%(year)s.pdf'
    else:
        fnametmpl='%(formName)s.pdf'
    for formName in formNamesToTry:
        fname=fnametmpl%dict(formName=formName,year=year)
        destfname=formName+'.pdf'
        destfpath=dirName+'/'+destfname
        if ut.exists(destfpath):
            foundfile=True
            break
    if not foundfile:
        for formName in formNamesToTry:
            fname=fnametmpl%dict(formName=formName,year=year)
            destfname=formName+'.pdf'
            destfpath=dirName+'/'+destfname
            if not cfg.okToDownload:
                msg='oops no '+destfpath+' and not okToDownload'
                logg(msg,[log.error,stdout])
                exit()
            try:
                if year<cfg.latestTaxYear:
                    url=prevurltmpl%(fname,)
                else:
                    url=currurltmpl%(fname,)
                if url in failurls:
                    continue
                log.warn('downloading: '+url+' for '+formName+' from '+url)
                fin=urlopen(url,'rb')
                if fin.getcode()!=200:
                    # not a pdf, just an html error page
                    continue
                pdf=fin.read()
                fin.close()
                fout=open(destfpath,'wb')
                fout.write(pdf)
                fout.close()
                foundfile=True
                break
            except HTTPError:
                msgs.append('HTTPError at '+url)
                failurls.add(url)
            except URLError,e:
                log.error(e)
                raise
    if not foundfile:
        if not msgs:
            msgs.append('url does not exist:  {}'.format(url))
        raise Exception('\n'.join(msgs))
    return destfname,url

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

def pdfInfo(fpath):
    # collect metadata from pdf file at document and page levels
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    with open(fpath,'rb') as fp:
        parser=PDFParser(fp)
        doc=PDFDocument(parser)
        docinfo={}
        if 'Metadata' in doc.catalog:
            from pdfminer.pdftypes import resolve1
            from xmp import xmp_to_dict
            metadata=resolve1(doc.catalog['Metadata']).get_data()
            xmpdict=xmp_to_dict(metadata)
            docinfo['titl']=xmpdict['dc']['title']['x-default']
            docinfo['desc']=xmpdict['dc']['description']['x-default']
            docinfo['isfillable']=xmpdict['pdf'].get('Keywords','').lower()=='fillable'
            m=re.search(r'(?:(\d\d\d\d) )?Form ([\w-]+(?: \w\w?)?)(?: or ([\w-]+))?(?:  ?\(?(?:Schedule ([\w-]+))\)?)?(?:  ?\((?:Rev|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec).+?\))?\s*$',docinfo['titl'])
                # eg 2016 Form W-2 AS 
                # eg 2015 Form 1120 S (Schedule D) 
                # eg 2015 Form 990 or 990-EZ (Schedule E)
                # eg Form 8818  (Rev. December 2007)
                # eg Form 8849  (Schedule 2)  (Rev. January 2009)
                # eg Form 1066 (Schedule Q) (Rev. December 2013)
                # eg Form 1120S Schedule B-1 (December 2013)
                # 'Rev' means 'revised'
            if m:
                taxyr,form1,form2,sched=m.groups()
            else:
                m=re.search(r'(?:(\d\d\d\d) )?Schedule ([-\w]+) \(Form ([\w-]+)(?: or ([\w-]+))? ?\)(?: \((?:Rev|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec).+?\))?\s*$',docinfo['titl'])
                    # eg 2015 Schedule M-3 (Form 1065)
                    # eg 2015 Schedule O (Form 990 or 990-EZ)
                    # eg Schedule O (Form 1120) (Rev. December 2012)
                    # eg Schedule C (Form 1065 ) (Rev. December 2014)
                if m:
                    taxyr,sched,form1,form2=m.groups()
                else:
                    msg=docinfo['titl']+' dont fit'
                    log.error(msg)
                    raise Exception(msg)
            docinfo['taxyr']=taxyr
            form=form1 if not form2 or len(form1)<len(form2) else form2
            docinfo['form' ]=form
            docinfo['sched']=sched
            docinfo['formName']=form if not sched else (form,sched)
            docinfo['fpath']=fpath
        # Check if the document allows text extraction. If not, abort.
        if not doc.is_extractable:
            raise Exception('PDFTextExtractionNotAllowed')
        PageInfo=ntuple('PageInfo','pagenum pagewidth pageheight textpoz')
        pageinfo={}
        rr=Renderer()
        #for ipage,page in enumerate(doc.get_pages()):
        for ipage,page in enumerate(PDFPage.create_pages(doc)):
            pagenum=1+ipage
            if page.cropbox!=page.mediabox:
                log.warn('boxesDontMatch: cropbox!=mediabox on page %d: cropbox=%s; mediabox=%s'%(pagenum,page.cropbox,page.mediabox))
            pagewidth=Qnty(page.cropbox[2]-page.cropbox[0],'printers_point')
            pageheight=Qnty(page.cropbox[3]-page.cropbox[1],'printers_point')
            pageinfo[pagenum]=PageInfo(pagenum,pagewidth,pageheight,rr.renderPage(page))
    return docinfo,pageinfo

class Renderer:
    def __init__(self):
        from pdfminer.layout import LAParams
        from pdfminer.converter import PDFPageAggregator
        from pdfminer.pdfinterp import PDFResourceManager,PDFPageInterpreter
        from pdfminer.pdfdevice import PDFDevice
        # Create a PDF resource manager object that stores shared resources.
        rsrcmgr=PDFResourceManager()
        # la=layout analysis
        laparams=LAParams()
        self.device=PDFPageAggregator(rsrcmgr,laparams=laparams)
        self.interpreter=PDFPageInterpreter(rsrcmgr,self.device)
        self.textPoz=None
    def renderPage(self,page):
        from pdfminer.layout import LTTextBox,LTTextLine,LTFigure,LTTextBoxHorizontal
        self.interpreter.process_page(page)
        layout=self.device.get_result()
        # http://denis.papathanasiou.org/2010/08/04/extracting-text-images-from-pdf-files/
        textPoz=TextPoz()
        for lt in layout:
            if lt.__class__ in (LTTextBoxHorizontal,LTTextBox,LTTextLine):
                textPoz.add(lt)
        return textPoz
from pdfminer.layout import LTChar,LTTextLineHorizontal
class TextPoz:
    FormPos=ntuple('FormPos','itxt ichar chrz bbox')
    def __init__(self):
        self.textPoz=[]
        self.Struct=ntuple('Struct','text bbox chars charobjs')
    def add(self,ltobj):
        def quantify(tupl,unit): return [Qnty(qnty,unit) for qnty in tupl]
        def accum(ltobj,ltchars,chars):
            for lto in ltobj:
                if isinstance(lto,LTChar):
                    ltchartext=lto.get_text()
                    ltchars.append((ltchartext,Bbox(*quantify(lto.bbox,'printers_point'))))
                    chars.append(ltchartext)
                elif isinstance(lto,LTTextLineHorizontal):
                    accum(lto,ltchars,chars)
        ltchars=[];chars=[]
        accum(ltobj,ltchars,chars)
        self.textPoz.append(self.Struct(
            ltobj.get_text(),
            Bbox(*quantify(ltobj.bbox,'printers_point')),
            ''.join(chars),
            ltchars))
    def optimize(self):
        # todo ensure objs are arranged by line (ie ypos) and left-to-right within line
        pass
    def find(self,s):
        if not s:
            raise Exception('empty string')
        def findstr(sl,found):
            for itxt,(txt,bbx,chrz,charobjs) in enumerate(self.textPoz):
                chrz=chrz.lower()
                # require target to be bordered by start/end of string, whitespace, or punctuation to avoid matching a mere subset of the actual form referenced
                #   [eg to avoid finding '1040' in '1040EZ']
                slsafe=re.escape(sl)
                for m in re.finditer(r'(?:^|[\s\W])('+slsafe+r')(?:$|[\s\W])',chrz):
                    if m:
                        ichar=m.start()
                        bbox1=charobjs[ichar][1]
                        bbox2=charobjs[ichar+len(sl)-1][1]
                        if not (bbox1.y0==bbox2.y0 and bbox1.y1==bbox2.y1):
                            log.info('bbox.y coords dont match for [{}]'.format(sl))
                        bbox=merge(bbox1,bbox2)
                        found.append(TextPoz.FormPos(itxt,ichar,chrz[ichar:ichar+len(sl)],bbox))
                    else:
                        break
            return found
        sl=s.lower()
        found=[]
        while not found:
            found=findstr(sl,found)
            if not found and ' ' in sl:
                sl=sl.rsplit(None,1)[-1]
            else:
                break
        if not found:
            log.warn('textNotFound: '+s+' in '+self.alltext().replace(NL,' [newline] '))
        if len(found)>1:
            log.warn('textRepeats: found too many (returning all of them), seeking '+s+' in '+self.alltext().replace(NL,'  ')[:60]+' ... [run in debug mode for fulltext]: '+str(found) )
            log.debug(' fulltext: seeking '+s+' in '+self.alltext().replace(NL,'  '))
        return found
    def alltext(self):
        return NL.join(o.text for o in self.textPoz)

def readImgSize(fname,dirName):
    from PIL import Image
    f=open(dirName+'/'+fname,'rb')
    img=Image.open(f)
    imgw,imgh=img.size
    f.close()
    return imgw,imgh

formcondPtn=re.compile(r'form (\w+)(?: and (\w+))? filers: (\w+)',re.I)
ifcondPtn  =re.compile(r'if (.+?), (.+?)(?: otherwise,? (.+))?$')
def normalize(s):
    # replace each whitespace string with a single space
    return re.sub(r'\s+',' ',s)
def condtopy(cond):
    '''
        >>> condtopy('line 2 is more than line 1')
        'line2>line1'
        '''
    delim=' is more than '
    if delim in cond:
        lh,rh=cond.split(delim,1)
        lh=lh.replace(' ','')
        rh=rh.replace(' ','')
        return '%s>%s'%(lh,rh)
    raise Exception('dunno condition [%s]'%(cond,))
def computeMath(fields,draws,fieldsByLine,prefix):
    # determines which fields are computed from others
    # 'dep' means dependency
    fields,draws=(fields,draws) if 'm' in cfg.steps else ([],[])
    Term=ntuple('Term','linenum unit uniqname npage'); linenumk,unitk,namek,pagek=Term._fields
    computedFields=ut.odict()
    upstreamFields=set()
    for field in fields:
        ll,uu,nn,pg=[field[key] for key in Term._fields]
        speak=normalize(field['speak'])
        colinstruction=normalize(field['colinstruction'])
        if colinstruction:
            instruction=colinstruction
        else:
            instruction=speak
        currLine,unit=findLineAndUnit(speak)
        math={}
        m=re.search(r'open parenthes.s.*closed? parenthes.s',speak,re.I)
        if m:
            # this field is intrinsically a loss, ie, a negative number,
            #   w/o the user writing parens ob the parens are 'builtin' to the form
            #   eg f1040sd/line6
            #   todo could instead detect draw object w/ same x,y,w,h as field object and text r'\( +\)'
            field['sign']='-'
            dx=.05*field['wdim']  # shift field rightward to make room for '('
            field['dx']=dx
        sents=re.split(r'\.\s*',instruction)
        op=None
        terms=None
        constantUnit=None
        for s in sents:
            s=s.lower()
            if s.startswith('this is the amount'):
                # eg 1040/line75  this is the amount you overpaid
                #    'amount' here is not a cmd [and thus op is not '+']
                continue
            if s.startswith('boxes checked on'):
                # insert implicit command
                s='howmany '+s
            m=re.match(formcondPtn,s)
            if m:
                form1,form2,s=m.groups()
                assert form1,'formcondPtn w/o form1!'
                forms=[form1,form2] if form2 else [form1]
            else:
                forms=None
            m=re.match(ifcondPtn,s)
            if m:
                cond,s,s2=m.groups()
            else:
                cond=s2=None
            m=re.match(domain.commandPtn,s)
            if m:
                cmd,s=m.groups()
            else:
                continue
            if cmd in ('add','combine','howmany','total','amount'):
                op='+'
                # eg f1040: Add lines 47 through 53. These are your t
                # eg f1040: Add lines 62, 63, 64a, and 65 through 71.
                # eg f1040sb: Add the amounts on line 1.
                # eg f1040/line22 : Combine the amounts in the far right column for lines 7 through 21.
                # eg f1040/line6d : [howmany] Boxes checked on 6a and 6b 
                # eg f1040/line6d : Add numbers on  lines above [here meaning same line (6d)]
                # eg f1040: Line 38. Amount from line 37 (adjusted gross income) 
                # eg f1040/line39a: Total Boxes Checked   [but not: Line 6d. Total number of exemptions claimed. Boxes checked on 6a and 6b.]
                # eg f1040sd: Combine lines 1a through 6 in column (h).
                def numOrRange(s,col=None):
                    prefix='line'
                    try:
                        start,end=s.split(' through ',1)
                        if end.startswith(prefix):
                            prefix=''
                        startnum,endnum=numerify(start),numerify(end)
                        start,end=(prefix+start,prefix+end)
                        startxpoz=[f['xpos'] for f in fieldsByLine[(pg,start)] if f['unit']!='cents']
                        endxpoz  =[f['xpos'] for f in fieldsByLine[(pg,end  )] if f['unit']!='cents']
                        for pos in startxpoz:
                            if pos in endxpoz:
                                startxpos=endxpos=pos
                                break
                        else:
                            # no matching xpos for start and end lines so just use rightmost xpos for each
                            startxpos=max(startxpoz)
                            endxpos  =max(endxpoz)
                        # todo make this less sensitive to adjustments in xpos--for now, moved dx adjustment from top of computeMath [where it wrecked havoc] to writeEmptyHtmlPages/adjustxpos
                        lines=ut.uniqify([(f['linenum'],f['unit'],f['xpos'])
                            for k,fs in fieldsByLine.iteritems()
                                for f in fs
                                    if f['linenum'] \
                                        and startnum<=numerify(f['linenum'])<=endnum \
                                        and f['unit']!='cents' \
                                        and (startxpos!=endxpos or startxpos==f['xpos'])])
                        lines=[x[0] for x in lines]
                    except ValueError:  # really only want to catch 'ValueError: need more than 1 value to unpack'
                        if s.startswith(prefix):
                            prefix=''
                        lines=[prefix+s]
                    if col:
                        lines=[l+'.col.'+col for l in lines]
                    return lines
                # 'Total of all amounts reported on line 3 for ...'  f1040se/23
                # 'Combine lines 7 and 15 and enter the result'      f1040sd/16
                s=s.replace('the amounts in the far right column for ','') \
                   .replace('of all amounts reported on line ','lines ') \
                   .replace(' and enter the result','') \
                   .replace('boxes checked on ','lines ') \
                   .replace('boxes checked','lines '+(ll if ll else ''))
                # remove "for all rental properties", "for all royalty properties", "for all properties"  f1040se/23
                s=re.sub(r' for all(?: \S+)? properties','',s,re.I)
                # could be elim'd by allowing multi-word cmds
                if cmd=='amount' and not s.startswith('from line '):
                    # eg 2015/f5329/line3 Amount subject to additional tax. Subtract line 2 from line 1
                    continue
                if s.startswith('lines '):
                    s=s.replace('lines ','')
                    m=re.search(r' in column \((.)\)',s,re.I)
                    col=None
                    if m:
                        col=m.group(1)
                        s=s[:m.start()]
                    terms=sorted(ut.flattened([numOrRange(entry,col) for entry in re.split(r' and |, (?:and )?',s)]),key=numerify)
                elif s.startswith('from line '):
                    s=s.replace('from ','')
                    if '(' in s:
                        s=s[:s.index('(')]
                    s=s.replace(' ','')
                    terms=[s]
                elif s.startswith('the amounts on line '):
                    s=s.replace('the amounts on','').replace(' ','')
                    terms=[s]
                elif cmd=='howmany' or s=='numbers on lines above':
                    terms=[currLine]
                elif s in ('number of exemptions claimed',):
                    # todo
                    continue
                else:
                    msg='cannotParse: cannot parse [{}] cmd [{}] on {}/p{}/{}'.format(cmd,s,prefix,pg,ll)
                    log.warn(msg)
                    if terms is None:
                        op='?'
                        terms=[]
                math=dict(op=op,terms=terms)
            elif cmd in ('subtract','multiply'):
                # eg 1040/line43 Subtract line 42 from line 41
                # eg 1040/line42 Multiply $3,800 by the number on line 6d
                # todo eg Subtract column (e) from column (d) and combine the result with column (g).
                #      * recognize this as columnMath, assoc w/ currTable, find cells via coltitle and setup terms; continue to apply columnMath throughout currTable
                #      1065b/p4/bottomSection/line1  In column (b), add lines 1c through 4b, 7, and 8. From the result, subtract line 14g 
                delim,op=dict(
                    subtract=(' from ','-'),
                    multiply=(' by (?:the number on )?','*'),
                    )[cmd]
                terms=re.split(delim,s,re.I)
                if len(terms)!=2:
                    log.error('oops, expected 2 terms for cmd [{}] using delim [{}] in [{}], found [{}]: [{}]'.format(cmd,delim,s,len(terms),terms))
                    continue
                if ' and ' in terms[1]:
                    m=re.search(r' and combine the result with (.*)$',terms[1],re.I)
                    if m:
                        terms[1]=terms[1][:m.start()]
                        # NOTE this means op=='-' is really a-b+c+d+....
                        terms.append(m.group(1))
                        def linecolterm(term):
                            if 'column' in term:
                                lin,col=term.split('column')
                                lin=lin.strip()
                                col=col.strip(' ()')
                                return lin+'.col.'+col
                            else:
                                return term
                        terms=[linecolterm(t) for t in terms]
                    else:
                        msg='cannotParse: cannot parse [%s]'%(terms[1],)
                        log.warn(msg)
                        op='?'
                if op=='-':
                    # swap 1st two terms cuz 'subtract a from b' means 'b-a'
                    terms[0],terms[1]=terms[1],terms[0]
                terms=[re.sub(r'[\s\$,]','',term) for term in terms]
                math=dict(op=op,terms=terms)
            elif cmd in ('enter',):
                # eg 1040/line43: Line 43. Taxable income.  Subtract line 42 from line 41. If line 42 is more than line 41, enter zero. Dollars.  [[topmostSubform[0].Page2[0].p2-t10[0]]]
                # eg 4684/line4 : If line 3 is more than line 2, enter the difference here and skip lines 5 through 9 for that column. 
                # eg 1040ez/line43: Line 6. ... If line 5 is larger than line 4, enter -0-.
                if s=='zero':
                    s='-0-'
                elif cond and s.startswith('the difference here'):
                    op='-'
                    m1=re.match(r'(line \w+) is (less|more|larger|smaller|greater) than (line \w+)',cond)
                    if m1:
                        lineA,cmpOp,lineB=m1.groups()
                        if cmpOp in ('more','larger','greater'):
                            terms=[lineA,lineB]
                        else:
                            terms=[lineB,lineA]
                    else:
                        log.warn(jj('cannotParseMath: cannot parse math: cmd,s,cond:',cmd,cond,s,delim='|'))
                        continue
            else:
                log.warn(jj('cannotParseCmd: cannot parse command: cmd s cond:',cmd,s,cond,delim='|'))
                continue
            if cond:
                # 1040/line43 line 42 is more than line 41
                # 1040/line42 line 38 is $154,950 or less
                # 1040/line4  the qualifying person is a child but not your dependent
                if cond.startswith('zero or') and terms and len(terms)==2:
                    # 4684/line9: Subtract line 3 from line 8. If zero or less, enter -0-
                    cond=terms[0].replace('line','line ')+' is more than '+terms[1].replace('line','line ')
                m1=re.match(r'(line \w+) is (less|more|larger|smaller|greater) than (line \w+)',cond)
                m2=re.match(r'(line \w+) is ([$\d,]+) or (less|more)',cond)
                condparse=None
                if m1:
                    lineA,cmpOp,lineB=m1.groups()
                    condparse=(
                        '<' if cmpOp in ('less','smaller') else '>',
                        lineA.replace(' ',''),
                        lineB.replace(' ',''),
                        )
                elif m2:
                    line,amt,cmpOp=m2.groups()
                    if '$' in amt:
                        constantUnit='dollars'
                    condparse=(
                        '<=' if cmpOp=='less' else '>=',
                        line.replace(' ',''),
                        amt.replace('$','').replace(',',''),
                        )
                else:
                    log.warn(jj('cannotParseCond: cannot parse condition',cond))
                if condparse is not None:
                    def flipcondition(cond):
                        cmpOp,x,y=cond
                        cmpOp={
                            '<':'>=',
                            '<=':'>',
                            '>':'<=',
                            '>=':'<',
                            }[cmpOp]
                        return (cmpOp,x,y)
                    if cmd=='enter' and s=='-0-':
                        math['zcond']=condparse
                    else:
                        log.debug(jj('397 how interpret condition?  assuming zcond=flipcondition',cond))
                        math['zcond']=flipcondition(condparse)
        # this assumes terms can be parsed from the 1st sentence of the instructions in the speak element
        if math and terms:
            math['text']=''
            myFieldName=field[namek]
            myFieldUnit=field[unitk]
            if op=='*' and constantUnit=='dollars':
                # eg 1040/line42 our dep fields are unitless cuz our constant is in dollars
                myFieldUnit=None
            def findin(term,parentline,pgnum,fieldsByLine):
                # find fields that correspond to the term; parentline is lhs
                # typically returns the dollar and cent fields corresponding to a term such as 'line7'
                if term.isdigit():
                    return [dict(typ='constant',uniqname=term,unit=None,val=term,npage=pgnum,linenum=term,centfield='centfield_of_constant')]
                if '.col.' in term:
                    # field is in a table
                    line,col=term.split('.col.')
                    if not line:
                        line=parentline
                    returnFields=[field for field in fieldsByLine[(pgnum,line)] if field.get('coltitle')==col]
                    if returnFields:
                        return returnFields
                    else:
                        # if coltitle restricts fields down to zero, ignore it [eg 1040sd/line4-6 called 'column h'in line7]
                        term=line
                found=fieldsByLine[(pgnum,term)]
                if not found:
                    canGetValuesFromOtherPages=True
                    if canGetValuesFromOtherPages:
                        # assuming that most recent occurrence of term is intended
                        #   term [eg 'line3'] may occur on multiple pages of the form
                        sourcepage=pgnum-1
                        while not found and sourcepage>=1:
                            found=fieldsByLine[(sourcepage,term)]
                            sourcepage-=1
                    else:
                        # let the user fill the computed-from-other-page field manually
                        found=[]
                return found
            upfields=[findin(term,ll,pg,fieldsByLine) for term in terms]
            upfields=[upf for upfs in upfields for upf in upfs if upf[namek]!=myFieldName and upf[unitk]==myFieldUnit]
            if op=='*':
                # todo yikes! here we assume that 1. we want to multiply only two fields, and 2. the first and the last [and thus most derived/computed] field
                # for line42, this will give constant and computedline6d
                if len(upfields)>1:
                    upfields=[upfields[0],upfields[-1]]
            upstreamFields.update([upf['uniqname'] for upf in upfields if upf.get('typ')!='constant'])
            #upstreamFields.remove(myFieldName)  # do this later in case fields are not in dependency order [otherPlaceHere]
            computedFields[myFieldName]=field
            field['deps']=upfields
            field['op']=op
            mathstr=op.join(terms)
            if 'cond' in math:
                math['cond']=' if not %s else %s'%(condtopy(math['cond']),s)
            mathstr='='+mathstr
            math['text']=mathstr
        field['math']=math
    upstreamFields.difference_update(computedFields.keys())  # do this here in case fields are not in dependency order [otherPlaceHere]
    # reorder by deps to avoid undefined vars
    delays=[]
    upstreamFieldsList=list(upstreamFields)
    for name,f in computedFields.iteritems():
        for depfield in f['deps']:
            if depfield['uniqname'] not in upstreamFieldsList:
                delays.append(name)
    for name in delays:
        val=computedFields[name]
        del computedFields[name]
        computedFields[name]=val
    return fields,computedFields,upstreamFields
def mathStatus(computedFields):
    # computedFields are computed from other, dependent fields
    #   If a computed field has no dependencies, 
    #   either its dependencies are missing or the field isnt really computed [a bug either way].
    #   This is a coarse measure--even a perfect score could mask incorrect dependency lists.
    nComputedFieldsWithDeps=sum(1 for f in computedFields.values() if f['deps'])
    nComputedFieldsSansDeps=sum(1 for f in computedFields.values() if not f['deps'])
    return nComputedFieldsWithDeps,nComputedFieldsSansDeps

# nonforms are numbers that dont represent forms
nonforms=[str(yr) for yr in range(2000,2050)]
''' nonformcontexts are text signals that the number to follow is not a form.  eg:
    line 40
    lines 40 through 49
    pub 15
    Form 1116, Part II
    use Schedule EIC to give the IRS informationabout
    2439[instructions] ... and the tax shown in box 2 on the Form 2439 for each owner must agree with the amounts on Copy B that you received from the RIC or REIT.
    3903: This amount should be shown in box 12 of your Form W-2 with code P
    2015/f1040sd: Box A
    '''
nonformcontexts='box line lines through pub part parts to the copy copies code'.split()
def findFormRefs(formName,prefix,dirName,draws,pageinfo):
    if 'r' not in cfg.steps:
        return
    class PrintableFunc:
        # for debugging
        def __call__(self,o):
            return self.ypos==o.get('ypos',None)
        def __repr__(self):
            return str(self.ypos)
        def __str__(self):
            return str(self.ypos)
    # maybeForms should be called formContext or expectingFormsOnThisLine
    maybeForms=PrintableFunc()
    class FormRefs:
        # list of key,val,context tuples w/ set of keys for uniqness
        def __init__(self):
            self.set=set()
            self.list=[]
            self.nErrs=0
        def add(self,*info):
            if info[0]=='err':
                self.nErrs+=1
                return False
            elif info[0]=='excludedform':
                log.info('FormRefs: ignoring excludedform')
                return False
            (key,val),context=info
            self.set.add((key,val))
            self.list.append(((key,val),context))
            return True
        def __contains__(self,key):
            return key in self.set
        def keys(self):
            return iter(self.set)
        def items(self):
            return iter(self.list)
        def status(self):
            return (len(self.list),self.nErrs)  # like 'wins n losses'
        def __repr__(self):
            return ut.pf(sorted(self.set))
    def checkForm(formish,sched=None,**kw):
        # filter out excludedforms and require presence in allpdfnames
        # partly not needed after issues/formInfoPass
        if ',' in formish:
            formish=formish.split(',')
        context=kw
        if sched:
            formish=formish,sched
        try:
            form,sched=formish
            formFnames=possibleFilePrefixes((form,sched))
        except ValueError:
            form,sched=formish,None
            formFnames=possibleFilePrefixes(form)
        # check excludedformsPttn before allpdfnames cuz excludedforms are included in allpdfnames
        m=re.match(domain.excludedformsPttn,form)
        if m:
            log.debug('ignoring excludedform: {}'.format(m.group()))
            return ['excludedform']
        for formFname in formFnames:
            if formFname in cfg.allpdfnames:
                context['fprefix']=formFname
                return (form,sched),context
        log.warn('unrecognizedRefs: not in allpdfnames: {} from {} originally {} eg {}'.format(formFnames,formish,context,cfg.allpdfnames[:4]))
        return ['err']
    def relaxRegex(pttnstr):
        # convert spaces in regex to string of [xfa] whitespace [and pipe chars]
        #   do this .only. for spaces not followed by a count [like * or + or {}]
        # u'\xa0' is unicode char used as newline [in xfa or just irs?]
        # eg f2438: 'Schedule  D (Form 1120)'  # note extra space
        '''
            # this doctest doesnt work [even when un-nested] due to \xa0
            >>> relaxRegex(r'(Form (\S+), Schedule (\S+)\b)')
            '(Form[ |\xa0]+(\S+),[ |\xa0]+Schedule[ |\xa0]+(\S+)\b)'
            '''
        return re.sub(r' ($|[^*+{])','[ |\xa0]+\\1',pttnstr)
    formrefs=FormRefs()
    lines=[]
    maybeForms.ypos=-99
    for idraw,el in enumerate(draws):
        rawtext=el['text']  # el.text for draws or el.speak for fields
        if not rawtext.strip():
            continue
        formsinline=[]
        lineHasForms=False
        iFormInLine=0
        txt=rawtext
        # todo match should be assigned the biggest string that will occur on the form.
        #   eg 'Schedule B' is better than just 'B'
        #   this way the user has a bigger area to click on.
        # 2015/8801: or 2014 Form 1041, Schedule I, line 55 
        # todo order searches by decreasing length?  alg: min length of a regex eg len(regex)-nSpecialChars where nSpecialChars=len(re.escape(regex))-len(regex)
        # todo nonformcontexts have not yet been removed, so eg could use 'line' here
        searches=[
            ('form,sched',  # arbitrary string to summarize this search
                # 1st field should be 'match', the rest should be 'form' or 'sched' with trailing '?' if optional
                'match form sched'.split(),
                # the actual pattern to seek
                r'(Form (\S+), Schedule (\S+)\b)'),
            ('schedAorBInForm',
                'match sched sched2? form'.split(),
                r'(Schedules? (\S+)(?: or (\S+))? *\(Form (\S+?)\))'),
            ('schedInFormAorB',
                'match sched form1 form2'.split(),
                r'(Schedules? (\S+) \(Form (\S+?) or (?:Form )?(\S+?)\))'),
            ]
        def fieldIsOptional(field): return field.endswith('?')
        for summa,matchfields,pttn in searches:
            formfields=[field for field in matchfields if field.startswith('form')]
            schedfields=[field for field in matchfields if field.startswith('sched')]
            matches=re.findall(relaxRegex(pttn),txt)
            for m in matches:
                lineHasForms=True
                d=dict(zip(matchfields,m))
                match=d['match']
                for formfield in formfields:
                    form=d[formfield].upper()
                    if fieldIsOptional(formfield) and not form:
                        continue
                    for schedfield in schedfields:
                        sched=d[schedfield].upper()
                        if fieldIsOptional(schedfield) and not sched:
                            continue
                        # context highlights the match we found [for logging]
                        context=txt.replace(match,'[['+match+']]')
                        if formrefs.add(*checkForm(form,sched,**dict(iFormInLine=iFormInLine,draw=el,match=match,form=formName,context=context))):
                            formsinline.append(jj(idraw,summa,jj(form,sched,delim=','),match,txt,delim='|'))
                        # remove the matching text to avoid matching a subset of it in subsequent searches
                        txt=txt.replace(match,'')
                        iFormInLine+=1
        # 'to' or 'if' as delimiters prevent (Schedule,1099) in 1040-cez: See the instructions for line I in the instructions for Schedule C to help determine if you are required to file any Forms 1099.
        # 8824: If more than zero, enter here and on Schedule D or Form 4797 (see instructions)  -> (8824,4797) wh is wrong, but may be tricky to get right
        nicetext=re.sub(u'[\s\xa0|]+',' ',txt)
        matches=re.findall(r'(((Form|Schedule)(?:s|\(s\))?)\s*(.+?))(?:[,\.;:\)]| to | if |$)',nicetext)
        for match in matches:
            context,fulltype,typ,rest=match
            words=rest.split()
            wordslower=rest.lower().split()
            def couldbeform(s):
                # Schedule EIC requires isalpha len to allow up to 3
                '''
                    >>> couldbeform('4962')
                    True
                    >>> couldbeform('2015')  # 2015 is in nonforms
                    False
                    >>> couldbeform('EIC')
                    True
                    '''
                return s  \
                    and ( \
                        (len(s)>=4 and s[0].isdigit()) \
                        or (len(s)<=3 and s[0].isalpha()) \
                        or (len(s)>1 and s[1]=='-')) \
                    and all(c.isupper() or c.isdigit() for c in s if c not in '-') \
                    and s not in nonforms \
                    and not s.startswith('1-800-')
            for signal in nonformcontexts:  # eg 'line' or 'pub'
                while signal in wordslower:
                    # excise eg 'line','19' from list
                    i=wordslower.index(signal)
                    # 'line 43' vs 'lines 43a and 43b'
                    gap=4 if signal=='lines' and len(wordslower)>i+2 and wordslower[i+2] in 'and or' else 2
                    words=words[:i]+words[i+gap:]
                    wordslower=wordslower[:i]+wordslower[i+gap:]
            for iword,txt in enumerate(words):
                if not txt: continue  # there wont always be an 'and/or' form
                txt=txt.strip('.,;()|')
                if txt==formName:
                    # omit mentions of the current form
                    continue
                if couldbeform(txt):
                    lineHasForms=True
                    def merge(formName,sched):
                        sched=sched.upper()
                        try:
                            # merge(('1040','A'), 'B') -> ('1040','B')
                            formName,fsched=formName
                            formName=formName.upper()
                        except:
                            # merge('1040','B') -> ('1040','B')
                            formName=formName.upper()
                        formName=formName.split('-')[0]  # 1120-reit -> 1120
                        return ','.join((formName,sched))
                    key=txt if typ=='Form' else merge(formName,txt)
                    if iword==0:
                        matchingtext=fulltype+' '+txt
                    else:
                        matchingtext=txt
                    checkedForm=checkForm(key,**dict(iFormInLine=iFormInLine,draw=el,match=matchingtext,form=formName,call='words'))
                    if formrefs.add(*checkedForm):
                        formsinline.append(jj(idraw,'couldbe',key,matchingtext,nicetext,delim='|'))
                        iFormInLine+=1
        # section for forms announced in previous layout object
        #   eg 1040/54 Other credits from Form: a 3800 b 8801 c ____
        if unicode(rawtext).strip(u' |\xa0').endswith('Form:'):
            maybeForms.ypos=el['ypos']
        elif maybeForms(el):
            for txt in rawtext.strip().split():
                txt=txt.strip(' .,;()|').upper()
                if len(txt)>1 and couldbeform(txt):
                    if formrefs.add(*checkForm(txt,**dict(iFormInLine=iFormInLine,draw=el,match=txt,form=formName,call='rawtext'))):
                        matchingtext=txt
                        formsinline.append(jj(idraw,'maybe',txt,matchingtext,rawtext,delim='|'))
                        iFormInLine+=1
        if lineHasForms:
            lines.extend(formsinline)
    with open(dirName+'/'+prefix+'-refs.txt','w') as f:
        f.write('\n'.join(lines).encode('utf8'))
    formrefs=findFormRefPoz(formrefs,pageinfo)
    return formrefs

def findFormRefPoz(formrefs,pageinfo):
    for form,ref in formrefs.items():
        matchingtext=ref['match'].replace('|','').strip()
        npage=ref['draw'].d['npage']
        try:
            textpoz=pageinfo[npage].textpoz
        except KeyError as e:
            log.warn(jj('noSuchPage: no page',npage,'in',form,'; ref:',ref))
            continue
        found=textpoz.find(matchingtext)
        if found:
            ref['bboxz']=[f.bbox for f in found]
    return formrefs

def layoutStatus(fields):
    def overlap(f1,f2):
        # where f1,f2 are fields
        bb1=Bbox(
            int(f1['xpos'].magnitude),
            int(f1['ypos'].magnitude),
            int(f1['xpos'].magnitude)+int(f1.get('xdim',Qnty(0)).magnitude),
            int(f1['ypos'].magnitude)+int(f1.get('ydim',Qnty(0)).magnitude))
        bb2=Bbox(
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

def linkfields(fields):
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
            if any(typ in f['coltype'] for typ in domain.possibleColTypes):
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
    return fieldsByName,fieldsByLine

def fixFormBugs(fields,cfg):
    if cfg.formyear in ('2012','2013'):
	for f in fields:
	    # fix an error in 2012,2013 f1040 [in which there is no line 59, only 59a and 59b]
	    # todo autodetect such errors by matching draw text w/ field text?
	    if 'Line 59. Cents.' in f['speak']:
		f['speak']=f['speak'].replace('Line 59','Line 60')
    return fields

def cleanupFiles(prefix):
    if 'c' in cfg.steps:
        rawXmlFname='{}/{}-text.xml'.format(cfg.dirName,prefix)
        fmtXmlFname='{}/{}-fmt.xml'.format(cfg.dirName,prefix)
        if ut.exists(rawXmlFname):
            removeFile(rawXmlFname)
        if ut.exists(fmtXmlFname):
            removeFile(fmtXmlFname)

def getNextForm(formName,recurselevel):
    # todo class Form would self.logname=[eg]computeFormId(...) and then it's avail everywhere
    log.name=formName
    if cfg.indicateProgress:
        msg='--------'+jj(formName,('recurselevel=%d'%(recurselevel) if cfg.recurse else ''))
        logg(msg,[stdout,log.warn])  # use warn level so that transition to new form is logged by default
    if type(formName)==str and formName.endswith('.pdf'):
        # pdf suffix means the file is local
        fname=formName
        url=None
    else:
        fname,url=dlform(formName,cfg.formyear,cfg.dirName)
    log.name=fname
    return fname
def getFormInfo(fname):
    prefix=fname.rsplit('.',1)[0]
    log.name=prefix
    fpath=cfg.dirName+'/'+prefix+'.pdf'
    docinfo,pageinfo=pdfInfo(fpath)
    formName=docinfo['formName']
    return prefix,fpath,docinfo,pageinfo,formName

statusmsgtmpl='layoutBoxes: {}found,{}overlapping,?missing,?spurious; refs: {}found,{}unrecognized,?missing,?spurious; computedFields: {}found,{}empty,?missing,?spurious'
def logFormStatus(formName,fv,formrefs):
    z=Bag()
    z.lgood,z.lerrs=layoutStatus(fv.fields)
    z.rgood,z.rerrs=formrefs.status() if formrefs else (0,0)
    z.mgood,z.merrs=mathStatus(fv.computedFields)
    statusmsg='form {} status: '.format(formName)+statusmsgtmpl.format(
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
        msg='failed to process %d forms: %s'%(len(formsfail),[domain.computeFormId(f) for f in formsfail])
        logg(msg,[log.error,stdout])
        logg('logfilename is "{}"'.format(cfg.logfilename))
    import json
    status.update({'f'+domain.computeFormId(f).lower():None for f in formsfail})
    statusStr=json.dumps(status.__dict__)
    # status is partial because missing,spurious values are unknown and thus omitted
    log.warn('status partial data: %s'%(statusStr))

def addFormsTodo(formsdone,formstodo,recurselevel,formrefs,formsfail):
    if cfg.recurse and (cfg.maxrecurselevel==RecurseInfinitely or recurselevel<cfg.maxrecurselevel):
        newforms=set(formrefs.keys()) \
            .difference(formsdone) \
            .difference(set(form for form,reclevel in formstodo)) \
            .difference(set(formsfail))
        formstodo.extend((f,1+recurselevel) for f in newforms)
        if ut.hasdups(formstodo,lambda (form,reclevel):form):
            raise Exception('formstodo hasdups')
    return formstodo

def packageFieldViews(fields,computedFields,upstreamFields,fieldsByName,fieldsByLine):
    bfields=[Bag(f.d) for f in fields]  # just to shorten field['a'] to field.a
    fieldviews=Bag(
        fields=fields,
        bfields=bfields,
        computedFields=computedFields,
        upstreamFields=upstreamFields,
        fieldsByName=fieldsByName,
        fieldsByLine=fieldsByLine,
        )
    return fieldviews

def opentaxforms(**args):
    global cfg,log
    cfg,log=setup(**args)
    dirName=cfg.dirName
    
    formstodo,formsdone,formsfail=[],[],[]
    formstodo.extend(cfg.formsRequested)
    cfg.indicateProgress=cfg.recurse or len(formstodo)>1
    status=Bag()
    
    while formstodo:
        formName,recurselevel=formstodo.pop(0)
        try:
            fname=getNextForm(formName,recurselevel)
            prefix,fpath,docinfo,pageinfo,formName=getFormInfo(fname)
            # fields refers to fillable fields only; draws are all (fillable and read-only/non-fillable) fields
            fields,draws=extractFields(prefix,dirName)
            fields=fixFormBugs(fields,cfg)
            fieldsByName,fieldsByLine=linkfields(fields)
            fields,computedFields,upstreamFields=computeMath(fields,draws,fieldsByLine,prefix)
            fv=packageFieldViews(fields,computedFields,upstreamFields,fieldsByName,fieldsByLine)
            formrefs=findFormRefs(formName,prefix,dirName,draws,pageinfo)
            schema.writeFormToDb(formName,cfg.formyear,fv.bfields,formrefs,prefix,pageinfo)
            html.writeEmptyHtmlPages(formName,dirName,prefix,fv,formrefs,pageinfo)
            cleanupFiles(prefix)
            formsdone.append(formName)
            formstodo=addFormsTodo(formsdone,formstodo,recurselevel,formrefs,formsfail)
            status[prefix]=logFormStatus(formName,fv,formrefs)
        except domain.CrypticXml as e:
            # eg 1040 older than 2012 fails here
            log.error(jj('EEEError',e.__class__.__name__,str(e)))
            formsfail.append(formName)
        except Exception as e:
            log.error(jj('EEEError',traceback.format_exc()))
            if cfg.debug: raise
            formsfail.append(formName)
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

