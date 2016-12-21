from collections import namedtuple as ntuple, defaultdict as ddict, OrderedDict as odict
from decimal import Decimal as dc
from pprint import pprint as pp,pformat as pf
from sys import exit,stdout
NL='\n'
TAB='\t'

quiet=False

class Pass:
    def __getattr__(self,*args,**kw):
        print 'Pass',args,kw
        return lambda *args,**kw:None
log=Pass()

# NT eg X=ntuple('X','linenum unit name')

def localsitepkgs():
    import sys; sys.path = sys.path[1:]; import django; print(django.__path__)
#python -c "import sys; sys.path = sys.path[1:]; import django; print(django.__path__)"

def numerify(s):
    try:
        return int(''.join(d for d in s if d.isdigit()))
    except ValueError:
        return s

def pickle(data,pickleFilePrefix):
    from cPickle import dump
    picklname='%s.pickl'%(pickleFilePrefix)
    with open(picklname,'w') as pickl:
        dump(data,pickl)
def unpickle(pickleFilePrefix,default):
    from cPickle import load
    picklname='%s.pickl'%(pickleFilePrefix)
    try:
        with open(picklname) as pickl:
            data=load(pickl)
    except IOError as e:
        if e.errno==2:  # no such file
            data=default
        else:
            raise
    return data

def flattened(l):
    # only works for single level of sublists
    return [i for sublist in l for i in sublist]
def hasdups(l,key=None):
    if key is None:
        key=lambda x:x
    ll=[key(it) for it in l]
    return any(it in ll[1+i:] for i,it in enumerate(ll))
def uniqify(l):
    '''uniqify in place'''
    s=set()
    idxs=[]  # indexes of duplicate items
    for i,item in enumerate(l):
        if item in s:
            idxs.append(i)
        else:
            s.add(item)
    for i in reversed(idxs):
        l.pop(i)
    return l
def uniqify2(l):
    '''uniqify in place; probably faster for small lists'''
    for i,item in enumerate(reversed(l)):
        if item in l[:i-1]:
            l.pop(i)
    return l

import logging
defaultLoglevel='WARN'
alreadySetupLogging=False
def setupLogging(loggerId,args=None):
    global log,alreadySetupLogging
    if alreadySetupLogging:
        log.warn('ignoring extra call to setupLogging')
        return log
    if args:
        loglevel=args.loglevel.upper()
    else:
        loglevel=defaultLoglevel
    loglevel=getattr(logging,loglevel)
    if not isinstance(loglevel, int):
        allowedLogLevels='debug info warn warning error critical exception'
        raise ValueError('Invalid log level: %s, allowedLogLevels are %s'%(args.loglevel,allowedLogLevels))
    fname=loggerId+'.log'
    logging.basicConfig(filename=fname,filemode='w',level=loglevel)
    alreadySetupLogging=True
    log=logger=logging.getLogger(loggerId)
    return logger,fname

defaultOutput=stdout
def logg(msg,outputs=None):
    '''
        >>> log=setupLogging('test')
        >>> logg('just testing',[stdout,log.warn])
        '''
    if outputs==None:
        outputs=[defaultOutput]
    for o in outputs:
        m=msg
        if o==stdout:
            o=stdout.write
            m=msg+'\n'
        if quiet and o==stdout.write:
            continue
        o(m)

def jj(*args,**kw):
    '''
        jj is a more flexible join(), handy for debug output
        >>> jj(330,'info',None)
        '330 info None'
        '''
    delim=kw.get('delim',' ')
    try:
        return delim.join(str(x) for x in args)
    except Exception as e:
        return delim.join(unicode(x) for x in args)
def jdb(*args,**kw):
    logg(jj(*args,**kw),[log.debug])

def run0(cmd):
    from subprocess import Popen,PIPE
    try:
        # shell is handy for executable path, etc
        proc=Popen(cmd,shell=True,stdout=PIPE,stderr=PIPE)
        out,err=proc.communicate()
    except OSError as exc:
        err=str(exc)
        out=None
    return out,err
def run(cmd,*kw):
    logprefix='run' if 'logprefix' not in kw else kw['logprefix']
    loglevel=logging.INFO if 'loglevel' not in kw else getattr(logging,kw['loglevel'].upper(),None)
    out,err=run0(cmd)
    out,err=err.strip(),out.strip()
    msg=logprefix+': command [%s] returned error [%s] and output [%s]'%(cmd,err,out)
    if err:
        log.error(msg)
        raise Exception(msg)
    else:
        log.log(loglevel,msg)
    return out,err

def enc(s): return ''.join([chr(158-ord(c)) for c in s])

class Resource(object):
    def __init__(self,pkgname,fpath=None):
        self.pkgname=pkgname
        self.fpath=fpath
    def path(self):
        import pkg_resources
        return pkg_resources.resource_filename(self.pkgname,self.fpath)
    def content(self):
        import pkg_resources
        return pkg_resources.resource_string(self.pkgname,self.fpath)

