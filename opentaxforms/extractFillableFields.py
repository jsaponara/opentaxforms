
from ut import setupLogging,exists,skip,NL,Qnty,pf,run
from irs import commandPtn,possibleColTypes,CrypticXml
from sys import exc_info
import re

from re import compile
ESC_PAT = compile(r'[\000-\037&<>()"\042\047\134\177-\377]')
def escape(s):
    '''
        >>> escape('<field name="blah">')
        '&#60;field name=&#34;blah&#34;&#62;'
        '''
    return ESC_PAT.sub(lambda m:'&#%d;' % ord(m.group(0)), s)
UNESC_PAT=compile(r'&#(\d+);')
def unescape(s):
    '''
        >>> unescape('&#60;field name=&#34;blah&#34;&#62;')
        '<field name="blah">'
        '''
    return UNESC_PAT.sub(lambda m:chr(int(m.group(1))),s)
def unescapeline(line):
    return unescape(line.replace('&#10;','').replace('&#13;',''))
def getRawXml(prefix,path='.'):
    xmltextfname='%s/%s-text.xml'%(path,prefix)
    if exists(xmltextfname):
        log.debug('xml text file already exists [{}]'.format(xmltextfname))
        xmlAsStr=open(xmltextfname).read()
    else:
        log.debug('creating xml text file [{}]'.format(xmltextfname))
        f=open('%s/%s.xml'%(path,prefix),'rb')
        datanamespace='xfa-template'
        fieldFrags=[]
        for line in f:
            if datanamespace in line:
                # just in case there are multiple data elements with the target datanamespace
                # must not give multiple toplevel elements to lxml to avoid 'lxml.etree.XMLSyntaxError: Extra content at the end of the document'
                log.debug( 'found datanamespace' )
                if fieldFrags:
                    log.warn('skipping [{}] chars of xml, already have [{}] chars'.format(len(line),len(fieldFrags[0])))
                else:
                    fieldFrags.append(unescapeline(line))
        xmlAsStr='\n'.join(f for f in fieldFrags if f and 'form checksum' not in f)
        if not xmlAsStr:
            xmlAsStr='\n'.join(f for f in fieldFrags if f)
        if not xmlAsStr.strip():
            raise CrypticXml('cannot textify xml file for form {}'.format(prefix))
        open(xmltextfname,'w').write(xmlAsStr)
        f.close()
    return xmlAsStr

def collectTables(tree,namespaces):
    tableEls=tree.xpath('//*[@layout="table"]',namespaces=namespaces)
    tables={}
    for el in tableEls:
        tablename=el.attrib.get('name','nameless')
        key=computePath(el,namespaces)
        maxhs=[]
        for iele,ele in enumerate(el.xpath('.//*[@layout="row"]',namespaces=namespaces)):
            rowname=ele.attrib.get('name','nameless')
            # todo for maxheight in each row, assuming just need 'h' attrib, but f1040/line6ctable also has node w/ lineHeight attrib
            cells=ele.xpath('./*[@h or @minH]',namespaces=namespaces)
            if iele==0:
                # get titles from 1st row
                def getcoltext(elem,namespaces):
                    txts=list(elem.xpath('.//*[@style]/text()',namespaces=namespaces))
                    alltxt=' '.join(txts).replace(u'\xa0','')
                    m=re.match(commandPtn,alltxt)
                    if m:
                        colinstruction=alltxt[m.start():]
                    else:
                        colinstruction=''
                    ctitles=[txt[:3].strip('()') for txt in txts if len(txt)>=3 and txt[0]=='(' and txt[2]==')' and txt[1].islower()]
                    coltext=(' '.join(txts)).lower()
                    coltype=' '.join(coltype for coltype in possibleColTypes if coltype in coltext)
                    return ctitles[0] if ctitles else '', coltype, colinstruction
                coltitles,coltypes,colinstructions=zip(*[getcoltext(elem,namespaces) for elem in cells])
            try:
                maxh=max([Qnty.fromstring(c.attrib.get('h',c.attrib.get('minH'))) for c in cells])
                log.debug('row name:'+ele.attrib.get('name','nameless')+' maxh:'+str(maxh))
            except:
                log.debug('oops row,cell names: '+','.join([el.attrib.get('name','nameless'),ele.attrib.get('name',str(ele.attrib))]))
                raise
            maxhs.append(maxh)
        if maxhs:
            tables[key]=dict(
                # elements in tables may not be directly assigned a width; widths are set for the columns so must track the column of each element
                colwidths=el.attrib['columnWidths'],
                maxheights=maxhs,
                coltitles=coltitles,
                coltypes=coltypes,
                colinstructions=colinstructions,
                )
    return tables

