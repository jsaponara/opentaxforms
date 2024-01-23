from __future__ import absolute_import
import six
import re

from . import irs
from .ut import log, jj, ddict, rstripAlpha, Qnty
from .config import cfg


def findLineAndUnit(field):
    '''
    >>> import logging
    >>> log.addHandler(logging.NullHandler())
    >>> s='Payments, Credits, and Tax. Line 7. Federal income tax ... Dollars.'
    >>> findLineAndUnit(s)
    ('line7', 'dollars')
    >>> findLineAndUnit('Line 7. Cents.')
    ('line7', 'cents')
    >>> findLineAndUnit('Personal identification number (P I N). 5 digits. ')
    (None, '')
    >>> findLineAndUnit('Page 2. Worksheet for Line 5, ...')
    (None, '')
    >>>
    f2106ez/part1/line1: without the dots in units pttn,
      unit here would be cents
    >>> findLineAndUnit('Part 1. Figure Your Expenses. Line 1.'
        ' Complete Part 2. Multiply line 8a by 55.5 cents (.555).'
        ' Enter the result here. Dollars.')
    ('line1', 'dollars')
    >>> findLineAndUnit("Part 1. Persons ... (If ..., see the instructions.)"
        " Line 1. Item 1. (a) Care provider's name. Caution. If the care was"
        " provided in your home, you may owe employment taxes. If you do,"
        " you cannot file Form 1040A. For details, see the instructions for"
        " Form 1040, line 60a, or Form 1040N R, line 59a. 2 lines available"
        " for entry.")  # f2441
    ('line1', '')
    >>> findLineAndUnit("4. Number of qualifying children under age 17 with the required social security number.")
    ('line4', 'number')
    '''
    speak = field['speak']
    log.debug('speak %s',speak)
    if isinstance(speak, six.binary_type):
        speak = speak.decode('utf8')
    speak = re.sub(r'Page \d+\.\s*', '', speak)
        # remove any eg "Page 2. " eg 1040/2022/line16
    # print('speak',speak)
    # todo unify searches and if-else via walrus op.
    findLineNum1 = re.search(r'(?:[\.\)]+\s*|^)(Line\s*\w+)\.(?:\s*\w\.)?', speak)
        # Line 62. a. etc
    findLineNum1a = re.search(r'\b(\d\d?)\.(?:.+:)\s*(\w)\.', speak)
        # 2020/1040/10a: 10. Adjustments to income: a. From Schedule 1, line 22.
        # 2022/1040/25a: Payments. 25. Federal income tax withheld from: a. Form(s) W-2.
    findLineNum1b = re.search(r'\b(\d\d?)\.\s*(\d)\.', speak)
        # 2022/1040/16/checkboxes: 16. 2. 4972.
    findLineNum2 = re.search(r'(?:\.\s*)(\d\d?)\.(?:\s*\w\.)?', speak)
        # Exemptions. 62. a. etc
    findLineNum2a = re.search(r'(?:\.\s*)(\d\d?\w?)\.', speak)
        # Income. Attach Form(s) W-2 here. Also attach Forms W-2G and 1099-R if tax was withheld. If you did not get a Form W-2, see instructions. 1a. Total amount from Form(s) W-2, box 1 (see instructions).
    findLineNum3 = re.search(r'^(\d\d?\w*)\.\s', speak)
        # 16b. ... eg 990/page6/line16b
    if cfg.formyear <= 2017:  # todo was 2017 the last year of Dollars and Cents?
        units = re.findall(r'\.?\s*(Dollars|Cents)\.?', speak, re.I)
    elif 'Number of' in speak:
        units = ['number']
    else:
        # we assume very wide fields are not quantities
        # eg 2020/1040sb amount fields are ~30mm wide [amt fields are also labeled "Amount." but not eg in 1040]
        if field['name'].startswith('f') and field['wdim'] < Qnty(50,'mm'):
            units = ['dollars']
        else:
            units = None
    if findLineNum1:
        # linenum is eg 'line62a' for 'Line 62. a. etc' or even for
        # 'Exemptions. 62. a. etc'
        linenum = findLineNum1.groups()[0]
    elif findLineNum1a:
        num, num_or_letter = findLineNum1a.groups()
        delim = '_' if num_or_letter.isdigit() else ''
        linenum = 'line' + num + delim + num_or_letter
    elif findLineNum1b:
        num_line, num_checkbox = findLineNum1b.groups()
        linenum = f'line{num_line}_{num_checkbox}'
    elif findLineNum2:
        linenum = 'line' + findLineNum2.groups()[0]
    elif findLineNum2a:
        linenum = 'line' + findLineNum2a.groups()[0]
    elif findLineNum3:
        linenum = 'line' + findLineNum3.groups()[0]
    else:
        linenum = None
        if 'amount' in speak or re.search(r'line\s+\d+', speak, re.I):
            log.warning(jj('linenumNotFound: cannot find the linenum in:', speak))
    if linenum:
        linenum = linenum.lower().replace(' ', '').replace('.', '')
    unit = units[-1].lower().strip(' .') if units else ''
    return linenum, unit


