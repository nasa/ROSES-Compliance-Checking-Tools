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
    n_brac = len([i.start() for i in re.finditer(']', tp)])
    n_etal = len([i.start() for i in re.finditer('et al', tp)])
    print("\n\t# [] refs:\t", str(n_brac))
    print("\t# et al. refs:\t", str(n_etal), '\n')

    return n_brac, n_etal
        

def get_pages(d):

    """
    PURPOSE:    identify sections of proposal (STM, references, other)
    INPUTS:     d = fitz Document object
    OUTPUTS:    stm_start = start page of STM section
                stm_end = end page of STM section
                ref_start = start page of references
                ref_end = end page of references
                pn = total number of pages
    """

    ### GET TOTAL NUMBER OF PAGES IN PDF
    pn = d.page_count

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
                team_info_path = path to either CSV and PDR file with team member info
    OUTPUTS:    names = last names of team members
                orgs = organizations of team members
                cities = cities of team members
    """

    ### LOAD TEAM INFO IF CVS FILE
    if team_info_path.split('.')[-1] == 'csv':

        ### LOAD CSV FILE
        df = pd.read_csv(Team_Info_Path)

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
            cp = get_text(doc, val)

            ### GRAB ALL TEAM MEMBER NAMES
            while 'Team Member Name' in cp:
                cp = cp[cp.index('Team Member Name'):]
                names.append(((cp[cp.index('Team Member Name'):cp.index('Contact Phone')]).split('\n')[1]).split(' ')[-1])
                orgs.append(((cp[cp.index('Organization/Business Relationship'):cp.index('CAGE Code')]).split('\n')[1]))
                cp = cp[cp.index('Total Funds Requested'):]

    
    ### CLEAN THINGS UP
    orgs = np.unique(orgs).tolist()
    names = np.unique(names).tolist()
    cities = np.unique(cities).tolist()
    if '' in orgs:
        orgs.remove('')

    return names, orgs, cities


def check_dapr_words(doc, names, orgs, cities, stm_pages, ref_pages):

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
    OUTPUTS:    dww = DAPR violation words that were found
                dwcc = number of times they were found
                dwpp = pages of proposal on which they were found
    """

    ### COMBINE AND ADD GENDER PRONOUNS
    dw = [' she ', ' he ', ' her ', ' his ']
    dw = dw + orgs + names + cities
    dw = np.unique(dw).tolist()

    ### GET PAGE NUMBERS WHERE DAPR WORDS APPEAR
    ### IGNORES REFERENCE SECTION, IF KNOWN
    dwp = []
    for i, ival in enumerate(dw):
        if pd.isnull(ival):
            continue
        pn = []
        for n, nval in enumerate(np.arange(stm_pages[0], doc.page_count)):
            if (nval >= np.min(ref_pages)) & (nval <= np.max(ref_pages)) & (np.min(ref_pages) > 5):
                continue
            tp = (get_text(doc, nval)).lower()
            # if (' ' + ival.lower() + ' ' in tp) | (' ' + ival.lower() + "'" in tp) | (' ' + ival.lower() + "." in tp):
            if (ival.lower() in tp):
                pn.append(nval) 
        dwp.append(pn)

    ### RECORD NUMBER OF TIMES EACH WORD FOUND AND UNIQUE PAGE NUMBERS
    ### PRINT FINDINGS TO SCREEN
    dww, dwcc, dwpp = [], [], []
    for m, mval in enumerate(dwp):
        if len(mval) > 0:
             print(f'\t"{dw[m]}" found {len(mval)} times on pages {np.unique(mval)+1}')
             dww.append(dw[m])
             dwcc.append(len(mval))
             dwpp.append((np.unique(mval)+1).tolist())

    return dww, dwcc, dwpp


# ====================== Main Code ========================

### GET PATHS
parser = argparse.ArgumentParser()
parser.add_argument("PDF_Anon_Path", type=str, help="path to anonymized proposal PDF")
parser.add_argument("Team_Info_Path", type=str, help="path to team info (NSPIRES cover pages or .csv file)")
args = parser.parse_args()

### IDENTIFY STM PAGES AND REF PAGES OF PROPOSAL
Doc = fitz.open(args.PDF_Anon_Path)
STM_Pages, Ref_Pages, Tot_Pages = get_pages(Doc)

### CHECK DAPR REFERENCING COMPLIANCE
N_Brac, N_EtAl = check_ref_type(Doc, STM_Pages[0], STM_Pages[1])

### GRAB TEAM INFO
Names, Orgs, Cities = get_team_info(args.Team_Info_Path)

### CHECK DAPR WORDS COMPLIANCE
DW, DWC, DWP = check_dapr_words(Doc, Names, Orgs, Cities, STM_Pages, Ref_Pages)

