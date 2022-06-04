# Background

This directory contains some code to pull and analyze data from [NSPIRES](https://nspires.nasaprs.com/external/)-formatted proposals submitted to NASA [ROSES](https://science.nasa.gov/researchers/roses-blogs) calls, including checks on compliance with certain NASA policies.

Code author: Megan Ansdell [@mansdell](https://github.com/mansdell)

# Setup

### Required Non-standard Packages

[PyMuPDF](https://pymupdf.readthedocs.io/en/latest/): a useful package for importing PDF text (which confusingly is imported as "import fitz")

[gender-guesser](https://pypi.org/project/gender-guesser/): only needed for one part of for check_proposals.py

# Description

### check_proposals.py

This code reads in an NSPIRES-formatted PDF submitted to a NASA ROSES call, attempts to find the "Scientific / Technical / Management" section (hereafter "the proposal"), and then grabs/checks a variety of useful things that are output into a csv file. These things are described below. Before you run the code, you'll want to change the "PDF_Path" and "Out_Path" variables to the desired directories.

* PI name and proposal number
  - These are taken from the cover page of the NSPIRES-formatted PDF
  
* Font size (useful for checking compliance)
  - The median font size used in the proposal is calculated, and a warning is given when <=11.8 pt (e.g., for checking compliance)
  - A histogram of the font sizes (based on each PDF ["span"](https://pymupdf.readthedocs.io/en/latest/faq.html#how-to-analyze-font-characteristics)) can be saved to the specified output directory (right now this isn't an active feature, which is a fancy way of saying I commented it out).
  
* Lines per inch (LPI) and counts per inch (CPI)
  - LPI is calculated per page and a warning is given for LPI > 5.5 with the page number
  - CPI is calculated per line and a warning is given for CPI > 16.0 with the line text
  - Note that PDF formats are weird, so these calculations are difficult and results should be checked.
 
* PhD Year (useful for identifying early career proposers)
  - The PhD year of the PI is extracted from the CV that is included within the PDF after the main proposal 
  - When extracted, the PhD year is correct in ~95% of cases (in some cases, no PhD year can be found, or a PhD year isn't provided in the proposal)
  - The text from which the year was guessed, and the page of the proposal from which it was extracted, are printed to the screen and useful for double checking

* Demographic information
  - Inferred gender of the PI based on the first name using [gender-guesser](https://pypi.org/project/gender-guesser/)
  - Zipcode of the PI (useful for geographic analysis)
  - Organization type (specified by the PI via NSPIRES)
  - Number of male and female Co-I's (based on inferred gender, as for the PI)

  
### check_dapr.py

This code reads in an anonymized proposal submitted to a ROSES program that follows Dual-Anonymouse Peer Reivew (DAPR). It attempts to find the different sections of the proposal (STM, DMP, Relevance, Budget) and then checks a variety of things to make sure it is DAPR compliant. The outputs are described below:

* Page ranges for propsal sections
  - These assume the following order: STM, References, DMP, Relevance, Budget
  - They're usually correct, but sometimes they're not; this only really matters for searching for the PI name but avoiding the References section
  - The value -99 is reported if the page limits could not be found
  
* Median font size
  - The median font size used in the proposal is calculated, and a warning is given when <=11.8 pt (e.g., for checking compliance)
  - This is the same as for check_proposal.py

* Reference format
  - DAPR proposals are supposed to use bracketed number references
  - Reports number of brackets found in proposal and number of "et al." usages in proposal (the former number should be high, the latter low)
  
* Forbidden DAPR words
  - DAPR proposal shouldn't include references to previous work, institutions/departments/universities/cities, PI or Co-I names, etc.
  - Reports number of times such things are found and page numbers on which they are found

### group_proposals.py

This code reads in the NSPIRES-formatted PDF, attempts to find the 15-page proposal text, performs some basic Natural Language Processing (NLP) pre-processing of the text, identifies key words, then attempts to group the proposals according to topic. The outputs are described below (TBD).


# Disclaimer

This is not an official NASA product. 
