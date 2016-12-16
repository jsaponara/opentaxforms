OpenTaxForms opens and automates US tax forms--it reads PDF tax forms
(currently from IRS.gov only, not state forms),
converts them to more feature-full HTML5, 
and offers a database and API for developers to create their own tax applications.
The converted forms will be available to test (and ultimately use)
at [OpenTaxForms.org](http://OpenTaxForms.org/).

  - **License**

    [GNU AGPLv3](http://choosealicense.com/licenses/agpl-3.0/)

  - **Install**

	pip install opentaxforms

  - **Github**

    - [code](https://github.com/jsaponara/opentaxforms/)
    - [issue tracker link forthcoming]
    - [milestones link forthcoming]

  - **Build status**

    [![Build Status](https://travis-ci.org/jsaponara/opentaxforms.svg?branch=0.4.9)](https://travis-ci.org/jsaponara/opentaxforms)

  - **Form status**
  	
	The script reports a status for each form.  Current status categories are:

	- layout means textboxes and checkboxes--they should not overlap.
	- refs are references to other forms--they should all be recognized (ie, in the list of all forms).
	- math is the computed fields and their dependencies--each computed field should have at least one dependency, or else what is it computed from?

	Each status error has a corresponding warning in the log file, so they're easy to find. Each bugfix will likely reduce errors across many forms.

    [form status listing forthcoming]

  - **API**

	The ReSTful API is read-only and provides a complete accounting of form fields:
	data type, size and position on page, and role in field groupings
	like dollars-and-cents fields, fields on the same line, fields in the same table,
	fields on the same page, and fields involved in the same formula.  The API will
	also provide status information and tester feedback for each form.

    [API docs forthcoming, for now see examples in test/run_apiclient.sh]

  - **How it works**

    Most of the IRS tax forms embed all the fillable field information in the
    [XML Forms Architecture](https://en.wikipedia.org/wiki/XFA) (XFA) format.
    The OpenTaxForms [python](https://www.python.org/) script extracts the XFA
    from each PDF form, and parses out:

    - relationships among fields (such as dollar and cent fields; fields on the same line; columns and rows of a table).
    - math formulas, including which fields are computed vs user-entered (such as "Subtract line 37 from line 35.  If line 37 is greaterthan line 35, enter -0-").
    - references to other forms

    All this information is stored in a database (optionally [PostgreSQL](https://www.postgresql.org/) 
	or the default (sqlite)[https://sqlite.org/]) and served according to
    a [ReSTful](https://en.wikipedia.org/wiki/Representational_state_transfer)
    API.  For each tax form page, an html form (with javascript to express the
    formulas) is generated and overlaid on an svg rendering of the original PDF.
    The javascript saves all user inputs to local/web storage in the browser
    via [basil.js](https://wisembly.github.io/basil.js/).  When the page is
    loaded, those values are retrieved.  Values are keyed by tax year, 
    form number (eg 1040), and XFA field id (and soon taxpayer name now that I do
	my kids' taxes too).  Testers will annotate the page image with boxes and comments
    via [annotorious.js](http://annotorious.github.io/).  A few of the 900+ IRS forms
    don't have embedded XFA (such as 2016 Form 1040 Schedule A).
    Eventually those forms may be updated to contain XFA, but until then, the
    best automated approach is probably
    [OCR](link:https://en.wikipedia.org/wiki/Optical_character_recognition)
    (optical character recognition).  OCR maybe a less fool-proof approach in general,
    especially for state (NJ, NY, etc) forms, which generally are not XFA-based.

  - **To do**

	- Replace ToDo with a link to github/issues.
    - Refactor toward a less script-ish architecture that will scale to more developers. [architecturePlease]
	- Switch to a pdf-to-svg converter that preserves text (rather than converting text to paths), perhaps pdfjs,
	  so that testers can easily copy and paste text from forms. [copyableText]
    - Should extractFillableFields.py be a separate project called xfadump? [xfadump]
	  This might provide a cleaner target output interface for an OCR effort.
	- Replace allpdfnames.txt with a more detailed form dictionary via a preprocess step. [formDictionary]
	- Offer entire-form html interface (currently presenting each page separately). [formAsSingleHtmlPage]
	- Incorporate instructions and publications, especially extracting the worksheets from instructions. [worksheets]
	- Add the ability to process US state forms. [stateForms]
	- Fix countless bugs, especially in forms that contain tables (see [issues])
	- Don't seek in a separate file a schedule that occurs within a form. [refsToEmbeddedSchedules]
	- Take any needed action regarding this from tox.readthedocs.io: Warning  Integrating tox with setup.py test is as of October 2016 discouraged as it breaks packaging/testing approaches as used by downstream distributions which expect setup.py test to run tests with the invocation interpreter rather than setting up many virtualenvs and installing packages. [toxSansSetup]
	- separate dirName into pdfInputDir,htmlOutputDir [splitIoDirs]

