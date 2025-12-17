"""Script for checking the compliance of proposals submitted to NSPIRES

Example:

python check_roses_compliance.py proposals/ _Redacted proposals.csv

"""


import sys, os, glob, re, pdb
import numpy as np
import pandas as pd
import argparse

import fitz 
fitz.TOOLS.mupdf_display_errors(False)


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


def get_median_font(doc, ps, pe, output=None):
    """
    PURPOSE:    check if median font used is valid

    INPUTS:     doc = fitz Document object
                ps = start page of STM section
                pe = end page of STM section
                output [optional] = if provided, print statements will be written to this file

    OUTPUTS:    n_brac = number bracketed references used
                n_etal = number  "et al." references used
    """

    ### GRAB FONT SIZE & CPI
    cpi = []
    for i, val in enumerate(np.arange(ps, pe)):
        cpi.append(len(get_text(doc, val)) / 44 / 6.5)
        if i ==0:
            df = get_fonts(doc, val)
        else:
            df = pd.concat([df, get_fonts(doc, val)], ignore_index=True)
    cpi = np.array(cpi)
       
    if len(df) == 0:
        return 0
       
    ### MEDIAN FONT SIZE (PRINT WARNING IF LESS THAN 12 PT)
    ### only use text > 50 characters (excludes random smaller text)
    mfs = round(np.median(df[df['Text'].apply(lambda x: len(x) > 50)]["Size"]), 1)
    if mfs <= 11.8:
        print("\n\tMed. font size: ", file=output)
    else:
        print("\n\tMed. font size: " + str(mfs), file=output)

    return mfs



def check_ref_type(doc, ps, pe, output=None):

    """
    PURPOSE:    check if proposal uses bracketed references rather than "et al." references

    INPUTS:     doc = fitz Document object
                ps = start page of STM section
                pe = end page of STM section
                output [optional] = if provided, print statements will be written to this file

    OUTPUTS:    n_brac = number bracketed references used
                n_etal = number  "et al." references used
    """

    ### GRAB TEXT OF STM SECTION
    tp = ''
    for n, nval in enumerate(np.arange(ps, pe)):    
        tp = tp + ' ' + get_text(doc, nval)
    tp = tp.lower()

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
        print("\n\t# [] refs:\t", str(n_brac), file=output)
        if n_para > 20:
            print("\tUsed () instead of []? # () refs:\t", str(n_para), file=output)
    else:
        print("\n\t# [] refs:\t", str(n_brac), file=output)
    if n_etal > 10:
        print("\t# et al. refs:\t", str(n_etal), '\n', file=output)
    else:
        print("\t# et al. refs:\t", str(n_etal), '\n', file=output)

    return n_brac, n_etal, n_para


