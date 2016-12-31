import re
import ut
from ut import jj
import irs

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
def findRefs(form,dirName):
    global cfg,log
    from config import cfg,log
    if 'r' not in cfg.steps:
        return
    formName=form.formName
    prefix=form.prefix
    pageinfo=form.pageinfo
    draws=form.draws
    theform=form
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
            formFnames=irs.possibleFilePrefixes((form,sched))
        except ValueError:
            form,sched=formish,None
            formFnames=irs.possibleFilePrefixes(form)
        # check excludedformsPttn before allpdfnames cuz excludedforms are included in allpdfnames
        m=re.match(irs.excludedformsPttn,form)
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
    theform.refs=formrefs

def findFormRefPoz(formrefs,pageinfo):
    for form,ref in formrefs.items():
        matchingtext=ref['match'].replace('|','').strip()
        npage=ref['draw']['npage']
        try:
            textpoz=pageinfo[npage].textpoz
        except KeyError as e:
            log.warn(jj('noSuchPage: no page',npage,'in',form,'; ref:',ref))
            continue
        found=textpoz.find(matchingtext)
        if found:
            ref['bboxz']=[f.bbox for f in found]
    return formrefs

