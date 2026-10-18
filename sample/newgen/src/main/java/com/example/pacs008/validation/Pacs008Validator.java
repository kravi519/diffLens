package com.example.pacs008.validation;

import com.example.pacs008.model.Pacs008Message;
import com.example.pacs008.model.Pacs008Message.AppHeader;
import com.example.pacs008.model.Pacs008Message.Party;
import com.example.pacs008.model.Pacs008Message.Transaction;
import com.example.pacs008.model.ValidationError;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * New-gen (Java 16+) business rules for CBPR+ pacs.008.001.08, OneClearstream SR2025 usage guideline:
 * CBL InstrId limit of 16 characters and structured postal addresses only (R49, from November 2025).
 */
public class Pacs008Validator {

    static final String BUSINESS_SERVICE = "swift.cbprplus.03";

    private static final Pattern BIC = Pattern.compile("[A-Z0-9]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?");
    private static final Pattern UETR =
            Pattern.compile("[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}");
    private static final Pattern FIN_X = Pattern.compile("[0-9a-zA-Z/\\-?:().,'+ ]+");
    private static final Pattern CURRENCY = Pattern.compile("[A-Z]{3}");
    private static final int MAX_TEXT_35 = 35;
    private static final int MAX_INSTRUCTION_ID = 16; // CBL usage: text{1,16}, unique per instruction
    private static final int MAX_UNSTRUCTURED = 140;
    private static final Set<String> SETTLEMENT_METHODS = Set.of("INDA", "INGA", "COVE");
    private static final Set<String> COMMODITIES = Set.of("XAU", "XAG", "XPD", "XPT");

    public List<ValidationError> validate(Pacs008Message message) {
        var group = message.groupHeader();
        if (group == null) {
            return List.of(new ValidationError("GRPHDR", "GrpHdr", "Group header is missing"));
        }
        var errors = new ArrayList<ValidationError>();
        check(errors, !matches(FIN_X, group.msgId()) || group.msgId().length() > MAX_TEXT_35,
                "MSGID", "GrpHdr/MsgId", "Mandatory, text{1,35} in the FIN-X character set");
        check(errors, !"1".equals(group.nbOfTxs()) || message.transactions().size() != 1,
                "NBOFTXS", "GrpHdr/NbOfTxs", "Single transactions only: NbOfTxs must be 1 and match the CdtTrfTxInf count");
        check(errors, !oneOf(group.settlementMethod(), SETTLEMENT_METHODS),
                "STTLMMTD", "GrpHdr/SttlmInf/SttlmMtd", "Must be INDA, INGA or COVE");

        var header = message.header();
        if (header == null) {
            errors.add(new ValidationError("BAH", "AppHdr", "Business Application Header is mandatory"));
        } else {
            check(errors, header.bizMsgIdr() == null || !header.bizMsgIdr().equals(group.msgId()),
                    "R5", "AppHdr/BizMsgIdr", "Must equal GrpHdr/MsgId");
            check(errors, !BUSINESS_SERVICE.equals(header.bizSvc()),
                    "R8", "AppHdr/BizSvc", "Must be " + BUSINESS_SERVICE);
            check(errors, !matches(BIC, header.fromBic()) || !matches(BIC, header.toBic()),
                    "BIC", "AppHdr/Fr|To", "BIC8 or BIC11 required");
        }

        message.transactions().forEach(tx -> validateTransaction(header, tx, errors));
        return errors;
    }

