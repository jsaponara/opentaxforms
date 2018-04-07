from __future__ import print_function
import logging
import os
import pkg_resources
import re
import six
import sys
from collections import (
    namedtuple as ntuple,
    defaultdict as ddict,
    OrderedDict as odict)
from datetime import datetime
from os.path import join as pathjoin, exists
from pint import UnitRegistry
from pprint import pprint as pp, pformat as pf
from subprocess import Popen, PIPE
from sys import stdout, exc_info
try:
    from cPickle import dump, load
except ImportError:
    from pickle import dump, load

NL = '\n'
TAB = '\t'

quiet = False


Bbox = ntuple('Bbox', 'x0 y0 x1 y1')


def merge(bb1, bb2):
    return Bbox(
        min(bb1.x0, bb2.x0),
        min(bb1.y0, bb2.y0),
        max(bb1.x1, bb2.x1),
        max(bb1.y1, bb2.y1))


def numerify(s):
    try:
        return int(''.join(d for d in s if d.isdigit()))
    except ValueError:
        return s


def compactify(multilineRegex):
    # to avoid having to replace spaces in multilineRegex's with less readable
    # '\s' etc no re.VERBOSE flag needed
    r"""
    line too long (folded):
        titlePttn1=re.compile(r'(?:(\d\d\d\d) )?Form ([\w-]+(?: \w\w?)?)
            (?: or ([\w-]+))?(?:  ?\(?(?:Schedule ([\w-]+))\)?)?
            (?:  ?\((?:Rev|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)
            .+?\))?\s*$')
    re.VERBOSE with spaces removed (else theyll be ignored in VERBOSE mode):
        pttn=re.compile(
            r'''(?:(\d\d\d\d)\s)?       # 2016
                Form\s([\w-]+           # Form 1040
                (?:\s\w\w?)?)           # AS
                (?:\sor\s([\w-]+))?     # or 1040A
                (?:\s\s?\(?(?:Schedule\s([\w-]+))\)?)?  # (Schedule B)
                (?:\s\s?\((?:Rev|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec).+?\))?\s*$''',re.VERBOSE)
    using compactify:
        >>> anyMonth = 'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec'
        >>> compactify(
        ... '''(?:(\d\d\d\d) )?       # 2016
        ...     Form ([\w-]+           # Form 1040
        ...     (?: \w\w?)?)           # AS
        ...     (?: or ([\w-]+))?      # or 1040A
        ...     (?:  ?\(?(?:Schedule ([\w-]+))\)?)?  # (Schedule B)
        ...     (?:  ?\((?:Rev|'''+anyMonth+''').+?\))?\s*$''')
        '(?:(\\d\\d\\d\\d) )?Form ([\\w-]+(?: \\w\\w?)?)(?: or ([\\w-]+))?'
          '(?:  ?\\(?(?:Schedule ([\\w-]+))\\)?)?'
          '(?:  ?\\('
          '(?:Rev|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec).+?\\))?'
          '\\s*$'

        # todo what should compactify return for these?
        #      [but note this entire docstring is raw]
        #>>> compactify(r'\   # comment')
        #>>> compactify(r'\\  # comment')
        #>>> compactify( '\   # comment')
        #>>> compactify( '\\  # comment')
        #print len(multilineRegex),
            '[%s%s]'%(multilineRegex[0],multilineRegex[1])
    """

    def crunch(seg):
        return re.sub(' *#.*$', '', seg.lstrip())
    segs = multilineRegex.split(NL)
    return ''.join(crunch(seg) for seg in segs)


class NoSuchPickle(Exception):
    pass


class PickleException(Exception):
    pass


def pickle(data, pickleFilePrefix):
    picklname = '%s.pickl' % (pickleFilePrefix)
    with open(picklname, 'wb') as pickl:
        dump(data, pickl)


def unpickle(pickleFilePrefix, default=None):
    picklname = '%s.pickl' % (pickleFilePrefix)
    try:
        with open(picklname, 'rb') as pickl:
            data = load(pickl)
    except IOError as e:
        clas, exc, tb = exc_info()
        if e.errno == 2:  # no such file
            if default == 'raise':
                raise NoSuchPickle(NoSuchPickle(exc.args)).with_traceback(tb)
            else:
                data = default
        else:
            raise PickleException(PickleException(exc.args)).with_traceback(tb)
    return data


def flattened(l):
    # only works for single level of sublists
    return [i for sublist in l for i in sublist]


def hasdups(l, key=None):
    if key is None:
        ll = l
    else:
        ll = [key(it) for it in l]
    return any(it in ll[1 + i:] for i, it in enumerate(ll))


def uniqify(l):
    '''uniqify in place'''
    s = set()
    idxs = []  # indexes of duplicate items
    for i, item in enumerate(l):
        if item in s:
            idxs.append(i)
        else:
            s.add(item)
    for i in reversed(idxs):
        l.pop(i)
    return l


def uniqify2(l):
    '''uniqify in place; probably faster for small lists'''
    for i, item in enumerate(reversed(l)):
        if item in l[:i - 1]:
            l.pop(i)
    return l


