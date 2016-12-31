import re
import ut
from ut import jj,numerify
import irs

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

def computeMath(form):
    global cfg,log
    from config import cfg,log
    fields,draws,fieldsByLine,prefix=form.fields,form.draws,form.fieldsByLine,form.prefix
    # determines which fields are computed from others
    # 'dep' means dependency
    fields,draws=(fields,draws) if 'm' in cfg.steps else ([],[])
    Term=ut.ntuple('Term','linenum unit uniqname npage'); linenumk,unitk,namek,pagek=Term._fields
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
        #currLine,unit=findLineAndUnit(speak) todo maybeWrong !
        currLine,unit=field['linenum'],field['unit']
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
            m=re.match(irs.commandPtn,s)
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
    form.computedFields=computedFields
    form.upstreamFields=upstreamFields
    form.bfields=[ut.Bag(f) for f in fields]  # just to shorten field['a'] to field.a

