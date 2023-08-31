# ============== Import Packages ================

import sys, os, glob, re, pdb
import numpy as np
import pandas as pd
import argparse
import fitz 
fitz.TOOLS.mupdf_display_errors(False)


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


def check_ref_type(doc, ps, pe):

    """
    PURPOSE:    check if proposal uses bracketed references rather than "et al." references

    INPUTS:     doc = fitz Document object
                ps = start page of STM section
                pe = end page of STM section

    OUTPUTS:    n_brac = number bracketed references used
                n_etal = number  "et al." references used
    """

    ### GRAB TEXT OF STM SECTION
    tp = ''
    for n, nval in enumerate(np.arange(ps, pe)):    
        tp = tp + ' ' + get_text(doc, nval)
    tp = tp.lower()

    ### CHECK FOR DAPR COMPLIANCE FOR REFERENCES

    ### GET NUMBER OF BRACKETED REFERENCES
    n_brac = 0
    i_brac = [i.start() for i in re.finditer(']', tp)]
    for i, val in enumerate(i_brac):
        if tp[val-1].isnumeric():
            n_brac += 1

    ### ALSO GET NUMBER OF POSSIBLE PARENTHETICAL REFERENCES
    ### MATCHES REQUIRE NUMBER WITHIN PARENTHASES < 200 (ASSUMES <200 REFS; HELPS CATCH YEARS IN PARENTHESIS)
    ### ValueError CATCHES SPECIAL CHARACTES THAT AREN'T ACTUALLY NUMBERS
    n_para = 0
    para_vals = [x for x in re.findall('\(([^)]+)', tp) if x.isnumeric()]
    for i, val in enumerate(para_vals):
        try:
            int(val)
        except ValueError:
            continue
        if int(val) < 200:
            n_para += 1

    ### CHECK FOR NUMBER OF ET AL REFERENCES
    n_etal = len([i.start() for i in re.finditer(r'\bet al\b', tp)])

    ### PRINT TO SCREEN
    if n_brac < 10:
        print("\n\t# [] refs:\t", str(n_brac))
        if n_para > 20:
            print("\tUsed () instead of []? # () refs:\t", str(n_para))
    else:
        print("\n\t# [] refs:\t", str(n_brac))
    if n_etal > 10:
        print("\t# et al. refs:\t", str(n_etal), '\n')
    else:
        print("\t# et al. refs:\t", str(n_etal), '\n')

    return n_brac, n_etal, n_para
        

def get_pages(d, rps, rpe):

    """
    PURPOSE:    identify sections of proposal (STM, references, other)

    INPUTS:     d = fitz Document object
                rps = start page of references in PDF (int)
                rpe = end page of references in PDF (int)

    OUTPUTS:    stm_start = start page of STM section (int)
                stm_end = end page of STM section (int)
                ref_start = start page of references (int)
                ref_end = end page of references (int)
                pn = total number of pages (int)
    """

    ### GET TOTAL NUMBER OF PAGES IN PDF
    pn = d.page_count

    if (rps == -99) & (rpe == -99):

        ### LOOP THROUGH PDF PAGES
        stm_start, stm_end, ref_start, ref_end, ref_end_bu = 0, -100, -100, -100, -100
        for i, val in enumerate(np.arange(5, pn-1)):
                
            ### READ IN TEXT FROM THIS PAGE AND NEXT PAGE
            t1 = get_text(d, val).replace('\n', '').replace('\t', ' ').replace('   ', ' ').replace('  ', ' ')[0:500]
            t2 = get_text(d, val + 1).replace('\n', '').replace('\t', ' ').replace('   ', ' ').replace('  ', ' ')[0:500]
            t1 = t1.lower()
            t2 = t2.lower()

            ### FIND START OF STM IF FULL NSPIRES PROPOSAL
            if ('section x - budget' in t1) & ('section x - budget' not in t2):
                stm_start = val + 1
                continue

            ### FIND STM END AND REFERENCES START
            if (stm_start != -100) & (('reference' in t2) & ('reference' not in t1)) | (('bibliography' in t2) & ('bibliography' not in t1)):
                stm_end = val
                ref_start = val + 1
                
            ### FIND REF END 
            # w1, w2, w3, w4, w5, w6, w7 = 'data management', 'budget justification', 'work plan', 'budget narrative', 'work effort', 'total budget'
            # if (ref_start != -100) & ((w1 in t2) & (w1 not in t1)) | ((w2 in t2) & (w2 not in t1)) | ((w3 in t2) & (w3 not in t1)) | ((w4 in t2) & (w4 not in t1)) | ((w5 in t2) & (w5 not in t1)) | ((w6 in t2) & (w6 not in t1)):
            w1, w2, w3, w4 = 'budget justification', 'budget narrative', 'total budget', 'table of work effort'
            if (ref_start != -100) & ((w1 in t2) & (w1 not in t1)) | ((w2 in t2) & (w2 not in t1)) | ((w3 in t2) & (w3 not in t1)) | ((w4 in t2) & (w4 not in t1)):
                ref_end = val
                if (ref_start != -100) & (ref_end > ref_start) & (stm_end - stm_start > 10):
                    break
        
        ### FIX SOME THINGS BASED ON COMMON SENSE
        if ref_end < ref_start:
            ### USE SIMPLE "BUDGET" FLAG IF WE HAVE TO
            ref_end = ref_end_bu
            if ref_end < ref_start:
                ref_end = -100
        if stm_end - stm_start <= 5:
            ### IF STM SECTION REALLY SHORT, ASSUME PTOT PAGES 
            ptot = 15
            stm_end = np.min([stm_start+ptot-1, pn])
        if (ref_end != -100) & (ref_start == -100) & (stm_end != -100):
            ### IF FOUND END BUT NOT START OF REFERENCES, ASSUME REFS START RIGHT AFTER STM
            ref_start = stm_end + 1
        if ref_end == -100:
            ### IF COULDN'T FIND REF END, ASSUME GOES TO END OF PDF (SOMETIMES THIS IS TRUE) 
            ref_end = pn-1

    else:

        stm_start, stm_end = 0, rps - 2
        ref_start, ref_end = rps - 1, rpe - 1

    ### IF PROPOSAL INCOMPLETE (E.G., WITHDRAWN) RETURN NOTHING
    if pn - stm_start < 3:
        return [], [], 0, ''

    ### OTHERWISE, RETURN PAGE GUESSES
    else:    
        print(f"\n\tPage Guesses:\n")
        print(f"\t\tSTM = {stm_start+1, stm_end+1}")
        print(f"\t\tRef = {ref_start+1, ref_end+1}")
        return [stm_start, stm_end], [ref_start, ref_end], pn