class CharEnum:
    # unlike a real enum, no order guarantee
    # the simplest one from this url:  http://stackoverflow.com/questions/2676133/
    @classmethod
    def keys(cls):
        return [k for k in cls.__dict__.iterkeys() if not k.startswith('_')]
    @classmethod
    def vals(cls):
        return [v for k,v in cls.__dict__.iteritems() if not k.startswith('_')]
    @classmethod
    def items(cls):
        return [(k,v) for k,v in cls.__dict__.iteritems() if not k.startswith('_')]

class ChainablyUpdatableOrderedDict(odict):
    '''
        handy for ordered initialization
        >>> d=ChainablyUpdatableDict()(a=0)(b=1)(c=2)
        >>> assert d.keys()==['a','b','c']
        '''
    def __init__(self):
        super(ChainablyUpdatableOrderedDict,self).__init__()
    def __call__(self,**kw):
        self.update(kw)
        return self

class Bag(object):
    # after alexMartelli at http://stackoverflow.com/questions/2597278
    def __init__(self,*maps,**kw):
        '''
            >>> b=Bag(a=0)
            >>> b.a=1
            >>> b.b=0
            >>> c=Bag(b)
            '''
        for mapp in maps:
            getdict=None
            if type(mapp)==dict:
                getdict=lambda x:x
            elif type(mapp)==Bag:
                getdict=lambda x:x.__dict__
            elif type(mapp)==tuple:
                mapp,getdict=mapp
            if getdict is not None:
                self.__dict__.update(getdict(mapp))
            else:
                mapp,getitems=self._getGetitems(mapp)
                for k,v in getitems(mapp):
                    self.__dict__[k]=v
        self.__dict__.update(kw)
    def _getGetitems(self,mapp):
        if type(mapp)==tuple:
            mapp,getitems=mapp
        else:
            getitems=lambda m:m.items()
        return mapp,getitems
    def __getitem__(self,key):
        return self.__dict__[key]
    def __setitem__(self,key,val):
        self.__dict__[key]=val
    def __len__(self):
        return len(self.__dict__)
    def __call__(self,*keys):
        '''slicing interface
            gimmicky but useful, and doesnt pollute key namespace
            >>> b=Bag(a=1,b=2)
            >>> assert b('a','b')==(1,2)
            '''
        return tuple(self.__dict__[k] for k in keys)
    def update(self,*maps):
        '''
            >>> b=Bag(a=1,b=2)
            >>> b.update(Bag(a=1,b=1,c=0))
            >>> assert b('a','b','c')==(1,2,0)
            '''
        for mapp in maps:
            mapp,getitems=self._getGetitems(mapp)
            for k,v in getitems(mapp):
                self.__dict__[k]=v
        return self
    def __add__(self,*maps):
        self.__iadd__(*maps)
        return self
    def __iadd__(self,*maps):
        '''
            >>> b=Bag(a=1,b=2)
            >>> b+=Bag(a=1,b=1,c=0)
            >>> assert b('a','b','c')==(2,3,0)
            >>> b=Bag(a='1',b='2')
            >>> b+=Bag(a='1',b='1',c='0')
            >>> assert b('a','b','c')==('11','21','0')
            '''
        # todo error for empty maps[0]
        zero=type(maps[0].values()[0])()
        for mapp in maps:
            mapp,getitems=self._getGetitems(mapp)
            for k,v in getitems(mapp):
                self.__dict__.setdefault(k,zero)
                self.__dict__[k]+=v
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
        return self.__dict__.iteritems()
    def iteritems(self):
        return self.__dict__.iteritems()
    def get(self,key,dflt=None):
        return self.__dict__.get(key,dflt)
    def __str__(self):
        return 'Bag('+pf(self.__dict__)+')'
    def __repr__(self):
        return self.__str__()

from pint import UnitRegistry
ureg = UnitRegistry()
# interactive use: from pint import UnitRegistry as ureg; ur=ureg(); qq=ur.Quantity
qq=ureg.Quantity
def notequalpatch(self,o): return not self.__eq__(o)
setattr(qq,'__ne__',notequalpatch)
assert qq(1,'mm')==qq(1,'mm')
assert not qq(1,'mm')!=qq(1,'mm')
class Qnty(qq):
    @classmethod
    def fromstring(cls,s):
        '''
            >>> Qnty.fromstring('25.4mm')
            <Quantity(25.4, 'millimeter')>
            '''
        import re
        if ' ' in s:
            qnty,unit=s.split()
        else:
            m=re.match(r'([\d\.\-]+)(\w+)',s)
            if m:
                qnty,unit=m.groups()
            else:
                raise Exception('unsupported Qnty format [%s]'%(s))
        if '.' in qnty:
            qnty=float(qnty)
        else:
            qnty=int(qnty)
        unit={
            'pt':'printers_point',
            'in':'inch',
            }.get(unit,unit)
        return Qnty(qnty,unit)