def computeUniqname(f, fieldsSofarByName):
    # [0] becomes L0T cuz L,T look like square brackets to me
    pathsegs = f['path'].replace('[', 'L').replace(']', 'T').split('.')
    i = -1
    name = f['name']
    uniqname = name
    while uniqname in fieldsSofarByName:
        uniqname = '_'. join(seg for seg in pathsegs[i:])
        i -= 1
        if i < -len(pathsegs):
            msg = (
                'cannot generate unique key from path segments %s in keys %s'
                % (pathsegs, fieldsSofarByName.keys()))
            log.error(msg)
            raise Exception(msg)
    return uniqname


def unifyTableRows(fieldsByRow):

    # force cells in each row to have same linenum as leftmost cell.
    # eg 2020/1040sh/line17
    # todo consider adding tolerance, eg if y,y+ht overlap >=90% for two cells
    #   then theyre in the same row
    def byPageAndYpos(pg_ypos_val):
        '''
            >>> byPageAndYpos((1,'67.346 mm'),['et','cetera'])
            (1,67.346)
            '''
        (pg, ypos), val = pg_ypos_val
        return (pg, float(ypos.split(None, 1)[0]))
    most_recent_linenum = None
    for row, fs in sorted(fieldsByRow.items(), key=byPageAndYpos):
        page, ht = row
        fs.sort(key=lambda f: f['xpos'])
        if fs[0].get('currTable'):
            ll0 = fs[0]['linenum'] or most_recent_linenum
                # todo is there a better way to handle null linenum in a leftmost cell?
                #      eg can prevent it?
            for f in fs[1:]:
                if f['linenum'] != ll0:
                    f['linenum-orig'] = f['linenum']
                    f['linenum'] = ll0
                    msgtmpl = 'leftmostCellOverride: p%d: changed %s' \
                              ' in field %s to %s from leftmost field %s'
                    log.info(
                        msgtmpl, page, f['linenum-orig'], f['uniqname'],
                        ll0, fs[0]['uniqname'])
            most_recent_linenum = fs[0]['linenum']


def uniqifyLinenums(ypozByLinenum, fieldsByLine, fieldsByLinenumYpos):
    # compute and assign unique linenums
    for lnum in ypozByLinenum:
        # using noncentFields to ensure just one field per ypos
        # eg dollar-and-cent pair usu at same ypos
        # newcode but wks for 1040,1040sb
        pg, linenumm = lnum
        noncentFields = [
            ff for ff in fieldsByLine[lnum]
            if ff['unit'] != 'cents']
        dupLinenumz = len(noncentFields) > 1
        ypozz = [ff['ypos'] for ff in noncentFields]
        for iypos, ypos in enumerate(sorted(ypozz)):
            for ff in fieldsByLinenumYpos[(pg, linenumm, ypos)]:
                if linenumm is None:
                    uniqlinenum = None
                elif dupLinenumz:
                    # todo ensure the delimiter char ['_'] doesnt occur in any
                    # linenum
                    uniqlinenum = ff['linenum'] + '_' + str(1 + iypos)
                else:
                    uniqlinenum = ff['linenum']
                ff['uniqlinenum'] = uniqlinenum
                if uniqlinenum: log.debug('uniqifyLinenums: pg=%s, uniqlinenum=%s', pg, uniqlinenum)