from itertools import chain
def computePath(el,namespaces):
    return '.'.join(reversed(list(ele.attrib.get('name','%s#%d'%(ele.tag,indexAmongSibs(ele,ele.tag,namespaces))) for ele in chain([el],el.iterancestors()))))
def indexAmongSibs(el,tag=None,namespaces=None):
    if not tag:
        tag='*'
    elif callable(tag):
        tag=str(tag).replace(' ','').replace('-','').strip('<>')
    if '}' in tag:
        tag='t:'+skip(tag,'}')
    p=el.getparent()
    if p is None:
        return 1
    return p.xpath('%s'%(tag,),namespaces=namespaces).index(el)

def parseXml(xmlAsStr,pathPrefix=None):
    '''
        xmlAsStr -> etree parse tree
        optionally write pretty_print'd xml to "-fmt.xml" file
        '''
    from lxml import etree
    from StringIO import StringIO
    parser=etree.XMLParser(encoding='utf-8',recover=True)
    tree=etree.parse(StringIO(xmlAsStr),parser)
    if pathPrefix:
        xmlfmtfname='%s-fmt.xml'%(pathPrefix)
        if not exists(xmlfmtfname):
            open(xmlfmtfname,'w').write(
                etree.tostring(tree, pretty_print=True)
                )
    return tree

def ensurePathsAreUniq(fields):
    fieldsbyid=set()
    for f in fields:
        if f['path'] in fieldsbyid:
            log.error('dup paths [%s]'%(f['path']))
        fieldsbyid.add(f['path'])
    assert len(fields)==len(fieldsbyid),'dup paths?  see log'

