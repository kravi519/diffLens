package com.example.pacs008.model;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * Legacy (Java 8) domain model of a CBPR+ pacs.008.001.08 business message: the Business Application
 * Header plus the FIToFICustomerCreditTransfer document. Mutable holders filled in by the mapper.
 */
public class Pacs008Message {

    public AppHeader header;
    public GroupHeader groupHeader;
    public final List<Transaction> transactions = new ArrayList<Transaction>();

    /** Business Application Header (head.001.001.02). */
    public static class AppHeader {
        public String fromBic;
        public String toBic;
        public String bizMsgIdr;
        public String msgDefIdr;
        public String bizSvc;
        public String creationDate;
    }

    /** GrpHdr. */
    public static class GroupHeader {
        public String msgId;
        public String creationDateTime;
        public String nbOfTxs;
        public String settlementMethod;
        public String settlementAccount;
    }

    /** CdtTrfTxInf. */
    public static class Transaction {
        public String instrId;
        public String endToEndId;
        public String uetr;
        public BigDecimal amount;
        public String currency;
        public String settlementDate;
        public String chargeBearer;
        public final List<Charge> charges = new ArrayList<Charge>();
        public String instructingAgentBic;
        public String instructedAgentBic;
        public String debtorAgentBic;
        public String creditorAgentBic;
        public Party debtor;
        public String debtorAccount;
        public Party creditor;
        public String creditorAccount;
        public final List<String> unstructuredRemittance = new ArrayList<String>();
        public boolean relatedRemittance;
    }

    /** Dbtr / Cdtr. */
    public static class Party {
        public String name;
        public String anyBic;
        public PostalAddress address;
    }

    /** PstlAdr. */
    public static class PostalAddress {
        public String streetName;
        public String buildingNumber;
        public String postCode;
        public String townName;
        public String country;
        public final List<String> addressLines = new ArrayList<String>();
    }

    /** ChrgsInf. */
    public static class Charge {
        public BigDecimal amount;
        public String currency;
        public String agentBic;
    }
}
