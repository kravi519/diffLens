package com.example.pacs008.mapper;

import com.example.pacs008.model.CreditTransferDto;
import com.example.pacs008.model.Pacs008Message;
import com.example.pacs008.model.Pacs008Message.Party;
import com.example.pacs008.model.Pacs008Message.Transaction;

/** Legacy (Java 8) converter from a validated message to the flat {@link CreditTransferDto}. */
public class Pacs008DtoConverter {

    public CreditTransferDto convert(Pacs008Message message) {
        Transaction tx = message.transactions.get(0);
        CreditTransferDto dto = new CreditTransferDto();
        dto.setMessageId(message.groupHeader.msgId);
        dto.setInstructionId(tx.instrId);
        dto.setEndToEndId(tx.endToEndId);
        dto.setUetr(tx.uetr);
        dto.setAmount(tx.amount);
        dto.setCurrency(tx.currency);
        dto.setSettlementDate(tx.settlementDate);
        dto.setChargeBearer(tx.chargeBearer);
        dto.setInstructingAgentBic(tx.instructingAgentBic);
        dto.setInstructedAgentBic(tx.instructedAgentBic);
        dto.setDebtorName(name(tx.debtor));
        dto.setDebtorAccount(tx.debtorAccount);
        dto.setDebtorAgentBic(tx.debtorAgentBic);
        dto.setCreditorName(name(tx.creditor));
        dto.setCreditorAccount(tx.creditorAccount);
        dto.setCreditorAgentBic(tx.creditorAgentBic);
        dto.setRemittanceInfo(tx.unstructuredRemittance.isEmpty() ? null : tx.unstructuredRemittance.get(0));
        return dto;
    }

    private static String name(Party party) {
        return party == null ? null : party.name;
    }
}
