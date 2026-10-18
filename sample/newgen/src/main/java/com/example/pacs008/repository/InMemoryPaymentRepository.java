package com.example.pacs008.repository;

import com.example.pacs008.model.CreditTransferDto;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * New-gen virtual DB: a concurrent map standing in for the PAYMENT table, unique key INSTRUCTION_ID
 * (CBL usage: InstrId must be unique for each instruction sent to Clearstream Banking).
 */
public class InMemoryPaymentRepository implements PaymentRepository {

    private final Map<String, CreditTransferDto> table = new ConcurrentHashMap<>();

    @Override
    public void save(CreditTransferDto payment) {
        if (table.putIfAbsent(payment.instructionId(), payment) != null) {
            throw new DuplicateKeyException("PAYMENT.INSTRUCTION_ID " + payment.instructionId() + " already exists");
        }
    }

    @Override
    public Optional<CreditTransferDto> findById(String instructionId) {
        return Optional.ofNullable(table.get(instructionId));
    }

    @Override
    public int count() {
        return table.size();
    }
}
