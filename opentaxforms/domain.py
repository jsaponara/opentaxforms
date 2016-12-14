
# domain-specific code

import re
from config import cfg,log

# ignore employer forms: 1099's, 1098's, w2, w4, etc
excludedformsPttn=re.compile(r'109\d.*|w.*',re.I)

# commands that are common in tax instructions
verbs=[v.replace('_',' ') for v in 'add amount combine total howmany subtract multiply enter include check'.lower().split()]
verbPtn='|'.join(verbs)
commandPtn=re.compile('.*?('+verbPtn+r') (.+)',re.I)

possibleColTypes='proceeds cost adjustment gain loss'.lower().split()

# xml that we cannot currently parse, eg 1040 older than 2012
class CrypticXml(Exception): pass

def computeFormId(formName):
    '''
        >>> computeFormId('1040')
        '1040'
        >>> computeFormId(('1040','SE'))
        '1040sSE'
        '''
    try:
        form,sched=formName
        idd=form+'s'+sched
    except ValueError:
        idd=formName
    return idd

def computeTitle(prefix):
    '''
    >>> computeTitle('f1040')
    'Form 1040'
    >>> computeTitle('f1040se')
    'Form 1040 Schedule E'
    >>> computeTitle('f1040ez')
    'Form 1040EZ'
    '''
    m=re.match(r'(\w)(\d+)([^s].*)?(?:s(\w))?$',prefix)
    if m:
        typ,num,suffix,sched=m.groups()
        suffix=suffix or ''
        if typ=='f':
            doctype='Form'
        else:
            raise Exception('unknown doctype [%s]'%(typ,))
        if suffix:
            num+=suffix.upper()  # .upper for eg 1040EZ
        titleEls=[doctype,num]
        if sched:
            titleEls.extend(['Schedule',sched.upper()])
        title=' '.join(el for el in titleEls if el)
    else:
        title=prefix.capitalize()
    return title

def sortableFieldname(fieldname):
    '''
        to avoid lexicographic malordering: f1_19,f1_2,f1_20 
        >>> sortableFieldname('f1_43_L0T')
        ('f1',43,'_L',0,'T')
        '''
    def intify(s):
        try:
            return int(s)
        except:
            return s
    try:
        segs=re.findall('(\D+|\d+)',fieldname)
        segs=[intify(seg) for seg in segs]
        return segs
    except Exception as e:
        log.error('sortableFieldname: exception: fieldname= '+fieldname)
        raise

