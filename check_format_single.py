# ============== Import Packages ================

import sys, os, glob, pdb
import numpy as np
import pandas as pd
import argparse

import fitz 
fitz.TOOLS.mupdf_display_errors(False)
from collections import Counter
import datetime
import unicodedata
import textwrap

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# ============== Define Functions ===============

def get_text(d, pn):
             
    """
    PURPOSE:    get the text from a given page of the proposal
    INPUTS:     d = fitz Document object
                pn = page number of text to grab
    OUTPUTS:    t = page text
    """

    ### LOAD PAGE
    p = d.load_page(int(pn))

    ### GET RAW TEXT
    t = p.get_text("text")

    ### FIX ENCODING
    t = t.encode('utf-8', 'replace').decode()
    
    return t


def get_pages(d, flg, pl=15):

    """
    PURPOSE:   find start and end pages of proposal within NSPIRES-formatted PDF
               [assumes proposal starts after budget, and references at end of proposal]
    INPUTS:    d  = fitz Document object
               pl = page limit of proposal (int; default = 15)
    OUTPUTS:   pn = number of pages of proposal (int)
               ps = start page number (int)
               pe = end page number (int)

    """

    ### GET TOTAL NUMBER OF PAGES IN PDF
    pn = d.page_count

    ### WORDS THAT INDICATE EXTRA STUFF BEFORE PROPOSAL STARTS
    check_words = ["contents", "c o n t e n t s", "budget", "cost", "costs",
                   "submitted to", "purposely left blank", "restrictive notice"]

    ### IF NO NSPIRES FRONT MATTER, SET START/END PAGES
    ps = 0
    if flg == 'Yes':
        pe  = ps + (pl - 1) 
    
    else:

        ### LOOP THROUGH PDF PAGES TO FIND START/END PAGES
        for i, val in enumerate(np.arange(pn)):
                
            ### READ IN TEXT FROM THIS PAGE AND NEXT PAGE
            t1 = get_text(d, val)
            t2 = get_text(d, val + 1)

            ### FIND PROPOSAL START USING END OF SECTION X IN NSPIRES
            if ('SECTION X - Budget' in t1) & ('SECTION X - Budget' not in t2):

                ### SET START PAGE
                ps = val + 1

                ### ATTEMPT TO CORRECT FOR (ASSUMED-TO-BE SHORT) COVER PAGES
                if len(t2) < 500:
                    ps += 1
                    t2 = get_text(d, val + 2)

                ### ATTEMP TO ACCOUNT FOR TOC OR EXTRA SUMMARIES
                if any([x in t2.lower() for x in check_words]):
                    ps += 1

                ### SET END PAGE ASSUMING AUTHORS USED FULL PAGE LIMIT
                pe  = ps + (pl - 1) 
                            
            ### EXIT LOOP IF START PAGE FOUND
            if ps != 0:
                break 

    ### ATTEMPT TO CORRECT FOR TOC > 1 PAGE OR SUMMARIES THAT WEREN'T CAUGHT ABOVE
    if any([x in get_text(d, ps).lower() for x in check_words]):
        ps += 1
        pe += 1

    ### CHECK THAT PAGE AFTER END PAGE IS REFERENCES
    Ref_Words = ['references', 'bibliography', "r e f e r e n c e s", "b i b l i o g r a p h y"]
    if not any([x in get_text(d, pe + 1).lower() for x in Ref_Words]):

        ### IF NOT, TRY NEXT PAGE (OR TWO) AND UPDATED LAST PAGE NUMBER
        if any([x in get_text(d, pe + 2).lower() for x in Ref_Words]):
            pe += 1
        elif any([x in get_text(d, pe + 3).lower() for x in Ref_Words]):
            pe += 2

        ### CHECK THEY DIDN'T GO UNDER THE PAGE LIMIT
        if any([x in get_text(d, pe).lower() for x in Ref_Words]):
            pe -= 1
        elif any([x in get_text(d, pe - 1).lower() for x in Ref_Words]):
            pe -= 2
        elif any([x in get_text(d, pe - 2).lower() for x in Ref_Words]):
            pe -= 3
        elif any([x in get_text(d, pe - 3).lower() for x in Ref_Words]):
            pe -= 4

    ### PRINT TO SCREEN (ACCOUNTING FOR ZERO-INDEXING)
    print("\n\tTotal pages = {},  Start page = {},   End page = {}".format(pn, ps + 1, pe + 1))

    return pn, ps, pe


