package com.example.pacs008.service;

import com.example.pacs008.model.CreditTransferDto;
import com.example.pacs008.model.ValidationError;
import java.util.List;

/** Outcome of processing one pacs.008 message: the model handed from the service to the view. */
public record ProcessingResult(Status status, List<ValidationError> errors, CreditTransferDto payment, int storedRows) {

    public enum Status { ACCEPTED, REJECTED }

    static ProcessingResult accepted(CreditTransferDto payment, int storedRows) {
        return new ProcessingResult(Status.ACCEPTED, List.of(), payment, storedRows);
    }

    static ProcessingResult rejected(List<ValidationError> errors, int storedRows) {
        return new ProcessingResult(Status.REJECTED, errors, null, storedRows);
    }

    public boolean hasError(String code) {
        return errors.stream().anyMatch(e -> e.code().equals(code));
    }
}