def get_pages(d, stm_pl=15, output=None):

    """
    PURPOSE:    identify sections of proposal (STM, references, other)

    INPUTS:     d = fitz Document object
                stm_pl = number of pages in STM section (int; default=15)

    OUTPUTS:    stm_start = start page of STM section (int)
                stm_end = end page of STM section (int)
                ref_start = start page of references (int)
                ref_end = end page of references (int)
                pn = total number of pages (int)
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
        if (stm_start != -100) & (('reference' in t2) & ('reference' not in t1)) | (('bibliography' in t2) & ('bibliography' not in t1)) | (('citations' in t2) & ('citations' not in t1)):
            stm_end = val
            ref_start = val + 1

        ### FIND REF END
        w1, w2, w3, w4, w5, w6, w7, w8, w9 = 'redacted', 'summary of work effort', 'budget', 'budget narrative', 'total budget', 'table of work effort', 'data management', 'table of personnel', 'inclusion plan'
        if (ref_start != -100) & ((w1 in t2) & (w1 not in t1)) | ((w2 in t2) & (w2 not in t1)) | ((w3 in t2) & (w3 not in t1)) | ((w4 in t2) & (w4 not in t1)) | ((w5 in t2) & (w5 not in t1)) | ((w6 in t2) & (w6 not in t1)) | ((w7 in t2) & (w7 not in t1)) | ((w8 in t2) & (w8 not in t1)) | ((w9 in t2) & (w9 not in t1)):
            ref_end = val
            if (ref_start != -100) & (ref_end > ref_start) & (stm_end - stm_start > stm_pl-5):
                break
        ### FOR WHEN REFERENCES ARE AT VERY END OF DOC
        if (val == pn - 2) & (ref_start != -100) & ((ref_end == -100) | (ref_end < ref_start)):
            ref_end = val + 1

    ### FIX SOME THINGS BASED ON COMMON SENSE
    tcs = False
    tcr = False
    pFlag = ''
    if ref_end < ref_start:
        ### USE SIMPLE "BUDGET" FLAG IF WE HAVE TO
        ref_end = ref_end_bu
        if ref_end < ref_start:
            ref_end = -100
    if stm_end - stm_start <= 5:
        ### IF STM SECTION REALLY SHORT, ASSUME PTOT PAGES
        ptot = 15
        stm_end = np.min([stm_start+ptot-1, pn])
        tcs = True
    if (ref_end != -100) & (ref_start == -100) & (stm_end != -100):
        ### IF FOUND END BUT NOT START OF REFERENCES, ASSUME REFS START RIGHT AFTER STM
        ref_start = stm_end + 1
        tcr = True
    if ref_end == -100:
        ### IF COULDN'T FIND REF END, ASSUME GOES TO END OF PDF (SOMETIMES THIS IS TRUE)
        ref_end = pn-1
        tcr = True

    if tcr | tcs: pFlag = 'Yes'
    

    ### IF PROPOSAL INCOMPLETE (E.G., WITHDRAWN) RETURN NOTHING
    if pn - stm_start < 3:
        return [], [], 0, ''

    ### OTHERWISE, RETURN PAGE GUESSES
    else:
        print(f"\n\tPage Guesses:\n", file=output)
        print(f"\t\tSTM = {stm_start+1, stm_end+1}", file=output)
        print(f"\t\tRef = {ref_start+1, ref_end+1}", file=output)
        return [stm_start, stm_end], [ref_start, ref_end], pn, pFlag

def check_dapr_words(doc, ps_file, pn, stm_pages, ref_pages, output):
       
    ### LOAD PROPOSAL MASTER FILE FROM NSPIRES
    ### TRY-EXCEPT IS TO HANDLE BOTH CSV AND EXCEL FILES
    try:
        dfp = pd.read_csv(ps_file)
    except:
        dfp = pd.read_excel(ps_file)
       
    ### FIGURE OUT WHICH COLUMN NAMES TO USE (DIFFERENT BETWEEN DIVISIONS)
    colnames_pm = np.array([x.lower() for x in dfp.columns])
    colnames = np.array(['response number', 'pi last name', 'linked org', 'pi company name', 'pi city'])

    for i, val in enumerate(colnames):
        if val in colnames_pm:
            colnames[i] = dfp.columns.values[ np.where(colnames_pm == val)][0]
        elif (val not in colnames_pm) & (val == 'response number') & ('proposal number' in colnames_pm):
            colnames[i] = dfp.columns.values[np.where(colnames_pm == 'proposal number')][0]
        # ' Lorenzo Edit '
        elif (val not in colnames_pm) & (val == 'response number') & ('proposal #' in colnames_pm):
            colnames[i] = dfp.columns.values[np.where(colnames_pm == 'proposal #')][0]
        elif  (val not in colnames_pm) & ('pi' in val) & (val.replace('pi', '').strip() in colnames_pm):
            colnames[i] = dfp.columns.values[np.where(colnames_pm == val.replace('pi', '').strip())][0]
        else:
            pdb.set_trace()
            print(f"\n\tUnknown column name in Proposal Master: {val}")
            print(f"\tProposal Master column: {dfp.columns.values[0:10]}")
            print("\tQuitting program\n")
            sys.exit()



    ### CHECK IF MISMATCH BETWEEN PROPOSAL NUMBER PARSED FROM PDF FILE AND WHAT IS USED IN PROPOSAL MASTER
    if len (dfp[dfp[colnames[0]] == pn]) == 0:
        print("\n\tNo matches found in Proposal Master for this proposal number")
        print("\tCheck for differences in proposal number format between PDF filenames and Proposal Master")
        print(f"\tTest: {pn} vs. {dfp[colnames[0]][0]} --> Update Prop_Nb if needed")
        print("\tQuitting program\n")
        sys.exit()

    ### GET PI INFO (iNSPIRES FORMAT)
    pi_name = (dfp[dfp[colnames[0]] == pn][colnames[1]].values[0]).split(',')
    pi_orgs = (dfp[dfp[colnames[0]] == pn][colnames[2]].values[0]).split(', ')
    pi_orgs.append(dfp[dfp[colnames[0]] == pn][colnames[3]].values[0])
    pi_city = (dfp[dfp[colnames[0]] == pn][colnames[4]].values[0]).split(',')[0]


    ### GET OTHER TEAM MEMBER NAMES
    for i, val in enumerate(np.arange(14)+1):

        ### MATCH THE TEAM MEMBER COLUMN NAME (HAS CHANGED BETWEEN YEARS AND/OR DIVISIONS)
        if 'Member - 1 Member name; Role; Email; Relationship_org; Phone' in dfp.columns:
            col = f'Member - {val} Member name; Role; Email; Relationship_org; Phone'
            col_org = col
            idx = [0, 0, 3]
        elif 'Member - 1 Member SUID; Name; Role; Email; Organization; Phone' in dfp.columns:
            col = f"Member - {val} Member SUID; Name; Role; Email; Organization; Phone"
            col_org = col
            idx = [0, 1, 4]
            # Nazifa Edit
        elif 'Member - 1 Member name; SUID; Role; Email; Relationship_org; Phone' in dfp.columns:
            col = f'Member - {val} Member name; SUID; Role; Email; Relationship_org; Phone'
            col_org = col
            idx = [0, 0, 4]
        elif 'Member 1 Name' in dfp.columns:
            col = f'Member {val} Name'
            col_org = f'Member {val} Organization'
            idx = [0, 0, 0]

        else:
            print("Team member column name not found")
            sys.exit()

        ### GRAB INFO
        if col not in dfp.columns:
            break
        if pd.isnull(dfp[dfp[colnames[0]] == pn][col].values[0]):
            break
        else:
            tm_name = dfp[dfp[colnames[0]] == pn][col].values[idx[0]].split('; ')[idx[1]].split(', ')[0]
            #print("Team Member Name: " + str(tm_name))
            tm_orgs = dfp[dfp[colnames[0]] == pn][col_org].values[idx[0]].split('; ')[idx[2]].split(', ')[0]
            #print("Team Member Org: " + str(tm_orgs))

            pi_name.append(tm_name)
            pi_orgs.append(tm_orgs)

    ### CLEAN THINGS UP
    pi_orgs = np.unique(pi_orgs).tolist()
    pi_name = np.unique(pi_name).tolist()
    pi_city = np.unique(pi_city).tolist()
    if 'nan' in pi_orgs:
        pi_orgs.remove('nan')
    if '' in pi_orgs:
        pi_orgs.remove('')
    if ';' in pi_orgs:
        pi_orgs.remove(';')
    if 'THE' in pi_orgs:
      pi_orgs.remove('THE')

    ### GET ALL DAPR WORDS
    dw_gp = ['she', 'he', 'her', 'hers', 'his', 'him']
    dw = dw_gp + pi_orgs + pi_name + pi_city
    dw = np.unique(dw).tolist()

    ### GET PAGE NUMBERS WHERE DAPR WORDS APPEAR
    ### IGNORES REFERENCE SECTION, IF KNOWN
    dwp, dwc, dww, pjsf = [], [], [], -99
    for i, ival in enumerate(dw):

        ### SKIP IF EMPTY
        if pd.isnull(ival):
            continue

        ### ADD COVER PAGE TO SEARCH TO INCLUDE PROJECT SUMMARY
        pg_arr = np.sort(np.append(np.arange(stm_pages[0], doc.page_count), np.arange(0, 5)))

        ### LOOP THROUGH PAGES
        for n, nval in enumerate(pg_arr):

            ### SKIP REFERENCES
            if (nval >= np.min(ref_pages)) & (nval <= np.max(ref_pages)) & (np.min(ref_pages) > 5):
                continue

            ### SKIP IF FRONT-MATTER BUT NOT PROJECT SUMMARY
            ### SAVE PAGE OF PROJECT SUMMARY IF FOUND
            if (nval < 4) and ("SECTION VII - Project Summary" not in get_text(doc, nval)):
                continue
            if (nval < 4) and ("SECTION VII - Project Summary" in get_text(doc, nval)):
                pjs, pjsf = 'NSPIRES Project Summary on page', nval
            else:
                pjs = ''
            ### READ IN TEXT AND INDEX DAPR WORD
            tp = (get_text(doc, nval)).lower()
            wi = [[i.start(), i.end()] for i in re.finditer(r'\b' + re.escape(ival.lower()) + r'\b', tp)]


            ### ITERATE THROUGH INDEXES
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
                            print(f'\t"{ival}" found {len(wi)} times {pjs} on page {nval+1}', file=output)

                else:

                    ### ONLY SAVE FLAGS FOR FIRST OCCURENCE ON PAGE
                    if m == 0:
                        dwp.append(nval)
                        dwc.append(len(wi))
                        dww.append(ival)
                        print(f'\t"{ival}" found {len(wi)} times {pjs} on page {nval+1}', file=output)

    ### PRINT WARNING IF COULD NOT FIND PROJECT SUMMARY
    if pjsf == -99:
        print("\n\tCould not locate Project Summary")

    return dww, dwc, dwp, pi_name, pi_orgs




if __name__ == "__main__":
   ### GET ARGUMENTS
   ### NOTE PDF_SUFFIX USES "REMAINDER" SO IT CAN HANDLE STRINGS STARTING WITH "-"

   Description = """
   Script for checking compliance of proposals submitted to NSPIRES. 

   Provide the script with a directory of redacted proposals, a suffix for the 
   proposals, and a list of the unredacted information.  The script will review
   the proposals for compliance with ROSES format and DAPR requirements. It will
   check the font size, number of pages, and the apeparance of words that would
   deanonymize the proposal.  

   The script will write out to a csv file that results of the tests. An 
   optional text file may also be provided that where the results will be
   written. 

   The list of unredacted information should either be a csv or xsls file with
   the standard column headings produced by NSPIRES.
   """

   parser = argparse.ArgumentParser(description=Description)
   parser.add_argument("PDF_Path", type=str, help="path to anonymized proposal PDF")
   parser.add_argument("PDF_Suffix", type=str, help="suffix of anonymized proposal PDF (what is before .pdf but after proposal number)", nargs=argparse.REMAINDER)
   parser.add_argument("PM_Path", type=str, help="path to Proposal Master report as Excel or .csv file)")
   parser.add_argument("-o", "--output", type=str, help="optional output file to write stdout to", default=None)
   parser.add_argument("-p", "--page_limit", type=int, help="page limit for the STM section. Default is set to 15.", default=15)
   args = parser.parse_args()
   STM_PL = args.page_limit

   # Set up output file
   if args.output:
      output = open(args.output, 'w')
   else:
      output = None

   ### GET LIST OF PDF FILES
   ### CHANGE IF NRESS USED DIFFERENT SUFFIX
   PDF_Files = np.sort(glob.glob(os.path.join(args.PDF_Path, '*' + args.PDF_Suffix[0] + '.pdf')))
   if len(PDF_Files) == 0:
       print("\nNo files found in folder set by PDF_Path\nCheck directory path in PDF_Path and PDF suffix in PDF_Files\nQuitting program\n")
       sys.exit()

   ### GET PROPOSAL MASTER
   if os.path.isfile(args.PM_Path) == False:
       print("\nNo Proposal Master file found in path set by PS_File\nCheck path for Proposal Master\nQuitting program\n")
       sys.exit()

   ### ARRAYS TO FILL
   Prop_Nb_All, TMN_All, Font_Size_All, N_Brac_All, N_EtAl_All, N_Para_All, N_NonNumericRefs_All = [], [], [], [], [], [],[]
   STM_Pages_All, Ref_Pages_All, pFlag_All = [], [], []
   DW_All, DWC_All, DWP_All = [], [], []

   ### LOOP THROUGH ALL PROPOSALS
   for p, pval in enumerate(PDF_Files):

       # Determine the proposal number
       Prop_Nb = os.path.split(pval)[-1].split(args.PDF_Suffix[0])[0]
       if (args.PDF_Suffix[0]!='_Script'):
         if ('_' in Prop_Nb) and ('_2' not in Prop_Nb):
             Prop_Nb = os.path.split(pval)[-1].split('_')[0]
         elif "-DAPR" in Prop_Nb:
             Prop_Nb = os.path.split(pval)[-1].split(args.PDF_Suffix[0])[0].split('-DAPR')[0]

       print(f'\n\n\n\t{Prop_Nb}', file=output)


       ### GET PAGES OF PROPOSAL
       pval = str(pval)
       Doc = fitz.open(pval)
       STM_Pages, Ref_Pages, Tot_Pages, pFlag = get_pages(Doc, stm_pl=STM_PL)
       ### PRINT TO SCREEN (ACCOUNTING FOR ZERO-INDEXING)
       print("\n\tTotal pages = {},  Start page = {},   End page = {}".format(Tot_Pages, STM_Pages[0]+1, STM_Pages[1]+1), file=output)

       
       if Tot_Pages == 0:
           print(f'\n\tProposal incomplete, skipping', file=output)
           continue

       ### CHECK FONT SIZE COMPLIANCE 
       Font_Size = get_median_font(Doc, STM_Pages[0], STM_Pages[1], output = output)

       ### CHECK DAPR REFERENCING COMPLIANCE
       N_Brac, N_EtAl, N_Para = check_ref_type(Doc, STM_Pages[0], STM_Pages[1], output = output)

       ### CHECK DAPR WORDS (AND GRAB TEAM MEMBER NAMES)
       DW, DWC, DWP, TMN, TMC = check_dapr_words(Doc, args.PM_Path, Prop_Nb, STM_Pages, Ref_Pages, output = output)

       ### RECORD STUFF
       Prop_Nb_All.append(Prop_Nb)
       Font_Size_All.append(Font_Size)
       N_Brac_All.append(N_Brac)
       N_EtAl_All.append(N_EtAl)
       N_Para_All.append(N_Para)
       STM_Pages_All.append((np.array(STM_Pages) + 1).tolist())
       Ref_Pages_All.append((np.array(Ref_Pages) + 1).tolist())
       pFlag_All.append(pFlag)
       DW_All.append(DW)
       DWC_All.append(DWC)
       DWP_All.append((np.array(DWP) + 1).tolist())
       TMN_All.append(TMN)


   # Write out the results
   d = {'Prop_Nb': Prop_Nb_All, 'Team Members': TMN_All, 'Font Size': Font_Size_All,
        'N_Brac': N_Brac_All, 'N_EtAl':N_EtAl_All, 'N_Para':N_Para_All,
        'STM_Pages': STM_Pages_All, 'Ref Pages': Ref_Pages_All, 'Flag Pages': pFlag_All,
        'DAPR_Words': DW_All, 'DAPR_Word_Count': DWC_All, 'DAPR_Word_Pages': DWP_All}

   df = pd.DataFrame(data=d)
   df.to_csv('dapr_checks.csv', index=False)