def get_fonts(doc, pn):

    """
    PURPOSE:   get font sizes used in the proposal
    INPUTS:    doc = fitz Document object
               pn  = page number to grab fonts (int)
    OUTPUTS:   df  = dictionary with font sizes, types, colors, and associated text

    """

    ### LOAD PAGE
    page = doc.load_page(int(pn))

    ### READ PAGE TEXT AS DICTIONARY (BLOCKS == PARAGRAPHS)
    blocks = page.get_text("dict", flags=11)["blocks"]

    ### ITERATE THROUGH TEXT BLOCKS
    fn, fs, fc, ft = [], [], [], []
    for b in blocks:
        ### ITERATE THROUGH TEXT LINES
        for l in b["lines"]:
            ### ITERATE THROUGH TEXT SPANS
            for s in l["spans"]:
                fn.append(s["font"])
                fs.append(s["size"])
                fc.append(s["color"])
                ft.append(s["text"])

    d = {'Page': np.repeat(pn, len(fn)), 'Font': fn, 'Size': fs, 'Color': fc, 'Text': ft}
    df = pd.DataFrame (d, columns = ['Page', 'Font', 'Size', 'Color', 'Text'])

    return df
            

def get_proposal_info(doc):

    """
    PURPOSE:   grab PI name and proposal number from cover page
    INPUTS:    doc  = fitz Document object
    OUTPUTS:   pi_first = PI first name (str)
               pi_last = PI last name (str)
               pn = proposal number assigned by NSPIRES (str)

    """

    ### GET COVER PAGE
    cp = (get_text(doc, 0)).lower()

    ### TRY TO GET PI NAME
    ### WILL RETURN NOTHING IF NOT FULL NSPIRES PROPOSAL
    try:
        pi_name = ((cp[cp.index('principal investigator'):cp.index('e-mail address')]).split('\n')[1]).split(' ')
    except ValueError:
        return '', '', 'NO NSPIRES FRONT MATTER FOUND', 'Yes'

    ### OTHERWISE CONTINUE GETTING PROPOSAL INFO
    pi_first, pi_last = pi_name[0], pi_name[-1]
    pn = ((cp[cp.index('proposal number'):cp.index('nasa procedure for')]).split('\n')[1]).split(' ')[0]

    return pi_first, pi_last, pn, 'N/A'