def get_team_info(team_info_path):

    """
    PURPOSE:    grab team member information
                (team member names, institutions, cities)
                from either csv file or NSPIRES-generated cover pages

    INPUTS:     doc = fitz Document object
                team_info_path = path to CSV file with team member info OR
                                 NSPIRES-generated PDF with team member info in front matter

    OUTPUTS:    names = last names of team members
                orgs = organizations of team members
                cities = cities of team members
    """

    ### LOAD TEAM INFO IF CVS FILE
    if team_info_path.split('.')[-1] == 'csv':

        ### LOAD CSV FILE
        df = pd.read_csv(team_info_path)

        ### GRAB INFO
        names, orgs, cities = [], [], []
        for i, val in enumerate(df['First Name']):
            names.append(df['Last Name'][i])
            orgs.append(df['Institution'][i])
            cities.append(df['City'][i])

    ### LOAD TEAM INFO IF PDF FROM NSPIRES
    ### THIS METHOD WILL NOT COLLECT CITIES
    if team_info_path.split('.')[-1] == 'pdf':

        ### LOAD PDF
        doc = fitz.open(team_info_path)

        ### GRAB INFO
        names, orgs, cities = [], [], []
        for i, val in enumerate(np.arange(0, doc.page_count)):

            ### LOAD PAGE TEXT
            cp = (get_text(doc, val)).lower()

            ### GRAB ALL TEAM MEMBER NAMES
            while 'team member name' in cp:
                cp = cp[cp.index('team member name'):]
                names.append(((cp[cp.index('team member name'):cp.index('contact phone')]).split('\n')[1]).split(' ')[-1])
                orgs.append(((cp[cp.index('organization/business relationship'):cp.index('cage code')]).split('\n')[1]))
                cp = cp[cp.index('total funds requested'):]
    
    ### CLEAN THINGS UP
    orgs = np.unique(orgs).tolist()
    names = np.unique(names).tolist()
    cities = np.unique(cities).tolist()
    if '' in orgs:
        orgs.remove('')

    return names, orgs, cities


