package com.example.pacs008.repository;

import com.example.pacs008.model.CreditTransferDto;
import java.util.Optional;

/** Persistence port for accepted credit transfers. */
public interface PaymentRepository {

    /** @throws DuplicateKeyException when the key is already stored */
    void save(CreditTransferDto payment);

    Optional<CreditTransferDto> findById(String id);

    int count();
}