log = logging.getLogger()
defaultLoglevel = 'WARN'
alreadySetupLogging = False


def setupLogging(loggerId, args=None):
    global alreadySetupLogging
    if alreadySetupLogging:
        log.warn('ignoring extra call to setupLogging')
        fname = log.name
    else:
        if args:
            loglevel = args.loglevel.upper()
        else:
            loglevel = defaultLoglevel
        loglevel = getattr(logging, loglevel)
        if not isinstance(loglevel, int):
            allowedLogLevels = 'debug info warn warning error critical exception'
            raise ValueError('Invalid log level: %s, allowedLogLevels are %s' % (
                args.loglevel, allowedLogLevels))
        fname = loggerId + '.log'
        filehandler=logging.FileHandler(fname, mode='w', encoding='utf-8')
        filehandler.setLevel(loglevel)
        log.setLevel(loglevel)
        log.addHandler(filehandler)
        alreadySetupLogging = True
    return fname


def unsetupLogging():
    global alreadySetupLogging
    alreadySetupLogging=False
    log.handlers = []


defaultOutput = stdout


def logg(msg, outputs=None):
    '''
        log=setupLogging('test')
        logg('just testing',[stdout,log.warn])
        '''
    if outputs is None:
        outputs = [defaultOutput]
    for o in outputs:
        m = msg
        if o == stdout:
            o = stdout.write
            m = msg + '\n'
        if quiet and o == stdout.write:
            continue
        o(m)


def jj(*args, **kw):
    '''
        jj is a more flexible join(), handy for debug output
        >>> jj(330,'info',None)
        '330 info None'
        '''
    delim = kw.get('delim', ' ')
    try:
        return delim.join(str(x) for x in args)
    except Exception:
        return delim.join(six.text_type(x) for x in args)


def jdb(*args, **kw):
    logg(jj(*args, **kw), [log.debug])


def run0(cmd):
    try:
        # shell is handy for executable path, etc
        proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        out, err = proc.communicate()
    except OSError as exc:
        err = str(exc)
        out = None
    return out, err


def run(cmd, logprefix='run', loglevel='INFO'):
    loglevel = getattr(logging, loglevel.upper(), None)
    out, err = run0(cmd)
    out, err = out.strip(), err.strip()
    msg = '%s: command [%s] returned error [%s] and output [%s]' % (
        logprefix, cmd, err, out)
    if err:
        log.error(msg)
        raise Exception(msg)
    else:
        log.log(loglevel, msg)
    return out, err


class Resource(object):
    def __init__(self, pkgname, fpath=None):
        self.pkgname = pkgname
        self.fpath = fpath

    def path(self):
        return pkg_resources.resource_filename(self.pkgname, self.fpath)

    def content(self):
        return pkg_resources.resource_string(self.pkgname, self.fpath)


class CharEnum(object):

    # unlike a real enum, no order guarantee the simplest one from this url:
    # http://stackoverflow.com/questions/2676133/
    @classmethod
    def keys(cls):
        return [k for k in cls.__dict__ if not k.startswith('_')]

    @classmethod
    def vals(cls):
        return [cls.__dict__[k] for k in cls.keys()]

    @classmethod
    def items(cls):
        return zip(cls.keys(), cls.vals())


class ChainablyUpdatableOrderedDict(odict):
    '''
        handy for ordered initialization
        >>> d=ChainablyUpdatableOrderedDict()(a=0)(b=1)(c=2)
        >>> assert d.keys()==['a','b','c']
        '''

    def __init__(self):
        super(ChainablyUpdatableOrderedDict, self).__init__()

    def __call__(self, **kw):
        self.update(kw)
        return self


