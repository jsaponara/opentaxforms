// casperjs script to test commands built into html flle
// todo generate such files from the pdf forms.
// todo consider nesting clicks in waitForSelector-then-click-else-assertExists as resurrectio does.
// todo move preamble into separate file.  http://stackoverflow.com/questions/27341395

// invoke: casperjs --local-storage-path=. test path/to/f1040.js

casper.on("page.error", function(msg, trace) {
    this.echo("Error: " + msg, "ERROR");
});
casper.on("exit", function(code){
	phantom.exit(code); // immediately exits
});

var cwd = fs.absolute(''),
	formpath=cwd+'/forms/f1040-p1.html';
casper.echo('starting test at '+formpath);
if (!fs.exists(formpath)) {
	casper.echo('ERR formpath doesnt exist');
	casper.exit(1);
}

casper.options.viewportSize={width:1224,height:1584};
var x = require('casper').selectXPath;
function ischecked(id,casper){
	var getcheckstate=function(idd) { return document.querySelector(idd).checked; };
	return casper.evaluate(getcheckstate,id);
};
casper.test.begin('math works', 12, function suite(test) {
	casper.start("file://"+formpath);
	casper.then(function() {
		// page basics
        test.assertTitle("Form 1040 page 1", "page1 title ok");
        test.assertExists('form', "form element found");
		// initial blank state of page
		test.assert(ischecked('#c1_04',this)==false,'line6a starts unchecked');
        test.assertField({type: 'css', path: '#f1_30'}, "", 'line6d1 starts empty');
	});
	casper.then(function() {
		// click on an input checkbox
		this.click(x("//label[@for='c1_04']"));
	});
	casper.then(function() {
		// check the checkbox counter
        test.assertField({type: 'css', path: '#f1_30'}, '1', 'line6d1 auto incremented');
	});
	casper.then(function() {
		// line22=line7+...
		// ensure line7 and line22 start empty
        test.assertField({type: 'css', path: '#f1_35'}, "", 'f1_35 is empty');
        test.assertField({type: 'css', path: '#f1_76'}, '', 'f1_76 is empty');
		// fill line7 [just dollars]
        this.fillSelectors('form', {
            '#f1_35': 235
        }, false);
        test.assertField({type: 'css', path: '#f1_35'}, '235', 'f1_35 now filled');
		// check that line22 auto filled
        test.assertField({type: 'css', path: '#f1_76'}, '235', 'f1_76 auto-filled');
    });
	// go to page 2
    casper.thenClick('#nextpagelink img');
	casper.then(function() {
		// page basics
        test.assertTitle("Form 1040 page 2", "page2 title ok");
        test.assertExists('form', "form element found");
		// ensure result from page 1 is propagated here
        test.assertField({type: 'css', path: '#f2_06'}, "235", 'line37 is filled from prev page');
    });
    casper.run(function() {
        test.done();
    });
});

