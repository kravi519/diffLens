package com.example.pacs008.model;

import java.math.BigDecimal;

/** New-gen (Java 16+) flat DTO of an accepted customer credit transfer, as stored in the PAYMENT table. */
public record CreditTransferDto(
        String messageId,
        String instructionId,
        String endToEndId,
        String uetr,
        BigDecimal amount,
        String currency,
        String settlementDate,
        String chargeBearer,
        String instructingAgentBic,
        String instructedAgentBic,
        String debtorName,
        String debtorAccount,
        String debtorAgentBic,
        String creditorName,
        String creditorAccount,
        String creditorAgentBic,
        String remittanceInfo) {
}
