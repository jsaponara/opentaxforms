import re
import ut
from ut import log, jj, numerify
import irs

Term = ut.ntuple('Term', 'linenum unit uniqname npage')
linenumk, unitk, namek, pagek = Term._fields


def normalize(s):
    # replace each whitespace string with a single space
    return re.sub(r'\s+', ' ', s)


def condtopy(cond):
    '''
        >>> condtopy('line 2 is more than line 1')
        'line2>line1'
        '''
    delim = ' is more than '
    if delim in cond:
        lh, rh = cond.split(delim, 1)
        lh = lh.replace(' ', '')
        rh = rh.replace(' ', '')
        return '%s>%s' % (lh, rh)
    raise Exception('dunno condition [%s]' % (cond, ))


def lineOrRange(s, pg, fieldsByLine, col=None):
    '''
    todo add enough of fieldsByLine arg to make these work
    #>>> lineOrRange('46','1')
    #['line46']
    #>>> lineOrRange('56 through 62','1')
    #['line57', 'line62', 'line60b', 'line59', 'line60a', 'line61', 'line56', 'line58']
    '''
    log.debug('+lineOrRange s=%s col=%s', s, col)
    prefix = 'line'
    try:
        start, end = s.split(' through ', 1)
        if end.startswith(prefix):
            prefix = ''
        startnum, endnum = numerify(start), numerify(end)
        start, end = (prefix + start, prefix + end)
        # find horizontally aligned non-cent start and end fields
        log.debug(' lineOrRange pg=%s start=%s end=%s fieldsByLine.pg,start=%s fieldsByLine.pg,end=%s',
          pg, start, end, fieldsByLine[(pg, start)], fieldsByLine[(pg, end)])
        startxpoz = [f['xpos'] for f in fieldsByLine[(pg, start)] if f['unit'] != 'cents']
        endxpoz = [f['xpos'] for f in fieldsByLine[(pg, end)] if f['unit'] != 'cents']
        for pos in startxpoz:
            if pos in endxpoz:
                startxpos = endxpos = pos
                break
        else:
            # no matching xpos for start and end lines so just use rightmost xpos for each
            startxpos = max(startxpoz)
            endxpos = max(endxpoz)
        # todo make this less sensitive to adjustments in xpos
        #      for now, moved dx adjustment from top of computeMath [where it wrecked havoc] to writeEmptyHtmlPages/adjustxpos
        lines = ut.uniqify([(f['linenum'], f['unit'], f['xpos'])
            for k, fs in fieldsByLine.iteritems()
                for f in fs
                    if f['linenum'] \
                        and startnum <= numerify(f['linenum']) <= endnum \
                        and f['unit'] != 'cents' \
                        and (startxpos != endxpos or startxpos == f['xpos'])])
        lines = [x[0] for x in lines]
    except ValueError:  # really only want to catch 'ValueError: need more than 1 value to unpack'
        if s.startswith(prefix):
            prefix = ''
        lines = [prefix + s]
    if col:
        lines = [l + '.col.' + col for l in lines]
    log.debug('-lineOrRange lines=%s', lines)
    return lines


def adjustNegativeField(field, speak):
    m = re.search(r'open parenthes.s.*closed? parenthes.s', speak, re.I)
    if m:
        # this field is intrinsically a loss, ie, a negative number,
        #   w/o the user writing parens ob the parens are 'builtin' to the form
        #   eg f1040sd/line6/speak: Line 6. Open parentheses. Short-term capital loss carryover. Enter the amount...from line 8 of.... Close parentheses.
        #   todo could instead detect draw object w/ same x,y,w,h as field object and text r'\( +\)'
        field['sign'] = '-'
        dx = .05 * field['wdim']  # shift field rightward to make room for '('
        field['dx'] = dx


