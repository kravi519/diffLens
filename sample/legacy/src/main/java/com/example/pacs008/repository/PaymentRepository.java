package com.example.pacs008.repository;

import com.example.pacs008.model.CreditTransferDto;

/** Persistence port for accepted credit transfers. */
public interface PaymentRepository {

    void save(CreditTransferDto payment) throws DuplicateKeyException;

    CreditTransferDto findById(String id);

    int count();
}
