
// caution: this code overwrites year N+1, so run it upon completing year N.
// NOTE: year0 is hardcoded.
// to run this, paste it into the devtools console after loading opentaxforms/static/html/displayStorage.html
// todo?  field id's seem more likely to change across years than line numbers, so line numbers would be better keys to use.

var year0 = 2021,
    year1 = year0 + 1,
    db=new window.Basil({namespace:'opentaxforms_' + year0, storage:'local'}),
    db_next_year = new window.Basil({namespace:'opentaxforms_' + year1, storage:'local'});
for (i in db.keys()) {
  var filer_form=db.keys()[i];
  //console.log('--', filer_form);
  var map = db.get(filer_form),
      map_keep = {};
  for (key in map) {
    //console.log('----', key, map[key]);
    var val = map[key];
    if (key && (typeof val === 'boolean' || isNaN(val))) {
      map_keep[key] = val;
    }
    db_next_year.set(filer_form, map_keep);
  }
}