def extractFields(form,dirName='.'):
    # create <form>.xml, single-line <form>-text.xml, and formatted <form>-fmt.xml
    global cfg,log
    from config import cfg,log
    prefix=form.prefix
    fields=form.fields
    visiblz=form.draws
    if 'x' not in cfg.steps:
        return
    pathprefix='%s/%s'%(dirName,prefix)
    def xmlFromPdf(pathprefix):
        outname='%s.xml'%(pathprefix)
        if not exists(outname):
            dumppdfName='dumppdf.py'
            run('%s -at %s.pdf > %s.xml'%(dumppdfName,pathprefix,pathprefix))
    xmlFromPdf(pathprefix)
    xmlAsStr=getRawXml(prefix,dirName)
    tree=parseXml(xmlAsStr,pathprefix)
    namespaces={'t':"http://www.xfa.org/schema/xfa-template/2.8/"}
    tables=collectTables(tree,namespaces)
    fieldEls=tree.xpath('//t:draw[t:value]|//t:field',namespaces=namespaces)
    prevTable=None
    for iel,el in enumerate(fieldEls):
        def getvar(varname):
            varnames=varname.split()
            for varname in varnames:
                try:
                    # in some draws, eg in 1040a, "h='=0mm'"
                    q=Qnty.fromstring(el.attrib[varname])
                    break  # to avoid trying 2nd varname, if any
                except:
                    q=Qnty.fromstring('0mm')
            return q
        xpos,ypos,hdim,wdim=[getvar(varname) for varname in ('x','y','h minH','w')]
        isfield=el.tag.endswith('field')
        isdraw=not isfield
        if isfield:
            # caption node isnt v.informative (or even common), at least for f1040schedB
            istextbox=bool(el.xpath('t:ui/t:textEdit',namespaces=namespaces))
            ischeckbox=bool(el.xpath('t:ui/t:checkButton',namespaces=namespaces))
            isReadonly=el.attrib.get('access')=='readOnly'
            speakNodes=el.xpath('t:assist/t:speak',namespaces=namespaces)
            if speakNodes:
                speak=unicode(speakNodes[0].text).encode('utf-8')
            else:
                speak=''
            code=el.xpath('t:items/t:text',namespaces=namespaces)
            if code:
                code=unicode(code[0].text).encode('utf-8')
            else:
                code=None
            captionText=el.xpath('t:caption/descendant-or-self::text()',namespaces=namespaces)
            if captionText:
                captionText=u'|'.join(unicode(t) for t in captionText)
            else:
                captionText=''
            # captionReserve info allows our textbox to avoid encompassing the caption
            captionReserveNodes=el.xpath('t:caption[@reserve]',namespaces=namespaces)
            if captionReserveNodes:
                xCaptionReserve=yCaptionReserve=wCaptionReserve=hCaptionReserve=Qnty(0,'inch')
                captionReserveNode=captionReserveNodes[0]
                captionReserve=Qnty.fromstring(captionReserveNode.attrib.get('reserve'))
                if captionReserveNode.attrib.get('placement','left') in 'right left':
                    if captionReserveNode.attrib.get('placement')=='right':
                        wCaptionReserve=captionReserve
                    else:
                        xCaptionReserve=wCaptionReserve=captionReserve
                    xpos+=xCaptionReserve
                    wdim-=wCaptionReserve
                else: # placement is top or bottom
                    if captionReserveNode.attrib.get('placement')=='top':
                        yCaptionReserve=captionReserve
                        hCaptionReserve=captionReserve
                    else:
                        hCaptionReserve=captionReserve
                    ypos+=yCaptionReserve
                    hdim-=hCaptionReserve
            multiline=False
            maxchars=None
            if istextbox:
                #hscrolllist=el.xpath('t:ui/t:textEdit/@hScrollPolicy',namespaces=namespaces)
                #hscroll=not hscrolllist or hscrolllist[0]!='off'
                multilinelist=el.xpath('t:ui/t:textEdit/@multiLine',namespaces=namespaces)
                multiline=multilinelist and multilinelist[0]=='1'
                maxcharslist=el.xpath('t:value/t:text/@maxChars',namespaces=namespaces)
                maxchars=maxcharslist[0] if maxcharslist else None
            if istextbox and not ischeckbox:
                typ='text'
            elif not istextbox and ischeckbox:
                typ='checkbox'
            else:
                # default to textbox but warn
                typ='text'
                uinodes=el.xpath('t:ui',namespaces=namespaces)
                if uinodes:
                    uikids=uinodes[0].getchildren()
                    info=str(uikids)
                else:
                    info=str(el.attrib)
                log.warn('not sure of element type: textbox, checkbox, other?  '+info)
        else:  # el is a draw 
            assert el.tag.endswith('draw'),'expected tag.endswith "draw" instead got tag=='+el.tag
            texts=el.xpath('*/t:exData/*/*/descendant-or-self::text()',namespaces=namespaces)
            if not texts:
                texts=el.xpath('t:value/t:text/descendant-or-self::text()',namespaces=namespaces)
            if texts:
                text='|'.join(texts)
            else:
                continue
        # climb node ancestry for relative position info
        from itertools import chain
        # to see entire subtree of field nodes, xmllint --format --recover form.xml [where form.xml is written above]
        path=[]
        # for fields in tables [if any]--typically in the table ancestor element
        currTable=None
        npage=None
        from itertools import chain
        for a in chain([el],el.iterancestors()):
            p=a.getparent()
            # todo are these two conditions the same?  if so, not-p is likely more general
            if a.tag.endswith('template') or p is None:
                break
            xpos+=Qnty.fromstring(p.attrib.get('x','0mm'))
            ypos+=Qnty.fromstring(p.attrib.get('y','0mm'))
            if p.attrib.get('name','').startswith('Page') and p.attrib.get('name')[4].isdigit():
                # or could assume that subforms just below the topmost are the pages/copies
                npage=int(p.attrib.get('name')[len('Page')])
            elif p.attrib.get('name','').startswith('Copy'):
                npage=ord(p.attrib.get('name')[len('Copy')].lower())-ord('a')+1
            idxfornamelessnode='[%d]'%(p.index(a)-1)
            if 'name' in a.attrib:
                ancname=a.get('name')
                sibsOfSameName=[c for c in p.getchildren() if c.get('name')==ancname]
                idxOfNamedNode='[%d]'%(sibsOfSameName.index(a))
                idx=idxOfNamedNode
            else:
                import re
                tag=re.sub(r'{.*}','',a.tag)
                ancname='#%s'%(tag)
                idx=idxfornamelessnode
            path.append(ancname+idx)
            if isfield:
                # todo maybe attrib layout="table" [as in collectTables] is better to use than existence of attrib columnWidths
                layout=p.attrib.get('layout')
                if layout=='table':
                    # record name of table
                    currTable=computePath(p,namespaces)
                elif layout=='row':
                    # record index of current row
                    irow=list(p.getparent().xpath('*[@layout="row"]')).index(p)
                    icol=list(p.xpath('t:draw|t:field|t:subform',namespaces=namespaces)).index(a)
        path='.'.join(p for p in reversed(path) if p)
        elname=el.attrib.get('name',path)
        coltitle=''
        coltype=''
        colinstruction=''
        if currTable:
            if currTable!=prevTable:
                # this is the first element in the table, so read the columnWidths and set icol to 1st column
                columnWidths=[Qnty.fromstring(width) for width in tables[currTable]['colwidths'].split()]
                cumColWidths=[sum(columnWidths[0:i],Qnty(0,columnWidths[0].units)) for i in range(len(columnWidths))]
                maxheights=tables[currTable]['maxheights']
                rowheights=[sum(maxheights[0:i],Qnty(0,maxheights[0].units)) for i in range(len(maxheights))]
                coltitles=tables[currTable]['coltitles']
                coltypes=tables[currTable]['coltypes']
                colinstructions=tables[currTable]['colinstructions']
                prevTable=currTable
                # todo chkboxes [and textboxes in tables] have more specific dims--reduce wdim,hdim,xpos,ypos by <field><margin> [see notes/27sep2013]
            try:
                wdim=columnWidths[icol]
            except Exception as e:
                msg='; icol,columnWidths=%s,%s'%(icol,columnWidths)
                raise type(e),type(e)(e.message+msg),exc_info()[2]
            try:
                ypos+=rowheights[irow]
            except Exception as e:
                msg='; irow,rowheights=%s,%s\n%s'%(irow,rowheights,pf(locals()))
                raise type(e),type(e)(e.message+msg),exc_info()[2]
            try:
                xpos+=cumColWidths[icol]
            except Exception as e:
                msg='; icol,cumColWidths=%s,%s'%(icol,cumColWidths)
                raise type(e),type(e)(e.message+msg),exc_info()[2]
            try:
                coltitle=coltitles[icol]
                coltype=coltypes[icol]
                colinstruction=colinstructions[icol]
            except Exception as e:
                msg=e.message+'; icol,coltitles,coltypes,colinstructions=%s,%s,%s,%s'%(icol,coltitles,coltypes,colinstructions)
                log.error(msg)
        if not npage:
            continue  # skip draw elements not assoc'd w/ a page; they are in some header
        if npage<1:
            log.warn('rejecting visibl [{}] on invalid page [{}]'.format(elname,npage))
            continue
        d=dict(el.attrib.iteritems())  # todo is el.attrib needed here?
        d.update(dict(
            i=iel,
            name=elname,  # this way there's a name key even if the element has no name attrib
            tag=el.tag,
            path=path,
            xpos=xpos,
            ypos=ypos,
            hdim=hdim,
            wdim=wdim,
            npage=npage,
            ))
        if isfield:
            d.update(dict(
                typ=typ,
                speak=speak,
                code=code,   # for checkboxes eg MJ for married filing jointly
                multiline=multiline,
                maxchars=maxchars,
                text=captionText,
                isReadonly=isReadonly,
                currTable=currTable,
                coltitle=coltitle,
                coltype=coltype,
                colinstruction=colinstruction,
                ))
        else:
            d.update(dict(
                text=text,
                parentForm=prefix,
                ))
        class El(dict):
            '''
                delegate to dict but override __str__
                # todo generalize at least the keys selected
                '''
            def __str__(self):
                speaklinecol=self.d.get('speak','<<speakless>>')
                try:
                    lineidx=speaklinecol.lower().index('line ')
                    speaklinecol=speaklinecol[lineidx:]
                except: pass
                col=''
                try:
                    # seek cols a-r since 's' occurs often as "Form(s)" and 18 cols is plenty!
                    parenchars=re.findall(r'\([a-r]\)',speaklinecol)
                    if parenchars and parenchars[0] not in speaklinecol[:13]:
                        col=parenchars[0]
                except: pass
                def shortname():
                    name=self.get('name','<<nameless>>')
                    if '.' in name:
                        name='....'+[n for n in name.split('.') if n][-1]
                    return name
                if self.get('tag','').endswith('draw'):
                    return "{name=%s,text=%s}"%(shortname(),self.get('text','--'))
                else:
                    return "{name=%s,speak=%s%s,unit=%s...}"%(shortname(),speaklinecol[:13],col,self.get('unit','--'))
        d=El(d)
        if isfield:
            fields.append(d)
            visiblz.append(d)  # because captionText is visible
        else:
            visiblz.append(d)
    ensurePathsAreUniq(fields)
    log.info('found [{}] fields, [{}] visiblz'.format(len(fields),len(visiblz)))
    with open(dirName+'/'+prefix+'-visiblz.txt','w') as f:
        f.write(NL.join(x['text'].encode('utf8') for x in visiblz))
    # fields refers to fillable fields only; draws are all (fillable and read-only/non-fillable) fields
    form.fields=fields
    form.draws=visiblz