def check_dapr_words(doc, names, orgs, cities, stm_pages, ref_pages, pdf_full_path):

    """
    PURPOSE:    check for DAPR violation words
                (team member names, institutions, cities)
                (gender pronouns)

    INPUTS:     doc = fitz Document object
                names = last names of team members
                orgs = organizations of team members
                cities = cities of team members
                stm_pages = [start, end] pages of STM section
                ref_pages = [start, end] pages of references section
                pdf_full_path = path to full pdf with team member info and project summary

    OUTPUTS:    dww = DAPR violation words that were found
                dwcc = number of times they were found
                dwp = pages of proposal on which they were found
    """

    ### COMBINE AND ADD GENDER PRONOUNS
    dw_gp = ['she', 'he', 'her', 'hers', 'his', 'him']
    dw = dw_gp + orgs + names + cities
    dw = np.unique(dw).tolist()

    ### READ IN FULL NSPIRE DOC
    ### USED FOR SEARCHING PROJECT SUMMARY
    doc2 = fitz.open(pdf_full_path)
    pg_arr = np.append(np.arange(stm_pages[0], doc.page_count), np.arange(0, 5))

    ### GET PAGE NUMBERS WHERE DAPR WORDS APPEAR
    ### IGNORES REFERENCE SECTION, IF KNOWN
    dwp, dwc, dww = [], [], []
    for i, ival in enumerate(dw):

        ### SKIP IF EMPTY
        if pd.isnull(ival):
            continue

        ### LOOP THROUGH PAGES
        for n, nval in enumerate(pg_arr):

            ### SKIP REFERENCES
            if (nval >= np.min(ref_pages)) & (nval <= np.max(ref_pages)) & (np.min(ref_pages) > 5):
                continue

            ### READ IN TEXT
            tp = (get_text(doc, nval)).lower()

            ### GET PROJECT SUMMARY FROM FULL NSPIRES PDF
            pjs = 'on pages'
            if (n > doc.page_count - 1):
                if ("SECTION VII - Project Summary" not in get_text(doc2, nval)):
                    continue
                if ("SECTION VII - Project Summary" in get_text(doc2, nval)):
                    pjs = 'in NSPIRES Project Summary on page'
                    tp = (get_text(doc2, nval)).lower()
                    tp = tp[tp.index('section vii - project summary'):]

            ### INDEX DAPR WORD
            wi = [[i.start(), i.end()] for i in re.finditer(r'\b' + re.escape(ival.lower()) + r'\b', tp)]

            ### LOOP THROUGH INDEXES
            for m, mval in enumerate(wi):
                ### CHECK IF GENDER PRONOUN CATCHES ARE ACTUALLY HE/SHE, HIM/HER, ETC.
                ### ONLY SAVE DW INFO IF NOT
                if ival in dw_gp:
                    if not (tp[mval[0]-1] == '/') | (tp[mval[1]] == '/'):

                        ### ONLY SAVE FLAGS FOR FIRST OCCURENCE ON PAGE
                        if m == 0:
                            dwp.append(nval)
                            dwc.append(len(wi)) 
                            dww.append(ival)
                            print(f'\t"{ival}" found {len(wi)} times {pjs} {nval+1}')

                else:

                    ### ONLY SAVE FLAGS FOR FIRST OCCURENCE ON PAGE
                    if m == 0:
                        dwp.append(nval)
                        dwc.append(len(wi)) 
                        dww.append(ival)      
                        print(f'\t"{ival}" found {len(wi)} times {pjs} {nval+1}')

    return dww, dwc, dwp


# ====================== Main Code ========================

### GET PATHS
parser = argparse.ArgumentParser()
parser.add_argument("PDF_Anon_Path", type=str, help="path to anonymized proposal PDF")
parser.add_argument("PDF_Full_Path", type=str, help="path to full proposals PDFs with team member info")
args = parser.parse_args()

### GET PROPOSALS (NEED TO CHECK IF ORDER HOLDS)
anon_pdfs = np.sort(glob.glob(args.PDF_Anon_Path+'/*.pdf'))
full_pdfs = np.sort(glob.glob(args.PDF_Full_Path+'/*.pdf'))

if len(anon_pdfs) != len(full_pdfs):
    print("\n\tNumber of anonymized and full proposals are not equal, exiting program\n")
    exit()

for i, val in enumerate(anon_pdfs):

    ### PRINT PROPOSALS BEING CONSIDERED
    print(f"\n\tChecking anonymized proposal:\t{anon_pdfs[i]}")
    print(f"\tAgainst team in full proposal:\t{full_pdfs[i]}")

    ### IDENTIFY STM PAGES AND REF PAGES OF PROPOSAL
    Doc = fitz.open(str(anon_pdfs[i]))
    STM_Pages, Ref_Pages, Tot_Pages = get_pages(Doc, -99, -99)

    ### CHECK DAPR REFERENCING COMPLIANCE
    N_Brac, N_EtAl, N_Para = check_ref_type(Doc, STM_Pages[0], STM_Pages[1])

    ### GRAB TEAM INFO
    Names, Orgs, Cities = get_team_info(str(full_pdfs[i]))

    ### CHECK DAPR WORDS COMPLIANCE
    DW, DWC, DWP = check_dapr_words(Doc, Names, Orgs, Cities, STM_Pages, Ref_Pages, str(full_pdfs[i]))
    print("\n\n\t==============")


