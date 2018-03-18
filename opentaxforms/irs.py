# domain-specific code

import re
import sys

# ignore employer forms: 1099's, 1098's, w2, w4, etc
excludedformsPttn = re.compile(r'109\d.*|w.*', re.I)

# commands that are common in tax instructions
verbs = [
    v.replace('_', ' ') for v in
    'add amount combine total howmany subtract multiply divide enter include check'.
    lower().split()]
verbPtn = '|'.join(verbs)
commandPtn = re.compile('.*?(' + verbPtn + r') (.+)', re.I)
fromLinePttn = re.compile(r'amounts? (?:on|from) lines? ', re.I)

possibleColTypes = 'proceeds cost adjustment gain loss'.lower().split()

# irs Prior Year Products
# https://apps.irs.gov/app/picklist/list/priorFormPublication.html     # 2014 tax year
# prevurltmpl='http://www.irs.gov/pub/irs-pdf/%s'%(fname,)
# currurltmpl='http://www.irs.gov/file_source/pub/irs-pdf/%s'%(fname,) # 2015 tax year
# prevurltmpl eg http://www.irs.gov/pub/irs-prior/f1040--2015.pdf
# currurltmpl eg http://www.irs.gov/pub/irs-pdf/f1040.pdf
#prevurltmpl = 'http://www.irs.gov/pub/irs-prior/%s'                   # 2016 tax year
#currurltmpl = 'http://www.irs.gov/pub/irs-pdf/%s'                     # 2016
prevurltmpl = 'https://www.irs.gov/pub/irs-prior/%s'                   # 2017 tax year
currurltmpl = 'https://www.irs.gov/pub/irs-pdf/%s'                     # 2017


# xml that we cannot currently parse, eg 1040 older than 2012
class CrypticXml(Exception):
    pass


def computeFormId(formName):
    '''
        >>> computeFormId('1040')
        '1040'
        >>> computeFormId(('1040','SE'))
        '1040sSE'
        '''
    try:
        form, sched = formName
        if sched is None:
            idd = form
        else:
            idd = form + 's' + sched
    except ValueError:
        idd = formName
    return idd


def computeTitle(prefix, form = None):
    '''
    >>> computeTitle('f1040')
    'Form 1040'
    >>> computeTitle('f1040se')
    'Form 1040 Schedule E'
    >>> computeTitle('f1040ez')
    'Form 1040EZ'
    '''
    m = re.match(r'(\w)(\d+)([^s].*)?(?:s(\w))?$', prefix)
    if m:
        typ, num, suffix, sched = m.groups()
        suffix = suffix or ''
        if typ == 'f':
            doctype = 'Form'
        else:
            # todo temporary fallback for CRA forms
            #raise Exception('unknown doctype [%s]' % (typ, ))
            return form.docinfo['titl']
        if suffix:
            num += suffix.upper()  # .upper for eg 1040EZ
        titleEls = [doctype, num]
        if sched:
            titleEls.extend(['Schedule', sched.upper()])
        title = ' '.join(el for el in titleEls if el)
    else:
        title = prefix.capitalize()
    return title


def sortableFieldname(fieldname):
    '''
        to avoid lexicographic malordering: f1_19,f1_2,f1_20
        >>> sortableFieldname('f1_43_L0T')
        ['f', 1, '_', 43, '_L', 0, 'T']
        '''

    def intify(s):
        try:
            return int(s)
        except ValueError:
            return s
    try:
        segs = re.findall('(\D+|\d+)', fieldname)
        segs = [intify(seg) for seg in segs]
        return segs
    except Exception:
        excclass, exc, tb = sys.exc_info()
        new_exc = Exception(
            'sortableFieldname: new exception: fieldname= ' + fieldname)
        raise new_exc.__class__(new_exc).with_traceback(tb)

# todo eliminate guesswork in setup()/allpdfnames and possibleFilePrefixes by
# reading document metadata as in pdfInfo() and mapping formName<->filename.


def possibleFilePrefixes(formName):
    '''
        the filename for form 1040 sched 8812 is f1040s8.pdf,
          whereas the typical pattern is f1040s8812.pdf.
        todo eliminate this guesswork by reading document metadata
             in the setup()/allpdfnames step as done in pdfInfo()
        >>> possibleFilePrefixes(('1040','8812'))
        ['f1040s8812', 'f1040s881', 'f1040s88', 'f1040s8']
        '''
    prefixes = []
    try:
        fform, fsched = formName
        if fsched is None:
            formName = fform
        ntrim = len(fsched)
        tmpl = {
            ('990', 'b'): '%sez%s',  # a glaring inconsistency--in 2015 only??
            ('1120', 'utp'): '%s%s',  # no delimiter at all--other forms too?
            }.get((fform, fsched), '%ss%s')  # the typical pattern
        formName = (tmpl % formName).lower()
        # formName may be eg ('f1040','A')
    except:
        def trailingLetters(s):
            i = -1
            if not s or not s[i].isalpha():
                return ''
            while len(s) >= abs(i) and s[i].isalpha():
                i -= 1
            return s[i + 1:]
        # cuz 1120reit->f1120rei
        ntrim = max(0, len(trailingLetters(formName)) - 1)
    # remove '-' but protect '--'
    formName = (
        'f' +
        formName.lower()
        .replace('--', '<>')
        .replace('-', '')
        .replace('<>', '--'))
    prefixes.append(formName)
    if any(formName.endswith(suffix) for suffix in ('ez', 'eic')):
        prefixes.append(formName[:-1])  # remove last char
    else:
        for i in range(1, ntrim):
            prefixes.append(formName[:-i])  # remove last chars
    return prefixes