    private void validateTransaction(AppHeader header, Transaction tx, List<ValidationError> errors) {
        check(errors, header != null && (!equal(header.fromBic(), tx.instructingAgentBic())
                        || !equal(header.toBic(), tx.instructedAgentBic())),
                "R3", "CdtTrfTxInf/InstgAgt|InstdAgt", "BAH From/To BIC must match Instructing/Instructed Agent BIC");

        var instrId = tx.instrId();
        if (!matches(FIN_X, instrId) || instrId.length() > MAX_INSTRUCTION_ID) {
            errors.add(new ValidationError("INSTRID", "PmtId/InstrId",
                    "Mandatory for CBL, text{1," + MAX_INSTRUCTION_ID + "}"));
        } else {
            check(errors, instrId.startsWith("/") || instrId.endsWith("/") || instrId.contains("//"),
                    "R20", "PmtId/InstrId", "Must not start or end with '/' or contain '//'");
        }
        check(errors, !matches(FIN_X, tx.endToEndId()) || tx.endToEndId().length() > MAX_TEXT_35,
                "ENDTOENDID", "PmtId/EndToEndId", "Mandatory, use NOTPROVIDED if unknown");
        check(errors, !matches(UETR, tx.uetr()), "UETR", "PmtId/UETR", "Mandatory UUID v4");

        var amount = tx.amount();
        check(errors, amount == null || amount.signum() < 0 || amount.scale() > 5 || amount.precision() > 14,
                "AMOUNT", "IntrBkSttlmAmt", "0 <= decimal, td = 14, fd = 5");
        if (!matches(CURRENCY, tx.currency())) {
            errors.add(new ValidationError("CCY", "IntrBkSttlmAmt/@Ccy", "ISO 4217 currency code required"));
        } else {
            check(errors, COMMODITIES.contains(tx.currency()),
                    "R22", "IntrBkSttlmAmt/@Ccy", "XAU, XAG, XPD and XPT are not allowed");
        }
        check(errors, tx.settlementDate() == null,
                "STTLMDT", "IntrBkSttlmDt", "Interbank settlement date is mandatory");

        switch (tx.chargeBearer() == null ? "" : tx.chargeBearer()) {
            // Migration change: the mapper now returns an empty list, never null.
            case "CRED" -> check(errors, tx.charges() == null,
                    "R17", "ChrgsInf", "Charges information is mandatory when ChrgBr is CRED");
            case "DEBT" -> check(errors, tx.charges().size() > 1,
                    "R19", "ChrgsInf", "Only one ChrgsInf allowed when ChrgBr is DEBT");
            case "SHAR" -> { }
            default -> errors.add(new ValidationError("CHRGBR", "ChrgBr", "Must be DEBT, CRED or SHAR"));
        }

        check(errors, !matches(BIC, tx.instructingAgentBic()) || !matches(BIC, tx.instructedAgentBic())
                        || !optionalBic(tx.debtorAgentBic()) || !optionalBic(tx.creditorAgentBic()),
                "BIC", "CdtTrfTxInf/*Agt", "Agents must be identified with a valid BICFI");
        validateParty(tx.debtor(), "Dbtr", "R52", "R55", errors);
        validateParty(tx.creditor(), "Cdtr", "R67", "R73", errors);

        var remittance = tx.unstructuredRemittance();
        check(errors, tx.relatedRemittance() && !remittance.isEmpty(),
                "R15", "RmtInf|RltdRmtInf", "RltdRmtInf and RmtInf are mutually exclusive");
        check(errors, remittance.size() > 1 || remittance.stream().anyMatch(l -> l.length() > MAX_UNSTRUCTURED),
                "USTRD", "RmtInf/Ustrd", "At most one Ustrd of up to 140 characters");
    }

    private void validateParty(Party party, String path, String nameRule, String addressRule,
                               List<ValidationError> errors) {
        check(errors, party == null || (party.name() == null && party.anyBic() == null),
                nameRule, path + "/Nm", "Name is mandatory when AnyBIC is absent");
        if (party == null) {
            return;
        }
        check(errors, !optionalBic(party.anyBic()), "BIC", path + "/Id/OrgId/AnyBIC", "Invalid AnyBIC");
        var address = party.address();
        if (address == null) {
            return;
        }
        if (!address.addressLines().isEmpty()) {
            errors.add(new ValidationError("R49", path + "/PstlAdr/AdrLine",
                    "Structured address is mandatory from November 2025; AdrLine is no longer allowed"));
        } else {
            check(errors, address.townName() == null || address.country() == null,
                    addressRule, path + "/PstlAdr", "Structured address needs at least TwnNm and Ctry");
        }
    }

    private static void check(List<ValidationError> errors, boolean failed, String code, String path, String message) {
        if (failed) {
            errors.add(new ValidationError(code, path, message));
        }
    }

    private static boolean oneOf(String value, Set<String> allowed) {
        return value != null && allowed.contains(value);
    }

    private static boolean optionalBic(String bic) {
        return bic == null || BIC.matcher(bic).matches();
    }

    private static boolean matches(Pattern pattern, String value) {
        return value != null && pattern.matcher(value).matches();
    }

    private static boolean equal(String a, String b) {
        return a == null ? b == null : a.equals(b);
    }
}