def playQnty():
    # pagewidth=Qnty(page.cropbox[2]-page.cropbox[0],'printers_point')
    a=Qnty.fromstring('2in')
    b=Qnty.fromstring('1in')
    print Qnty(a-b,'printers_point')
    print Qnty.fromstring('72pt')
    # cumColWidths=[sum(columnWidths[0:i],Qnty(0,columnWidths[0].units)) for i in range(len(columnWidths))]
    print Qnty(0,a.units)
    # maxh=max([Qnty.fromstring(c.attrib.get('h',c.attrib.get('minH'))) for c in cells])
    print max(a,b)
    s=set()
    s.update([a,b])
    assert len(s)==1

def classifyRange(amt,classes):
    '''
        >>> classifyRange(3,[(0,4),(2,3),(4,2),(6,0)])
        2
        '''
    for limit,classs in classes:
        if amt<limit:
            return classs
    return classes[-1][1]

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
    n=str(n)
    if n[-2:] in ('11','12','13'):
        return n+'th'
    return n+dict([(nth[0],nth[1:3]) for nth in '1st 2nd 3rd'.split()]).get(n[-1],'th')

# todo school stuff doesnt belong here--abstract this
def worddiffs(a,b):
    # todo add doctest to demo that order matters, ie 'east amwell' != 'amwell east'
    '''
        >>> sorted(worddiffs('east amwell township e.s.','east amwell twp'))
        ['E.S.', 'TOWNSHIP', 'TWP']
        '''
    from re import split as sp
    az =sp(r'[ -]',a.upper())
    bz=sp(r'[ -]',b.upper())
    #from difflib import context_diff as cdf; cdf(az,bz)
    from difflib import ndiff
    diffs=[dif[2:] for dif in ndiff(az,bz) if dif[0]!=' ']
    return diffs

def htmlTableFromDict(rows,cols):
    if type(cols)==str:
        cols=cols.split()
    table=[
        '<table>',
        '<tr>'+'\n'.join('<th>%s</th>'%(col,) for col in cols)+'</tr>',
        '\n'.join([
            '<tr>'+
            '\n\t'.join(
                '<td>%s</td>'%(row[col],)
                for col in cols)
            +'</tr>' for row in rows]),
        '</table>'
        ]
    return '\n'.join(table)

def skip(s,substr):
    '''
        >>> skip('0123456789','45')
        '6789'
        '''
    idx=s.index(substr)
    return s[idx+len(substr):]
def until(s,substr):
    '''
        >>> until('0123456789','45')
        '0123'
        '''
    try:
        idx=s.index(substr)
        return s[:idx]
    except ValueError:
        return s

def exists(fname):
    '''
        >>> exists('/usr')
        True
        >>> exists('/ldsj')
        False
    '''
    from os import access,F_OK
    return access(fname,F_OK)

def now(**kw):
    from datetime import datetime
    if 'format' in kw:
        return datetime.now().strftime(kw['format'])
    else:
        return datetime.now().isoformat()

def ipysession():
    return '\\n'.join('>>> '+str(In[i])+'\\n'+str(Out.get(i)) for i in range(max(len(In),max(Out.keys()))))

# simple server that allows injection of http response headers
#from http.server import SimpleHTTPRequestHandler  #py3?
import BaseHTTPServer  #py2
HOST_NAME='localhost'
PORT_NUMBER=8000
class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(s):
        content=open('f1040ez-fmt-1.xml').read()
        s.send_response(200)
        s.send_header("Content-type", "text/xml")
        s.end_headers()
        s.wfile.write(content)
def serve():
    Svr=BaseHTTPServer.HTTPServer
    svr=Svr((HOST_NAME,PORT_NUMBER),MyHandler)
    try:
        svr.serve_forever()
    except KeyboardInterrupt:
        pass
    svr.server_close()
    return 0

def nestedFunctionTest():
    '''
        just to see if doctest still doesnt run nested functions (as in py27,py34)
          cuz theyre not created until the outer function is run
          https://bugs.python.org/issue1650090
        >>> 'a'
        'a'
    '''
    def theNestedFunction():
        '''
            >>> 'a'
            'b'
        '''
        pass
    pass
'''

def parse_cli():
    from argparse import ArgumentParser   # https://docs.python.org/2/library/argparse.html
    parser = ArgumentParser(description='compute form connection graph')
    # required arg:
    parser.add_argument('directory', help='directory of "*-refs.txt" files to parse')
    # optional arg:
    parser.add_argument('-f', '--form', metavar='formName', nargs='?', help='form file name, eg f1040')
    return parser.parse_args()
if __name__=='__main__':
    # this code is not used here in ut.py cuz ut.py must stand alone.
    # for all modules:
    from config import setup
    cfg,log=setup()
    if cfg.doctests:
        import doctest; doctest.testmod(verbose=cfg.verbose)
    # for main module, add:
    else:
        sys.exit(main())
'''
if __name__=="__main__":
    import sys
    args=sys.argv[1:]
    if any('T' in arg for arg in args):
        verbose=any('v' in arg for arg in args)
        import doctest; doctest.testmod(verbose=verbose)

