from __future__ import absolute_import
import re
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import (
    LTTextBox, LTTextLine, LTTextBoxHorizontal, LAParams, LTChar,
    LTTextLineHorizontal
)
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdftypes import resolve1
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from six.moves.urllib.request import urlopen
from six.moves.urllib.error import URLError, HTTPError

from . import ut, irs
from .ut import log, ntuple, logg, stdout, Qnty, NL, pathjoin
from .config import cfg
from .xmp import xmp_to_dict
from .cmds import CommandParser, normalize, adjustNegativeField, CannotParse

# global so that theyre pickle-able
PageInfo = ntuple('PageInfo', 'pagenum pagewidth pageheight textpoz')
TextPozStruct = ntuple('TextPozStruct', 'text bbox chars charobjs')


class Form(object):
    def __init__(self, name, recurselevel):
        self.formName = name
        self.name = name
        self.recurselevel = recurselevel
        self.fields = []
        self.draws = []
        self.refs = []
        self.computedFields = ut.odict()
        self.upstreamFields = set()
        self.isCryptic = False
        try:
            form,sched = name
            self.nameAsTuple = name
        except ValueError:
            try:
                form,sched = name.split('s',1)
                assert form and sched
                self.nameAsTuple = form,sched
            except (ValueError,AttributeError):
                self.nameAsTuple = name, None

    def __eq__(self,o):
        return self.nameAsTuple==o.nameAsTuple

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return '<Form %s>' % (self.name, )

    def getFile(self, failurls):
        if hasattr(self.name, 'endswith') and self.name.endswith('.pdf'):
            # pdf suffix means the file is local
            fname = self.name
            url = None
        else:
            fname, url = self.download(cfg.formyear, failurls, cfg.dirName)
        log.name = fname
        self.fname = fname
        self.url = url

    def readInfo(self):
        prefix = self.fname.rsplit('.', 1)[0]
        log.name = prefix
        self.prefix = prefix
        pathPlusPrefix = pathjoin(cfg.dirName, prefix)
        self.fpath = pathPlusPrefix + '.pdf'
        cacheprefix = pathPlusPrefix + '-pdfinfo'
        infocache = None if not cfg.useCaches else ut.unpickle(cacheprefix)
        if infocache is None:
            self.docinfo, self.pageinfo = self.pdfInfo()
            ut.pickle((self.docinfo, self.pageinfo), cacheprefix)
        else:
            self.docinfo, self.pageinfo = infocache
        # todo should store this separately from self.name?
        self.name = self.docinfo['formName']

    def fixBugs(self):
        if cfg.formyear in ('2012', '2013'):
            for f in self.fields:
                # fix an error in 2012,2013 f1040 [in which there is no line
                # 59, only 59a and 59b] todo autodetect such errors by matching
                # draw text w/ field text?
                if 'Line 59. Cents.' in f['speak']:
                    f['speak'] = f['speak'].replace('Line 59', 'Line 60')

    def download(self, year, failurls, dirName='forms'):
        # download form from irs.gov into {dirName} if not already there
        formName = self.name
        year = int(year)
        formNamesToTry = irs.possibleFilePrefixes(formName)
        msgs = []
        foundfile = False
        url = ''
        if year < cfg.latestTaxYear:
            fnametmpl = '%(formName)s--%(year)s.pdf'
        else:
            fnametmpl = '%(formName)s.pdf'
        for formName in formNamesToTry:
            fname = fnametmpl % dict(formName=formName, year=year)
            destfname = formName + '.pdf'
            destfpath = pathjoin(dirName, destfname)
            if ut.exists(destfpath):
                foundfile = True
                break
        if not foundfile:
            for formName in formNamesToTry:
                fname = fnametmpl % dict(formName=formName, year=year)
                destfname = formName + '.pdf'
                destfpath = pathjoin(dirName, destfname)
                if not cfg.okToDownload:
                    msg = 'oops no ' + destfpath + ' and not okToDownload'
                    logg(msg, [log.error, stdout])
                    exit()
                try:
                    if year < cfg.latestTaxYear:
                        url = irs.prevurltmpl % (fname, )
                    else:
                        url = irs.currurltmpl % (fname, )
                    if url in failurls:
                        continue
                    log.warn(
                        'downloading: ' + url + ' for ' + formName +
                        ' from ' + url)
                    fin = urlopen(url, 'rb')
                    if fin.getcode() != 200:
                        # not a pdf, just an html error page
                        continue
                    pdf = fin.read()
                    fin.close()
                    fout = open(destfpath, 'wb')
                    fout.write(pdf)
                    fout.close()
                    foundfile = True
                    break
                except HTTPError:
                    msgs.append('HTTPError at ' + url)
                    failurls.add(url)
                except URLError as e:
                    log.error(e)
                    raise
        if not foundfile:
            if not msgs:
                msgs.append('url does not exist:  {}'.format(url))
            raise Exception('\n'.join(msgs))
        return destfname, url

    def pdfInfo(self):
        # collect metadata from pdf file at document and page levels
        with open(self.fpath, 'rb') as fp:
            parser = PDFParser(fp)
            doc = PDFDocument(parser)
            docinfo = {}
            if 'Metadata' in doc.catalog:
                metadata = resolve1(doc.catalog['Metadata']).get_data()
                xmpdict = xmp_to_dict(metadata)
                docinfo['titl'] = xmpdict['dc']['title']['x-default']
                docinfo['desc'] = xmpdict['dc']['description']['x-default']
                docinfo['isfillable'] = (
                    xmpdict['pdf'].get('Keywords', '').lower() == 'fillable')
                anyMonth = 'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec'
                titlePttn1 = re.compile(ut.compactify(
                    r'''(?:(\d\d\d\d) )?   # 2016
                    Form ([\w-]+           # Form 1040
                    (?: \w\w?)?)           # AS
                    (?: or ([\w-]+))?      # or 1040A
                    (?:  ?\(?(?:Schedule ([\w-]+))\)?)?  # (Schedule B)
                    (?:  ?\((?:Rev|'''+anyMonth+''').+?\))?\s*$'''
                    ))
                # eg 2016 Form W-2 AS
                # eg 2015 Form 1120 S (Schedule D)
                # eg 2015 Form 990 or 990-EZ (Schedule E)
                # eg Form 8818  (Rev. December 2007)
                # eg Form 8849  (Schedule 2)  (Rev. January 2009)
                # eg Form 1066 (Schedule Q) (Rev. December 2013)
                # eg Form 1120S Schedule B-1 (December 2013)
                # 'Rev' means 'revised'
                m = re.search(titlePttn1, docinfo['titl'])
                if m:
                    taxyr, form1, form2, sched = m.groups()
                else:
                    titlePttn2 = re.compile(ut.compactify(
                        r'''(?:(\d\d\d\d) )?   # 2016
                        Schedule ([\w-]+)[ ]   # Schedule B
                        \(Form ([\w-]+)        # (Form 1040
                        (?: or ([\w-]+))? ?\)  # or 1040A)
                        (?: \((?:Rev|'''+anyMonth+''').+?\))?\s*$''',
                        ))
                    # eg 2015 Schedule M-3 (Form 1065)
                    # eg 2015 Schedule O (Form 990 or 990-EZ)
                    # eg Schedule O (Form 1120) (Rev. December 2012)
                    # eg Schedule C (Form 1065 ) (Rev. December 2014)
                    m = re.search(titlePttn2, docinfo['titl'])
                    if m:
                        taxyr, sched, form1, form2 = m.groups()
                    else:
                        msg = docinfo['titl'] + ' dont fit'
                        log.error(msg)
                        raise Exception(msg)
                docinfo['taxyr'] = taxyr
                form = form1 if not form2 or len(form1) < len(form2) else form2
                docinfo['form'] = form
                docinfo['sched'] = sched
                docinfo['formName'] = form if not sched else (form, sched)
                docinfo['fpath'] = self.fpath
            # Check if the document allows text extraction. If not, abort.
            if not doc.is_extractable:
                raise Exception('PDFTextExtractionNotAllowed')
            pageinfo = {}
            rr = Renderer()
            # for ipage,page in enumerate(doc.get_pages()):
            for ipage, page in enumerate(PDFPage.create_pages(doc)):
                pagenum = 1 + ipage
                if page.cropbox != page.mediabox:
                    log.warn(
                        'boxesDontMatch: cropbox!=mediabox on page %d:'
                        ' cropbox=%s; mediabox=%s',
                        pagenum, page.cropbox, page.mediabox)
                pagewidth = Qnty(
                    page.cropbox[2] - page.cropbox[0], 'printers_point')
                pageheight = Qnty(
                    page.cropbox[3] - page.cropbox[1], 'printers_point')
                pageinfo[pagenum] = PageInfo(
                    pagenum, pagewidth, pageheight, rr.renderPage(page))
        return docinfo, pageinfo

    def orderDependencies(self):
        # reorder by deps to avoid undefined vars
        computedFields = self.computedFields
        self.upstreamFields.difference_update(computedFields.keys())
        delays = []
        upstreamFieldsList = list(self.upstreamFields)
        for name, f in computedFields.items():
            for depfield in f['deps']:
                if depfield['uniqname'] not in upstreamFieldsList:
                    delays.append(name)
        for name in delays:
            val = computedFields[name]
            del computedFields[name]
            computedFields[name] = val

    def computeMath(self):
        # determines which fields are computed from others
        # 'dep' means dependency
        fields = self.fields if 'm' in cfg.steps else []
        for field in fields:
            math = CommandParser(field, self)
            speak = normalize(field['speak'])
            adjustNegativeField(field, speak)
            colinstruction = normalize(field['colinstruction'])
            instruction = colinstruction if colinstruction else speak
            sentences = re.split(r'\.\s*', instruction)
            for s in sentences:
                try:
                    math.parseInstruction(s, field)
                    log.debug('found [%s] in sentence [%s] in field %s',math,s,field['uniqname'])
                except CannotParse as e:
                    log.debug('%s',e)
            if math and math.terms:
                # todo checkbox instructions refer to the named textbox
                # eg 2016/8814/line15
                #    p1-cb2    Line 15. Tax. Is the amount on line 14 less than $1,050? No. Enter $105 here and see the Note below. Note. If you checked the box on line C above, see the instructions. Otherwise, include the amount from line 15 in the tax you enter on Form 1040, line 44, or Form 1040N R, line 42. Be sure to check box a on Form 1040, line 44, or Form 1040N R, line 42.
                #    p1-cb2L1T Line 15. Yes. Multiply line 14 by 10 percent (.10). Enter the result here and see the Note below. Note: If you checked the box on line C above, see the instructions. Otherwise, include the amount from line 15 in the tax you enter on Form 1040, line 44, or Form 1040N R, line 42. Be sure to check box a on Form 1040, line 44, or Form 1040N R, line 42.
                #    p1-t37    Line 15. Tax. Dollars.
                #    p1-t38    Line 15. Cents.
                # for now we just suppress the math here
                if field['typ']!='checkbox':
                    math.assembleFields()
            field['math'] = math
        self.orderDependencies()
        self.bfields = [ut.Bag(f) for f in fields]
        # just to shorten field['a'] to field.a