def saveFields(fields,prefix):
    from cPickle import dump
    picklname='%s.pickl'%(prefix)
    pickl=open(picklname,'w')
    dump(fields,pickl)
    pickl.close()


from argparse import ArgumentParser
def parse_cli():
    '''Load command line arguments'''
    parser = ArgumentParser(description='extract field info of a PDF.')
    parser.add_argument('-p','--prefix', metavar='PREFIX',
                    nargs='?', help='prefix for names of files generated')
    parser.add_argument('infile', metavar='pdf_file',
                    nargs='?', default='stdin',
                    help='PDF file to extract from')
    parser.add_argument('-l', '--loglevel', help='Set loglevel',
                      default='WARN', metavar='LOG_LEVEL')
    parser.add_argument('-t', '--doctests', help='Run doctests',
                       action="store_true")
    return parser.parse_args()

def main():
    args=parse_cli()
    infile=args.infile
    def prefixify(s):
        return s.rsplit('.',1)[0]
    prefix=args.prefix or prefixify(infile)
    if prefix=='stdin': prefix=__name__
    global log
    log=setupLogging(prefix,args)
    if args.doctests:
        import doctest; doctest.testmod()
        import sys; sys.exit()
    if infile=='stdin':
        import sys
        f=sys.stdin
    else:
        f=open(infile)
    class Form: pass
    form=Form()
    form.prefix=prefix
    form.fields=[]
    form.draws=[]
    extractFields(form)
    if infile!='stdin':
        f.close()
    saveFields(form.fields,prefix)
    log.info(pf(form.fields))

if __name__ == '__main__': main()