def check_compliance(doc, ps, pe):

    """
    PURPOSE:   check font size and counts-per-inch 
    INPUTS:    doc = fitz Document object
               ps  = start page of proposal (int)
               pe  = end page of proposals (int)
    OUTPUTS:   mfs = median font size of proposal (int)
  
    """

    ### GRAB FONT SIZE & CPI PER LINE
    for i, val in enumerate(np.arange(ps, pe + 1)):
        t = get_text(doc, val)
        ln = t.split('\n')
        ln = [x for x in ln if len(x) > 50] ## TRY TO ONLY KEEP REAL LINES
        if i ==0:
            df = get_fonts(doc, val)
            cpi = [round(len(x)/6.5,2) for x in ln[2:-2]]  ### TRY TO AVOID HEADERS/FOOTERS
            lns, lpi = ln[2:-2], [round(len(ln)/9, 2)]
        else:
            df = pd.concat([df, get_fonts(doc, val)], ignore_index=True)
            cpi = cpi + [round(len(x)/6.5,2) for x in ln[2:-2]]
            lns = lns + ln[2:-2]
            lpi.append(round(len(ln)/9, 2))
    cpi, lns, lpi = np.array(cpi), np.array(lns), np.array(lpi)

    ### RETURN IF COULDN'T READ
    if len(df) == 0:
        return 0

    ### MEDIAN FONT SIZE (PRINT WARNING IF LESS THAN 12 PT)
    ### only use text > 50 characters (excludes random smaller text; see histograms for all)
    mfs = round(np.median(df[df['Text'].apply(lambda x: len(x) > 50)]["Size"]), 1)  
    if mfs <= 11.8:
        print("\n\tMedian font size:\t", str(mfs), '\n')
    else:
        print("\n\tMedian font size:\t" + str(mfs), '\n')

    ### MOST COMMON FONT TYPE USED
    # cft = Counter(df['Font'].values).most_common(1)[0][0]
    # print("\n\tMost common font:\t" + cft)

    ### COUNTS PER INCH
    cpi_max, lpi_max = 16.0, 5.5
    ind_cpi, ind_lpi = np.where(cpi > cpi_max), np.where(lpi > lpi_max)
    cpi, lns, lpi, pgs = cpi[ind_cpi], lns[ind_cpi], lpi[ind_lpi], (np.arange(ps, pe+1)+1)[ind_lpi].tolist()
    if len(lpi) >= 1:
        print(f"\tPages w/LPI > {lpi_max}:\tNumber of pages = {len(lpi)}\n\t\t\t\tLPI values = {lpi}\n\t\t\t\tPage numbers = {pgs}")
    else:
        print(f"\tPages w/LPI > {lpi_max}:\t None")
    if len(cpi) >= 1:
        print(f"\n\tLines w/CPI > {cpi_max}:\t Number of Lines = {len(cpi)}\n")
        [print('\t\t\t\t',textwrap.shorten(x, 60)) for x in lns]
        print("")
    else:
        print(f"\n\tLines w/CPI > {cpi_max}:\t None\n")

    ### PLOT HISTOGRAM OF FONTS
    mpl.rc('xtick', labelsize=10)
    mpl.rc('ytick', labelsize=10)
    mpl.rc('xtick.major', size=5, pad=7, width=2)
    mpl.rc('ytick.major', size=5, pad=7, width=2)
    mpl.rc('xtick.minor', width=2)
    mpl.rc('ytick.minor', width=2)
    mpl.rc('axes', linewidth=2)
    mpl.rc('lines', markersize=5)
    fig = plt.figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    ax.set_title("Median Font = " + str(mfs) + " pt", size=11)
    ax.set_xlabel('Font Size', size=10)
    ax.set_ylabel('Density', size=10)
    ax.axvspan(11.8, 12.2, alpha=0.5, color='gray')
    ax.hist(df["Size"], bins=np.arange(5.4, 18, 0.4), density=True)
    fig.savefig('./font_histogram', bbox_inches='tight', dpi=100)
    plt.close('all')

    return mfs, cpi, lns, lpi, pgs


# ====================== Main Code ========================

### PATH TO FULL ANONYMIZED PROPOSAL
parser = argparse.ArgumentParser()
parser.add_argument("PDF_Full_Path", type=str, help="path to full proposal PDF")
args = parser.parse_args()

### IDENTIFY STM PAGES AND REF PAGES OF PROPOSAL
Doc = fitz.open(args.PDF_Full_Path)
PI_First, PI_Last, Prop_Nb, Flg = get_proposal_info(Doc)
print(f'\n\t{Prop_Nb}\t{PI_Last}')

### GET PAGES OF S/T/M PROPOSAL
try:
    Page_Num, Page_Start, Page_End = get_pages(Doc, Flg)         
except RuntimeError:
    print("\tCould not read PDF")

### PRINT SOME TEXT TO CHECK
print("\n\tSample of first page:\t" + textwrap.shorten((get_text(Doc, Page_Start)[300:400]), 60))
print("\tSample of mid page:\t"     + textwrap.shorten((get_text(Doc, Page_Start + 8)[300:400]), 60))
print("\tSample of last page:\t"    + textwrap.shorten((get_text(Doc, Page_End)[300:400]), 60))  

### CHECK FONT/TEXT COMPLIANCE
Font_Size, CPI, CPI_Lines, LPI, LPI_Pages = check_compliance(Doc, Page_Start, Page_End)


   

