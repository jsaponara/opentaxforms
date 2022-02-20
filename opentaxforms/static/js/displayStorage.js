
var displayStorage = function(selector) {
  var 
    //content = '',  // pretty outline, but useless.
    code = '',       // executable format.
    params = (new URL(window.location.href)).searchParams,
    this_year = new Date().getFullYear(),
    target_year = params.get("year"),
    filer = params.get('filer'),
    start_year = this_year - 10,
    final_year = this_year ;
  if (target_year) {
    start_year = target_year;
    final_year = target_year;
  }
  for (year=start_year; year<=final_year; year++) {
    var namespace='opentaxforms_'+year,
      db=new window.Basil({namespace:namespace,storage:'local'}),
      forms=db.keys().sort();
    if (forms.length) {
      //content+='namespace '+namespace+'\n';
    }
    var form_codes = [];
    for (var i=0; i<forms.length; i++) {
      formname=forms[i];
      if (filer && !formname.startsWith(filer)) continue;
      //content+='  form '+formname+'\n';
      var code_form = '',
        quote = '';
      vals=db.get(formname)||{};
      for (var key in vals) {
        if (vals[key]) {
          //content+='    '+key+' '+vals[key]+'\n';
          quote = (typeof(vals[key]) === 'string' && isNaN(Number(vals[key])) ? '"' : '')
          code_form += `  ${key}: ${quote}${vals[key]}${quote},\n`;
        }
      }
      if (code_form) {
        form_codes.push(`db.set("${formname}", {\n${code_form}});\n`);
      }
    }
    if (form_codes.length) {
      form_codes.unshift(`var db=new window.Basil({namespace:'${namespace}',storage:'local'});`);
      code += form_codes.join('\n') + '\n';
    }
  }
  document.querySelector(selector).value = code;
}