class Renderer(object):
    def __init__(self):
        # Create a PDF resource manager object that stores shared resources.
        rsrcmgr = PDFResourceManager()
        # la=layout analysis
        laparams = LAParams()
        self.device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        self.interpreter = PDFPageInterpreter(rsrcmgr, self.device)
        self.textPoz = None

    def renderPage(self, page):
        self.interpreter.process_page(page)
        layout = self.device.get_result()
        # http://denis.papathanasiou.org/2010/08/04/extracting-text-images-
        # from-pdf-files/
        textPoz = TextPoz()
        for lt in layout:
            if isinstance(lt, (LTTextBoxHorizontal, LTTextBox, LTTextLine)):
                textPoz.add(lt)
        return textPoz


class TextPoz(object):
    # text positions
    FormPos = ntuple('FormPos', 'itxt ichar chrz bbox')

    def __init__(self):
        self.textPoz = []

    def add(self, ltobj):
        def quantify(tupl, unit):
            return [Qnty(qnty, unit) for qnty in tupl]

        def accum(ltobj, ltchars, chars):
            for lto in ltobj:
                if isinstance(lto, LTChar):
                    ltchartext = lto.get_text()
                    ltchars.append(
                        (ltchartext,
                         ut.Bbox(*quantify(lto.bbox, 'printers_point'))))
                    chars.append(ltchartext)
                elif isinstance(lto, LTTextLineHorizontal):
                    accum(lto, ltchars, chars)
        ltchars = []
        chars = []
        accum(ltobj, ltchars, chars)
        self.textPoz.append(TextPozStruct(
            ltobj.get_text(),
            ut.Bbox(*quantify(ltobj.bbox, 'printers_point')),
            ''.join(chars),
            ltchars))

    def optimize(self):
        # todo ensure objs are arranged by line (ie ypos) and left-to-right
        # within line
        pass

    def find(self, s):
        if not s:
            raise Exception('empty string')

        def findstr(sl, found):
            for itxt, (txt, bbx, chrz, charobjs) in enumerate(self.textPoz):
                chrz = chrz.lower()
                # require target to be bordered by start/end of string,
                # whitespace, or punctuation to avoid matching a mere subset of
                # the actual form referenced [eg to avoid finding '1040' in
                # '1040EZ']
                slsafe = re.escape(sl)
                slsafeExact = r'(?:^|[\s\W])(' + slsafe + r')(?:$|[\s\W])'
                for m in re.finditer(slsafeExact, chrz):
                    if m:
                        ichar = m.start()
                        bbox1 = charobjs[ichar][1]
                        bbox2 = charobjs[ichar + len(sl) - 1][1]
                        if not (bbox1.y0 == bbox2.y0 and bbox1.y1 == bbox2.y1):
                            log.info('bbox.y coords dont match for [%s]', sl)
                        bbox = ut.merge(bbox1, bbox2)
                        found.append(
                            TextPoz.FormPos(
                                itxt, ichar,
                                chrz[ichar: ichar + len(sl)], bbox))
                    else:
                        break
            return found
        sl = s.lower()
        found = []
        while not found:
            found = findstr(sl, found)
            if not found and ' ' in sl:
                sl = sl.rsplit(None, 1)[-1]
            else:
                break
        if not found:
            log.warn('textNotFound: ' + s + ' in ' + self.alltext().replace(
                NL, ' [newline] '))
        if len(found) > 1:
            msgtmpl = 'textRepeats: found too many (returning all of them),' \
                ' seeking %s in %s ... [run in debug mode for fulltext]: %s'
            log.info(
                msgtmpl, s, self.alltext().replace(NL, '  ')[:60], str(found))
            log.debug(' fulltext: seeking %s in %s',
                      s, self.alltext().replace(NL, '  '))
        return found

    def alltext(self):
        return NL.join(o.text for o in self.textPoz)
