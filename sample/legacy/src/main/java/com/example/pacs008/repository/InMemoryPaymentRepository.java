package com.example.pacs008.repository;

import com.example.pacs008.model.CreditTransferDto;
import java.util.LinkedHashMap;
import java.util.Map;

/** Legacy virtual DB: a map standing in for the PAYMENT table, primary key MESSAGE_ID. */
public class InMemoryPaymentRepository implements PaymentRepository {

    private final Map<String, CreditTransferDto> table = new LinkedHashMap<String, CreditTransferDto>();

    @Override
    public synchronized void save(CreditTransferDto payment) throws DuplicateKeyException {
        if (table.containsKey(payment.getMessageId())) {
            throw new DuplicateKeyException("PAYMENT.MESSAGE_ID " + payment.getMessageId() + " already exists");
        }
        table.put(payment.getMessageId(), payment);
    }

    @Override
    public synchronized CreditTransferDto findById(String messageId) {
        return table.get(messageId);
    }

    @Override
    public synchronized int count() {
        return table.size();
    }
}