class Bag(object):

    # after alexMartelli at http://stackoverflow.com/questions/2597278
    def __init__(self, *maps, **kw):
        '''
            >>> b=Bag(a=0)
            >>> b.a=1
            >>> b.b=0
            >>> c=Bag(b)
            '''
        for mapp in maps:
            getdict = None
            if type(mapp) == dict:
                getdict = lambda x: x
                # def getdict(x): return x
            elif type(mapp) == Bag:
                getdict = lambda x: x.__dict__
                # def getdict(x): return x.__dict__
            elif type(mapp) == tuple:
                mapp, getdict = mapp
            if getdict is not None:
                self.__dict__.update(getdict(mapp))
            else:
                mapp, getitems = self._getGetitems(mapp)
                for k, v in getitems(mapp):
                    self.__dict__[k] = v
        self.__dict__.update(kw)

    def _getGetitems(self, mapp):
        if type(mapp) == tuple:
            mapp, getitems = mapp
        else:
            getitems = lambda m: m.items()
            # def getitems(m): return m.items()
        return mapp, getitems

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, val):
        self.__dict__[key] = val

    def __len__(self):
        return len(self.__dict__)

    def __call__(self, *keys):
        '''slicing interface
            gimmicky but useful, and doesnt pollute key namespace
            >>> b=Bag(a=1,b=2)
            >>> assert b('a','b')==(1,2)
            '''
        return tuple(self.__dict__[k] for k in keys)

    def clear(self):
        self.__dict__={}

    def update(self, *maps):
        '''
            >>> b=Bag(a=1,b=2)
            >>> b.update(Bag(a=1,b=1,c=0))
            Bag({'a': 1, 'b': 1, 'c': 0})
            '''
        for mapp in maps:
            mapp, getitems = self._getGetitems(mapp)
            for k, v in getitems(mapp):
                self.__dict__[k] = v
        return self

    def __add__(self, *maps):
        self.__iadd__(*maps)
        return self

    def __iadd__(self, *maps):
        '''
            >>> b=Bag(a=1,b=2)
            >>> b+=Bag(a=1,b=1,c=0)
            >>> assert b('a','b','c')==(2,3,0)
            >>> b=Bag(a='1',b='2')
            >>> b+=Bag(a='1',b='1',c='0')
            >>> assert b('a','b','c')==('11','21','0')
            '''
        # todo error for empty maps[0]
        zero = type(list(maps[0].values())[0])()
        for mapp in maps:
            mapp, getitems = self._getGetitems(mapp)
            for k, v in getitems(mapp):
                self.__dict__.setdefault(k, zero)
                self.__dict__[k] += v
        return self

    def __iter__(self):
        return self.iterkeys()

    def iterkeys(self):
        return iter(self.__dict__.keys())

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def iteritems(self):
        return self.__dict__.iteritems()

    def get(self, key, dflt=None):
        return self.__dict__.get(key, dflt)

    def __str__(self):
        return 'Bag(' + pf(self.__dict__) + ')'

    def __repr__(self):
        return self.__str__()


ureg = UnitRegistry()
# interactive use: from pint import UnitRegistry as ureg; ur=ureg();
# qq=ur.Quantity
qq = ureg.Quantity


def notequalpatch(self, o):
    return not self.__eq__(o)


setattr(qq, '__ne__', notequalpatch)
assert qq(1, 'mm') == qq(1, 'mm')
assert not qq(1, 'mm') != qq(1, 'mm')


class Qnty(qq):
    @classmethod
    def fromstring(cls, s):
        '''
            >>> Qnty.fromstring('25.4mm')
            <Quantity(25.4, 'millimeter')>
            '''
        if ' ' in s:
            qnty, unit = s.split()
        else:
            m = re.match(r'([\d\.\-]+)(\w+)', s)
            if m:
                qnty, unit = m.groups()
            else:
                raise Exception('unsupported Qnty format [%s]' % (s))
        if '.' in qnty:
            qnty = float(qnty)
        else:
            qnty = int(qnty)
        unit = {
            'pt': 'printers_point',
            'in': 'inch',
            }.get(unit, unit)
        return Qnty(qnty, unit)

    def __hash__(self):
        return hash(repr(self))


def playQnty():
    # pagewidth=Qnty(page.cropbox[2]-page.cropbox[0],'printers_point')
    a = Qnty.fromstring('2in')
    b = Qnty.fromstring('1in')
    print(Qnty(a - b, 'printers_point'))
    print(Qnty.fromstring('72pt'))
    # cumColWidths=[sum(columnWidths[0:i],Qnty(0,columnWidths[0].units)) for i
    # in range(len(columnWidths))]
    print(Qnty(0, a.units))
    # maxh=max([Qnty.fromstring(c.attrib.get('h',c.attrib.get('minH'))) for c
    # in cells])
    print(max(a, b))
    s = set()
    s.update([a, b])
    assert len(s) == 1


def nth(n):
    '''
        >>> nth(2)
        '2nd'
        >>> nth(21)
        '21st'
        >>> nth('22')
        '22nd'
        >>> nth(23)
        '23rd'
        >>> nth(24)
        '24th'
        >>> nth(12)
        '12th'
        '''
    n = str(n)
    suffix = 'th'
    if n[-1] == '1' and n[-2:] != '11':
        suffix = 'st'
    elif n[-1] == '2' and n[-2:] != '12':
        suffix = 'nd'
    elif n[-1] == '3' and n[-2:] != '13':
        suffix = 'rd'
    return n + suffix


def skip(s, substr):
    '''
        >>> skip('0123456789','45')
        '6789'
        '''
    idx = s.index(substr)
    return s[idx + len(substr):]


def until(s, substr):
    '''
        >>> until('0123456789','45')
        '0123'
        '''
    try:
        idx = s.index(substr)
        return s[:idx]
    except ValueError:
        return s


def ensure_dir(folder):
    '''ensure that directory exists'''
    if not exists(folder):
        os.makedirs(folder)


def now(format=None):
    dt = datetime.now()
    if format is None:
        return dt.isoformat()
    return dt.strftime(format)


def readImgSize(fname, dirName):
    from PIL import Image
    with open(pathjoin(dirName,fname), 'rb') as fh:
        img = Image.open(fh)
        imgw, imgh = img.size
    return imgw, imgh


def asciiOnly(s):
    if s:
        s=''.join(c for c in s if ord(c)<127)
    return s


if __name__ == "__main__":
    args = sys.argv[1:]
    if any('T' in arg for arg in args):
        verbose = any('v' in arg for arg in args)
        import doctest
        doctest.testmod(verbose=verbose)
