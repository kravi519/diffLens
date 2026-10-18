"""Generate the shared pacs.008 input messages: one valid template plus one variation per edge case.

Usage:  python tools/generate_pacs008_inputs.py [output dir]   (default: sample/inputs/pacs008)

To add an edge case, add an entry to VARIANTS (file name -> list of (old, new) text replacements on the
valid template), run this script, then add a row for it to sample/inputs/pacs008.csv.
"""
import re
import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "sample/inputs/pacs008"
OUT.mkdir(parents=True, exist_ok=True)

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<BusMsg>
  <AppHdr xmlns="urn:iso:std:iso:20022:tech:xsd:head.001.001.02">
    <Fr><FIId><FinInstnId><BICFI>BANKDEFFXXX</BICFI></FinInstnId></FIId></Fr>
    <To><FIId><FinInstnId><BICFI>CEDELULLXXX</BICFI></FinInstnId></FIId></To>
    <BizMsgIdr>MSG-0001</BizMsgIdr>
    <MsgDefIdr>pacs.008.001.08</MsgDefIdr>
    <BizSvc>swift.cbprplus.03</BizSvc>
    <CreDt>2026-01-26T10:00:00+01:00</CreDt>
  </AppHdr>
  <Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
    <FIToFICstmrCdtTrf>
      <GrpHdr>
        <MsgId>MSG-0001</MsgId>
        <CreDtTm>2026-01-26T10:00:00+01:00</CreDtTm>
        <NbOfTxs>1</NbOfTxs>
        <SttlmInf>
          <SttlmMtd>INDA</SttlmMtd>
          <SttlmAcct><Id><Othr><Id>12345</Id></Othr></Id></SttlmAcct>
        </SttlmInf>
      </GrpHdr>
      <CdtTrfTxInf>
        <PmtId>
          <InstrId>INSTR-0001</InstrId>
          <EndToEndId>E2E-0001</EndToEndId>
          <UETR>8a562c67-ca16-48ba-b074-65581be6f001</UETR>
        </PmtId>
        <IntrBkSttlmAmt Ccy="EUR">1000.00</IntrBkSttlmAmt>
        <IntrBkSttlmDt>2026-01-27</IntrBkSttlmDt>
        <ChrgBr>SHAR</ChrgBr>
        <InstgAgt><FinInstnId><BICFI>BANKDEFFXXX</BICFI></FinInstnId></InstgAgt>
        <InstdAgt><FinInstnId><BICFI>CEDELULLXXX</BICFI></FinInstnId></InstdAgt>
        <Dbtr><Nm>Acme GmbH</Nm><PstlAdr><StrtNm>Hauptstrasse</StrtNm><BldgNb>1</BldgNb><PstCd>60311</PstCd><TwnNm>Frankfurt</TwnNm><Ctry>DE</Ctry></PstlAdr></Dbtr>
        <DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct>
        <DbtrAgt><FinInstnId><BICFI>BANKDEFFXXX</BICFI></FinInstnId></DbtrAgt>
        <CdtrAgt><FinInstnId><BICFI>BNPAFRPPXXX</BICFI></FinInstnId></CdtrAgt>
        <Cdtr><Nm>Globex SA</Nm><PstlAdr><TwnNm>Paris</TwnNm><Ctry>FR</Ctry></PstlAdr></Cdtr>
        <CdtrAcct><Id><IBAN>FR7630006000011234567890189</IBAN></Id></CdtrAcct>
        <RmtInf><Ustrd>Invoice 2026-001</Ustrd></RmtInf>
      </CdtTrfTxInf>
    </FIToFICstmrCdtTrf>
  </Document>
