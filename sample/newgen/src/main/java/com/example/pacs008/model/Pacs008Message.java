package com.example.pacs008.model;

import java.math.BigDecimal;
import java.util.List;

/**
 * New-gen (Java 16+) immutable domain model of a CBPR+ pacs.008.001.08 business message: the Business
 * Application Header plus the FIToFICustomerCreditTransfer document.
 */
public record Pacs008Message(AppHeader header, GroupHeader groupHeader, List<Transaction> transactions) {

    /** Business Application Header (head.001.001.02). */
    public record AppHeader(String fromBic, String toBic, String bizMsgIdr, String msgDefIdr, String bizSvc,
                            String creationDate) {
    }

    /** GrpHdr. */
    public record GroupHeader(String msgId, String creationDateTime, String nbOfTxs, String settlementMethod,
                              String settlementAccount) {
    }

    /** CdtTrfTxInf. */
    public record Transaction(String instrId, String endToEndId, String uetr, BigDecimal amount, String currency,
                              String settlementDate, String chargeBearer, List<Charge> charges,
                              String instructingAgentBic, String instructedAgentBic, String debtorAgentBic,
                              String creditorAgentBic, Party debtor, String debtorAccount, Party creditor,
                              String creditorAccount, List<String> unstructuredRemittance,
                              boolean relatedRemittance) {
    }

    /** Dbtr / Cdtr. */
    public record Party(String name, String anyBic, PostalAddress address) {
    }

    /** PstlAdr. */
    public record PostalAddress(String streetName, String buildingNumber, String postCode, String townName,
                                String country, List<String> addressLines) {
    }

    /** ChrgsInf. */
    public record Charge(BigDecimal amount, String currency, String agentBic) {
    }
}
