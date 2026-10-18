package com.example.pacs008.mapper;

import com.example.pacs008.model.CreditTransferDto;
import com.example.pacs008.model.Pacs008Message;
import com.example.pacs008.model.Pacs008Message.Party;
import java.util.Optional;

/** New-gen (Java 16+) converter from a validated message to the flat {@link CreditTransferDto}. */
public class Pacs008DtoConverter {

    public CreditTransferDto convert(Pacs008Message message) {
        var tx = message.transactions().get(0);
        return new CreditTransferDto(
                message.groupHeader().msgId(),
                tx.instrId(),
                tx.endToEndId(),
                tx.uetr(),
                tx.amount(),
                tx.currency(),
                tx.settlementDate(),
                tx.chargeBearer(),
                tx.instructingAgentBic(),
                tx.instructedAgentBic(),
                name(tx.debtor()),
                tx.debtorAccount(),
                tx.debtorAgentBic(),
                name(tx.creditor()),
                tx.creditorAccount(),
                tx.creditorAgentBic(),
                tx.unstructuredRemittance().stream().findFirst().orElse(null));
    }

    private static String name(Party party) {
        return Optional.ofNullable(party).map(Party::name).orElse(null);
    }
}
