package com.example.pacs008.validation;

import com.example.pacs008.model.Pacs008Message;
import com.example.pacs008.model.Pacs008Message.AppHeader;
import com.example.pacs008.model.Pacs008Message.GroupHeader;
import com.example.pacs008.model.Pacs008Message.Party;
import com.example.pacs008.model.Pacs008Message.PostalAddress;
import com.example.pacs008.model.Pacs008Message.Transaction;
import com.example.pacs008.model.ValidationError;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Legacy (Java 8) business rules for CBPR+ pacs.008.001.08, written against the pre-SR2025 rulebook:
 * InstrId up to 35 characters and unstructured (AdrLine) postal addresses still accepted.
 */
public class Pacs008Validator {

    static final String BUSINESS_SERVICE = "swift.cbprplus.03";

    private static final Pattern BIC = Pattern.compile("[A-Z0-9]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?");
    private static final Pattern UETR =
            Pattern.compile("[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}");
    private static final Pattern FIN_X = Pattern.compile("[0-9a-zA-Z/\\-?:().,'+ ]+");
    private static final Pattern CURRENCY = Pattern.compile("[A-Z]{3}");
    private static final int MAX_TEXT_35 = 35;
    private static final int MAX_INSTRUCTION_ID = 35;
    private static final int MAX_UNSTRUCTURED = 140;
    private static final List<String> SETTLEMENT_METHODS = Arrays.asList("INDA", "INGA", "COVE");
    private static final List<String> CHARGE_BEARERS = Arrays.asList("DEBT", "CRED", "SHAR");
    private static final List<String> COMMODITIES = Arrays.asList("XAU", "XAG", "XPD", "XPT");

    public List<ValidationError> validate(Pacs008Message message) {
        List<ValidationError> errors = new ArrayList<ValidationError>();
        GroupHeader group = message.groupHeader;
        if (group == null) {
            errors.add(new ValidationError("GRPHDR", "GrpHdr", "Group header is missing"));
            return errors;
        }
        if (!matches(FIN_X, group.msgId) || group.msgId.length() > MAX_TEXT_35) {
            errors.add(new ValidationError("MSGID", "GrpHdr/MsgId", "Mandatory, text{1,35} in the FIN-X character set"));
        }
        if (!"1".equals(group.nbOfTxs) || message.transactions.size() != 1) {
            errors.add(new ValidationError("NBOFTXS", "GrpHdr/NbOfTxs",
                    "Single transactions only: NbOfTxs must be 1 and match the CdtTrfTxInf count"));
        }
        if (!SETTLEMENT_METHODS.contains(group.settlementMethod)) {
            errors.add(new ValidationError("STTLMMTD", "GrpHdr/SttlmInf/SttlmMtd", "Must be INDA, INGA or COVE"));
        }

        AppHeader header = message.header;
        if (header == null) {
            errors.add(new ValidationError("BAH", "AppHdr", "Business Application Header is mandatory"));
        } else {
            if (header.bizMsgIdr == null || !header.bizMsgIdr.equals(group.msgId)) {
                errors.add(new ValidationError("R5", "AppHdr/BizMsgIdr", "Must equal GrpHdr/MsgId"));
            }
            if (!BUSINESS_SERVICE.equals(header.bizSvc)) {
                errors.add(new ValidationError("R8", "AppHdr/BizSvc", "Must be " + BUSINESS_SERVICE));
            }
            if (!matches(BIC, header.fromBic) || !matches(BIC, header.toBic)) {
                errors.add(new ValidationError("BIC", "AppHdr/Fr|To", "BIC8 or BIC11 required"));
            }
        }

        for (Transaction tx : message.transactions) {
            validateTransaction(header, tx, errors);
        }
        return errors;
    }