class Parser(object):

    def __init__(self, sentence):
        self.sentence = sentence
        self.cond = None

    def requireCouldBeCommand(self):
        if self.sentence.startswith('this is the amount'):
            # eg 1040/line75  this is the amount you overpaid
            #    'amount' here is not a cmd [and thus op is not '+']
            raise NoCommand('sentence.startswith "this is the amount": [%s]' % (self.sentence, ))
        elif 'total number of exemptions claimed' in self.sentence:
            # eg 1040a/line6d Total number of exemptions claimed.  Boxes checked on 6a and 6b
            # todo
            raise NoCommand('sentence.contains "total number of exemptions claimed": [%s]' % (self.sentence, ))
        # could be elim'd by allowing multi-word cmds
        elif 'amount' in self.sentence and 'amount from line ' not in self.sentence:
            # eg 2015/f5329/line3 Amount subject to additional tax. Subtract line 2 from line 1
            raise NoCommand('sentence.contains "amount" but not "amount from line": [%s]' % (self.sentence, ))

    def editCommand(self, field):
        ll = field['linenum']
        self.sentence = self.sentence.lower()
        if self.sentence.startswith('boxes checked on'):
            # insert implicit command
            self.sentence = 'howmany ' + self.sentence
        # 'Total of all amounts reported on line 3 for ...'  f1040se/23
        # 'Combine lines 7 and 15 and enter the result'      f1040sd/16
        # 'Boxes checked on 6a and 6b'   f1040/line6d [we prepend 'howmany']
        self.sentence = self.sentence.replace('the amounts in the far right column for ', '') \
           .replace('of all amounts reported on line ', 'lines ') \
           .replace(' and enter the result', '') \
           .replace('boxes checked on ', 'lines ') \
           .replace('boxes checked', 'lines ' + (ll if ll else ''))
        # remove "for all rental properties", "for all royalty properties", "for all properties"  f1040se/23
        self.sentence = re.sub(r' for all(?: \S+)? properties', '', self.sentence, re.I)

    def extractCondition(self):
        # todo complete this function--forms,s2 are unused
        # eg Form 1040 and 1040A filers: complete section B  [just made that up]
        formcondPtn = re.compile(r'form (\w+)(?: and (\w+))? filers: (\w+)', re.I)
        ifcondPtn = re.compile(r'if (.+?), (.+?)(?: otherwise,? (.+))?$')
        m = re.match(formcondPtn, self.sentence)
        if m:
            form1, form2, self.sentence = m.groups()
            assert form1, 'formcondPtn w/o form1!'
            #forms=[form1,form2] if form2 else [form1]
        else:
            #forms=None
            pass
        m = re.match(ifcondPtn, self.sentence)
        if m:
            self.cond, self.sentence, s2 = m.groups()

    def parseCommand(self):
        m = re.match(irs.commandPtn, self.sentence)
        if m:
            self.cmd, self.sentence = m.groups()
            return self.cmd, self.sentence
        else:
            raise NoCommand('no command found in [%s]' % (self.sentence, ))


class CannotParse(BaseException):
    pass


class TooManyTerms(CannotParse):
    pass


class NoCommand(CannotParse):
    pass