</BusMsg>
"""

CHARGE = ('<ChrgsInf><Amt Ccy="EUR">5.00</Amt>'
          '<Agt><FinInstnId><BICFI>BANKDEFFXXX</BICFI></FinInstnId></Agt></ChrgsInf>')

INSTR_SLASH = ("<InstrId>INSTR-0001</InstrId>", "<InstrId>/INS//03</InstrId>")
COMMODITY = ('Ccy="EUR">1000.00', 'Ccy="XAU">1000.00')
NO_DEBTOR_NAME = ("<Nm>Acme GmbH</Nm>", "")

VARIANTS = {
    "p8_01_valid.xml": [],
    "p8_03_instrid_slash.xml": [INSTR_SLASH],
    "p8_04_commodity_currency.xml": [COMMODITY],
    "p8_05_cred_without_charges.xml": [("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>CRED</ChrgBr>")],
    "p8_06_debt_two_charges.xml": [("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>DEBT</ChrgBr>\n        " + CHARGE
                                    + "\n        " + CHARGE)],
    "p8_07_bah_from_mismatch.xml": [("<Fr><FIId><FinInstnId><BICFI>BANKDEFFXXX",
                                     "<Fr><FIId><FinInstnId><BICFI>OTHRGB2LXXX")],
    "p8_08_debtor_without_name.xml": [NO_DEBTOR_NAME],
    "p8_09_both_remittances.xml": [("</RmtInf>",
                                    "</RmtInf>\n        <RltdRmtInf><RmtId>REM-0001</RmtId></RltdRmtInf>")],
    "p8_10_instrid_too_long.xml": [("<InstrId>INSTR-0001</InstrId>", "<InstrId>INSTR-0001-ABCDEFGH</InstrId>")],
    "p8_11_unstructured_address.xml": [(
        "<Cdtr><Nm>Globex SA</Nm><PstlAdr><TwnNm>Paris</TwnNm><Ctry>FR</Ctry></PstlAdr>",
        "<Cdtr><Nm>Globex SA</Nm><PstlAdr><AdrLine>12 Rue de Rivoli</AdrLine>"
        "<AdrLine>75001 Paris France</AdrLine></PstlAdr>")],
    "p8_12_duplicate_instrid.xml": [("MSG-0001", "MSG-0002"), ("E2E-0001", "E2E-0002"),
                                    ("65581be6f001", "65581be6f002")],
    "p8_13_invalid_uetr.xml": [("8a562c67-ca16-48ba-b074-65581be6f001", "not-a-valid-uetr")],
    "p8_14_creditor_without_town.xml": [("<PstlAdr><TwnNm>Paris</TwnNm><Ctry>FR</Ctry></PstlAdr>",
                                         "<PstlAdr><Ctry>FR</Ctry></PstlAdr>")],
    "p8_15_multiple_errors.xml": [INSTR_SLASH, COMMODITY, NO_DEBTOR_NAME],
    "p8_16_invalid_settlement_method.xml": [("<SttlmMtd>INDA</SttlmMtd>", "<SttlmMtd>CLRG</SttlmMtd>")],
    "p8_18_second_payment.xml": [("MSG-0001", "MSG-0003"), ("INSTR-0001", "INSTR-0003"), ("E2E-0001", "E2E-0003"),
                                 ("65581be6f001", "65581be6f003"), ('Ccy="EUR">1000.00', 'Ccy="USD">250.50')],
}

CRED_ADDR = "<Cdtr><Nm>Globex SA</Nm><PstlAdr><TwnNm>Paris</TwnNm><Ctry>FR</Ctry></PstlAdr>"
VARIANTS.update({
    "p8_19_instrid_16_chars.xml": [("<InstrId>INSTR-0001</InstrId>", "<InstrId>INSTR-0001-ABCDE</InstrId>")],
    "p8_20_instrid_17_chars.xml": [("<InstrId>INSTR-0001</InstrId>", "<InstrId>INSTR-0001-ABCDEF</InstrId>")],
    "p8_21_instrid_trailing_slash.xml": [("<InstrId>INSTR-0001</InstrId>", "<InstrId>INSTR-0001/</InstrId>")],
    "p8_22_bic8.xml": [("BANKDEFFXXX", "BANKDEFF")],
    "p8_23_lowercase_bic.xml": [("CEDELULLXXX", "cedelullxxx")],
    "p8_24_zero_amount.xml": [('Ccy="EUR">1000.00', 'Ccy="EUR">0.00')],
    "p8_25_negative_amount.xml": [('Ccy="EUR">1000.00', 'Ccy="EUR">-5.00')],
    "p8_26_six_decimals.xml": [('Ccy="EUR">1000.00', 'Ccy="EUR">1.000001')],
    "p8_27_max_digits.xml": [('Ccy="EUR">1000.00', 'Ccy="EUR">999999999.99999')],
    "p8_28_too_many_digits.xml": [('Ccy="EUR">1000.00', 'Ccy="EUR">9999999999.99999')],
    "p8_29_lowercase_currency.xml": [('Ccy="EUR">1000.00', 'Ccy="eur">1000.00')],
    "p8_30_amount_not_a_number.xml": [('Ccy="EUR">1000.00', 'Ccy="EUR">1,000.00')],
    "p8_33_bizmsgidr_mismatch.xml": [("<BizMsgIdr>MSG-0001</BizMsgIdr>", "<BizMsgIdr>MSG-9999</BizMsgIdr>")],
    "p8_34_old_business_service.xml": [("swift.cbprplus.03", "swift.cbprplus.02")],
    "p8_35_debt_one_charge.xml": [("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>DEBT</ChrgBr>\n        " + CHARGE)],
    "p8_36_cred_with_charge.xml": [("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>CRED</ChrgBr>\n        " + CHARGE)],
    "p8_37_slev_charge_bearer.xml": [("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>SLEV</ChrgBr>")],
    "p8_38_debtor_anybic_only.xml": [("<Nm>Acme GmbH</Nm>", "<Id><OrgId><AnyBIC>ACMEDEFFXXX</AnyBIC></OrgId></Id>")],
    "p8_39_remittance_140_chars.xml": [("<Ustrd>Invoice 2026-001</Ustrd>", "<Ustrd>" + "R" * 140 + "</Ustrd>")],
    "p8_40_remittance_141_chars.xml": [("<Ustrd>Invoice 2026-001</Ustrd>", "<Ustrd>" + "R" * 141 + "</Ustrd>")],
    "p8_41_two_remittance_lines.xml": [("<Ustrd>Invoice 2026-001</Ustrd>",
                                        "<Ustrd>Invoice 2026-001</Ustrd><Ustrd>Invoice 2026-002</Ustrd>")],
    "p8_42_no_settlement_date.xml": [("        <IntrBkSttlmDt>2026-01-27</IntrBkSttlmDt>\n", "")],
    "p8_43_no_endtoend_id.xml": [("          <EndToEndId>E2E-0001</EndToEndId>\n", "")],
    "p8_44_uppercase_uetr.xml": [("8a562c67-ca16-48ba-b074-65581be6f001", "8A562C67-CA16-48BA-B074-65581BE6F001")],
    "p8_45_msgid_36_chars.xml": [("MSG-0001", "MSG-" + "0" * 32)],
    "p8_46_hybrid_address.xml": [(CRED_ADDR, "<Cdtr><Nm>Globex SA</Nm><PstlAdr><TwnNm>Paris</TwnNm><Ctry>FR</Ctry>"
                                             "<AdrLine>12 Rue de Rivoli</AdrLine></PstlAdr>")],
    "p8_47_doctype_xxe.xml": [('<?xml version="1.0" encoding="UTF-8"?>\n',
                               '<?xml version="1.0" encoding="UTF-8"?>\n'
                               '<!DOCTYPE BusMsg [<!ENTITY xxe SYSTEM "file:///c:/windows/win.ini">]>\n'),
                              ("<Ustrd>Invoice 2026-001</Ustrd>", "<Ustrd>&xxe;</Ustrd>")],
    "p8_49_wrong_message_type.xml": [("FIToFICstmrCdtTrf", "FICdtTrf")],
    "p8_50_duplicate_msgid.xml": [("INSTR-0001", "INSTR-0050"), ("E2E-0001", "E2E-0050"),
                                  ("65581be6f001", "65581be6f050")],
    "p8_52_padded_values.xml": [("<InstrId>INSTR-0001</InstrId>", "<InstrId>  INSTR-0001  </InstrId>")],
    "p8_53_no_namespaces.xml": [(' xmlns="urn:iso:std:iso:20022:tech:xsd:head.001.001.02"', ""),
                                (' xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"', "")],
    "p8_54_uetr_version_1.xml": [("8a562c67-ca16-48ba", "8a562c67-ca16-18ba")],
})

for name, replacements in VARIANTS.items():
    xml = TEMPLATE
    for old, new in replacements:
        assert xml.count(old) >= 1, (name, old)
        xml = xml.replace(old, new)
    (OUT / name).write_text(xml, encoding="utf-8")

# Two transactions in one message: CBPR+ allows single transactions only (NbOfTxs fixed value 1).
block = re.search(r"      <CdtTrfTxInf>.*?</CdtTrfTxInf>\n", TEMPLATE, re.S).group(0)
second = (block.replace("INSTR-0001", "INSTR-0002").replace("E2E-0001", "E2E-0002")
          .replace("65581be6f001", "65581be6f002"))
two_tx = TEMPLATE.replace("<NbOfTxs>1</NbOfTxs>", "<NbOfTxs>2</NbOfTxs>").replace(block, block + second)
(OUT / "p8_02_two_transactions.xml").write_text(two_tx, encoding="utf-8")

# Truncated message: not well-formed XML.
(OUT / "p8_17_malformed.xml").write_text(TEMPLATE[:TEMPLATE.index("<GrpHdr>")], encoding="utf-8")

# Header says one transaction, but the document carries none.
(OUT / "p8_31_no_transaction.xml").write_text(TEMPLATE.replace(block, ""), encoding="utf-8")

# Bare Document without the Business Application Header.
doc = re.search(r"  <Document .*?</Document>\n", TEMPLATE, re.S).group(0)
(OUT / "p8_32_no_bah.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + doc.replace("\n  ", "\n")[2:],
                                      encoding="utf-8")

# Empty request body.
(OUT / "p8_48_empty.xml").write_text("", encoding="utf-8")

print("\n".join(sorted(p.name for p in OUT.glob("*.xml"))))