    private void validateTransaction(AppHeader header, Transaction tx, List<ValidationError> errors) {
        if (header != null && (!equal(header.fromBic, tx.instructingAgentBic)
                || !equal(header.toBic, tx.instructedAgentBic))) {
            errors.add(new ValidationError("R3", "CdtTrfTxInf/InstgAgt|InstdAgt",
                    "BAH From/To BIC must match Instructing/Instructed Agent BIC"));
        }
        if (!matches(FIN_X, tx.instrId) || tx.instrId.length() > MAX_INSTRUCTION_ID) {
            errors.add(new ValidationError("INSTRID", "PmtId/InstrId",
                    "Mandatory for CBL, text{1," + MAX_INSTRUCTION_ID + "}"));
        } else if (tx.instrId.startsWith("/") || tx.instrId.endsWith("/") || tx.instrId.contains("//")) {
            errors.add(new ValidationError("R20", "PmtId/InstrId", "Must not start or end with '/' or contain '//'"));
        }
        if (!matches(FIN_X, tx.endToEndId) || tx.endToEndId.length() > MAX_TEXT_35) {
            errors.add(new ValidationError("ENDTOENDID", "PmtId/EndToEndId", "Mandatory, use NOTPROVIDED if unknown"));
        }
        if (!matches(UETR, tx.uetr)) {
            errors.add(new ValidationError("UETR", "PmtId/UETR", "Mandatory UUID v4"));
        }
        if (tx.amount == null || tx.amount.signum() < 0 || tx.amount.scale() > 5 || tx.amount.precision() > 14) {
            errors.add(new ValidationError("AMOUNT", "IntrBkSttlmAmt", "0 <= decimal, td = 14, fd = 5"));
        }
        if (!matches(CURRENCY, tx.currency)) {
            errors.add(new ValidationError("CCY", "IntrBkSttlmAmt/@Ccy", "ISO 4217 currency code required"));
        } else if (COMMODITIES.contains(tx.currency)) {
            errors.add(new ValidationError("R22", "IntrBkSttlmAmt/@Ccy", "XAU, XAG, XPD and XPT are not allowed"));
        }
        if (tx.settlementDate == null) {
            errors.add(new ValidationError("STTLMDT", "IntrBkSttlmDt", "Interbank settlement date is mandatory"));
        }
        if (!CHARGE_BEARERS.contains(tx.chargeBearer)) {
            errors.add(new ValidationError("CHRGBR", "ChrgBr", "Must be DEBT, CRED or SHAR"));
        } else if ("CRED".equals(tx.chargeBearer) && tx.charges.isEmpty()) {
            errors.add(new ValidationError("R17", "ChrgsInf", "Charges information is mandatory when ChrgBr is CRED"));
        } else if ("DEBT".equals(tx.chargeBearer) && tx.charges.size() > 1) {
            errors.add(new ValidationError("R19", "ChrgsInf", "Only one ChrgsInf allowed when ChrgBr is DEBT"));
        }
        if (!matches(BIC, tx.instructingAgentBic) || !matches(BIC, tx.instructedAgentBic)
                || !optionalBic(tx.debtorAgentBic) || !optionalBic(tx.creditorAgentBic)) {
            errors.add(new ValidationError("BIC", "CdtTrfTxInf/*Agt", "Agents must be identified with a valid BICFI"));
        }
        validateParty(tx.debtor, "Dbtr", "R52", "R55", errors);
        validateParty(tx.creditor, "Cdtr", "R67", "R73", errors);
        if (tx.relatedRemittance && !tx.unstructuredRemittance.isEmpty()) {
            errors.add(new ValidationError("R15", "RmtInf|RltdRmtInf", "RltdRmtInf and RmtInf are mutually exclusive"));
        }
        boolean tooLong = false;
        for (String line : tx.unstructuredRemittance) {
            tooLong |= line.length() > MAX_UNSTRUCTURED;
        }
        if (tx.unstructuredRemittance.size() > 1 || tooLong) {
            errors.add(new ValidationError("USTRD", "RmtInf/Ustrd", "At most one Ustrd of up to 140 characters"));
        }
    }

    private void validateParty(Party party, String path, String nameRule, String addressRule,
                               List<ValidationError> errors) {
        if (party == null || (party.name == null && party.anyBic == null)) {
            errors.add(new ValidationError(nameRule, path + "/Nm", "Name is mandatory when AnyBIC is absent"));
        }
        if (party != null && !optionalBic(party.anyBic)) {
            errors.add(new ValidationError("BIC", path + "/Id/OrgId/AnyBIC", "Invalid AnyBIC"));
        }
        PostalAddress address = party == null ? null : party.address;
        if (address != null && address.addressLines.isEmpty()
                && (address.townName == null || address.country == null)) {
            errors.add(new ValidationError(addressRule, path + "/PstlAdr",
                    "Structured address needs at least TwnNm and Ctry"));
        }
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
