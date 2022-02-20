
var displayStorage = function(selector) {
	// todo consider emitting code that would read the data into local storage
	//   code = `var db=new window.Basil({namespace:'${namespace}',storage:'local'});` +
	//          `db.set(form,{` ;
	//   for(...)
	//       code += `  ${key}:${vals[key]},`
	//   code += `});`
	//   tho js string interpolation via template literal: caniuse/06apr2018 says 92% tho not msie=2.5% [es6 shim for msie?  yes but this feature too syntax-y?]
	var content = '',
    code = '',
		thisYear = new Date().getFullYear();
	for (year=thisYear-10; year<thisYear; year++) {
		var namespace='opentaxforms_'+year,
			db=new window.Basil({namespace:namespace,storage:'local'}),
			forms=db.keys();
		if (forms.length) {
			content+='namespace '+namespace+'\n';
      code += `var db=new window.Basil({namespace:'${namespace}',storage:'local'});\n`;
		}
		for (var i=0; i<forms.length; i++) {
			formname=forms[i];
			content+='  form '+formname+'\n';
      var code_form = '',
        quote = '';
			vals=db.get(formname)||{};
			for (var key in vals) {
				if (vals[key]) {
					content+='    '+key+' '+vals[key]+'\n';
          quote = (typeof(vals[key]) === 'string' ? '"' : '')
          code_form += `  ${key}: ${quote}${vals[key]}${quote},\n`;
				}
			}
      if (code_form) {
        code += `db.set("${formname}", {\n${code_form}});\n`;
      }
		}
		document.querySelector(selector).value = code;
	}
}