def linkfields(form):
    # link and classify fields: dollar and cent; by line; by name
    fields = form.fields
    ypozByLinenum = ddict(set)
    fieldsByLinenumYpos = ddict(list)
    fieldsByName = {}
    fieldsByLine = ddict(list)
    fieldsByNumericLine = ddict(list)
    fieldsByRow = ddict(list)
    fprev = None
    for f in fields:
        uniqname = computeUniqname(f, fieldsByName)
        fieldsByName[uniqname] = f
        f['uniqname'] = uniqname
        pg = f['npage']
        l, u = findLineAndUnit(f)
        log.debug('l_and_u=%s,%s.', l, u)
        # use page,linenum as key
        #   eg f3800 has line3 on both page1 and page3.
        #   so p1/line6 deps on which line3?
        # todo can fields w/ same linenum occur on same page?
        #   eg f990/p12/line1?  thus must track section numbers as well?
        lnumeric = rstripAlpha(l)
        log.debug('linkfields l,lnumeric=%s,%s.', l, lnumeric)
            # eg if l=='5a' then lnumeric=='5'
            # eg 2018/1040/line6: 'lines 1 through 5' really means thru 5a and 5b
            #    so if '5' not in fieldsByLine, try fieldsByNumericLine['5']
        fieldsByLine[(pg, l)].append(f)
        fieldsByNumericLine[(pg, lnumeric)].append(f)
        ypozByLinenum[(pg, l)].add(f['ypos'])
        fieldsByLinenumYpos[(pg, l, f['ypos'])].append(f)
        f['linenum'] = l
        f['unit'] = u.lower() if u else None
        if f['unit'] is not None:
            if any(typ in f['coltype'] for typ in irs.possibleColTypes):
                f['unit'] = None  # 'dollars'
        if u == 'cents':
            # todo should check abit more, eg approx dollars.ypos==cents.ypos
            # and dollars.xpos+dollars.wdim==cents.xpos
            cc, dd = f, fprev
            if dd['unit'] != 'dollars':
                # occasionally dollars fields are not so labeled
                # eg 2015/f1040sse/line7 and 2015/f8814/line5
                # speak has the amt but not always with a "$"
                # todo always true for pre-filled fields?
                msgtmpl=('expectedDollars: expected field [%s]'
                         ' to have unit==dollars, instead got [%s]'
                         ' from previous speak: [%r]')
                log.warning(msgtmpl, dd['uniqname'], dd['unit'], dd['speak'])
                dd['unit'] = 'dollars'
                dd['expectedDollars'] = 1  # just in case it's useful later
            dd['centfield'] = cc
            cc['dollarfieldname'] = dd['uniqname']
        elif b'Numbers after the decimal.' in f['speak']:
            cc, dd = f, fprev
            assert b'Numbers before the decimal.' in dd['speak']
            #assert dd['unit'] is None
            dd['centfield'] = cc
            cc['dollarfieldname'] = dd['uniqname']
            dd['unit'] = 'dollars'
            cc['unit'] = 'cents'
            dd['realunit'] = 'ratio'
        fieldsByRow[(pg, str(f['ypos']))].append(f)
        fprev = f
    unifyTableRows(fieldsByRow)
    uniqifyLinenums(ypozByLinenum, fieldsByLine, fieldsByLinenumYpos)
    form.fieldsByName = fieldsByName
    form.fieldsByLine = fieldsByLine
    form.fieldsByNumericLine = fieldsByNumericLine
