import re
import six
import opentaxforms.ut as ut
from opentaxforms.ut import log, jj, pathjoin, asciiOnly
from opentaxforms.config import cfg
import opentaxforms.irs as irs

# nonforms are numbers that dont represent forms
nonforms = [str(yr) for yr in range(2000, 2050)]
''' nonformcontexts are text signals that the number to follow is not a form.
    eg:
    line 40
    lines 40 through 49
    pub 15
    Form 1116, Part II
    use Schedule EIC to give the IRS informationabout
    2439[instructions] ... and the tax shown in box 2 on the Form 2439
        for each owner must agree with the amounts on Copy B that you received
        from the RIC or REIT.
    3903: This amount should be shown in box 12 of your Form W-2 with code P
    2015/f1040sd: Box A
    8814/p4/line10 instructions: unrecaptured section 1250 gain, section 1202 gain, ...
    '''
nonformcontexts = (
    'box line lines through pub part parts section to the copy copies code'.split())


def findRefs(form):
    if 'r' not in cfg.steps:
        return
    dirName = cfg.dirName
    formName,schedName = form.nameAsTuple
    prefix = form.prefix
    pageinfo = form.pageinfo
    draws = form.draws
    theform = form

    class PrintableFunc(object):

        # for debugging
        def __call__(self, o):
            return self.ypos == o.get('ypos', None)

        def __repr__(self):
            return str(self.ypos)

        def __str__(self):
            return str(self.ypos)
    # maybeForms should be called formContext or expectingFormsOnThisLine
    maybeForms = PrintableFunc()

    class FormRefs(object):

        # list of key,val,context tuples w/ set of keys for uniqness
        def __init__(self):
            self.set = set()
            self.list = []
            self.nErrs = 0

        def add(self, *info):
            if info[0] == 'err':
                self.nErrs += 1
                return False
            elif info[0] == 'excludedform':
                log.info('FormRefs: ignoring excludedform')
                return False
            (key, val), context = info
            key=asciiOnly(key)
            val=asciiOnly(val)
            self.set.add((key, val))
            self.list.append(((key, val), context))
            return True

        def __contains__(self, key):
            return key in self.set

        def keys(self):
            return iter(self.set)

        def items(self):
            return iter(self.list)

        # like 'wins n losses'
        def status(self):
            return (len(self.list), self.nErrs)

        def __repr__(self):
            return ut.pf(sorted(self.set))

    def checkForm(formish, sched=None, **kw):
        # filter out excludedforms and require presence in allpdfnames
        # partly not needed after issues/formInfoPass
        if ',' in formish:
            formish = formish.split(',')
        context = kw
        if sched:
            formish = formish, sched
        try:
            form, sched = formish
            formFnames = irs.possibleFilePrefixes((form, sched))
        except ValueError:
            form, sched = formish, None
            formFnames = irs.possibleFilePrefixes(form)
        # check excludedformsPttn before allpdfnames cuz excludedforms are
        # included in allpdfnames
        m = re.match(irs.excludedformsPttn, form)
        if m:
            log.debug('ignoring excludedform: %s',m.group())
            return ['excludedform']
        for formFname in formFnames:
            if formFname in cfg.allpdfnames:
                context['fprefix'] = formFname
                return (form, sched), context
        log.warn(u'unrecognizedRefs: not in allpdfnames:'
                 u' %s from %s originally %s eg %s',
                 formFnames, formish, context, cfg.allpdfnames[:4])
        return ['err']

    def relaxRegex(pttnstr):
        # convert spaces in regex to string of [xfa] whitespace [and pipe
        # chars] do this .only. for spaces not followed by a count [like * or +
        # or {}] u'\xa0' is unicode char used as newline [in xfa or just irs?]
        # eg f2438: 'Schedule  D (Form 1120)'  # note extra space
        '''
            # this doctest doesnt work [even when un-nested] due to \xa0
            >>> relaxRegex(r'(Form (\S+), Schedule (\S+)\b)')
            '(Form[ |\xa0]+(\S+),[ |\xa0]+Schedule[ |\xa0]+(\S+)\b)'
            '''
        return re.sub(r' ($|[^*+{])', '[ |\xa0]+\\1', pttnstr)
    formrefs = FormRefs()
    lines = []
    maybeForms.ypos = -99
    # when we see 'Schedule D (Form 1040)' we record '1040' as
    #   scheduleContext['d'] for later solo mentions of 'Schedule D'
    scheduleContext={}
    for idraw, el in enumerate(draws):
        rawtext = el['text']  # el.text for draws or el.speak for fields
        if not rawtext.strip():
            continue
        formsinline = []
        lineHasForms = False
        iFormInLine = 0
        txt = rawtext
        # todo match should be assigned the biggest string that will occur on
        # the form. eg 'Schedule B' is better than just 'B' this way the user
        # has a bigger area to click on. 2015/8801: or 2014 Form 1041, Schedule
        # I, line 55
        # todo order searches by decreasing length?  alg: min length
        # of a regex eg len(regex)-nSpecialChars where
        # nSpecialChars=len(re.escape(regex))-len(regex) todo nonformcontexts
        # have not yet been removed, so eg could use 'line' here
        searches = [
            ('form,sched',  # arbitrary string to summarize this search
                            # 1st field should be 'match'; the
                            #   rest should be 'form' or 'sched'
                            #   with trailing '?' if optional
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

        def fieldIsOptional(field):
            return field.endswith('?')
        for summa, matchfields, pttn in searches:
            formfields = [field for field in matchfields if field.startswith(
                'form')]
            schedfields = [field for field in matchfields if field.startswith(
                'sched')]
            matches = re.findall(relaxRegex(pttn), txt)
            for m in matches:
                lineHasForms = True
                d = dict(zip(matchfields, m))
                match = d['match']
                formvalues=[val.lower() for key,val in d.items() if key.startswith('form')]
                schedvalues=[val.lower() for key,val in d.items() if key.startswith('sched')
                    and val]
                def inSameFamily(*formnames):
                    '''
                        >>> inSameFamily(['1040','1040A','1040EZ'])
                        True
                        >>> inSameFamily(['1040','1120'])
                        False
                        >>> inSameFamily(['1040'])
                        True
                        '''
                    for f in formnames:
                        for g in formnames[1:]:
                            if f.lower() not in g.lower() and \
                               g.lower() not in f.lower():
                                # neither is a substring of the other
                                return False
                    return True
                if len(schedvalues)==1:
                    sched=schedvalues[0].lower()
                    if len(formvalues)==1:
                        scheduleContext[sched]=formvalues[0].lower()
                    else:
                        # len(formvalues)==1
                        thisform,thissched=theform.nameAsTuple
                        if thisform.lower() in formvalues and thissched.lower() in schedvalues:
                            # ignore self-mentions and assume forms use the same schedule
                            # eg ignore "Schedule B (Form 1040 or 1040A)" in f1040sb
                            #    because we are in Schedule B already,
                            #    and we assume that 1040A uses 1040's sched B.
                            txt = txt.replace(match, '')
                            continue
                        elif inSameFamily(*formvalues):
                            # in 'schedX(form1 or form2) assume both forms use the same schedX
                            #   if both forms are in the same form family [eg 1040 and 1040A]
                            #   and separate schedX's dont occur in allpdfnames.
                            formvaluesToRemove=[f.lower() for f in formvalues
                                if ('f%ss%s'%(f,sched)).lower() not in cfg.allpdfnames]
                            formfields=[k for k,v in d.items() if k.startswith('form') and v.lower() not in formvaluesToRemove]
                            if len(formfields)==1:
                                scheduleContext[sched]=d[formfields[0]].lower()
                for formfield in formfields:
                    form = d[formfield].upper()
                    if fieldIsOptional(formfield) and not form:
                        continue
                    for schedfield in schedfields:
                        sched = d[schedfield].upper()
                        if fieldIsOptional(schedfield) and not sched:
                            continue
                        # context highlights the match we found [for logging]
                        context = txt.replace(match, '[[' + match + ']]')
                        if formrefs.add(
                           *checkForm(
                               form, sched,
                               **dict(
                                 iFormInLine=iFormInLine, draw=el, match=match,
                                 form=formName, context=context))):
                            formsinline.append(
                                jj(
                                    idraw, summa, jj(form, sched, delim=','),
                                    match, txt, delim='|'))
                        # remove the matching text to avoid matching a subset
                        # of it in subsequent searches
                        txt = txt.replace(match, '')
                        iFormInLine += 1
        # 'to' or 'if' as delimiters prevent (Schedule,1099) in 1040-cez: See
        # the instructions for line I in the instructions for Schedule C to
        # help determine if you are required to file any Forms 1099. 8824: If
        # more than zero, enter here and on Schedule D or Form 4797 (see
        # instructions)  -> (8824,4797) wh is wrong, but may be tricky to get
        # right
        nicetext = re.sub(u'[\s\xa0|]+', ' ', txt)
        p = '(((Form|Schedule)(?:s|\(s\))?)\s*(.+?))(?:[,\.;:\)]| to | if |$)'
        matches = re.findall(p, nicetext)
        for match in matches:
            context, fulltype, typ, rest = match
            words = rest.split()
            wordslower = rest.lower().split()

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
                return (
                    s and (
                        (len(s) >= 4 and s[0].isdigit())
                        or (len(s) <= 3 and s[0].isalpha())
                        or (len(s) > 1 and s[1] == '-'))
                    and
                    all(c.isupper() or c.isdigit() for c in s if c not in '-')
                    and s not in nonforms and not s.startswith('1-800-'))
            for signal in nonformcontexts:  # eg 'line' or 'pub'
                while signal in wordslower:
                    # excise eg 'line','19' from list
                    i = wordslower.index(signal)
                    # 'line 43' vs 'lines 43a and 43b'
                    gap = (
                        4
                        if signal == 'lines' and len(wordslower) > i + 2
                        and wordslower[i + 2] in 'and or'
                        else 2)
                    words = words[:i] + words[i + gap:]
                    wordslower = wordslower[:i] + wordslower[i + gap:]
            for iword, txt in enumerate(words):
                if not txt:
                    continue  # there wont always be an 'and/or' form
                txt = txt.strip('.,;()|')
                if txt == formName:
                    # omit mentions of the current form
                    continue
                if couldbeform(txt):
                    lineHasForms = True

                    def merge(formName, sched):
                        try:
                            # merge(('1040','A'), 'B') -> ('1040','B')
                            formName, fsched = formName
                        except ValueError:
                            # merge('1040','B') -> ('1040','B')
                            pass
                        formName = formName.split('-')[0]  # 1120-reit -> 1120
                        return ','.join((formName, sched)).upper()
                    if typ=='Schedule':
                        formcontext=scheduleContext.get(txt.lower(),formName)
                    else:
                        formcontext=formName
                    key = txt if typ == 'Form' else merge(formcontext, txt)
                    if iword == 0:
                        matchingtext = fulltype + ' ' + txt
                    else:
                        matchingtext = txt
                    checkedForm = checkForm(key, **dict(
                        iFormInLine=iFormInLine, draw=el, match=matchingtext,
                        form=formName, call='words'))
                    if formrefs.add(*checkedForm):
                        formsinline.append(
                            jj(idraw, 'couldbe', key,
                               matchingtext, nicetext, delim='|'))
                        iFormInLine += 1
        # section for forms announced in previous layout object
        #   eg 1040/54 Other credits from Form: a 3800 b 8801 c ____
        if six.text_type(rawtext).strip(u' |\xa0').endswith('Form:'):
            maybeForms.ypos = el['ypos']
        elif maybeForms(el):
            for txt in rawtext.strip().split():
                txt = txt.strip(' .,;()|').upper()
                if len(txt) > 1 and couldbeform(txt):
                    if formrefs.add(*checkForm(txt, **dict(
                         iFormInLine=iFormInLine, draw=el, match=txt,
                         form=formName, call='rawtext'))):
                        matchingtext = txt
                        formsinline.append(
                            jj(idraw, 'maybe', txt,
                               matchingtext, rawtext, delim='|'))
                        iFormInLine += 1
        if lineHasForms:
            lines.extend(formsinline)
    with open(pathjoin(dirName, prefix) + '-refs.txt', 'wb') as f:
        for line in lines:
            f.write(line.encode('utf8') + b'\n')
    formrefs = findFormRefPoz(formrefs, pageinfo)
    theform.refs = formrefs


def findFormRefPoz(formrefs, pageinfo):
    for form, ref in formrefs.items():
        matchingtext = ref['match'].replace('|', '').strip()
        npage = ref['draw']['npage']
        try:
            textpoz = pageinfo[npage].textpoz
        except KeyError:
            log.warn(jj('noSuchPage: no page', npage,
                        'in', form, '; ref:', ref))
            continue
        found = textpoz.find(matchingtext)
        if found:
            ref['bboxz'] = [f.bbox for f in found]
    return formrefs