class CommandParser(object):
    def __init__(self, field, form):
        self.op = None
        self.terms = None
        self.constantUnit = None
        self.cond = None
        self.zcond = None
        self.text = None
        self.field = field
        self.form = form

    def parseAdd(math, cmd, s):
        fieldsByLine = math.form.fieldsByLine
        ll, pg = [math.field[key] for key in ('linenum', 'npage')]
        terms = math.terms
        op = '+'
        if s.startswith('lines '):
            # eg f1040sd: Combine lines 1a through 6 in column (h).
            s = s.replace('lines ', '')
            m = re.search(r' in column \((.)\)', s, re.I)
            col = None
            if m:
                col = m.group(1)
                s = s[:m.start()]
            terms = sorted(ut.flattened([lineOrRange(entry, pg, fieldsByLine, col) for entry in re.split(r' and |, (?:and )?', s)]), key=numerify)
        elif s.startswith('from line '):
            s = s.replace('from ', '')
            if '(' in s:
                s = s[:s.index('(')]
            s = s.replace(' ', '')
            terms = [s]
        elif s.startswith('the amounts on line '):
            s = s.replace('the amounts on', '').replace(' ', '')
            terms = [s]
        elif cmd == 'howmany' or s == 'numbers on lines above':
            terms = [ll]
        else:
            msg = 'cannotParse: cannot parse [{}] cmd [{}] on {}/p{}/{}'.format(cmd, s, math.form.prefix, pg, ll)
            log.warn(msg)
            if terms is None:
                op = '?'
                terms = []
        #math.update(dict(op=op,terms=terms))
        math.op = op
        math.terms = terms

    def parseSubOrMult(math, cmd, s):
        # eg 1040/line43 Subtract line 42 from line 41
        # eg 1040/line42 Multiply $3,800 by the number on line 6d
        # todo eg Subtract column (e) from column (d) and combine the result with column (g).
        #      * recognize this as columnMath, assoc w/ currTable, find cells via coltitle and setup terms; continue to apply columnMath throughout currTable
        #      1065b/p4/bottomSection/line1  In column (b), add lines 1c through 4b, 7, and 8. From the result, subtract line 14g
        delim, op = dict(
            subtract=(' from ', '-'),
            multiply=(' by (?:the number on )?', '*'),
            )[cmd]
        terms = re.split(delim, s, re.I)
        if len(terms) != 2:
            msg = 'oops, expected 2 terms for cmd [{}] using delim [{}] in [{}], found [{}]: [{}]'.format(cmd, delim, s, len(terms), terms)
            log.error(msg)
            # or just return empty like parseAdd
            raise TooManyTerms(msg)
        if ' and ' in terms[1]:
            m = re.search(r' and combine the result with (.*)$', terms[1], re.I)
            if m:
                terms[1] = terms[1][:m.start()]
                # NOTE this means op=='-' is really a-b+c+d+....
                terms.append(m.group(1))

                def linecolterm(term):
                    if 'column' in term:
                        lin, col = term.split('column')
                        lin = lin.strip()
                        col = col.strip(' ()')
                        return lin + '.col.' + col
                    else:
                        return term
                terms = [linecolterm(t) for t in terms]
            else:
                msg = 'cannotParse: cannot parse [%s]' % (terms[1], )
                log.warn(msg)
                op = '?'
        if op == '-':
            # swap 1st two terms cuz 'subtract a from b' means 'b-a'
            terms[0], terms[1] = terms[1], terms[0]
        terms = [re.sub(r'[\s\$,]', '', term) for term in terms]
        #math.update(dict(op=op,terms=terms))
        math.op = op
        math.terms = terms

    def parseEnter(math, s, cond):
        # eg 1040/line43: Line 43. Taxable income.  Subtract line 42 from line 41. If line 42 is more than line 41, enter zero. Dollars.
        #                 [[topmostSubform[0].Page2[0].p2-t10[0]]]
        # eg 4684/line4 : If line 3 is more than line 2, enter the difference here and skip lines 5 through 9 for that column.
        # eg 1040ez/line43: Line 6. ... If line 5 is larger than line 4, enter -0-.
        op, terms = math.op, math.terms
        cmd = 'enter'
        if s == 'zero':
            s = '-0-'
        elif cond and s.startswith('the difference here'):
            op = '-'
            m1 = re.match(r'(line \w+) is (less|more|larger|smaller|greater) than (line \w+)', cond)
            if m1:
                lineA, cmpOp, lineB = m1.groups()
                if cmpOp in ('more', 'larger', 'greater'):
                    terms = [lineA, lineB]
                else:
                    terms = [lineB, lineA]
                math.terms = terms
            else:
                msg = jj('cannotParseMath: cannot parse math: cmd,s,cond:', cmd, cond, s, delim='|')
                log.warn(msg)
                raise CannotParse(msg)
        return s

    def parseCondition(math, cmd, s, cond):
        # 1040/line43 line 42 is more than line 41
        # 1040/line42 line 38 is $154,950 or less
        # 1040/line4  the qualifying person is a child but not your dependent
        terms = math.terms
        if cond.startswith('zero or') and terms and len(terms) == 2:
            # 4684/line9: Subtract line 3 from line 8. If zero or less, enter -0-
            cond = terms[0].replace('line', 'line ') + ' is more than ' + terms[1].replace('line', 'line ')
        m1 = re.match(r'(line \w+) is (less|more|larger|smaller|greater) than (line \w+)', cond)
        m2 = re.match(r'(line \w+) is ([$\d,]+) or (less|more)', cond)
        condparse = None
        if m1:
            lineA, cmpOp, lineB = m1.groups()
            condparse = (
                '<' if cmpOp in ('less', 'smaller') else '>',
                lineA.replace(' ', ''),
                lineB.replace(' ', ''),
                )
        elif m2:
            line, amt, cmpOp = m2.groups()
            if '$' in amt:
                math.constantUnit = 'dollars'
            condparse = (
                '<=' if cmpOp == 'less' else '>=',
                line.replace(' ', ''),
                amt.replace('$', '').replace(',', ''),
                )
        else:
            log.warn(jj('cannotParseCond: cannot parse condition', cond))
        if condparse is not None:
            def flipcondition(cond):
                cmpOp, x, y = cond
                cmpOp = {
                    '<': '>=',
                    '<=': '>',
                    '>': '<=',
                    '>=': '<',
                    }[cmpOp]
                return (cmpOp, x, y)
            if cmd == 'enter' and s == '-0-':
                math.zcond = condparse
            else:
                log.debug(jj('397 how interpret condition?  assuming zcond=flipcondition', cond))
                math.zcond = flipcondition(condparse)

    def getFieldFromTerm(math, term, parentline, pgnum, fieldsByLine):
        # find fields that correspond to the term; parentline is lhs
        # typically returns the dollar and cent fields corresponding to a term such as 'line7'
        if term.isdigit():
            return [dict(typ='constant', uniqname=term, unit=None, val=term, npage=pgnum, linenum=term, centfield='centfield_of_constant')]
        if '.col.' in term:
            # field is in a table
            line, col = term.split('.col.')
            if not line:
                line = parentline
            returnFields = [field for field in fieldsByLine[(pgnum, line)] if field.get('coltitle') == col]
            if returnFields:
                return returnFields
            else:
                # if coltitle restricts fields down to zero, ignore it [eg 1040sd/line4-6 called 'column h'in line7]
                term = line
        found = fieldsByLine[(pgnum, term)]
        if not found:
            canGetValuesFromOtherPages = True
            if canGetValuesFromOtherPages:
                # assuming that most recent occurrence of term is intended
                #   term [eg 'line3'] may occur on multiple pages of the form
                sourcepage = pgnum - 1
                while not found and sourcepage >= 1:
                    found = fieldsByLine[(sourcepage, term)]
                    sourcepage -= 1
            else:
                # let the user fill the computed-from-other-page field manually
                found = []
        return found

    def assembleFields(math):
        op = math.op
        terms = math.terms
        math.text = ''
        myFieldName = math.field[namek]
        myFieldUnit = math.field[unitk]
        fieldsByLine = math.form.fieldsByLine
        ll, pg = [math.field[key] for key in ('linenum', 'npage')]
        if op == '*' and math.constantUnit == 'dollars':
            # eg 1040/line42 our dep fields are unitless cuz our constant is in dollars
            myFieldUnit = None
        upfields = [math.getFieldFromTerm(term, ll, pg, fieldsByLine) for term in terms]
        upfields = [upf for upfs in upfields for upf in upfs if upf[namek] != myFieldName and upf[unitk] == myFieldUnit]
        if op == '*':
            # todo revisit: here we assume that
            #      1. we want to multiply only two fields, and specifically
            #      2. we want the first and the last [and thus most derived/computed] field
            #      for 1040/line42, this gives a constant and the [computed] line6d
            if len(upfields) > 1:
                upfields = [upfields[0], upfields[-1]]
        math.form.upstreamFields.update([upf['uniqname'] for upf in upfields if upf.get('typ') != 'constant'])
        #math.form.upstreamFields.remove(myFieldName)  # do this later in case fields are not in dependency order [see laterIsHere]
        math.form.computedFields[myFieldName] = math.field
        math.field['deps'] = upfields
        math.field['op'] = op
        mathstr = op.join(terms)
        if math.cond:
            math.cond = ' if not %s else %s' % (condtopy(math.cond), self.pred)
        mathstr = '=' + mathstr
        math.text = mathstr

    def parseSentence(self, sentence, field):
        parser = Parser(sentence)
        parser.editCommand(field)
        parser.requireCouldBeCommand()
        parser.extractCondition()
        cmd, pred = parser.parseCommand()
        cond = parser.cond
        return cmd, cond, pred

    def parseInstruction(self, sentence, field):
        try:
            cmd, cond, pred = self.parseSentence(sentence, field)
            if cmd in ('add', 'combine', 'howmany', 'total', 'amount'):
                self.parseAdd(cmd, pred)
            elif cmd in ('subtract', 'multiply'):
                self.parseSubOrMult(cmd, pred)
            elif cmd in ('enter', ):
                pred = self.parseEnter(pred, cond)
            else:
                msg = jj('cannotParseCmd: cannot parse command: cmd pred cond:', cmd, pred, cond, delim='|')
                log.warn(msg)
                raise CannotParse(msg)
            if cond:
                self.parseCondition(cmd, pred, cond)
            # just for line: math.cond=' if not %s else %s'%(condtopy(math.cond),self.pred)
            self.pred = pred
        except CannotParse:
            raise
