
var opentaxforms=(function() {
	var me={};
	me.zz=function(g){
		// display zero or less as empty string
		return function(){if(g()=='-0-')return '0';return g()>0?g():g()<0?'('+-g()+')':'';;} };
	me.koo=ko.observable;
	me.koc=ko.computed;
	//me.pad=function(cents){var x=cents+''; return x.length==2?x:'0'+x;},
	me.dd=function(totaler){
		// extract dollars eg 23454->'234'
		return function() {
			var total=''+totaler();
			if (total=='?') {
				return total;
			}
			if (total=='-0-')
				return total;
			return total.slice(0,-2);
		}
	};
	me.cc=function(totaler) {
		// extract cents eg 23454->'54'
		return function() {
			var total=''+totaler();
			if (total=='?') {
				return total;
			}
			if (total.length<2)
				total='00'.slice(total.length-2)+total
			return total.slice(-2); 
		}
	};
	me.nn=function(n) {
		return function() { return +n(); }
	}
	me.ll=function(dollar,cent,msg){return function(){
		var dd=dollar(),cc=(cent?cent():''),ddstart=0,ddend=dd.length,ccstart=0,ccend=cc.length,factor=100;
		if(dd.charAt(0)=='('){
			ddstart=1;
			if(dd.slice(-1)==')')ddend=-1;
			dd=dd.slice(ddstart,ddend);
			if(cc.slice(-1)==')')ccend=-1;
			factor*=-1;
		}
		if(cc)return factor*(dd.slice(ddstart,ddend)+(+cc.slice(ccstart,ccend))); else return factor*dd;
	}}
	me.pp=function(op,xs,signs,ys,zcond){
		// xs are dollars or dimless, ys are cents; '(x)' -> -x else x
		var doop=function(op,xs,start) {  // as in do-op-on-array-of-xs-accum-from-start
			var nz=false,n,result=0;
			if (op=='*') { result=1; }
			for (var i=0,l=xs.length;i<l;i++) {
				var x=xs[i]()
				arg=''+x;
				if (arg=='?') { return '?'; }
				if (arg.length) {nz=true;}
				if (arg.charAt(0)=='(' && arg.slice(-1)==')') {
					n=-arg.slice(1,-1);
				} else {
					n=+x;
				}
				if (signs && signs.charAt(i)=='-') {
					n=-n;
				}
				if (op=='+' || (op=='-' && i!=1)) { result+=n; }
					else if (op=='-') {result-=n;}
					else if (op=='*') {result*=n;}
					else if (op=='?') {result='?';}
					else alert('unknown operator ['+op+']');
			}
			result+=start
			return {'result':result,'nz':nz};
		}
		return function() {
			var start=0,nz=false,n,result;
			//if (op=='*') { start=1; }
			if (zcond && zcond()) return 0;
			o=doop(op,xs,start);
			result=o.result;
			nz=o.nz;
			if (result=='?') { return result; }
			if (ys && ys.length) {
				o=doop(op,ys,100*result);
				result=o.result;
				nz=nz&&o.nz;
			}
			if (op=='?') {
				if (nz) { return '?'; }
				else { return ''; }
			}
			else if (result==0 && !nz) {result='';}
			else if (result<0) { result='('+-result+')'; }
			return result;
		}
	}
	me.ld=function(x,func,defaultval){if (x) return func(x); else return func(defaultval); } 
	me.setval=function(val,id) {
		var el=document.getElementById(id);
		if (el) {
			if (id.charAt(0)=='c') {
				el.checked=val;
			} else {
				el.value=(val?val:'');
			}
		}
	}
	me.getval=function(id) {
		var val=document.getElementById(id);
		if (!val) {
		} else if (id.charAt(0)=='c') {
			val=val.checked;
		} else {
			val=val.value;
		}
		return val;
	}
	return me;
}());
