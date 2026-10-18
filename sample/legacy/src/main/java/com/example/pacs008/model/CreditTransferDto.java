package com.example.pacs008.model;

import java.math.BigDecimal;

/** Legacy (Java 8) flat DTO of an accepted customer credit transfer, as stored in the PAYMENT table. */
public class CreditTransferDto {

    private String messageId;
    private String instructionId;
    private String endToEndId;
    private String uetr;
    private BigDecimal amount;
    private String currency;
    private String settlementDate;
    private String chargeBearer;
    private String instructingAgentBic;
    private String instructedAgentBic;
    private String debtorName;
    private String debtorAccount;
    private String debtorAgentBic;
    private String creditorName;
    private String creditorAccount;
    private String creditorAgentBic;
    private String remittanceInfo;

    public String getMessageId() {
        return messageId;
    }

    public void setMessageId(String messageId) {
        this.messageId = messageId;
    }

    public String getInstructionId() {
        return instructionId;
    }

    public void setInstructionId(String instructionId) {
        this.instructionId = instructionId;
    }

    public String getEndToEndId() {
        return endToEndId;
    }

    public void setEndToEndId(String endToEndId) {
        this.endToEndId = endToEndId;
    }

    public String getUetr() {
        return uetr;
    }

    public void setUetr(String uetr) {
        this.uetr = uetr;
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public void setAmount(BigDecimal amount) {
        this.amount = amount;
    }

    public String getCurrency() {
        return currency;
    }

    public void setCurrency(String currency) {
        this.currency = currency;
    }

    public String getSettlementDate() {
        return settlementDate;
    }

    public void setSettlementDate(String settlementDate) {
        this.settlementDate = settlementDate;
    }

    public String getChargeBearer() {
        return chargeBearer;
    }

    public void setChargeBearer(String chargeBearer) {
        this.chargeBearer = chargeBearer;
    }

    public String getInstructingAgentBic() {
        return instructingAgentBic;
    }

    public void setInstructingAgentBic(String instructingAgentBic) {
        this.instructingAgentBic = instructingAgentBic;
    }

    public String getInstructedAgentBic() {
        return instructedAgentBic;
    }

    public void setInstructedAgentBic(String instructedAgentBic) {
        this.instructedAgentBic = instructedAgentBic;
    }

    public String getDebtorName() {
        return debtorName;
    }

    public void setDebtorName(String debtorName) {
        this.debtorName = debtorName;
    }

    public String getDebtorAccount() {
        return debtorAccount;
    }

    public void setDebtorAccount(String debtorAccount) {
        this.debtorAccount = debtorAccount;
    }

    public String getDebtorAgentBic() {
        return debtorAgentBic;
    }

    public void setDebtorAgentBic(String debtorAgentBic) {
        this.debtorAgentBic = debtorAgentBic;
    }

    public String getCreditorName() {
        return creditorName;
    }

    public void setCreditorName(String creditorName) {
        this.creditorName = creditorName;
    }

    public String getCreditorAccount() {
        return creditorAccount;
    }

    public void setCreditorAccount(String creditorAccount) {
        this.creditorAccount = creditorAccount;
    }

    public String getCreditorAgentBic() {
        return creditorAgentBic;
    }

    public void setCreditorAgentBic(String creditorAgentBic) {
        this.creditorAgentBic = creditorAgentBic;
    }

    public String getRemittanceInfo() {
        return remittanceInfo;
    }

    public void setRemittanceInfo(String remittanceInfo) {
        this.remittanceInfo = remittanceInfo;
    }
}
